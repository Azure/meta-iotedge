#!/usr/bin/env python3
"""Best-effort container-visible telemetry around one command; never retries it.

Not host-runner diagnostics: procfs values may have wider kernel scope than the
visible cgroup. Counters cannot establish the cause of a runner disconnect.
Telemetry reads are limited to 64 KiB each (mount discovery: 1 MiB); samples.jsonl
is limited to 8 MiB with end-record space reserved. Oversized records are visibly
replaced, not silently cut into invalid JSON. summary.json is always attempted
separately. SIGKILL, container/host loss, disk failure, and processes that escape
the child's process group can prevent final diagnostics or complete cleanup.
"""
import argparse
import errno
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import time
from typing import Any, Dict

READ_LIMIT = 64 * 1024
CGROUP_FILES = ("memory.current", "memory.peak", "memory.max", "memory.events",
                "cpu.stat", "cpu.pressure", "memory.pressure", "io.pressure", "io.stat")
PROC_FILES = ("meminfo", "loadavg", "pressure/cpu", "pressure/memory", "pressure/io")


def read_bounded(path, limit=READ_LIMIT):
    """Only allowlisted callers supply paths; never walk directories or read env/cmdline."""
    try:
        with Path(path).open("rb") as source:
            data = source.read(limit + 1)
        return {"status": "truncated" if len(data) > limit else "ok",
                "text": data[:limit].decode("utf-8", errors="replace")}
    except OSError as error:
        status = {errno.ENOENT: "absent", errno.EACCES: "permission-denied",
                  errno.EPERM: "permission-denied", errno.ENOTSUP: "unsupported",
                  errno.ENOSYS: "unsupported"}.get(error.errno or 0, "unavailable")
        return {"status": status, "errno": error.errno}


def unescape_mount(value):
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value)


def discover_cgroup(proc_root=Path("/proc")) -> Dict[str, Any]:
    """Resolve unified membership against mount roots, not a hardcoded mountpoint."""
    proc_root = Path(proc_root)
    membership = read_bounded(proc_root / "self/cgroup")
    # Many unrelated bind mounts can precede the cgroup mount in containers.
    # Bound discovery separately; none of the raw mount table enters artifacts.
    mounts = read_bounded(proc_root / "self/mountinfo", limit=1024 * 1024)
    metadata = {"membership_status": membership["status"],
                "mountinfo_status": mounts["status"]}
    if membership["status"] != "ok" or mounts["status"] != "ok":
        return dict(metadata, status="unavailable")
    current = next((line[3:] for line in membership["text"].splitlines()
                    if line.startswith("0::")), None)
    if current is None:
        return dict(metadata, status="unsupported", reason="no-unified-cgroup-v2")
    candidates = []
    for line in mounts["text"].splitlines():
        before, separator, after = line.partition(" - ")
        fields = before.split()
        if not separator or not after.startswith("cgroup2 ") or len(fields) < 5:
            continue
        mount_root = PurePosixPath(unescape_mount(fields[3]))
        mountpoint = Path(unescape_mount(fields[4]))
        if not mount_root.is_absolute() or not mountpoint.is_absolute():
            continue
        path = PurePosixPath(current)
        if path.is_absolute() and ".." not in path.parts:
            try:
                relative = path.relative_to(mount_root)
            except ValueError:
                visible = mountpoint.joinpath(*path.parts[1:])
                if current != "/" and ((visible / "cgroup.controllers").exists()
                                       or (visible / "memory.current").exists()):
                    candidates.append((0, visible, "namespace-relative-fallback"))
            else:
                candidates.append((len(mount_root.parts), mountpoint / str(relative),
                                   "mount-root-relative"))
        # A cgroup namespace may report / (or inaccessible ../ ancestors) while
        # mountinfo still names the host-side subtree. Only use a visible root
        # with a cgroup marker; never follow .. outside the discovered mount.
        if current == "/" or ".." in path.parts:
            if (mountpoint / "cgroup.controllers").exists() or (mountpoint / "memory.current").exists():
                candidates.append((-1, mountpoint, "namespace-root-fallback"))
    for _, path, mapping in sorted(candidates, key=lambda entry: entry[0], reverse=True):
        if path.is_dir():
            return dict(metadata, status="ok", path=str(path), mapping=mapping)
    return dict(metadata, status="unavailable", reason="current-cgroup-not-visible")


