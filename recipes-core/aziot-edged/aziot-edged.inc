DEPENDS += "openssl virtual/docker iotedge aziotd"
RDEPENDS_${PN} += "docker iotedge aziotd"

inherit systemd

SYSTEMD_AUTO_ENABLE_${PN} = "enable"
SYSTEMD_SERVICE_${PN} = "aziot-edged.service"

SRC_URI += "file://aziot-edged.service  \
"

do_install () {
    # Binaries
    install -d  "${D}${bindir}"
    install -m 755 "${WORKDIR}/build/target/${TARGET_SYS}/release/aziot-edged" ${D}${bindir}/aziot-edged

    # Config file
    install -d "${D}${sysconfdir}/aziot"
    install -d "${D}${sysconfdir}/aziot/edged"
    install -d "${D}${sysconfdir}/aziot/edged/config.d"

    # Data dir
    install -d -o iotedge -g iotedge "${D}${localstatedir}/lib/iotedge"

    if ${@bb.utils.contains('DISTRO_FEATURES', 'systemd', 'true', 'false', d)}; then
        install -d ${D}${systemd_unitdir}/system
        install -m 644 ${WORKDIR}/aziot-edged.service ${D}${systemd_unitdir}/system
        install -m 644 ${WORKDIR}/git/edgelet/contrib/systemd/debian/aziot-edged.workload.socket ${D}${systemd_unitdir}/system
        install -m 644 ${WORKDIR}/git/edgelet/contrib/systemd/debian/aziot-edged.mgmt.socket ${D}${systemd_unitdir}/system
    else
        install -d ${D}${sysconfdir}/init.d
        install -m 755 ${WORKDIR}/aziot-edged-${PV}/contrib/debian/aziot-edged.init ${D}${sysconfdir}/init.d/aziot-edged
    fi
}

inherit useradd
USERADD_PACKAGES = "${PN}"
USERADD_PARAM_${PN} = "-r -u 15580 -g iotedge -G docker -s /bin/false -d ${localstatedir}/lib/iotedge iotedge"
GROUPADD_PARAM_${PN} = "-r -g 15580 iotedge"

FILES_${PN} += " \
    ${systemd_unitdir}/system/* \
    ${localstatedir}/lib/iotedge \
    ${sysconfdir}/aziot/ \
    "