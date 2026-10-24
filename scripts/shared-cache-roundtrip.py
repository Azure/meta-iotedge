#!/usr/bin/env python3
"""Bounded official BuildXL action pilot. Never emit native logs or credentials."""
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import resource
import signal
import stat
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile

RUNTIME_CONFIG = Path('/buildcacheconfig.json')
METADATA_LIMIT = 1024 * 1024


def require(value):
    if not value:
        raise ValueError('pilot contract not satisfied')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def read_regular(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= limit)
        data = stream.read(limit + 1)
        require(len(data) <= limit)
        return data


def read_metadata(path=RUNTIME_CONFIG):
    return json.loads(read_regular(path, METADATA_LIMIT), object_pairs_hook=unique_object)


def exact_fields(obj, fields):
    require(type(obj) is dict and set(obj) == set(fields))


def validate_metadata(data):
    # Pinned native PascalCase hosted-pool array contract, not the developer API.
    require(type(data) is list and 0 < len(data) <= 16)
    for cache in data:
        exact_fields(cache, ('Name', 'RetentionDays', 'Shards'))
        require(type(cache['Name']) is str)
    selected = [cache for cache in data if cache['Name'] == 'yocto-sstate']
    require(len(selected) == 1)
    cache = selected[0]
    retention = cache['RetentionDays']
    require(retention is None or (type(retention) is int and retention > 0))
    shards = cache['Shards']
    require(type(shards) is list and 0 < len(shards) <= 4)
    targets = []
    accounts = set()
    for shard in shards:
        exact_fields(shard, ('StorageUrl', 'Containers'))
        url = shard['StorageUrl']
        require(type(url) is str and re.fullmatch(
            r'https://[a-z0-9]{3,24}\.(?:blob\.core\.windows\.net|'
            r'z[0-9]{2}\.blob\.storage\.azure\.net)/?', url))
        require(url.rstrip('/') not in accounts)
        accounts.add(url.rstrip('/'))
        containers = shard['Containers']
        require(type(containers) is list and len(containers) == 3)
        require({c.get('Type') for c in containers if type(c) is dict} ==
                {'Content', 'Metadata', 'Checkpoint'})
        names = set()
        for container in containers:
            exact_fields(container, ('Name', 'Type', 'Signature'))
            name = container['Name']
            require(type(name) is str and re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', name)
                    and '--' not in name and name not in names)
            names.add(name)
            signature = container['Signature']
            require(type(signature) is str and len(signature) <= 8192 and
                    not any(c in signature for c in '\r\n#') and
                    not signature.startswith(('http:', 'https:')))
            pairs = urllib.parse.parse_qsl(signature.lstrip('?'), keep_blank_values=True,
                                           strict_parsing=True, max_num_fields=32)
            query = unique_object(pairs)
            allowed = {'sv', 'sr', 'sp', 'st', 'se', 'sig', 'sip', 'spr', 'si',
                       'skoid', 'sktid', 'skt', 'ske', 'sks', 'skv', 'saoid', 'suoid', 'scid'}
            require(set(query) <= allowed and query.get('sr') == 'c' and
                    bool(query.get('sig')) and bool(query.get('sp')) and
                    'r' in query['sp'] and set(query['sp']) <= set('racwdxltmeop') and
                    all(query.values()))
            require(query.get('spr', 'https') == 'https')
            targets.append(url.rstrip('/') + '/' + name + '?' +
                           urllib.parse.urlencode(pairs + [('restype', 'container')]))
    return targets


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def private_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def check_containers(data, opener=None):
    targets = validate_metadata(data)  # Validate every target before any I/O.
    opener = opener or private_opener()
    for url in targets:
        with opener.open(urllib.request.Request(url, method='HEAD'), timeout=5) as response:
            require(response.status == 200)
    return len(targets)


PACKAGE_SHA = '1332d1b02d686328369fb75742fd5942f0eef84aa24aea73b358852715359456'
PACKAGE_URL = ('https://pkgs.dev.azure.com/mseng/c86767d8-af79-4303-a7e6-21da0ba435e2/'
               '_packaging/5a7f3a3c-0417-461d-aee8-d898cc4a0d4d/nuget/v3/flat2/'
               'microsoft.buildxl.linux-x64/0.1.0-20261016.6/'
               'microsoft.buildxl.linux-x64.0.1.0-20261016.6.nupkg')
PACKAGE_LIMIT = 200 * 1024 * 1024


class PackageRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections = 2
    max_repeats = 1

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        uri = urllib.parse.urlsplit(newurl)
        if not (uri.scheme == 'https' and not uri.username and not uri.password and
                uri.port is None and uri.hostname and
                (uri.hostname == 'pkgs.dev.azure.com' or
                 re.fullmatch(r'[a-z0-9-]+\.vsblob\.vsassets\.io', uri.hostname))):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_package(path, opener=None):
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), PackageRedirect())
    start = time.monotonic()
    total = 0
    with opener.open(PACKAGE_URL, timeout=15) as response, path.open('xb') as stream:
        require(response.status == 200)
        while True:
            if time.monotonic() - start > 90:
                raise TimeoutError('package acquisition limit')
            block = response.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            require(total <= PACKAGE_LIMIT)
            stream.write(block)


def extract_package(archive, destination, expected_sha=PACKAGE_SHA):
    digest = hashlib.sha256()
    with open(archive, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    require(digest.hexdigest() == expected_sha)
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        require(len(members) <= 3000 and sum(i.file_size for i in members) <= 512 * 1024 * 1024)
        names = set()
        for info in members:
            path = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            require(info.filename and not path.is_absolute() and '..' not in path.parts and
                    '\\' not in info.filename and ':' not in info.filename and
                    info.filename not in names and
                    stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR))
            names.add(info.filename)
        require('bxl' in names and not destination.exists())
        destination.mkdir(mode=0o700)
        z.extractall(destination)
    (destination / 'bxl').chmod(0o700)


def trial_nonce(run_id, attempt):
    require(re.fullmatch(r'[1-9][0-9]{0,19}', run_id) and
            re.fullmatch(r'[1-9][0-9]{0,5}', attempt))
    return hashlib.sha256(('Azure/meta-iotedge:managed-roundtrip:' + run_id + ':' + attempt).encode()).hexdigest()[:32]


def prepare_action(root, phase, nonce):
    require(phase in ('producer', 'consumer') and re.fullmatch('[0-9a-f]{32}', nonce))
    run = root / phase
    run.mkdir(mode=0o700)  # No phase reuse, including on retry.
    src = root / 'src'
    if phase == 'consumer':
        for name, destination in [('src', 'previous-src'), ('work', 'previous-work'),
                                  ('execution-marker.txt', 'previous-marker')]:
            old = root / name
            if old.exists() or old.is_symlink():
                require(not old.is_symlink() and (root / 'producer').is_dir())
                old.rename(root / 'producer' / destination)
    src.mkdir(mode=0o700)
    (src / 'nonce.txt').write_text(nonce + '\n')
    (src / 'action.sh').write_text('set -eu\nprintf "executed\\n" >> "$3"\n'
        'while IFS= read -r line; do printf "official-buildxl-spike:%s\\n" "$line"; '
        'done < "$1" > "$2"\n')
    (src / 'module.config.dsc').write_text('module({name: "ManagedCachePilot", projects: [f`action.dsc`]});\n')
    (src / 'config.dsc').write_text('config({resolvers: [{kind: "DScript", modules: [f`module.config.dsc`]}]});\n')
    marker = str(root / 'execution-marker.txt')
    (src / 'action.dsc').write_text('''import {Transformer, Cmd, Artifact} from "Sdk.Transformers";
const out = p`${Context.getMount("ObjectRoot").path}/artifact.txt`;
@@public
export const action = Transformer.execute({
    tool: {exe: f`/usr/bin/bash`, dependsOnCurrentHostOSDirectories: true,
           untrackedFiles: [f`MARKER`], timeoutInMilliseconds: 10000},
    workingDirectory: d`.`,
    arguments: [Cmd.argument(Artifact.input(f`action.sh`)),
                Cmd.argument(Artifact.input(f`nonce.txt`)),
                Cmd.argument(Artifact.output(out)),
                Cmd.argument(Artifact.none(p`MARKER`))],
    description: "bounded-managed-cache-pilot"
});
'''.replace('MARKER', marker))
    config = {
        'Assembly': 'BuildXL.Cache.MemoizationStoreAdapter',
        'Type': 'BuildXL.Cache.MemoizationStoreAdapter.BlobWithLocalCacheFactory',
        'FailIfRemoteFails': True,
        'LocalCache': {'CacheId': 'PilotLocal', 'CacheRootPath': str(run / 'local-cache'),
                       'CacheLogPath': str(run / 'local.log'), 'MaxCacheSizeInMB': 64,
                       'IsReadOnly': False},
        'RemoteCache': {'CacheId': 'PilotManaged', 'CacheLogPath': str(run / 'remote.log'),
                        'HostedPoolBuildCacheConfigurationFile': str(RUNTIME_CONFIG),
                        'HostedPoolActiveBuildCacheName': 'yocto-sstate',
                        'ConnectionStringFileDataProtectionEncrypted': False,
                        'IsReadOnly': phase == 'consumer', 'AllowInteractiveAuth': False,
                        'LogToKusto': False, 'EnableContentRecoveryOnPlaceFailure': False}}
    (run / 'cache.json').write_text(json.dumps(config))
    return {'config': config, 'run': run, 'src': src}


