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
- Resolves IIS SRCREV entries to actual git SHAs (not branch names).

Notes:

- If **only** IoT Edge changes, omit the `--iis-*` flags. The script will automatically
  resolve the latest IIS release tag for SRCREV entries.
- If **only** IoT Identity Service changes, omit the `--iotedge-*` flags.
- The script creates new `*.bb` and `*.inc` files alongside existing versions; it does **not** delete older versions.
- Use `--keep-workdir` to inspect generated files for debugging.

## Validate recipes

After updating recipes, validate that they parse correctly before running a full build:

```bash
# Fetch Yocto layers for the target release
./scripts/fetch.sh scarthgap

# Parse recipes to check for errors (quick validation)
cd poky && source oe-init-build-env && bitbake -p iotedge aziot-edged
```

This validates:
- Recipe syntax is correct
- All SRCREV entries are valid git SHAs (not branch names like "main")
- Dependencies resolve correctly

## Validate build (local or CI)

For a full build validation:

```bash
# Fetch Yocto layers (use Yocto branch name: scarthgap, kirkstone, etc.)
./scripts/fetch.sh scarthgap

# Build recipes (use template name: default, kirkstone, etc.)
./scripts/build.sh default
```

To validate IoT Edge in QEMU:

```bash
./scripts/validate-qemu.sh default
```

### Script parameters

| Script | Parameter | Description | Examples |
|--------|-----------|-------------|----------|
| `fetch.sh` | `<yocto-branch>` | Yocto release branch to fetch | `scarthgap`, `kirkstone` |
| `build.sh` | `<template>` | Build template from `conf/templates/` | `default`, `kirkstone` |
| `validate-qemu.sh` | `<template>` | Template for QEMU validation | `default`, `kirkstone` |

### Branch to template mapping

| Branch | Yocto Release | fetch.sh | build.sh |
|--------|---------------|----------|----------|
| main | Scarthgap | `scarthgap` | `default` |
| kirkstone | Kirkstone | `kirkstone` | `kirkstone` |

### Script explanations

- `scripts/fetch.sh`: clones required Yocto layers (poky, meta-openembedded, etc.) at the specified Yocto branch. Supports optional GitHub mirrors/fallbacks.
- `scripts/build.sh`: runs the containerized build and invokes BitBake for the main IoT Edge targets using the specified template.
- `scripts/containerize.sh`: wraps Docker to run builds consistently and passes timeouts/UID/GID through.
- `scripts/bitbake.sh`: sets up the OE environment and starts BitBake with longer server/client timeouts.

### Devcontainer note

If you reopen the repo in the devcontainer (public Yocto image), `scripts/build.sh` will run
`scripts/bitbake.sh` directly and skip Docker nesting. You can also run bitbake directly:

```bash
export DEVCONTAINER=1
export TEMPLATECONF="meta-iotedge/conf/templates/default"
./scripts/bitbake.sh iotedge aziot-edged
```

### Build notes

- Full Yocto builds can exceed GitHub-hosted runner limits (time/disk). For CI reliability, prefer a **self-hosted runner** with sstate caches.
- Templates set `BB_FETCH_RETRIES` and `BB_FETCH_TIMEOUT` for network robustness, and keep `BB_HASHSERVE = ""` to avoid hashserv socket issues in Codespaces.

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

```bash
./scripts/fetch.sh scarthgap
./scripts/build.sh default
```

This requires Docker, large disk, and enough runtime for full Yocto builds. It is
intended to be used as a PR status check. GitHub-hosted runners may time out.

## End-to-end release checklist

1. **Update recipes**
   ```bash
   ./scripts/update-recipes.sh \
     --iotedge-rev <sha> --iotedge-version <ver> \
     --iis-rev <sha> --iis-version <ver>
   ```

2. **Validate recipe parsing** (quick, ~1 min)
   ```bash
   ./scripts/fetch.sh scarthgap
   cd poky && source oe-init-build-env && bitbake -p iotedge aziot-edged
   ```

3. **Full build validation** (slow, hours)
   ```bash
   ./scripts/build.sh default
   ```

4. **Create PR** targeting the appropriate branch (main for Scarthgap, kirkstone for Kirkstone)

## Troubleshooting

### SRCREV = "main" errors

If BitBake fails with errors about unable to fetch a git revision like "main":

```
ERROR: iotedge: Fetcher failure: Unable to find revision main in branch main
```

This means the recipe has SRCREV entries pointing to branch names instead of commit SHAs.
The `update-recipes.sh` script should automatically fix these, but if updating manually,
ensure all `SRCREV_*` entries are valid 40-character git commit SHAs.

### Recipe parsing errors

Run `bitbake -p <recipe>` to validate recipe syntax without building:

```bash
cd poky && source oe-init-build-env
bitbake -p iotedge aziot-edged
```

### When manual fixes are still needed

Most release steps are automated. Manual intervention may still be required if
upstream changes introduce new build or recipe issues, for example:

- Additional devtool patches (e.g., bindgen for `aziot-keyd`, rustdoc warnings).
- Regenerating missing `SRC_URI` checksums reported by BitBake.
