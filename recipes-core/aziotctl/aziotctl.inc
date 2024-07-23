DEPENDS += "openssl virtual/docker"
RDEPENDS:${PN} += "docker"

export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"