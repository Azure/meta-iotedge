meta-iotedge
===========

This layer provides support for building [IoT Edge](https://github.com/azure/iotedge) with [Yocto](https://www.yoctoproject.org/).

Please see the corresponding sections below for details.

Adding the meta-iotedge layer to your build
=================================================

Use the branch of `meta-iotedge` corresponding to your Yocto release:

* [Sumo](https://github.com/Azure/meta-iotedge/tree/sumo) - `git clone -b sumo https://github.com/Azure/meta-iotedge.git`
* [Thud](https://github.com/Azure/meta-iotedge/tree/thud) - `git clone -b thud https://github.com/Azure/meta-iotedge.git`
* [Warrior](https://github.com/Azure/meta-iotedge/tree/warrior) - `git clone -b warrior https://github.com/Azure/meta-iotedge.git`
* [Zeus](https://github.com/Azure/meta-iotedge/tree/zeus) - `git clone -b zeus https://github.com/Azure/meta-iotedge.git`
* [Dunfell](https://github.com/Azure/meta-iotedge/tree/dunfell) - `git clone -b dunfell https://github.com/Azure/meta-iotedge.git`

In almost all cases, you should not use the `master` branch of `meta-iotedge` in your image.

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