COUNTERS = {
    'hits': 'PipExecution.CacheHitsForProcessPipDescriptors',
    'executions': 'PipExecution.ProcessPipsExecutedDueToCacheMiss',
    'remote_bytes': 'PipExecution.RemoteContentDownloadedBytes',
    'remote_hits': 'PipExecution.RemoteCacheHitsForProcessPipDescriptorAndContent',
    'warnings': 'WarningWasLogged', 'errors': 'ErrorWasLogged'}


def verify_result(phase, nonce, artifact, marker, stats, exit_code):
    require(phase in ('producer', 'consumer') and exit_code == 0)
    counters = {name: stats[key] for name, key in COUNTERS.items()}
    require(all(type(value) is int and value >= 0 for value in counters.values()))
    consumer = phase == 'consumer'
    require(counters['hits'] == int(consumer) and counters['executions'] == int(not consumer)
            and counters['warnings'] == 0 and counters['errors'] == 0)
    expected = b'official-buildxl-spike:' + nonce.encode() + b'\n'
    content = read_regular(artifact, 64 * 1024)
    require(content == expected and len(content) == 56)
    if consumer:
        require(not marker.exists() and not marker.is_symlink() and
                counters['remote_bytes'] == 56 and counters['remote_hits'] == 1)
    else:
        require(read_regular(marker, 64) == b'executed\n')
    return {'schema_version': 1, 'phase': phase, 'status': 'passed',
            'artifact_bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
            **counters}


def read_stats(path):
    result = {}
    for line in read_regular(path, 2 * 1024 * 1024).decode('utf-8').splitlines():
        key, separator, value = line.partition('=')
        if key in COUNTERS.values():
            require(separator and key not in result and re.fullmatch(r'[0-9]{1,12}', value))
            result[key] = int(value)
    require(set(result) == set(COUNTERS.values()))
    return result


def limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run_engine(command, run, timeout=90):
    for name in ('home', 'tmp'):
        (run / name).mkdir(mode=0o700, exist_ok=True)
    env = {'HOME': str(run / 'home'), 'TMPDIR': str(run / 'tmp'), 'PATH': '/usr/bin:/bin',
           'DOTNET_CLI_TELEMETRY_OPTOUT': '1', 'DOTNET_EnableDiagnostics': '0'}
    def private_log(name):
        fd = os.open(run / name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        return os.fdopen(fd, 'wb')
    with private_log('stdout.private') as stdout, private_log('stderr.private') as stderr:
        process = subprocess.Popen(command, cwd=run, env=env, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr, start_new_session=True,
                                   preexec_fn=limits)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            raise TimeoutError('engine execution limit') from None
        finally:
            # Also runs if the overall pilot deadline interrupts wait().
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


DIGEST_FIELDS = ('sha256', 'host_id', 'path_id', 'input_id')


def validate_summary(summary):
    keys = {'schema_version', 'phase', 'status', 'artifact_bytes', 'runner_id',
            'different_host_identity', 'containers', *DIGEST_FIELDS, *COUNTERS}
    exact_fields(summary, keys)
    require(type(summary['schema_version']) is int and summary['schema_version'] == 1 and
            summary['phase'] in ('producer', 'consumer') and summary['status'] == 'passed')
    for key in (*DIGEST_FIELDS, 'runner_id'):
        require(type(summary[key]) is str and re.fullmatch('[0-9a-f]{64}', summary[key]))
    for key in ('artifact_bytes', 'containers', *COUNTERS):
        require(type(summary[key]) is int and 0 <= summary[key] <= 1024 * 1024)
    require(summary['artifact_bytes'] == 56 and 0 < summary['containers'] <= 12 and
            type(summary['different_host_identity']) is bool)


def private_directory(path, allow_existing=False):
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        require(allow_existing)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
            info.st_mode & 0o077 == 0)


