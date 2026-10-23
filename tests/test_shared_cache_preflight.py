"""Offline fixtures only: no host sudo, Docker, mount or package calls."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import subprocess
import json
import os
import tempfile
import contextlib
import io
import inspect
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/shared-cache-preflight.py'


def load_probe():
    spec = importlib.util.spec_from_file_location('cache_preflight', SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CommandTests(unittest.TestCase):
    def test_bounded_command_suppresses_output_and_classifies_results(self):
        self.assertTrue(SCRIPT.is_file(), 'missing bounded preflight implementation')
        probe = load_probe()
        for code, expected in [('0', 'passed'), ('17', 'failed')]:
            with self.subTest(code=code):
                result = probe.check_command([sys.executable, '-c',
                    'import sys; print("SENTINEL_SECRET"); '
                    'print("SENTINEL_SECRET", file=sys.stderr); sys.exit(' + code + ')'])
                self.assertEqual(result, expected)
        self.assertEqual(probe.check_command(['/not/a/cache-preflight-helper']), 'unavailable')
        start = time.monotonic()
        self.assertEqual(probe.check_command([sys.executable, '-c',
            'import time; time.sleep(30)'], timeout=0.05), 'timeout')
        self.assertLess(time.monotonic() - start, 2)


    def test_secret_streams_are_suppressed_at_process_boundary(self):
        child = 'import sys; print("SENTINEL_SECRET"); print("SENTINEL_SECRET", file=sys.stderr)'
        wrapper = ('import runpy; probe = runpy.run_path(' + repr(str(SCRIPT)) + '); '
                   'print(probe["check_command"](' +
                   repr([sys.executable, '-c', child]) + '))')
        result = subprocess.run([sys.executable, '-c', wrapper],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=3, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'passed\n')
        self.assertEqual(result.stderr, b'')

    def test_unexecutable_helper_is_unknown_without_exception_disclosure(self):
        probe = load_probe()
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / 'SENTINEL_SECRET'
            helper.write_text('not executable')
            self.assertEqual(probe.check_command([str(helper)]), 'unknown')

    def test_package_query_requires_exact_installed_status(self):
        probe = load_probe()
        self.assertIn('expected_stdout', inspect.signature(probe.check_command).parameters)
        for output, expected in [('installed', 'passed'),
                                 ('config-files', 'failed'),
                                 ('SENTINEL_SECRET', 'failed')]:
            with self.subTest(output=output):
                self.assertEqual(probe.check_command(
                    [sys.executable, '-c', 'print(' + repr(output) + ', end="")'],
                    expected_stdout=b'installed'), expected)


class SnapshotTests(unittest.TestCase):
    def test_fixed_probe_collects_only_allowlisted_prerequisites(self):
        probe = load_probe()
        self.assertTrue(hasattr(probe, 'collect'), 'missing fixed read-only probe')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = root / 'calls'
            # Real processes stand in for host commands. A mount invocation is
            # a test failure: only executable discovery is permitted for it.
            def helper(name, body):
                path = root / name
                path.write_text('#!' + sys.executable + '\n' + body)
                path.chmod(0o755)
                return str(path)
            tools = {}
            for name in ['sudo', 'docker', 'dpkg-query']:
                tools[name] = helper(name,
                    'import sys\nfrom pathlib import Path\n'
                    'p = Path(' + repr(str(calls)) + ')\n'
                    'with p.open("a") as f: f.write(repr(sys.argv[1:]) + "\\n")\n'
                    'print("installed" if sys.argv[1:2] == ["-W"] else "SENTINEL_SECRET", end="")\n'
                    'print("SENTINEL_SECRET", file=sys.stderr)\n')
            for name in ['mount', 'mount.nfs']:
                tools[name] = helper(name,
                    'from pathlib import Path\nPath(' + repr(str(calls)) +
                    ').write_text("FORBIDDEN_MOUNT")\nraise SystemExit(91)\n')
            for mode in ['present', 'missing', 'failed', 'timeout']:
                calls.unlink(missing_ok=True)
                if mode in ['failed', 'timeout']:
                    for name in ['sudo', 'docker', 'dpkg-query']:
                        helper(name, ('import time; time.sleep(30)\n' if mode == 'timeout'
                                      else 'raise SystemExit(1)\n'))
                captured = io.StringIO()
                with patch.object(probe.shutil, 'which', side_effect=lambda name, **kwargs:
                                  None if mode == 'missing' else tools[name]) as which, \
                     contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                    snapshot = probe.collect(timeout=0.05 if mode == 'timeout' else 3)
                self.assertEqual(captured.getvalue(), '')
                self.assertTrue(all(call.kwargs.get('path') == '/usr/sbin:/usr/bin:/sbin:/bin'
                                    for call in which.call_args_list),
                                'tool discovery must ignore caller PATH')
                expected = {'schema_version': 1, 'uid': os.getuid(), 'euid': os.geteuid(),
                    'mount_binary_available': mode != 'missing',
                    'mount_nfs_binary_available': mode != 'missing',
                    'nfs_common_package': {'present': 'installed', 'missing': 'unavailable',
                        'failed': 'not_confirmed', 'timeout': 'timeout'}[mode],
                    'docker_cli': {'present': 'passed', 'missing': 'unavailable',
                        'failed': 'failed', 'timeout': 'timeout'}[mode],
                    'sudo_noninteractive_true': {'present': 'passed', 'missing': 'unavailable',
                        'failed': 'failed', 'timeout': 'timeout'}[mode],
                    'mount_authorization': 'unknown', 'mount_success': 'unknown',
                    'network_access': 'unknown', 'shared_storage_support': 'unknown',
                    'docker_daemon_access': 'unknown'}
                self.assertEqual(snapshot, expected)
                self.assertNotIn('SENTINEL_SECRET', json.dumps(snapshot))
                if mode == 'present':
                    self.assertEqual(calls.read_text().splitlines(), [
                        "['-W', '-f=${db:Status-Status}', 'nfs-common']",
                        "['--version']", "['-n', 'true']"])
                else:
                    self.assertFalse(calls.exists())


    def test_cli_emits_json_and_rejects_all_arguments_without_echo(self):
        probe = load_probe()
        self.assertTrue(hasattr(probe, 'main'), 'missing fixed CLI')
        with patch.object(probe, 'collect', return_value={'uid': 1001}) as collect, \
             patch.object(sys, 'argv', [str(SCRIPT)]), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(probe.main(), 0)
            self.assertEqual(json.loads(output.getvalue()), {'uid': 1001})
            collect.assert_called_once_with()
        result = subprocess.run([sys.executable, str(SCRIPT), '--endpoint=SENTINEL_SECRET'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=3, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout + result.stderr, b'')


if __name__ == '__main__':
    unittest.main()
