"""Cold-cache safety checks; filesystem probes stay in private scratch fixtures."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/ci-cold-cache.py'


class ColdCacheTests(unittest.TestCase):
    def test_prepare_initializes_only_an_empty_root_and_rejects_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / 'cold'
            cache.mkdir()
            command = [sys.executable, str(SCRIPT), 'prepare', str(cache)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(sorted(p.name for p in cache.iterdir()), ['downloads', 'sstate-cache'])
            self.assertTrue(all(not list(p.iterdir()) for p in cache.iterdir()))
            sentinel = cache / 'downloads/keep'
            sentinel.write_text('preserve')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(sentinel.read_text(), 'preserve')

    def test_configure_checks_empty_caches_before_writing_and_pins_local_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / 'cold'
            cache.mkdir()
            for name in ('downloads', 'sstate-cache'):
                (cache / name).mkdir()
            conf = root / 'local.conf'
            conf.write_text('MACHINE = "fixture"\n')
            command = [sys.executable, str(SCRIPT), 'configure', str(conf), '--cache-root', str(cache)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = conf.read_text()
            self.assertIn(f'DL_DIR = "{cache}/downloads"', text)
            self.assertIn(f'SSTATE_DIR = "{cache}/sstate-cache"', text)
            self.assertIn('TMPDIR = "${TOPDIR}/tmp"', text)
            self.assertIn('SSTATE_MIRRORS = ""', text)
            for name in ('downloads', 'sstate-cache'):
                sentinel = cache / name / 'keep'
                sentinel.write_text('preserve')
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(conf.read_text(), text)
                self.assertEqual(sentinel.read_text(), 'preserve')
                sentinel.unlink()

    def test_workflow_cold_gate_is_manual_scarthgap_branch_only_with_qemu(self):
        self.assertIn('        id: set-cold-cache\n', (ROOT / '.github/workflows/ci-build.yml').read_text(),
                      'missing cold diagnostic launch gate')
        from test_ci_manual_scope import ManualScopeTests
        runner = ManualScopeTests()
        for event, branch, template, skip, allowed in [
                ('workflow_dispatch', 'diag/pr232-cold-observation', 'scarthgap', 'false', True),
                ('workflow_dispatch', 'diag/pr232-live-telemetry', 'scarthgap', 'false', False),
                ('workflow_dispatch', 'diag/pr232-cold-observation', 'all', 'false', False),
                ('workflow_dispatch', 'diag/pr232-cold-observation', 'wrynose', 'false', False),
                ('workflow_dispatch', 'diag/pr232-cold-observation', 'scarthgap', 'true', False),
                ('workflow_dispatch', 'diag/pr232-cold-observation', 'scarthgap-1.6', 'false', False)]:
            with self.subTest(event=event, branch=branch, template=template, skip=skip):
                context = runner.context(event=event, choice=template, ref=branch)
                context.update({'inputs.cold_cache': 'true', 'inputs.skip_qemu': skip})
                with mock.patch.dict(os.environ, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='2'):
                    result, outputs = runner.execute('set-cold-cache', context)
                self.assertEqual(result.returncode == 0, allowed, result.stderr)
                if allowed:
                    self.assertEqual(outputs['cold_cache_path'], '/mnt/yocto-cold-123-2')
                    self.assertEqual(outputs['cold_cache'], '1')
                else:
                    self.assertNotIn('cold_cache_path', outputs)
        for event in ('push', 'pull_request', 'workflow_call'):
            context = runner.context(event=event, choice='scarthgap', ref='diag/pr232-cold-observation')
            context['inputs.cold_cache'] = 'true'
            result, outputs = runner.execute('set-cold-cache', context)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(outputs, {'cold_cache': '0'})
        context = runner.context(choice='scarthgap', ref='diag/pr232-cold-observation')
        context['inputs.cold_cache'] = 'false'
        result, outputs = runner.execute('set-cold-cache', context)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outputs, {'cold_cache': '0'})

    def test_prepare_capacity_guard_blocks_mutation_when_free_space_or_inodes_are_low(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('cold_cache', SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(hasattr(module, 'capacity_guard'), 'missing cold disk-capacity preflight')
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for bytes_free, inodes in [(1024 ** 3 - 1, 100000), (1024 ** 3, 99999)]:
                with mock.patch.object(module.os, 'statvfs', return_value=SimpleNamespace(
                        f_bavail=bytes_free, f_frsize=1, f_favail=inodes)):
                    with self.assertRaises(ValueError):
                        module.prepare(root)
                self.assertEqual(list(root.iterdir()), [])
            with mock.patch.object(module.os, 'statvfs', return_value=SimpleNamespace(
                    f_bavail=1024 ** 3, f_frsize=1, f_favail=100000)):
                module.prepare(root)

    def test_real_wrapper_pins_and_verifies_caches_before_build_preserving_build_exit(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ('scripts', 'poky', 'bin', 'cache/downloads', 'cache/sstate-cache'):
                (root / folder).mkdir(parents=True, exist_ok=True)
            for name in ('bitbake.sh', 'ci-cold-cache.py', 'ci-bitbake-limits.py'):
                shutil.copy(ROOT / 'scripts' / name, root / 'scripts' / name)
            (root / 'scripts/verify-release-selection.py').write_text('raise SystemExit(0)\n')
            (root / 'poky/oe-init-build-env').write_text(
                'mkdir -p "$FIXTURE/build/conf"\ncd "$FIXTURE/build"\nprintf \'MACHINE="fixture"\\n\' > conf/local.conf\n')
            binary = root / 'bin/bitbake'
            binary.write_text('''#!/bin/sh
case "$1" in
-p) cp conf/local.conf "$FIXTURE/parsed.conf"; exit 0;;
-e) printf 'BB_NUMBER_THREADS="4"\\nPARALLEL_MAKE="-j4"\\nBB_NUMBER_PARSE_THREADS="4"\\n'
    printf 'DL_DIR="%s"\\nSSTATE_DIR="%s"\\nTMPDIR="%s"\\nSSTATE_MIRRORS="%s"\\n' "$EFFECTIVE_DL" "$FIXTURE/cache/sstate-cache" "$FIXTURE/build/tmp" "$MIRRORS"
    printf 'SECRET="do-not-print"\\n'; exit "$QUERY_EXIT";;
*) touch "$FIXTURE/built"; exit 37;;
esac
''')
            binary.chmod(0o755)
            env = {**os.environ, 'PATH': str(root / 'bin') + os.pathsep + os.environ['PATH'],
                   'FIXTURE': tmp, 'TEMPLATECONF': 'conf/templates/scarthgap',
                   'CI_YOCTO_RESOURCE_LIMITS': '1', 'CI_YOCTO_COLD_CACHE': '1',
                   'CI_YOCTO_COLD_CACHE_ROOT': str(root / 'cache'), 'QUERY_EXIT': '0',
                   'EFFECTIVE_DL': str(root / 'cache/downloads'), 'MIRRORS': ''}
            command = ['bash', str(root / 'scripts/bitbake.sh'), 'iotedge', 'iotedge-qemu-image']
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 37, result.stdout + result.stderr)
            self.assertIn(f'DL_DIR = "{root}/cache/downloads"', (root / 'parsed.conf').read_text(),
                          'cold config must be applied before first parse')
            self.assertIn('Verified effective cold BitBake cache paths', result.stdout)
            self.assertNotIn('do-not-print', result.stdout + result.stderr)
            for bad in ({'EFFECTIVE_DL': '/old/cache'}, {'MIRRORS': 'https://warm'}, {'QUERY_EXIT': '23'}):
                (root / 'built').unlink(missing_ok=True)
                result = subprocess.run(command, cwd=root, env={**env, **bad}, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertFalse((root / 'built').exists())
                self.assertNotIn('do-not-print', result.stdout + result.stderr)

    def test_workflow_routes_new_bind_source_and_prepares_before_ownership(self):
        text = (ROOT / '.github/workflows/ci-build.yml').read_text()
        self.assertIn("options: --user root -v ${{ needs.check-changes.outputs.cold_cache_path || vars.YOCTO_CACHE_PATH || '/mnt/yocto-cache' }}:/workspaces/yocto-cache", text)
        self.assertIn("CI_YOCTO_COLD_CACHE: ${{ needs.check-changes.outputs.cold_cache || '0' }}", text)
        self.assertIn("if: needs.check-changes.outputs.cold_cache == '1'", text)
        self.assertLess(text.index('- name: Prepare empty cold caches'), text.index('- name: Create build user'))
        self.assertIn('python3 scripts/ci-cold-cache.py prepare /workspaces/yocto-cache', text)
        self.assertIn('chown builder:builder /workspaces/yocto-cache /workspaces/yocto-cache/downloads /workspaces/yocto-cache/sstate-cache', text)
        self.assertNotIn('rm -rf /mnt', text)

    def test_configure_rejects_reused_tmpdir_before_parsing_or_config_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('cache/downloads', 'cache/sstate-cache', 'tmp'):
                (root / name).mkdir(parents=True, exist_ok=True)
            sentinel = root / 'tmp/keep'
            sentinel.write_text('preserve')
            conf = root / 'local.conf'
            conf.write_text('MACHINE = "fixture"\n')
            result = subprocess.run([sys.executable, str(SCRIPT), 'configure', str(conf),
                                     '--cache-root', str(root / 'cache')], cwd=root,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(conf.read_text(), 'MACHINE = "fixture"\n')
            self.assertEqual(sentinel.read_text(), 'preserve')

    def test_initialization_failure_stops_before_cold_configuration_with_original_exit(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'scripts').mkdir()
            (root / 'poky').mkdir()
            shutil.copy(ROOT / 'scripts/bitbake.sh', root / 'scripts/bitbake.sh')
            (root / 'poky/oe-init-build-env').write_text('return 23\n')
            (root / 'scripts/ci-cold-cache.py').write_text('from pathlib import Path\nPath("must-not-run").touch()\n')
            result = subprocess.run(['bash', str(root / 'scripts/bitbake.sh'), 'iotedge'], cwd=root,
                                    env={**os.environ, 'CI_YOCTO_RESOURCE_LIMITS': '0', 'CI_YOCTO_COLD_CACHE': '1'},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 23, result.stderr)
            self.assertFalse((root / 'must-not-run').exists())

    def test_symlinks_fail_without_touching_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'target'
            target.mkdir()
            sentinel = target / 'keep'
            sentinel.write_text('preserve')
            link = root / 'link'
            link.symlink_to(target, target_is_directory=True)
            result = subprocess.run([sys.executable, str(SCRIPT), 'prepare', str(link)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            cache = root / 'cache'
            cache.mkdir()
            (cache / 'downloads').symlink_to(target, target_is_directory=True)
            (cache / 'sstate-cache').mkdir()
            conf = root / 'local.conf'
            conf.write_text('original\n')
            result = subprocess.run([sys.executable, str(SCRIPT), 'configure', str(conf),
                                     '--cache-root', str(cache)], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(conf.read_text(), 'original\n')
            self.assertEqual(sentinel.read_text(), 'preserve')
            self.assertEqual(list(target.iterdir()), [sentinel])

    def test_cold_gate_rejects_tag_or_unsafe_run_identity_without_path_output(self):
        from test_ci_manual_scope import ManualScopeTests
        runner = ManualScopeTests()
        for ref_type, run_id, attempt in [('tag', '123', '2'), ('branch', '$(exit 73)', '2'),
                                           ('branch', '123', ''), ('branch', '123', '2\n3')]:
            context = runner.context(choice='scarthgap', ref='diag/pr232-cold-observation', ref_type=ref_type)
            context.update({'inputs.cold_cache': 'true', 'inputs.skip_qemu': 'false'})
            with mock.patch.dict(os.environ, GITHUB_RUN_ID=run_id, GITHUB_RUN_ATTEMPT=attempt):
                result, outputs = runner.execute('set-cold-cache', context)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertNotIn('cold_cache_path', outputs)


if __name__ == '__main__':
    unittest.main()
