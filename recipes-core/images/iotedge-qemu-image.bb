SUMMARY = "QEMU validation image with IoT Edge runtime"
DESCRIPTION = "Minimal image for QEMU validation of IoT Edge binaries."
LICENSE = "MIT"

inherit core-image

IMAGE_FEATURES += "ssh-server-dropbear"

# Core IoT Edge packages
IMAGE_INSTALL:append = " iotedge aziot-edged"

# Docker/Moby container runtime - required for IoT Edge to manage containers
# Note: Uses docker-moby from meta-virtualization layer
IMAGE_INSTALL:append = " docker"
