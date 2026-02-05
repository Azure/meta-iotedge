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

Examples:
    ./scripts/update-recipes.sh --iotedge-version <ver> --clean
    ./scripts/update-recipes.sh --iotedge-version <ver> --template kirkstone --clean
EOF
}

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HELPERS="${ROOT_DIR}/scripts/recipe_helpers.py"
PATCHER="${ROOT_DIR}/scripts/patch-bitbake.py"

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
CARGO_HOME_DIR=$(mktemp -d)

cleanup() {
    [[ "${KEEP_WORKDIR}" != true ]] && rm -rf "${WORKDIR}"
    rm -rf "${CARGO_HOME_DIR}"
}
trap cleanup EXIT

# Check dependencies
for cmd in git cargo python3; do
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

# Git helpers using Python script
resolve_latest() { python3 "${HELPERS}" latest-release "$1"; }
resolve_tag_sha() { python3 "${HELPERS}" tag-sha "$1" "$2"; }
resolve_version() { python3 "${HELPERS}" version-from-rev "$1" "$2"; }

# Prepare a git repo at specific revision
prepare_repo() {
    local url="$1" dir="$2" rev="$3"
    rm -rf "${dir}"
    retry "clone ${url}" git clone "${url}" "${dir}"
    retry "checkout ${rev}" git -C "${dir}" checkout "${rev}"
}

# Normalize .cargo/config.toml to use standard crates.io
normalize_cargo_config() {
    local cargo_dir="$1"
    [[ -d "${cargo_dir}" ]] || return 0
    rm -f "${cargo_dir}/config.toml" "${cargo_dir}/config"
    cat > "${cargo_dir}/config.toml" <<'EOF'
[source.crates-io]
registry = "https://github.com/rust-lang/crates.io-index"

[net]
git-fetch-with-cli = true
EOF
}

# Copy and transform recipe
copy_recipe() {
    local component="$1" src="$2" dest_dir="$3" version="$4"
    local dest_bb="${dest_dir}/${component}_${version}.bb"
    local dest_inc="${dest_dir}/${component}-${version}.inc"

    # Remove any existing files (--clean already handled cleanup of other versions)
    rm -f "${dest_bb}" "${dest_inc}"

    python3 "${PATCHER}" --component "${component}" --input "${src}" --output "${dest_bb}"
    printf 'export VERSION = "%s"\n' "${version}" > "${dest_inc}"
}

# Fix SRCREV entries with "main" to actual SHA
fix_srcrev() {
    local recipe="$1" sha="$2"
    [[ -f "${recipe}" && -n "${sha}" ]] || return 0
    sed -i -E "s/^(SRCREV_[a-zA-Z0-9_-]+) = \"main\"$/\1 = \"${sha}\"/" "${recipe}"
}

# Generate patch to remove git deps
generate_patch() {
    local repo_dir="$1" dest_patch="$2" lock_target="$3"
    local tmpdir; tmpdir=$(mktemp -d)
    
    mkdir -p "${tmpdir}"/{orig,mod}/edgelet "${tmpdir}/mod/edgelet/${lock_target}"
    cp "${repo_dir}/edgelet/Cargo."{lock,toml} "${tmpdir}/orig/edgelet/"
    cp "${tmpdir}/orig/edgelet/Cargo."{lock,toml} "${tmpdir}/mod/edgelet/"
    
    python3 "${HELPERS}" strip-git-deps "${tmpdir}/mod/edgelet/Cargo.lock" "${tmpdir}/mod/edgelet/Cargo.toml"
    cp "${tmpdir}/mod/edgelet/Cargo.lock" "${tmpdir}/mod/edgelet/${lock_target}/"
    
    mkdir -p "$(dirname "${dest_patch}")"
    git -C "${tmpdir}" diff --no-index --binary orig mod > "${dest_patch}" || true
    python3 "${HELPERS}" fix-patch-paths "${dest_patch}"
    rm -rf "${tmpdir}"
}

