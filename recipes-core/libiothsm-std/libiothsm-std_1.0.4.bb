DESCRIPTION = "Standard mode libiothsm implementation for Azure IoT Edge"
LICENSE = "MIT"

# FIXME: update generateme with the real MD5 of the license file
LIC_FILES_CHKSUM=" \
"

SRC_URI += "gitsm://git@github.com/myagley/iotedge.git;protocol=ssh;branch=miyagley/libiothsm-version"
SRCREV = "e15a7dff0af7f8419952466b6cdc4112ea96af51"

S = "${WORKDIR}/git/edgelet/hsm-sys/azure-iot-hsm-c"

DEPENDS += "openssl10"
PROVIDES += "virtual/libiothsm"
RPROVIDES_${PN} += "virtual/libiothsm"

EXTRA_OECMAKE += "-DBUILD_SHARED=On -Duse_emulator=Off -Duse_http=Off -Duse_default_uuid=On"
inherit cmake
