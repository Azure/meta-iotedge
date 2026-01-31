#!/usr/bin/env bash
set -euo pipefail

TEMPLATE=${1-default}
IMAGE_TARGET=${IMAGE_TARGET:-iotedge-qemu-image}
MACHINE=${MACHINE:-qemux86-64}
SSH_PORT=${SSH_PORT:-2222}
SSH_HOST=${SSH_HOST:-127.0.0.1}
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

cleanup() {
    if [[ -n "${RUNQEMU_PID:-}" ]]; then
        kill "${RUNQEMU_PID}" >/dev/null 2>&1 || true
        wait "${RUNQEMU_PID}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

export MACHINE
if [[ -n "${DEVCONTAINER:-}" || -n "${CODESPACES:-}" || -f "/.devcontainer" ]]; then
    export TEMPLATECONF="meta-iotedge/conf/templates/${TEMPLATE}"
    ./scripts/bitbake.sh "${IMAGE_TARGET}"
else
    ./scripts/containerize.sh "${TEMPLATE}" ./scripts/bitbake.sh "${IMAGE_TARGET}"
fi

source ./poky/oe-init-build-env build >/dev/null

runqemu "${MACHINE}" nographic slirp &
RUNQEMU_PID=$!

for _ in $(seq 1 60); do
    if ssh ${SSH_OPTS} -p "${SSH_PORT}" "root@${SSH_HOST}" "iotedge --version" >/dev/null 2>&1; then
        echo "IoT Edge QEMU validation passed."
        exit 0
    fi
    sleep 5
done

echo "IoT Edge QEMU validation failed (ssh/iotedge timeout)." >&2
exit 1
