#!/usr/bin/env python3
"""Reject provider fallback against the newest tracked release's component pair.

Run in an initialized BitBake build directory with --template NAME. No network
manifest or template preference is used as the expected version oracle.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PACKAGES = ("iotedge", "aziot-edged", "aziotd", "aziotctl", "aziot-keys")
TEMPLATE_LINES = {"kirkstone": "1.5", "scarthgap": "1.5", "wrynose": "1.6", "scarthgap-1.6": "1.6"}
VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?")


def version_key(value):
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ValueError(f"Invalid release version: {value!r}")
    major, minor, patch, pre = match.groups()
    identifiers = tuple((0, int(p)) if p.isdigit() else (1, p) for p in (pre or "").split("."))
    return int(major), int(minor), int(patch), pre is None, identifiers


def assignments(text):
    """Read literal assignments (also expanded bitbake -e output, not history)."""
    return dict(re.findall(r'^(?:export )?([A-Za-z0-9_:+.\-]+)\s*=\s*"([^"\n]*)"\s*$', text, re.M))


def expected_selection(root, template):
    root = Path(root)
    if template not in TEMPLATE_LINES:
        raise ValueError(f"Unknown template: {template}")
    tracked = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z", "recipes-core"], text=True).split("\0")
    files = set(tracked)

    def read(path):
        if path not in files:
            raise ValueError(f"Missing tracked release metadata: {path}")
        return assignments((root / path).read_text())

    candidates = []
    for path in files:
        match = re.fullmatch(r"recipes-core/iotedge/iotedge-([0-9][^/]*)\.inc", path)
        if path.endswith("-crates.inc") or not match or not VERSION_RE.fullmatch(match[1]):
            continue  # Never treat a -crates.inc as release metadata.
        values = read(path)
        if values.get("VERSION") != match[1]:
            raise ValueError(f"{path}: filename/VERSION mismatch")
        release = values.get("IOTEDGE_RELEASE", "")
        key = version_key(release)
        if ".".join(map(str, key[:2])) == TEMPLATE_LINES[template]:
            candidates.append((key, path, values))
    if not candidates:
        raise ValueError(f"No tracked release metadata for {template}")
    newest_key, _, edge = max(candidates)
    if sum(key == newest_key for key, _, _ in candidates) != 1:
        raise ValueError(f"Ambiguous release metadata for {edge['IOTEDGE_RELEASE']}")
    edge_version = edge["VERSION"]
    # Match the committed fetcher refs, not a guessed IIS version or a network
    # re-resolution of a tag. Older pins can name annotated tag objects; -e
    # exposes that literal SRCREV, not necessarily the peeled Git commit.
    iis_ref = edge["IIS_SRCREV"]
    packages = {}
    for package in PACKAGES:
        if package in ("iotedge", "aziot-edged"):
            version = edge_version
            inc = read(f"recipes-core/{package}/{package}-{version}.inc")
            for variable in ("VERSION", "IOTEDGE_RELEASE", "IIS_SRCREV"):
                if inc.get(variable) != edge[variable]:
                    raise ValueError(f"{package}: inconsistent {variable} for release {edge['IOTEDGE_RELEASE']}")
            source = read(f"recipes-core/{package}/{package}_{version}.bb")["SRCREV"]
            packages[package] = {"PV": version, "SRCREV": source, **inc}
        else:
            matches = []
            for path in files:
                match = re.fullmatch(rf"recipes-core/{package}/{package}_([^/]+)\.bb", path)
                if match and read(path).get("SRCREV") == iis_ref:
                    version = match[1]
                    inc = read(f"recipes-core/{package}/{package}-{version}.inc")
                    if inc.get("VERSION") != version:
                        raise ValueError(f"{package}: filename/VERSION mismatch")
                    matches.append({"PV": version, "SRCREV": iis_ref, **inc})
            if len(matches) != 1:
                raise ValueError(f"{package}: expected exactly one recipe matching IIS_SRCREV {iis_ref}, found {len(matches)}")
            packages[package] = matches[0]
    if packages["iotedge"]["SRCREV"] != packages["aziot-edged"]["SRCREV"]:
        raise ValueError("Edge CLI and daemon source revisions disagree")
    if len({packages[p]["PV"] for p in PACKAGES[2:]}) != 1:
        raise ValueError("IIS component recipe versions disagree")
    return {"release": edge["IOTEDGE_RELEASE"], "template": template, "packages": packages}


def verify_release_tag(expected, tag):
    """A release archive's tag must describe the selected product and Yocto line."""
    match = re.fullmatch(
        r"(1\.[56]\.\d+(?:-(?:beta|rc)\.\d+)?)(?:-([1-9]\d*))?(?:-(scarthgap)(?:\.[1-9]\d*)?)?", tag
    )
    if not match or (match[2] and match[3]):
        raise ValueError(f"Unsupported release tag: {tag!r}")
    product = match[1]
    template = "scarthgap-1.6" if match[3] else "wrynose" if product.startswith("1.6.") else "scarthgap"
    if product != expected["release"] or template != expected["template"]:
        raise ValueError(f"Release tag {tag} does not match selected product {expected['release']} / {expected['template']}")


