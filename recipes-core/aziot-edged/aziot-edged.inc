DEPENDS += "openssl iotedge aziotd systemd"
RDEPENDS:${PN} += "iotedge aziotd aziot-keys systemd glibc-utils"

export SOCKET_DIR="/run/aziot"

inherit systemd

SYSTEMD_AUTO_ENABLE:${PN} = "enable"
SYSTEMD_SERVICE:${PN} = "aziot-edged.service"


SRC_URI += "file://aziot-edged.service \
            file://iotedge.conf \
            file://0001-Remove-git-from-Cargo.patch \
            file://0002-Work-around-Rust-1.78-dead_code-lint-issues.patch \
"

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

inherit useradd
USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "-r -g iotedge -c 'iotedge user' -G docker,systemd-journal,aziotcs,aziotks,aziottpm,aziotid -s /sbin/nologin -d ${localstatedir}/lib/aziot/edged iotedge; "
USERADD_PARAM:${PN} += "-r -g iotedge -c 'edgeAgent user' -s /bin/sh -u 13622 edgeagentuser; "
USERADD_PARAM:${PN} += "-r -g iotedge -c 'edgeHub user' -s /bin/sh -u 13623 edgehubuser; "
# Create both iotedge and docker groups - docker group is needed for iotedge user supplementary groups
GROUPADD_PARAM:${PN} = "-r iotedge; -r docker"

FILES:${PN} += " \
    ${systemd_unitdir}/system/* \
    ${localstatedir}/lib/ \
    ${sysconfdir}/aziot/ \
    "
