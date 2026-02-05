meta-iotedge
===========

This layer provides support for building [IoT Edge](https://github.com/azure/iotedge) with [Yocto](https://www.yoctoproject.org/).

Please see the corresponding sections below for details.

Adding the meta-iotedge layer to your build
=================================================

Use the branch of `meta-iotedge` corresponding to your Yocto release:

**Active and maintained**:
* [Scarthgap](https://github.com/Azure/meta-iotedge/tree/main)  - `git clone -b main https://github.com/Azure/meta-iotedge.git`

**Kirkstone (out of support April 2026)**:
* No dedicated branch or CI runs. Use the templates in `conf/templates/kirkstone` on the main branch.
* The kirkstone templates and recipes are validated, but ongoing CI coverage is scarthgap only.


Run `bitbake-layers add-layer meta-iotedge`

**Not active and Not maintained**
* [Dunfell](https://github.com/Azure/meta-iotedge/tree/dunfell) - `git clone -b dunfell https://github.com/Azure/meta-iotedge.git`
* [Sumo](https://github.com/Azure/meta-iotedge/tree/sumo) - `git clone -b sumo https://github.com/Azure/meta-iotedge.git`
* [Thud](https://github.com/Azure/meta-iotedge/tree/thud) - `git clone -b thud https://github.com/Azure/meta-iotedge.git`
* [Warrior](https://github.com/Azure/meta-iotedge/tree/warrior) - `git clone -b warrior https://github.com/Azure/meta-iotedge.git`
* [Zeus](https://github.com/Azure/meta-iotedge/tree/zeus) - `git clone -b zeus https://github.com/Azure/meta-iotedge.git`

Branching Strategy and Timelines
===============================

| Yocto Release | IoT Edge version | Branch Name | Branch Status |
| :- | :- | :- | :- |
| Scarthgap | 1.5.x | main | Active and maintained |
| Kirkstone | 1.5.x | main (templates only) | Out of Support Apr'2026 |
| Kirkstone | 1.4.x | main (templates only) | Out of Support Nov'2024 |
| Dunfell | 1.4.x  | dunfell | Not active and Not maintained |
| Dunfell | 1.1.x  | dunfell-1.1 | Not active and Not maintained |
| Sumo | 1.1.x | sumo | Not active and Not maintained |
| Thud | 1.1.x | thud | Not active and Not maintained |
| Warrior | 1.1.x | warrior | Not active and Not maintained |
| Zeus | 1.1.x | zeus | Not active and Not maintained |

Release process
===============

See the step-by-step guide in [docs/release.md](docs/release.md).

Reliability defaults
====================

The default and kirkstone templates include conservative settings to improve build reliability
across varying machines and networks:

- `BB_FETCH_RETRIES` and `BB_FETCH_TIMEOUT` to retry network fetches.
- `BB_HASHSERVE = ""` to disable hashserv (avoids socket/connect failures in Codespaces).
- `DL_DIR`/`SSTATE_DIR` set to `/workspaces/yocto-cache` (override for non-container hosts).

**Kirkstone-specific:** The kirkstone template uses `meta-rust` for Rust 1.78+ (Poky kirkstone only has Rust 1.59)
and masks Poky's built-in rust recipes via `BBMASK`. The `fetch.sh` script automatically clones meta-rust
when fetching kirkstone layers.

Validation helpers
==================

- `scripts/validate-qemu.sh` boots a QEMU image and validates IoT Edge installation:
  - Checks `iotedge --version` and service status over SSH
  - Uses mock config by default (all services start, connectivity errors expected)
  - Use `--no-mock-config` when testing with a real Azure IoT Hub configuration


Contributing
============

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.microsoft.com.

When you submit a pull request, a CLA-bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
