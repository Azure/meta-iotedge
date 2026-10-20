'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const script = path.join(__dirname, '../scripts/publish-release.cjs');
function implementation() { assert.ok(fs.existsSync(script), 'publisher implementation missing'); return require(script); }

test('release workflow gates builds on tag preflight and consumes complete collector output via pinned first-party publisher', () => {
  const workflow = fs.readFileSync(path.join(__dirname, '../.github/workflows/release.yml'), 'utf8');
  assert.match(workflow, /preflight:\n/);
  assert.match(workflow, /needs: preflight/);
  assert.match(workflow, /ref: \$\{\{ needs.preflight.outputs.commit \}\}/);
  assert.match(workflow, /release_tag: \$\{\{ needs.preflight.outputs.tag \}\}/);
  assert.match(workflow, /collect-release-artifacts.py/);
  assert.doesNotMatch(workflow, /softprops\//);
  assert.match(workflow, /actions\/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3/);
  assert.match(workflow, /publishRelease\(/);
  assert.doesNotMatch(workflow, /VERSION="\$\{\{/);
  assert.match(workflow, /test-only|test image.*blank|blank.*password/i);
});

test('devcontainer uses password-stdin Docker CLI with both tags and registry/inline cache, never unpinned actions', () => {
  const workflow = fs.readFileSync(path.join(__dirname, '../.github/workflows/build-devcontainer.yml'), 'utf8');
  assert.doesNotMatch(workflow, /uses: docker\//);
  assert.match(workflow, /docker login ghcr.io --username "\$REGISTRY_USER" --password-stdin/);
  assert.match(workflow, /docker buildx build/);
  assert.match(workflow, /--tag "\$IMAGE:latest"/);
  assert.match(workflow, /--tag "\$IMAGE:scarthgap"/);
  assert.match(workflow, /--cache-from "type=registry,ref=\$IMAGE:latest"/);
  assert.match(workflow, /--cache-to type=inline/);
  assert.match(workflow, /docker logout ghcr.io/);
  assert.doesNotMatch(workflow, /set -x|--password /);
});

test('workflow shell blocks parse and devcontainer CLI executes with a fake Docker without leaking its token', () => {
  const scripts = ['release.yml', 'build-devcontainer.yml'].map(name => {
    const workflow = fs.readFileSync(path.join(__dirname, '../.github/workflows', name), 'utf8');
    return [...workflow.matchAll(/^        run: \|\n((?:          .*\n|\n)*)/gm)].map(match => match[1].replace(/^          /gm, ''));
  });
  assert.ok(scripts[0].length >= 2 && scripts[1].length === 4);
  for (const blocks of scripts) for (const block of blocks) execFileSync('bash', ['-n'], {input: block});
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'fake-docker-'));
  try {
    const docker = path.join(dir, 'docker');
    fs.writeFileSync(docker, '#!/usr/bin/env node\nconst fs = require("node:fs"); fs.appendFileSync(process.env.DOCKER_LOG, JSON.stringify(process.argv.slice(2))+"\\n"); if(process.argv[2] === "login") { const input = fs.readFileSync(0,"utf8"); if(input !== "fixture-secret") process.exit(2); }\n', {mode: 0o755});
    const log = path.join(dir, 'calls');
    const env = {...process.env, PATH: `${dir}:${process.env.PATH}`, DOCKER_LOG: log, REGISTRY_TOKEN: 'fixture-secret', REGISTRY_USER: 'tester', BUILDER: 'fixture-builder', GITHUB_REPOSITORY_OWNER: 'MiXeD'};
    for (const block of scripts[1]) {
      const output = execFileSync('bash', ['-e', '-c', block], {env, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe']});
      assert.ok(!output.includes('fixture-secret'));
    }
    const calls = fs.readFileSync(log, 'utf8').trim().split('\n').map(line => JSON.parse(line));
    const build = calls.find(args => args[0] === 'buildx' && args[1] === 'build');
    assert.ok(build.includes('ghcr.io/mixed/meta-iotedge-devcontainer:latest'));
    assert.ok(build.includes('ghcr.io/mixed/meta-iotedge-devcontainer:scarthgap'));
    assert.ok(!fs.readFileSync(log, 'utf8').includes('fixture-secret'));
    assert.ok(calls.some(args => args[0] === 'logout'));
  } finally { fs.rmSync(dir, {recursive: true, force: true}); }
});

test('supported release grammar maps all three lines without accepting executable input', () => {
  const {parseTag} = implementation();
  for (const [tag, template, prerelease] of [
    ['1.5.35', 'scarthgap', false], ['1.5.35-1', 'scarthgap', false],
    ['1.6.4', 'wrynose', false], ['1.6.0-rc.1', 'wrynose', true],
    ['1.6.4-scarthgap', 'scarthgap-1.6', false],
    ['1.6.4-scarthgap.2', 'scarthgap-1.6', false],
    ['1.6.4-beta.2-scarthgap', 'scarthgap-1.6', true],
  ]) {
    assert.equal(parseTag(tag).template, template);
    assert.equal(parseTag(tag).prerelease, prerelease);
  }
  for (const tag of ['v1.6.4', '1.7.0', '1.5.35-scarthgap', '1.6.04', '1.6.4-rc', '1.6.4;echo bad', '1.6.4\n', '../1.6.4']) {
    assert.throws(() => parseTag(tag), /Unsupported release tag/);
  }
});


test('Latest never moves to an older stable release or compatibility/prerelease line', () => {
  const {releasePolicy} = implementation();
  assert.equal(typeof releasePolicy, 'function', 'release policy missing');
  const release = (tag_name, more = {}) => ({tag_name, draft: false, prerelease: false, ...more});
  const cases = [
    ['1.5.35', [], 'true'], ['1.5.35', [release('1.5.36')], 'false'],
    ['1.5.40', [release('1.6.0')], 'false'],
    ['1.6.4', [release('1.6.5')], 'false'], ['1.6.4', [release('1.6.3')], 'true'],
    ['1.6.4', [release('1.6.4')], 'true'],
    ['1.6.4-rc.1', [], 'false'], ['1.6.4-scarthgap', [], 'false'],
    ['1.6.4', [release('1.6.5', {draft: true})], 'true'],
  ];
  for (const [tag, releases, expected] of cases) assert.equal(releasePolicy(tag, releases).make_latest, expected, tag);
});

const requiredBuildTools = [
  'scripts/check-recipe-consistency.py', 'scripts/release_versions.py',
  'scripts/verify-release-selection.py', 'scripts/collect-release-artifacts.py',
  'tests/test_release_versions.py', 'tests/test_verify_release_selection.py',
  'tests/test_collect_release_artifacts.py', 'tests/test_publish_release.cjs',
  'scripts/publish-release.cjs',
];

test('preflight rejects historical source commits even when current checkout has tooling', () => {
  const {preflight} = implementation();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'historical-release-'));
  const git = (...args) => execFileSync('git', args, {cwd: dir, encoding: 'utf8'}).trim();
  try {
    git('init', '-q'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.invalid');
    git('commit', '--allow-empty', '-qm', 'historical source');
    git('tag', '1.5.35'); git('tag', '1.6.0');
    for (const file of requiredBuildTools) {
      fs.mkdirSync(path.dirname(path.join(dir, file)), {recursive: true});
      fs.writeFileSync(path.join(dir, file), 'fixture tooling\n');
    }
    git('add', '.'); git('commit', '-qm', 'supported tooling');
    git('tag', '1.6.4');
    assert.equal(preflight('1.6.4', {cwd: dir}).commit, git('rev-parse', 'HEAD'));
    for (const tag of ['1.5.35', '1.6.0']) {
      assert.throws(() => preflight(tag, {cwd: dir}), /Unsupported release source.*missing required build tooling.*scripts\/check-recipe-consistency.py/i);
    }
    // Every required file is checked at the tag, not just the first helper.
    for (const file of requiredBuildTools) {
      fs.unlinkSync(path.join(dir, file)); git('add', '-u'); git('commit', '-qm', 'missing tool');
      git('tag', '-f', '1.6.4');
      assert.throws(() => preflight('1.6.4', {cwd: dir}), error => error.message.includes(file));
      git('reset', '--hard', 'HEAD~1');
    }
  } finally { fs.rmSync(dir, {recursive: true, force: true}); }
});

test('preflight requires an existing exact tag commit and selects strictly older same-line ancestor', () => {
  const {preflight} = implementation();
  assert.equal(typeof preflight, 'function', 'preflight implementation missing');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'release-git-'));
  const git = (...args) => execFileSync('git', args, {cwd: dir, encoding: 'utf8'}).trim();
  try {
    git('init', '-q'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.invalid');
    for (const file of requiredBuildTools) {
      fs.mkdirSync(path.dirname(path.join(dir, file)), {recursive: true});
      fs.writeFileSync(path.join(dir, file), 'fixture tooling\n');
    }
    git('add', '.'); git('commit', '-qm', 'fixture');
    for (const tag of ['1.6.2', '1.6.3', '1.6.4', '1.6.5', '1.6.4-scarthgap', '1.5.35']) git('tag', tag);
    const result = preflight('1.6.4', {cwd: dir});
    assert.equal(result.previous_tag, '1.6.3');
    assert.equal(result.commit, git('rev-parse', 'HEAD'));
    assert.throws(() => preflight('1.6.9', {cwd: dir}), /existing tag/);
    assert.throws(() => preflight('1.6.4;bad', {cwd: dir}), /Unsupported release tag/);
  } finally { fs.rmSync(dir, {recursive: true, force: true}); }
});

function apiFixture(initial = null, options = {}) {
  let release = initial && {...initial};
  let assets = (initial?.assets || []).map(a => ({...a}));
  let nextAssetId = 20;
  const calls = [];
  const rest = {repos: {}, git: {
    getRef: async args => {
      calls.push({name: 'getRef', args});
      if (options.missingTag) throw Object.assign(new Error('missing remote tag'), {status: 404});
      return {data: {object: {type: 'commit', sha: options.tagCommit || 'a'.repeat(40)}}};
    },
    getTag: async () => { throw new Error('unexpected annotated tag lookup'); },
  }};
  for (const name of ['getReleaseByTag', 'createRelease', 'updateRelease', 'getRelease', 'listReleases', 'generateReleaseNotes', 'listReleaseAssets', 'uploadReleaseAsset', 'deleteReleaseAsset', 'getReleaseAsset']) {
    rest.repos[name] = async args => {
      calls.push({name, args});
      if (options.fail === name) throw Object.assign(new Error('injected API failure'), {status: options.status || 500});
      switch (name) {
        case 'getReleaseByTag': if (!release) throw Object.assign(new Error('not found'), {status: 404}); return {data: {...release}};
        case 'createRelease': release = {...args, id: 9, upload_url: 'https://uploads.invalid/{?name,label}', immutable: false}; return {data: {...release}};
        case 'updateRelease': Object.assign(release, args); return {data: {...release}};
        case 'getRelease': return {data: {...release}};
        case 'listReleases': return {data: options.releases || []};
        case 'generateReleaseNotes': return {data: {body: 'Generated changes'}};
        case 'listReleaseAssets': return {data: assets.map(a => ({...a}))};
        case 'deleteReleaseAsset': assets = assets.filter(a => a.id !== args.asset_id); return {};
        case 'uploadReleaseAsset': {
          const data = Buffer.from(args.data);
          const a = {id: nextAssetId++, name: args.name, size: data.length, state: 'uploaded', bytes: data};
          assets.push(a); return {data: a};
        }
        case 'getReleaseAsset': return {data: assets.find(a => a.id === args.asset_id).bytes};
      }
    };
  }
  return {rest, calls, paginate: async (method, args) => (await method(args)).data, current: () => release};
}

async function publishingFixture(run, initial = null, options = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'release-assets-'));
  const github = apiFixture(initial, options);
  try {
    for (const name of ['iotedge-rpms-1.6.4.tar.gz', 'iotedge-qemu-image-qemux86-64.rootfs.ext4.zst', 'bzImage']) fs.writeFileSync(path.join(dir, name), `fixture ${name}`);
    const params = {github, owner: 'owner', repo: 'repo', tag: '1.6.4', previousTag: '1.6.3', commit: 'a'.repeat(40), artifactDir: dir, customNotes: 'Custom line notes'};
    await run(params, github);
  } finally { fs.rmSync(dir, {recursive: true, force: true}); }
}

