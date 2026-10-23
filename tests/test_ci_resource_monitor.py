"""Stdlib tests; fixtures exercise APIs, subprocesses exercise the real CLI."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import io

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci-resource-monitor.py"


def load_monitor():
    spec = importlib.util.spec_from_file_location("ci_resource_monitor", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MonitorTests(unittest.TestCase):
    def test_disk_fixtures_report_capacity_and_unknown_without_reading_contents(self):
        monitor = load_monitor()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / 'cache-private-path'
            cache.mkdir()
            marker = cache / 'private-cache-content'
            marker.write_text('must-not-be-read-or-changed')
            space = os.statvfs(root)
            with patch.object(Path, 'open', side_effect=AssertionError('no content reads')):
                disks = monitor.collect_disks(root, root, cache)
            self.assertTrue(disks['workspace_cache_same_device'])
            entry = disks['cache']
            self.assertEqual(entry['bytes_total'], space.f_blocks * space.f_frsize)
            self.assertEqual(entry['inodes_total'], space.f_files)
            self.assertEqual(set(entry), {'status', 'uid', 'gid', 'mode', 'bytes_total',
                                         'bytes_free', 'bytes_available', 'inodes_total',
                                         'inodes_free', 'inodes_available'})
            missing = root / 'missing'
            disks = monitor.collect_disks(root, root, missing)
            self.assertEqual(disks['cache'], {'status': 'unknown', 'errno': 2})
            self.assertIsNone(disks['workspace_cache_same_device'])
            self.assertFalse(missing.exists())
            for operation in ('stat', 'statvfs'):
                original = getattr(monitor.os, operation)

                def fail_cache(path):
                    if path == cache:
                        raise PermissionError(13, 'private failure text', str(cache))
                    return original(path)

                with self.subTest(operation=operation), \
                        patch.object(monitor.os, operation, side_effect=fail_cache):
                    disks = monitor.collect_disks(root, root, cache)
                self.assertEqual(disks['cache'], {'status': 'unknown', 'errno': 13})
                self.assertEqual(disks['workspace']['status'], 'ok')
                self.assertIsNone(disks['workspace_cache_same_device'])
                self.assertNotIn('private', json.dumps(disks))
            self.assertEqual(marker.read_text(), 'must-not-be-read-or-changed')

    def test_disk_device_comparison_does_not_emit_identifiers(self):
        from types import SimpleNamespace
        monitor = load_monitor()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / 'cache'
            cache.mkdir()
            real_stat = os.stat

            def metadata(path):
                result = real_stat(path)
                return SimpleNamespace(st_dev=987654321 if path == cache else 123456789,
                                       st_uid=result.st_uid, st_gid=result.st_gid,
                                       st_mode=result.st_mode)

            with patch.object(monitor.os, 'stat', side_effect=metadata):
                disks = monitor.collect_disks(root, root, cache)
            self.assertFalse(disks['workspace_cache_same_device'])
            self.assertNotIn('987654321', json.dumps(disks))
            self.assertNotIn('123456789', json.dumps(disks))

    def test_closed_warning_pipe_does_not_mask_child_exit37(self):
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                blocked = Path(tmp) / 'not-a-directory'
                blocked.write_text('fixture')
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), '--output-dir', str(blocked), '--label', 'build',
                     '--', sys.executable, '-c', 'raise SystemExit(37)'],
                    stdout=subprocess.PIPE, stderr=write_fd, text=True, timeout=10)
                self.assertEqual(result.returncode, 37, result.stdout)
        finally:
            os.close(write_fd)

    def test_closed_console_pipe_does_not_mask_child_exit37(self):
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), '--output-dir', tmp, '--label', 'build',
                     '--', sys.executable, '-c', 'raise SystemExit(37)'],
                    stdout=write_fd, stderr=subprocess.PIPE, text=True, timeout=10)
                self.assertEqual(result.returncode, 37, result.stderr)
                report = json.loads((Path(tmp) / 'summary.json').read_text())
                self.assertEqual(report['child_returncode'], 37)
        finally:
            os.close(write_fd)

    def test_live_disk_periodic_output_is_at_most_once_per_minute(self):
        monitor = load_monitor()
        now = [0.0]

        def run(command, interval, periodic):
            for instant in (0.1, 59.9, 60.0, 60.1, 119.9, 120.0):
                now[0] = instant
                periodic()
            return 37, None, False, None

        with tempfile.TemporaryDirectory() as tmp:
            console = []
            with patch.object(monitor.time, 'monotonic', side_effect=lambda: now[0]), \
                    patch.object(monitor, 'run_command', side_effect=run), \
                    patch.object(monitor.os, 'write', side_effect=lambda fd, data: console.append(data)):
                code = monitor.main(['--output-dir', tmp, '--label', 'build', '--', 'unused'])
            self.assertEqual(code, 37)
            records = [json.loads(line.decode().split(': ', 1)[1]) for line in console]
            self.assertEqual([r['phase'] for r in records], ['start', 'periodic', 'periodic', 'end'])
            self.assertEqual([r['elapsed_seconds'] for r in records], [0.0, 60.0, 120.0, 120.0])
            samples = (Path(tmp) / 'samples.jsonl').read_text().splitlines()
            self.assertEqual(len(samples), 8)  # Artifact cadence is not reduced.

    def test_live_disk_lines_survive_artifact_failure_without_changing_exit37(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocked = Path(tmp) / 'not-a-directory'
            blocked.write_text('fixture')
            result = subprocess.run(
                [sys.executable, str(SCRIPT), '--output-dir', str(blocked),
                 '--label', 'private-label', '--interval', '0.01', '--',
                 sys.executable, '-c', 'import time; time.sleep(0.08); raise SystemExit(37)'],
                cwd=tmp, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 37, result.stderr)
            lines = [line for line in result.stdout.splitlines()
                     if line.startswith('resource-monitor disk: ')]
            self.assertEqual(len(lines), 2, result.stdout)
            records = [json.loads(line.split(': ', 1)[1]) for line in lines]
            self.assertEqual([r['phase'] for r in records], ['start', 'end'])
            self.assertTrue(all(r['scope'] == 'container-visible' for r in records))
            for line, record in zip(lines, records):
                self.assertLess(len(line), 1024)
                self.assertEqual(set(record['disks']),
                                 {'container_root', 'workspace', 'cache', 'workspace_cache_same_device'})
                self.assertEqual(set(record['disks']['workspace']),
                                 {'status', 'bytes_available', 'inodes_available'})
                self.assertNotIn(tmp, line)
                self.assertNotIn('private-label', line)
            self.assertIn('warning', result.stderr)

    def test_cli_records_only_selected_disk_metadata_and_preserves_exit37(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), '--output-dir', str(root / 'out'),
                 '--label', 'build', '--', sys.executable, '-c',
                 'raise SystemExit(37)', 'private-command-argument'], cwd=root,
                env=dict(os.environ, PRIVATE_ENV='private-environment-value'),
                capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 37, result.stderr)
            report = json.loads((root / 'out/summary.json').read_text())
            self.assertIn('disks', report['end_sample'])
            disks = report['end_sample']['disks']
            self.assertEqual(set(disks), {'container_root', 'workspace', 'cache',
                                         'workspace_cache_same_device'})
            workspace = disks['workspace']
            self.assertEqual(workspace['status'], 'ok')
            stat = root.stat()
            self.assertEqual((workspace['uid'], workspace['gid'], workspace['mode']),
                             (stat.st_uid, stat.st_gid, stat.st_mode))
            for field in ('bytes_total', 'bytes_free', 'bytes_available',
                          'inodes_total', 'inodes_free', 'inodes_available'):
                self.assertIsInstance(workspace[field], int)
                self.assertGreaterEqual(workspace[field], 0)
            output = result.stdout + result.stderr + (root / 'out/summary.json').read_text()
            output += (root / 'out/samples.jsonl').read_text()
            for private in ('private-command-argument', 'private-environment-value', str(root)):
                self.assertNotIn(private, output)
            self.assertNotIn('st_dev', json.dumps(disks))
            self.assertEqual(report['child_returncode'], 37)

    def test_cgroup_subtree_discovery_and_bounded_unavailable_reads(self):
        monitor = load_monitor()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = root / "proc"
            (proc / "self").mkdir(parents=True)
            (proc / "pressure").mkdir()
            mount = root / "mounted cgroup"
            group = mount / "job"
            group.mkdir(parents=True)
            (proc / "self/cgroup").write_text("0::/tenant/job\n")
            escaped_mount = str(mount).replace(" ", r"\040")
            (proc / "self/mountinfo").write_text(
                f"27 22 0:23 /tenant {escaped_mount} rw - cgroup2 cgroup rw\n")
            (proc / "meminfo").write_text("MemTotal: 1234 kB\n")
            (proc / "loadavg").write_text("1.0 2.0 3.0 1/10 99\n")
            (proc / "pressure/memory").write_text("some avg10=1.0\n")
            (group / "memory.current").write_text("123\n")
            (group / "memory.max").write_text("max\n")
            (group / "io.stat").write_text("x" * 200)
            snapshot = monitor.collect_snapshot(proc_root=proc, read_limit=64)
            self.assertEqual(snapshot["scope"], "container-visible")
            self.assertEqual(snapshot["cgroup"]["path"], str(group))
            self.assertEqual(snapshot["cgroup"]["mapping"], "mount-root-relative")
            self.assertEqual(snapshot["cgroup"]["files"]["memory.current"]["text"], "123\n")
            self.assertEqual(snapshot["cgroup"]["files"]["memory.max"]["text"], "max\n")
            self.assertEqual(snapshot["cgroup"]["files"]["memory.events"]["status"], "absent")
            self.assertEqual(snapshot["cgroup"]["files"]["io.stat"]["status"], "truncated")
            self.assertEqual(len(snapshot["cgroup"]["files"]["io.stat"]["text"]), 64)
            self.assertEqual(snapshot["proc"]["pressure/cpu"]["status"], "absent")
            self.assertEqual(snapshot["proc"]["pressure/memory"]["status"], "ok")
            self.assertEqual(snapshot["proc"]["meminfo"]["text"], "MemTotal: 1234 kB\n")

    def test_namespaced_membership_resolves_under_visible_mount(self):
        monitor = load_monitor()
        for membership, child_path, expected_mapping in (
                ("/", "", "namespace-root-fallback"),
                ("/nested", "nested", "namespace-relative-fallback"),
                ("/../../outside", "", "namespace-root-fallback")):
            with self.subTest(membership=membership), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                proc = root / "proc"
                (proc / "self").mkdir(parents=True)
                mount = root / "visible"
                group = mount / child_path
                group.mkdir(parents=True)
                (group / "memory.current").write_text("42\n")
                (proc / "self/cgroup").write_text(f"0::{membership}\n")
                (proc / "self/mountinfo").write_text(
                    f"27 22 0:23 /host/container {mount} rw - cgroup2 cgroup rw\n")
                found = monitor.discover_cgroup(proc)
                self.assertEqual(found["status"], "ok")
                self.assertEqual(found["path"], str(group))
                self.assertEqual(found["mapping"], expected_mapping)

    def test_discovery_handles_large_mountinfo_without_unbounded_reads(self):
        monitor = load_monitor()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = root / "proc"
            (proc / "self").mkdir(parents=True)
            mount = root / "group"
            mount.mkdir()
            (proc / "self/cgroup").write_text("0::/\n")
            unrelated_mount = "1 0 0:1 / /unrelated rw - tmpfs tmpfs rw\n"
            (proc / "self/mountinfo").write_text(unrelated_mount * 3000 +
                f"27 22 0:23 / {mount} rw - cgroup2 cgroup rw\n")
            found = monitor.discover_cgroup(proc)
            self.assertEqual(found["status"], "ok")
            self.assertEqual(found["path"], str(mount))
            (proc / "self/mountinfo").write_text("x" * (1024 * 1024 + 1))
            found = monitor.discover_cgroup(proc)
            self.assertEqual(found["status"], "unavailable")
            self.assertEqual(found["mountinfo_status"], "truncated")

    def test_unavailable_and_unsupported_sources_are_explicit(self):
        monitor = load_monitor()
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp) / "proc"
            (proc / "self").mkdir(parents=True)
            snapshot = monitor.collect_snapshot(proc_root=proc)
            self.assertEqual(snapshot["cgroup"]["status"], "unavailable")
            self.assertEqual(snapshot["cgroup"]["membership_status"], "absent")
            self.assertTrue(all(item["status"] == "absent" for item in snapshot["proc"].values()))
            (proc / "self/cgroup").write_text("3:memory:/legacy\n")
            (proc / "self/mountinfo").write_text("1 0 0:1 / /legacy rw - cgroup cgroup rw\n")
            snapshot = monitor.collect_snapshot(proc_root=proc)
            self.assertEqual(snapshot["cgroup"]["status"], "unsupported")
            self.assertTrue(all(item["status"] == "unavailable"
                                for item in snapshot["cgroup"]["files"].values()))
        # Permission/unsupported read failures need injection to work equally as
        # root and non-root; all discovery/missing-file tests above use files.
        for number, status in ((13, "permission-denied"), (1, "permission-denied"),
                               (95, "unsupported"), (38, "unsupported"), (5, "unavailable")):
            with self.subTest(errno=number), patch.object(Path, "open", side_effect=OSError(number, "private")):
                result = monitor.read_bounded("unused")
                self.assertEqual(result["status"], status)
                self.assertEqual(result["errno"], number)
                self.assertNotIn("private", json.dumps(result))

    def test_periodic_snapshots_include_real_allowlisted_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output-dir", tmp, "--label", "build",
                 "--interval", "0.04", "--", sys.executable, "-c",
                 "import time; time.sleep(0.22)"], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            samples = [json.loads(line) for line in (Path(tmp) / "samples.jsonl").read_text().splitlines()]
            self.assertEqual(samples[0]["phase"], "start")
            self.assertEqual(samples[-1]["phase"], "end")
            self.assertGreaterEqual(sum(s["phase"] == "periodic" for s in samples), 2)
            self.assertEqual(samples[0]["proc"]["meminfo"]["status"], "ok")
            self.assertIn("memory.current", samples[-1]["cgroup"]["files"])
            self.assertEqual([s["elapsed_seconds"] for s in samples],
                             sorted(s["elapsed_seconds"] for s in samples))
            self.assertTrue(all(s["scope"] == "container-visible" for s in samples))
            summary = json.loads((Path(tmp) / "summary.json").read_text())
            self.assertEqual(summary["samples_written"], len(samples))
            self.assertEqual(summary["end_sample"]["phase"], "end")

    def test_diagnostics_write_failure_does_not_change_command_status(self):
        for failure in ("directory", "sample-write"):
            for code in (0, 37):
                with self.subTest(failure=failure, code=code), tempfile.TemporaryDirectory() as tmp:
                    output = Path(tmp) / "diagnostics"
                    if failure == "directory":
                        output.write_text("not a directory")
                    else:
                        output.mkdir()
                        (output / "samples.jsonl").symlink_to("/dev/full")
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT), "--output-dir", str(output),
                         "--label", "build", "--", sys.executable, "-c",
                         f"print('executed once'); raise SystemExit({code})"],
                        capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, code, result.stderr)
                    self.assertEqual(result.stdout.count("executed once"), 1)
                    self.assertIn("warning", result.stderr.lower())
                    self.assertNotIn("Traceback", result.stderr)
                    if failure == "sample-write":
                        summary = json.loads((output / "summary.json").read_text())
                        self.assertTrue(summary["diagnostics_write_failed"])
                        self.assertEqual(summary["child_returncode"], code)

    def test_sample_cap_reserves_final_record_and_bounds_large_records(self):
        monitor = load_monitor()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            writer = monitor.SampleWriter(output, max_bytes=2048, record_bytes=512)
            with patch.object(monitor, "console_line"):
                for i in range(100):
                    writer.write({"phase": "start" if i == 0 else "periodic",
                                  "scope": "container-visible", "text": "x" * 350})
            writer.write({"phase": "end", "scope": "container-visible", "text": "x" * 5000}, final=True)
            writer.close()
            data = (output / "samples.jsonl").read_bytes()
            self.assertLessEqual(len(data), 2048)
            records = [json.loads(line) for line in data.splitlines()]
            self.assertEqual(records[0]["phase"], "start")
            self.assertEqual(records[-1]["phase"], "end")
            self.assertEqual(records[-1]["status"], "telemetry-record-too-large")
            self.assertTrue(writer.capped)
            self.assertGreater(writer.dropped, 0)
            self.assertEqual(writer.written, len(records))

    def test_summary_is_separate_and_complete_after_sample_cap(self):
        monitor = load_monitor()
        writer_class = monitor.SampleWriter
        with tempfile.TemporaryDirectory() as tmp:
            def small_writer(output):
                return writer_class(output, max_bytes=2048, record_bytes=512)

            # Real proc/cgroup collection and a real command, with only the
            # writer's cap reduced through its API to make this test fast.
            with patch.object(monitor, "SampleWriter", side_effect=small_writer):
                with patch.object(monitor, "console_line"):
                    code = monitor.main(["--output-dir", tmp, "--label", "build", "--interval", "0.001",
                                         "--", sys.executable, "-c", "import time; time.sleep(0.3); raise SystemExit(37)"])
            self.assertEqual(code, 37)
            summary = json.loads((Path(tmp) / "summary.json").read_text())
            self.assertTrue(summary["samples_capped"])
            self.assertGreater(summary["samples_dropped"], 0)
            self.assertEqual(summary["child_returncode"], 37)
            self.assertEqual(summary["end_sample"]["proc"]["meminfo"]["status"], "ok")
            data = (Path(tmp) / "samples.jsonl").read_bytes()
            self.assertLessEqual(len(data), 2048)
            self.assertEqual(json.loads(data.splitlines()[-1])["phase"], "end")

    def test_forwards_signals_to_group_and_bounds_stubborn_cleanup(self):
        for sig, stubborn in ((signal.SIGTERM, False), (signal.SIGINT, False),
                              (signal.SIGTERM, True)):
            with self.subTest(signal=sig, stubborn=stubborn), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                code = """
