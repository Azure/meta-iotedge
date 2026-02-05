#!/usr/bin/env bash
set -euo pipefail

TEMPLATE=scarthgap
IMAGE_TARGET=${IMAGE_TARGET:-iotedge-qemu-image}
MACHINE=${MACHINE:-qemux86-64}
SSH_PORT=${SSH_PORT:-2222}
SSH_HOST=${SSH_HOST:-127.0.0.1}
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 -o PubkeyAuthentication=no"
MOCK_IOTEDGE_CONFIG=

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mock-config)
            MOCK_IOTEDGE_CONFIG=1
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [template] [--mock-config]"
            exit 0
            ;;
        *)
            TEMPLATE="$1"
            shift
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Check for existing QEMU image
IMAGE_DIR="${REPO_ROOT}/build/tmp/deploy/images/${MACHINE}"
IMAGE_FILE="${IMAGE_DIR}/${IMAGE_TARGET}-${MACHINE}.rootfs.ext4"

# SSH with empty password (debug-tweaks enables blank root password)
ssh_cmd() {
    # Use sshpass for empty password authentication
    sshpass -p '' ssh ${SSH_OPTS} -p "${SSH_PORT}" "root@${SSH_HOST}" "$@"
}

cleanup() {
    if [[ -n "${RUNQEMU_PID:-}" ]]; then
        echo "Shutting down QEMU..."
        kill "${RUNQEMU_PID}" >/dev/null 2>&1 || true
        wait "${RUNQEMU_PID}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

# Check for sshpass
if ! command -v sshpass &>/dev/null; then
    echo "Installing sshpass for automated SSH authentication..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update && sudo apt-get install -y sshpass
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y sshpass
    else
        echo "ERROR: sshpass not found. Please install it manually." >&2
        exit 1
    fi
fi

export MACHINE

# Skip build if image already exists
if [[ -f "${IMAGE_FILE}" ]]; then
    echo "QEMU image already exists: ${IMAGE_FILE}"
    echo "Skipping build step. Delete the image to force a rebuild."
elif [[ -n "${DEVCONTAINER:-}" || -n "${CODESPACES:-}" || -f "/.devcontainer" ]]; then
    export TEMPLATECONF="meta-iotedge/conf/templates/${TEMPLATE}"
    ./scripts/bitbake.sh "${IMAGE_TARGET}"
else
    ./scripts/containerize.sh "${TEMPLATE}" ./scripts/bitbake.sh "${IMAGE_TARGET}"
fi

# Source build environment (disable strict mode temporarily as oe-init-build-env uses unset vars)
set +u
source ./poky/oe-init-build-env build >/dev/null 2>&1
set -u

# Start QEMU with slirp networking (automatically forwards host:2222 -> guest:22)
echo "Starting QEMU with slirp networking (SSH on localhost:${SSH_PORT})..."
runqemu "${MACHINE}" nographic slirp &
RUNQEMU_PID=$!

# Wait for SSH to become available
echo "Waiting for QEMU to boot and SSH to become available..."
for i in $(seq 1 60); do
    if ssh_cmd "true" 2>/dev/null; then
        echo "SSH connection established after ~$((i * 5)) seconds."
        break
    fi
    if [[ $i -eq 60 ]]; then
        echo "SSH connection timeout after 5 minutes." >&2
        exit 1
    fi
    sleep 5
done

if [[ -n "${MOCK_IOTEDGE_CONFIG}" ]]; then
    echo "Preparing mock IoT Edge config (MOCK_IOTEDGE_CONFIG=1) and applying it..."
    ssh_cmd "sh -s" <<'EOF'
set -e

if [ ! -f /etc/aziot/config.toml ]; then
    mkdir -p /etc/aziot
    cat >/etc/aziot/config.toml <<'EOC'
# Minimal mock config for diagnostics.
hostname = "qemu-iotedge"

[provisioning]
source = "manual"
iothub_hostname = "example.azure-devices.net"
device_id = "qemu-device"

[provisioning.authentication]
method = "sas"
device_id_pk = { value = "ZmFrZV9rZXk=" }
EOC
fi

if command -v iotedge >/dev/null 2>&1; then
    iotedge config apply -c /etc/aziot/config.toml || true
elif command -v aziotctl >/dev/null 2>&1; then
    aziotctl config apply -c /etc/aziot/config.toml || true
fi
EOF
fi

# Run validation commands
echo ""
echo "=== IoT Edge Validation ==="
echo ""

echo "1. Checking iotedge version:"
ssh_cmd "iotedge --version"

echo ""
if [[ -n "${MOCK_IOTEDGE_CONFIG}" ]]; then
    echo "2. Running iotedge check (connectivity errors expected with mock config):"
else
    echo "2. Running iotedge check (some failures expected without config):"
fi
ssh_cmd "iotedge check --verbose 2>&1" || true

echo ""
echo "3. Checking aziot-edged service status:"
ssh_cmd "systemctl is-active aziot-edged || true"

echo ""
echo "4. Checking aziot-identityd service status:"
ssh_cmd "systemctl is-active aziot-identityd || true"

echo ""
echo "5. Listing installed IoT Edge packages:"
if ssh_cmd "command -v rpm" >/dev/null 2>&1; then
    ssh_cmd "rpm -qa | grep -E 'iotedge|aziot' | sort"
elif ssh_cmd "command -v opkg" >/dev/null 2>&1; then
    ssh_cmd "opkg list-installed | grep -E 'iotedge|aziot' | sort"
elif ssh_cmd "command -v dpkg" >/dev/null 2>&1; then
    ssh_cmd "dpkg -l | grep -E 'iotedge|aziot'"
else
    echo "(Package manager not found - skipping package listing)"
fi

echo ""
echo "=== IoT Edge QEMU validation passed! ==="
exit 0
