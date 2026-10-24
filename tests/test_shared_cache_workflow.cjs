const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
function job(workflow, name) {
  const block = workflow.match(new RegExp(`^  ${name}:\\n([\\s\\S]*?)(?=^  [\\w-]+:|$(?![\\s\\S]))`, 'm'));
  assert.ok(block, `missing job ${name}`);
  return block[1];
}
function condition(block) {
  const match = block.match(/^    if: \$\{\{ (.+) \}\}$/m);
  assert.ok(match, 'missing explicit job condition');
  return match[1];
}
function event(overrides = {}) {
  return {repository: 'Azure/meta-iotedge', event_name: 'pull_request',
    event: {pull_request: {draft: true, head: {ref: 'experiment/shared-yocto-cache',
      repo: {full_name: 'Azure/meta-iotedge'}}}}, ...overrides};
}

test('only exact own-repo draft avoids expensive change/recipe/build path; ready restores gates', () => {
  const workflow = read('.github/workflows/ci-build.yml');
  assert.match(workflow, /types: \[opened, synchronize, reopened, ready_for_review, converted_to_draft\]/);
  const gate = condition(job(workflow, 'check-changes'));
  const evaluate = github => vm.runInNewContext(gate, {github, inputs: {}});
  assert.equal(evaluate(event()), false);
  for (const mutate of [
    g => g.event.pull_request.draft = false,
    g => g.event.pull_request.head.ref = 'experiment/shared-yocto-cache-other',
    g => g.event.pull_request.head.repo.full_name = 'fork/meta-iotedge',
    g => g.repository = 'fork/meta-iotedge',
  ]) {
    const github = event(); mutate(github); assert.equal(evaluate(github), true);
  }
  for (const event_name of ['push', 'workflow_dispatch', 'workflow_call']) {
    assert.equal(evaluate(event({event_name, event: {}})), true);
  }
  assert.equal(vm.runInNewContext(gate, {github: event(), inputs: {ref: 'release-source-sha'}}), true,
    'reusable caller with explicit source must retain full gates');
  assert.match(job(workflow, 'check-recipes'), /needs: check-changes/);
  assert.match(job(workflow, 'build'), /needs: \[check-changes, check-recipes\]/);
  assert.doesNotMatch(job(workflow, 'regression-tests'), /^    (if|needs):/m);
  const status = job(workflow, 'status-check');
  assert.match(status, /if: always\(\)/);
  const shell = status.split('        run: |\n')[1].split('\n')
    .map(line => line.startsWith('          ') ? line.slice(10) : line).join('\n')
    .replaceAll('${{ needs.regression-tests.result }}', 'success')
    .replaceAll('${{ needs.check-changes.result }}', 'skipped')
    .replaceAll('${{ needs.check-changes.outputs.docs_only }}', '')
    .replaceAll('${{ needs.check-recipes.result }}', 'skipped')
    .replaceAll('${{ needs.build.result }}', 'skipped');
  const result = spawnSync('bash', ['-c', shell], {encoding: 'utf8', timeout: 3000});
  assert.equal(result.status, 1);
  assert.match(result.stdout, /Full Build\/QEMU acceptance pending/);
});

test('pilot is PR-offline or exact-branch manual host inventory, never push or container', () => {
  const file = '.github/workflows/shared-cache-pilot.yml';
  assert.ok(fs.existsSync(path.join(root, file)), 'missing isolated pilot workflow');
  const workflow = read(file);
  const triggers = workflow.split('\njobs:')[0];
  assert.equal(/^  push:/m.test(triggers), false);
  assert.equal(/^  (schedule|pull_request_target|workflow_call):/m.test(triggers), false);
  assert.match(triggers, /^  pull_request:/m);
  assert.match(triggers, /^  workflow_dispatch:\s*$/m);
  assert.match(triggers, /inputs:\n      operation:\n        description: .+\n        type: choice\n        default: preflight\n        options: \[preflight, managed-roundtrip\]/);
  assert.match(triggers, /permissions:\n  contents: read/);
  assert.doesNotMatch(workflow, /sparse-checkout|container:|secrets\.|sudo |docker |buildcacheconfig/);
  const offline = job(workflow, 'offline-tests');
  const host = job(workflow, 'host-preflight');
  const evaluate = github => vm.runInNewContext(condition(host), {github, inputs: {operation: 'preflight'}});
  const dispatch = {...event({event_name: 'workflow_dispatch', event: {}}),
    ref: 'refs/heads/experiment/shared-yocto-cache', ref_type: 'branch'};
  assert.equal(evaluate(dispatch), true);
  assert.equal(evaluate(event()), false);
  for (const mutation of [{repository: 'fork/meta-iotedge'}, {ref: 'refs/heads/main'},
                          {ref_type: 'tag'}, {event_name: 'push'}]) {
    assert.equal(evaluate({...dispatch, ...mutation}), false);
  }
  assert.equal(vm.runInNewContext(condition(offline), {github: event()}), true);
  assert.equal(vm.runInNewContext(condition(offline), {github: dispatch}), false);
  assert.match(offline, /runs-on: ubuntu-22.04/);
  assert.match(offline, /python3 -m unittest discover -s tests -p test_shared_cache_preflight.py/);
  assert.match(offline, /node --test tests\/test_shared_cache_workflow.cjs/);
  assert.match(host, /1ES.Pool=meta-iotedge-1es-github-linux-amd64/);
  assert.match(host, /1ES.ImageOverride=agent-aziotedge-ubuntu-22.04-msmoby/);
  for (const block of [offline, host]) {
    assert.match(block, /timeout-minutes: 5/);
    assert.match(block, /uses: actions\/checkout@[a-f0-9]{40}\b/);
    assert.match(block, /path: shared-cache-pilot-source/);
    assert.match(block, /persist-credentials: false/);
    assert.match(block, /fetch-depth: 1/);
  }
  assert.match(offline, /ref: \$\{\{ github.sha \}\}/);
  assert.match(host, /ref: \$\{\{ github.workflow_sha \}\}/);
  assert.match(host, /python3 shared-cache-pilot-source\/scripts\/shared-cache-preflight.py > "\$REPORT_DIR\/preflight.json"/);
  assert.match(host, /REPORT_DIR: \$\{\{ runner.temp \}\}\/shared-cache-pilot-\$\{\{ github.run_id \}\}-\$\{\{ github.run_attempt \}\}/);
  assert.match(host, /uses: actions\/upload-artifact@[a-f0-9]{40}\b/);
  assert.match(host, /path: \$\{\{ runner.temp \}\}\/shared-cache-pilot-\$\{\{ github.run_id \}\}-\$\{\{ github.run_attempt \}\}\/preflight.json/);
  assert.match(host, /if-no-files-found: error/);
});

