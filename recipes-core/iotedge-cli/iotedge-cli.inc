DEPENDS += "openssl10"

export BUILD_SOURCEVERSION="${SRCREV}"

do_install () {
    # Binaries
    install -d  "${D}${bindir}"
    install -m 755 "${WORKDIR}/git/edgelet/target/${CARGO_TARGET_SUBDIR}/iotedge" ${D}${bindir}/iotedge
}

