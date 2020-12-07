DESCRIPTION = "Standard mode libiothsm implementation for Azure IoT Edge"
LICENSE = "MIT"

LIC_FILES_CHKSUM=" \
file://LICENSE;md5=b98fddd052bb2f5ddbcdbd417ffb26a8 \
"

SRC_URI += "https://github.com/Azure/azure-iotedge/releases/download/${PV}/iotedge-${PV}.tar.gz"
SRC_URI[md5sum]="fe99f044469fcf9173555d835fdee178"
SRC_URI[sha256sum]="df22d2764a3b0418024e13d15c3476e842c2bef95c23066d9103e33059e20aaf"

S = "${WORKDIR}/iotedge-${PV}/edgelet/hsm-sys/azure-iot-hsm-c"

DEPENDS += "openssl"
PROVIDES += "virtual/libiothsm"
RPROVIDES_${PN} += "virtual/libiothsm"

EXTRA_OECMAKE += "-DBUILD_SHARED=On -Duse_emulator=Off -Duse_http=Off -Duse_default_uuid=On -DCMAKE_SYSTEM_VERSION=10"
inherit cmake

