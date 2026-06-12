DEPENDS += "openssl iotedge aziotd systemd"
RDEPENDS:${PN} += "iotedge aziotd aziot-keys systemd glibc-utils docker"

export SOCKET_DIR = "/run/aziot"

inherit systemd

SYSTEMD_AUTO_ENABLE:${PN} = "enable"
SYSTEMD_SERVICE:${PN} = "aziot-edged.service"


SRC_URI += "file://aziot-edged.service \
            file://iotedge.conf \
"

# Source-compatibility patches are version-specific (the upstream Cargo.toml /
# source layout differs between releases), so each aziot-edged-<ver>.inc adds
# its own patch SRC_URI entries rather than carrying them here in the shared
# include (this lets 1.5.x and 1.6.x recipes coexist on the same branch).

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
    # Wrynose (Yocto 6.0) unpacks file:// SRC_URI entries to ${UNPACKDIR}
    # (= ${WORKDIR}/sources), not ${WORKDIR}.
    install -m 644 ${UNPACKDIR}/aziot-edged.service ${D}${systemd_unitdir}/system
    install -m 644 ${S}/edgelet/contrib/systemd/debian/aziot-edged.workload.socket ${D}${systemd_unitdir}/system
    install -m 644 ${S}/edgelet/contrib/systemd/debian/aziot-edged.mgmt.socket ${D}${systemd_unitdir}/system

    #Creates /var/run/iotedge as 755, iotedge:iotedge via systemd-tmpfiles.setup.service
    install -d ${D}${sysconfdir}/tmpfiles.d
    install -m 644 ${UNPACKDIR}/iotedge.conf ${D}${sysconfdir}/tmpfiles.d/iotedge.conf
}

inherit useradd
USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "-r -u 13620 -g iotedge -c 'iotedge user' -G docker,systemd-journal,aziotcs,aziotks,aziottpm,aziotid -s /sbin/nologin -d ${localstatedir}/lib/aziot/edged iotedge; "
USERADD_PARAM:${PN} += "-r -g iotedge -c 'edgeAgent user' -s /bin/sh -u 13622 edgeagentuser; "
USERADD_PARAM:${PN} += "-r -g iotedge -c 'edgeHub user' -s /bin/sh -u 13623 edgehubuser; "
# Create both iotedge and docker groups - docker group is needed for iotedge user supplementary groups
# Static GID for iotedge group; docker group left dynamic (shared with other layers)
GROUPADD_PARAM:${PN} = "-r -g 13620 iotedge; -r docker"

FILES:${PN} += " \
    ${systemd_unitdir}/system/* \
    ${localstatedir}/lib/ \
    ${sysconfdir}/aziot/ \
    "
