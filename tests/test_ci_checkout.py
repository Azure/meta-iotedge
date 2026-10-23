"""Replay checkout's sparse-state transition only in disposable Git repositories."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/ci-build.yml'


def repair_fragment():
    text = WORKFLOW.read_text()
    marker = '      - name: Materialize full checkout\n'
    if marker not in text:
        return ':'  # Baseline checkout has no repair: assert the missing source.
    step = text.split(marker, 1)[1].split('\n      - name:', 1)[0]
    return textwrap.dedent(step.split('        run: |\n', 1)[1])


class CheckoutTests(unittest.TestCase):
    def git(self, root, *args):
        result = subprocess.run(['git', *args], cwd=root, text=True, capture_output=True,
                                env=self.env, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def fixture(self, root):
        # No global Git configuration, hooks, remotes, or paths outside the fixture.
        self.env = {**os.environ, 'GIT_CONFIG_NOSYSTEM': '1',
                    'GIT_CONFIG_GLOBAL': os.devnull, 'HOME': str(root)}
        self.git(root, 'init', '-q')
        self.git(root, 'config', 'user.name', 'Fixture')
        self.git(root, 'config', 'user.email', 'fixture@example.invalid')
        files = {'scripts/fetch.sh': '#!/bin/sh\nexit 0\n',
                 'scripts/build.sh': '#!/bin/sh\nexit 0\n',
                 'scripts/validate-qemu.sh': '#!/bin/sh\nexit 0\n',
                 'docs/source file.md': 'source content\n'}
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            if name.endswith('.sh'):
                path.chmod(0o755)
        self.git(root, 'add', '.')
        self.git(root, 'commit', '-qm', 'build source')
        target = self.git(root, 'rev-parse', 'HEAD')
        for name in ('scripts/host-preflight.py', '.github/workflows/host-preflight.yml',
                     'docs/host-preflight.md', 'tests/test_host_preflight.py'):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('probe only\n')
        self.git(root, 'add', '.')
        self.git(root, 'commit', '-qm', 'diagnostic source')
        # Pinned checkout's non-cone mode writes only the local setting and
        # appends this pattern; do not pre-inject worktree configuration.
        self.git(root, 'config', '--local', 'core.sparseCheckout', 'true')
        (root / '.git/info/sparse-checkout').write_text('\nscripts/host-preflight.py\n')
        self.git(root, 'read-tree', '-mu', 'HEAD')
        self.assertFalse((root / 'scripts/fetch.sh').exists())
        # Exact relevant built-ins from pinned actions/checkout, not a proposed fix.
        self.git(root, 'clean', '-ffdx')
        self.git(root, 'reset', '--hard', 'HEAD')
        self.git(root, 'sparse-checkout', 'disable')
        # Git 2.34.1 leaves local true effective already; newer Git writes a
        # worktree false override, which the next command stops reading.
        self.assertEqual(self.git(root, 'config', '--local', '--get', 'core.sparseCheckout'), 'true')
        self.assertEqual(self.git(root, 'config', '--local', '--get', 'extensions.worktreeConfig'), 'true')
        self.git(root, 'config', '--local', '--unset-all', 'extensions.worktreeConfig')
        checkout = subprocess.run(['git', 'checkout', '--progress', '--force', target],
                                  cwd=root, env=self.env, text=True, capture_output=True)
        self.assertEqual(checkout.returncode, 0, checkout.stderr)
        self.assertIn("Path '.github/workflows/host-preflight.yml' not uptodate", checkout.stderr)
        self.assertEqual(self.git(root, 'rev-parse', 'HEAD'), target)
        self.assertEqual(self.git(root, 'config', '--get', 'core.sparseCheckout'), 'true')

        self.assertFalse((root / 'scripts/fetch.sh').exists(), 'repro must lose source despite exit 0')
        self.assertIn('S scripts/fetch.sh', self.git(root, 'ls-files', '-t'))
        return files

    def test_reused_sparse_checkout_materializes_full_tracked_source(self):
        with tempfile.TemporaryDirectory(prefix='checkout-regression-') as tmp:
            root = Path(tmp)
            files = self.fixture(root)
            (root / 'untracked-sentinel').write_text('do not delete\n')
            result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', repair_fragment()],
                                    cwd=root, env=self.env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name, content in files.items():
                self.assertTrue((root / name).is_file(), f'checkout omitted {name}')
                self.assertEqual((root / name).read_text(), content)
                if name.endswith('.sh'):
                    self.assertTrue(os.access(root / name, os.X_OK))
            self.assertFalse(any(line.startswith('S ') for line in self.git(root, 'ls-files', '-t').splitlines()))
            self.assertEqual(self.git(root, 'diff', '--cached', '--exit-code'), '')
            self.assertEqual(self.git(root, 'diff', '--exit-code'), '')
            self.assertEqual(self.git(root, 'status', '--porcelain'), '?? untracked-sentinel')
            self.assertEqual((root / 'untracked-sentinel').read_text(), 'do not delete\n')
            # Repair is repeatable without deleting untracked build/cache data.
            subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', repair_fragment()],
                           cwd=root, env=self.env, check=True, capture_output=True)


    def test_git_errors_preserve_failure_and_block_fetch(self):
        for command in ('config', 'ls-files', 'update-index', 'restore'):
            with self.subTest(command=command), tempfile.TemporaryDirectory(prefix='checkout-failure-') as tmp:
                root = Path(tmp)
                self.fixture(root)
                binary = root / 'bin/git'
                binary.parent.mkdir()
                binary.write_text('#!/bin/sh\nif [ "$1" = "$FAIL_GIT_COMMAND" ]; then exit 37; fi\nexec "$REAL_GIT" "$@"\n')
                binary.chmod(0o755)
                env = {**self.env, 'FAIL_GIT_COMMAND': command, 'REAL_GIT': shutil.which('git'),
                       'PATH': str(binary.parent) + os.pathsep + os.environ['PATH']}
                result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c',
                                         repair_fragment() + '\ntouch fetch-layer-reached'],
                                        cwd=root, env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 37, result.stdout + result.stderr)
                self.assertFalse((root / 'fetch-layer-reached').exists())

    def test_workflow_repairs_before_user_cache_or_fetch_steps(self):
        text = WORKFLOW.read_text().split('\n  build:\n', 1)[1]
        self.assertIn('shell: bash', text)
        repair = text.index('- name: Materialize full checkout')
        for name in ('Create build user', 'Fix permissions', 'Show cache status', 'Fetch layers'):
            self.assertLess(repair, text.index('- name: ' + name))
        step = text[repair:].split('\n      - name:', 1)[0]
        self.assertNotIn('continue-on-error:', step)
        self.assertNotIn('        if:', step)
        self.assertIn('actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1', text)

    def test_missing_empty_or_nonexecutable_required_script_blocks_fetch(self):
        for name in ('fetch.sh', 'build.sh', 'validate-qemu.sh'):
            for damage in ('missing', 'empty', 'nonexecutable'):
                with self.subTest(name=name, damage=damage), tempfile.TemporaryDirectory(prefix='checkout-gate-') as tmp:
                    root = Path(tmp)
                    self.fixture(root)
                    # First restore with known Git commands, then commit the bad
                    # source so the real workflow repair cannot conceal it.
                    self.git(root, 'config', '--local', 'core.sparseCheckout', 'false')
                    self.git(root, 'update-index', '--no-skip-worktree', '--',
                             'scripts/fetch.sh', 'scripts/build.sh', 'scripts/validate-qemu.sh', 'docs/source file.md')
                    self.git(root, 'restore', '--source=HEAD', '--staged', '--worktree',
                             '--ignore-skip-worktree-bits', '--', '.')
                    script = root / 'scripts' / name
                    if damage == 'missing':
                        script.unlink()
                    elif damage == 'empty':
                        script.write_text('')
                    else:
                        script.chmod(0o644)
                    self.git(root, 'add', '-A')
                    self.git(root, 'commit', '-qm', 'unsupported source fixture')
                    result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c',
                                             repair_fragment() + '\ntouch fetch-layer-reached'],
                                            cwd=root, env=self.env, text=True, capture_output=True)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('Checkout missing required executable: scripts/' + name, result.stderr)
                    self.assertFalse((root / 'fetch-layer-reached').exists())


if __name__ == '__main__':
    unittest.main()
