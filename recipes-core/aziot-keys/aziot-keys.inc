DEPENDS += "openssl pkgconfig"
RDEPENDS:${PN} += ""

SRC_URI+= " file://0001-Remove-panic.patch"