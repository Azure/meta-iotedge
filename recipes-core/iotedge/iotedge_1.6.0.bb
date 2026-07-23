SUMMARY = "The iotedge tool is used to manage the IoT Edge runtime."
HOMEPAGE = "https://aka.ms/iotedge"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \
    file://LICENSE;md5=0f7e3b1308cb5c00b372a6e78835732d \
    file://THIRDPARTYNOTICES;md5=c613cff9021777004379d01ee4e2aad1 \
"

inherit cargo cargo-update-recipe-crates

SRC_URI += "git://github.com/Azure/iotedge.git;protocol=https;nobranch=1"
SRCREV = "314983eaa92809521518a95631a22d7a9259a3eb"
# Yocto release-agnostic source dir: mirror the git fetcher so ONE recipe is
# correct on both Yocto lines that build it. git unpacks to
# ${UNPACKDIR:-${WORKDIR}}/${BB_GIT_DEFAULT_DESTSUFFIX:-git}: Scarthgap (5.0)
# leaves both unset -> ${WORKDIR}/git; Wrynose (6.0) sets them -> ${WORKDIR}/
# sources/${BP}. A hardcoded /git breaks Wrynose; omitting S breaks Scarthgap.
S = "${@(d.getVar('UNPACKDIR') or d.getVar('WORKDIR')) + '/' + (d.getVar('BB_GIT_DEFAULT_DESTSUFFIX') or 'git')}"
CARGO_SRC_DIR = "edgelet"
CARGO_BUILD_FLAGS += "-p iotedge"
CARGO_LOCK_SRC_DIR = "${S}/edgelet"
do_compile[network] = "1"

require ${BPN}-${PV}-crates.inc
require recipes-core/iot-identity-service.inc

include iotedge-${PV}.inc
include iotedge.inc
