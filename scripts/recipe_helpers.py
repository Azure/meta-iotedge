#!/usr/bin/env python3
"""Helper functions for update-recipes.sh"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from typing import Optional


def get_github_latest_release(repo_url: str, tag_pattern: str = None) -> tuple:
    """Get latest release from GitHub API (not pre-release, not draft).
    
    Args:
        repo_url: Git repository URL
        tag_pattern: Optional regex pattern to filter tags (e.g., r'^v?\d+\.\d+\.\d+$' for semver only)
    """
    # Extract owner/repo from URL
    match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", repo_url)
    if not match:
        return None, None
    owner, repo = match.groups()
    repo = repo.rstrip(".git")
    
    # For iotedge repo, we need to filter releases since it has multiple products
    # (metrics-collector, api-proxy, etc.) but iotedge itself uses plain semver tags
    if tag_pattern is None and repo == "iotedge":
        tag_pattern = r"^v?\d+\.\d+\.\d+$"
    
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    try:
        req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            releases = json.load(resp)
            for release in releases:
                if release.get("draft") or release.get("prerelease"):
                    continue
                tag = release.get("tag_name", "")
                if tag_pattern and not re.match(tag_pattern, tag):
                    continue
                # Get the SHA for this tag
                sha = get_tag_sha_direct(repo_url, tag)
                if sha:
                    return tag, sha
        return None, None
    except Exception as e:
        print(f"Warning: GitHub API failed ({e}), falling back to tags", file=sys.stderr)
        return None, None


def get_tag_sha_direct(repo_url: str, tag: str) -> str:
    """Get SHA for a specific tag."""
    out = subprocess.check_output(["git", "ls-remote", "--tags", repo_url], text=True)
    refs = {ref: sha for sha, ref in (line.split() for line in out.splitlines())}
    # Try peeled ref first (for annotated tags)
    for suffix in ["^{}", ""]:
        ref = f"refs/tags/{tag}{suffix}"
        if ref in refs:
            return refs[ref]
    return ""


def get_tags(repo_url: str) -> dict:
    """Fetch and parse semver tags from a git repository."""
    out = subprocess.check_output(["git", "ls-remote", "--tags", repo_url], text=True)
    tags = {}
    for line in out.splitlines():
        sha, ref = line.split()
        if not ref.startswith("refs/tags/"):
            continue
        tag = ref[len("refs/tags/"):]
        peeled = tag.endswith("^{}")
        if peeled:
            tag = tag[:-3]
        tag_clean = tag.lstrip("v")
        if not re.fullmatch(r"\d+\.\d+\.\d+", tag_clean):
            continue
        version = tuple(map(int, tag_clean.split(".")))
        entry = tags.setdefault(tag, {"tag": tag, "version": version})
        entry["peeled" if peeled else "sha"] = sha
    return tags


def cmd_latest_release(repo_url: str):
    """Print latest release tag and SHA from GitHub releases API."""
    # Try GitHub API first (gets actual releases, not just tags)
    tag, sha = get_github_latest_release(repo_url)
    if tag and sha:
        print(tag)
        print(sha)
        return
    
    # Fallback to tag-based lookup
    tags = get_tags(repo_url)
    if not tags:
        raise SystemExit("No semver tags found")
    latest = max(tags.values(), key=lambda x: x["version"])
    print(latest["tag"])
    print(latest.get("peeled") or latest.get("sha"))


def cmd_tag_sha(repo_url: str, tag: str):
    """Print SHA for a specific tag."""
    out = subprocess.check_output(["git", "ls-remote", "--tags", repo_url], text=True)
    refs = {ref: sha for sha, ref in (line.split() for line in out.splitlines())}
    for candidate in [tag, f"v{tag}"]:
        for suffix in ["^{}", ""]:
            ref = f"refs/tags/{candidate}{suffix}"
            if ref in refs:
                print(refs[ref])
                return
    raise SystemExit(f"Tag not found: {tag}")


def cmd_version_from_rev(repo_url: str, rev: str):
    """Print version tag matching a revision."""
    tags = get_tags(repo_url)
    matches = [e for e in tags.values() if e.get("peeled") == rev or e.get("sha") == rev]
    if not matches:
        raise SystemExit("No matching tag found for revision")
    print(max(matches, key=lambda x: x["version"])["tag"])


def cmd_fix_cargo_paths(repo_dir: str, recipe_path: str):
    """Fix SRC_URI git deps and EXTRA_OECARGO_PATHS to use correct subdirectory paths.
    
    cargo-bitbake generates git deps like:
      git://...iot-identity-service;...;name=aziot-cert-client-async;destsuffix=aziot-cert-client-async
    
    But IIS crates are in subdirectories like cert/aziot-cert-client-async, so we need:
      git://...iot-identity-service;...;name=aziot-cert-client-async;destsuffix=cert/aziot-cert-client-async;subpath=cert/aziot-cert-client-async
    """
    # Build map of crate name -> relative path in IIS repo
    crate_paths = {}
    for root, _, files in os.walk(repo_dir):
        if "Cargo.toml" not in files:
            continue
        try:
            with open(os.path.join(root, "Cargo.toml"), encoding="utf-8") as fh:
                contents = fh.read()
        except OSError:
            continue
        match = re.search(r'\[package\][^\[]*name\s*=\s*"([^"]+)"', contents, re.DOTALL)
        if match:
            rel = os.path.relpath(root, repo_dir)
            if rel != ".":
                crate_paths[match.group(1)] = rel

    with open(recipe_path, encoding="utf-8") as fh:
        content = fh.read()

    # Fix SRC_URI git lines for iot-identity-service dependencies
    # Pattern: git://...iot-identity-service;...;name=CRATE;destsuffix=CRATE ...
    def fix_git_line(match):
        line = match.group(0)
        name_match = re.search(r';name=([^;\\]+)', line)
        if not name_match:
            return line
        crate_name = name_match.group(1)
        crate_path = crate_paths.get(crate_name)
        if not crate_path:
            return line  # No fix needed (crate at repo root)
        
        # Fix destsuffix: name=foo;destsuffix=foo -> name=foo;destsuffix=path/foo
        line = re.sub(
            rf';destsuffix={re.escape(crate_name)}([;\s\\])',
            f';destsuffix={crate_path};subpath={crate_path}\\1',
            line
        )
        return line

    # Fix all iot-identity-service git lines
    content = re.sub(
        r'git://github\.com/Azure/iot-identity-service[^\n]+',
        fix_git_line,
        content
    )

    # Fix EXTRA_OECARGO_PATHS lines
    def fix_paths_line(match):
        line = match.group(0)
        path_match = re.search(r'\$\{WORKDIR\}/([^/"]+)"', line)
        if not path_match:
            return line
        crate_name = path_match.group(1)
        crate_path = crate_paths.get(crate_name)
        if not crate_path:
            return line
        return line.replace(f'${{WORKDIR}}/{crate_name}"', f'${{WORKDIR}}/{crate_path}"')

    content = re.sub(
        r'EXTRA_OECARGO_PATHS \+= "\$\{WORKDIR\}/[^"]+"\s*',
        fix_paths_line,
        content
    )

    with open(recipe_path, "w", encoding="utf-8") as fh:
        fh.write(content)


def cmd_add_checksums(recipe_path: str, lockfile_path: str):
    """Add SHA256 checksums from Cargo.lock to recipe."""
    # Parse Cargo.lock
    pkgs = {}
    with open(lockfile_path, encoding="utf-8") as fh:
        name = version = checksum = None
        for line in fh:
            line = line.strip()
            if line == "[[package]]":
                if name and version and checksum:
                    pkgs[(name, version)] = checksum
                name = version = checksum = None
            elif line.startswith("name = "):
                name = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("version = "):
                version = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("checksum = "):
                checksum = line.split("=", 1)[1].strip().strip('"')
        if name and version and checksum:
            pkgs[(name, version)] = checksum

    # Find existing checksums and missing ones
    with open(recipe_path, encoding="utf-8") as fh:
        content = fh.read()

    existing = set(re.findall(r"SRC_URI\[([^\]]+)\.sha256sum\]", content))
    crate_re = re.compile(r"crate://crates\.io/([^/]+)/([0-9A-Za-z._-]+)")
    missing = []
    for m in crate_re.finditer(content):
        key = f"{m.group(1)}-{m.group(2)}"
        if key not in existing and (checksum := pkgs.get((m.group(1), m.group(2)))):
            missing.append(f'SRC_URI[{key}.sha256sum] = "{checksum}"\n')
            existing.add(key)

    if missing:
        with open(recipe_path, "a", encoding="utf-8") as fh:
            fh.write("\n")
            fh.writelines(missing)


def cmd_strip_git_deps(lock_path: str, toml_path: str):
    """Remove git dependencies from Cargo.lock and panic=abort from Cargo.toml."""
    with open(lock_path, encoding="utf-8") as fh:
        lines = [l for l in fh if "git+https://github.com/Azure/iot-identity-service" not in l]
    with open(lock_path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)

    with open(toml_path, encoding="utf-8") as fh:
        lines = [l for l in fh if l.strip() != "panic = 'abort'"]
    with open(toml_path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)


def cmd_fix_patch_paths(patch_path: str):
    """Fix paths in generated patch file."""
    with open(patch_path, encoding="utf-8") as fh:
        data = fh.read()
    for prefix in ["a/", "b/"]:
        for old in ["orig/edgelet/", "mod/edgelet/"]:
            data = data.replace(f"{prefix}{old}", f"{prefix}edgelet/")
    with open(patch_path, "w", encoding="utf-8") as fh:
        fh.write(data)


# Known crates that may need checksums fetched from crates.io
# (these are crates that bitbake often complains about missing checksums)
CRATES_NEEDING_CHECKSUMS = [
    ("wasi", "0.10.0+wasi-snapshot-preview1"),
    ("wasi", "0.11.0+wasi-snapshot-preview1"),
]


def fetch_crate_checksum(crate_name: str, version: str) -> Optional[str]:
    """Fetch SHA256 checksum for a crate from crates.io API."""
    # crates.io API: https://crates.io/api/v1/crates/{crate}/{version}
    api_url = f"https://crates.io/api/v1/crates/{crate_name}/{version}"
    try:
        req = urllib.request.Request(api_url, headers={
            "User-Agent": "meta-iotedge-recipe-helper/1.0",
            "Accept": "application/json"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
            return data.get("version", {}).get("checksum")
    except Exception as e:
        print(f"Warning: Failed to fetch checksum for {crate_name}-{version}: {e}", file=sys.stderr)
        return None


def cmd_add_known_checksums(recipe_path: str):
    """Add checksums for known crates that bitbake may complain about."""
    with open(recipe_path, encoding="utf-8") as fh:
        content = fh.read()
    
    missing = []
    for crate_name, version in CRATES_NEEDING_CHECKSUMS:
        # Check if this crate is in SRC_URI
        crate_url_pattern = f"crate://crates.io/{crate_name}/{version}"
        crate_key = f"{crate_name}-{version}"
        
        if crate_url_pattern in content:
            checksum_line = f'SRC_URI[{crate_key}.sha256sum]'
            if checksum_line not in content:
                checksum = fetch_crate_checksum(crate_name, version)
                if checksum:
                    missing.append(f'{checksum_line} = "{checksum}"\n')
    
    if missing:
        with open(recipe_path, "a", encoding="utf-8") as fh:
            fh.write("\n# Checksums fetched from crates.io\n")
            fh.writelines(missing)


COMMANDS = {
    "latest-release": (cmd_latest_release, ["repo_url"]),
    "tag-sha": (cmd_tag_sha, ["repo_url", "tag"]),
    "version-from-rev": (cmd_version_from_rev, ["repo_url", "rev"]),
    "fix-cargo-paths": (cmd_fix_cargo_paths, ["repo_dir", "recipe_path"]),
    "add-checksums": (cmd_add_checksums, ["recipe_path", "lockfile_path"]),
    "add-known-checksums": (cmd_add_known_checksums, ["recipe_path"]),
    "strip-git-deps": (cmd_strip_git_deps, ["lock_path", "toml_path"]),
    "fix-patch-paths": (cmd_fix_patch_paths, ["patch_path"]),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: {sys.argv[0]} <command> [args...]", file=sys.stderr)
        print(f"Commands: {', '.join(COMMANDS.keys())}", file=sys.stderr)
        sys.exit(1)
    func, args = COMMANDS[sys.argv[1]]
    if len(sys.argv) - 2 != len(args):
        print(f"Usage: {sys.argv[0]} {sys.argv[1]} {' '.join(f'<{a}>' for a in args)}", file=sys.stderr)
        sys.exit(1)
    func(*sys.argv[2:])