def collect_disks(container_root=Path("/"), workspace=Path("."),
                  cache=Path("/workspaces/yocto-cache")):
    """Read only three selected paths; never disclose paths or device identifiers.

    Container root is not host root. Same-device is a comparison, not proof of
    host bind-source placement, cache durability, or a dedicated filesystem.
    """
    disks = {}
    devices = {}
    for name, path in (("container_root", container_root), ("workspace", workspace),
                       ("cache", cache)):
        try:
            metadata = os.stat(path)
            space = os.statvfs(path)
            disks[name] = {"status": "ok", "uid": metadata.st_uid,
                           "gid": metadata.st_gid, "mode": metadata.st_mode,
                           "bytes_total": space.f_blocks * space.f_frsize,
                           "bytes_free": space.f_bfree * space.f_frsize,
                           "bytes_available": space.f_bavail * space.f_frsize,
                           "inodes_total": space.f_files, "inodes_free": space.f_ffree,
                           "inodes_available": space.f_favail}
            devices[name] = metadata.st_dev
        except OSError as error:
            disks[name] = {"status": "unknown", "errno": error.errno}
    disks["workspace_cache_same_device"] = (
        devices["workspace"] == devices["cache"]
        if "workspace" in devices and "cache" in devices else None)
    return disks


def collect_snapshot(proc_root=Path("/proc"), read_limit=READ_LIMIT) -> Dict[str, Any]:
    proc_root = Path(proc_root)
    cgroup = discover_cgroup(proc_root)
    cgroup["files"] = {
        name: read_bounded(Path(cgroup["path"]) / name, read_limit)
        if cgroup["status"] == "ok" else {"status": "unavailable"}
        for name in CGROUP_FILES}
    return {"scope": "container-visible", "proc": {
        name: read_bounded(proc_root / name, read_limit) for name in PROC_FILES},
        "cgroup": cgroup, "disks": collect_disks()}


def console_line(fd, message):
    """No buffering: failed diagnostic flushes must not change exit status to 120."""
    try:
        os.write(fd, (message + "\n").encode("utf-8"))
    except OSError:
        pass


def warn(message):
    # Do not include command arguments, environment, or arbitrary exception text.
    console_line(2, "resource-monitor warning: " + message)


