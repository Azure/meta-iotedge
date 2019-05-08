DESCRIPTION = "Standard mode libiothsm implementation for Azure IoT Edge"
LICENSE = "MIT"

LIC_FILES_CHKSUM=" \
file://LICENSE;md5=b98fddd052bb2f5ddbcdbd417ffb26a8 \
"

SRC_URI += "https://github.com/Azure/azure-iotedge/releases/download/1.0.7/libiothsm-std-1.0.7.tar.gz"
SRC_URI[md5sum] = "6c350e72436bff6d83b8580ef2a1bbe4"
SRC_URI[sha256sum] = "335fcbdb7ba5fefa59e1857fed76b61c3d97a84249f4d7181f312ef218bc1f9c"

DEPENDS += "openssl"
PROVIDES += "virtual/libiothsm"
RPROVIDES_${PN} += "virtual/libiothsm"

EXTRA_OECMAKE += "-DBUILD_SHARED=On -Duse_emulator=Off -Duse_http=Off -Duse_default_uuid=On -DCMAKE_SYSTEM_VERSION=10"
inherit cmake

