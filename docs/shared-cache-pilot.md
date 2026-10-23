# Shared-cache pilot (draft experiment only)

No shared storage is deployed or assumed. This scaffold's first live deliverable
is a read-only prerequisite inventory on the **existing**
`meta-iotedge-1es-github-linux-amd64` pool with
`agent-aziotedge-ubuntu-22.04-msmoby`. It does not change that pool or image.
The local UID/GID 1001 and nonrecursive cache preparation remain independent
of this experiment; see [CI cache](ci-cache.md).

## Draft PR behavior

Only an own-repository draft PR in `Azure/meta-iotedge` with the exact head
`experiment/shared-yocto-cache` defers the ordinary change detection,
network-dependent recipe consistency check and three BitBake/QEMU jobs.
Fast offline regressions still run. **Status check deliberately fails with
“Full Build/QEMU acceptance pending”; skipped builds are not acceptance.**
Other branches, forks, normal PRs, main/kirkstone pushes, manual builds and
explicit-ref reusable release builds retain their gates. `ready_for_review`
triggers normal CI again: marking this draft ready can start all three builds.
No extra push trigger was added for the pilot.

The dedicated `Shared cache pilot` workflow runs only offline fixtures on PR
updates for this own-repository branch. Its self-hosted job is manual-only,
restricted to that exact branch, with a five-minute job timeout. Both jobs use
full tracked-source checkouts (shallow history is intentional, not sparse) in
`shared-cache-pilot-source`, with credentials persistence disabled. The host
job checks out the immutable workflow SHA, not an arbitrary caller ref.
Reports are isolated under a run/attempt-specific runner temporary directory.

## First read-only host preflight (not yet executed)

After independent review and separately authorized publication as a **draft**:

1. Verify the exact remote SHA/files and that PR updates launched only the
   expected cheap jobs. Do not mark the PR ready just to register a workflow.
2. Check registration using read-only calls, for example:
   `gh workflow view shared-cache-pilot.yml --repo Azure/meta-iotedge`.
   A newly added dispatch workflow may need default-branch registration.
   Merely being visible on the experiment branch does **not** prove it is
   dispatchable. If unsupported/unregistered, stop and ask for an approved
   registration approach; do not add a push bootstrap, merge, change settings,
   or launch another workflow as a workaround.
3. Only after registration/support and the published SHA are verified, invoke
   **one** authorized short run:

   ```sh
   gh workflow run shared-cache-pilot.yml --repo Azure/meta-iotedge \
     --ref experiment/shared-yocto-cache
   ```

4. Read back the run's exact head SHA, workflow, branch, assigned runner, job
   outcomes and artifact. Download only
   `shared-cache-preflight-<run-id>-<attempt>` and inspect `preflight.json`.
   Queue/provisioning time is not host probe execution time. Job success means
   inventory collection, not that every prerequisite passed or storage works.

## Probe contract

The collector accepts **no arguments**. It emits only fixed JSON keys with
numbers, booleans or allowlisted status enums; no command output, exception
text, paths, usernames, environment values or credentials are emitted.
Executable discovery and child environments use a fixed system PATH.

- Numeric real/effective UID; executable availability for `mount` and
  `mount.nfs` (neither is executed).
- Read-only `dpkg-query -W -f=${db:Status-Status} nfs-common`: `installed`
  requires the exact installed status; nonzero or other output means
  `not_confirmed`, not proof of absence. Unavailable/timeout/unknown stay explicit.
- `docker --version`, with both output streams discarded: **CLI availability
  only**. No Docker socket, daemon contact, configuration/credential reads or
  code container is used; `docker_daemon_access` remains `unknown`.
- Bounded `sudo -n true`: a noninteractive root no-op only. A `passed`
  `sudo_noninteractive_true` does **not** authorize a mount or demonstrate mount
  success; both corresponding fields remain `unknown`.

Each subprocess has a three-second timeout. Exit outcomes are `passed`,
`failed`, `unavailable`, `timeout`, or `unknown`; raw stdout/stderr and
exceptions are never copied to the report. The exact package-state stdout is
compared internally and discarded. Missing commands do not trigger installs.

`network_access`, `mount_authorization`, `mount_success`,
`shared_storage_support`, and `docker_daemon_access` are always `unknown`.
There is no approved endpoint. The probe does not read `/buildcacheconfig.json`,
probe a network, mount anything, install packages, write shared markers,
modify caches, or perform producer/consumer share operations. Only the source
checkout and isolated diagnostic report/artifact are written by the workflow.
A no-op may still be recorded by the host's normal sudo audit logging.

Any next storage test requires separate approval of its endpoint, isolated
path, writes/removal and lifecycle. Cross-agent visibility, persistence,
locking, permissions and real BitBake cache hits remain untested. No inference
about runner-disconnect root cause or cache performance follows from inventory.

## Offline checks

```sh
python3 -m unittest discover -s tests -p test_shared_cache_preflight.py -v
node --test tests/test_shared_cache_workflow.cjs
```

Fixtures execute real bounded child processes for success, failure, missing
commands, sleeps/timeouts, package states and secret-bearing stdout/stderr;
host tool discovery is replaced with disposable fixture executables. These
tests do not invoke host sudo/Docker or claim live runner results. Workflow
guards and the deliberately failing aggregate status shell are exercised
locally. Full normal regression commands remain unchanged.
