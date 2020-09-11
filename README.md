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
revision: d8d77be1292064a02adcb5e72e293604b704f69b
prio: default
```

```
URI: git://git.yoctoproject.org/meta-virtualization
branch: thud
revision: HEAD
prio: default
```

```
URI: git://github.com/openembedded/openembedded-core.git
branch: thud
revision: HEAD
prio: default
```

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
