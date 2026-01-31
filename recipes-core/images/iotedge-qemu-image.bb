SUMMARY = "QEMU validation image with IoT Edge runtime"
DESCRIPTION = "Minimal image for QEMU validation of IoT Edge binaries."
LICENSE = "MIT"

inherit core-image

IMAGE_FEATURES += "ssh-server-dropbear"

IMAGE_INSTALL:append = " iotedge aziot-edged"
