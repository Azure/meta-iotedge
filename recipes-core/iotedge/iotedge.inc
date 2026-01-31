DEPENDS += "openssl aziotctl"
RDEPENDS:${PN} += "aziotctl"

export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"
export LIBIOTHSM_NOBUILD="On"
export SOCKET_DIR="/run/aziot"
export USER_AZIOTID="aziotid"
export USER_AZIOTCS="aziotcs"
export USER_AZIOTKS="aziotks"
export USER_AZIOTTPM="aziottpm"

SRC_URI += "file://0001-Remove-git-from-Cargo.patch \
            file://0002-Work-around-Rust-1.78-dead_code-lint-issues.patch \
"
