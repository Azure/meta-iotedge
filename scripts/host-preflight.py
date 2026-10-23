#!/usr/bin/env python3
"""Read-only, allowlisted observations; unknown is never zero or unlimited."""
import errno
import json
import os
from pathlib import Path
import re
import stat
import sys


def read_text(path, limit=16384):
    """No final symlink/device/FIFO reads; procfs regular files have size zero."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return None, 'unsafe'
            data = stream.read(limit + 1)
        if len(data) > limit:
            return None, 'too_large'
        return data.decode('ascii'), 'ok'
    except FileNotFoundError:
        return None, 'missing'
    except PermissionError:
        return None, 'denied'
    except UnicodeError:
        return None, 'invalid'
    except OSError as error:
        return None, 'unsafe' if error.errno == errno.ELOOP else 'unreadable'


def unknown() -> dict:
    return {'status': 'unknown'}


def mount_records(text):
    """Internal-only paths; sources/options never leave this parser."""
    records = []
    if text is None or len(text) > 1048576 or len(text.splitlines()) > 4096:
        return records
    for line in text.splitlines():
        before, sep, after = line.partition(' - ')
        left, right = before.split(), after.split()
        if not sep or len(left) < 6 or len(right) < 3:
            return []
        root, target = [re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)
                        for value in left[3:5]]
        if any(not p.startswith('/') or '..' in p.split('/') for p in (root, target)):
            return []
        records.append((root, target, right[0]))
    return records


def cache_filesystem(text):
    target = '/var/cache/yocto'
    candidates = [row for row in mount_records(text)
                  if target == row[1] or target.startswith(row[1].rstrip('/') + '/')]
    if not candidates:
        return unknown()
    _, mountpoint, filesystem = max(candidates, key=lambda row: len(row[1]))
    allowed = {'nfs', 'nfs4', 'cifs', 'ext4', 'xfs', 'overlay', 'tmpfs', 'btrfs'}
    return {'status': 'ok', 'covering_filesystem': filesystem if filesystem in allowed else 'other',
            'exact_mountpoint': mountpoint == target,
            'shared_filesystem_type': filesystem in {'nfs', 'nfs4', 'cifs'}}


def scalar(path, unlimited=False):
    text, status = read_text(path, 128)
    if text is None:
        return {'status': 'unknown', 'reason': status}
    value = text.strip()
    if unlimited and value == 'max':
        return {'status': 'unlimited'}
    if re.fullmatch(r'[0-9]{1,24}', value):
        return {'status': 'ok', 'value': int(value)}
    return unknown()


def counters(path, keys):
    text, status = read_text(path)
    result: dict = {key: {'status': 'unknown', 'reason': status if text is None else 'invalid_or_missing'}
              for key in keys}
    for line in (text or '').splitlines():
        match = re.fullmatch(r'(\w+) ([0-9]{1,24})', line)
        if match and match[1] in result:
            result[match[1]] = {'status': 'ok', 'value': int(match[2])}
    return result


def cpu_limit(path):
    text, status = read_text(path, 128)
    match = re.fullmatch(r'(max|[0-9]{1,24}) ([0-9]{1,24})\s*', text or '')
    if status != 'ok' or not match or int(match[2]) == 0:
        return unknown()
    return {'status': 'unlimited' if match[1] == 'max' else 'ok',
            'quota_usec': None if match[1] == 'max' else int(match[1]),
            'period_usec': int(match[2])}


def cgroup_memory(proc, cgroot, mounts, membership_file=None):
    result = {'status': 'unknown', 'version': 'unknown',
              'host_ancestor_coverage': 'UNVERIFIED'}
    membership, status = read_text(membership_file or proc / 'self/cgroup')
    if membership is None:
        return dict(result, reason=status)
    unified = [line[3:] for line in membership.splitlines() if line.startswith('0::')]
    if not unified:
        if any(re.fullmatch(r'[0-9]+:[^:]*\bmemory\b[^:]*:/.*', line)
               for line in membership.splitlines()):
            return dict(result, version='v1', reason='v1_not_collected')
        return dict(result, reason='membership_unrecognized')
    if len(unified) != 1:
        return dict(result, reason='ambiguous_membership')
    result['version'] = 'v2'
    membership = unified[0]
    parts = membership.split('/')[1:]
    if (not re.fullmatch(r'/[A-Za-z0-9_./:@-]*', membership)
            or any(p in {'.', '..', ''} for p in parts if membership != '/')):
        return dict(result, reason='unsafe_membership')
    cgmounts = [row for row in mount_records(mounts) if row[2] == 'cgroup2']
    # Fail closed on unusual mount-root/namespace mappings instead of guessing.
    if cgmounts != [('/', '/sys/fs/cgroup', 'cgroup2')]:
        return dict(result, reason='unsupported_mount_mapping')
    if len(parts) > 15:
        return dict(result, reason='ancestor_bound')
    directory = cgroot.joinpath(*parts)
    ancestors = []
    while True:
        entry = {name: scalar(directory / name, unlimited=name.endswith(('.max', '.high')))
                 for name in ('memory.current', 'memory.peak', 'memory.max', 'memory.high',
                              'memory.swap.current', 'memory.swap.max')}
        entry['memory.events'] = counters(directory / 'memory.events', ('low', 'high', 'max', 'oom', 'oom_kill'))
        entry['memory.stat'] = counters(directory / 'memory.stat',
                                        ('anon', 'file', 'shmem', 'inactive_file', 'slab_reclaimable'))
        entry['cpu.max'] = cpu_limit(directory / 'cpu.max')
        entry['cpu.stat'] = counters(directory / 'cpu.stat',
                                     ('usage_usec', 'nr_periods', 'nr_throttled', 'throttled_usec'))
        ancestors.append(entry)
        if directory == cgroot:
            break
        directory = directory.parent
    return dict(result, status='partial', visible_ancestors_including_self=ancestors)


def service_budgets(proc, cgroot, mounts):
    services = {name: [] for name in ('Runner.Listener', 'Runner.Worker', 'dockerd')}
    incomplete = False
    try:
        for index, directory in enumerate(proc.iterdir()):
            if index >= 4096:
                incomplete = True
                break
            if not re.fullmatch(r'[0-9]{1,10}', directory.name):
                continue
            name, status = read_text(directory / 'comm', 64)
            if status != 'ok' or name is None:
                incomplete = True
                continue
            name = name.strip()
            if name in services and len(services[name]) < 4:
                services[name].append(cgroup_memory(proc, cgroot, mounts, directory / 'cgroup'))
    except OSError:
        incomplete = True
    return {'status': 'partial' if any(services.values()) else 'unknown',
            'process_scan_incomplete': incomplete, 'services': services}


def pressure(path):
    text, status = read_text(path, 2048)
    result = {key: unknown() for key in ('some', 'full')}
    if text is None:
        return {key: {'status': 'unknown', 'reason': status} for key in result}
    for line in text.splitlines():
        match = re.fullmatch(r'(some|full) avg10=([0-9]{1,3}\.[0-9]{2}) '
                             r'avg60=([0-9]{1,3}\.[0-9]{2}) avg300=([0-9]{1,3}\.[0-9]{2}) '
                             r'total=([0-9]{1,24})', line)
        if match:
            result[match[1]] = {'status': 'ok', 'avg10': float(match[2]),
                                'avg60': float(match[3]), 'avg300': float(match[4]),
                                'total_usec': int(match[5])}
    return result


def binary_present(name):
    # Do not execute helpers or honor an injected PATH.
    return any(os.access(Path(directory) / name, os.X_OK)
               and (Path(directory) / name).is_file()
               for directory in ('/usr/bin', '/bin', '/usr/sbin', '/sbin'))


def prerequisites(proc):
    filesystems, status = read_text(proc / 'filesystems')
    kernel = {'status': 'unknown', 'reason': status}
    if filesystems is not None:
        kernel = {'status': 'ok', 'present': any(line.split() in [['nfs'], ['nfs4'],
                   ['nodev', 'nfs'], ['nodev', 'nfs4']] for line in filesystems.splitlines())}
    return {'mount_privilege': 'UNVERIFIED', 'sudo_binary_present': binary_present('sudo'),
            'nfs_helper_present': binary_present('mount.nfs') or binary_present('mount.nfs4'),
            'docker_cli_present': binary_present('docker'), 'nfs_kernel_registered': kernel,
            'network_connectivity': 'UNVERIFIED', 'cache_write_and_locking': 'UNVERIFIED'}


def memory(proc):
    fields = ('MemTotal', 'MemAvailable', 'MemFree', 'SwapTotal', 'SwapFree')
    result = {key: unknown() for key in fields}
    text, status = read_text(proc / 'meminfo')
    if text is None:
        return {key: {'status': 'unknown', 'reason': status} for key in fields}
    for line in text.splitlines():
        match = re.fullmatch(r'(\w+):\s+([0-9]{1,24}) kB', line)
        if match and match[1] in result:
            result[match[1]] = {'status': 'ok', 'bytes': int(match[2]) * 1024}
    return result


def disk_capacity():
    for source, path in (('cache', '/var/cache/yocto'), ('cache_parent', '/var/cache'), ('root', '/')):
        try:
            value = os.statvfs(path)
            return {'status': 'ok', 'source': source,
                    'total_bytes': value.f_blocks * value.f_frsize,
                    'available_bytes': value.f_bavail * value.f_frsize,
                    'free_inodes': value.f_favail}
        except FileNotFoundError:
            continue
        except OSError:
            return unknown()
    return unknown()


def collect(proc=Path('/proc'), cgroot=Path('/sys/fs/cgroup')):
    """Root parameters are for imported offline tests, never CLI/workflow inputs."""
    mounts, status = read_text(proc / 'self/mountinfo', 1048576)
    cache = cache_filesystem(mounts)
    if mounts is None:
        cache = {'status': 'unknown', 'reason': status}
    return {
        'schema_version': 1,
        'execution_context': {'observation_scope': 'current_process_visible_procfs',
                              'host_job_declaration': 'external_workflow_only',
                              'idle_host': 'UNVERIFIED'},
        'user': {'effective_uid': os.geteuid(), 'effective_gid': os.getegid(),
                 'is_root': os.geteuid() == 0},
        'prerequisites': prerequisites(proc),
        'cache_path': {'target': '/var/cache/yocto', 'filesystem': cache,
                       'directory_exists': 'UNVERIFIED', 'shared_storage_ready': 'UNVERIFIED'},
        'memory': memory(proc),
        'memory_pressure': pressure(proc / 'pressure/memory'),
        'cpu_pressure': pressure(proc / 'pressure/cpu'),
        'io_pressure': pressure(proc / 'pressure/io'),
        'disk_capacity': disk_capacity(),
        'host_identity': {'hostname': os.uname().nodename},
        'self_cgroup': cgroup_memory(proc, cgroot, mounts),
        'service_budgets': service_budgets(proc, cgroot, mounts),
    }


def main(args):
    if args:
        print('unsupported arguments', file=sys.stderr)
        return 2
    print(json.dumps(collect(), sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
