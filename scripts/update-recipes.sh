#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: update-recipes.sh [options]

Options:
    --iotedge-rev <sha>       IoT Edge git commit SHA (required with --iotedge-version)
    --iotedge-version <ver>   IoT Edge version (e.g., 1.5.35)
    --iis-rev <sha>           IoT Identity Service git commit SHA (required with --iis-version)
    --iis-version <ver>       IoT Identity Service version (e.g., 1.5.6)
    --clean                   Remove old version-specific recipe files before generating
    --skip-validate           Skip bitbake validation (not recommended)
    --workdir <path>          Work directory (default: mktemp)
    --keep-workdir            Do not delete work directory
    -h, --help                Show this help

Examples:
    # Update IoT Edge only (IIS rev needed for path fixing)
    ./scripts/update-recipes.sh --iotedge-rev SHA --iotedge-version 1.5.35 --iis-rev SHA --clean
    
    # Update both IoT Edge and IIS
    ./scripts/update-recipes.sh --iotedge-rev SHA --iotedge-version 1.5.35 --iis-rev SHA --iis-version 1.5.6 --clean
EOF
}

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HELPERS="${ROOT_DIR}/scripts/recipe_helpers.py"
PATCHER="${ROOT_DIR}/scripts/patch-bitbake.py"

# Defaults
WORKDIR="" KEEP_WORKDIR=false CLEAN=false SKIP_VALIDATE=false
IOTEDGE_REV="" IOTEDGE_VERSION="" IIS_REV="" IIS_VERSION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --iotedge-rev)     IOTEDGE_REV="$2"; shift 2;;
        --iotedge-version) IOTEDGE_VERSION="$2"; shift 2;;
        --iis-rev)         IIS_REV="$2"; shift 2;;
        --iis-version)     IIS_VERSION="$2"; shift 2;;
        --clean)           CLEAN=true; shift;;
        --skip-validate)   SKIP_VALIDATE=true; shift;;
        --workdir)         WORKDIR="$2"; shift 2;;
        --keep-workdir)    KEEP_WORKDIR=true; shift;;
        -h|--help)         usage; exit 0;;
        *)                 echo "Unknown arg: $1"; usage; exit 1;;
    esac
done

# Determine what to update based on version args
UPDATE_IOTEDGE=false UPDATE_IIS=false
[[ -n "${IOTEDGE_VERSION}" ]] && UPDATE_IOTEDGE=true
[[ -n "${IIS_VERSION}" ]] && UPDATE_IIS=true

# Validate required args
if [[ "${UPDATE_IOTEDGE}" == true && -z "${IOTEDGE_REV}" ]]; then
    echo "Error: --iotedge-rev required when --iotedge-version is specified"
    exit 1
fi
if [[ "${UPDATE_IIS}" == true && -z "${IIS_REV}" ]]; then
    echo "Error: --iis-rev required when --iis-version is specified"
    exit 1
fi
if [[ "${UPDATE_IOTEDGE}" == true && -z "${IIS_REV}" ]]; then
    echo "Error: --iis-rev required for IoT Edge updates (needed for path fixing)"
    exit 1
fi
if [[ "${UPDATE_IOTEDGE}" != true && "${UPDATE_IIS}" != true ]]; then
    echo "Error: Must specify at least --iotedge-version or --iis-version"
    usage
    exit 1
fi

# Clean old recipes if requested
if [[ "${CLEAN}" == true ]]; then
    echo "Cleaning old recipe files..."
    if [[ "${UPDATE_IOTEDGE}" == true ]]; then
        for dir in iotedge aziot-edged; do
            find "${ROOT_DIR}/recipes-core/${dir}" -name "*_*.bb" -type f -delete 2>/dev/null || true
            find "${ROOT_DIR}/recipes-core/${dir}" -name "*-[0-9]*.inc" -type f -delete 2>/dev/null || true
        done
    fi
    if [[ "${UPDATE_IIS}" == true ]]; then
        for dir in aziotd aziotctl aziot-keys; do
            find "${ROOT_DIR}/recipes-core/${dir}" -name "*_*.bb" -type f -delete 2>/dev/null || true
            find "${ROOT_DIR}/recipes-core/${dir}" -name "*-[0-9]*.inc" -type f -delete 2>/dev/null || true
        done
    fi
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