test('publisher refuses nonexistent or moved remote tags before writing release state', async () => {
  const {publishRelease} = implementation();
  for (const options of [{missingTag: true}, {tagCommit: 'b'.repeat(40)}]) await publishingFixture(async (params, github) => {
    await assert.rejects(publishRelease(params), /tag|commit/i);
    assert.ok(!github.calls.some(c => ['createRelease', 'updateRelease'].includes(c.name)));
  }, null, options);
});

test('publisher rejects nonolder or cross-line previous tags', async () => {
  const {publishRelease} = implementation();
  for (const previousTag of ['1.6.4', '1.6.5', '1.6.3-scarthgap', '1.5.35']) await publishingFixture(async (params, github) => {
    await assert.rejects(publishRelease({...params, previousTag}), /previous tag/i);
    assert.equal(github.calls.length, 0);
  });
});

test('publisher caps aggregate local assets at 512 MiB before buffering or API calls', async () => {
  const {publishRelease} = implementation();
  const limit = 512 * 1024 * 1024;
  for (const extra of [1, 0]) await publishingFixture(async (params, github) => {
    const archive = path.join(params.artifactDir, 'iotedge-rpms-1.6.4.tar.gz');
    const image = path.join(params.artifactDir, 'iotedge-qemu-image-qemux86-64.rootfs.ext4.zst');
    const kernel = path.join(params.artifactDir, 'bzImage');
    fs.truncateSync(archive, limit / 2);
    fs.truncateSync(image, limit / 2 - fs.statSync(kernel).size + extra);
    const read = fs.readFileSync;
    let assetReads = 0;
    fs.readFileSync = function(file, ...args) {
      if (path.dirname(String(file)) === params.artifactDir) {
        assetReads++;
        throw new Error('reached allowed asset read');
      }
      return read.call(this, file, ...args);
    };
    try {
      await assert.rejects(publishRelease(params), extra ? /aggregate.*512 MiB/i : /reached allowed asset read/);
      assert.equal(assetReads, extra ? 0 : 1);
      assert.equal(github.calls.length, 0);
    } finally { fs.readFileSync = read; }
  });
});

