'use strict';
// Invoked by the pinned first-party github-script action; no token handling here.
function parseTag(tag) {
  const n = '(0|[1-9][0-9]*)';
  const pattern = new RegExp(`^1\\.([56])\\.${n}(?:-(beta|rc)\\.${n})?(?:-([1-9][0-9]*))?(?:-(scarthgap)(?:\\.([1-9][0-9]*))?)?$`);
  const m = typeof tag === 'string' && pattern.exec(tag);
  if (!m || m[0] !== tag || (m[6] && m[1] !== '6') || (m[5] && m[6])) {
    throw new Error(`Unsupported release tag: ${JSON.stringify(tag)}`);
  }
  const template = m[6] ? 'scarthgap-1.6' : m[1] === '6' ? 'wrynose' : 'scarthgap';
  return {tag, template, series: `1.${m[1]}`, yocto: template === 'wrynose' ? 'Wrynose' : 'Scarthgap', prerelease: Boolean(m[3]),
    order: [Number(m[1]), Number(m[2]), m[3] === 'beta' ? 0 : m[3] === 'rc' ? 1 : 2, Number(m[4] || 0), Number(m[5] || m[7] || 0)]};
}

function compare(a, b) {
  for (let i = 0; i < a.order.length; i++) {
    if (a.order[i] !== b.order[i]) return a.order[i] < b.order[i] ? -1 : 1;
  }
  return 0;
}

