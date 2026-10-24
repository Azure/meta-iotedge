"""CI-only concurrency configuration, including the actual shell wrapper."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ci-bitbake-limits.py"
LIMITS = {'BB_NUMBER_THREADS': '4', 'PARALLEL_MAKE': '-j4', 'BB_NUMBER_PARSE_THREADS': '4'}


class LimitsTests(unittest.TestCase):
    def test_cache_placement_changes_only_the_host_default_and_retains_override(self):
        workflow = (ROOT / '.github/workflows/ci-build.yml').read_text()
        container = workflow.split('    container:\n', 1)[1].split('    env:', 1)[0]
        options = next(line.strip() for line in container.splitlines()
                       if line.strip().startswith('options:'))
        self.assertEqual(options, "options: --user root -v ${{ vars.YOCTO_CACHE_PATH || '/mnt/yocto-cache' }}:/workspaces/yocto-cache")
        self.assertIn('image: ghcr.io/azure/meta-iotedge-devcontainer:latest', workflow)
        self.assertIn('chown -R builder:builder /workspaces/yocto-cache', workflow)

    def test_configuration_is_idempotent_and_preserves_user_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf = Path(tmp) / 'local.conf'
            original = 'BB_NUMBER_THREADS ?= "32"\nMACHINE = "qemux86-64"\n'
            conf.write_text(original)
            for _ in range(2):
                result = subprocess.run([sys.executable, str(SCRIPT), 'configure', str(conf)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            text = conf.read_text()
            self.assertTrue(text.startswith(original))
            for name, value in LIMITS.items():
                self.assertEqual(text.count(f'{name} = "{value}"'), 1)

    def test_verification_checks_effective_bitbake_values_without_dumping_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / 'bitbake'
            binary.write_text('#!/bin/sh\nprintf \'UNRELATED_SECRET="do-not-print"\\n\'\nprintf \'BB_NUMBER_THREADS="4"\\nPARALLEL_MAKE="-j4"\\n\'\nprintf \'BB_NUMBER_PARSE_THREADS="%s"\\n\' "$PARSE_THREADS"\n')
            binary.chmod(0o755)
            for value, passed in [('4', True), ('32', False), ('', False)]:
                with self.subTest(value=value):
                    env = {**os.environ, 'PATH': tmp + os.pathsep + os.environ['PATH'], 'PARSE_THREADS': value}
                    result = subprocess.run([sys.executable, str(SCRIPT), 'verify'], env=env,
                                            text=True, capture_output=True)
                    self.assertEqual(result.returncode == 0, passed, result.stderr)
                    self.assertNotIn('do-not-print', result.stdout + result.stderr)
                    if passed:
                        self.assertIn('BB_NUMBER_PARSE_THREADS', result.stdout)

    def test_real_shell_wrapper_gates_limits_before_parse_and_checks_before_build(self):
        for enabled, effective, passed in [(False, '32', True), (True, '4', True), (True, '32', False)]:
            with self.subTest(enabled=enabled, effective=effective), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for folder in ('scripts', 'poky', 'bin'):
                    (root / folder).mkdir()
                for name in ('bitbake.sh', 'ci-bitbake-limits.py'):
                    shutil.copy(ROOT / 'scripts' / name, root / 'scripts' / name)
                (root / 'scripts/verify-release-selection.py').write_text('raise SystemExit(0)\n')
                (root / 'poky/oe-init-build-env').write_text(
                    'mkdir -p "$FIXTURE/build/conf"\ncd "$FIXTURE/build"\nprintf \'MACHINE="fixture"\\n\' > conf/local.conf\n')
                binary = root / 'bin/bitbake'
                binary.write_text('''#!/bin/sh
case "$1" in
-p) cp conf/local.conf "$FIXTURE/parsed.conf"; exit 0;;
-e) printf 'BB_NUMBER_THREADS="4"\\nPARALLEL_MAKE="-j4"\\nBB_NUMBER_PARSE_THREADS="%s"\\n' "$PARSE_THREADS";;
*) touch "$FIXTURE/built";;
esac
''')
                binary.chmod(0o755)
                env = {**os.environ, 'PATH': str(root / 'bin') + os.pathsep + os.environ['PATH'],
                       'FIXTURE': tmp, 'TEMPLATECONF': 'conf/templates/wrynose',
                       'CI_YOCTO_RESOURCE_LIMITS': '1' if enabled else '0', 'PARSE_THREADS': effective}
                result = subprocess.run(['bash', str(root / 'scripts/bitbake.sh'), 'iotedge'],
                                        cwd=root, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, passed, result.stdout + result.stderr)
                self.assertEqual((root / 'built').exists(), passed)
                parsed = (root / 'parsed.conf').read_text()
                self.assertEqual('BB_NUMBER_THREADS = "4"' in parsed, enabled)

    def test_workflow_enables_limits_and_uploads_diagnostics_even_on_failure(self):
        workflow = (ROOT / '.github/workflows/ci-build.yml').read_text()
        self.assertIn('CI_YOCTO_RESOURCE_LIMITS: "1"', workflow)
        self.assertIn('scripts/ci-resource-monitor.py', workflow)
        self.assertIn('--label build --', workflow)
        self.assertIn('--label qemu --', workflow)
        upload = workflow.split('- name: Upload runner resource diagnostics', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('always()', upload)
        self.assertIn('continue-on-error: true', upload)
        self.assertIn('runner-diagnostics-${{ matrix.template }}', upload)
        self.assertIn('path: runner-diagnostics/', upload)
        self.assertRegex(upload, r'actions/upload-artifact@[0-9a-f]{40}')

    def test_workflow_commands_keep_separate_diagnostics_and_preserve_failure(self):
        import json
        import textwrap
        workflow = (ROOT / '.github/workflows/ci-build.yml').read_text()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'scripts').mkdir()
            (root / 'bin').mkdir()
            shutil.copy(ROOT / 'scripts/ci-resource-monitor.py', root / 'scripts/ci-resource-monitor.py')
            sudo = root / 'bin/sudo'
            sudo.write_text('#!/bin/sh\nshift 3\nexec "$@"\n')
            sudo.chmod(0o755)
            for label, name, script, code in [('build', 'Build', 'build.sh', 37),
                                              ('qemu', 'Run QEMU validation', 'validate-qemu.sh', 0)]:
                command = root / 'scripts' / script
                command.write_text(f'#!/bin/sh\necho live-{label}\nexit {code}\n')
                command.chmod(0o755)
                step = workflow.split(f'      - name: {name}\n', 1)[1].split('\n      - name:', 1)[0]
                shell = textwrap.dedent(step.split('        run: |\n', 1)[1])
                shell = shell.replace('${{ inputs.skip_qemu }}', 'false')
                env = {**os.environ, 'PATH': str(root / 'bin') + os.pathsep + os.environ['PATH'], 'TEMPLATE': 'wrynose'}
                result = subprocess.run(['bash', '-e', '-c', shell], cwd=root, env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertIn(f'live-{label}', result.stdout)
                disk_lines = [json.loads(line.split(': ', 1)[1]) for line in result.stdout.splitlines()
                              if line.startswith('resource-monitor disk: ')]
                self.assertEqual([line['phase'] for line in disk_lines], ['start', 'end'])
                self.assertTrue(all(line['disks']['workspace']['status'] == 'ok' for line in disk_lines))
            for label, code in [('build', 37), ('qemu', 0)]:
                summary = root / f'runner-diagnostics/{label}/summary.json'
                self.assertTrue(summary.is_file(), f'{label} diagnostics must survive the other phase')
                report = json.loads(summary.read_text())
                self.assertEqual(report['exit_status'], code)
                self.assertEqual(report['label'], label)


if __name__ == '__main__':
    unittest.main()