def private_root(run_id, attempt, phase):
    # Use the OS account home, never caller-selected HOME/TMPDIR/workspace paths.
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    require(home.is_absolute() and not home.is_symlink())
    base = home / '.meta-iotedge-managed-roundtrip'
    private_directory(base, allow_existing=True)
    root = base / (run_id + '-' + attempt)
    private_directory(root, allow_existing=phase == 'consumer')
    require(re.fullmatch(r'/[A-Za-z0-9_./-]+', str(root)) and '..' not in root.parts)
    return root


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def perform(root, phase, nonce, expected, set_stage=lambda stage: None):
    set_stage('metadata-validation')
    metadata = read_metadata()
    validate_metadata(metadata)
    set_stage('container-preflight')
    containers = check_containers(metadata)
    set_stage('initialization')
    path_id = digest_bytes(str(root).encode())
    if phase == 'consumer':
        require(set(expected) == set(DIGEST_FIELDS))
        require(all(type(v) is str and re.fullmatch('[0-9a-f]{64}', v) for v in expected.values()))
        require(expected['path_id'] == path_id)
    action = prepare_action(root, phase, nonce)
    run = action['run']
    input_bytes = b''.join(f.name.encode() + b'\0' + f.read_bytes()
                           for f in sorted(action['src'].iterdir()))
    input_id = digest_bytes(input_bytes + read_regular('/usr/bin/bash', 4 * 1024 * 1024) + PACKAGE_SHA.encode())
    if phase == 'consumer':
        require(expected['input_id'] == input_id)
    archive = run / 'package.nupkg'
    set_stage('package-acquisition')
    download_package(archive)
    package = root / 'package'
    if package.exists() or package.is_symlink():
        require(phase == 'consumer' and not package.is_symlink() and (root / 'producer').is_dir())
        package.rename(root / 'producer' / 'previous-package')
    extract_package(archive, package)
    # Fresh phase roots were created exclusively. No prior engine/local state is reused.
    command = [str(package / 'bxl'), '/c:' + str(action['src'] / 'config.dsc'),
               '/cacheConfigFilePath:' + str(run / 'cache.json'), '/server-', '/remoteTelemetry-',
               '/interactive-', '/cacheGraph-', '/logExecution-', '/enableLinuxEBPFSandbox-',
               '/incrementalScheduling-', '/reuseOutputsOnDisk-', '/fingerprintSalt:' + nonce,
               '/objectDirectory:' + str(root / 'work/obj'),
               '/cacheDirectory:' + str(run / 'engine-artifacts'),
               '/engineCacheDirectory:' + str(run / 'engine-state'),
               '/logsDirectory:' + str(run / 'logs')]
    # Runtime credentials stay in-place; never copy them into the private trial.
    set_stage('metadata-validation')
    require(read_metadata() == metadata)
    metadata = None
    set_stage('engine-execution')
    code = run_engine(command, run)
    require(code == 0)  # Preserve the engine stage before attempting to read results.
    set_stage('result-verification')
    summary = verify_result(phase, nonce, root / 'work/obj/artifact.txt',
                            root / 'execution-marker.txt', read_stats(run / 'logs/BuildXL.stats'), code)
    host_id = digest_bytes(read_regular('/etc/machine-id', 256).strip())
    summary.update(host_id=host_id, runner_id=digest_bytes(os.environ.get('RUNNER_NAME', '').encode()),
                   path_id=path_id, input_id=input_id, containers=containers,
                   different_host_identity=(phase == 'consumer' and host_id != expected['host_id']))
    if phase == 'consumer':
        require(summary['sha256'] == expected['sha256'])
    validate_summary(summary)
    return summary


def deadline(*args):
    raise TimeoutError('pilot overall limit')


# Native keys: pinned BuildCache{Configuration,Shard,Container}.cs (see pilot docs).
# Lowercase spellings/wrappers are diagnostic comparisons only, never runtime adapters.
SCHEMA_FIELDS = {
    'root': ('AssociatedBuildCaches', 'associatedBuildCaches', 'BuildCaches', 'buildCaches'),
    'resource': ('Name', 'name', 'RetentionDays', 'retentionDays', 'Shards', 'shards'),
    'shard': ('StorageUrl', 'storageUrl', 'Containers', 'containers'),
    'container': ('Name', 'name', 'Signature', 'signature', 'Type', 'type')}