function preflight(tag, {cwd = process.cwd()} = {}) {
  const info = parseTag(tag);
  const git = (...args) => require('node:child_process').execFileSync('git', args, {cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe']}).trim();
  let commit;
  try { commit = git('rev-parse', '--verify', `refs/tags/${tag}^{commit}`); }
  catch { throw new Error(`Release requires an existing tag pointing to a commit: ${tag}`); }
  // Reusable CI checks out this exact source commit, without a tooling overlay.
  // Historical tags predating these helpers cannot use the current build contract.
  const required = [
    'scripts/check-recipe-consistency.py', 'scripts/release_versions.py',
    'scripts/verify-release-selection.py', 'scripts/collect-release-artifacts.py',
    'tests/test_release_versions.py', 'tests/test_verify_release_selection.py',
    'tests/test_collect_release_artifacts.py', 'tests/test_publish_release.cjs',
    'scripts/publish-release.cjs',
  ];
  const missing = required.filter(file => {
    try { return git('cat-file', '-t', `${commit}:${file}`) !== 'blob'; }
    catch { return true; }
  });
  if (missing.length) throw new Error(`Unsupported release source ${tag} (${commit}): missing required build tooling: ${missing.join(', ')}. Historical tags without this tooling cannot be rebuilt by this workflow.`);
  const candidates = git('tag', '--list', '--merged', commit).split('\n').flatMap(candidate => {
    try { const parsed = parseTag(candidate); return parsed.template === info.template && compare(parsed, info) < 0 ? [parsed] : []; }
    catch { return []; }
  }).sort(compare);
  return {...info, commit, previous_tag: candidates.at(-1)?.tag || ''};
}

function releasePolicy(tag, releases) {
  const info = parseTag(tag);
  const stable = releases.filter(r => !r.draft && !r.prerelease).flatMap(r => {
    try { const parsed = parseTag(r.tag_name); return !parsed.prerelease && parsed.template !== 'scarthgap-1.6' ? [parsed] : []; }
    catch { return []; }
  });
  const make_latest = !info.prerelease && info.template !== 'scarthgap-1.6' && !stable.some(r => compare(r, info) > 0) ? 'true' : 'false';
  return {...info, make_latest, has_stable_16: stable.some(r => r.series === '1.6') || (info.series === '1.6' && !info.prerelease && info.template === 'wrynose')};
}

async function publishRelease({github, owner, repo, tag, previousTag = '', commit, artifactDir, customNotes}) {
  const fs = require('node:fs');
  const path = require('node:path');
  const hash = data => require('node:crypto').createHash('sha256').update(data).digest('hex');
  const common = {owner, repo};
  const info = parseTag(tag);
  if (previousTag) {
    const previous = parseTag(previousTag);
    if (previous.template !== info.template || compare(previous, info) >= 0) throw new Error('Previous tag must be strictly older on the same release line');
  }
  if (!/^[0-9a-f]{40}$/.test(commit)) throw new Error('Expected resolved tag commit SHA');
  const expected = [`iotedge-rpms-${tag}.tar.gz`, 'iotedge-qemu-image-qemux86-64.rootfs.ext4.zst', 'bzImage'].map(name => {
    const file = path.join(artifactDir, name);
    if (!fs.existsSync(file) || !fs.statSync(file).isFile() || fs.statSync(file).size === 0) throw new Error(`Require nonempty local asset: ${name}`);
    return {name, file, size: fs.statSync(file).size};
  });
  // Octokit's authenticated asset endpoints buffer responses. Keep this path
  // conservative: larger releases are blocked until authenticated streaming is
  // implemented, not silently accepted with unbounded runner memory usage.
  const maxAggregateBytes = 512 * 1024 * 1024;
  if (expected.reduce((total, asset) => total + asset.size, 0) > maxAggregateBytes) {
    throw new Error('Release aggregate asset size exceeds 512 MiB; larger releases require a streaming publisher');
  }
  for (const asset of expected) asset.sha256 = hash(fs.readFileSync(asset.file));
  // Verify the remote ref too: createRelease otherwise silently creates missing tags.
  const ref = (await github.rest.git.getRef({...common, ref: `tags/${tag}`})).data;
  let object = ref.object;
  for (let depth = 0; object.type === 'tag' && depth < 10; depth++) {
    object = (await github.rest.git.getTag({...common, tag_sha: object.sha})).data.object;
  }
  if (object.type !== 'commit' || object.sha !== commit) throw new Error('Release tag no longer matches the validated build commit');
  const releases = await github.paginate(github.rest.repos.listReleases, {...common, per_page: 100});
  const policy = releasePolicy(tag, releases);
  const generated = await github.rest.repos.generateReleaseNotes({...common, tag_name: tag, target_commitish: commit, ...(previousTag ? {previous_tag_name: previousTag} : {})});
  const metadata = {name: `IoT Edge Yocto Layer ${tag} (${info.yocto} / ${info.series}.x)`, body: `${customNotes.trim()}\n\n${generated.data.body.trim()}`, prerelease: info.prerelease};
  let release;
  try { release = (await github.rest.repos.getReleaseByTag({...common, tag})).data; }
  catch (error) { if (error.status !== 404) throw error; }
  if (release?.immutable && !release.draft) {
    try { await verify(); }
    catch (error) { throw new Error(`Immutable release ${tag} cannot replace assets: ${error.message}`); }
    return (await github.rest.repos.getRelease({...common, release_id: release.id})).data;
  }
  if (release) {
    await github.rest.repos.updateRelease({...common, release_id: release.id, ...metadata, draft: true, make_latest: 'false'});
  } else {
    release = (await github.rest.repos.createRelease({...common, tag_name: tag, target_commitish: commit, ...metadata, draft: true, make_latest: 'false'})).data;
  }
  const draft = (await github.rest.repos.getRelease({...common, release_id: release.id})).data;
  if (draft.draft !== true || draft.immutable) throw new Error('Release must be a verified mutable draft before changing assets');
  const oldAssets = await github.paginate(github.rest.repos.listReleaseAssets, {...common, release_id: release.id, per_page: 100});
  for (const asset of expected) {
    for (const old of oldAssets.filter(a => a.name === asset.name)) {
      await github.rest.repos.deleteReleaseAsset({...common, asset_id: old.id});
    }
    const data = fs.readFileSync(asset.file);
    await github.rest.repos.uploadReleaseAsset({...common, release_id: release.id, url: release.upload_url, name: asset.name, data, headers: {'content-type': 'application/octet-stream', 'content-length': data.length}});
  }
  async function verify() {
    const assets = await github.paginate(github.rest.repos.listReleaseAssets, {...common, release_id: release.id, per_page: 100});
    for (const local of expected) {
      const matches = assets.filter(a => a.name === local.name);
      if (matches.length !== 1 || matches[0].size !== local.size || matches[0].state !== 'uploaded') throw new Error(`Incomplete release asset: ${local.name}`);
      // Download and hash one file at a time; do not retain response bodies.
      const remote = await github.rest.repos.getReleaseAsset({...common, asset_id: matches[0].id, headers: {accept: 'application/octet-stream'}});
      if (hash(Buffer.isBuffer(remote.data) ? remote.data : Buffer.from(remote.data)) !== local.sha256) throw new Error(`Release asset checksum mismatch: ${local.name}`);
    }
  }
  await verify();
  await github.rest.repos.updateRelease({...common, release_id: release.id, ...metadata, draft: false, make_latest: policy.make_latest});
  const published = (await github.rest.repos.getRelease({...common, release_id: release.id})).data;
  if (published.draft || published.prerelease !== metadata.prerelease || published.body !== metadata.body || published.name !== metadata.name) throw new Error('Published release metadata verification failed');
  await verify();
  return published;
}

module.exports = {parseTag, preflight, releasePolicy, publishRelease};
