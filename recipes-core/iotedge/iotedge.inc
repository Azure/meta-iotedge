DEPENDS += "openssl aziotctl"
RDEPENDS:${PN} += "aziotctl"

export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"
export LIBIOTHSM_NOBUILD="On"