import os, pathlib, signal, sys, time
root = pathlib.Path(sys.argv[1])
def handler(sig, frame):
    (root / ('signal-' + str(os.getpid()))).write_text(str(sig))
    if sys.argv[2] != 'stubborn':
        if globals().get('pid'):
            os.waitpid(pid, 0)
        os._exit(43)
signal.signal(signal.SIGTERM, handler)
signal.signal(signal.SIGINT, handler)
pid = os.fork()
(root / ('leader' if pid else 'descendant')).write_text(str(os.getpid()))
while True:
    time.sleep(0.05)
"""
                process = subprocess.Popen(
                    [sys.executable, str(SCRIPT), "--output-dir", str(root / "out"),
                     "--label", "build", "--interval", "0.05", "--",
                     sys.executable, "-c", code, tmp, "stubborn" if stubborn else "normal"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                pids = []
                try:
                    deadline = time.monotonic() + 5
                    while not all((root / name).exists() for name in ("leader", "descendant")):
                        if process.poll() is not None or time.monotonic() >= deadline:
                            self.fail("child group did not become ready")
                        time.sleep(0.01)
                    pids = [int((root / name).read_text()) for name in ("leader", "descendant")]
                    before = time.monotonic()
                    process.send_signal(sig)
                    _, errors = process.communicate(timeout=8)
                    self.assertLess(time.monotonic() - before, 7)
                    self.assertEqual(process.returncode, 137 if stubborn else 43, errors)
                    for pid in pids:
                        self.assertEqual((root / f"signal-{pid}").read_text(), str(sig))
                        status = Path(f"/proc/{pid}/stat")
                        self.assertTrue(not status.exists() or status.read_text().split()[2] == "Z",
                                        f"process {pid} remains running")
                    summary = json.loads((root / "out/summary.json").read_text())
                    self.assertEqual(summary["received_signal"], sig)
                    self.assertEqual(summary["child_returncode"], -signal.SIGKILL if stubborn else 43)
                    self.assertEqual(summary["termination_escalated"], stubborn)
                finally:
                    for name in ("leader", "descendant"):
                        if (root / name).exists():
                            try:
                                os.kill(int((root / name).read_text()), signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                    if process.poll() is None:
                        process.kill()
                    process.communicate(timeout=5)

    def test_cancellation_cannot_succeed_when_leader_exits_zero_and_descendant_ignores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = """
