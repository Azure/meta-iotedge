DESCRIPTION = "Standard mode libiothsm implementation for Azure IoT Edge"
LICENSE = "MIT"

LIC_FILES_CHKSUM=" \
file://LICENSE;md5=b98fddd052bb2f5ddbcdbd417ffb26a8 \
"

SRC_URI += "https://github.com/Azure/azure-iotedge/releases/download/1.0.7/iotedge-1.0.7.tar.gz"
SRC_URI[md5sum] = "5130423e5a77e7e3016c4f03bbde46e8"
SRC_URI[sha256sum] = "59a2366fade6be3aa5a67771bd6c288604c552e5b2aa91c2655b5068cd48babe"

S = "${WORKDIR}/iotedge-${PV}/edgelet/hsm-sys/azure-iot-hsm-c"

DEPENDS += "openssl"
PROVIDES += "virtual/libiothsm"
RPROVIDES_${PN} += "virtual/libiothsm"

EXTRA_OECMAKE += "-DBUILD_SHARED=On -Duse_emulator=Off -Duse_http=Off -Duse_default_uuid=On -DCMAKE_SYSTEM_VERSION=10"
inherit cmake

