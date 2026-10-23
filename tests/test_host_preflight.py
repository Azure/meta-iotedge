"""Offline fixtures only; all temporary files use the configured TMPDIR."""
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'host-preflight.py'


class HostPreflightTests(unittest.TestCase):
    def test_disk_capacity_is_read_only_and_numeric(self):
        module = self.module()
        self.assertTrue(callable(getattr(module, 'disk_capacity', None)))
        mounts, _ = module.read_text(Path('/proc/self/mountinfo'), 1048576)
        result = module.disk_capacity(mounts)
        self.assertEqual(result['status'], 'ok')
        self.assertGreater(result['total_bytes'], 0)
        self.assertGreaterEqual(result['available_bytes'], 0)
        with patch.object(module.os, 'statvfs', side_effect=PermissionError):
            self.assertEqual(module.disk_capacity(mounts)['status'], 'unknown')

    def test_disk_locations_distinguish_workspace_mnt_and_cache_fallback_without_paths(self):
        module = self.module()
        mounts = '1 0 0:1 / / rw - ext4 secret rw\n'
        with tempfile.TemporaryDirectory(prefix='FAKE_CREDENTIAL_SENTINEL-') as tmp:
            with patch.dict(os.environ, {'GITHUB_WORKSPACE': tmp, 'SECRET': 'FAKE_CREDENTIAL_SENTINEL'}):
                def capacity_value(fd):
                    # Distinct fixture capacities prove workspace is not a cache alias.
                    blocks = 200 if os.readlink(f'/proc/self/fd/{fd}') == '/mnt' else 100
                    return os.statvfs_result((4096, 4096, blocks, 75, 60, 50, 40, 30, 0, 255))
                with patch.object(module.os, 'statvfs', side_effect=capacity_value):
                    result = module.disk_capacity(mounts)
            self.assertEqual(result['locations']['workspace']['total_bytes'], 409600)
            self.assertEqual(result['locations']['mnt']['total_bytes'], 819200)
            self.assertEqual(set(result['locations']), {'cache', 'cache_parent', 'root', 'workspace', 'mnt'})
            self.assertEqual(result['locations']['workspace']['status'], 'ok')
            self.assertEqual(result['locations']['mnt']['status'], 'ok')
            self.assertEqual(result['locations']['cache_parent']['status'], 'ok')
            self.assertEqual(result['locations']['workspace']['covering_filesystem'], 'ext4')
            self.assertNotIn(tmp, json.dumps(result))
            self.assertNotIn('FAKE_CREDENTIAL_SENTINEL', json.dumps(result))
            # No filesystem syscalls for invalid workspace values or remote mounts.
            for workspace in ('relative', '/bad/../path', '/bad/./path', '/bad\x00path', '/' + 'a' * 4096):
                with patch.object(module.os, 'environ', dict(os.environ, GITHUB_WORKSPACE=workspace)), \
                        patch.object(module, 'local_capacity', wraps=module.local_capacity) as capacity:
                    result = module.disk_capacity(mounts)
                    self.assertEqual(result['locations']['workspace']['reason'], 'invalid_workspace')
                    self.assertNotIn(workspace, [call.args[0] for call in capacity.call_args_list])
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(module.disk_capacity(mounts)['locations']['workspace']['reason'], 'workspace_unset')
            remote = mounts + f'2 1 0:2 / {tmp} rw - nfs4 secret rw\n'
            with patch.object(module.os, 'open', side_effect=AssertionError('remote path reached')):
                self.assertEqual(module.local_capacity(tmp, remote)['reason'], 'nonlocal_or_unknown_filesystem')
            (Path(tmp) / 'link').symlink_to('/var/cache', target_is_directory=True)
            self.assertEqual(module.local_capacity(tmp + '/link', mounts)['status'], 'unknown')

    def test_missing_mount_table_never_retries_against_another_proc_scope(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(module, 'read_text', wraps=module.read_text) as reader:
                result = module.collect(Path(tmp), Path(tmp) / 'cg')
            self.assertEqual(result['disk_capacity']['status'], 'unknown')
            self.assertFalse(any(str(call.args[0]) == '/proc/self/mountinfo' for call in reader.call_args_list))

    def test_selected_service_budgets_without_process_arguments(self):
        module = self.module()
        self.assertTrue(callable(getattr(module, 'service_budgets', None)))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'proc/123').mkdir(parents=True)
            (root / 'proc/123/comm').write_text('Runner.Listener\n')
            (root / 'proc/123/cgroup').write_text('0::/listener\n')
            (root / 'proc/123/cmdline').write_text('FAKE_CREDENTIAL_SENTINEL')
            (root / 'cg/listener').mkdir(parents=True)
            (root / 'cg/listener/memory.max').write_text('123456\n')
            mounts = '1 0 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n'
            with patch.object(module, 'read_text', wraps=module.read_text) as reader:
                result = module.service_budgets(root / 'proc', root / 'cg', mounts)
                self.assertFalse(any(str(call.args[0]).endswith('cmdline') for call in reader.call_args_list))
            instance = result['services']['Runner.Listener'][0]
            self.assertEqual(instance['visible_ancestors_including_self'][0]['memory.max']['value'], 123456)
            self.assertNotIn('FAKE_CREDENTIAL_SENTINEL', json.dumps(result))

    def test_cpu_quota_and_throttling_are_collected_with_memory(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'proc/self').mkdir(parents=True)
            (root / 'proc/self/cgroup').write_text('0::/job\n')
            (root / 'cg/job').mkdir(parents=True)
            (root / 'cg/job/cpu.max').write_text('200000 100000\n')
            (root / 'cg/job/cpu.stat').write_text('nr_throttled 12\nthrottled_usec 345\n')
            mounts = '1 0 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n'
            result = module.cgroup_memory(root / 'proc', root / 'cg', mounts)
            leaf = result['visible_ancestors_including_self'][0]
            self.assertIn('cpu.max', leaf)
            self.assertEqual(leaf['cpu.max']['quota_usec'], 200000)
            self.assertEqual(leaf['cpu.max']['period_usec'], 100000)
            self.assertEqual(leaf['cpu.stat']['nr_throttled']['value'], 12)

    def module(self):
        self.assertTrue(SCRIPT.is_file(), 'collector implementation is missing')
        spec = importlib.util.spec_from_file_location('host_preflight', SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_memory_is_numeric_allowlist_not_procfs_dump(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            (proc / 'meminfo').write_text(
                'MemTotal: 100 kB\nMemAvailable: 40 kB\nSwapTotal: 0 kB\n'
                'SwapFree: 0 kB\nPrivate: FAKE_CREDENTIAL_SENTINEL\n')
            result = module.memory(proc)
        self.assertEqual(result['MemTotal'], {'status': 'ok', 'bytes': 102400})
        self.assertEqual(result['SwapTotal'], {'status': 'ok', 'bytes': 0})
        self.assertEqual(result['MemFree']['status'], 'unknown')
        self.assertNotIn('FAKE_CREDENTIAL_SENTINEL', json.dumps(result))

    def test_read_guards_and_failures_remain_unknown_without_raw_input(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'read_text'), 'bounded reader missing')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'target'
            target.write_text('FAKE_CREDENTIAL_SENTINEL')
            (root / 'link').symlink_to(target)
            os.mkfifo(root / 'fifo')
            for name, reason in [('missing', 'missing'), ('link', 'unsafe'),
                                 ('fifo', 'unsafe'), ('target', 'too_large')]:
                text, status = module.read_text(root / name, limit=8)
                self.assertIsNone(text)
                self.assertEqual(status, reason)
            with patch.object(module.os, 'open', side_effect=PermissionError):
                self.assertEqual(module.read_text(target), (None, 'denied'))
            (root / 'meminfo').write_text('MemTotal: FAKE_CREDENTIAL_SENTINEL\n')
            self.assertEqual(module.memory(root)['MemTotal']['status'], 'unknown')
            self.assertNotIn('FAKE_CREDENTIAL_SENTINEL', json.dumps(module.memory(root)))

    def test_mount_diagnostics_are_counts_and_fixed_enums_not_raw_paths(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            (proc / 'self').mkdir()
            table = ('1 0 0:1 / / rw - ext4 FAKE_CREDENTIAL_SENTINEL rw\n'
                     'bad unrelated FAKE_CREDENTIAL_SENTINEL\n')
            (proc / 'self/mountinfo').write_text(table)
            result = module.collect(proc, proc / 'cg')
            self.assertEqual(result['execution_context']['mount_table'], {
                'status': 'partial', 'reason': 'invalid_rows_skipped',
                'valid_row_count': 1, 'invalid_row_count': 1})
            self.assertNotIn('FAKE_CREDENTIAL_SENTINEL', json.dumps(result))
            for text, reason in ((None, 'missing'), ('x' * 1048577, 'table_bound'),
                                 ('\n' * 4097, 'table_bound')):
                diagnostics = {}
                self.assertEqual(module.mount_records(text, diagnostics), [])
                self.assertEqual(diagnostics['status'], 'unknown')
                self.assertEqual(diagnostics['reason'], reason)
                self.assertIsNone(diagnostics['valid_row_count'])

    def test_invalid_covering_mount_blocks_io_without_erasing_unrelated_valid_rows(self):
        module = self.module()
        table = ('1 0 0:1 / / rw - ext4 secret rw\n'
                 '2 1 0:2 /../hidden /var/cache rw - nfs4 secret rw\n')
        with patch.object(module.os, 'open', side_effect=AssertionError('unsafe mount reached')):
            result = module.local_capacity('/var/cache', table)
        self.assertEqual(result['reason'], 'nonlocal_or_unknown_filesystem')
        self.assertEqual(module.cache_filesystem(table)['status'], 'unknown')
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            (proc / 'self').mkdir()
            (proc / 'self/cgroup').write_text('0::/job\n')
            table += ('3 1 0:3 / /sys/fs/cgroup rw - cgroup2 secret rw\n'
                      '4 3 0:4 /../hidden /sys/fs/cgroup/job rw - cgroup2 secret rw\n')
            with patch.object(module, 'read_text', wraps=module.read_text) as reader:
                result = module.cgroup_memory(proc, proc / 'cg', table)
                self.assertEqual(result['mapping']['reason'], 'shadowed_mount')
                self.assertEqual(reader.call_count, 1)

    def test_unrelated_invalid_mount_rows_do_not_discard_valid_rows(self):
        module = self.module()
        mounts = (
            '1 0 0:1 / / rw - ext4 /dev/root rw\n'
            'bad unrelated FAKE_CREDENTIAL_SENTINEL\n'
            '2 1 0:2 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n'
            '3 1 0:3 /bad\\000path /unrelated rw - tmpfs secret rw\n'
            '4 1 0:4 / /unrelated/../bad rw - tmpfs secret rw\n')
        self.assertEqual(module.cache_filesystem(mounts)['covering_filesystem'], 'ext4')
        self.assertEqual(module.mount_records(mounts),
                         [('/', '/', 'ext4'), ('/', '/sys/fs/cgroup', 'cgroup2'), (None, '/unrelated', None)])
        self.assertEqual(module.mount_records(mounts * 4097), [])
        self.assertNotIn('FAKE_CREDENTIAL_SENTINEL', json.dumps(module.cache_filesystem(mounts)))

    def test_cache_filesystem_never_exports_mount_source_or_options(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'cache_filesystem'), 'mountinfo parser missing')
        mounts = (
            '1 0 0:1 / / rw - ext4 /dev/root rw\n'
            '2 1 0:2 / /var/cache/yocto rw - nfs4 '
            '10.1.2.3:/FAKE_CREDENTIAL_SENTINEL rw,secret=FAKE_CREDENTIAL_SENTINEL\n')
        result = module.cache_filesystem(mounts)
        self.assertEqual(result, {'status': 'ok', 'covering_filesystem': 'nfs4',
                                 'exact_mountpoint': True, 'shared_filesystem_type': True})
        self.assertNotIn('FAKE_CREDENTIAL_SENTINEL', json.dumps(result))
        self.assertNotIn('10.1.2.3', json.dumps(result))
        local = module.cache_filesystem(mounts.splitlines()[0])
        self.assertFalse(local['exact_mountpoint'])
        self.assertFalse(local['shared_filesystem_type'])
        self.assertEqual(module.cache_filesystem('FAKE_CREDENTIAL_SENTINEL')['status'], 'unknown')

    def test_unavailable_mount_mapping_counts_remain_unknown_not_zero(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            (proc / 'self').mkdir()
            (proc / 'self/cgroup').write_text('0::/\n')
            for mounts in (None, 'x' * 1048577):
                result = module.cgroup_memory(proc, proc / 'cg', mounts)
                self.assertEqual(result['mapping']['reason'], 'mount_table_unavailable')
                self.assertIsNone(result['mapping']['candidate_count'])
                self.assertIsNone(result['mapping']['matching_candidate_count'])

    def test_nonstandard_cgroup_mount_maps_only_proven_membership_suffix(self):
        module = self.module()
        mounts = ('bad unrelated row\n'
                  '1 0 0:1 /tenant /sys/fs/cgroup/unified rw - cgroup2 secret rw\n')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'proc/self').mkdir(parents=True)
            (root / 'proc/self/cgroup').write_text('0::/tenant/job\n')
            (root / 'cg/unified/job').mkdir(parents=True)
            (root / 'cg/unified/job/memory.max').write_text('123\n')
            (root / 'cg/unified/memory.max').write_text('456\n')
            (root / 'cg/memory.max').write_text('999\n')
            result = module.cgroup_memory(root / 'proc', root / 'cg', mounts)
            self.assertEqual(result['status'], 'partial')
            self.assertEqual([entry['memory.max']['value'] for entry in
                              result['visible_ancestors_including_self']], [123, 456])
            self.assertEqual(result['mapping'], {
                'candidate_count': 1, 'matching_candidate_count': 1,
                'reason': 'mapped', 'root_is_global': False,
                'mountpoint_category': 'under_cgroup_root'})
            self.assertEqual(result['host_ancestor_coverage'], 'UNVERIFIED')
            self.assertNotIn('/tenant', json.dumps(result))
            # Namespace-relative '/' cannot be guessed to mean '/tenant'.
            for member in ('/', '/tenant2/job', '/other/job'):
                (root / 'proc/self/cgroup').write_text('0::' + member + '\n')
                with patch.object(module, 'read_text', wraps=module.read_text) as reader:
                    rejected = module.cgroup_memory(root / 'proc', root / 'cg', mounts)
                    self.assertEqual(rejected['status'], 'unknown')
                    self.assertEqual(rejected['mapping']['reason'], 'membership_not_covered')
                    self.assertEqual(reader.call_count, 1)
            # A namespace-visible global root and namespace-relative '/' are safe.
            (root / 'proc/self/cgroup').write_text('0::/\n')
            namespaced = mounts.replace('/tenant ', '/ ')
            result = module.cgroup_memory(root / 'proc', root / 'cg', namespaced)
            self.assertEqual(len(result['visible_ancestors_including_self']), 1)
            self.assertTrue(result['mapping']['root_is_global'])

    def test_cgroup_directory_symlinks_are_not_followed(self):
        module = self.module()
        mounts = '1 0 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'proc/self').mkdir(parents=True)
            (root / 'proc/self/cgroup').write_text('0::/job\n')
            (root / 'outside').mkdir()
            (root / 'outside/memory.max').write_text('123\n')
            (root / 'cg').mkdir()
            (root / 'cg/job').symlink_to(root / 'outside', target_is_directory=True)
            with patch.object(module, 'read_text', wraps=module.read_text) as reader:
                result = module.cgroup_memory(root / 'proc', root / 'cg', mounts)
                self.assertEqual(result['status'], 'unknown')
                self.assertEqual(result['mapping']['reason'], 'unsafe_or_unreadable_directory')
                self.assertEqual(reader.call_count, 1)

    def test_ambiguous_outside_shadowed_and_traversing_cgroup_mounts_do_not_read_metrics(self):
        module = self.module()
        valid = '1 0 0:1 / /sys/fs/cgroup rw - cgroup2 secret rw\n'
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            (proc / 'self').mkdir()
            (proc / 'self/cgroup').write_text('0::/job\n')
            cases = [
                (valid + valid, 'ambiguous_candidates'),
                (valid + '2 1 0:2 /../hidden /sys/fs/cgroup rw - cgroup2 secret rw\n', 'shadowed_mount'),
                (valid.replace('/sys/fs/cgroup', '/outside'), 'membership_not_covered'),
                (valid.replace('/sys/fs/cgroup', '/sys/fs/cgroup/../outside'), 'membership_not_covered'),
                (valid + '2 1 0:2 / /sys/fs/cgroup/job rw - tmpfs secret rw\n', 'shadowed_mount'),
            ]
            for mounts, reason in cases:
                with self.subTest(reason=reason), patch.object(module, 'read_text', wraps=module.read_text) as reader:
                    result = module.cgroup_memory(proc, proc / 'cg', mounts)
                    self.assertEqual(result['status'], 'unknown')
                    self.assertEqual(result['mapping']['reason'], reason)
                    self.assertEqual(reader.call_count, 1)

    def test_v2_ancestors_preserve_finite_unlimited_missing_and_bad_counters(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'cgroup_memory'), 'cgroup collector missing')
        with tempfile.TemporaryDirectory() as tmp:
            proc, cg = Path(tmp) / 'proc', Path(tmp) / 'cg'
            (proc / 'self').mkdir(parents=True)
            leaf = cg / 'service' / 'worker'
            leaf.mkdir(parents=True)
            (proc / 'self/cgroup').write_text('0::/service/worker\n')
            (leaf / 'memory.current').write_text('123\n')
            (leaf / 'memory.max').write_text('max\n')
            (leaf / 'memory.peak').write_text('FAKE_CREDENTIAL_SENTINEL\n')
            (cg / 'service/memory.max').write_text('456\n')
            (leaf / 'memory.events').write_text('oom 2\noom_kill 1\nsecret FAKE_CREDENTIAL_SENTINEL\n')
            (leaf / 'memory.stat').write_text('anon 100\nfile 23\ninactive_file 20\n')
            mounts = '1 0 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n'
            result = module.cgroup_memory(proc, cg, mounts)
            self.assertEqual(result['version'], 'v2')
            self.assertEqual(len(result['visible_ancestors_including_self']), 3)
            self.assertEqual(result['visible_ancestors_including_self'][0]['memory.current'],
                             {'status': 'ok', 'value': 123})
            self.assertEqual(result['visible_ancestors_including_self'][0]['memory.max'],
                             {'status': 'unlimited'})
            self.assertEqual(result['visible_ancestors_including_self'][1]['memory.max']['value'], 456)
            self.assertEqual(result['visible_ancestors_including_self'][0]['memory.peak']['status'], 'unknown')
            self.assertEqual(result['visible_ancestors_including_self'][2]['memory.max']['status'], 'unknown')
            self.assertEqual(result['visible_ancestors_including_self'][0]['memory.events']['oom']['value'], 2)
            self.assertEqual(result['visible_ancestors_including_self'][0]['memory.stat']['file']['value'], 23)
            self.assertEqual(result['host_ancestor_coverage'], 'UNVERIFIED')
            self.assertNotIn('FAKE_CREDENTIAL_SENTINEL', json.dumps(result))
            (proc / 'self/cgroup').write_text('5:memory:/service\n')
            self.assertEqual(module.cgroup_memory(proc, cg, mounts)['version'], 'v1')
            (proc / 'self/cgroup').write_text('0::/../../secret\n')
            with patch.object(module, 'read_text', wraps=module.read_text) as reader:
                self.assertEqual(module.cgroup_memory(proc, cg, mounts)['status'], 'unknown')
                self.assertEqual(reader.call_count, 1)
            (proc / 'self/cgroup').unlink()
            self.assertEqual(module.cgroup_memory(proc, cg, mounts)['reason'], 'missing')
            with patch.object(module, 'read_text', return_value=(None, 'denied')):
                self.assertEqual(module.cgroup_memory(proc, cg, mounts)['reason'], 'denied')

    def test_pressure_and_readiness_are_allowlisted_not_mount_authorization(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'pressure'), 'pressure parser missing')
        self.assertTrue(hasattr(module, 'prerequisites'), 'prerequisite checks missing')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'pressure').write_text('some avg10=1.25 avg60=0.00 avg300=0.50 total=123\n'
                                           'full FAKE_CREDENTIAL_SENTINEL\n')
            result = module.pressure(root / 'pressure')
            self.assertEqual(result['some']['avg10'], 1.25)
            self.assertEqual(result['some']['total_usec'], 123)
            self.assertEqual(result['full']['status'], 'unknown')
            (root / 'filesystems').write_text('nodev\tsysfs\n\tnfs\n\tnfs4\nFAKE_CREDENTIAL_SENTINEL\n')
            with patch.object(module, 'binary_present', return_value=True):
                ready = module.prerequisites(root)
            self.assertTrue(ready['sudo_binary_present'])
            self.assertEqual(ready['mount_privilege'], 'UNVERIFIED')
            self.assertEqual(ready['nfs_kernel_registered'], {'status': 'ok', 'present': True})
            self.assertNotIn('FAKE_CREDENTIAL_SENTINEL', json.dumps(ready))
            (root / 'filesystems').unlink()
            self.assertEqual(module.prerequisites(root)['nfs_kernel_registered']['status'], 'unknown')

    def test_cli_emits_exact_artifact_with_no_fixture_or_ref_inputs(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'collect'), 'collector entry point missing')
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            (proc / 'self').mkdir()
            (proc / 'self/mountinfo').write_text(
                '1 0 0:1 / / rw - ext4 FAKE_CREDENTIAL_SENTINEL secret=FAKE_CREDENTIAL_SENTINEL\n')
            (proc / 'meminfo').write_text('MemTotal: ' + '9' * 5000 + ' kB\n')
            actual_collect = module.collect
            output = io.StringIO()
            with patch.object(module, 'collect', side_effect=lambda: actual_collect(proc, proc / 'cg')), \
                    contextlib.redirect_stdout(output), patch.dict(os.environ, {'SECRET': 'FAKE_CREDENTIAL_SENTINEL'}):
                self.assertEqual(module.main([]), 0)
            artifact = json.loads(output.getvalue())
            self.assertEqual(set(artifact), {'schema_version', 'execution_context', 'user', 'prerequisites',
                                            'cache_path', 'memory', 'memory_pressure', 'self_cgroup', 'service_budgets',
                                            'cpu_pressure', 'io_pressure', 'disk_capacity', 'host_identity'})
            self.assertEqual(artifact['memory']['MemTotal']['status'], 'unknown')
            self.assertEqual(artifact['execution_context']['idle_host'], 'UNVERIFIED')
            self.assertEqual(artifact['service_budgets']['status'], 'unknown')
            self.assertNotIn('FAKE_CREDENTIAL_SENTINEL', output.getvalue())
        # This read-only CLI execution is on the Hermes VM, NOT a 1ES measurement.
        completed = subprocess.run([sys.executable, str(SCRIPT)], text=True,
                                   capture_output=True, timeout=10, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, '')
        self.assertEqual(json.loads(completed.stdout)['schema_version'], 1)
        rejected = subprocess.run([sys.executable, str(SCRIPT), '--proc-root=FAKE_CREDENTIAL_SENTINEL'],
                                  text=True, capture_output=True, timeout=10, check=False)
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(rejected.stdout, '')
        self.assertNotIn('FAKE_CREDENTIAL_SENTINEL', rejected.stderr)
        self.assertNotIn('Traceback', rejected.stderr)

    def test_workflow_is_manual_host_job_with_pinned_exact_artifact(self):
        path = SCRIPT.parents[1] / '.github/workflows/host-preflight.yml'
        self.assertTrue(path.is_file(), 'manual workflow missing')
        text = path.read_text()
        self.assertIn('\non: workflow_dispatch\n', text)
        self.assertNotIn('  push:', text)
        self.assertNotIn('sparse-checkout:', text)
        self.assertIn('timeout-minutes: 2', text)
        for label in ('self-hosted', '1ES.Pool=meta-iotedge-1es-github-linux-amd64',
                      '1ES.ImageOverride=agent-aziotedge-ubuntu-22.04-msmoby'):
            self.assertIn(label, text)
        self.assertIn('actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1', text)
        self.assertIn('ref: ${{ github.workflow_sha }}', text)
        self.assertIn('persist-credentials: false', text)
        self.assertIn('actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a', text)
        self.assertIn('          path: host-preflight-source\n', text)
        self.assertIn('path: host-preflight-source/host-preflight.json\n', text)
        self.assertIn('if-no-files-found: error', text)
        self.assertIn('python3 host-preflight-source/scripts/host-preflight.py > host-preflight-source/host-preflight.json', text)
        for excluded in ('container:', 'build.sh', 'bitbake', 'sudo ', 'secrets.', 'inputs.',
                         'pull_request:', 'workflow_call:', 'cancel-in-progress: true'):
            self.assertNotIn(excluded, text.lower())
        self.assertEqual(text.count('uses:'), 2)
        self.assertEqual(text.count('run:'), 1)

    def test_workflow_collector_uses_isolated_source_and_output_paths(self):
        workflow = (SCRIPT.parents[1] / '.github/workflows/host-preflight.yml').read_text()
        command = next(line.strip().removeprefix('run: ') for line in workflow.splitlines()
                       if line.strip().startswith('run: '))
        with tempfile.TemporaryDirectory(prefix='host-checkout-path-') as tmp:
            root = Path(tmp)
            source = root / 'host-preflight-source/scripts'
            source.mkdir(parents=True)
            (source / 'host-preflight.py').write_text('print(\'{"fixture": true}\')\n')
            (root / '.git').mkdir()
            (root / '.git/config').write_text('default checkout sentinel\n')
            result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', command],
                                    cwd=root, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            artifact = root / 'host-preflight-source/host-preflight.json'
            self.assertEqual(json.loads(artifact.read_text()), {'fixture': True})
            self.assertFalse((root / 'host-preflight.json').exists())
            self.assertEqual((root / '.git/config').read_text(), 'default checkout sentinel\n')
            self.assertIn('          path: ' + str(artifact.relative_to(root)) + '\n', workflow)

    def test_malformed_membership_stops_before_counter_reads_without_traceback(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            (proc / 'self').mkdir()
            (proc / 'self/cgroup').write_bytes(b'0::/bad\x00FAKE_CREDENTIAL_SENTINEL\n')
            mounts = '1 0 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n'
            with patch.object(module, 'read_text', wraps=module.read_text) as reader:
                try:
                    result = module.cgroup_memory(proc, proc / 'cg', mounts)
                except ValueError:
                    self.fail('malformed membership reached filesystem path handling')
                self.assertEqual(result['status'], 'unknown')
                self.assertEqual(reader.call_count, 1)
                self.assertNotIn('FAKE_CREDENTIAL_SENTINEL', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