def verify_environments(expected, environments):
    """Assert expanded provider metadata, returning expected RPM VERSIONs."""
    versions = {}
    for package, intended in expected["packages"].items():
        actual = environments.get(package, {})
        for variable, value in {"PN": package, **intended}.items():
            if actual.get(variable) != value:
                raise ValueError(f"{package}: {variable} expected {value!r}, selected {actual.get(variable)!r}")
        if actual.get("PKGV") != intended["PV"]:
            raise ValueError(f"{package}: PKGV does not match intended PV {intended['PV']}")
        repo = "iotedge" if package in PACKAGES[:2] else "iot-identity-service"
        urls = actual.get("SRC_URI", "").split()
        if not any(re.fullmatch(rf"(?:git|gitsm)://github\.com/Azure/{repo}(?:\.git)?(?:;[^ ]*)?", url) for url in urls):
            raise ValueError(f"{package}: missing expected upstream {repo} source")
        if package in PACKAGES[:2]:
            if not any(re.fullmatch(r"git://github\.com/Azure/iot-identity-service(?:\.git)?;.*", url) for url in urls):
                raise ValueError(f"{package}: missing embedded IIS source")
            for name, value in actual.items():
                if name.startswith("SRCREV_") and name != "SRCREV_FORMAT" and value != intended["IIS_SRCREV"]:
                    raise ValueError(f"{package}: {name} does not match IIS_SRCREV")
            for url in urls:
                if "github.com/Azure/iot-identity-service" in url:
                    name = re.search(r";name=([^;]+)", url)
                    if not name or actual.get("SRCREV_" + name[1]) != intended["IIS_SRCREV"]:
                        raise ValueError(f"{package}: missing/mismatched named IIS source revision: {url}")
        # package_rpm converts hyphens in the provider/package version to '+'.
        versions[package] = actual["PKGV"].replace("-", "+")
    return versions


def verify_installed(expected, rpm_versions, cli_output, inventory):
    cli_version = expected["packages"]["iotedge"]["VERSION"]
    if cli_output.strip() != f"iotedge {cli_version}":
        raise ValueError(f"iotedge --version expected 'iotedge {cli_version}', got {cli_output.strip()!r}")
    installed = {}
    for line in inventory.splitlines():
        fields = line.split()
        if len(fields) != 2 or fields[0] in installed:
            raise ValueError(f"Invalid or duplicate installed RPM record: {line!r}")
        installed[fields[0]] = fields[1]
    for package, version in rpm_versions.items():
        if installed.get(package) != version:
            raise ValueError(f"Installed {package}: expected RPM version {version!r}, got {installed.get(package)!r}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--template", required=True, choices=TEMPLATE_LINES)
    parser.add_argument("--release-tag", default=os.environ.get("RELEASE_TAG", ""))
    parser.add_argument("--iotedge-version-file", type=Path)
    parser.add_argument("--rpm-versions-file", type=Path, help="rpm -q --qf '%%{NAME} %%{VERSION}\\n' for the five runtime packages")
    args = parser.parse_args()
    if bool(args.iotedge_version_file) != bool(args.rpm_versions_file):
        parser.error("installed validation requires both --iotedge-version-file and --rpm-versions-file")
    try:
        expected = expected_selection(args.root, args.template)
        if args.release_tag:
            verify_release_tag(expected, args.release_tag)
        environments = {package: assignments(subprocess.check_output(["bitbake", "-e", package], text=True)) for package in PACKAGES}
        versions = verify_environments(expected, environments)
        if args.iotedge_version_file:
            verify_installed(expected, versions, args.iotedge_version_file.read_text(), args.rpm_versions_file.read_text())
        print(json.dumps({**expected, "rpm_versions": versions}, indent=2, sort_keys=True))
        return 0
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Release selection verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
