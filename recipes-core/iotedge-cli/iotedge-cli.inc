DEPENDS += "openssl virtual/libiothsm"
RDEPENDS_${PN} += "virtual/libiothsm"

export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"
export LIBIOTHSM_NOBUILD="On"

do_install () {
    # Binaries
    install -d  "${D}${bindir}"
    install -m 755 "${B}/target/${CARGO_TARGET_SUBDIR}/iotedge" ${D}${bindir}/iotedge
}

