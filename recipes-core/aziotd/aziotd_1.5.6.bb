SUMMARY = "aziotd is the main binary for the IoT Identity Service and related services."
HOMEPAGE = "https://azure.github.io/iot-identity-service/"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \
    file://LICENSE;md5=4f9c2c296f77b3096b6c11a16fa7c66e \
"

inherit cargo cargo-update-recipe-crates pkgconfig

SRC_URI += "gitsm://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1"
SRCREV = "833381accec8d53436cac20fc3fb85303e4504eb"
S = "${WORKDIR}/git"
CARGO_SRC_DIR = "aziotd"

require ${BPN}-crates.inc

include aziotd-${PV}.inc
include aziotd.inc
