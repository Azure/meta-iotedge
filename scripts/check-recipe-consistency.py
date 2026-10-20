#!/usr/bin/env python3
"""Regenerate each maintained template using its newest tracked release metadata."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    spec = importlib.util.spec_from_file_location("release_selection", Path(__file__).with_name("verify-release-selection.py"))
    assert spec is not None and spec.loader is not None
    selection = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(selection)
    def require_clean_output():
        scope = ["--", "recipes-core/", "conf/templates/"]
        tracked = subprocess.check_output(["git", "diff", "--name-only", "-z", *scope], cwd=root, text=True)
        untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z", *scope], cwd=root, text=True)
        drift = sorted(set((tracked + untracked).rstrip("\0").split("\0")) - {""})
        if drift:
            raise ValueError("Generated/committed drift (including untracked files): " + ", ".join(drift))

    try:
        require_clean_output()
        for template in selection.TEMPLATE_LINES:
            release = selection.expected_selection(root, template)["release"]
            print(f"Checking {template}: release {release}", flush=True)
            subprocess.run([str(root / "scripts/update-recipes.sh"), "--iotedge-version", release,
                            "--template", template, "--skip-validate"], cwd=root, check=True)
            require_clean_output()
        return 0
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Recipe consistency check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
