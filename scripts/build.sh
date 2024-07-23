#!/bin/bash

# Grab the MACHINE from the environment; otherwise, set it to a sane default
export MACHINE="${MACHINE-qemux86-64}"

# Install and set nightly Rust toolchain
rustup toolchain install nightly
rustup default nightly

# What to build
BUILD_TARGETS="\
    iotedge \
    aziot-edged \
    "

die() {
    echo "$*" >&2
    exit 1
}

rm -f build/conf/bblayers.conf || die "failed to nuke bblayers.conf"
rm -f build/conf/local.conf || die "failed to nuke local.conf"

./scripts/containerize.sh ./scripts/bitbake.sh ${BUILD_TARGETS} || die "failed to build"

