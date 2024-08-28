DEPENDS += "openssl virtual/docker pkgconfig"
RDEPENDS:${PN} += "docker "

SRC_URI+= " file://0001-Remove-panic.patch"