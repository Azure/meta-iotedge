# Read-only host preflight

A two-minute diagnostic using the existing 1ES pool/image. No custom VM image,
job container, BitBake, cache writes, mount/package/service changes, credentials,
raw logs or resource-limit changes. This is a snapshot, not a reliability fix.

## Trigger and authorized execution

`workflow_dispatch` remains available after registration. The initial isolated
publication uses a push trigger restricted to branch
`diag/host-cache-memory-preflight` and the exact workflow/collector paths.
Do not open a PR: that would trigger unrelated Yocto builds. Inspect all existing
workflow triggers before publishing. Further matching pushes can run the probe
again; do not push unreviewed iterations or create an automatic retry loop.

John authorized proceeding with a small host diagnostic for both runner reliability
and cache feasibility. GitHub schedules this separate job on an available runner;
it must not interrupt or alter the main or PR232 builds. An available runner is
not proof of a quiescent host or pool: idleness/non-build demand remain explicitly
UNVERIFIED. The concurrency group serializes preflights only. If no runner is
available, leave it queued rather than cancelling builds or recycling agents.

## What it records

- Current-process-visible RAM/swap and CPU/memory/I/O PSI.
- Bounded cgroup-v2 self and visible ancestors: memory limits/current/peak,
  selected reclaimability/OOM counters, CPU quota/period and throttling counters.
- Selected Runner.Listener, Runner.Worker and dockerd cgroup budgets, discovered
  only by fixed executable names in `/proc/<pid>/comm`; never process arguments.
  At most4096 proc entries and four instances per selected service are considered.
  Disappearing/denied processes and hidden ancestors remain explicit gaps.
- Numeric free bytes/inodes for the default cache filesystem, falling back to its
  parent or root when absent. The source is a fixed enum, not a mount URL.
- Numeric effective UID/GID, hostname, NFS/Docker/sudo binary presence, kernel NFS
  registration and the covering filesystem type of `/var/cache/yocto`.

Binary presence does NOT prove sudo/mount authorization or daemon health. No sudo
or mount command is executed. No endpoint/network/locking check occurs. Cache
mount readiness, durability, trust isolation and customized cache paths remain
unverified. This cannot establish the historical failed host's state.

## Collection and security boundaries

The host job checks out its immutable workflow SHA with full-SHA-pinned Actions,
contents-read permissions and no persisted Git credentials. It uploads exactly
`host-preflight.json`, retained three days. No arbitrary ref/path inputs exist.
The imported fixture-root API is for offline tests, not CLI/workflow input.

Individual reads reject final symlinks and nonregular files and are size bounded;
mountinfo has a separate1MiB/4096-line bound. Parsers discard unapproved fields,
mount sources/options and malformed raw input. No environment dump, credential
files, `/buildcacheconfig.json`, Docker inspection, SSH/auth files or journals.
Kernel cgroup paths are validated before reading selected counters. V1/unusual
mount mappings remain unknown, not zero or unlimited. `memory.events` and PSI
are cumulative; one snapshot does not measure rates or build peaks.

The workflow declaration supplies host execution context, not the collector.
A local or container smoke run is NOT a 1ES measurement. Visible ancestry is not
proof of complete outside-host budgets. Host-local evidence is not durable across
VM loss; provider lifecycle/retained failure evidence remains a separate need.
No RAM cap should be selected automatically from this artifact.

## Local validation

```
python3 -m unittest discover -s tests -p test_host_preflight.py -v
python3 -m unittest discover -s tests
node --test tests/*.cjs
```

Fixtures use the configured TMPDIR, with sentinel credential/IP values tested for
non-disclosure. Root operations, Docker daemon queries and package installation
are not part of these tests. Publishing/running is distinct from local tests;
report actual run SHA, runner identity, output and gaps after execution.
