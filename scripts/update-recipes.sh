#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: update-recipes.sh [options]

Options:
    --iotedge-version <ver>   IoT Edge version tag (e.g., 1.5.35)
    --template <name>         Yocto template (kirkstone or scarthgap, default: scarthgap)
    --clean                   Remove old version-specific recipe files before generating
    --skip-validate           Skip bitbake validation (not recommended)
    --workdir <path>          Work directory (default: mktemp)
    --keep-workdir            Do not delete work directory
    -h, --help                Show this help

The IIS version is automatically resolved from the IoT Edge release's product-versions.json.

Recipes use `inherit cargo-update-recipe-crates` and split crate data into
*-crates.inc files.  This script generates those files from Cargo.lock and can
also be refreshed later via `bitbake <recipe> -c update_crates`.

Examples:
    ./scripts/update-recipes.sh --iotedge-version <ver> --clean
    ./scripts/update-recipes.sh --iotedge-version <ver> --template kirkstone --clean
EOF
}

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HELPERS="${ROOT_DIR}/scripts/recipe_helpers.py"

# Defaults
WORKDIR="" KEEP_WORKDIR=false CLEAN=false SKIP_VALIDATE=false
IOTEDGE_VERSION=""
TEMPLATE="scarthgap"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --iotedge-version) IOTEDGE_VERSION="$2"; shift 2;;
        --template)        TEMPLATE="$2"; shift 2;;
        --clean)           CLEAN=true; shift;;
        --skip-validate)   SKIP_VALIDATE=true; shift;;
        --workdir)         WORKDIR="$2"; shift 2;;
        --keep-workdir)    KEEP_WORKDIR=true; shift;;
        -h|--help)         usage; exit 0;;
        *)                 echo "Unknown arg: $1"; usage; exit 1;;
    esac
done

# Validate required args
if [[ -z "${IOTEDGE_VERSION}" ]]; then
    echo "Error: --iotedge-version is required"
    usage
    exit 1
fi

# Validate template
if [[ "${TEMPLATE}" != "scarthgap" && "${TEMPLATE}" != "kirkstone" ]]; then
    echo "Error: --template must be 'scarthgap' or 'kirkstone'"
    exit 1
fi
echo "Using template: ${TEMPLATE}"

# Resolve versions from the IoT Edge release's product-versions.json
echo "Fetching product-versions.json from IoT Edge ${IOTEDGE_VERSION}..."
PRODUCT_VERSIONS_URL="https://raw.githubusercontent.com/Azure/azure-iotedge/${IOTEDGE_VERSION}/product-versions.json"
PRODUCT_VERSIONS=$(curl -fsSL "$PRODUCT_VERSIONS_URL") || {
    echo "Error: Could not fetch product-versions.json for tag ${IOTEDGE_VERSION}"
    exit 1
}