SCHEMA_SAS = ('sv', 'sr', 'sp', 'st', 'se', 'sig', 'sip', 'spr', 'si', 'skoid', 'sktid',
              'skt', 'ske', 'sks', 'skv', 'saoid', 'suoid', 'scid', 'ss', 'srt')
SCHEMA_ENUMS = {
    'read_status': ('missing', 'symlink-refused', 'nonregular', 'oversized', 'permission-denied',
                    'invalid-json', 'duplicate-or-contract', 'ok'),
    'file_kind': ('missing', 'regular', 'symlink', 'directory', 'fifo', 'socket', 'character', 'block', 'other'),
    'root_kind': ('unread', 'array', 'object', 'string', 'number', 'boolean', 'null')}
SCHEMA_COUNTS = ('file_bytes', 'resource_count', 'cache_name_match_count', 'selected_shard_count',
                 'container_count', 'permissions_valid_count', 'credential_container_scope_count',
                 *(f'{level}_unknown_key_count' for level in SCHEMA_FIELDS),
                 *(f'{level}_{key}_present_count' for level, keys in SCHEMA_FIELDS.items() for key in keys),
                 *(f'sas_{key}_present_count' for key in SCHEMA_SAS),
                 *(f'role_{kind}_count' for kind in ('content', 'metadata', 'checkpoint', 'other')),
                 *(f'type_{kind}_count' for kind in ('string', 'number', 'boolean', 'null', 'array', 'object')),
                 *(f'signature_{kind}_count' for kind in ('empty', 'query', 'full_uri', 'other')))


def validate_schema_summary(summary):
    exact_fields(summary, (*SCHEMA_ENUMS, *SCHEMA_COUNTS, 'validator_passes',
                           'permissions_valid', 'credential_container_scope'))
    for key in ('validator_passes', 'permissions_valid', 'credential_container_scope'):
        require(type(summary[key]) is bool)
    for key, choices in SCHEMA_ENUMS.items():
        require(type(summary[key]) is str and summary[key] in choices)
    for key in SCHEMA_COUNTS:
        require(type(summary[key]) is int and 0 <= summary[key] <= METADATA_LIMIT)
    require(len(json.dumps(summary)) <= 16384)


def schema_facts(data, summary):
    def kind(value):
        return {list: 'array', dict: 'object', str: 'string', int: 'number', float: 'number',
                bool: 'boolean', type(None): 'null'}[type(value)]
    def fields(level, obj):
        if type(obj) is not dict:
            return
        summary[level + '_unknown_key_count'] += len(set(obj) - set(SCHEMA_FIELDS[level]))
        for key in SCHEMA_FIELDS[level]:
            summary[f'{level}_{key}_present_count'] += int(key in obj)
    def value(obj, key):
        return obj.get(key, obj.get(key[0].lower() + key[1:])) if type(obj) is dict else None
    def array(obj):
        return obj if type(obj) is list else []
    summary['root_kind'] = kind(data)
    fields('root', data)
    resources = (data if type(data) is list else
                 [item for key in SCHEMA_FIELDS['root']
                  for item in array(data.get(key) if type(data) is dict else None)])
    summary['resource_count'] = len(resources)
    for cache in resources:
        fields('resource', cache)
        if value(cache, 'Name') != 'yocto-sstate':
            continue
        summary['cache_name_match_count'] += 1
        shards = array(value(cache, 'Shards'))
        summary['selected_shard_count'] += len(shards)
        for shard in shards:
            fields('shard', shard)
            containers = array(value(shard, 'Containers'))
            summary['container_count'] += len(containers)
            for container in containers:
                fields('container', container)
                role = value(container, 'Type')
                summary[f'type_{kind(role)}_count'] += 1
                role = role.lower() if type(role) is str else ''
                summary['role_' + (role if role in ('content', 'metadata', 'checkpoint') else 'other') + '_count'] += 1
                signature = value(container, 'Signature')
                signature = signature if type(signature) is str else None
                full = signature is not None and signature.lower().startswith(('https:', 'http:'))
                sig_kind = ('empty' if signature == '' else 'full_uri' if full else
                            'query' if signature and '=' in signature else 'other')
                summary[f'signature_{sig_kind}_count'] += 1
                try:
                    require(signature is not None and len(signature) <= 8192)
                    signature = signature or ''
                    query = unique_object(urllib.parse.parse_qsl(
                        urllib.parse.urlsplit(signature).query if full else signature.lstrip('?'),
                        keep_blank_values=True, strict_parsing=True, max_num_fields=32))
                    for key in SCHEMA_SAS:
                        summary[f'sas_{key}_present_count'] += int(key in query)
                    permission = query.get('sp', '')
                    summary['permissions_valid_count'] += int(bool(permission) and 'r' in permission and
                                                               set(permission) <= set('racwdxltmeop'))
                    summary['credential_container_scope_count'] += int(query.get('sr') == 'c' and
                                                                      not {'ss', 'srt'} & set(query))
                except ValueError:
                    pass
    for key in ('permissions_valid', 'credential_container_scope'):
        summary[key] = 0 < summary['container_count'] == summary[key + '_count']
    try:
        validate_metadata(data)  # Pure existing validator; no container I/O or normalization.
        summary['validator_passes'] = True
    except (ValueError, TypeError, KeyError):
        pass


