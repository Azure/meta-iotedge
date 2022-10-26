DEPENDS += "openssl virtual/docker "
RDEPENDS_${PN} += "docker "

SRC_URI +="file://0001-Change-panic-strategy-to-unwind.patch"
