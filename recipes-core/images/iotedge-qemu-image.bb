SUMMARY = "QEMU validation image with IoT Edge runtime"
DESCRIPTION = "Minimal image for QEMU validation of IoT Edge binaries."
LICENSE = "MIT"

inherit core-image

# Force an uncompressed ext4 rootfs. Yocto 6.0 (Wrynose) changed the qemux86-64
# default IMAGE_FSTYPES to emit a compressed ext4.zst, which runqemu refuses to
# boot without "snapshot" ("runqemu - ERROR - .zst images are only supported
# with snapshot mode"). scripts/validate-qemu.sh, the CI artifact upload, and
# release.yml all consume the plain *.rootfs.ext4, so pin it here for every
# Yocto version. (release.yml still produces its own .ext4.zst via zstd.)
IMAGE_FSTYPES = "ext4"

IMAGE_FEATURES += "ssh-server-dropbear"

# Core IoT Edge packages
IMAGE_INSTALL:append = " iotedge aziot-edged"

# Docker/Moby container runtime - required for IoT Edge to manage containers
# Note: Uses docker-moby from meta-virtualization layer
IMAGE_INSTALL:append = " docker"
