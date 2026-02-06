SUMMARY = "The iotedge tool is used to manage the IoT Edge runtime."
HOMEPAGE = "https://aka.ms/iotedge"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \
    file://LICENSE;md5=0f7e3b1308cb5c00b372a6e78835732d \
    file://THIRDPARTYNOTICES;md5=11604c6170b98c376be25d0ca6989d9b \
"

inherit cargo cargo-update-recipe-crates

SRC_URI += "git://github.com/Azure/iotedge.git;protocol=https;nobranch=1"
SRCREV = "2dfe54c62398403cf4d7c908625196b4a1834385"
S = "${WORKDIR}/git"
CARGO_SRC_DIR = "edgelet"
CARGO_BUILD_FLAGS += "-p iotedge"
CARGO_LOCK_SRC_DIR = "${S}/edgelet"
do_compile[network] = "1"

require ${BPN}-crates.inc
require recipes-core/iot-identity-service.inc

include iotedge-${PV}.inc
include iotedge.inc
