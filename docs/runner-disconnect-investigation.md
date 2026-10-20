# Investigating self-hosted Yocto runner disconnects

This is a **concurrency mitigation and evidence-collection experiment**, not a
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
