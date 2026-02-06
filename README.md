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
* The `kirkstone` branch is frozen at IoT Edge 1.4.27 and will not receive further updates.
* Use the templates in `conf/templates/kirkstone` on the **main** branch for IoT Edge 1.5.x on Kirkstone.
* The Kirkstone templates and recipes are validated, but ongoing CI coverage is Scarthgap only.


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
| Kirkstone | 1.4.x | kirkstone (frozen) | Not active and Not maintained |
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

The default and Kirkstone templates include conservative settings to improve build reliability
across varying machines and networks:

- `BB_FETCH_RETRIES` and `BB_FETCH_TIMEOUT` to retry network fetches.
- `BB_HASHSERVE = ""` to disable hashserv (avoids socket/connect failures in Codespaces).
- `DL_DIR`/`SSTATE_DIR` set to `/workspaces/yocto-cache` (override for non-container hosts).

**Kirkstone-specific:** The Kirkstone template uses `meta-rust` for Rust 1.78+ (Poky Kirkstone only has Rust 1.59)
and masks Poky's built-in rust recipes via `BBMASK`. The `fetch.sh` script automatically clones meta-rust
when fetching Kirkstone layers.

Validation helpers
==================

- `scripts/validate-qemu.sh` boots a QEMU image and validates IoT Edge installation:
  - Checks `iotedge --version` and service status over SSH
  - Uses mock config by default (all services start, connectivity errors expected)
  - Use `--no-mock-config` when testing with a real Azure IoT Hub configuration


FAQ / Known Issues
==================

**Running without a TPM module**

On devices without a TPM, `aziot-tpmd` will fail to start. To disable it, add the following
to a `.bbappend` file or your machine configuration:

```
SYSTEMD_SERVICE:${PN}:remove:my-machine = "aziot-tpmd.service"
```

Replace `my-machine` with your `MACHINE` name. See [#149](https://github.com/Azure/meta-iotedge/issues/149).

**ARM32 time_t ABI mismatch (e.g. STM32MP1)**

On 32-bit ARM targets where OpenSSL is compiled with `_TIME_BITS=64`, the Rust `libc` crate
(< 0.2.179) still uses 32-bit `time_t`, causing certificate timestamp corruption. Workaround:
remove `-D_TIME_BITS=64` from OpenSSL flags. Fix: update the vendored `libc` crate to >= 0.2.179
and set `RUST_LIBC_UNSTABLE_GNU_TIME_BITS=64`. See [#187](https://github.com/Azure/meta-iotedge/issues/187).

**Static UIDs for aziotd users**

The recipes currently create system users with dynamic UIDs via `useradd`. If you need static UIDs
(e.g. for A/B partition schemes or `[[principal]]` config references), override `USERADD_PARAM` in
a `.bbappend` with explicit `-u <uid>` flags. See [#130](https://github.com/Azure/meta-iotedge/issues/130).

**Overriding `do_install:append` in recipes**

The `aziot-edged.inc` and `aziotd.inc` recipes use `do_install:append` (rather than `do_install`)
so that the base `cargo` class handles the binary installation first, and the append adds config
files, systemd units, and directory setup. To customize install paths (e.g. moving data dirs from
`${localstatedir}` to `${sysconfdir}`), create a `.bbappend` that defines your own
`do_install:append` — it will run after the layer's append. Alternatively, override `do_install`
entirely in your `.bbappend` if you need full control. See [#181](https://github.com/Azure/meta-iotedge/issues/181).

**Kirkstone and meta-rust**

Kirkstone templates intentionally use `meta-rust` to provide Rust 1.78+ (Poky Kirkstone ships
Rust 1.59, which is too old for IoT Edge 1.5). This is not required for Scarthgap. The `fetch.sh`
script clones meta-rust automatically when targeting Kirkstone.


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
