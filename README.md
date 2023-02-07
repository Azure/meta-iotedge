meta-iotedge
===========

This layer provides support for building [IoT Edge][iotedge] with [Yocto][yocto].

Please see the corresponding sections below for details.

[iotedge]: https://github.com/azure/iotedge
[yocto]: https://www.yoctoproject.org/

Dependencies
------------
This layer depends on:

```
URI: git://github.com/meta-rust/meta-rust.git
branch: master
revision: 1ed669c464a113cddba8222b419565273d3410f2
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

```
URI: git://git.yoctoproject.org/meta-security
branch: dunfell
revision: HEAD
prio: default
```

```
URI: https://github.com/kraj/meta-clang.git
branch: dunfell
revision: HEAD
prio: default
```

Adding the meta-iotedge layer to your build
=================================================

Run `bitbake-layers add-layer meta-iotedge`.

The relevant recipes are:

* `aziot-edged` – contains all required dependencies for IoT Edge and IoT Identity Service
* `aziotctl` – optional CLI tool for IoT Identity Service

Migration from IoT Edge 1.1 LTS
===============================

IoT Edge 1.2 introduced many changes affecting the services which are running,
configuration file locations, and also configuration file format. The changes
are listed in the [IoT Edge Packaging][packaging] document. Additionally, [How
to Update IoT Edge][updating-guide] describes how to migrate existing
installation and configuration.

[packaging]: https://github.com/Azure/iotedge/blob/main/doc/packaging.md
[updating-guide]: https://learn.microsoft.com/azure/iot-edge/how-to-update-iot-edge?view=iotedge-1.4&tabs=ubuntu#special-case-update-from-10-or-11-to-latest-release

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
