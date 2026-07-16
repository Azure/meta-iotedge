SUMMARY = "QEMU validation image with IoT Edge runtime"
DESCRIPTION = "Minimal image for QEMU validation of IoT Edge binaries."
LICENSE = "MIT"

inherit core-image

# Boot the QEMU validation image with an uncompressed ext4 rootfs.
#
# Yocto 6.0 (Wrynose) changed the qemux86-64 machine defaults: IMAGE_FSTYPES
# gained "tar.zst ext4.zst" and QB_DEFAULT_FSTYPE became "ext4.zst". runqemu
# reads QB_DEFAULT_FSTYPE (from the image's qemuboot.conf) to locate the rootfs,
# so it looked for *.rootfs.ext4.zst and either refused the compressed image
# ("runqemu - ERROR - .zst images are only supported with snapshot mode") or
# failed to find it ("Failed to find rootfs ... .ext4.zst"). scarthgap (Yocto
# 5.0) defaulted to plain ext4, which is why its QEMU leg passed.
#
# scripts/validate-qemu.sh, the CI artifact upload, and release.yml all consume
# the plain *.rootfs.ext4, so force both the produced fstype and runqemu's
# default to ext4. (release.yml still makes its own .ext4.zst via zstd.)
IMAGE_FSTYPES = "ext4"
QB_DEFAULT_FSTYPE = "ext4"

IMAGE_FEATURES += "ssh-server-dropbear"

# QEMU validation runs `iotedge check --verbose`, which docker-pulls the
# azureiotedge-diagnostics image (a multi-layer .NET runtime image) into the
# guest rootfs. The default rootfs has almost no free space, so the pull fails
# mid-unpack with "no space left on device" (observed on the scarthgap 1.5.21
# QEMU leg, unpacking Microsoft.NETCore.App). Give the validation image ~1 GiB
# of headroom so the diagnostics image fits. This only affects the throwaway
# QEMU image, not shipped RPMs.
IMAGE_ROOTFS_EXTRA_SPACE = "1048576"

# Core IoT Edge packages
IMAGE_INSTALL:append = " iotedge aziot-edged"

# Docker/Moby container runtime - required for IoT Edge to manage containers
# Note: Uses docker-moby from meta-virtualization layer
IMAGE_INSTALL:append = " docker"
