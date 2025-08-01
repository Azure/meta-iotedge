SUMMARY = "aziot-keys is the default implementation of cryptographic operations used by the Keys Service."
HOMEPAGE = "https://azure.github.io/iot-identity-service/"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \
    file://LICENSE;md5=4f9c2c296f77b3096b6c11a16fa7c66e \
"

inherit cargo pkgconfig cargo-update-recipe-crates

SRC_URI = "\ 
    git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;tag=${PV} \
    file://0001-Remove-panic.patch \
"
S = "${WORKDIR}/git"
CARGO_SRC_DIR = "aziotctl"

DEPENDS += "openssl virtual/docker"
RDEPENDS:${PN} += "docker"

export VERSION = "${PV}"
export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"
export SOCKET_DIR="/run/aziot"
export USER_AZIOTID="aziotid"
export USER_AZIOTCS="aziotcs"
export USER_AZIOTKS="aziotks"
export USER_AZIOTTPM="aziottpm"

# Include auto-generated crate dependencies
require ${BPN}-crates.inc
