#!/usr/bin/env python3
"""Collect reviewed RPM names; CLI also prepares complete ext4 release assets."""
import argparse
import gzip
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

BASES = ('iotedge', 'aziot-edged', 'aziotd', 'aziotctl', 'aziot-keys')
# These standard OE subpackages are intentional; arbitrary prefix matches are not.
SUBPACKAGES = ('dbg', 'dev', 'staticdev', 'doc')
NAMES = set(BASES) | {f'{base}-{suffix}' for base in BASES for suffix in SUBPACKAGES}
RPM = re.compile(r'^(.+)-([0-9][^-]*)-([^-]+)\.([^.]+)\.rpm$')


def collect(rpm_dir, output_dir, *, version, packages_only=False, qemu_dir=None):
    output = Path(output_dir)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+-]*', version):
        raise ValueError('Unsafe version for artifact name')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be empty (avoid stale assets)')
    if not packages_only:
        if qemu_dir is None:
            raise ValueError('--qemu-dir is required for release packaging')
        for name in ('iotedge-qemu-image-qemux86-64.rootfs.ext4', 'bzImage'):
            path = Path(qemu_dir) / name
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f'Missing or empty QEMU artifact: {path}')
    selected = []
    seen = set()
    runtime = {base: [] for base in BASES}
    for path in sorted(Path(rpm_dir).rglob('*.rpm')):
        match = RPM.fullmatch(path.name)
        if match and match[1] in NAMES and match[4] not in ('src', 'nosrc'):
            if path.name in seen or not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f'Duplicate or empty RPM: {path}')
            seen.add(path.name)
            selected.append(path)
            if match[1] in runtime:
                runtime[match[1]].append(path)
    if any(len(paths) != 1 for paths in runtime.values()):
        raise ValueError('Require exactly one nonempty base RPM for each of: ' + ', '.join(BASES))
    output.mkdir(parents=True, exist_ok=True)
    if packages_only:
        for path in selected:
            shutil.copyfile(path, output / path.name)
        return [output / path.name for path in selected]
    qemu = Path(qemu_dir)
    archive = output / f'iotedge-rpms-{version}.tar.gz'
    # Normalize both gzip and tar metadata so reruns can verify immutable assets.
    with archive.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as tar:
            for path in sorted(selected, key=lambda path: path.name):
                info = tar.gettarinfo(path, arcname=path.name)
                info.mtime = info.uid = info.gid = 0
                info.uname = info.gname = ''
                with path.open('rb') as contents:
                    tar.addfile(info, contents)
    image = output / 'iotedge-qemu-image-qemux86-64.rootfs.ext4.zst'
    subprocess.run(['zstd', '-f', '-T0', '-19', str(qemu / 'iotedge-qemu-image-qemux86-64.rootfs.ext4'), '-o', str(image)], check=True)
    kernel = output / 'bzImage'
    shutil.copyfile(qemu / 'bzImage', kernel)
    return [archive, image, kernel]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rpm-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--version', required=True)
    parser.add_argument('--qemu-dir', type=Path)
    parser.add_argument('--packages-only', action='store_true', help='Copy validated RPMs without archiving or requiring QEMU assets')
    args = parser.parse_args()
    for path in collect(**vars(args)):
        print(path)


if __name__ == '__main__':
    main()
