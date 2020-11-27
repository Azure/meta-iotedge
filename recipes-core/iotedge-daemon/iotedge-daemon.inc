DEPENDS += "openssl10 docker virtual/libiothsm"
RDEPENDS_${PN} += "virtual/libiothsm docker"
INSANE_SKIP_${PN} += "dev-deps"

export SYSROOT = "${STAGING_DIR_HOST}"
export OpenSSLDir = "${STAGING_EXECPREFIXDIR}"
export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"
export OPENSSL_ROOT_DIR = "${STAGING_EXECPREFIXDIR}"
export OPENSSL_INCLUDE_DIR = "${STAGING_INCDIR}"
export OPENSSL_LIB_DIR = "${STAGING_LIBDIR}"
export BUILD_SOURCEVERSION="${SRCREV}"
export FORCE_NO_UNITTEST="On"
export BUILD_SHARED="On"

inherit systemd update-rc.d

SYSTEMD_PACKAGES = "${@bb.utils.contains('DISTRO_FEATURES', 'systemd', '${PN}', '', d)}"
SYSTEMD_SERVICE_${PN} = "${@bb.utils.contains('DISTRO_FEATURES', 'systemd', 'iotedge.service', '', d)}"
SYSTEMD_AUTO_ENABLE_${PN} = "enable"

INITSCRIPT_PACKAGES += "${@bb.utils.contains('DISTRO_FEATURES','sysvinit','${PN}','',d)}"
INITSCRIPT_NAME_${PN} = "${@bb.utils.contains('DISTRO_FEATURES','sysvinit','iotedge','',d)}"
INITSCRIPT_PARAMS_${PN} = "defaults"

do_install () {
    # Binaries
    install -d  "${D}${bindir}"
    install -m 755 "${WORKDIR}/git/edgelet/target/${CARGO_TARGET_SUBDIR}/iotedged" ${D}${bindir}/iotedged

    # Config file
    install -d "${D}${sysconfdir}/iotedge"
    install -m 400 -o iotedge -g iotedge "${WORKDIR}/git/edgelet/contrib/config/linux/debian/config.yaml" ${D}${sysconfdir}/iotedge/config.yaml

    # Data dir
    install -d -o iotedge -g iotedge "${D}${localstatedir}/lib/iotedge"

    if ${@bb.utils.contains('DISTRO_FEATURES', 'systemd', 'true', 'false', d)}; then
        install -d ${D}${systemd_unitdir}/system
        install -m 644 ${WORKDIR}/git/edgelet/contrib/systemd/debian/iotedge.service ${D}${systemd_unitdir}/system
        install -m 644 ${WORKDIR}/git/edgelet/contrib/systemd/debian/iotedge.socket ${D}${systemd_unitdir}/system
        install -m 644 ${WORKDIR}/git/edgelet/contrib/systemd/debian/iotedge.mgmt.socket ${D}${systemd_unitdir}/system
    else
        install -d ${D}${sysconfdir}/init.d
        install -m 755 ${WORKDIR}/git/edgelet/contrib/debian/iotedge.init ${D}${sysconfdir}/init.d/iotedge
    fi
}

inherit useradd
USERADD_PACKAGES = "${PN}"
SERVICE_USER_ID ?= "15580"

USERADD_PARAM_${PN} = "-r -u ${SERVICE_USER_ID} -g iotedge -G docker -s /bin/false -d ${localstatedir}/lib/iotedge iotedge"
GROUPADD_PARAM_${PN} = "-r -g ${SERVICE_USER_ID} iotedge"

FILES_${PN} += " \
    ${systemd_unitdir}/system/* \
    ${localstatedir}/lib/iotedge \
    "
