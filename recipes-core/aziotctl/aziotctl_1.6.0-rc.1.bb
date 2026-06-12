SUMMARY = "aziotctl is the CLI tool for the IoT Identity Service."
HOMEPAGE = "https://azure.github.io/iot-identity-service/"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \
    file://LICENSE;md5=4f9c2c296f77b3096b6c11a16fa7c66e \
"

inherit cargo cargo-update-recipe-crates

SRC_URI += "gitsm://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1"
SRCREV = "1a7a6e70c3a20389fd24090bba201b7fdd7de582"
CARGO_SRC_DIR = "aziotctl"

require ${BPN}-${PV}-crates.inc

include aziotctl-${PV}.inc
include aziotctl.inc
