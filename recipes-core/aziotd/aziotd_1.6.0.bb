SUMMARY = "aziotd is the main binary for the IoT Identity Service and related services."
HOMEPAGE = "https://azure.github.io/iot-identity-service/"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \
    file://LICENSE;md5=4f9c2c296f77b3096b6c11a16fa7c66e \
"

inherit cargo cargo-update-recipe-crates pkgconfig

SRC_URI += "gitsm://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1"
SRCREV = "a6b1d1628be550ddda8cc65573e509c753b7cb65"
CARGO_SRC_DIR = "aziotd"
# Yocto release-agnostic source dir: mirror the git fetcher so ONE recipe is
# correct on both Yocto lines that build it. git unpacks to
# ${UNPACKDIR:-${WORKDIR}}/${BB_GIT_DEFAULT_DESTSUFFIX:-git}: Scarthgap (5.0)
# leaves both unset -> ${WORKDIR}/git; Wrynose (6.0) sets them -> ${WORKDIR}/
# sources/${BP}. A hardcoded /git breaks Wrynose; omitting S breaks Scarthgap.
S = "${@(d.getVar('UNPACKDIR') or d.getVar('WORKDIR')) + '/' + (d.getVar('BB_GIT_DEFAULT_DESTSUFFIX') or 'git')}"

require ${BPN}-${PV}-crates.inc

include aziotd-${PV}.inc
include aziotd.inc