# Sync checksums from Cargo.lock and previous recipes
sync_checksums() {
    local component="$1" version="$2" lockfile="$3"
    local recipe="${ROOT_DIR}/recipes-core/${component}/${component}_${version}.bb"
    local recipe_dir="${ROOT_DIR}/recipes-core/${component}"
    
    [[ -f "${recipe}" ]] || return 0
    [[ -f "${lockfile}" ]] && python3 "${HELPERS}" add-checksums "${recipe}" "${lockfile}"
    
    # Add known checksums (e.g., wasi crates that bitbake complains about)
    python3 "${HELPERS}" add-known-checksums "${recipe}"
    
    # Copy checksums from previous version
    local prev; prev=$(ls "${recipe_dir}/${component}_"*.bb 2>/dev/null | sort -V | grep -v "_${version}.bb$" | tail -1 || true)
    [[ -n "${prev}" ]] || return 0
    
    while IFS= read -r line; do
        local key; key=$(echo "${line}" | cut -d= -f1)
        grep -qF "${key}" "${recipe}" || echo "${line}" >> "${recipe}"
    done < <(grep -E '^SRC_URI\[.*\.sha256sum\] = ' "${prev}" 2>/dev/null || true)
}

# --- Main ---

IOTEDGE_REPO="https://github.com/Azure/iotedge.git"
IIS_REPO="https://github.com/Azure/iot-identity-service.git"

echo "Updating IoT Edge to ${IOTEDGE_VERSION} (${IOTEDGE_REV:0:8})"

IOTEDGE_DIR="${WORKDIR}/iotedge"
prepare_repo "${IOTEDGE_REPO}" "${IOTEDGE_DIR}" "${IOTEDGE_REV}"
normalize_cargo_config "${IOTEDGE_DIR}/edgelet/.cargo"

# Generate IoT Edge recipes
for pkg in aziot-edged iotedge; do
    pushd "${IOTEDGE_DIR}/edgelet/${pkg}" >/dev/null
    retry "cargo bitbake (${pkg})" env CARGO_HOME="${CARGO_HOME_DIR}" cargo bitbake
    bb_file=$(ls "${pkg}_"*.bb | head -1)
    popd >/dev/null
    copy_recipe "${pkg}" "${IOTEDGE_DIR}/edgelet/${pkg}/${bb_file}" \
        "${ROOT_DIR}/recipes-core/${pkg}" "${IOTEDGE_VERSION}"
done

# Clone IIS repo for fixing IoT Edge recipes and generating IIS recipes
echo "Updating IIS to ${IIS_VERSION} (${IIS_REV:0:8})"
IIS_DIR="${WORKDIR}/iot-identity-service"
prepare_repo "${IIS_REPO}" "${IIS_DIR}" "${IIS_REV}"
normalize_cargo_config "${IIS_DIR}/.cargo"

# Fix IoT Edge recipes with IIS paths
for pkg in aziot-edged iotedge; do
    recipe="${ROOT_DIR}/recipes-core/${pkg}/${pkg}_${IOTEDGE_VERSION}.bb"
    python3 "${HELPERS}" fix-cargo-paths "${IIS_DIR}" "${recipe}"
    fix_srcrev "${recipe}" "${IIS_REV}"
    generate_patch "${IOTEDGE_DIR}" "${ROOT_DIR}/recipes-core/${pkg}/files/0001-Remove-git-from-Cargo.patch" "${pkg}"
    sync_checksums "${pkg}" "${IOTEDGE_VERSION}" "${IOTEDGE_DIR}/edgelet/Cargo.lock"
done

# Generate IIS recipes
declare -A IIS_PATHS=([aziot-keys]="key/aziot-keys" [aziotd]="aziotd" [aziotctl]="aziotctl")
for pkg in aziot-keys aziotd aziotctl; do
    pushd "${IIS_DIR}/${IIS_PATHS[$pkg]}" >/dev/null
    retry "cargo bitbake (${pkg})" env CARGO_HOME="${CARGO_HOME_DIR}" cargo bitbake
    bb_file=$(ls "${pkg}_"*.bb | head -1)
    popd >/dev/null
    copy_recipe "${pkg}" "${IIS_DIR}/${IIS_PATHS[$pkg]}/${bb_file}" \
        "${ROOT_DIR}/recipes-core/${pkg}" "${IIS_VERSION}"
    sync_checksums "${pkg}" "${IIS_VERSION}" "${IIS_DIR}/Cargo.lock"
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
