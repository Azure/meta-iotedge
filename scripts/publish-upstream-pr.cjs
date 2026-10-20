'use strict';
// One combined PR, deliberately retaining automation/upstream-update for migration.
// All maintained lines are generated sequentially from the same fresh base.
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const BRANCH = 'automation/upstream-update';
const ALLOWED = ['recipes-core', 'conf/templates'];
function git(cwd, ...args) {
  return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 32 * 1024 * 1024 }).trim();
}
function validatePlans(plans) {
  const version = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$/;
  if (!Array.isArray(plans) || plans.length !== 2 || new Set(plans.map(p => p?.line)).size !== 2 || plans.some(p =>
    !p || !['1.5', '1.6'].includes(p.line) || typeof p.needs_update !== 'boolean' ||
    !['none', 'significant', 'docker-only'].includes(p.update_type) ||
    !['release_version', 'daemon_version', 'iis_version', 'current_release'].every(k => typeof p[k] === 'string' && version.test(p[k]) && p[k].startsWith(`${p.line}.`)) ||
    !(p.line === '1.5' ? ['scarthgap', 'kirkstone'] : ['wrynose', 'scarthgap-1.6']).includes(p.template)
  )) throw new Error('Invalid upstream plans: require exactly both maintained LTS lines and validated versions/templates');
  return plans;
}
async function ensureLabels(github, repo, names) {
  const labels = await github.paginate(github.rest.issues.listLabelsForRepo, { ...repo, per_page: 100 });
  for (const name of names) {
    if (labels.some(label => label.name === name)) continue;
    try { await github.rest.issues.createLabel({ ...repo, name, color: '0366d6' }); }
    catch (error) {
      if (error.status !== 422) throw error;
      const current = await github.paginate(github.rest.issues.listLabelsForRepo, { ...repo, per_page: 100 });
      if (!current.some(label => label.name === name)) throw error;
    }
  }
}
function metadata(plans, base) {
  const versions = plans.map(p => `| ${p.line} Release | ${p.current_release} | ${p.release_version} |\n| ${p.line} Daemon | - | ${p.daemon_version} |\n| ${p.line} IIS | - | ${p.iis_version} |`).join('\n');
  const instructions = plans.map(p => `### IoT Edge ${p.release_version}\n\`\`\`bash\ngit pull origin ${base}\ngit tag ${p.release_version}\ngit push origin ${p.release_version}\n\`\`\`\n- [Azure IoT Edge ${p.release_version}](https://github.com/Azure/azure-iotedge/releases/tag/${p.release_version})`).join('\n\n');
  return {
    title: `Update to IoT Edge ${plans.map(p => p.release_version).join(' and ')}`,
    body: `## Automated Upstream Update\n\nThis PR was automatically created by the upstream release watcher.\n\n### Versions\n| Component | Current | New |\n|-----------|---------|-----|\n${versions}\n\n### Validation Checklist\n- [ ] CI build passes\n- [ ] QEMU validation passes\n\n### After Merging\nCreate a release by running the commands below. This will trigger the [release workflow](../actions/workflows/release.yml) to build and publish packages.\n\n### Release Notes\n${instructions}`
  };
}
async function publish({ github, context, plans, expectedBase, cwd = process.cwd(), generate = (dir, p) => execFileSync('bash', ['scripts/update-recipes.sh', '--iotedge-version', p.release_version, '--template', p.template, '--clean'], { cwd: dir, stdio: 'inherit' }) }) {
  validatePlans(plans);
  const repo = context.repo;
  const base = (await github.rest.repos.get(repo)).data.default_branch;
  const ref = `refs/heads/${BRANCH}`;
  git(cwd, 'fetch', '--no-tags', 'origin', `refs/heads/${base}`);
  const baseSha = git(cwd, 'rev-parse', 'FETCH_HEAD');
  if (expectedBase && expectedBase !== baseSha) throw new Error('Default branch changed after detection; rerun to refresh both LTS plans');
  const observed = git(cwd, 'ls-remote', '--heads', 'origin', ref).split(/\s/)[0];
  if (observed) git(cwd, 'fetch', '--no-tags', 'origin', ref);
  const open = await github.paginate(github.rest.pulls.list, { ...repo, state: 'open', head: `${repo.owner}:${BRANCH}`, base, per_page: 100 });
  const matching = open.filter(pr => pr.state === 'open' && pr.head.ref === BRANCH && pr.head.repo?.full_name === `${repo.owner}/${repo.repo}` && pr.base.ref === base);
  const active = plans.filter(p => p.needs_update && p.update_type === 'significant');
  const root = fs.mkdtempSync(path.join(process.env.RUNNER_TEMP || process.env.TMPDIR || os.tmpdir(), 'upstream-publish-'));
  const work = path.join(root, 'tree');
  try {
    git(cwd, 'worktree', 'add', '--detach', work, baseSha);
    for (const plan of active) await generate(work, plan);
    // Do not trust any incidental staging done by a generator/tool. Start the
    // candidate index at base, then include only generated paths (also deleted
    // directories that no longer exist on disk).
    git(work, 'reset', '--mixed', baseSha);
    const paths = ALLOWED.filter(p => fs.existsSync(path.join(work, p)) || git(work, 'ls-files', '--', p));
    if (paths.length) git(work, 'add', '-A', '--', ...paths);
    const tree = git(work, 'write-tree');
    const baseTree = git(cwd, 'rev-parse', `${baseSha}^{tree}`);
    // A false detector result is not permission to delete a still-differing PR.
    let redundant = observed && (git(cwd, 'rev-parse', `${observed}^{tree}`) === baseTree || (() => { try { git(cwd, 'merge-base', '--is-ancestor', observed, baseSha); return true; } catch { return false; } })());
    if (observed && !active.length && !redundant) {
      // Squash/rebase merges need the exact merged PR head and a merge commit
      // reachable from today's base. A later update of this branch is NOT owned
      // by that historical PR and must survive housekeeping.
      const closed = await github.paginate(github.rest.pulls.list, { ...repo, state: 'closed', head: `${repo.owner}:${BRANCH}`, base, per_page: 100 });
      redundant = closed.some(pr => pr.state === 'closed' && pr.merged_at && pr.head.ref === BRANCH && pr.head.sha === observed && pr.head.repo?.full_name === `${repo.owner}/${repo.repo}` && pr.base.ref === base && pr.merge_commit_sha && (() => { try { git(cwd, 'merge-base', '--is-ancestor', pr.merge_commit_sha, baseSha); return true; } catch { return false; } })());
    }
    if (tree === baseTree) {
      if (!active.length && !redundant) return { status: 'preserved' };
      for (const pr of matching) {
        await github.rest.pulls.update({ ...repo, pull_number: pr.number, state: 'closed' });
        if ((await github.rest.pulls.get({ ...repo, pull_number: pr.number })).data.state !== 'closed') throw new Error('PR cleanup readback failed');
      }
      if (observed) {
        git(cwd, 'push', `--force-with-lease=${ref}:${observed}`, 'origin', `:${ref}`);
        if (git(cwd, 'ls-remote', '--heads', 'origin', ref)) throw new Error('Branch cleanup readback failed');
      }
      return { status: 'no-diff' };
    }
    if (!observed || git(cwd, 'rev-parse', `${observed}^{tree}`) !== tree) {
      const message = active.map(p => `Update IoT Edge recipes for ${p.release_version}\n\nIoT Edge daemon version: ${p.daemon_version}`).join('\n\n');
      const sha = execFileSync('git', ['commit-tree', tree, '-p', baseSha, '-m', message], { cwd, encoding: 'utf8', env: { ...process.env, GIT_AUTHOR_NAME: 'github-actions[bot]', GIT_AUTHOR_EMAIL: '41898282+github-actions[bot]@users.noreply.github.com', GIT_COMMITTER_NAME: 'github-actions[bot]', GIT_COMMITTER_EMAIL: '41898282+github-actions[bot]@users.noreply.github.com' } }).trim();
      git(cwd, 'push', `--force-with-lease=${ref}:${observed}`, 'origin', `${sha}:${ref}`);
      if (git(cwd, 'ls-remote', '--heads', 'origin', ref).split(/\s/)[0] !== sha) throw new Error('Branch publication readback failed');
    }
    const fields = metadata(active, base);
    let pr = matching[0];
    if (!pr) {
      // A manually closed unmerged PR is deliberately superseded by a new PR;
      // merged history is never reopened. Only exact open matches are reused.
      try { pr = (await github.rest.pulls.create({ ...repo, head: BRANCH, base, ...fields, draft: false, maintainer_can_modify: true })).data; }
      catch (error) {
        if (error.status === 403) throw new Error(`PR creation forbidden. Ask an administrator to check \"Allow GitHub Actions to create and approve pull requests\" and token/org policy. Original error: ${error.message}`, { cause: error });
        if (error.status !== 422) throw error;
        const raced = await github.paginate(github.rest.pulls.list, { ...repo, state: 'open', head: `${repo.owner}:${BRANCH}`, base, per_page: 100 });
        pr = raced.find(p => p.state === 'open' && p.head.ref === BRANCH && p.head.repo?.full_name === `${repo.owner}/${repo.repo}` && p.base.ref === base);
        if (!pr) throw error;
        if (pr.title !== fields.title || pr.body !== fields.body) await github.rest.pulls.update({ ...repo, pull_number: pr.number, ...fields });
      }
    } else if (pr.title !== fields.title || pr.body !== fields.body) await github.rest.pulls.update({ ...repo, pull_number: pr.number, ...fields });
    await ensureLabels(github, repo, ['automated', 'upstream-update']);
    const missing = ['automated', 'upstream-update'].filter(name => !pr.labels?.some(label => label.name === name));
    if (missing.length) await github.rest.issues.addLabels({ ...repo, issue_number: pr.number, labels: missing });
    const readback = (await github.rest.pulls.get({ ...repo, pull_number: pr.number })).data;
    if (readback.title !== fields.title || readback.body !== fields.body || !['automated', 'upstream-update'].every(name => readback.labels.some(label => label.name === name))) throw new Error('PR metadata readback failed');
    return { status: 'published', number: pr.number };
  } finally {
    try { git(cwd, 'worktree', 'remove', '--force', work); } finally { fs.rmSync(root, { recursive: true, force: true }); }
  }
}
module.exports = { publish, ensureLabels, validatePlans };
