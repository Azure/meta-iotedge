DEPENDS += "openssl virtual/docker pkgconfig"
RDEPENDS:${PN} += "docker "

SRC_URI +="file://0001-Change-panic-strategy-to-unwind.patch"

export SOCKET_DIR="/run/aziot"
export USER_AZIOTID="aziotid"
export USER_AZIOTCS="aziotcs"
export USER_AZIOTKS="aziotks"
export USER_AZIOTTPM="aziottpm"
