DEPENDS += "openssl virtual/docker iotedge aziotd systemd"
RDEPENDS_${PN} += "docker iotedge aziotd aziot-keys systemd"

inherit systemd

SYSTEMD_AUTO_ENABLE_${PN} = "enable"
SYSTEMD_SERVICE_${PN} = "aziot-edged.service"


SRC_URI += "file://aziot-edged.service \
            file://0001-Change-panic-strategy-to-unwind.patch \
"

do_install () {
    # Binaries
    install -d ${D}${bindir}
    install -m 755 ${WORKDIR}/build/target/${TARGET_SYS}/release/aziot-edged ${D}${bindir}/aziot-edged

    # Create symbolic links
    install -d ${D}${libexecdir}/aziot
    ln -s ${bindir}/aziot-edged ${D}${libexecdir}/aziot/aziot-edged

    # Config file
    install -d ${D}${sysconfdir}/aziot
    install -d ${D}${sysconfdir}/aziot/edged
    install -d -m 700 -o iotedge -g iotedge ${D}${sysconfdir}/aziot/edged/config.d

    # Data dir
    install -d ${D}${localstatedir}/lib
    install -d ${D}${localstatedir}/log
    install -d ${D}${localstatedir}/lib/aziot
    install -d ${D}${localstatedir}/log/aziot
    install -d -m 755 -o iotedge -g iotedge ${D}${localstatedir}/lib/aziot/edged
    install -d -m 755 -o iotedge -g iotedge ${D}${localstatedir}/log/aziot/edged

    install -d ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/aziot-edged.service ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/git/edgelet/contrib/systemd/debian/aziot-edged.workload.socket ${D}${systemd_unitdir}/system
    install -m 644 ${WORKDIR}/git/edgelet/contrib/systemd/debian/aziot-edged.mgmt.socket ${D}${systemd_unitdir}/system

}

inherit useradd
USERADD_PACKAGES = "${PN}"
USERADD_PARAM_${PN} = "-r -g iotedge -c 'iotedge user' -G docker,systemd-journal,aziotcs,aziotks,aziottpm,aziotid -s /sbin/nologin -d ${localstatedir}/lib/aziot/edged iotedge; "
USERADD_PARAM_${PN} += "-r -g iotedge -c 'edgeAgent user' -s /bin/sh -u 13622 edgeagentuser; "
USERADD_PARAM_${PN} += "-r -g iotedge -c 'edgeHub user' -s /bin/sh -u 13623 edgehubuser; "
GROUPADD_PARAM_${PN} = "-r iotedge"

FILES_${PN} += " \
    ${systemd_unitdir}/system/* \
    ${localstatedir}/lib/ \
    ${localstatedir}/log/ \
    ${sysconfdir}/aziot/ \
    "
