"""Offline safety fixtures; never read runtime credentials or contact Azure."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/shared-cache-roundtrip.py'


def load():
    spec = importlib.util.spec_from_file_location('roundtrip', SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metadata():
    return [{'Name': 'yocto-sstate', 'RetentionDays': 7, 'Shards': [{
        'StorageUrl': 'https://fixtureaccount.blob.core.windows.net/',
        'Containers': [{'Name': 'fixture-' + kind.lower(), 'Type': kind,
                        'Signature': '?sv=2024-11-04&sr=c&sp=racwl&se=2099-01-01T00%3A00%3A00Z&sig=FIXTURE_SECRET'}
                       for kind in ('Content', 'Metadata', 'Checkpoint')]}]}]


class SchemaTests(unittest.TestCase):
    def test_schema_facts_are_fixed_secret_free_and_do_not_normalize_validator(self):
        m = load()
        def probe(data):
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'metadata'
                path.write_text(json.dumps(data))
                result = m.metadata_schema(path)
                m.validate_schema_summary(result)
                self.assertNotIn('FIXTURE_SECRET', json.dumps(result))
                self.assertNotIn('fixtureaccount', json.dumps(result))
                return result
        good = probe(metadata())
        self.assertTrue(good['validator_passes'])
        self.assertIs(good['permissions_valid'], True)
        self.assertIs(good['credential_container_scope'], True)
        self.assertEqual(good['root_kind'], 'array')
        for key, count in {'resource_count': 1, 'cache_name_match_count': 1,
                'selected_shard_count': 1, 'container_count': 3, 'role_content_count': 1,
                'type_string_count': 3, 'signature_query_count': 3,
                'sas_sig_present_count': 3, 'permissions_valid_count': 3,
                'credential_container_scope_count': 3}.items():
            self.assertEqual(good[key], count, key)
        for wrapper in ('AssociatedBuildCaches', 'associatedBuildCaches', 'BuildCaches', 'buildCaches'):
            data = metadata()
            data[0]['FIXTURE_SECRET_UNKNOWN_KEY'] = 'FIXTURE_SECRET_VALUE'
            for obj in [data[0], data[0]['Shards'][0], *data[0]['Shards'][0]['Containers']]:
                for key in list(obj):
                    if key != 'FIXTURE_SECRET_UNKNOWN_KEY':
                        obj[key[0].lower() + key[1:]] = obj.pop(key)
            result = probe({wrapper: data, 'FIXTURE_SECRET_ROOT_KEY': 'FIXTURE_SECRET'})
            self.assertFalse(result['validator_passes'])
            self.assertEqual(result['root_' + wrapper + '_present_count'], 1)
            self.assertEqual(result['root_unknown_key_count'], 1)
            self.assertEqual(result['resource_unknown_key_count'], 1)
            self.assertEqual(result['resource_name_present_count'], 1)
            self.assertEqual(result['container_signature_present_count'], 3)
            self.assertEqual(result['cache_name_match_count'], 1)
        data = metadata()
        containers = data[0]['Shards'][0]['Containers']
        for obj in [data[0]['Shards'][0], containers[0]]:
            obj['FIXTURE_SECRET_KEY'] = 'FIXTURE_SECRET'
        for container, kind, signature in zip(containers, [17, 'CONTENT', 'FIXTURE_SECRET'],
                ['', 'https://fixtureaccount.invalid/?sp=FIXTURE_SECRET&sr=b&sig=FIXTURE_SECRET',
                 'FIXTURE_SECRET']):
            container.update(Type=kind, Signature=signature)
        result = probe(data)
        for key in ('type_number_count', 'role_content_count',
                    'signature_empty_count', 'signature_full_uri_count', 'signature_other_count',
                    'shard_unknown_key_count', 'container_unknown_key_count'):
            self.assertEqual(result[key], 1, key)
        self.assertEqual(result['role_other_count'], 2)  # Numeric and unknown string roles.
        self.assertEqual(result['permissions_valid_count'], 0)
        self.assertEqual(result['credential_container_scope_count'], 0)
        for bad in (dict(good, injected='FIXTURE_SECRET'), dict(good, root_kind='FIXTURE_SECRET'),
                    dict(good, file_bytes=True), dict(good, file_bytes=m.METADATA_LIMIT + 1)):
            with self.assertRaises(ValueError):
                m.validate_schema_summary(bad)

    def test_read_classification_reuses_bounded_nofollow_helper(self):
        from unittest.mock import patch
        import socket
        m = load()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / 'regular'
            file.write_text('[]')
            (root / 'link').symlink_to(file)
            (root / 'directory').mkdir()
            os.mkfifo(root / 'fifo')
            with socket.socket(socket.AF_UNIX) as sock:
                sock.bind(str(root / 'socket'))
                for name, kind, status in [('absent', 'missing', 'missing'),
                        ('link', 'symlink', 'symlink-refused'), ('directory', 'directory', 'nonregular'),
                        ('fifo', 'fifo', 'nonregular'), ('socket', 'socket', 'nonregular')]:
                    with self.subTest(name=name), patch.object(m, 'read_regular') as read:
                        summary = m.metadata_schema(root / name)
                        self.assertEqual((summary['file_kind'], summary['read_status']), (kind, status))
                        read.assert_not_called()
            for content, status in [(b'x' * (m.METADATA_LIMIT + 1), 'oversized'),
                    (b'{', 'invalid-json'), (b'\xff', 'invalid-json'),
                    (b'{"Name":1,"Name":2}', 'duplicate-or-contract'), (b'[]', 'ok')]:
                file.write_bytes(content)
                summary = m.metadata_schema(file)
                self.assertEqual(summary['read_status'], status)
                self.assertLessEqual(summary['file_bytes'], m.METADATA_LIMIT)
            with patch.object(m, 'read_regular', side_effect=PermissionError('FIXTURE_SECRET')):
                self.assertEqual(m.metadata_schema(file)['read_status'], 'permission-denied')
            import errno
            for number, status in [(errno.ELOOP, 'symlink-refused'), (errno.EISDIR, 'nonregular'),
                                   (errno.EFBIG, 'oversized')]:
                with patch.object(m, 'read_regular', side_effect=OSError(number, 'FIXTURE_SECRET')):
                    self.assertEqual(m.metadata_schema(file)['read_status'], status)
            from types import SimpleNamespace
            import stat
            for mode, kind in [(stat.S_IFCHR, 'character'), (stat.S_IFBLK, 'block'), (0, 'other')]:
                with patch.object(Path, 'lstat', return_value=SimpleNamespace(st_mode=mode, st_size=0)), \
                     patch.object(m, 'read_regular') as read:
                    self.assertEqual(m.metadata_schema(file)['file_kind'], kind)
                    read.assert_not_called()

    def test_cli_validates_before_print_and_reads_only_the_fixed_fixture(self):
        import contextlib
        import io
        from unittest.mock import patch
        m = load()
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / 'metadata'
            for raw in (json.dumps(metadata()), '{', '{"FIXTURE_SECRET":1,"FIXTURE_SECRET":2}'):
                fixture.write_text(raw)
                public, errors = io.StringIO(), io.StringIO()
                with patch.object(m, 'RUNTIME_CONFIG', fixture), \
                     patch.object(m, 'read_regular', wraps=m.read_regular) as read, \
                     patch.object(m, 'perform', side_effect=AssertionError('engine')), \
                     patch.object(m, 'private_root', side_effect=AssertionError('trial writes')), \
                     patch.object(m.subprocess, 'Popen', side_effect=AssertionError('process')), \
                     patch.object(m.urllib.request, 'build_opener', side_effect=AssertionError('network')), \
                     patch.object(m.urllib.request, 'urlopen', side_effect=AssertionError('network')), \
                     contextlib.redirect_stdout(public), contextlib.redirect_stderr(errors):
                    self.assertEqual(m.main(['metadata-schema']), 0)
                    read.assert_called_once_with(fixture, m.METADATA_LIMIT)
                m.validate_schema_summary(json.loads(public.getvalue()))
                self.assertEqual(errors.getvalue(), '')
                self.assertNotIn('FIXTURE_SECRET', public.getvalue())
            public = io.StringIO()
            with patch.object(m, 'metadata_schema', return_value={'raw': 'FIXTURE_SECRET'}), \
                 contextlib.redirect_stdout(public), self.assertRaises(ValueError):
                m.main(['metadata-schema'])
            self.assertEqual(public.getvalue(), '')

    def test_cli_is_early_readonly_inventory_even_when_missing(self):
        import contextlib
        import io
        from unittest.mock import patch
        m = load()
        public, errors = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(m, 'RUNTIME_CONFIG', Path('/fixture-missing-metadata')))
            forbidden = [stack.enter_context(patch.object(m, name, side_effect=AssertionError(name)))
                         for name in ('perform', 'private_root', 'download_package', 'check_containers',
                                      'run_engine', 'private_opener')]
            stack.enter_context(patch.object(m.urllib.request, 'build_opener', side_effect=AssertionError('network')))
            stack.enter_context(contextlib.redirect_stdout(public))
            stack.enter_context(contextlib.redirect_stderr(errors))
            self.assertEqual(m.main(['metadata-schema']), 0)
            for call in forbidden:
                call.assert_not_called()
        summary = json.loads(public.getvalue())
        self.assertEqual(summary['read_status'], 'missing')
        self.assertFalse(summary['validator_passes'])
        self.assertEqual(errors.getvalue(), '')


class MetadataTests(unittest.TestCase):
    def test_native_array_selects_exact_cache_and_container_scoped_targets(self):
        self.assertTrue(SCRIPT.exists(), 'managed roundtrip helper is missing')
        m = load()
        targets = m.validate_metadata(metadata())
        self.assertEqual(len(targets), 3)
        self.assertTrue(all(url.startswith('https://fixtureaccount.blob.core.windows.net/fixture-') for url in targets))
        self.assertTrue(all('restype=container' in url for url in targets))

    def test_schema_url_and_credential_ambiguity_fail_closed(self):
        m = load()
        cases = [
            lambda d: {'AssociatedBuildCaches': d},
            lambda d: d + copy.deepcopy(d),
            lambda d: [dict(d[0], Name='other')],
            lambda d: [dict(d[0], RetentionDays=True)],
            lambda d: [dict(d[0], retentiondays=7)],
            lambda d: [dict(d[0], Shards=[])],
        ]
        for mutation in cases:
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    m.validate_metadata(mutation(metadata()))
        for field, values in {
            'StorageUrl': ['http://fixtureaccount.blob.core.windows.net/',
                           'https://fixtureaccount.blob.core.windows.net.evil/',
                           'https://user@fixtureaccount.blob.core.windows.net/',
                           'https://fixtureaccount.blob.core.windows.net:443/',
                           'https://fixtureaccount.blob.core.windows.net/other',
                           'https://fixtureaccount.blob.core.windows.net/?sig=secret'],
            'Name': ['../other', 'abc/def', 'ab', 'abc--def'],
            'Type': ['Unknown', 'Metadata', 0],
            'Signature': ['?ss=b&srt=sco&sp=r&sig=secret',
                          '?sr=b&sp=r&sig=secret', '?sr=c&sp=r',
                          '?sr=c&sp=r&sig=a&sig=b',
                          '?sr=c&sp=r&sig=secret&credential=secret',
                          '?sr=c&sp=r&sig=secret&ss=b',
                          '?sr=c&sp=r&sig=secret&sr=c',
                          'https://evil/?sr=c&sp=r&sig=secret'],
        }.items():
            for value in values:
                data = metadata()
                obj = data[0]['Shards'][0]
                if field != 'StorageUrl':
                    obj = obj['Containers'][0]
                obj[field] = value
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        m.validate_metadata(data)
        data = metadata()
        data[0]['Shards'][0]['Containers'][1]['Name'] = 'fixture-content'
        with self.assertRaises(ValueError):
            m.validate_metadata(data)

    def test_bounded_regular_nofollow_read_rejects_links_fifo_oversize_duplicates(self):
        m = load()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            regular = root / 'metadata'
            regular.write_text(json.dumps(metadata()))
            self.assertEqual(m.read_metadata(regular), metadata())
            link = root / 'link'
            link.symlink_to(regular)
            fifo = root / 'fifo'
            os.mkfifo(fifo)
            for path in (link, fifo):
                with self.assertRaises((ValueError, OSError)):
                    m.read_metadata(path)
            regular.write_bytes(b'x' * (m.METADATA_LIMIT + 1))
            with self.assertRaises(ValueError):
                m.read_metadata(regular)
            regular.write_text('{"Name":1,"Name":2}')
            with self.assertRaises(ValueError):
                m.read_metadata(regular)


class NetworkPackageTests(unittest.TestCase):
    def test_heads_only_preexisting_selected_containers_no_redirect_or_proxy(self):
        m = load()
        self.assertTrue(hasattr(m, 'check_containers'), 'bounded container HEAD preflight missing')
        calls = []
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args): raise AssertionError('must not download body')
        class Opener:
            def open(self, request, timeout):
                calls.append((request.get_method(), request.full_url, timeout))
                return Response()
        m.check_containers(metadata(), opener=Opener())
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(method == 'HEAD' and timeout <= 5 for method, url, timeout in calls))
        import urllib.request
        from unittest.mock import patch
        with patch.dict(os.environ, {'HTTPS_PROXY': 'http://fixture-secret.invalid'}):
            opener = m.private_opener()
            self.assertFalse(any(isinstance(h, urllib.request.ProxyHandler) and h.proxies
                                 for h in opener.handlers))
            redirect = next(h for h in opener.handlers if isinstance(h, urllib.request.HTTPRedirectHandler))
            self.assertIsNone(redirect.redirect_request(None, None, 302, '', {}, 'https://evil.invalid'))
        for status in (301, 302, 403, 404, 500):
            Response.status = status
            with self.assertRaises(ValueError):
                m.check_containers(metadata(), opener=Opener())
        invalid = metadata()
        invalid[0]['Shards'][0]['Containers'][0]['Signature'] += '&ss=b'
        calls.clear()
        with self.assertRaises(ValueError):
            m.check_containers(invalid, opener=Opener())
        self.assertEqual(calls, [])
        class Timeout:
            def open(self, *args, **kwargs): raise TimeoutError('FIXTURE_SECRET')
        with self.assertRaises(TimeoutError):
            m.check_containers(metadata(), opener=Timeout())

    def test_package_pin_and_full_zip_validation_before_extract(self):
        m = load()
        self.assertTrue(hasattr(m, 'extract_package'), 'verified package extraction missing')
        import hashlib
        import zipfile
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'package.zip'
            def archive_with(name, mode=0o100644):
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr('bxl', b'fixture')
                    info = zipfile.ZipInfo(name)
                    info.external_attr = mode << 16
                    z.writestr(info, b'fixture')
                return hashlib.sha256(archive.read_bytes()).hexdigest()
            digest = archive_with('Sdk.Transformers/test')
            m.extract_package(archive, root / 'good', expected_sha=digest)
            self.assertTrue(os.access(root / 'good/bxl', os.X_OK))
            for name, mode in [('../escape', 0o100644), ('/absolute', 0o100644),
                               ('safe/link', 0o120777), ('safe/../../escape', 0o100644),
                               ('safe\\escape', 0o100644)]:
                digest = archive_with(name, mode)
                with self.assertRaises(ValueError):
                    m.extract_package(archive, root / 'bad', expected_sha=digest)
                self.assertFalse((root / 'bad').exists())
            digest = archive_with('valid')
            with self.assertRaises(ValueError):
                m.extract_package(archive, root / 'bad', expected_sha='0' * 64)
            self.assertFalse((root / 'bad').exists())


class ActionTests(unittest.TestCase):
    def test_official_topology_quota_nonce_and_stable_fresh_local_paths(self):
        m = load()
        self.assertTrue(hasattr(m, 'prepare_action'), 'native action preparation missing')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            nonce = m.trial_nonce('400000001', '1')
            self.assertRegex(nonce, r'^[0-9a-f]{32}$')
            self.assertNotEqual(nonce, m.trial_nonce('400000001', '2'))
            producer = m.prepare_action(root, 'producer', nonce)
            source = {f.name: f.read_bytes() for f in (root / 'src').iterdir()}
            cfg = producer['config']
            self.assertEqual(cfg['Type'], 'BuildXL.Cache.MemoizationStoreAdapter.BlobWithLocalCacheFactory')
            self.assertEqual(cfg['LocalCache']['MaxCacheSizeInMB'], 64)
            self.assertFalse(cfg['LocalCache']['IsReadOnly'])
            self.assertTrue(cfg['FailIfRemoteFails'])
            remote = cfg['RemoteCache']
            self.assertEqual(remote['HostedPoolBuildCacheConfigurationFile'], '/buildcacheconfig.json')
            self.assertEqual(remote['HostedPoolActiveBuildCacheName'], 'yocto-sstate')
            for field in ('ConnectionStringFileDataProtectionEncrypted', 'IsReadOnly',
                          'AllowInteractiveAuth', 'LogToKusto', 'EnableContentRecoveryOnPlaceFailure'):
                self.assertIs(remote[field], False)
            self.assertNotIn('Universe', remote)
            self.assertNotIn('Namespace', remote)
            self.assertIn(nonce.encode(), source['nonce.txt'])
            self.assertIn(b'Artifact.input(f`nonce.txt`)', source['action.dsc'])
            self.assertIn(b'untrackedFiles', source['action.dsc'])
            (root / 'work/obj').mkdir(parents=True)
            (root / 'work/obj/artifact.txt').write_text('old')
            (root / 'execution-marker.txt').write_text('executed\n')
            consumer = m.prepare_action(root, 'consumer', nonce)
            self.assertFalse((root / 'work').exists())
            self.assertFalse((root / 'execution-marker.txt').exists())
            self.assertEqual(source, {f.name: f.read_bytes() for f in (root / 'src').iterdir()})
            self.assertTrue((root / 'producer/previous-work/obj/artifact.txt').exists())
            self.assertTrue(consumer['config']['RemoteCache']['IsReadOnly'])
            for key in ('CacheRootPath', 'CacheLogPath'):
                self.assertNotEqual(cfg['LocalCache'][key], consumer['config']['LocalCache'][key])
            self.assertFalse(Path(consumer['config']['LocalCache']['CacheRootPath']).exists())
            with self.assertRaises((ValueError, FileExistsError)):
                m.prepare_action(root, 'consumer', nonce)

    def test_stats_and_exact_bytes_detect_consumer_fallback_and_warnings(self):
        m = load()
        self.assertTrue(hasattr(m, 'verify_result'), 'hit/miss classification missing')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            nonce = 'a' * 32
            artifact = root / 'artifact'
            artifact.write_bytes(b'official-buildxl-spike:' + nonce.encode() + b'\n')
            marker = root / 'marker'
            stats = {'PipExecution.CacheHitsForProcessPipDescriptors': 1,
                     'PipExecution.ProcessPipsExecutedDueToCacheMiss': 0,
                     'PipExecution.RemoteContentDownloadedBytes': 56,
                     'PipExecution.RemoteCacheHitsForProcessPipDescriptorAndContent': 1,
                     'WarningWasLogged': 0, 'ErrorWasLogged': 0}
            summary = m.verify_result('consumer', nonce, artifact, marker, stats, 0)
            self.assertEqual(summary['artifact_bytes'], 56)
            self.assertEqual(summary['status'], 'passed')
            for key, value in [('PipExecution.ProcessPipsExecutedDueToCacheMiss', 1),
                               ('PipExecution.CacheHitsForProcessPipDescriptors', 0),
                               ('PipExecution.RemoteContentDownloadedBytes', 0),
                               ('PipExecution.RemoteCacheHitsForProcessPipDescriptorAndContent', 0),
                               ('WarningWasLogged', 1), ('ErrorWasLogged', 1)]:
                with self.subTest(key=key):
                    with self.assertRaises(ValueError):
                        m.verify_result('consumer', nonce, artifact, marker, dict(stats, **{key: value}), 0)
            marker.write_text('executed\n')
            with self.assertRaises(ValueError):
                m.verify_result('consumer', nonce, artifact, marker, stats, 0)
            producer = dict(stats, **{'PipExecution.CacheHitsForProcessPipDescriptors': 0,
                                     'PipExecution.ProcessPipsExecutedDueToCacheMiss': 1,
                                     'PipExecution.RemoteContentDownloadedBytes': 0,
                                     'PipExecution.RemoteCacheHitsForProcessPipDescriptorAndContent': 0})
            m.verify_result('producer', nonce, artifact, marker, producer, 0)
            artifact.write_bytes(b'wrong')
            with self.assertRaises(ValueError):
                m.verify_result('producer', nonce, artifact, marker, producer, 0)
            with self.assertRaises(ValueError):
                m.verify_result('consumer', nonce, artifact, marker, stats, 1)


class ExecutionTests(unittest.TestCase):
    def test_real_child_output_secrets_env_and_process_group_timeout_are_private(self):
        m = load()
        self.assertTrue(hasattr(m, 'run_engine'), 'bounded private engine launch missing')
        import contextlib
        import io
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            child = root / 'child.py'
            child.write_text('import os,resource\nprint("FIXTURE_SECRET")\n'
                             'print(os.getenv("INHERITED_SECRET", "cleared"))\n'
                             'print(resource.getrlimit(resource.RLIMIT_CORE)[0])\n')
            public = io.StringIO()
            with patch.dict(os.environ, {'INHERITED_SECRET': 'FIXTURE_SECRET'}), contextlib.redirect_stdout(public):
                code = m.run_engine(['/usr/bin/python3', str(child)], root, timeout=2)
            self.assertEqual(code, 0)
            self.assertEqual(public.getvalue(), '')
            self.assertIn('cleared', (root / 'stdout.private').read_text())
            self.assertTrue((root / 'stdout.private').read_text().endswith('0\n'))
            self.assertEqual((root / 'stdout.private').stat().st_mode & 0o777, 0o600)
            child.write_text('import subprocess,time\nsubprocess.Popen(["/bin/sleep", "30"])\ntime.sleep(30)\n')
            with self.assertRaises(TimeoutError):
                m.run_engine(['/usr/bin/python3', str(child)], root, timeout=0.1)

    def test_stats_parser_rejects_missing_duplicate_or_non_numeric_counters(self):
        m = load()
        self.assertTrue(hasattr(m, 'read_stats'), 'strict stats parser missing')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'stats'
            valid = ''.join(key + '=0\n' for key in m.COUNTERS.values())
            path.write_text(valid)
            self.assertEqual(len(m.read_stats(path)), len(m.COUNTERS))
            for text in (valid + 'WarningWasLogged=0\n', valid.replace('ErrorWasLogged=0\n', ''),
                         valid.replace('ErrorWasLogged=0', 'ErrorWasLogged=secret')):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    m.read_stats(path)

    def test_download_has_size_timeout_and_redirect_limits(self):
        m = load()
        self.assertTrue(hasattr(m, 'download_package'), 'bounded public package acquisition missing')
        import io
        class Response(io.BytesIO):
            status = 200
        class Opener:
            def open(self, url, timeout):
                self.url, self.timeout = url, timeout
                return Response(b'package')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'archive'
            opener = Opener()
            m.download_package(path, opener=opener)
            self.assertEqual(opener.url, m.PACKAGE_URL)
            self.assertLessEqual(opener.timeout, 15)
            self.assertEqual(path.read_bytes(), b'package')
            from unittest.mock import patch
            with patch.object(m, 'PACKAGE_LIMIT', 2):
                with self.assertRaises(ValueError):
                    m.download_package(Path(temp) / 'oversize', opener=Opener())
            with patch.object(m.time, 'monotonic', side_effect=[0, 100]):
                with self.assertRaises(TimeoutError):
                    m.download_package(Path(temp) / 'slow', opener=Opener())
        redirect = m.PackageRedirect()
        import urllib.request
        request = urllib.request.Request(m.PACKAGE_URL)
        self.assertIsNone(redirect.redirect_request(request, None, 302, '', {}, 'http://evil.invalid'))
        self.assertIsNone(redirect.redirect_request(request, None, 302, '', {}, 'https://evil.invalid'))
        self.assertIsNotNone(redirect.redirect_request(request, None, 302, '', {},
                                                     'https://fixture.vsblob.vsassets.io/public'))


class LifecycleTests(unittest.TestCase):
    def test_allowlisted_summary_rejects_raw_metadata_and_invalid_digest(self):
        m = load()
        self.assertTrue(hasattr(m, 'validate_summary'), 'allowlisted publication contract missing')
        summary = {'schema_version': 1, 'phase': 'consumer', 'status': 'passed',
                   'artifact_bytes': 56, 'sha256': 'a' * 64, 'host_id': 'b' * 64,
                   'runner_id': 'c' * 64, 'path_id': 'd' * 64, 'input_id': 'e' * 64,
                   'different_host_identity': False, 'hits': 1, 'executions': 0,
                   'remote_bytes': 56, 'remote_hits': 1, 'warnings': 0, 'errors': 0,
                   'containers': 3}
        m.validate_summary(summary)
        for bad in (dict(summary, raw='FIXTURE_SECRET'), dict(summary, sha256='secret'),
                    dict(summary, status='secret'), dict(summary, hits=True)):
            with self.assertRaises(ValueError):
                m.validate_summary(bad)

    def test_coordinator_stops_before_engine_on_missing_container_or_mismatched_inputs(self):
        m = load()
        self.assertTrue(hasattr(m, 'perform'), 'managed lifecycle coordinator missing')
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            nonce = 'a' * 32
            with patch.object(m, 'read_metadata', return_value=metadata()), \
                 patch.object(m, 'check_containers', side_effect=ValueError('FIXTURE_SECRET')), \
                 patch.object(m, 'download_package') as download, patch.object(m, 'run_engine') as engine:
                with self.assertRaises(ValueError):
                    m.perform(root, 'producer', nonce, {})
                download.assert_not_called()
                engine.assert_not_called()
            with patch.object(m, 'read_metadata', return_value=metadata()), \
                 patch.object(m, 'check_containers', return_value=3), \
                 patch.object(m, 'download_package') as download, patch.object(m, 'run_engine') as engine:
                with self.assertRaises(ValueError):
                    m.perform(root, 'consumer', nonce, {'path_id': '0' * 64})
                download.assert_not_called()
                engine.assert_not_called()

    def test_changed_runtime_metadata_stops_before_native_launch(self):
        m = load()
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            changed = metadata()
            changed[0]['Shards'][0]['Containers'][0]['Name'] = 'different-existing'
            def extract(archive, package):
                package.mkdir()
                (package / 'bxl').write_text('fixture')
            with patch.object(m, 'read_metadata', side_effect=[metadata(), changed]), \
                 patch.object(m, 'check_containers', return_value=3), \
                 patch.object(m, 'download_package'), patch.object(m, 'extract_package', side_effect=extract), \
                 patch.object(m, 'run_engine', side_effect=AssertionError('native launch reached after metadata changed')) as engine:
                with self.assertRaises(ValueError):
                    m.perform(root, 'producer', 'a' * 32, {})
                engine.assert_not_called()

    def test_private_root_refuses_symlinks_permissive_dirs_and_phase_reuse(self):
        m = load()
        from unittest.mock import patch
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            with patch.object(m.pwd, 'getpwuid', return_value=SimpleNamespace(pw_dir=str(home))):
                root = m.private_root('400000001', '1', 'producer')
                self.assertEqual(root.stat().st_mode & 0o777, 0o700)
                with self.assertRaises(ValueError):
                    m.private_root('400000001', '1', 'producer')
                self.assertEqual(m.private_root('400000001', '1', 'consumer'), root)
                root.chmod(0o755)
                with self.assertRaises(ValueError):
                    m.private_root('400000001', '1', 'consumer')
                link = home / '.meta-iotedge-managed-roundtrip/400000001-2'
                link.symlink_to(root, target_is_directory=True)
                with self.assertRaises(ValueError):
                    m.private_root('400000001', '2', 'consumer')

    def test_cli_failure_stages_are_fixed_and_never_publish_raw_details(self):
        import contextlib
        import io
        from unittest.mock import patch
        secret = 'https://fixtureaccount.blob.core.windows.net/?sig=FIXTURE_SECRET'
        cases = [
            ('private_root', 'initialization', RuntimeError(secret)),
            ('read_metadata', 'metadata-validation', RuntimeError(secret)),
            ('invalid_metadata', 'metadata-validation', None),
            ('changed_metadata', 'metadata-validation', None),
            ('check_containers', 'container-preflight', RuntimeError(secret)),
            ('download_package', 'package-acquisition', RuntimeError(secret)),
            ('extract_package', 'package-acquisition', RuntimeError(secret)),
            ('run_engine', 'engine-execution', RuntimeError(secret)),
            ('engine_nonzero', 'engine-execution', None),
            ('read_stats', 'result-verification', RuntimeError(secret)),
            ('verify_result', 'result-verification', RuntimeError(secret)),
            ('publication', 'summary-publication', None),
            ('success', None, None),
        ]
        for target, stage, error in cases:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                m = load()
                root = Path(temp)
                summary = {'schema_version': 1, 'phase': 'producer', 'status': 'passed',
                           'artifact_bytes': 56, **{key: 'a' * 64 for key in m.DIGEST_FIELDS},
                           **dict.fromkeys(m.COUNTERS, 0)}
                defaults = {'private_root': root, 'read_metadata': metadata(),
                            'check_containers': 3, 'download_package': None,
                            'extract_package': None, 'run_engine': 0,
                            'read_stats': {}, 'verify_result': summary,
                            'read_regular': b'fixture'}
                public, diagnostic = io.StringIO(), io.StringIO()
                with contextlib.ExitStack() as stack:
                    mocks = {name: stack.enter_context(patch.object(m, name, return_value=value))
                             for name, value in defaults.items()}
                    if error is not None:
                        mocks[target].side_effect = error
                    elif target == 'invalid_metadata':
                        invalid = metadata()
                        invalid[0]['Shards'][0]['StorageUrl'] = secret
                        mocks['read_metadata'].return_value = invalid
                    elif target == 'engine_nonzero':
                        mocks['run_engine'].return_value = 17
                        # Missing stats must not mask the earlier engine failure.
                        mocks['read_stats'].side_effect = RuntimeError(secret)
                    elif target == 'changed_metadata':
                        changed = metadata()
                        changed[0]['Shards'][0]['Containers'][0]['Name'] = 'different-existing'
                        mocks['read_metadata'].side_effect = [metadata(), changed]
                    output = root / ('missing/output' if target == 'publication' else 'output')
                    stack.enter_context(patch.dict(os.environ, {
                        'GITHUB_RUN_ID': '400000001', 'GITHUB_RUN_ATTEMPT': '1',
                        'GITHUB_OUTPUT': str(output)}))
                    stack.enter_context(contextlib.redirect_stdout(public))
                    stack.enter_context(contextlib.redirect_stderr(diagnostic))
                    if target == 'success':
                        self.assertEqual(m.main(['producer']), 0)
                        m.validate_summary(json.loads(public.getvalue()))
                        self.assertEqual(diagnostic.getvalue(), '')
                        self.assertEqual(output.read_text(), ''.join(
                            key + '=' + summary[key] + '\n' for key in m.DIGEST_FIELDS))
                        continue
                    self.assertEqual(m.main(['producer']), 1)
                    self.assertEqual(json.loads(public.getvalue()),
                                     {'schema_version': 1, 'phase': 'producer', 'status': 'failed'})
                    self.assertEqual(diagnostic.getvalue(), 'failure-stage: ' + stage + '\n')
                    self.assertNotIn(secret, public.getvalue() + diagnostic.getvalue())
                    self.assertNotIn('FIXTURE_SECRET', public.getvalue() + diagnostic.getvalue())
                    self.assertFalse(output.exists())
                    if stage in ('initialization', 'metadata-validation', 'container-preflight',
                                 'package-acquisition'):
                        mocks['run_engine'].assert_not_called()
                    if target == 'engine_nonzero':
                        mocks['read_stats'].assert_not_called()
                        mocks['verify_result'].assert_not_called()

    def test_cli_errors_suppress_secrets_and_invalid_args_before_runtime_read(self):
        m = load()
        self.assertTrue(hasattr(m, 'main'), 'safe CLI entry point missing')
        import contextlib
        import io
        from unittest.mock import patch
        for args in ([], ['other'], ['producer', 'extra']):
            public = io.StringIO()
            with patch.object(m, 'read_metadata') as read, contextlib.redirect_stdout(public):
                self.assertEqual(m.main(args), 2)
                read.assert_not_called()
            self.assertNotIn('secret', public.getvalue())
        public, diagnostic = io.StringIO(), io.StringIO()
        with patch.object(m, 'private_root', side_effect=RuntimeError('FIXTURE_SECRET')), \
             patch.dict(os.environ, {'GITHUB_RUN_ID': '400000001', 'GITHUB_RUN_ATTEMPT': '1'}), \
             contextlib.redirect_stdout(public), contextlib.redirect_stderr(diagnostic):
            self.assertEqual(m.main(['producer']), 1)
        self.assertEqual(json.loads(public.getvalue()), {'schema_version': 1, 'phase': 'producer', 'status': 'failed'})
        self.assertEqual(diagnostic.getvalue(), 'failure-stage: initialization\n')


if __name__ == '__main__':
    unittest.main()