# Extract IIS version from product-versions.json
IIS_VERSION=$(echo "$PRODUCT_VERSIONS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
# Use lts channel (preferred for embedded systems)
lts = next((c for c in data['channels'] if c['name'] == 'lts'), None)
if not lts:
    print('Error: No lts channel found', file=sys.stderr)
    sys.exit(1)
aziot = next((p for p in lts['products'] if p['id'] == 'aziot-edge'), None)
if not aziot:
    print('Error: No aziot-edge product found', file=sys.stderr)
    sys.exit(1)
iis = next((c['version'] for c in aziot['components'] if c['name'] == 'aziot-identity-service'), '')
if not iis:
    print('Error: No IIS version found', file=sys.stderr)
    sys.exit(1)
print(iis)
")
echo "  IoT Edge version: ${IOTEDGE_VERSION}"
echo "  IIS version: ${IIS_VERSION}"

# Resolve SHAs from version tags
echo "Resolving git SHAs..."
IOTEDGE_REV=$(git ls-remote --tags https://github.com/Azure/iotedge.git "refs/tags/${IOTEDGE_VERSION}" | cut -f1)
if [[ -z "${IOTEDGE_REV}" ]]; then
    echo "Error: Could not resolve SHA for tag ${IOTEDGE_VERSION} in Azure/iotedge"
    exit 1
fi
echo "  IoT Edge SHA: ${IOTEDGE_REV}"

IIS_REV=$(git ls-remote --tags https://github.com/Azure/iot-identity-service.git "refs/tags/${IIS_VERSION}" | cut -f1)
if [[ -z "${IIS_REV}" ]]; then
    echo "Error: Could not resolve SHA for tag ${IIS_VERSION} in Azure/iot-identity-service"
    exit 1
fi
echo "  IIS SHA: ${IIS_REV}"

# Clean old recipes if requested
if [[ "${CLEAN}" == true ]]; then
    echo "Cleaning old recipe files..."
    for dir in iotedge aziot-edged aziotd aziotctl aziot-keys; do
        find "${ROOT_DIR}/recipes-core/${dir}" -name "*_*.bb" -type f -delete 2>/dev/null || true
        find "${ROOT_DIR}/recipes-core/${dir}" -name "*-[0-9]*.inc" -type f -delete 2>/dev/null || true
    done
fi

# Setup directories
[[ -z "${WORKDIR}" ]] && WORKDIR=$(mktemp -d)

cleanup() {
    [[ "${KEEP_WORKDIR}" != true ]] && rm -rf "${WORKDIR}"
}
trap cleanup EXIT

# Check dependencies
for cmd in git python3 curl; do
    command -v "$cmd" >/dev/null || { echo "Missing: $cmd"; exit 1; }
done

# Retry helper for flaky networks
retry() {
    local desc="$1" attempt=1 delay=2; shift
    while ! "$@"; do
        ((attempt >= ${RETRY_MAX:-5})) && { echo "Failed: ${desc}"; return 1; }
        echo "Retry ${attempt}: ${desc} in ${delay}s" >&2
        sleep "$delay"; ((attempt++, delay*=2))
    done
}

# Prepare a git repo at specific revision
prepare_repo() {
    local url="$1" dir="$2" rev="$3"
    rm -rf "${dir}"
    retry "clone ${url}" git clone "${url}" "${dir}"
    retry "checkout ${rev}" git -C "${dir}" checkout "${rev}"
}

# --- Generate IoT Edge recipes ---

echo "Updating IoT Edge to ${IOTEDGE_VERSION} (${IOTEDGE_REV:0:8})"

IOTEDGE_DIR="${WORKDIR}/iotedge"
prepare_repo "https://github.com/Azure/iotedge.git" "${IOTEDGE_DIR}" "${IOTEDGE_REV}"

for pkg in aziot-edged iotedge; do
    recipe_dir="${ROOT_DIR}/recipes-core/${pkg}"
    bb="${recipe_dir}/${pkg}_${IOTEDGE_VERSION}.bb"
    ver_inc="${recipe_dir}/${pkg}-${IOTEDGE_VERSION}.inc"
    crates_inc="${recipe_dir}/${pkg}-crates.inc"

    # Generate .bb (template — only metadata + SRCREV change between versions)
    cat > "${bb}" <<BBEOF
SUMMARY = "$(if [[ "${pkg}" == "aziot-edged" ]]; then echo "The aziot-edged is the main binary for the IoT Edge daemon."; else echo "The iotedge tool is used to manage the IoT Edge runtime."; fi)"
HOMEPAGE = "https://aka.ms/iotedge"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \\
    file://LICENSE;md5=0f7e3b1308cb5c00b372a6e78835732d \\
    file://THIRDPARTYNOTICES;md5=11604c6170b98c376be25d0ca6989d9b \\
"

inherit cargo cargo-update-recipe-crates$(if [[ "${pkg}" == "aziot-edged" ]]; then echo " pkgconfig"; fi)

SRC_URI += "git://github.com/Azure/iotedge.git;protocol=https;nobranch=1"
SRCREV = "${IOTEDGE_REV}"
S = "\${WORKDIR}/git"
CARGO_SRC_DIR = "edgelet"
CARGO_BUILD_FLAGS += "-p ${pkg}"
CARGO_LOCK_SRC_DIR = "\${S}/edgelet"
do_compile[network] = "1"

require \${BPN}-crates.inc
require recipes-core/iot-identity-service.inc

include ${pkg}-\${PV}.inc
include ${pkg}.inc
BBEOF
    echo "  Generated ${bb}"

    # Generate version-specific .inc
    cat > "${ver_inc}" <<INCEOF
export VERSION = "${IOTEDGE_VERSION}"
IIS_SRCREV = "${IIS_REV}"
INCEOF
    echo "  Generated ${ver_inc}"

    # Generate crates.inc from Cargo.lock
    python3 "${HELPERS}" generate-crates-inc "${IOTEDGE_DIR}/edgelet/Cargo.lock" "${crates_inc}"
done

# --- Generate IIS recipes ---

echo "Updating IIS to ${IIS_VERSION} (${IIS_REV:0:8})"

IIS_DIR="${WORKDIR}/iot-identity-service"
prepare_repo "https://github.com/Azure/iot-identity-service.git" "${IIS_DIR}" "${IIS_REV}"

declare -A IIS_PKGS=(
    [aziotd]="aziotd"
    [aziotctl]="aziotctl"
    [aziot-keys]="key/aziot-keys"
)
declare -A IIS_SUMMARIES=(
    [aziotd]="aziotd is the main binary for the IoT Identity Service and related services."
    [aziotctl]="aziotctl is the CLI tool for the IoT Identity Service."
    [aziot-keys]="aziot-keys is the keys library for the IoT Identity Service."
)
declare -A IIS_INHERIT=(
    [aziotd]="cargo cargo-update-recipe-crates pkgconfig"
    [aziotctl]="cargo cargo-update-recipe-crates"
    [aziot-keys]="cargo cargo-update-recipe-crates pkgconfig"
)
declare -A IIS_PROTO=(
    [aziotd]="gitsm"
    [aziotctl]="gitsm"
    [aziot-keys]="gitsm"
)

for pkg in aziotd aziotctl aziot-keys; do
    recipe_dir="${ROOT_DIR}/recipes-core/${pkg}"
    bb="${recipe_dir}/${pkg}_${IIS_VERSION}.bb"
    ver_inc="${recipe_dir}/${pkg}-${IIS_VERSION}.inc"
    crates_inc="${recipe_dir}/${pkg}-crates.inc"
    cargo_src="${IIS_PKGS[$pkg]}"

    # Generate .bb
    cat > "${bb}" <<BBEOF
SUMMARY = "${IIS_SUMMARIES[$pkg]}"
HOMEPAGE = "https://azure.github.io/iot-identity-service/"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \\
    file://LICENSE;md5=4f9c2c296f77b3096b6c11a16fa7c66e \\
"

inherit ${IIS_INHERIT[$pkg]}

SRC_URI += "${IIS_PROTO[$pkg]}://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1"
SRCREV = "${IIS_REV}"
S = "\${WORKDIR}/git"
CARGO_SRC_DIR = "${cargo_src}"

require \${BPN}-crates.inc

include ${pkg}-\${PV}.inc
include ${pkg}.inc
BBEOF
    echo "  Generated ${bb}"

    # Generate version-specific .inc
    cat > "${ver_inc}" <<INCEOF
export VERSION = "${IIS_VERSION}"
INCEOF
    echo "  Generated ${ver_inc}"

    # Generate crates.inc from Cargo.lock
    python3 "${HELPERS}" generate-crates-inc "${IIS_DIR}/Cargo.lock" "${crates_inc}"
done

# Validate recipes with bitbake (skip with --skip-validate)
if [[ "${SKIP_VALIDATE}" != true ]]; then
    echo "Validating recipes with bitbake (template: ${TEMPLATE})..."
    VALIDATE_DIR=$(mktemp -d)
    
    # Fetch required layers and use template configs to avoid drift.
    retry "fetch layers" bash -c "cd '${VALIDATE_DIR}' && '${ROOT_DIR}/scripts/fetch.sh' '${TEMPLATE}'"
    rm -rf "${VALIDATE_DIR}/poky/meta-iotedge"
    ln -sf "${ROOT_DIR}" "${VALIDATE_DIR}/poky/meta-iotedge"
    
    # Source build environment using the template configs.
    pushd "${VALIDATE_DIR}" >/dev/null
    set +u  # oe-init-build-env uses unset variables
    TEMPLATECONF="poky/meta-iotedge/conf/templates/${TEMPLATE}" \
        . poky/oe-init-build-env build >/dev/null
    set -u
    
    # Allow running as root (CI containers) and silence meta-virtualization warning.
    echo 'INHERIT:remove = "sanity"' >> conf/local.conf
    echo 'SKIP_META_VIRT_SANITY_CHECK = "1"' >> conf/local.conf
    
    # Parse recipes
    if bitbake -p; then
        echo "✓ Recipe validation passed"
    else
        echo "✗ Recipe validation failed"
        popd >/dev/null
        rm -rf "${VALIDATE_DIR}"
        exit 1
    fi
    
    popd >/dev/null
    rm -rf "${VALIDATE_DIR}"
fi

echo "Recipe update complete."
