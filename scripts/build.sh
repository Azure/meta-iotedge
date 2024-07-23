#!/bin/bash

# Grab the MACHINE from the environment; otherwise, set it to a sane default
export MACHINE="${MACHINE-qemux86-64}"

# Install rustup if not already installed
if [ ! -x "$(command -v rustup)" ]; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
fi

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