if [[ "${UPDATE_IOTEDGE}" == true ]]; then
    echo "Updating IoT Edge to ${IOTEDGE_VERSION} (${IOTEDGE_REV:0:8})"
    
    IOTEDGE_DIR="${WORKDIR}/iotedge"
    prepare_repo "${IOTEDGE_REPO}" "${IOTEDGE_DIR}" "${IOTEDGE_REV}"
    normalize_cargo_config "${IOTEDGE_DIR}/edgelet/.cargo"
    
    # Generate recipes
    for pkg in aziot-edged iotedge; do
        pushd "${IOTEDGE_DIR}/edgelet/${pkg}" >/dev/null
        retry "cargo bitbake (${pkg})" env CARGO_HOME="${CARGO_HOME_DIR}" cargo bitbake
        bb_file=$(ls "${pkg}_"*.bb | head -1)
        popd >/dev/null
        copy_recipe "${pkg}" "${IOTEDGE_DIR}/edgelet/${pkg}/${bb_file}" \
            "${ROOT_DIR}/recipes-core/${pkg}" "${IOTEDGE_VERSION}"
    done
    
    # Clone IIS repo to get crate subdirectory paths for fixing recipes
    IIS_PATH="${WORKDIR}/iot-identity-service"
    prepare_repo "${IIS_REPO}" "${IIS_PATH}" "${IIS_REV}"
    
    # Fix recipes
    for pkg in aziot-edged iotedge; do
        recipe="${ROOT_DIR}/recipes-core/${pkg}/${pkg}_${IOTEDGE_VERSION}.bb"
        python3 "${HELPERS}" fix-cargo-paths "${IIS_PATH}" "${recipe}"
        fix_srcrev "${recipe}" "${IIS_REV}"
        generate_patch "${IOTEDGE_DIR}" "${ROOT_DIR}/recipes-core/${pkg}/files/0001-Remove-git-from-Cargo.patch" "${pkg}"
        sync_checksums "${pkg}" "${IOTEDGE_VERSION}" "${IOTEDGE_DIR}/edgelet/Cargo.lock"
    done
fi

if [[ "${UPDATE_IIS}" == true ]]; then
    echo "Updating IIS to ${IIS_VERSION} (${IIS_REV:0:8})"
    
    IIS_DIR="${WORKDIR}/iot-identity-service"
    if [[ ! -d "${IIS_DIR}" ]]; then
        prepare_repo "${IIS_REPO}" "${IIS_DIR}" "${IIS_REV}"
    fi
    normalize_cargo_config "${IIS_DIR}/.cargo"
    
    # Generate recipes
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
fi

# Validate recipes with bitbake (skip with --skip-validate)
if [[ "${SKIP_VALIDATE}" != true ]]; then
    echo "Validating recipes with bitbake..."
    VALIDATE_DIR=$(mktemp -d)
    
    # Fetch required layers
    retry "fetch poky" git clone --depth=1 --branch scarthgap git://git.yoctoproject.org/poky "${VALIDATE_DIR}/poky"
    retry "fetch meta-openembedded" git clone --depth=1 --branch scarthgap git://git.openembedded.org/meta-openembedded "${VALIDATE_DIR}/meta-openembedded"
    retry "fetch meta-rust-bin" git clone --depth=1 --branch master https://github.com/rust-embedded/meta-rust-bin.git "${VALIDATE_DIR}/meta-rust-bin"
    retry "fetch meta-virtualization" git clone --depth=1 --branch scarthgap git://git.yoctoproject.org/meta-virtualization "${VALIDATE_DIR}/meta-virtualization"
    
    # Source build environment and set up layers
    pushd "${VALIDATE_DIR}" >/dev/null
    set +u  # oe-init-build-env uses unset variables
    . poky/oe-init-build-env build >/dev/null
    set -u
    
    # Allow running as root (CI containers) and silence meta-virtualization warning
    echo 'INHERIT:remove = "sanity"' >> conf/local.conf
    echo 'SKIP_META_VIRT_SANITY_CHECK = "1"' >> conf/local.conf
    
    bitbake-layers add-layer "${VALIDATE_DIR}/meta-openembedded/meta-oe"
    bitbake-layers add-layer "${VALIDATE_DIR}/meta-openembedded/meta-python"
    bitbake-layers add-layer "${VALIDATE_DIR}/meta-openembedded/meta-networking"
    bitbake-layers add-layer "${VALIDATE_DIR}/meta-openembedded/meta-filesystems"
    bitbake-layers add-layer "${VALIDATE_DIR}/meta-rust-bin"
    bitbake-layers add-layer "${VALIDATE_DIR}/meta-virtualization"
    bitbake-layers add-layer "${ROOT_DIR}"
    
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
