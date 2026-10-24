# Shared-cache pilot (draft experiment only)

No shared filesystem is deployed or assumed. The first completed live deliverable
was a read-only prerequisite inventory on the **existing**
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
updates for this own-repository branch. Self-hosted jobs are manual-only,
restricted to that exact branch, with five-minute job timeouts. Dispatch defaults
to `operation=preflight`; `managed-roundtrip` instead selects exactly two ordered
jobs (producer, then consumer) and skips host preflight. Every job uses
full tracked-source checkouts (shallow history is intentional, not sparse) in
`shared-cache-pilot-source`, with credentials persistence disabled. The host
job checks out the immutable workflow SHA, not an arbitrary caller ref.
Reports are isolated under a run/attempt-specific runner temporary directory.

## Completed first read-only host preflight

[Run 40038583985](https://github.com/Azure/meta-iotedge/actions/runs/40038583985)
completed inventory collection on the existing image. The observed real/effective
UID was 1000, `sudo_noninteractive_true` was `passed`, the `mount.nfs` helper
was not found, and the `nfs-common` package was `not_confirmed` (not proof of
absence). `docker --version` reached the original three-second timeout; this
is inconclusive CLI-startup evidence, not proof of an unsupported image or
Docker failure. Docker daemon access remains `unknown`.

The follow-up gives only the Docker CLI check a fixed 15-second bound; no live
follow-up result is claimed here. Neither the completed inventory nor successful
`sudo -n true` establishes mount authorization, mount success, network access or
shared-storage support. Those fields remain `unknown`.

## Reusable authorized dispatch procedure

For each future run, after independent review and separately authorized
publication as a **draft**, obtain separate dispatch authorization:

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

## Preflight probe contract

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

The Docker CLI version subprocess has a fixed 15-second timeout; sudo and
package-query subprocesses retain three seconds each (21 seconds combined,
within the one-minute collector step and five-minute job limits). Exit outcomes
are `passed`, `failed`, `unavailable`, `timeout`, or `unknown`; raw stdout/stderr and
exceptions are never copied to the report. The exact package-state stdout is
compared internally and discarded. Missing commands do not trigger installs.

`network_access`, `mount_authorization`, `mount_success`,
`shared_storage_support`, and `docker_daemon_access` are always `unknown`.
There is no approved endpoint. The probe does not read `/buildcacheconfig.json`,
probe a network, mount anything, install packages, write shared markers,
modify caches, or perform producer/consumer share operations. Only the source
checkout and isolated diagnostic report/artifact are written by the workflow.
A no-op may still be recorded by the host's normal sudo audit logging.

The preflight authorizes no storage test. The separately approved tiny managed
roundtrip below is not a mount, shared-filesystem or BitBake acceptance test.
Locking, filesystem permissions and real BitBake cache hits remain untested.
No inference about runner-disconnect root cause or cache performance follows
from inventory.

## Approved managed-cache action roundtrip (implementation; live result pending)

The approved scope is one tiny uniquely keyed publish to the existing
`yocto-sstate` managed cache and one fresh-local restore on the existing pool
and image. Normal official engine metadata/retention writes are allowed.
No new resource, pool, image, network, container, service, mount or SDK install;
no deletion, GC, agent recycling, live negative publication or full BitBake run.
The existing production build workflow is unchanged.

After independent review, authorized publication and exact remote-SHA checks,
the registered workflow can be selected explicitly (do not dispatch from an
unreviewed/moving branch):

```sh
gh workflow run shared-cache-pilot.yml --repo Azure/meta-iotedge \
  --ref experiment/shared-yocto-cache -f operation=managed-roundtrip
```

This document is not a live-run receipt. Keep PR233 draft; PR events run only
cheap offline fixtures and cannot enter the self-hosted jobs. Consumer has a
normal success dependency on producer; failure never triggers a fallback job.
Both jobs have five-minute limits, four-minute action steps, a 230-second
whole-helper deadline and a 90-second engine process-group timeout. The public
package transfer has a 90-second checked deadline with 15-second socket bounds,
no retries and a 200 MiB compressed ceiling; the whole-helper deadline also
bounds DNS/extraction/HEAD delays. Slow acquisition fails rather than extending
job limits or installing host tools. Container HEAD requests have five-second
bounds, at most twelve targets and no retry/redirect/proxy/body download.

### Official executable and runtime contract

Only public `Microsoft.BuildXL.linux-x64` `0.1.0-20261016.6` is acquired from the
[official external feed](https://pkgs.dev.azure.com/mseng/PipelineTools/_packaging/BuildXL.External/nuget/v3/index.json).
The exact download URL is pinned in `scripts/shared-cache-roundtrip.py`; SHA256
`1332d1b02d686328369fb75742fd5942f0eef84aa24aea73b358852715359456`
is verified **before** extraction. ZIP traversal, links, special files and
oversized extraction are refused; only the bundled `bxl` needs user execute
permission. No internal package contents/documentation are included.

Pinned public source revision
[`9caed4d586bb6421ad6491eb6e4a54a8e839c5af`](https://github.com/microsoft/BuildXL/tree/9caed4d586bb6421ad6491eb6e4a54a8e839c5af/Public/Src/Cache)
backs these contracts: `BuildCacheResource/Helper/Model/{BuildCacheConfiguration,BuildCacheShard,BuildCacheContainer}.cs`
and `VerticalStore/MemoizationStoreAdapter/{BlobWithLocalCacheConfig,BlobWithLocalCacheFactory,BlobCacheConfig}.cs`.
The helper reads only fixed `/buildcacheconfig.json`, bounded to 1 MiB, as a
regular no-follow file; it never prints, copies or uploads it. The accepted
hosted-pool schema is a PascalCase array with exactly one `Name=yocto-sstate`,
`RetentionDays`, and nonempty `Shards`. Every selected shard must have its
`StorageUrl` and three distinct named `Content`, `Metadata`, `Checkpoint`
containers, each with native `Name`, `Type`, `Signature`. Unknown/ambiguous
schema fails, without guessed normalization or a developer-token workaround.

Only HTTPS account roots matching `*.blob.core.windows.net` are accepted.
Every selected credential must explicitly be a service/user-delegation
container SAS (`sr=c`, explicit read permission); account SAS (`ss`/`srt`),
unknown/duplicate credential fields and URI overrides are refused. The helper
HEADs only those actual container URIs and stops before engine startup if any
container is absent/inaccessible. It also refuses metadata changes detected
between this check and launch. It never lists/downloads objects during preflight.
Native startup may still call ensure-container-exists: `IsReadOnly` alone is
**not** a no-create guarantee. Preexisting containers and container-scoped SAS
prevent authorization to create other containers. Runtime metadata must remain
stable through native startup; the helper does not lock or alter the host file.

The official outer `BlobWithLocalCacheFactory` has `FailIfRemoteFails=true`, a
writable local `MaxCacheSizeInMB=64`, and a remote configured with
`HostedPoolBuildCacheConfigurationFile=/buildcacheconfig.json`,
`HostedPoolActiveBuildCacheName=yocto-sstate`,
`ConnectionStringFileDataProtectionEncrypted=false`, `AllowInteractiveAuth=false`,
`LogToKusto=false`, `EnableContentRecoveryOnPlaceFailure=false`.
Only remote `IsReadOnly` changes: false for producer, true for consumer.
No container overrides, Namespace or Universe are used: those names do not
isolate managed-container keys in this revision.

### Freshness and evidence

Both jobs derive the same 32-hex nonce from the public run ID/attempt; it is an
actual declared input file and the identical `fingerprintSalt`. A single bundled
DScript `Transformer.execute` invokes `/usr/bin/bash` and writes exactly 56 bytes.
An untracked execution marker sits outside cached outputs. The artifact bound
is **not** a bound on native metadata, requests or traffic and does not mean one
Blob object. Existing retention governs the entry; nothing is deleted afterward.

Private paths are fixed under the OS account home (not caller-selected HOME or
TMPDIR), `.meta-iotedge-managed-roundtrip/<run-id>-<attempt>`. Home/path or action
input differences fail before consumer launch. Source, package, object and
marker absolute paths stay identical on both jobs. Engine artifact/state and
64 MiB local-cache directories are new for each phase. If scheduled on the same
host, only this run's prior source/work/marker/package is renamed into its
producer directory; no existing cache is modified or deleted. A repeated phase
is refused. No producer artifact is sent to the consumer: only digest, path/input
fingerprint and hashed host identity job outputs cross the dependency.

Producer must report one execution, zero process hits and zero warnings/errors.
Consumer must report zero executions, one process hit, one remote process/content
hit, exactly 56 downloaded output bytes, no execution marker, and byte-for-byte
expected output with SHA256 equal to producer. Engine exit0 with fallback
execution is failure. These are native engine counters, not synthetic success
messages. Offline fixtures do not establish live Blob integration.

Hashed runner name and machine ID record identity; `different_host_identity`
compares machine IDs, not scheduling labels. Different VMs are **not required**.
A same-host restore still establishes fresh-local/remote-content behavior when
the native counters pass. Do not label a run cross-VM unless actual assigned
runner/host evidence confirms different VMs (machine IDs may be cloned).

The engine receives a cleared environment, private HOME/TMPDIR, no inherited
credentials/proxies, disabled core dumps, and server/telemetry/interactivity/
graph reuse/output reuse disabled. Native stdout/stderr/cache logs remain
private; public errors contain only fixed failure status plus a stderr-only `failure-stage` enum (`initialization`, `metadata-validation`, `container-preflight`, `package-acquisition`, `engine-execution`, `result-verification`, or `summary-publication`), never exception details. Only validated,
allowlisted summary JSON (fixed enums, counters, counts and hex digests) uploads
on success. No package, raw SDK logs, runtime metadata, cache files or generated
engine files are pipeline artifacts. Review both job outcomes and the two
`shared-cache-roundtrip-<run-id>-<attempt>-{producer,consumer}` summaries; failed
jobs require private diagnostics, not publication of raw logs.

## Read-only metadata schema follow-up (implementation; not a live receipt)

`operation=metadata-schema` selects **only one** manually gated job on the same
pool/image; offline tests, host preflight and both managed jobs skip. The job is
five minutes; checkout, collector and summary upload each have one-minute limits.
It reads only fixed `/buildcacheconfig.json` with the existing 1 MiB regular-file,
no-follow reader and duplicate-key guard. It never launches an engine, downloads
a package, authenticates, performs HEAD/Blob/network operations or creates a
private cache trial. Checkout and the isolated report/artifact are its only writes.

Only `metadata-schema.json` uploads, on successful validated inventory emission.
The fixed, at-most-16-KiB summary contains read-status/file/root-kind enums,
bounded counts, exact known-field/casing presence, unknown-key counts (never their
names), cache-name matches, selected shards, container roles/type kinds, signature
kinds and SAS **key presence only**. Permission/container-scope booleans require
all selected containers and are false for an empty selection; no permission or
credential values, names, account URLs, raw metadata or exception text are emitted.
PascalCase fields are backed by the pinned source above; camelCase and the four
wrapper spellings are diagnostic comparisons, not schema normalization. The
unchanged pure validator supplies `validator_passes`; no guessed failure cause or
new cache-client behavior is introduced. Inventory success with a non-`ok` read
status is **not cache acceptance**. This probe cannot diagnose the prelaunch
changed-file guard because it deliberately takes only one snapshot. Review the
probe before considering the separately bounded producer/consumer retry.

## Offline checks

```sh
python3 -m unittest discover -s tests -p test_shared_cache_preflight.py -v
python3 -m unittest discover -s tests -p test_shared_cache_roundtrip.py -v
node --test tests/test_shared_cache_workflow.cjs
```

Fixtures execute real bounded child processes for success, failure, missing
commands, sleeps/timeouts, package states and secret-bearing stdout/stderr;
host tool discovery is replaced with disposable fixture executables. These
tests do not invoke host sudo/Docker or claim live runner results. Workflow
guards and the deliberately failing aggregate status shell are exercised
locally. Full normal regression commands remain unchanged.
