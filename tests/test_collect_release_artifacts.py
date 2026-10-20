import importlib.util
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/collect-release-artifacts.py'


def load_collector():
    spec = importlib.util.spec_from_file_location('collector', SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(root):
    src = root / 'rpm'
    src.mkdir()
    for base in ['iotedge', 'aziot-edged', 'aziotd', 'aziotctl', 'aziot-keys']:
        (src / f'{base}-1.6.4-r0.core2_64.rpm').write_bytes(b'rpm fixture')
    return src


class CollectorTests(unittest.TestCase):
    def test_source_rpm_cannot_satisfy_required_runtime_package(self):
        module = load_collector()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = fixture(root)
            (src / 'aziotctl-1.6.4-r0.core2_64.rpm').unlink()
            (src / 'aziotctl-1.6.4-r0.src.rpm').write_bytes(b'source, not runtime')
            with self.assertRaises(ValueError):
                module.collect(src, root / 'out', version='1.6.4', packages_only=True)

    def test_rejects_incomplete_empty_or_ambiguous_runtime_inventory(self):
        module = load_collector()
        for bad in ['missing', 'empty', 'duplicate', 'multiple-versions']:
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                src = fixture(root)
                rpm = src / 'aziotd-1.6.4-r0.core2_64.rpm'
                if bad == 'missing':
                    rpm.unlink()
                    (src / 'aziotd-dbg-1.6.4-r0.core2_64.rpm').write_bytes(b'dbg')
                elif bad == 'empty':
                    rpm.write_bytes(b'')
                elif bad == 'duplicate':
                    (src / 'nested').mkdir()
                    (src / 'nested' / rpm.name).write_bytes(b'different')
                else:
                    (src / 'aziotd-1.6.0-r0.core2_64.rpm').write_bytes(b'old')
                with self.assertRaises(ValueError):
                    module.collect(src, root / 'out', version='1.6.4', packages_only=True)

    def test_rejects_missing_empty_qemu_and_stale_outputs_before_packaging(self):
        module = load_collector()
        for bad in ['missing-kernel', 'empty-kernel', 'missing-image', 'empty-image', 'unsafe-version', 'stale-output']:
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                src = fixture(root)
                qemu = root / 'qemu'
                qemu.mkdir()
                image = qemu / 'iotedge-qemu-image-qemux86-64.rootfs.ext4'
                kernel = qemu / 'bzImage'
                image.write_bytes(b'image')
                kernel.write_bytes(b'kernel')
                if bad == 'missing-kernel': kernel.unlink()
                if bad == 'empty-kernel': kernel.write_bytes(b'')
                if bad == 'missing-image': image.unlink()
                if bad == 'empty-image': image.write_bytes(b'')
                out = root / 'out'
                if bad == 'stale-output':
                    out.mkdir()
                    (out / 'old.rpm').write_bytes(b'old')
                version = '../escape' if bad == 'unsafe-version' else '1.6.4'
                with self.assertRaises(ValueError):
                    module.collect(src, out, qemu_dir=qemu, version=version)
                self.assertFalse((out / 'iotedge-rpms-1.6.4.tar.gz').exists())

    def test_archive_is_reproducible_after_clock_and_input_mtime_changes(self):
        import os
        from unittest.mock import patch
        module = load_collector()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = fixture(root)
            # Source directory order must not determine flat archive order.
            (src / 'a').mkdir()
            rpm = src / 'iotedge-1.6.4-r0.core2_64.rpm'
            rpm.rename(src / 'a' / rpm.name)
            qemu = root / 'qemu'
            qemu.mkdir()
            (qemu / 'iotedge-qemu-image-qemux86-64.rootfs.ext4').write_bytes(b'image')
            (qemu / 'bzImage').write_bytes(b'kernel')
            with patch('time.time', return_value=1700000000):
                first = module.collect(src, root / 'first', qemu_dir=qemu, version='1.6.4')[0]
            for rpm in src.rglob('*.rpm'):
                os.utime(rpm, (1800000000, 1800000000))
            with patch('time.time', return_value=1900000000):
                second = module.collect(src, root / 'second', qemu_dir=qemu, version='1.6.4')[0]
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(int.from_bytes(first.read_bytes()[4:8], 'little'), 0)
            self.assertEqual(first.read_bytes()[3] & 8, 0, 'gzip must not embed a filename')
            with tarfile.open(first) as archive:
                self.assertEqual(archive.getnames(), sorted(archive.getnames()))
                for member in archive.getmembers():
                    self.assertEqual((member.mtime, member.uid, member.gid, member.uname, member.gname), (0, 0, 0, '', ''))
                    extracted = archive.extractfile(member)
                    self.assertIsNotNone(extracted)
                    assert extracted is not None
                    self.assertEqual(extracted.read(), b'rpm fixture')

    def test_full_cli_creates_nonempty_exact_archive_ext4_and_kernel(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = fixture(root)
            qemu = root / 'qemu'
            qemu.mkdir()
            (qemu / 'iotedge-qemu-image-qemux86-64.rootfs.ext4').write_bytes(b'ext4 fixture')
            (qemu / 'bzImage').write_bytes(b'kernel fixture')
            out = root / 'out'
            result = subprocess.run([sys.executable, str(SCRIPT), '--rpm-dir', str(src), '--qemu-dir', str(qemu), '--output-dir', str(out), '--version', '1.6.4'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((out / 'iotedge-rpms-1.6.4.tar.gz').exists(), 'release archive missing')
            with tarfile.open(out / 'iotedge-rpms-1.6.4.tar.gz') as archive:
                self.assertEqual(sorted(archive.getnames()), sorted(p.name for p in src.iterdir()))
                self.assertTrue(all(member.size > 0 for member in archive.getmembers()))
            self.assertEqual((out / 'bzImage').read_bytes(), b'kernel fixture')
            decoded = subprocess.check_output(['zstd', '-dc', str(out / 'iotedge-qemu-image-qemux86-64.rootfs.ext4.zst')])
            self.assertEqual(decoded, b'ext4 fixture')
            self.assertEqual(len(list(out.iterdir())), 3)

    def test_packages_include_all_five_base_rpms_and_only_reviewed_subpackages(self):
        self.assertTrue(SCRIPT.exists(), 'collector implementation is missing')
        module = load_collector()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / 'rpm'
            src.mkdir()
            bases = ['iotedge', 'aziot-edged', 'aziotd', 'aziotctl', 'aziot-keys']
            names = [f'{base}-1.6.4-r0.core2_64.rpm' for base in bases]
            names += ['aziotd-dbg-1.6.4-r0.core2_64.rpm']
            for name in names + ['aziotd-unreviewed-1.6.4-r0.core2_64.rpm', 'iotedge-tools-1.6.4-r0.core2_64.rpm', 'bash-5.2-r0.core2_64.rpm']:
                (src / name).write_bytes(b'rpm fixture')
            result = module.collect(src, root / 'out', version='1.6.4', packages_only=True)
            self.assertEqual(sorted(p.name for p in result), sorted(names))
            self.assertEqual(sorted(p.name for p in (root / 'out').iterdir()), sorted(names))


if __name__ == '__main__':
    unittest.main()
