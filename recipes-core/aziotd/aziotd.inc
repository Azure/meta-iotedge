DEPENDS += "openssl virtual/docker tpm2-tss clang"
RDEPENDS_${PN} += "docker"
TOOLCHAIN = "clang"

inherit systemd 

SYSTEMD_PACKAGES = "${@bb.utils.contains('DISTRO_FEATURES', 'systemd', '${PN}', '', d)}"
SYSTEMD_AUTO_ENABLE_${PN} = "enable"
SYSTEMD_SERVICE_${PN} = "aziot-certd.service "
SYSTEMD_SERVICE_${PN} += "aziot-identityd.service "
SYSTEMD_SERVICE_${PN} += "aziot-keyd.service "
SYSTEMD_SERVICE_${PN} += "aziot-tpmd.service "

SRC_URI += "file://aziot-certd.service \
            file://aziot-identityd.service \
            file://aziot-keyd.service \
            file://aziot-tpmd.service \
            file://keys.generated.rs \
"

# Copy keys.generated.rs
do_deploy () {
    install -m 644 ${WORKDIR}/keys.generated.rs ${WORKDIR}/git/key/aziot-keyd/src/keys.generated.rs
}
addtask deploy after do_install

do_install () {
    # Binaries
    install -d "${D}${bindir}"
    install -m 755 "${WORKDIR}/build/target/${TARGET_SYS}/release/aziotd" ${D}${bindir}/aziotd
    install -d ${D}${systemd_unitdir}/system

    # Create symbolic links
    ln -s ${bindir}/aziotd ${D}${bindir}/aziot-certd
    ln -s ${bindir}/aziotd ${D}${bindir}/aziot-identityd
    ln -s ${bindir}/aziotd ${D}${bindir}/aziot-keyd
    ln -s ${bindir}/aziotd ${D}${bindir}/aziot-tpmd

    # Install all folders
    install -d "${D}${sysconfdir}/aziot"
    install -d -m 0700 ${D}${sysconfdir}/aziot/certd/config.d
    install -d -m 0700 ${D}${sysconfdir}/aziot/identityd/config.d
    install -d -m 0700 ${D}${sysconfdir}/aziot/keyd/config.d
    install -d -m 0700 ${D}${sysconfdir}/aziot/tpmd/config.d

    # Configuration files
    install -m 644 ${WORKDIR}/git/cert/aziot-certd/config/unix/default.toml ${D}${sysconfdir}/aziot/certd/config.toml.default
    install -m 644 ${WORKDIR}/git/identity/aziot-identityd/config/unix/default.toml ${D}${sysconfdir}/aziot/identityd/config.toml.default
    install -m 644 ${WORKDIR}/git/key/aziot-keyd/config/unix/default.toml ${D}${sysconfdir}/aziot/keyd/config.toml.default
    install -m 644 ${WORKDIR}/git/tpm/aziot-tpmd/config/unix/default.toml ${D}${sysconfdir}/aziot/tpmd/config.toml.default
    install -m 644 ${WORKDIR}/git/aziotctl/config/unix/template.toml ${D}${sysconfdir}/aziot/config.toml.template

    # Install all required services
    install -m 644 ${WORKDIR}/aziot-certd.service ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/git/cert/aziot-certd/aziot-certd.socket ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/aziot-identityd.service ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/git/identity/aziot-identityd/aziot-identityd.socket ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/aziot-keyd.service ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/git/key/aziot-keyd/aziot-keyd.socket ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/aziot-tpmd.service ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/git/tpm/aziot-tpmd/aziot-tpmd.socket ${D}${systemd_unitdir}/system
}

inherit useradd
USERADD_PACKAGES = "${PN}"
USERADD_PARAM_${PN} = "-r -s /bin/false aziotid; "
USERADD_PARAM_${PN} += "-r -s /bin/false aziotcs; "
USERADD_PARAM_${PN} += "-r -s /bin/false aziotks; "
USERADD_PARAM_${PN} += "-r -s /bin/false aziottpm; "

FILES_${PN} += " \
    ${systemd_unitdir}/system/* \
    ${bindir}/aziot-* \
    ${localstatedir}/lib/aziotid \
   "