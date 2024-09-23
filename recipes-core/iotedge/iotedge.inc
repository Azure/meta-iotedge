DEPENDS += "openssl aziotctl"
RDEPENDS:${PN} += "aziotctl"

export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"
export LIBIOTHSM_NOBUILD="On"

export SOCKET_DIR="/run/aziot"
export USER_AZIOTID="aziotid"
export USER_AZIOTCS="aziotcs"
export USER_AZIOTKS="aziotks"
export USER_AZIOTTPM="aziottpm"