def metadata_schema(path=None):
    summary: dict = dict.fromkeys(SCHEMA_COUNTS, 0)
    summary.update(read_status='missing', validator_passes=False, file_kind='missing', root_kind='unread',
                   permissions_valid=False, credential_container_scope=False)
    try:
        path = RUNTIME_CONFIG if path is None else path
        info = path.lstat()
        summary['file_kind'] = next((name for predicate, name in (
            (stat.S_ISREG, 'regular'), (stat.S_ISLNK, 'symlink'), (stat.S_ISDIR, 'directory'),
            (stat.S_ISFIFO, 'fifo'), (stat.S_ISSOCK, 'socket'), (stat.S_ISCHR, 'character'),
            (stat.S_ISBLK, 'block')) if predicate(info.st_mode)), 'other')
        if summary['file_kind'] != 'regular':
            summary['read_status'] = ('symlink-refused' if summary['file_kind'] == 'symlink'
                                      else 'nonregular')
            return summary
        if info.st_size > METADATA_LIMIT:
            summary['read_status'] = 'oversized'
            return summary
        raw = read_regular(path, METADATA_LIMIT)
        summary['file_bytes'] = len(raw)
        data = json.loads(raw, object_pairs_hook=unique_object)
        summary['read_status'] = 'ok'
        schema_facts(data, summary)
    except FileNotFoundError:
        summary['read_status'] = 'missing'
    except PermissionError:
        summary['read_status'] = 'permission-denied'
    except (json.JSONDecodeError, UnicodeError, RecursionError):
        summary['read_status'] = 'invalid-json'
    except OSError as error:
        summary['read_status'] = {errno.ELOOP: 'symlink-refused', errno.EISDIR: 'nonregular',
                                  errno.EFBIG: 'oversized'}.get(error.errno or 0, 'duplicate-or-contract')
    except ValueError:
        summary['read_status'] = 'duplicate-or-contract'
    return summary


def main(args):
    if args == ['metadata-schema']:
        summary = metadata_schema()
        validate_schema_summary(summary)
        print(json.dumps(summary, sort_keys=True))
        return 0
    if len(args) != 1 or args[0] not in ('producer', 'consumer'):
        return 2
    phase = args[0]
    os.umask(0o077)
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(230)
    stage = 'initialization'
    def set_stage(value):
        nonlocal stage
        stage = value
    try:
        run_id, attempt = os.environ.get('GITHUB_RUN_ID', ''), os.environ.get('GITHUB_RUN_ATTEMPT', '')
        nonce = trial_nonce(run_id, attempt)
        root = private_root(run_id, attempt, phase)
        expected = ({key: os.environ.get('PRODUCER_' + key.upper(), '') for key in DIGEST_FIELDS}
                    if phase == 'consumer' else {})
        summary = perform(root, phase, nonce, expected, set_stage)
        set_stage('summary-publication')
        validate_summary(summary)
        # All output values are validated hex digests; no raw native data reaches job outputs.
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            for key in DIGEST_FIELDS:
                output.write(key + '=' + summary[key] + '\n')
        print(json.dumps(summary, sort_keys=True))
        return 0
    except Exception:
        print('failure-stage: ' + stage, file=sys.stderr)
        print(json.dumps({'schema_version': 1, 'phase': phase, 'status': 'failed'}))
        return 1
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