class SampleWriter:
    """Bound JSONL size, reserving a record for end; summary is independent."""
    def __init__(self, output_dir, max_bytes=8 * 1024 * 1024, record_bytes=512 * 1024):
        self.max_bytes = max_bytes
        self.record_bytes = min(record_bytes, max_bytes // 2)
        self.bytes_written = self.written = self.dropped = 0
        self.capped = self.failed = False
        self.stream = None
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            self.stream = (Path(output_dir) / "samples.jsonl").open("wb", buffering=0)
        except OSError as error:
            self.fail(error)

    def fail(self, error):
        if not self.failed:
            warn("diagnostics write failed (errno=%s); command will continue" % error.errno)
        self.failed = True

    def write(self, snapshot, final=False):
        if self.failed or self.stream is None:
            return
        data = (json.dumps(snapshot, separators=(",", ":")) + "\n").encode("utf-8")
        if len(data) > self.record_bytes:
            snapshot = {key: snapshot[key] for key in ("phase", "scope", "elapsed_seconds")
                        if key in snapshot}
            snapshot["status"] = "telemetry-record-too-large"
            data = (json.dumps(snapshot) + "\n").encode("utf-8")
        limit = self.max_bytes if final else self.max_bytes - self.record_bytes
        if self.bytes_written + len(data) > limit:
            if not self.capped:
                warn("sample byte cap reached; periodic samples will be dropped")
            self.capped = True
            self.dropped += 1
            return
        try:
            # Unbuffered writes may be short. Stop on failure; never retry a build.
            view = memoryview(data)
            while view:
                written = self.stream.write(view)
                if not written:
                    raise OSError(errno.EIO, "short diagnostics write")
                self.bytes_written += written
                view = view[written:]
            self.written += 1
        except OSError as error:
            self.fail(error)

    def close(self):
        if self.stream is not None:
            try:
                self.stream.close()
            except OSError as error:
                self.fail(error)


def run_command(command, interval, periodic):
    """Forward cancellation to a new process group; escalate after two seconds."""
    child = None
    received = None
    deadline = 0.0
    escalated = False

    def send(signum):
        if child is not None:
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass
            except PermissionError:
                warn("cannot signal child process group: permission denied")

    def on_signal(signum, frame):
        nonlocal received, deadline
        if received is None:
            received = signum
            deadline = time.monotonic() + 2.0
        send(signum)

    previous = {sig: signal.signal(sig, on_signal) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        # stdout/stderr are inherited deliberately: build logs stay live.
        try:
            child = subprocess.Popen(command, start_new_session=True)
        except OSError as error:
            warn("command could not be launched (errno=%s)" % error.errno)
            return None, received, False, error.errno
        if received is not None:
            send(received)
        next_sample = time.monotonic() + interval
        while True:
            code = child.poll()
            if received is None:
                if code is not None:
                    break
            else:
                try:
                    os.killpg(child.pid, 0)
                except ProcessLookupError:
                    break
                if time.monotonic() >= deadline:
                    send(signal.SIGKILL)
                    escalated = True
                    break
            now = time.monotonic()
            if now >= next_sample:
                periodic()
                next_sample = time.monotonic() + interval
            time.sleep(min(0.05, max(0, next_sample - time.monotonic())))
        code = child.wait()
        return code, received, escalated, None
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--interval", type=float, default=15)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("--interval must be finite and greater than zero")
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("a command is required after --")
    output = Path(args.output_dir)
    started = time.monotonic()
    collection_warned = False
    last_disk_console = 0.0

    def sample(phase):
        nonlocal collection_warned, last_disk_console
        snapshot: Dict[str, Any]
        try:
            snapshot = collect_snapshot()
        except Exception as error:
            if not collection_warned:
                warn("telemetry collection failed (%s); command will continue" % type(error).__name__)
                collection_warned = True
            snapshot = {"scope": "container-visible", "status": "collection-failed",
                        "error_type": type(error).__name__}
        snapshot.update(phase=phase, elapsed_seconds=time.monotonic() - started)
        if phase != "periodic" or snapshot["elapsed_seconds"] - last_disk_console >= 60:
            last_disk_console = snapshot["elapsed_seconds"]
            # Compact allowlisted values also survive when artifact writes fail.
            disks = snapshot.get("disks", {})
            compact: Dict[str, Any] = {name: {key: value for key, value in disks.get(name, {"status": "unknown"}).items()
                              if key in ("status", "errno", "bytes_available", "inodes_available")}
                       for name in ("container_root", "workspace", "cache")}
            compact["workspace_cache_same_device"] = disks.get("workspace_cache_same_device")
            console_line(1, "resource-monitor disk: " + json.dumps({
                "phase": phase, "scope": "container-visible",
                "elapsed_seconds": round(snapshot["elapsed_seconds"], 3),
                "disks": compact}, separators=(",", ":")))
        return snapshot

    writer = SampleWriter(output)
    writer.write(sample("start"))
    code, received, escalated, launch_errno = run_command(
        command, args.interval, lambda: writer.write(sample("periodic")))
    if code is None:
        exit_status = 127 if launch_errno == errno.ENOENT else 126
    else:
        exit_status = code if code >= 0 else 128 - code
        if received is not None and code == 0:
            exit_status = 128 + received
    end_sample = sample("end")
    writer.write(end_sample, final=True)
    writer.close()
    summary = {"label": args.label, "scope": "container-visible",
               "child_returncode": code, "exit_status": exit_status,
               "launch_errno": launch_errno,
               "received_signal": received, "termination_escalated": escalated,
               "samples_written": writer.written, "end_sample": end_sample,
               "samples_capped": writer.capped, "samples_dropped": writer.dropped,
               "diagnostics_write_failed": writer.failed,
               "duration_seconds": time.monotonic() - started}
    try:
        (output / "summary.json").write_text(json.dumps(summary) + "\n")
    except OSError as error:
        warn("summary unavailable (errno=%s); preserving command status" % error.errno)
    return exit_status


if __name__ == "__main__":
    raise SystemExit(main())
