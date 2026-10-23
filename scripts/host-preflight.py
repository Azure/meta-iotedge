#!/usr/bin/env python3
"""Read-only, allowlisted observations; unknown is never zero or unlimited."""
import contextlib
import errno
import json
import os
from pathlib import Path
import re
import stat
import sys


def read_text(path, limit=16384, dir_fd=None):
    """No final symlink/device/FIFO reads; procfs regular files have size zero."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
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


def safe_absolute_path(value):
    return (isinstance(value, str) and 0 < len(value) <= 4096
            and value.startswith('/') and not any(ord(c) < 32 or ord(c) == 127 for c in value)
            and (value == '/' or all(p not in {'', '.', '..'} for p in value.split('/')[1:])))


def mount_records(text, diagnostics=None):
    """Internal-only paths; one unrelated bad row must not erase valid mappings."""
    diagnostics = diagnostics if diagnostics is not None else {}
    diagnostics.update(status='unknown', reason='missing', valid_row_count=None, invalid_row_count=None)
    records = []
    if text is None:
        return records
    if len(text) > 1048576 or len(text.splitlines()) > 4096:
        diagnostics['reason'] = 'table_bound'
        return records
    invalid = valid = 0
    for line in text.splitlines():
        before, sep, after = line.partition(' - ')
        left, right = before.split(), after.split()
        root, target = (None, None)
        if len(left) >= 5:
            root, target = [re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)
                            for value in left[3:5]]
        if (not sep or len(left) < 6 or len(right) < 3
                or not all(safe_absolute_path(p) for p in (root, target))):
            invalid += 1
            # A known target with an invalid root/row must block covering reads,
            # not silently expose an apparently safe less-specific filesystem.
            if safe_absolute_path(target):
                records.append((None, target, None))
            continue
        records.append((root, target, right[0]))
        valid += 1
    diagnostics.update(status=('partial' if invalid else 'ok') if valid else 'unknown',
                       reason='invalid_rows_skipped' if invalid else 'parsed',
                       valid_row_count=valid, invalid_row_count=invalid)
    return records


def covering_mount(records, target):
    candidates = [row for row in records
                  if target == row[1] or target.startswith(row[1].rstrip('/') + '/')]
    if not candidates:
        return None
    longest = max(len(row[1]) for row in candidates)
    selected = [row for row in candidates if len(row[1]) == longest]
    return selected[0] if len(selected) == 1 and selected[0][2] is not None else None


def cache_filesystem(text):
    target = '/var/cache/yocto'
    selected = covering_mount(mount_records(text), target)
    if selected is None:
        return unknown()
    _, mountpoint, filesystem = selected
    allowed = {'nfs', 'nfs4', 'cifs', 'ext4', 'xfs', 'overlay', 'tmpfs', 'btrfs'}
    return {'status': 'ok', 'covering_filesystem': filesystem if filesystem in allowed else 'other',
            'exact_mountpoint': mountpoint == target,
            'shared_filesystem_type': filesystem in {'nfs', 'nfs4', 'cifs'}}


def scalar(path, unlimited=False, dir_fd=None):
    text, status = read_text(path, 128, dir_fd=dir_fd)
    if text is None:
        return {'status': 'unknown', 'reason': status}
    value = text.strip()
    if unlimited and value == 'max':
        return {'status': 'unlimited'}
    if re.fullmatch(r'[0-9]{1,24}', value):
        return {'status': 'ok', 'value': int(value)}
    return unknown()


def counters(path, keys, dir_fd=None):
    text, status = read_text(path, dir_fd=dir_fd)
    result: dict = {key: {'status': 'unknown', 'reason': status if text is None else 'invalid_or_missing'}
              for key in keys}
    for line in (text or '').splitlines():
        match = re.fullmatch(r'(\w+) ([0-9]{1,24})', line)
        if match and match[1] in result:
            result[match[1]] = {'status': 'ok', 'value': int(match[2])}
    return result


def cpu_limit(path, dir_fd=None):
    text, status = read_text(path, 128, dir_fd=dir_fd)
    match = re.fullmatch(r'(max|[0-9]{1,24}) ([0-9]{1,24})\s*', text or '')
    if status != 'ok' or not match or int(match[2]) == 0:
        return unknown()
    return {'status': 'unlimited' if match[1] == 'max' else 'ok',
            'quota_usec': None if match[1] == 'max' else int(match[1]),
            'period_usec': int(match[2])}


def cgroup_memory(proc, cgroot, mounts, membership_file=None):
    result: dict = {'status': 'unknown', 'version': 'unknown',
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
    mount_diagnostics = {}
    records = mount_records(mounts, mount_diagnostics)
    cgmounts = [row for row in records if row[2] == 'cgroup2']
    matches = [row for row in cgmounts
               if (row[1] == '/sys/fs/cgroup' or row[1].startswith('/sys/fs/cgroup/'))
               and (row[0] == '/' or membership == row[0] or membership.startswith(row[0] + '/'))]
    mapping = {'candidate_count': len(cgmounts), 'matching_candidate_count': len(matches),
               'reason': 'membership_not_covered', 'root_is_global': None,
               'mountpoint_category': 'unknown'}
    result['mapping'] = mapping
    if mount_diagnostics['valid_row_count'] is None:
        mapping.update(candidate_count=None, matching_candidate_count=None, reason='mount_table_unavailable')
        return dict(result, reason='unsupported_mount_mapping')
    if len(matches) != 1:
        mapping['reason'] = 'ambiguous_candidates' if matches else 'membership_not_covered'
        return dict(result, reason='unsupported_mount_mapping')
    mountroot, mountpoint, _ = matches[0]
    mapping.update(root_is_global=mountroot == '/',
                   mountpoint_category='cgroup_root' if mountpoint == '/sys/fs/cgroup'
                   else 'under_cgroup_root')
    relative = membership[len(mountroot):].lstrip('/') if mountroot != '/' else membership.lstrip('/')
    parts = relative.split('/') if relative else []
    mountparts = mountpoint.split('/')[4:]
    visible_path = mountpoint + ('/' + relative if relative else '')
    if (covering_mount(records, mountpoint) != matches[0]
            or any(target != mountpoint and target.startswith(mountpoint + '/')
                   and (visible_path == target or visible_path.startswith(target + '/'))
                   for _, target, _ in records)):
        mapping['reason'] = 'shadowed_mount'
        return dict(result, reason='unsupported_mount_mapping')
    if len(parts) > 15 or len(mountparts) > 15:
        mapping['reason'] = 'ancestor_bound'
        return dict(result, reason='ancestor_bound')
    mapping['reason'] = 'mapped'
    ancestors = []
    try:
        with contextlib.ExitStack() as opened:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
            fd = os.open(cgroot, flags)
            opened.callback(os.close, fd)
            descriptors = [fd]
            for part in mountparts + parts:
                fd = os.open(part, flags, dir_fd=fd)
                opened.callback(os.close, fd)
                descriptors.append(fd)
            # Only the selected mount and descendants; never its hidden parents.
            for fd in reversed(descriptors[len(mountparts):]):
                entry = {name: scalar(name, unlimited=name.endswith(('.max', '.high')), dir_fd=fd)
                         for name in ('memory.current', 'memory.peak', 'memory.max', 'memory.high',
                                      'memory.swap.current', 'memory.swap.max')}
                entry['memory.events'] = counters('memory.events', ('low', 'high', 'max', 'oom', 'oom_kill'), dir_fd=fd)
                entry['memory.stat'] = counters('memory.stat',
                                                ('anon', 'file', 'shmem', 'inactive_file', 'slab_reclaimable'), dir_fd=fd)
                entry['cpu.max'] = cpu_limit('cpu.max', dir_fd=fd)
                entry['cpu.stat'] = counters('cpu.stat',
                                             ('usage_usec', 'nr_periods', 'nr_throttled', 'throttled_usec'), dir_fd=fd)
                ancestors.append(entry)
    except OSError:
        mapping['reason'] = 'unsafe_or_unreadable_directory'
        return dict(result, reason='unsafe_or_unreadable_directory')
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


def local_capacity(path, mounts):
    """Stat only proven local directories; do not follow symlinks or remote mounts."""
    if not safe_absolute_path(path):
        return {'status': 'unknown', 'reason': 'unsafe_path'}
    parts = path.split('/')[1:] if path != '/' else []
    if len(parts) > 64:
        return {'status': 'unknown', 'reason': 'path_bound'}
    records = mount_records(mounts)
    prefixes = ['/'] + ['/' + '/'.join(parts[:index]) for index in range(1, len(parts) + 1)]
    selected = [covering_mount(records, prefix) for prefix in prefixes]
    if any(row is None or row[2] not in {'ext4', 'xfs', 'overlay', 'tmpfs', 'btrfs'} for row in selected):
        return {'status': 'unknown', 'reason': 'nonlocal_or_unknown_filesystem'}
    try:
        with contextlib.ExitStack() as opened:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
            fd = os.open('/', flags)
            opened.callback(os.close, fd)
            for part in parts:
                fd = os.open(part, flags, dir_fd=fd)
                opened.callback(os.close, fd)
            value = os.statvfs(fd)
        return {'status': 'ok', 'covering_filesystem': selected[-1][2] if selected[-1] is not None else 'other',
                'total_bytes': value.f_blocks * value.f_frsize,
                'available_bytes': value.f_bavail * value.f_frsize,
                'free_inodes': value.f_favail}
    except FileNotFoundError:
        return {'status': 'unknown', 'reason': 'missing'}
    except OSError:
        return {'status': 'unknown', 'reason': 'unsafe_or_unreadable_directory'}


def disk_capacity(mounts):
    locations = {source: local_capacity(path, mounts) for source, path in (
        ('cache', '/var/cache/yocto'), ('cache_parent', '/var/cache'), ('root', '/'), ('mnt', '/mnt'))}
    workspace = os.environ.get('GITHUB_WORKSPACE')
    if workspace is None:
        locations['workspace'] = {'status': 'unknown', 'reason': 'workspace_unset'}
    elif not safe_absolute_path(workspace):
        locations['workspace'] = {'status': 'unknown', 'reason': 'invalid_workspace'}
    else:
        locations['workspace'] = local_capacity(workspace, mounts)
    # Preserve the original cache/default fallback summary, not workspace capacity.
    for source in ('cache', 'cache_parent', 'root'):
        if locations[source]['status'] == 'ok':
            return dict(locations[source], source=source, locations=locations)
    return dict(unknown(), locations=locations)


def collect(proc=Path('/proc'), cgroot=Path('/sys/fs/cgroup')):
    """Root parameters are for imported offline tests, never CLI/workflow inputs."""
    mounts, status = read_text(proc / 'self/mountinfo', 1048576)
    mount_table = {}
    mount_records(mounts, mount_table)
    if mounts is None:
        mount_table['reason'] = status
    cache = cache_filesystem(mounts)
    if mounts is None:
        cache = {'status': 'unknown', 'reason': status}
    return {
        'schema_version': 1,
        'execution_context': {'observation_scope': 'current_process_visible_procfs',
                              'host_job_declaration': 'external_workflow_only',
                              'idle_host': 'UNVERIFIED', 'mount_table': mount_table},
        'user': {'effective_uid': os.geteuid(), 'effective_gid': os.getegid(),
                 'is_root': os.geteuid() == 0},
        'prerequisites': prerequisites(proc),
        'cache_path': {'target': '/var/cache/yocto', 'filesystem': cache,
                       'directory_exists': 'UNVERIFIED', 'shared_storage_ready': 'UNVERIFIED'},
        'memory': memory(proc),
        'memory_pressure': pressure(proc / 'pressure/memory'),
        'cpu_pressure': pressure(proc / 'pressure/cpu'),
        'io_pressure': pressure(proc / 'pressure/io'),
        'disk_capacity': disk_capacity(mounts),
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
