#!/usr/bin/env python3
"""Read-only host prerequisites; never mounts or configures shared storage."""
import json
import os
import sys
import shutil
import subprocess


def check_command(argv, timeout=3, expected_stdout=None):
    """Emit no child output or exception text; optionally compare fixed stdout."""
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL,
                                stdout=(subprocess.PIPE if expected_stdout is not None
                                        else subprocess.DEVNULL),
                                stderr=subprocess.DEVNULL,
                                timeout=timeout, check=False,
                                env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin',
                                     'LC_ALL': 'C'})
    except subprocess.TimeoutExpired:
        return 'timeout'
    except FileNotFoundError:
        return 'unavailable'
    except OSError:
        return 'unknown'
    if expected_stdout is not None and result.stdout != expected_stdout:
        return 'failed'
    return 'passed' if result.returncode == 0 else 'failed'


def collect(timeout=3):
    """Fixed inventory only. Success of sudo true is NOT mount authorization."""
    tools = {name: shutil.which(name, path='/usr/sbin:/usr/bin:/sbin:/bin') for name in
             ('mount', 'mount.nfs', 'dpkg-query', 'docker', 'sudo')}
    package = (check_command([tools['dpkg-query'], '-W',
                             '-f=${db:Status-Status}', 'nfs-common'],
                            timeout=timeout, expected_stdout=b'installed')
               if tools['dpkg-query'] else 'unavailable')
    return {
        'schema_version': 1,
        'uid': os.getuid(),
        'euid': os.geteuid(),
        'mount_binary_available': tools['mount'] is not None,
        'mount_nfs_binary_available': tools['mount.nfs'] is not None,
        'nfs_common_package': {'passed': 'installed', 'failed': 'not_confirmed'}.get(
            package, package),
        # CLI only: never reads Docker configuration or contacts a daemon.
        # Allow slow CLI startup without extending sudo/package checks (3s each).
        'docker_cli': (check_command([tools['docker'], '--version'], timeout=15)
                       if tools['docker'] else 'unavailable'),
        'sudo_noninteractive_true': (
            check_command([tools['sudo'], '-n', 'true'], timeout=timeout)
            if tools['sudo'] else 'unavailable'),
        'mount_authorization': 'unknown',
        'mount_success': 'unknown',
        'network_access': 'unknown',
        'shared_storage_support': 'unknown',
        'docker_daemon_access': 'unknown',
    }


def main():
    # No caller-selected command, endpoint, output path, or echoed arguments.
    if len(sys.argv) != 1:
        return 2
    print(json.dumps(collect(), sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
