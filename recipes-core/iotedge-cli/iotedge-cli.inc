DEPENDS += "openssl10 virtual/libiothsm"
RDEPENDS_${PN} += "virtual/libiothsm"

export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"

export BUILD_SOURCEVERSION="${SRCREV}"

do_install () {
    # Binaries
    install -d  "${D}${bindir}"

    install -m 755 "${EDGELETDIR}/target/${CARGO_TARGET_SUBDIR}/iotedge" ${D}${bindir}/iotedge
}

