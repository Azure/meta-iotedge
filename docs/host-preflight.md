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
- Numeric capacity/available bytes/free inodes separately for the default cache,
  cache parent, root, Actions workspace and `/mnt` (when present). The original
  `disk_capacity` summary remains the cache/default fallback; `locations` is the
  per-location evidence. `/mnt` availability is not proof of ephemeral storage.
  Only `GITHUB_WORKSPACE` is read from the environment, as a validated absolute
  path (no NUL/control characters, traversal, empty components or >4096 chars).
  The workspace path is never emitted; it is not inferred from the checkout or
  cache location. Custom cache paths and Docker data-root remain unknown.
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
Malformed mount rows are skipped individually; a safe known target from an
invalid row blocks covering reads rather than trusting a less-specific mount.
Table status, valid/invalid row counts and fixed reason enums expose parser gaps
without raw mount paths. Counts are unknown when the table is unavailable.
Cgroup-v2 mapping requires exactly one matching mount at or below
`/sys/fs/cgroup`, and membership equal to/below its root on component boundaries.
A non-global root is subtracted only when that relation is proved; namespace
relative paths are never guessed to be host paths. Diagnostics expose candidate
counts of valid candidates, mapping reason, a root-is-global boolean and a mountpoint category only.
Here global means `/` in the visible mount table, NOT proven host-global ancestry.
Ambiguous, nonmatching, shadowed, unsafe or bounded-out mappings stay unknown.
Directory descriptors are opened component-by-component without following
symlinks; metric reads are anchored to those descriptors and ancestors stop at
the selected mount (at most16 levels). V1 remains uncollected.

Disk statvfs uses similarly anchored local directory descriptors, only when every
path prefix has an unambiguous allowlisted local covering filesystem. NFS/CIFS,
autofs, other/unknown types, symlinks and missing paths remain unknown; no remote
filesystem capacity or connectivity probe is attempted. Paths are at most64
components deep. A mount table failure does not fall back to another proc scope.
These are snapshots, not an atomic guarantee against concurrent mount changes.
Unknown is never zero or unlimited. `memory.events` and PSI
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
