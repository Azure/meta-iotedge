DESCRIPTION = "Standard mode libiothsm implementation for Azure IoT Edge"
LICENSE = "MIT"

LIC_FILES_CHKSUM=" \
file://LICENSE;md5=b98fddd052bb2f5ddbcdbd417ffb26a8 \
"

SRC_URI += "https://github.com/Azure/azure-iotedge/releases/download/${PV}/iotedge-${PV}.tar.gz"
SRC_URI[md5sum]="88fc1f825b6285e92da0b635d033173a"
SRC_URI[sha256sum]="c9e49a5243428b2b6edb5f2a6310ba45cd3d79067c0c6a2bfba9abab49082c3e"

S = "${WORKDIR}/iotedge-${PV}/hsm-sys/azure-iot-hsm-c"

DEPENDS += "openssl"
PROVIDES += "virtual/libiothsm"
RPROVIDES_${PN} += "virtual/libiothsm"

EXTRA_OECMAKE += "-DBUILD_SHARED=On -Duse_emulator=Off -Duse_http=Off -Duse_default_uuid=On -DCMAKE_SYSTEM_VERSION=10"
inherit cmake
