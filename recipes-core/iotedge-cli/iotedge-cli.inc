DEPENDS += "openssl10"

export BUILD_SOURCEVERSION="${SRCREV}"
export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"
export OpenSSLDir = "${STAGING_EXECPREFIXDIR}"
export OPENSSL_ROOT_DIR = "${STAGING_EXECPREFIXDIR}"

do_install () {
    # Binaries
    install -d  "${D}${bindir}"

    install -m 755 "${EDGELETDIR}/target/${CARGO_TARGET_SUBDIR}/iotedge" ${D}${bindir}/iotedge
}

