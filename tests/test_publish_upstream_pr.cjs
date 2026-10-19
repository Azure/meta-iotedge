'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const helper = '../scripts/publish-upstream-pr.cjs';
function git(cwd, ...args) { return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim(); }
function fixture(t) {
  const dir = fs.mkdtempSync(path.join(process.env.TMPDIR || os.tmpdir(), 'watcher-test-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const remote = path.join(dir, 'origin.git'), cwd = path.join(dir, 'checkout');
  git(dir, 'init', '--bare', remote); git(dir, 'clone', remote, cwd);
  git(cwd, 'config', 'user.name', 'Fixture'); git(cwd, 'config', 'user.email', 'fixture@example.invalid');
  git(cwd, 'checkout', '-b', 'main');
  fs.mkdirSync(path.join(cwd, 'recipes-core'), { recursive: true });
  fs.writeFileSync(path.join(cwd, 'recipes-core', 'old.inc'), 'base\n');
  fs.writeFileSync(path.join(cwd, 'README'), 'base\n');
  git(cwd, 'add', '.'); git(cwd, 'commit', '-m', 'base'); git(cwd, 'push', 'origin', 'main');
  return { cwd, remote };
}
const plans = () => ['1.5', '1.6'].map(line => ({ line, release_version: `${line}.45`, daemon_version: `${line}.21`, iis_version: `${line}.6`, template: line === '1.5' ? 'scarthgap' : 'wrynose', update_type: 'significant', needs_update: true, current_release: `${line}.0` }));
function api() {
  const prs = [], labels = [], calls = [];
  const github = { rest: {
    repos: { get: async () => ({ data: { default_branch: 'main' } }) },
    pulls: {
      list: async args => { calls.push(['list', args]); return { data: prs }; },
      create: async args => { calls.push(['create', args]); const pr = { ...args, number: prs.length + 1, state: 'open', head: { ref: args.head, repo: { full_name: 'owner/repo' } }, base: { ref: args.base }, labels: [] }; prs.push(pr); return { data: pr }; },
      get: async ({ pull_number }) => ({ data: prs.find(p => p.number === pull_number) }),
      update: async args => { calls.push(['update', args]); Object.assign(prs.find(p => p.number === args.pull_number), args); return { data: prs.find(p => p.number === args.pull_number) }; }
    },
    issues: {
      listLabelsForRepo: async () => ({ data: labels }),
      createLabel: async args => { labels.push({ name: args.name }); return { data: args }; },
      addLabels: async args => { calls.push(['labels', args]); prs.find(p => p.number === args.issue_number).labels.push(...args.labels.map(name => ({ name }))); return { data: [] }; }
    }
  }, paginate: async (method, args) => (await method({ ...args, per_page: 100 })).data };
  return { github, prs, labels, calls };
}
const context = { repo: { owner: 'owner', repo: 'repo' } };
const ref = 'refs/heads/automation/upstream-update';
test('rejects incomplete, duplicate or hostile plans before git or API side effects', async () => {
  const { publish } = require(helper);
  for (const bad of [plans().slice(0, 1), [...plans(), plans()[0]], plans().map(p => ({ ...p, release_version: '1.6.1; touch /x' })), plans().map(p => ({ ...p, needs_update: 'false' }))]) {
    await assert.rejects(publish({ github: {}, context, plans: bad, cwd: '/not-a-repo' }), /Invalid upstream plans/);
  }
});
test('reconciles a duplicate-create race by exact owner head and base', async t => {
  const f = fixture(t), a = api();
  const create = a.github.rest.pulls.create;
  a.github.rest.pulls.create = async args => { await create(args); throw Object.assign(new Error('already exists'), { status: 422 }); };
  await require(helper).publish({ ...f, ...a, context, plans: plans(), generate });
  assert.equal(a.prs.length, 1);
});
test('Docker notifications paginate all states and honor exact closed acknowledgement without title substring matches', async () => {
  const { notify } = require('../scripts/notify-upstream.cjs');
  const a = api(), created = [], queries = [];
  const dockerPlans = plans().map(p => ({ ...p, needs_update: false, update_type: 'docker-only' }));
  a.github.rest.issues.listForRepo = async args => { queries.push(args); return { data: args.page === 1 ? [{ title: '1.5.450', body: '<!-- meta-iotedge:docker-only:1.5:1.5.450 -->' }] : [{ state: 'closed', body: '<!-- meta-iotedge:docker-only:1.5:1.5.45 -->' }] }; };
  a.github.paginate = async (method, args) => [...(await method({ ...args, page: 1 })).data, ...(await method({ ...args, page: 2 })).data];
  a.github.rest.issues.create = async args => { created.push({ ...args, number: 9 }); return { data: created.at(-1) }; };
  a.github.rest.issues.get = async () => ({ data: created.at(-1) });
  await notify({ ...a, context, plans: dockerPlans });
  assert.equal(created.length, 1); assert.match(created[0].body, /<!-- meta-iotedge:docker-only:1.6:1.6.45 -->/);
  assert.ok(queries.every(q => q.state === 'all' && q.per_page === 100));
  assert.deepEqual(created[0].labels, ['docker-only-update', 'no-action-needed']);
});
test('Docker notifications deduplicate exact legacy acknowledgements and markers only', async t => {
  const { notify } = require('../scripts/notify-upstream.cjs');
  const title = 'IoT Edge 1.5.45 released (Docker images only)';
  const field = '**Latest Release:** 1.5.45';
  const marker = '<!-- meta-iotedge:docker-only:1.5:1.5.45 -->';
  const legacy = { title, body: `Legacy notification\n\n${field}\n**Daemon Version:** 1.5.21 (unchanged)` };
  const cases = [
    ...['open', 'closed'].flatMap(state => [
      { name: `${state} legacy LF`, issue: { ...legacy, state }, acknowledged: true },
      { name: `${state} legacy CRLF`, issue: { ...legacy, state, body: legacy.body.replace(/\n/g, '\r\n') }, acknowledged: true },
      { name: `${state} exact marker`, issue: { state, body: marker }, acknowledged: true }
    ]),
    { name: 'legacy pull request', issue: { ...legacy, pull_request: {} } },
    { name: 'marked pull request', issue: { ...legacy, body: marker, pull_request: {} } },
    { name: 'different title release', issue: { ...legacy, title: title.replace('1.5.45', '1.5.450') } },
    { name: 'title prefix', issue: { ...legacy, title: `prefix ${title}` } },
    { name: 'title suffix', issue: { ...legacy, title: `${title} suffix` } },
    { name: 'different field release', issue: { ...legacy, body: field.replace('1.5.45', '1.5.450') } },
    { name: 'field prefix', issue: { ...legacy, body: `prefix ${field}` } },
    { name: 'field suffix', issue: { ...legacy, body: `${field} suffix` } },
    { name: 'missing field', issue: { ...legacy, body: null } },
    { name: 'different marker release', issue: { body: marker.replace('1.5.45', '1.5.450') } },
    { name: 'different marker line', issue: { body: marker.replace('docker-only:1.5:', 'docker-only:1.6:') } },
    { name: 'marker prefix', issue: { body: `prefix ${marker}` } },
    { name: 'marker suffix', issue: { body: `${marker} suffix` } }
  ];
  for (const { name, issue, acknowledged = false } of cases) await t.test(name, async () => {
    const a = api(), created = [];
    a.github.rest.issues.listForRepo = async args => {
      assert.equal(args.state, 'all');
      assert.equal(args.per_page, 100);
      assert.equal(args.labels, undefined);
      return { data: [issue] };
    };
    a.github.rest.issues.create = async args => { created.push({ ...args, number: 9 }); return { data: created.at(-1) }; };
    a.github.rest.issues.get = async () => ({ data: created.at(-1) });
    const dockerPlans = plans().map((p, i) => ({ ...p, needs_update: false, update_type: i === 0 ? 'docker-only' : 'none' }));
    await notify({ ...a, context, plans: dockerPlans });
    assert.equal(created.length, acknowledged ? 0 : 1);
  });
});
test('workflow uses pinned first-party publication with unconditional housekeeping, explicit permissions, serialized list plans and env inputs', () => {
  const source = fs.readFileSync(path.join(__dirname, '../.github/workflows/watch-upstream.yml'), 'utf8');
  assert.doesNotMatch(source, /peter-evans|\bgh pr\b/);
  assert.match(source, /cancel-in-progress: false/);
  assert.match(source, /--plans-json/);
  assert.match(source, /packages: read/); assert.match(source, /issues: write/);
  assert.match(source, /PLANS_JSON:/);
  assert.match(source, /require\('\.\/scripts\/publish-upstream-pr\.cjs'\)/);
  assert.doesNotMatch(source, /if:.*needs_update/);
  for (const [, script] of source.matchAll(/^ {10}script: \|\n((?: {12}.*\n)*)/gm)) assert.doesNotMatch(script, /\$\{\{/);
});
test('stale detection snapshot fails before generation instead of overwriting a newer base', async t => {
  const f = fixture(t), a = api();
  await assert.rejects(require(helper).publish({ ...f, ...a, context, plans: plans(), expectedBase: '0'.repeat(40), generate: () => assert.fail('stale generation') }), /Default branch changed/);
});
test('disabled PR creation reports the separate administrator setting', async t => {
  const f = fixture(t), a = api();
  a.github.rest.pulls.create = async () => { throw Object.assign(new Error('Resource not accessible by integration'), { status: 403 }); };
  await assert.rejects(require(helper).publish({ ...f, ...a, context, plans: plans(), generate }), /administrator.*Allow GitHub Actions to create and approve pull requests/);
});
test('unchanged reruns preserve branch SHA and PR metadata; changed plans safely rebuild the same branch', async t => {
  const f = fixture(t), a = api(), { publish } = require(helper);
  await publish({ ...f, ...a, context, plans: plans(), generate });
  const first = git(f.remote, 'rev-parse', ref);
  a.prs[0].labels.push({ name: 'maintainer-label' }); a.calls.length = 0;
  await publish({ ...f, ...a, context, plans: plans(), generate });
  assert.equal(git(f.remote, 'rev-parse', ref), first);
  assert.deepEqual(a.calls.filter(([kind]) => ['create', 'update', 'labels'].includes(kind)), []);
  const next = plans(); next[1].release_version = '1.6.46';
  await publish({ ...f, ...a, context, plans: next, generate });
  assert.notEqual(git(f.remote, 'rev-parse', ref), first); assert.equal(a.prs.length, 1);
  assert.equal(git(f.remote, 'show', `${ref}:recipes-core/1.5.inc`), '1.5.45');
  assert.ok(a.prs[0].labels.some(l => l.name === 'maintainer-label'));
});
test('no-update preserves a differing legacy branch, but merged/no-diff housekeeping closes exact PR and deletes only owned branch', async t => {
  const f = fixture(t), a = api(), { publish } = require(helper);
  await publish({ ...f, ...a, context, plans: plans(), generate });
  const first = git(f.remote, 'rev-parse', ref);
  git(f.cwd, 'push', 'origin', 'main:refs/heads/unrelated');
  const idle = plans().map(p => ({ ...p, needs_update: false, update_type: 'none' }));
  await publish({ ...f, ...a, context, plans: idle, generate: () => assert.fail('idle generation') });
  assert.equal(git(f.remote, 'rev-parse', ref), first); assert.equal(a.prs[0].state, 'open');
  git(f.cwd, 'fetch', 'origin', ref); git(f.cwd, 'merge', '--ff-only', 'FETCH_HEAD');
  fs.writeFileSync(path.join(f.cwd, 'README'), 'subsequent unrelated base change');
  git(f.cwd, 'add', 'README'); git(f.cwd, 'commit', '-m', 'after merge'); git(f.cwd, 'push', 'origin', 'main');
  await publish({ ...f, ...a, context, plans: idle, generate: () => assert.fail('idle generation') });
  assert.equal(a.prs[0].state, 'closed'); assert.equal(git(f.cwd, 'ls-remote', '--heads', 'origin', ref), '');
  assert.ok(git(f.cwd, 'ls-remote', '--heads', 'origin', 'refs/heads/unrelated'));
});
test('active generation with a base-identical tree closes the obsolete matching PR', async t => {
  const f = fixture(t), a = api(), { publish } = require(helper);
  await publish({ ...f, ...a, context, plans: plans(), generate });
  await publish({ ...f, ...a, context, plans: plans(), generate: () => {} });
  assert.equal(a.prs[0].state, 'closed'); assert.equal(git(f.cwd, 'ls-remote', '--heads', 'origin', ref), '');
});
test('lease prevents an actor creating the automation branch during generation from being overwritten', async t => {
  const f = fixture(t), a = api(); let raced = false;
  await assert.rejects(require(helper).publish({ ...f, ...a, context, plans: plans(), generate: (cwd, plan) => {
    generate(cwd, plan);
    if (!raced) { git(f.cwd, 'push', 'origin', `HEAD:${ref}`); raced = true; }
  } }), /stale info|rejected/);
  assert.equal(git(f.remote, 'rev-parse', ref), git(f.cwd, 'rev-parse', 'HEAD')); assert.equal(a.prs.length, 0);
});
test('previously manually closed and merged PRs are not reopened or reused; wrong owner/base/head PRs are untouched', async t => {
  const f = fixture(t), a = api(), { publish } = require(helper);
  await publish({ ...f, ...a, context, plans: plans(), generate });
  a.prs[0].state = 'closed';
  await publish({ ...f, ...a, context, plans: plans(), generate });
  assert.equal(a.prs.length, 2); assert.equal(a.prs[0].state, 'closed');
  a.prs[1].state = 'closed'; a.prs[1].merged_at = '2026-01-01T00:00:00Z';
  a.prs.push({ ...a.prs[0], number: 50, state: 'open', base: { ref: 'other' } }, { ...a.prs[0], number: 51, state: 'open', head: { ref: 'automation/upstream-update', repo: { full_name: 'fork/repo' } } }, { ...a.prs[0], number: 52, state: 'open', head: { ref: 'other', repo: { full_name: 'owner/repo' } } });
  a.calls.length = 0;
  await publish({ ...f, ...a, context, plans: plans(), generate });
  assert.equal(a.prs.length, 6);
  assert.ok(a.calls.filter(([kind]) => kind === 'list').every(([, args]) => args.head === 'owner:automation/upstream-update' && args.base === 'main' && args.per_page === 100));
  assert.equal(a.calls.filter(([kind]) => kind === 'update').length, 0);
});
test('housekeeping also deletes a squash-merged branch after subsequent base changes without deleting newer branch work', async t => {
  const f = fixture(t), a = api(), { publish } = require(helper);
  await publish({ ...f, ...a, context, plans: plans(), generate });
  const head = git(f.remote, 'rev-parse', ref);
  git(f.cwd, 'fetch', 'origin', ref); git(f.cwd, 'merge', '--squash', 'FETCH_HEAD'); git(f.cwd, 'commit', '-m', 'squashed');
  const merged = git(f.cwd, 'rev-parse', 'HEAD');
  fs.writeFileSync(path.join(f.cwd, 'README'), 'new base'); git(f.cwd, 'add', 'README'); git(f.cwd, 'commit', '-m', 'subsequent'); git(f.cwd, 'push', 'origin', 'main');
  Object.assign(a.prs[0], { state: 'closed', merged_at: '2026-01-01T00:00:00Z', merge_commit_sha: merged }); a.prs[0].head.sha = head;
  await publish({ ...f, ...a, context, plans: plans().map(p => ({ ...p, needs_update: false, update_type: 'none' })), generate });
  assert.equal(git(f.cwd, 'ls-remote', '--heads', 'origin', ref), '');
  const newer = git(f.cwd, 'commit-tree', `${head}^{tree}`, '-p', head, '-m', 'new automation work after merge');
  git(f.cwd, 'push', 'origin', `${newer}:${ref}`);
  await publish({ ...f, ...a, context, plans: plans().map(p => ({ ...p, needs_update: false, update_type: 'none' })), generate });
  assert.equal(git(f.remote, 'rev-parse', ref), newer);
});
test('publisher excludes generator-staged unrelated files and stages complete directory deletions', async t => {
  const f = fixture(t), a = api();
  await require(helper).publish({ ...f, ...a, context, plans: plans(), generate: cwd => {
    fs.rmSync(path.join(cwd, 'recipes-core'), { recursive: true, force: true });
    fs.writeFileSync(path.join(cwd, 'README'), 'staged secret'); git(cwd, 'add', '-A');
  } });
  assert.equal(git(f.remote, 'show', `${ref}:README`), 'base');
  assert.equal(git(f.remote, 'ls-tree', '-r', '--name-only', ref), 'README');
});
function generate(cwd, plan) {
  fs.writeFileSync(path.join(cwd, 'recipes-core', `${plan.line}.inc`), plan.release_version);
  fs.rmSync(path.join(cwd, 'recipes-core', 'old.inc'), { force: true });
  fs.writeFileSync(path.join(cwd, 'README'), 'must not publish');
}
test('publishes both maintained lines sequentially on legacy branch with metadata and allowlisted additions/deletions', async t => {
  const f = fixture(t), a = api(), order = [];
  const { publish } = require(helper);
  await publish({ ...f, ...a, context, plans: plans(), generate: async (cwd, plan) => { order.push(plan.line); generate(cwd, plan); } });
  assert.deepEqual(order, ['1.5', '1.6']);
  const ref = 'refs/heads/automation/upstream-update';
  const tree = git(f.remote, 'ls-tree', '-r', '--name-only', ref).split('\n');
  assert.deepEqual(tree, ['README', 'recipes-core/1.5.inc', 'recipes-core/1.6.inc']);
  assert.equal(git(f.remote, 'show', `${ref}:README`), 'base');
  assert.equal(a.prs.length, 1); assert.equal(a.prs[0].base.ref, 'main');
  assert.match(a.prs[0].body, /Validation Checklist/); assert.match(a.prs[0].body, /git tag 1\.6\.45/);
  assert.deepEqual(a.labels.map(l => l.name).sort(), ['automated', 'upstream-update']);
  assert.deepEqual(a.prs[0].labels.map(l => l.name).sort(), ['automated', 'upstream-update']);
});
