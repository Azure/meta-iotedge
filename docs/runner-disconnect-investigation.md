# Investigating self-hosted Yocto runner disconnects

This is a **concurrency/storage mitigation and evidence-collection experiment**, not a
confirmed root-cause fix. Lost communication can reflect host resource pressure,
runner/service faults, network interruption, or provider VM lifecycle events.
A passing retry alone does not distinguish these causes.

## CI-only concurrency limits

The build job opts in with `CI_YOCTO_RESOURCE_LIMITS=1`. After `oe-init-build-env`
creates `build/conf/local.conf`, and before the first recipe parse, the wrapper
adds an idempotent CI block:

```bitbake
BB_NUMBER_THREADS = "4"
PARALLEL_MAKE = "-j4"
BB_NUMBER_PARSE_THREADS = "4"
```

After parsing, `bitbake -e` verifies all three effective values before provider
verification and compilation. Only those three values are printed; the rest of
the BitBake environment is not dumped. A mismatch fails the build, rather than
silently running at unrestricted concurrency. Ordinary developer builds do not
opt in, and committed templates remain unchanged. Four tasks and four compiler
jobs do not impose an exact process, CPU, or memory cap.

The reusable workflow can check out an explicit older ref. If that ref predates
the resource-monitor script, the workflow warns and runs that ref's original
build/QEMU tooling. Such a run is **not** evidence that this mitigation was
applied. Supported historical-ref/preflight constraints otherwise remain unchanged.

## Local cache placement experiment

The default host bind source is now `/mnt/yocto-cache`, rather than
`/var/cache/yocto`, with the existing `vars.YOCTO_CACHE_PATH` override retained.
The container destination remains `/workspaces/yocto-cache`. This is **local
per-VM capacity**, not shared or durable cross-agent storage. No old cache is
migrated, cleared or deleted; cache ownership preparation is unchanged.

The fresh-host preflight in run `40030226512` observed local ext4 capacity of
66,404,147,200 bytes on root/cache-parent versus 269,425,381,376 bytes on `/mnt`
and the workspace. The default cache directory did not yet exist. That snapshot
motivates testing the larger volume; it is not evidence of disk exhaustion on
a failed runner, nor proof of placement on a future agent. Image, concurrency,
cache configuration, local build `TMPDIR`, templates, build/QEMU checks and
artifact acceptance are unchanged. No RAM cap is included.

Each monitor sample adds `stat`/`statvfs` numeric capacity, free/available bytes,
inodes, UID/GID and mode for only `container_root`, the current repository
(`workspace`), and `cache`. Read errors are `unknown` with numeric errno, not
zero. A workspace/cache same-device comparison is boolean, or null if unknown;
no disk paths, device identifiers, raw mount sources or cache contents are
emitted. `container_root` is **not host root**. The comparison alone does not
identify the host bind source or establish durability.

Compact `resource-monitor disk:` JSON lines show available bytes/inodes at START
and END, plus at most one periodic line per minute (on the existing sampling
cadence). Artifact sampling retains its original cadence and size cap. Console
and artifact I/O failures are best effort and must not replace the command's
exit status. Partial live logs may retain early evidence even if a disconnect
prevents END and artifact upload; samples can miss short-lived exhaustion.

For each experimental leg, record the checked-out source SHA, actual pulled
image digest, initial cache status and BitBake `Sstate summary` Local/Mirrors/
Missed counts. Compare the **observed container-visible capacity and device
comparison** with that agent's known filesystem layout; do not assume the new
default applied, because a repository/organization override may still select
another source. These metrics cannot prove the exact host bind source; leave it
unverified without host evidence. A new default directory can mean a cold cache,
so this is not a controlled warm-cache A/B comparison. Require repeated full
build/QEMU acceptance and correlated host evidence before claiming reliability
improvement or a historical cause.

## Resource evidence

Build and QEMU commands run through `scripts/ci-resource-monitor.py`, retaining
live command output and failure status, with no automatic retries. Each matrix
leg attempts an `always()` upload of `runner-diagnostics-<template>`, retained
for seven days. Diagnostic upload failure is non-blocking; package and image
artifact requirements remain strict.

The monitor samples container-visible memory/load, CPU/memory/I/O pressure, and
available current-cgroup-v2 counters, including memory usage/peak/limit and OOM
events. It records elapsed time and command result. Unsupported, missing or
unreadable telemetry is reported rather than represented as zero. Output is
bounded. No environment dump, process command lines, credential files, host
mounts, or recursive log collection is added.

**Scope matters:** `/proc` may expose shared kernel-wide values, while cgroup
counters describe the visible container cgroup. These are not the host GitHub
runner's `_diag` files and cannot by themselves establish host health. A hard
host loss may prevent the final sample, summary, and artifact upload entirely.

## Evaluation and escalation

1. Confirm the effective 4/`-j4`/4 values in each matrix leg's log.
2. Require complete build, QEMU validation and normal artifact checks across
   Scarthgap, Wrynose, and Scarthgap-1.6, not only fast regressions.
3. Compare duration, sampled memory/pressure and OOM-counter changes across
   repeated runs. A sampled peak can miss short spikes; kernel `memory.peak`
   may cover more than a single monitored command.
4. If a disconnect recurs, correlate the exact attempt/job/runner identity and
   timestamps with pool-owner evidence: runner `_diag`, kernel OOM/service logs,
   network events, and 1ES VM lifecycle records. Missing diagnostics are a gap,
   not proof that resource pressure was absent.

No container resource caps, runner/image version changes, 1ES holds/debug
profiles, pool changes, or retry automation are included. If needed, evaluate
container limits as a separate measured experiment after confirming host size
and headroom. Do not claim a permanent fix from one green run.

References:
- https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/monitor-and-troubleshoot
- https://docs.github.com/en/actions/how-tos/monitor-workflows/enable-debug-logging
- https://docs.yoctoproject.org/dev/dev-manual/limiting-resources.html