test('empty or missing local asset fails before any API call', async () => {
  const {publishRelease} = implementation();
  for (const mode of ['empty', 'missing']) await publishingFixture(async (params, github) => {
    const file = path.join(params.artifactDir, 'bzImage');
    if (mode === 'empty') fs.writeFileSync(file, ''); else fs.unlinkSync(file);
    await assert.rejects(publishRelease(params), /nonempty.*bzImage/i);
    assert.equal(github.calls.length, 0);
  });
});

test('immutable published rerun accepts identical verified assets without writes and rejects changed bytes', async () => {
  const {publishRelease} = implementation();
  await publishingFixture(async (params, github) => {
    await publishRelease(params);
    github.current().immutable = true;
    github.calls.length = 0;
    await publishRelease(params);
    assert.ok(!github.calls.some(c => ['createRelease', 'updateRelease', 'deleteReleaseAsset', 'uploadReleaseAsset'].includes(c.name)));
    fs.writeFileSync(path.join(params.artifactDir, 'bzImage'), 'changed');
    await assert.rejects(publishRelease(params), /[Ii]mmutable/);
  });
});

test('mutable reruns replace owned assets without accumulating notes or deleting unrelated assets', async () => {
  const {publishRelease} = implementation();
  const initial = {id: 9, draft: false, immutable: false, upload_url: 'https://uploads.invalid/{?name,label}', assets: [{id: 2, name: 'bzImage', size: 1, state: 'uploaded', bytes: Buffer.from('x')}, {id: 3, name: 'unrelated.txt', size: 1, bytes: Buffer.from('x')}]};
  await publishingFixture(async (params, github) => {
    await publishRelease(params);
    await publishRelease(params);
    assert.equal(github.calls.filter(c => c.name === 'createRelease').length, 0);
    assert.equal(github.current().body, 'Custom line notes\n\nGenerated changes');
    assert.ok(!github.calls.some(c => c.name === 'deleteReleaseAsset' && c.args.asset_id === 3));
    const firstWrite = github.calls.find(c => ['updateRelease', 'uploadReleaseAsset', 'deleteReleaseAsset'].includes(c.name));
    assert.equal(firstWrite.name, 'updateRelease'); assert.equal(firstWrite.args.draft, true);
  }, initial);
});

