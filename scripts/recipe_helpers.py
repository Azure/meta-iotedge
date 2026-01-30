#!/usr/bin/env python3
"""Helper functions for update-recipes.sh"""

import os
import re
import subprocess
import sys
from typing import Optional


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
    """Print latest release tag and SHA."""
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
    """Fix EXTRA_OECARGO_PATHS in recipe to use correct subdirectory paths."""
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
            crate_paths[match.group(1)] = os.path.relpath(root, repo_dir)

    pattern = re.compile(r'^(EXTRA_OECARGO_PATHS \+= "\$\{WORKDIR\}/)([^"/]+)"\s*$')
    with open(recipe_path, encoding="utf-8") as fh:
        lines = fh.readlines()

    with open(recipe_path, "w", encoding="utf-8") as fh:
        for line in lines:
            m = pattern.match(line.rstrip("\n"))
            if m and (rel := crate_paths.get(m.group(2))) and rel != ".":
                fh.write(f'{m.group(1)}{m.group(2)}/{rel}"\n')
            else:
                fh.write(line)


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


COMMANDS = {
    "latest-release": (cmd_latest_release, ["repo_url"]),
    "tag-sha": (cmd_tag_sha, ["repo_url", "tag"]),
    "version-from-rev": (cmd_version_from_rev, ["repo_url", "rev"]),
    "fix-cargo-paths": (cmd_fix_cargo_paths, ["repo_dir", "recipe_path"]),
    "add-checksums": (cmd_add_checksums, ["recipe_path", "lockfile_path"]),
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
