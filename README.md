meta-iotedge
===========

This layer provides support for building [IoT Edge](https://github.com/azure/iotedge) with [Yocto](https://www.yoctoproject.org/).

Please see the corresponding sections below for details.

Adding the meta-iotedge layer to your build
=================================================

Use the branch of `meta-iotedge` corresponding to your Yocto release:

* [Kirkstone](https://github.com/Azure/meta-iotedge/tree/kirkstone) - `git clone -b kirkstone https://github.com/Azure/meta-iotedge.git`

**Active and maintained**:
* [Dunfell](https://github.com/Azure/meta-iotedge/tree/dunfell) - `git clone -b dunfell https://github.com/Azure/meta-iotedge.git`

Run `bitbake-layers add-layer meta-iotedge`

**Not active and Not maintained**
* [Sumo](https://github.com/Azure/meta-iotedge/tree/sumo) - `git clone -b sumo https://github.com/Azure/meta-iotedge.git`
* [Thud](https://github.com/Azure/meta-iotedge/tree/thud) - `git clone -b thud https://github.com/Azure/meta-iotedge.git`
* [Warrior](https://github.com/Azure/meta-iotedge/tree/warrior) - `git clone -b warrior https://github.com/Azure/meta-iotedge.git`
* [Zeus](https://github.com/Azure/meta-iotedge/tree/zeus) - `git clone -b zeus https://github.com/Azure/meta-iotedge.git`

In almost all cases, you should not use the `main` branch of `meta-iotedge` in your image.

Branching Strategy and Timelines
===============================

| Yocto Release | IoT Edge version | Branch Name | Branch Status |
| :- | :- | :- | :- |
| Kirkstone | 1.4.x | main | Active and maintained |
| Dunfell | 1.4.x  | dunfell | Active and maintained through April 2024 |
| Dunfell | 1.1.x  | dunfell-1.1 | 1.1.x is retired in Dec'22. Not maintained |
| Sumo | 1.1.x | sumo | Not active and Not maintained |
| Thud | 1.1.x | thud | Not active and Not maintained |
| Warrior | 1.1.x | warrior | Not active and Not maintained |
| Zeus | 1.1.x | zeus | Not active and Not maintained |


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
