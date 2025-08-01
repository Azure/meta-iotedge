SUMMARY = "aziot-keys is the default implementation of cryptographic operations used by the Keys Service."
HOMEPAGE = "https://azure.github.io/iot-identity-service/"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \
    file://LICENSE;md5=4f9c2c296f77b3096b6c11a16fa7c66e \
"

inherit cargo pkgconfig cargo-update-recipe-crates

SRC_URI = " \
    git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;tag=${PV} \
    file://0001-Remove-panic.patch \
"
S = "${WORKDIR}/git"
CARGO_SRC_DIR = "key/aziot-keys"

DEPENDS += "openssl virtual/docker pkgconfig"
RDEPENDS:${PN} += "docker "

export VERSION = "${PV}"

# Include auto-generated crate dependencies
require ${BPN}-crates.inc
