#!/usr/bin/env python3
"""Shared, offline-testable product manifest resolution for recipe maintenance."""
import json
from pathlib import Path
import re
import sys


def version_key(version):
    """Strict SemVer ordering, including numeric prerelease identifiers."""
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?", version or "")
    if not match:
        raise ValueError(f"Invalid version: {version!r}")
    major, minor, patch, pre = match.groups()
    identifiers = pre.split(".") if pre else []
    if any(p.isdigit() and len(p) > 1 and p.startswith("0") for p in identifiers):
        raise ValueError(f"Invalid version: {version!r}")
    prerelease = tuple((0, int(p)) if p.isdigit() else (1, p) for p in identifiers)
    return (int(major), int(minor), int(patch), not bool(pre), prerelease)


def resolve_release(data, release):
    """Resolve an exact product, never the first product of its channel."""
    matches = [p for channel in data["channels"] for p in channel["products"]
               if p.get("id") == "aziot-edge" and p.get("version") == release]
    if not matches:
        raise ValueError(f"Unknown release: {release}")
    version_key(release)
    pairs = set()
    for product in matches:
        components = {}
        for component in product["components"]:
            name, version = component["name"], component["version"]
            if name in components and components[name] != version:
                raise ValueError(f"Conflicting component {name} for release: {release}")
            components[name] = version
        daemon, iis = components["aziot-edge"], components["aziot-identity-service"]
        if version_key(daemon)[:2] != version_key(release)[:2] or version_key(iis)[:2] != version_key(release)[:2]:
            raise ValueError(f"Conflicting component line for release: {release}")
        pairs.add((daemon, iis))
    if len(pairs) != 1:
        raise ValueError(f"Conflicting products for release: {release}")
    return pairs.pop()


TEMPLATES = {"1.5": ("scarthgap", "kirkstone"), "1.6": ("wrynose", "scarthgap-1.6")}
EDGE_PACKAGES = ("iotedge", "aziot-edged")
IIS_PACKAGES = ("aziotd", "aziotctl", "aziot-keys")


def validate_template(template, daemon, iis):
    """Reject cross-line generation before any cleanup or repository writes."""
    line = ".".join(daemon.split(".")[:2])
    if line not in TEMPLATES or template not in TEMPLATES[line]:
        raise ValueError(f"Template {template!r} does not support daemon {daemon}")
    return line


def update_template_versions(root, template, daemon, iis):
    """Update existing exact selectors in every template for this product line."""
    line = validate_template(template, daemon, iis)
    paths = []
    for name in TEMPLATES[line]:
        path = Path(root) / "conf/templates" / name / "local.conf.sample"
        text = path.read_text()
        for package in EDGE_PACKAGES + IIS_PACKAGES:
            version = daemon if package in EDGE_PACKAGES else iis
            text, count = re.subn(rf'^(PREFERRED_VERSION_{re.escape(package)}\s*=\s*)"[^"]+"',
                                  lambda m: f'{m[1]}"{version}"', text, flags=re.M)
            if count != 1:
                raise ValueError(f"Expected one exact selector for {package} in {path}")
        paths.append((path, text))
    for path, text in paths:
        path.write_text(text)


def current_version(root, package, line):
    """Highest recipe version on one maintained line (final > prerelease)."""
    versions = [p.stem.removeprefix(f"{package}_")
                for p in (Path(root) / "recipes-core" / package).glob(f"{package}_{line}.*.bb")]
    return max(versions, key=version_key) if versions else ""


def release_plans(data, root):
    """One deterministic plan per supported LTS product, newest line first."""
    products = {}
    for channel in data["channels"]:
        if channel["name"] != "lts":
            continue
        for product in channel["products"]:
            if product.get("id") != "aziot-edge":
                continue
            release = product["version"]
            version_key(release)
            line = ".".join(release.split(".")[:2])
            if line not in TEMPLATES:
                continue
            daemon, iis = resolve_release(data, release)
            if line not in products or version_key(release) > version_key(products[line][0]):
                products[line] = release, daemon, iis
    if not products:
        raise ValueError("No supported LTS aziot-edge products found")
    plans = []
    for line in sorted(products, reverse=True):
        release, daemon, iis = products[line]
        current = current_version(root, "iotedge", line)
        current_iis = current_version(root, "aziotd", line)
        current_release = current
        if current:
            inc = Path(root) / f"recipes-core/iotedge/iotedge-{current}.inc"
            if inc.exists():
                matches = re.findall(r'^IOTEDGE_RELEASE\s*=\s*"([^"]+)"', inc.read_text(), re.M)
                if len(matches) > 1:
                    raise ValueError(f"Conflicting IOTEDGE_RELEASE in {inc}")
                if matches:
                    current_release = matches[0]
                    version_key(current_release)
        update_type = "none"
        if current_release and version_key(current_release) <= version_key(release):
            if ((current and version_key(current) > version_key(daemon)) or
                    (current_iis and version_key(current_iis) > version_key(iis))):
                raise ValueError(f"Refusing component downgrade for release {release} on line {line}")
        if not current or not current_iis or (version_key(current_release) <= version_key(release) and
                (version_key(current) < version_key(daemon) or version_key(current_iis) < version_key(iis))):
            update_type = "significant"
        elif version_key(current_release) < version_key(release):
            update_type = "docker-only"
        plans.append(dict(release_version=release, daemon_version=daemon, iis_version=iis,
                          current_recipe=current, current_iis=current_iis, current_release=current_release,
                          template=TEMPLATES[line][0], line=line, update_type=update_type,
                          needs_update=update_type == "significant", is_significant=update_type == "significant"))
    return plans


if __name__ == "__main__":
    try:
        if sys.argv[1] == "plans":
            plans = release_plans(json.load(sys.stdin), sys.argv[2])
            mode = sys.argv[3]
            if mode == "--plans-json":
                print(json.dumps(plans, indent=2))
            elif mode == "--json":
                print(json.dumps(plans[0], indent=2))
            else:
                for key, value in plans[0].items():
                    print(f"{key}={str(value).lower() if isinstance(value, bool) else value}")
        elif sys.argv[1] == "select":
            update_template_versions(*sys.argv[2:])
        else:
            daemon, iis = resolve_release(json.load(sys.stdin), sys.argv[2])
            if len(sys.argv) > 3:
                validate_template(sys.argv[3], daemon, iis)
            print(daemon, iis)
    except (ValueError, KeyError) as exc:
        sys.exit(f"Error: {exc}")
