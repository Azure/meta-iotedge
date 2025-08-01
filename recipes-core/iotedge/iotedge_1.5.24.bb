SUMMARY = "The iotedge tool is used to manage the IoT Edge runtime."
HOMEPAGE = "https://aka.ms/iotedge"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \
    file://LICENSE;md5=0f7e3b1308cb5c00b372a6e78835732d \
    file://THIRDPARTYNOTICES;md5=11604c6170b98c376be25d0ca6989d9b \
"

inherit cargo cargo-update-recipe-crates

IOT_IDENTITY_SERVICE_SRCREV = "1e38b9e5295cc09f0fd4c6b810632fd91e0340f5"

# Main source configuration with individual subpaths for iot-identity-service components
SRC_URI += " \
    git://github.com/Azure/iotedge.git;protocol=https;nobranch=1;name=iotedge \
    file://0002-Work-around-Rust-1.78-dead_code-lint-issues.patch \
    file://0001-Use-panic-unwind-for-cross-compilation-compatibility.patch \
"
SRCREV_FORMAT = "iotedge"

#Version 1.5.24
SRCREV_iotedge = "cc03778adadd4bce84b99241e5649eed82ebdeb9"

S = "${WORKDIR}/git"
CARGO_SRC_DIR = "edgelet"
CARGO_BUILD_FLAGS += "-p iotedge"
CARGO_LOCK_SRC_DIR = "${S}/edgelet"

DEPENDS += "openssl pkgconfig-native aziotctl"
RDEPENDS:${PN} += "aziotctl"

export VERSION = "${PV}"

# OpenSSL cross-compilation configuration
export OPENSSL_DIR = "${STAGING_DIR_HOST}${prefix}"
export OPENSSL_LIB_DIR = "${STAGING_DIR_HOST}${libdir}"
export OPENSSL_INCLUDE_DIR = "${STAGING_DIR_HOST}${includedir}"
export PKG_CONFIG_ALLOW_CROSS = "1"

# Target-specific OpenSSL environment variables
export AARCH64_POKY_LINUX_GNU_OPENSSL_DIR = "${STAGING_DIR_HOST}${prefix}"
export AARCH64_POKY_LINUX_GNU_OPENSSL_LIB_DIR = "${STAGING_DIR_HOST}${libdir}"
export AARCH64_POKY_LINUX_GNU_OPENSSL_INCLUDE_DIR = "${STAGING_DIR_HOST}${includedir}"

# Get SRCREV, SRC_URI, and Extra cargo paths for iot-identity-service
# Version 1.5.6
IOT_IDENTITY_SERVICE_SRCREV = "833381accec8d53436cac20fc3fb85303e4504eb"
require iot-identity-service.inc

export LIBIOTHSM_NOBUILD = "On"
export SOCKET_DIR = "/run/aziot"
export USER_AZIOTID = "aziotid"
export USER_AZIOTCS = "aziotcs"
export USER_AZIOTKS = "aziotks"
export USER_AZIOTTPM = "aziottpm"

require ${BPN}-crates.inc
