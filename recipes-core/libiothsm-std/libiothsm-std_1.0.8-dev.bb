DESCRIPTION = "Standard mode libiothsm implementation for Azure IoT Edge"
LICENSE = "MIT"

LIC_FILES_CHKSUM=" \
file://LICENSE;md5=b98fddd052bb2f5ddbcdbd417ffb26a8 \
"

SRC_URI += "gitsm://git@github.com/azure/iotedge.git;protocol=https"
SRCREV = "54dccb0881f587f4004513800894e8052401f766"

S = "${WORKDIR}/git/edgelet/hsm-sys/azure-iot-hsm-c"

DEPENDS += "openssl10"
PROVIDES += "virtual/libiothsm"
RPROVIDES_${PN} += "virtual/libiothsm"

# Remove this with actual release
DEFAULT_PREFERENCE = "-1"

EXTRA_OECMAKE += "-DBUILD_SHARED=On -Duse_emulator=Off -Duse_http=Off -Duse_default_uuid=On -DCMAKE_SYSTEM_VERSION=10"
inherit cmake
