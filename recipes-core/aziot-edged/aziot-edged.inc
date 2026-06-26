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
    # file:// SRC_URI assets unpack into the recipe's unpack root, which differs
    # by Yocto release: Scarthgap unpacks to ${WORKDIR}, Wrynose (6.0) to
    # ${UNPACKDIR} (= ${WORKDIR}/sources). ${UNPACK_ROOT} (defined in the shared
    # iot-identity-service.inc, required by this recipe) resolves to whichever
    # one applies.
    install -m 644 ${UNPACK_ROOT}/aziot-edged.service ${D}${systemd_unitdir}/system
    install -m 644 ${S}/edgelet/contrib/systemd/debian/aziot-edged.workload.socket ${D}${systemd_unitdir}/system
    install -m 644 ${S}/edgelet/contrib/systemd/debian/aziot-edged.mgmt.socket ${D}${systemd_unitdir}/system

    #Creates /var/run/iotedge as 755, iotedge:iotedge via systemd-tmpfiles.setup.service
    install -d ${D}${sysconfdir}/tmpfiles.d
    install -m 644 ${UNPACK_ROOT}/iotedge.conf ${D}${sysconfdir}/tmpfiles.d/iotedge.conf
}

inherit useradd
USERADD_PACKAGES = "${PN}"

# Optionally pin the iotedge user/group to a static UID/GID.
#
# Static IDs are required for stable [[principal]] config references and make
# A/B partition upgrades deterministic, but switching an already-deployed device
# from a dynamically-allocated ID to a static one changes the on-disk ownership
# of persisted data under ${localstatedir}/lib/aziot, which must then be chowned.
# To avoid surprising existing integrators, this is opt-in and defaults off
# (legacy dynamic allocation). Set IOTEDGE_STATIC_UIDS = "1" in your distro or
# local.conf to enable. See https://github.com/Azure/meta-iotedge/issues/130
IOTEDGE_STATIC_UIDS ??= "0"
IOTEDGE_UID_IOTEDGE = "${@'-u 13620 ' if d.getVar('IOTEDGE_STATIC_UIDS') == '1' else ''}"
IOTEDGE_GID_IOTEDGE = "${@'-g 13620 ' if d.getVar('IOTEDGE_STATIC_UIDS') == '1' else ''}"

USERADD_PARAM:${PN} = "-r ${IOTEDGE_UID_IOTEDGE}-g iotedge -c 'iotedge user' -G docker,systemd-journal,aziotcs,aziotks,aziottpm,aziotid -s /sbin/nologin -d ${localstatedir}/lib/aziot/edged iotedge; "
# edgeagentuser/edgehubuser have been statically pinned since before the optional
# flag existed; left unchanged to avoid a regression for existing builds.
USERADD_PARAM:${PN} += "-r -g iotedge -c 'edgeAgent user' -s /bin/sh -u 13622 edgeagentuser; "
USERADD_PARAM:${PN} += "-r -g iotedge -c 'edgeHub user' -s /bin/sh -u 13623 edgehubuser; "
# Create both iotedge and docker groups - docker group is needed for iotedge user supplementary groups
# iotedge GID is static only when IOTEDGE_STATIC_UIDS = "1"; docker group left dynamic (shared with other layers)
GROUPADD_PARAM:${PN} = "-r ${IOTEDGE_GID_IOTEDGE}iotedge; -r docker"

FILES:${PN} += " \
    ${systemd_unitdir}/system/* \
    ${localstatedir}/lib/ \
    ${sysconfdir}/aziot/ \
    "
