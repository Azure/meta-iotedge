DEPENDS += "openssl aziotctl"

export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"
export LIBIOTHSM_NOBUILD="On"

do_install () {
    # Binaries
    install -d  "${D}${bindir}"
    install -m 755 "${WORKDIR}/build/target/${RUST_TARGET_SYS}/release/iotedge" ${D}${bindir}/iotedge
}