DESCRIPTION = "Standard mode libiothsm implementation for Azure IoT Edge"
LICENSE = "MIT"

LIC_FILES_CHKSUM=" \
file://LICENSE;md5=b98fddd052bb2f5ddbcdbd417ffb26a8 \
"

SRC_URI += "gitsm://github.com/azure/iotedge.git;protocol=https"
SRCREV = "d76e0316c6f324345d77c48a83ce836d09392699"

S = "${WORKDIR}/git/edgelet/hsm-sys/azure-iot-hsm-c"

DEPENDS += "openssl10"
PROVIDES += "virtual/libiothsm"
RPROVIDES_${PN} += "virtual/libiothsm"

EXTRA_OECMAKE += "-DBUILD_SHARED=On -Duse_emulator=Off -Duse_http=Off -Duse_default_uuid=On"
inherit cmake