test('refuses asset replacement if API did not actually put a mutable release into draft', async () => {
  const {publishRelease} = implementation();
  await publishingFixture(async (params, github) => {
    github.rest.repos.updateRelease = async args => ({data: {...github.current(), ...args}});
    await assert.rejects(publishRelease(params), /draft/i);
    assert.ok(!github.calls.some(c => ['deleteReleaseAsset', 'uploadReleaseAsset'].includes(c.name)));
  }, {id: 9, draft: false, immutable: false, upload_url: 'https://uploads.invalid/'});
});

test('API lookup errors never become absence and partial upload/verification failures leave a draft', async () => {
  const {publishRelease} = implementation();
  for (const [fail, status] of [['getReleaseByTag', 403], ['getReleaseByTag', 500], ['uploadReleaseAsset', 502], ['getReleaseAsset', 500], ['generateReleaseNotes', 500]]) {
    await publishingFixture(async (params, github) => {
      await assert.rejects(publishRelease(params), /injected API failure/);
      assert.ok(!github.calls.some(c => c.name === 'updateRelease' && c.args.draft === false));
      if (fail === 'getReleaseByTag') assert.ok(!github.calls.some(c => c.name === 'createRelease'));
      if (github.current()) assert.equal(github.current().draft, true);
    }, null, {fail, status});
  }
});

