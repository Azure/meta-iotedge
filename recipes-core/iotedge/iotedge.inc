DEPENDS += "openssl aziotctl"
RDEPENDS:${PN} += "aziotctl"

export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"
export LIBIOTHSM_NOBUILD = "On"
export SOCKET_DIR = "/run/aziot"
export USER_AZIOTID = "aziotid"
export USER_AZIOTCS = "aziotcs"
export USER_AZIOTKS = "aziotks"
export USER_AZIOTTPM = "aziottpm"

# Source-compatibility patches are version-specific (the upstream Cargo.toml /
# source layout differs between releases), so each iotedge-<ver>.inc adds its
# own patch SRC_URI entries rather than carrying them here in the shared
# include (this lets 1.5.x and 1.6.x recipes coexist on the same branch).
