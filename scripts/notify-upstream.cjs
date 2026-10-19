'use strict';
const { ensureLabels, validatePlans } = require('./publish-upstream-pr.cjs');
async function notify({ github, context, plans }) {
  validatePlans(plans);
  const repo = context.repo;
  for (const p of plans.filter(p => p.update_type === 'docker-only')) {
    const marker = `<!-- meta-iotedge:docker-only:${p.line}:${p.release_version} -->`;
    // No label filter: an acknowledged issue stays acknowledged even if relabeled.
    const issues = await github.paginate(github.rest.issues.listForRepo, { ...repo, state: 'all', per_page: 100 });
    if (issues.some(issue => {
      const lines = (issue.body || '').split(/\r?\n/);
      return !issue.pull_request && (lines.includes(marker) ||
        (issue.title === `IoT Edge ${p.release_version} released (Docker images only)` &&
          lines.includes(`**Latest Release:** ${p.release_version}`)));
    })) continue;
    const labels = ['docker-only-update', 'no-action-needed'];
    await ensureLabels(github, repo, labels);
    const body = `${marker}\nA new IoT Edge release is available, but it only contains Docker image updates.\n\n**Latest Release:** ${p.release_version}\n**Maintained line:** ${p.line}\n**Daemon Version:** ${p.daemon_version} (unchanged)\n**IIS Version:** ${p.iis_version} (unchanged)\n**Current Release:** ${p.current_release}\n\nNo recipe updates are needed since the daemon and IIS sources have not changed.\n\nThis issue is for tracking purposes only. Close it once acknowledged; closed acknowledgements are not recreated.\n\n[View release notes](https://github.com/Azure/azure-iotedge/releases/tag/${p.release_version})`;
    const result = await github.rest.issues.create({ ...repo, title: `IoT Edge ${p.release_version} released (Docker images only, ${p.line})`, labels, body });
    const saved = (await github.rest.issues.get({ ...repo, issue_number: result.data.number })).data;
    if (saved.body !== body) throw new Error('Docker notification readback failed');
  }
}
module.exports = { notify };
