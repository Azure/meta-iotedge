SUMMARY = "aziotd is the main binary for the IoT Identity Service and related services."
HOMEPAGE = "https://azure.github.io/iot-identity-service/"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \
    file://LICENSE;md5=4f9c2c296f77b3096b6c11a16fa7c66e \
"

inherit cargo pkgconfig cargo-update-recipe-crates systemd useradd

SRC_URI = " \
    git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;tag=${PV} \
    file://aziot-certd.service \
    file://aziot-identityd.service \
    file://aziot-keyd.service \
    file://aziot-tpmd.service \
    file://keys.generated.rs \
    file://0001-Remove-panic.patch \
"
S = "${WORKDIR}/git"
CARGO_SRC_DIR = "aziotd"

DEPENDS += "openssl virtual/docker aziotctl aziot-keys tpm2-tss clang-native libtss2"
RDEPENDS:${PN} += "docker libtss2 libtss2-mu libtss2-tcti-device aziot-keys"
TOOLCHAIN = "clang"
RUSTFLAGS += "-Clink-arg=-Wl,-rpath,${libdir}/rustlib/${RUST_HOST_SYS}/lib"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"
SYSTEMD_SERVICE:${PN} = "aziot-certd.service "
SYSTEMD_SERVICE:${PN} += "aziot-identityd.service "
SYSTEMD_SERVICE:${PN} += "aziot-keyd.service "
SYSTEMD_SERVICE:${PN} += "aziot-tpmd.service "

export VERSION = "${PV}"

do_install:append  () {
    install -d ${D}${systemd_unitdir}/system

    # Create symbolic links
    ln -s ${bindir}/aziotd ${D}${bindir}/aziot-certd
    ln -s ${bindir}/aziotd ${D}${bindir}/aziot-identityd
    ln -s ${bindir}/aziotd ${D}${bindir}/aziot-keyd
    ln -s ${bindir}/aziotd ${D}${bindir}/aziot-tpmd

    # Install all folders
    install -d ${D}${sysconfdir}/aziot
    install -d -m 700 -o aziotcs -g aziotcs ${D}${sysconfdir}/aziot/certd/config.d
    install -d -m 700 -o aziotid -g aziotid ${D}${sysconfdir}/aziot/identityd/config.d
    install -d -m 700 -o aziotks -g aziotks ${D}${sysconfdir}/aziot/keyd/config.d
    install -d -m 700 -o aziottpm -g aziottpm ${D}${sysconfdir}/aziot/tpmd/config.d

    # Configuration files
    install -m 644 ${WORKDIR}/git/cert/aziot-certd/config/unix/default.toml ${D}${sysconfdir}/aziot/certd/config.toml.default
    install -m 644 ${WORKDIR}/git/identity/aziot-identityd/config/unix/default.toml ${D}${sysconfdir}/aziot/identityd/config.toml.default
    install -m 644 ${WORKDIR}/git/key/aziot-keyd/config/unix/default.toml ${D}${sysconfdir}/aziot/keyd/config.toml.default
    install -m 644 ${WORKDIR}/git/tpm/aziot-tpmd/config/unix/default.toml ${D}${sysconfdir}/aziot/tpmd/config.toml.default
    install -m 644 ${WORKDIR}/git/aziotctl/config/unix/template.toml ${D}${sysconfdir}/aziot/config.toml.template

    # Data dir
    install -d ${D}${localstatedir}/lib
    install -d ${D}${localstatedir}/lib/aziot
    install -d -m 700 -o aziotks -g aziotks ${D}${localstatedir}/lib/aziot/keyd
    install -d -m 700 -o aziotcs -g aziotcs ${D}${localstatedir}/lib/aziot/certd
    install -d -m 700 -o aziotid -g aziotid ${D}${localstatedir}/lib/aziot/identityd
    install -d -m 700 -o aziottpm -g aziottpm ${D}${localstatedir}/lib/aziot/tpmd


    # Install all required services
    install -m 644 ${WORKDIR}/aziot-certd.service ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/aziot-identityd.service ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/aziot-keyd.service ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/aziot-tpmd.service ${D}${systemd_unitdir}/system

    install -m 644 ${WORKDIR}/git/cert/aziot-certd/aziot-certd.socket.in ${D}${systemd_unitdir}/system/aziot-certd.socket
    install -m 644 ${WORKDIR}/git/identity/aziot-identityd/aziot-identityd.socket.in ${D}${systemd_unitdir}/system/aziot-identityd.socket
    install -m 644 ${WORKDIR}/git/key/aziot-keyd/aziot-keyd.socket.in ${D}${systemd_unitdir}/system/aziot-keyd.socket
    install -m 644 ${WORKDIR}/git/tpm/aziot-tpmd/aziot-tpmd.socket.in ${D}${systemd_unitdir}/system/aziot-tpmd.socket

    sed -i \
        -e "s|@user_aziotid@|${USER_AZIOTID}|" \
                -e "s|@user_aziotks@|${USER_AZIOTKS}|" \
                -e "s|@user_aziotcs@|${USER_AZIOTCS}|" \
                -e "s|@user_aziottpm@|${USER_AZIOTTPM}|" \
                -e "s|@socket_dir@|${SOCKET_DIR}|" \
        ${D}${systemd_unitdir}/system/aziot-certd.socket \
        ${D}${systemd_unitdir}/system/aziot-identityd.socket \
        ${D}${systemd_unitdir}/system/aziot-keyd.socket \
        ${D}${systemd_unitdir}/system/aziot-tpmd.socket
}

USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "-r -g aziotcs -c 'aziot-certd user' -G aziotks -s /sbin/nologin -d ${localstatedir}/lib/aziot/certd aziotcs; "
USERADD_PARAM:${PN} += "-r -g aziotks -c 'aziot-keyd user' -s /sbin/nologin -d ${localstatedir}/lib/aziot/keyd aziotks; "
USERADD_PARAM:${PN} += "-r -g aziotid -c 'aziot-identityd user' -G aziotcs,aziotks,aziottpm -s /sbin/nologin -d ${localstatedir}/lib/aziot/identityd aziotid; "
USERADD_PARAM:${PN} += "-r -g aziottpm -c 'aziot-tpmd user' -s /sbin/nologin -d ${localstatedir}/lib/aziot/tpmd aziottpm; "

GROUPADD_PARAM:${PN} = "-r aziotcs; "
GROUPADD_PARAM:${PN} += "-r aziotks; "
GROUPADD_PARAM:${PN} += "-r aziotid; "
GROUPADD_PARAM:${PN} += "-r aziottpm; "

export SOCKET_DIR="/run/aziot"
export USER_AZIOTID="aziotid"
export USER_AZIOTCS="aziotcs"
export USER_AZIOTKS="aziotks"
export USER_AZIOTTPM="aziottpm"

FILES:${PN} += " \
    ${systemd_unitdir}/system/* \
    ${bindir}/aziot-* \
    ${localstatedir}/lib/ \
"

# Include auto-generated crate dependencies
require ${BPN}-crates.inc
