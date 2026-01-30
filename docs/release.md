# Yocto + IoT Edge release guide

This guide describes how to update recipes for a new IoT Edge and/or IoT Identity Service release, and how to validate for Scarthgap (main) and Kirkstone (kirkstone).

## Quick summary

- **main** tracks **Scarthgap**.
- **kirkstone** tracks **Kirkstone**.
- Dunfell and earlier are out of support.

## Prerequisites

- Rust toolchain is taken from the upstream repos via their `rust-toolchain.toml`. You **do not** need to pin a specific Rust version in this repo.
- Install cargo-bitbake once:
  - `cargo install --locked cargo-bitbake`

## Release inputs

You need the release commit SHAs for:

- **IoT Edge** repo: https://github.com/Azure/iotedge
- **IoT Identity Service** repo: https://github.com/Azure/iot-identity-service

And the corresponding version numbers (for example, `1.5.21`).

## Update recipes (automated)

Use the helper script in this repo to generate and patch recipes from the upstream repos:

```
./scripts/update-recipes.sh \
  --iotedge-rev <iotedge_sha> --iotedge-version 1.5.21 \
  --iis-rev <iis_sha> --iis-version 1.5.21
```

What it does:

- Generates `*.bb` and `*.inc` via cargo-bitbake for IoT Edge and IoT Identity Service.
- Normalizes cargo sources and registry configuration to crates.io.
- Sets `CARGO_SRC_DIR` for monorepo subpaths where needed.
- Fixes license checksums and applies known recipe patches (e.g., `pkgconfig` inherits).

Notes:

- If **only** IoT Edge changes, omit the `--iis-*` flags.
- If **only** IoT Identity Service changes, omit the `--iotedge-*` flags.
- The script creates new `*.bb` and `*.inc` files alongside existing versions; it does **not** delete older versions.

## Validate (local or CI)

For a full build:

```
./scripts/fetch.sh <template>
./scripts/build.sh <template>
```

Script explanations:

- `scripts/fetch.sh`: clones required Yocto layers (poky, meta-openembedded, etc.) and supports optional GitHub mirrors/fallbacks.
- `scripts/build.sh`: runs the containerized build and invokes BitBake for the main IoT Edge targets.
- `scripts/containerize.sh`: wraps Docker to run builds consistently and passes timeouts/UID/GID through.
- `scripts/bitbake.sh`: sets up the OE environment and starts BitBake with longer server/client timeouts.

Notes:

- Full Yocto builds can exceed GitHub-hosted runner limits (time/disk). For CI reliability, prefer a **self-hosted runner** with sstate caches.
- Use the same `<template>` value for fetch and build (for example: `default`).

## Update meta-rust (if needed)

If the build fails due to Rust version incompatibility:

- Update `METARUST_REV` in builds/checkin.yaml to a commit that adds support for the needed Rust version.

## Branching rules

- **Scarthgap** updates go to **main**.
- **Kirkstone** updates go to **kirkstone**.

Create a PR with the updated recipes and validate as above.

## Automation (GitHub Actions)

The workflow in [.github/workflows/update-recipes.yml](.github/workflows/update-recipes.yml)
can generate updated recipes and open a PR. Trigger it via **Actions → Update Yocto recipes**
with the desired SHAs and versions.

## CI validation (GitHub Actions)

The workflow in [.github/workflows/ci-build.yml](.github/workflows/ci-build.yml)
mimics the Azure DevOps pipeline by running:

```
./scripts/fetch.sh scarthgap
./scripts/build.sh default
```

This requires Docker, large disk, and enough runtime for full Yocto builds. It is
intended to be used as a PR status check. GitHub-hosted runners may time out.

## When manual fixes are still needed

Most release steps are automated. Manual intervention may still be required if
upstream changes introduce new build or recipe issues, for example:

- Additional devtool patches (e.g., bindgen for `aziot-keyd`, rustdoc warnings).
- Regenerating missing `SRC_URI` checksums reported by BitBake.
