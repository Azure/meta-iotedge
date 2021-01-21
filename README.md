meta-iotedge
===========

This layer provides support for building [IoT Edge](https://github.com/azure/iotedge).

Please see the corresponding sections below for details.

Dependencies
------------
This layer depends on:

```
URI: git://github.com/meta-rust/meta-rust.git
branch: master
revision: e4d25b98083bcecb94df6ee189a165d63ede7f3d
prio: default
```

```
URI: git://git.yoctoproject.org/meta-virtualization
branch: dunfell
revision: HEAD
prio: default
```

```
URI: git://github.com/openembedded/openembedded-core.git
branch: dunfell
revision: HEAD
prio: default
```

If you use newer meta-rust and iotedge-{cli,daemon} fail because of:
#![deny(rust_2018_idioms, warnings)]
in various files, then select older than current (1.47.0) version of rust:
RUST_VERSION = "1.41.0"
PREFERRED_VERSION_rust-native ?= "${RUST_VERSION}"
PREFERRED_VERSION_rust-cross-${TARGET_ARCH} ?= "${RUST_VERSION}"
PREFERRED_VERSION_rust-llvm-native ?= "${RUST_VERSION}"
PREFERRED_VERSION_libstd-rs ?= "${RUST_VERSION}"
PREFERRED_VERSION_cargo-native ?= "${RUST_VERSION}"

or work around this issue in source with do_compile_prepend():
find ${WORKDIR}/iotedge-${PV} -name "*.rs" -exec sed -i 's/idioms, warnings)/idioms)/g' {} \;

Adding the meta-iotedge layer to your build
=================================================

Run `bitbake-layers add-layer meta-iotedge`

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
