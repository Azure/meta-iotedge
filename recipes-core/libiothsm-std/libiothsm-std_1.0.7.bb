DESCRIPTION = "Standard mode libiothsm implementation for Azure IoT Edge"
LICENSE = "MIT"

LIC_FILES_CHKSUM=" \
file://LICENSE;md5=b98fddd052bb2f5ddbcdbd417ffb26a8 \
"

SRC_URI += "gitsm://github.com/azure/iotedge.git;protocol=https;branch=release/1.0.7"
SRCREV = "f455ae2cd66db716c4bd8e7aaa7984ce092481c0"

S = "${WORKDIR}/git/edgelet/hsm-sys/azure-iot-hsm-c"

DEPENDS += "openssl10"
PROVIDES += "virtual/libiothsm"
RPROVIDES_${PN} += "virtual/libiothsm"

EXTRA_OECMAKE += "-DBUILD_SHARED=On -Duse_emulator=Off -Duse_http=Off -Duse_default_uuid=On -DCMAKE_SYSTEM_VERSION=10"
inherit cmake

