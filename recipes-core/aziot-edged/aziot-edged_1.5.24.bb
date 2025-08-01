SUMMARY = "The aziot-edged is the main binary for the IoT edge daemon."
HOMEPAGE = "https://aka.ms/iotedge"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \
    file://LICENSE;md5=0f7e3b1308cb5c00b372a6e78835732d \
    file://THIRDPARTYNOTICES;md5=11604c6170b98c376be25d0ca6989d9b \
"

inherit cargo cargo-update-recipe-crates systemd useradd


# Main source configuration with individual subpaths for iot-identity-service components
SRC_URI += " \
           git://github.com/Azure/iotedge.git;protocol=https;nobranch=1;name=iotedge \
           file://0001-Use-panic-unwind-for-cross-compilation-compatibility.patch \
           file://0002-Work-around-Rust-1.78-dead_code-lint-issues.patch \
           file://aziot-edged.service \
           file://iotedge.conf \
           "
SRCREV_FORMAT = "iotedge"

# Version 1.5.24
SRCREV_iotedge = "cc03778adadd4bce84b99241e5649eed82ebdeb9"

S = "${WORKDIR}/git"
CARGO_SRC_DIR = "edgelet"
CARGO_BUILD_FLAGS += "-p aziot-edged"
CARGO_LOCK_SRC_DIR = "${S}/edgelet"

DEPENDS += "openssl pkgconfig-native virtual/docker iotedge aziotd systemd"
RDEPENDS:${PN} += "docker iotedge aziotd aziot-keys systemd glibc-utils"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"
SYSTEMD_SERVICE:${PN} = "aziot-edged.service"

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

do_install:append () {
    # Create symbolic links
    install -d ${D}${libexecdir}/aziot
    ln -s ${bindir}/aziot-edged ${D}${libexecdir}/aziot/aziot-edged

    # Config file
    install -d ${D}${sysconfdir}/aziot
    install -d ${D}${sysconfdir}/aziot/edged
    install -d -m 700 -o iotedge -g iotedge ${D}${sysconfdir}/aziot/edged/config.d

    # Data dir
    install -d ${D}${localstatedir}/lib
    install -d ${D}${localstatedir}/lib/aziot
    install -d -m 755 -o iotedge -g iotedge ${D}${localstatedir}/lib/aziot/edged

    install -d ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/aziot-edged.service ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/git/edgelet/contrib/systemd/debian/aziot-edged.workload.socket ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/git/edgelet/contrib/systemd/debian/aziot-edged.mgmt.socket ${D}${systemd_unitdir}/system

    #Creates /var/run/iotedge as 755, iotedge:iotedge via systemd-tmpfiles.setup.service
    install -d ${D}${sysconfdir}/tmpfiles.d
    install -m 644 ${WORKDIR}/iotedge.conf ${D}${sysconfdir}/tmpfiles.d/iotedge.conf
}

USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "-r -g iotedge -c 'iotedge user' -G docker,systemd-journal,aziotcs,aziotks,aziottpm,aziotid -s /sbin/nologin -d ${localstatedir}/lib/aziot/edged iotedge; "
USERADD_PARAM:${PN} += "-r -g iotedge -c 'edgeAgent user' -s /bin/sh -u 13622 edgeagentuser; "
USERADD_PARAM:${PN} += "-r -g iotedge -c 'edgeHub user' -s /bin/sh -u 13623 edgehubuser; "
GROUPADD_PARAM:${PN} = "-r iotedge"

export SOCKET_DIR="/run/aziot"
export USER_AZIOTID="aziotid"
export USER_AZIOTCS="aziotcs"
export USER_AZIOTKS="aziotks"
export USER_AZIOTTPM="aziottpm"

FILES:${PN} += " \
    ${systemd_unitdir}/system/* \
    ${localstatedir}/lib/ \
    ${sysconfdir}/aziot/ \
"

# Include auto-generated crate dependencies
require ${BPN}-crates.inc
