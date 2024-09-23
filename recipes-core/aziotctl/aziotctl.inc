DEPENDS += "openssl virtual/docker"
RDEPENDS:${PN} += "docker"

export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"
export SOCKET_DIR="/run/aziot"
export USER_AZIOTID="aziotid"
export USER_AZIOTCS="aziotcs"
export USER_AZIOTKS="aziotks"
export USER_AZIOTTPM="aziottpm"