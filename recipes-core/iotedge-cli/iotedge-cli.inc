DEPENDS += "openssl"

do_install () {
    # Binaries
    install -d  "${D}${bindir}"
    install -m 755 "${WORKDIR}/iotedge-${PV}/edgelet/target/${CARGO_TARGET_SUBDIR}/iotedge" ${D}${bindir}/iotedge
}

