DEPENDS += "openssl virtual/docker"
RDEPENDS:${PN} += "docker"

export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"

SRC_URI +="file://0001-Change-panic-strategy-to-unwind.patch"

do_install () {
    # Binaries
    install -d  "${D}${bindir}"
    install -m 755 "${WORKDIR}/build/target/${RUST_TARGET_SYS}/release/aziotctl" ${D}${bindir}/aziotctl
}