test('corrupted remote bytes or wrong uploaded size never publish a draft', async () => {
  const {publishRelease} = implementation();
  for (const mode of ['bytes', 'size', 'missing']) await publishingFixture(async (params, github) => {
    const original = github.rest.repos.listReleaseAssets;
    github.rest.repos.listReleaseAssets = async args => {
      const response = await original(args);
      if (mode === 'size') response.data = response.data.map(a => ({...a, size: a.size + 1}));
      if (mode === 'missing') response.data = response.data.filter(a => a.name !== 'bzImage');
      return response;
    };
    if (mode === 'bytes') github.rest.repos.getReleaseAsset = async () => ({data: Buffer.from('corrupt')});
    await assert.rejects(publishRelease(params), /asset|checksum/i);
    assert.ok(!github.calls.some(c => c.name === 'updateRelease' && c.args.draft === false));
  });
});

test('new release is a draft until complete uploaded assets are verified and final metadata is read back', async () => {
  const {publishRelease} = implementation();
  assert.equal(typeof publishRelease, 'function', 'publication implementation missing');
  await publishingFixture(async (params, github) => {
    const result = await publishRelease(params);
    assert.equal(result.draft, false);
    const create = github.calls.find(c => c.name === 'createRelease').args;
    assert.equal(create.draft, true); assert.equal(create.prerelease, false); assert.equal(create.make_latest, 'false');
    assert.equal(create.body, 'Custom line notes\n\nGenerated changes');
    const generate = github.calls.find(c => c.name === 'generateReleaseNotes').args;
    assert.equal(generate.previous_tag_name, '1.6.3');
    const publishIndex = github.calls.findIndex(c => c.name === 'updateRelease' && c.args.draft === false);
    assert.equal(github.calls.filter(c => c.name === 'uploadReleaseAsset').length, 3);
    assert.equal(github.calls.filter(c => c.name === 'getReleaseAsset').length, 6);
    assert.ok(github.calls.slice(0, publishIndex).filter(c => c.name === 'getReleaseAsset').length >= 3);
    const final = github.calls[publishIndex].args;
    assert.equal(final.make_latest, 'true'); assert.equal(final.prerelease, false);
    assert.ok(github.calls.slice(publishIndex + 1).some(c => c.name === 'getRelease'));
  });
});
