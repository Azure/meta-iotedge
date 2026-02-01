#!/bin/bash

# Yocto build script
# Usage: build.sh [template] [--with-qemu]
#
# Arguments:
#   template    - Yocto template to use (default: scarthgap)
#   --with-qemu - Also build the QEMU validation image

set -euo pipefail

# Grab the MACHINE from the environment; otherwise, set it to a sane default
export MACHINE="${MACHINE:-qemux86-64}"

TEMPLATE="scarthgap"
BUILD_QEMU=false

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --with-qemu) BUILD_QEMU=true ;;
        -*) echo "Unknown option: $arg" >&2; exit 1 ;;
        *) TEMPLATE="$arg" ;;
    esac
done

# Package targets - these are the RPM packages we ship
# Note: iotedge/aziot-edged depend on aziotd/aziotctl/aziot-keys via RDEPENDS
BUILD_TARGETS="iotedge aziot-edged"

if [[ "$BUILD_QEMU" == true ]]; then
    BUILD_TARGETS="$BUILD_TARGETS iotedge-qemu-image"
fi

die() {
    echo "$*" >&2
    exit 1
}

rm -f build/conf/bblayers.conf || die "failed to nuke bblayers.conf"
rm -f build/conf/local.conf || die "failed to nuke local.conf"

if [[ -n "${DEVCONTAINER:-}" || -n "${CODESPACES:-}" || -f "/.devcontainer" ]]; then
    export TEMPLATECONF="meta-iotedge/conf/templates/${TEMPLATE}"
    ./scripts/bitbake.sh ${BUILD_TARGETS} || die "failed to build"
else
    ./scripts/containerize.sh "${TEMPLATE}" ./scripts/bitbake.sh ${BUILD_TARGETS} || die "failed to build"
fi

