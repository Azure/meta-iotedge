#!/usr/bin/env python3
"""Fail-closed preparation for the explicit manual cold-cache diagnostic."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def empty_directory(path):
    if path.is_symlink() or not path.is_dir() or any(path.iterdir()):
        raise ValueError('Cold cache directory must be a real, empty directory')


def capacity_guard(path):
    # Same floor as the template's existing STOPTASKS disk/inode policy, not
    # a claimed cold-build sizing budget. Docker placement remains unverified.
    stat = os.statvfs(path)
    free_bytes = stat.f_bavail * stat.f_frsize
    print('cold-cache disk: ' + json.dumps({'free_bytes': free_bytes, 'free_inodes': stat.f_favail}))
    if free_bytes < 1024 ** 3 or stat.f_favail < 100000:
        raise ValueError('Cold cache disk below existing 1GiB/100000-inode stop floor')


def prepare(root):
    empty_directory(root)
    capacity_guard(root)
    for name in ('downloads', 'sstate-cache'):
        (root / name).mkdir()
        empty_directory(root / name)
    print('Verified cold cache: DL_DIR and SSTATE_DIR start empty')


def configure(path, root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Cold cache root must be a real directory')
    for name in ('downloads', 'sstate-cache'):
        empty_directory(root / name)
    tmpdir = Path.cwd() / 'tmp'
    if tmpdir.exists() or tmpdir.is_symlink():
        empty_directory(tmpdir)
    capacity_guard(Path.cwd())
    text = path.read_text()
    path.write_text(text + f'\n# Explicit manual cold-cache diagnostic\nDL_DIR = "{root}/downloads"\n'
                    f'SSTATE_DIR = "{root}/sstate-cache"\nTMPDIR = "${{TOPDIR}}/tmp"\n'
                    'SSTATE_MIRRORS = ""\n')
    print('Verified both cold caches empty before first BitBake parse; sstate mirrors disabled')


def verify(root):
    expected = {'DL_DIR': str(root / 'downloads'), 'SSTATE_DIR': str(root / 'sstate-cache'),
                'TMPDIR': str(Path.cwd() / 'tmp'), 'SSTATE_MIRRORS': ''}
    values = {}
    counts = dict.fromkeys(expected, 0)
    with subprocess.Popen(['bitbake', '-e'], stdout=subprocess.PIPE, text=True) as process:
        assert process.stdout is not None
        for line in process.stdout:
            match = re.fullmatch(r'(?:export )?(DL_DIR|SSTATE_DIR|TMPDIR|SSTATE_MIRRORS)="([^"\n]*)"\n?', line)
            if match:
                values[match[1]] = match[2]
                counts[match[1]] += 1
        if process.wait() != 0:
            raise ValueError('bitbake -e failed checking cold caches')
    if values != expected or any(count != 1 for count in counts.values()):
        raise ValueError('Effective cold cache paths, local TMPDIR or disabled sstate mirrors mismatch')
    print('Verified effective cold BitBake cache paths; TMPDIR local, sstate mirrors disabled')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['prepare', 'configure', 'verify'])
    parser.add_argument('path', type=Path, nargs='?')
    parser.add_argument('--cache-root', type=Path, default=Path('/workspaces/yocto-cache'))
    args = parser.parse_args()
    try:
        if args.operation == 'prepare':
            if args.path is None:
                parser.error('prepare requires a cache root')
            prepare(args.path)
        elif args.operation == 'configure':
            if args.path is None:
                parser.error('configure requires local.conf')
            configure(args.path, args.cache_root)
        else:
            verify(args.cache_root)
    except (OSError, ValueError) as exc:
        print(f'Cold cache preflight failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