import os, pathlib, signal, sys, time
root = pathlib.Path(sys.argv[1])
signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))
pid = os.fork()
if pid == 0:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    (root / 'descendant').write_text(str(os.getpid()))
else:
    while not (root / 'descendant').exists():
        time.sleep(0.01)
    (root / 'ready').touch()
while True:
    time.sleep(0.05)
"""
            process = subprocess.Popen(
                [sys.executable, str(SCRIPT), "--output-dir", str(root / "out"), "--label", "build", "--",
                 sys.executable, "-c", code, tmp], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 5
                while not (root / "ready").exists():
                    if process.poll() is not None or time.monotonic() >= deadline:
                        self.fail("child not ready")
                    time.sleep(0.01)
                process.terminate()
                _, errors = process.communicate(timeout=8)
                self.assertEqual(process.returncode, 143, errors)
                summary = json.loads((root / "out/summary.json").read_text())
                self.assertEqual(summary["child_returncode"], 0)
                self.assertTrue(summary["termination_escalated"])
                pid = int((root / "descendant").read_text())
                status = Path(f"/proc/{pid}/stat")
                self.assertTrue(not status.exists() or status.read_text().split()[2] == "Z")
            finally:
                if (root / "descendant").exists():
                    try:
                        os.kill(int((root / "descendant").read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)

    def test_child_signal_death_is_reported_without_masking(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output-dir", tmp, "--label", "build", "--",
                 sys.executable, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 143, result.stderr)
            summary = json.loads((Path(tmp) / "summary.json").read_text())
            self.assertEqual(summary["child_returncode"], -signal.SIGTERM)
            self.assertEqual(summary["exit_status"], 143)

    def test_collection_failure_is_visible_but_child_failure_is_preserved(self):
        monitor = load_monitor()
        with tempfile.TemporaryDirectory() as tmp:
            errors = io.StringIO()
            with patch.object(monitor, "collect_snapshot", side_effect=PermissionError(13, "private details")):
                with patch.object(monitor.os, 'write', side_effect=lambda fd, data: errors.write(data.decode())):
                    code = monitor.main(["--output-dir", tmp, "--label", "build", "--",
                                         sys.executable, "-c", "raise SystemExit(37)"])
            self.assertEqual(code, 37)
            self.assertIn("warning", errors.getvalue())
            self.assertNotIn("private details", errors.getvalue())
            summary = json.loads((Path(tmp) / "summary.json").read_text())
            self.assertEqual(summary["end_sample"]["status"], "collection-failed")
            self.assertEqual(summary["child_returncode"], 37)

    def test_launch_failure_has_separate_summary_without_command_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "secret-executable-that-does-not-exist")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output-dir", tmp, "--label", "build", "--", missing],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 127, result.stderr)
            self.assertNotIn(missing, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            summary = json.loads((Path(tmp) / "summary.json").read_text())
            self.assertIsNone(summary["child_returncode"])
            self.assertEqual(summary["launch_errno"], 2)
            self.assertEqual(summary["exit_status"], 127)
            self.assertEqual(summary["end_sample"]["phase"], "end")

    def test_invalid_intervals_do_not_execute_command(self):
        for interval in ("0", "-1", "nan", "inf"):
            with self.subTest(interval=interval), tempfile.TemporaryDirectory() as tmp:
                marker = Path(tmp) / "executed"
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--output-dir", tmp, "--label", "build",
                     "--interval", interval, "--", sys.executable, "-c",
                     f"from pathlib import Path; Path({str(marker)!r}).touch()"],
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(marker.exists())

    def test_command_output_and_exact_exit_status(self):
        for code in (0, 37):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "diagnostics"
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--output-dir", str(output),
                     "--label", "build", "--", sys.executable, "-c",
                     f"import sys; print('live output'); print('live error', file=sys.stderr); sys.exit({code})",
                     "private-argument-token"],
                    env=dict(os.environ, MONITOR_TEST_SECRET="private-environment-token"),
                    text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertIn("live output", result.stdout)
                self.assertIn("live error", result.stderr)
                summary = json.loads((output / "summary.json").read_text())
                self.assertEqual(summary["child_returncode"], code)
                self.assertEqual(summary["exit_status"], code)
                self.assertGreaterEqual(summary["duration_seconds"], 0)
                self.assertEqual(summary["scope"], "container-visible")
                samples = [json.loads(line) for line in (output / "samples.jsonl").read_text().splitlines()]
                self.assertEqual([s["phase"] for s in samples], ["start", "end"])
                self.assertNotIn("live output", json.dumps(summary))
                for path in (output / "summary.json", output / "samples.jsonl"):
                    self.assertNotIn("private-argument-token", path.read_text())
                    self.assertNotIn("private-environment-token", path.read_text())


if __name__ == "__main__":
    unittest.main()