test('managed roundtrip runs exactly producer then consumer; preflight and PR never join', () => {
  const workflow = read('.github/workflows/shared-cache-pilot.yml');
  const dispatch = {repository: 'Azure/meta-iotedge', event_name: 'workflow_dispatch',
    ref: 'refs/heads/experiment/shared-yocto-cache', ref_type: 'branch', event: {}};
  const names = ['host-preflight', 'managed-producer', 'managed-consumer'];
  const evaluate = (name, github, operation) => vm.runInNewContext(condition(job(workflow, name)),
    {github, inputs: {operation}});
  assert.deepEqual(names.filter(n => evaluate(n, dispatch, 'managed-roundtrip')),
    ['managed-producer', 'managed-consumer']);
  assert.deepEqual(names.filter(n => evaluate(n, dispatch, 'preflight')), ['host-preflight']);
  assert.deepEqual(names.filter(n => evaluate(n, dispatch, 'other')), []);
  for (const mutation of [{repository: 'fork/meta-iotedge'}, {ref: 'refs/heads/main'},
    {ref_type: 'tag'}, {event_name: 'push'}, {event_name: 'pull_request'}]) {
    assert.deepEqual(names.filter(n => evaluate(n, {...dispatch, ...mutation}, 'managed-roundtrip')), []);
  }
  const producer = job(workflow, 'managed-producer');
  const consumer = job(workflow, 'managed-consumer');
  assert.match(consumer, /^    needs: managed-producer$/m);
  assert.doesNotMatch(consumer, /always\(\)|download-artifact/);
  assert.doesNotMatch(producer, /^    needs:/m);
  assert.equal((workflow.match(/^      - self-hosted$/gm) || []).length, 3);
  for (const [phase, block] of [['producer', producer], ['consumer', consumer]]) {
    assert.match(block, /1ES.Pool=meta-iotedge-1es-github-linux-amd64/);
    assert.match(block, /1ES.ImageOverride=agent-aziotedge-ubuntu-22.04-msmoby/);
    assert.match(block, /timeout-minutes: 5/);
    assert.match(block, /ref: \$\{\{ github.workflow_sha \}\}/);
    assert.match(block, /persist-credentials: false/);
    assert.match(block, new RegExp(`python3 shared-cache-pilot-source/scripts/shared-cache-roundtrip.py ${phase} > "\\$REPORT_DIR/roundtrip.json"`));
    assert.match(block, /path: \$\{\{ runner.temp \}\}\/shared-cache-roundtrip-[^\n]+\/roundtrip.json/);
    assert.doesNotMatch(block.replace(/^\s*#.*$/gm, ''), /if: always\(\)|matrix:|strategy:|affinity|recycle|continue-on-error/);
  }
  for (const key of ['sha256', 'host_id', 'path_id', 'input_id']) {
    assert.ok(producer.includes(`${key}: \${{ steps.roundtrip.outputs.${key} }}`));
    assert.ok(consumer.includes(`PRODUCER_${key.toUpperCase()}: \${{ needs.managed-producer.outputs.${key} }}`));
  }
  assert.match(job(workflow, 'offline-tests'), /python3 -m unittest discover -s tests -p test_shared_cache_roundtrip.py/);
});
