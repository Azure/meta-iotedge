#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  update-recipes.sh [options]

Options:
  --iotedge-rev <sha>           IoT Edge git commit SHA (iotedge repo).
  --iotedge-version <ver>       IoT Edge version (e.g., 1.5.21).
  --iis-rev <sha>               IoT Identity Service git commit SHA.
  --iis-version <ver>           IoT Identity Service version (e.g., 1.5.21).
  --workdir <path>              Work directory (default: mktemp).
  --keep-workdir                Do not delete work directory.
  --overwrite                   Overwrite existing recipe files.
    --no-sync-checksums           Do not copy SRC_URI checksums from previous recipes.
  -h, --help                    Show this help.

Examples:
  ./scripts/update-recipes.sh \
    --iotedge-rev <sha> --iotedge-version 1.5.21 \
    --iis-rev <sha> --iis-version 1.5.21
EOF
}

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WORKDIR=""
KEEP_WORKDIR="false"
OVERWRITE="false"
SYNC_CHECKSUMS="true"
IOTEDGE_REV=""
IOTEDGE_VERSION=""
IIS_REV=""
IIS_VERSION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --iotedge-rev) IOTEDGE_REV="$2"; shift 2;;
        --iotedge-version) IOTEDGE_VERSION="$2"; shift 2;;
        --iis-rev) IIS_REV="$2"; shift 2;;
        --iis-version) IIS_VERSION="$2"; shift 2;;
        --workdir) WORKDIR="$2"; shift 2;;
        --keep-workdir) KEEP_WORKDIR="true"; shift;;
        --overwrite) OVERWRITE="true"; shift;;
        --no-sync-checksums) SYNC_CHECKSUMS="false"; shift;;
        -h|--help) usage; exit 0;;
        *) echo "Unknown arg: $1"; usage; exit 1;;
    esac
 done

if [[ -z "${WORKDIR}" ]]; then
    WORKDIR=$(mktemp -d)
fi

CARGO_HOME_DIR=$(mktemp -d)

cleanup() {
    if [[ "${KEEP_WORKDIR}" != "true" ]]; then
        rm -rf "${WORKDIR}"
    fi
    rm -rf "${CARGO_HOME_DIR}"
}
trap cleanup EXIT

require() {
    command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1"; exit 1; }
}

require git
require cargo
require python3

PATCHER="${ROOT_DIR}/scripts/patch-bitbake.py"

prepare_repo() {
    local repo_url="$1"
    local repo_dir="$2"
    local repo_rev="$3"

    if [[ -d "${repo_dir}" ]]; then
        rm -rf "${repo_dir}"
    fi

    git clone "${repo_url}" "${repo_dir}"
    git -C "${repo_dir}" checkout "${repo_rev}"
}

normalize_iotedge_cargo_config() {
    local repo_dir="$1"
    local cargo_dir="${repo_dir}/edgelet/.cargo"
    if [[ -d "${cargo_dir}" ]]; then
        if [[ -f "${cargo_dir}/config.toml" ]]; then
            cp "${cargo_dir}/config.toml" "${cargo_dir}/config.toml.bak"
        fi
        if [[ -f "${cargo_dir}/config" ]]; then
            cp "${cargo_dir}/config" "${cargo_dir}/config.bak"
        fi
        rm -f "${cargo_dir}/config.toml" "${cargo_dir}/config"
        cat > "${cargo_dir}/config.toml" <<'EOF'
[source.crates-io]
registry = "https://github.com/rust-lang/crates.io-index"

[net]
git-fetch-with-cli = true
EOF
    fi
}

normalize_iis_cargo_config() {
    local repo_dir="$1"
    local cargo_dir="${repo_dir}/.cargo"
    if [[ -d "${cargo_dir}" ]]; then
        if [[ -f "${cargo_dir}/config.toml" ]]; then
            cp "${cargo_dir}/config.toml" "${cargo_dir}/config.toml.bak"
        fi
        if [[ -f "${cargo_dir}/config" ]]; then
            cp "${cargo_dir}/config" "${cargo_dir}/config.bak"
        fi
        rm -f "${cargo_dir}/config.toml" "${cargo_dir}/config"
        cat > "${cargo_dir}/config.toml" <<'EOF'
[source.crates-io]
registry = "https://github.com/rust-lang/crates.io-index"

[net]
git-fetch-with-cli = true
EOF
    fi
}

copy_recipe() {
    local component="$1"
    local src_file="$2"
    local dest_dir="$3"
    local version="$4"

    local dest_bb="${dest_dir}/${component}_${version}.bb"
    local dest_inc="${dest_dir}/${component}-${version}.inc"

    if [[ -e "${dest_bb}" || -e "${dest_inc}" ]]; then
        if [[ "${OVERWRITE}" != "true" ]]; then
            echo "Refusing to overwrite existing recipe files for ${component} ${version}. Use --overwrite."
            exit 1
        fi
    fi

    python3 "${PATCHER}" --component "${component}" --input "${src_file}" --output "${dest_bb}"
    printf 'export VERSION = "%s"\n' "${version}" > "${dest_inc}"
}

sync_checksums_from_previous() {
    local component="$1"
    local version="$2"
    local dest_bb="${ROOT_DIR}/recipes-core/${component}/${component}_${version}.bb"
    local recipe_dir="${ROOT_DIR}/recipes-core/${component}"

    [[ -f "${dest_bb}" ]] || return 0
    [[ -d "${recipe_dir}" ]] || return 0

    mapfile -t candidates < <(ls "${recipe_dir}/${component}_"*.bb 2>/dev/null | sort -V)
    local prev=""
    for candidate in "${candidates[@]}"; do
        local base
        base=$(basename "${candidate}")
        local ver
        ver=${base#${component}_}
        ver=${ver%.bb}
        if [[ "${ver}" != "${version}" ]]; then
            prev="${candidate}"
        fi
    done

    [[ -n "${prev}" ]] || return 0

    mapfile -t checksum_lines < <(grep -E '^SRC_URI\[.*\.sha256sum\] = ' "${prev}" || true)
    if [[ ${#checksum_lines[@]} -eq 0 ]]; then
        return 0
    fi

    for line in "${checksum_lines[@]}"; do
        local key
        key=$(echo "${line}" | cut -d= -f1)
        if ! grep -qF "${key}" "${dest_bb}"; then
            echo "${line}" >> "${dest_bb}"
        fi
    done
}

add_checksums_from_cargo_lock() {
    local component="$1"
    local version="$2"
    local lockfile="$3"
    local dest_bb="${ROOT_DIR}/recipes-core/${component}/${component}_${version}.bb"

    [[ -f "${dest_bb}" ]] || return 0
    [[ -f "${lockfile}" ]] || return 0

    python3 - "${dest_bb}" "${lockfile}" <<'PY'
import re
import sys

recipe = sys.argv[1]
lockfile = sys.argv[2]

pkgs = {}
name = version = checksum = None
with open(lockfile, "r", encoding="utf-8") as fh:
    for raw in fh:
        line = raw.strip()
        if line == "[[package]]":
            if name and version and checksum:
                pkgs[(name, version)] = checksum
            name = version = checksum = None
            continue
        if line.startswith("name = "):
            name = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("version = "):
            version = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("checksum = "):
            checksum = line.split("=", 1)[1].strip().strip('"')

if name and version and checksum:
    pkgs[(name, version)] = checksum

existing = set()
with open(recipe, "r", encoding="utf-8") as fh:
    for raw in fh:
        m = re.match(r"SRC_URI\[([^\]]+)\.sha256sum\]", raw)
        if m:
            existing.add(m.group(1))

crate_re = re.compile(r"crate://crates\.io/([^/]+)/([0-9A-Za-z._-]+)")
missing_lines = []
with open(recipe, "r", encoding="utf-8") as fh:
    for raw in fh:
        for m in crate_re.finditer(raw):
            key = f"{m.group(1)}-{m.group(2)}"
            if key in existing:
                continue
            checksum = pkgs.get((m.group(1), m.group(2)))
            if checksum:
                missing_lines.append(f"SRC_URI[{key}.sha256sum] = \"{checksum}\"\n")
                existing.add(key)

if missing_lines:
    with open(recipe, "a", encoding="utf-8") as fh:
        fh.write("\n")
        fh.writelines(missing_lines)
PY
}

if [[ -n "${IOTEDGE_REV}" || -n "${IOTEDGE_VERSION}" ]]; then
    if [[ -z "${IOTEDGE_REV}" || -z "${IOTEDGE_VERSION}" ]]; then
        echo "Both --iotedge-rev and --iotedge-version are required when updating IoT Edge recipes."
        exit 1
    fi

    IOTEDGE_DIR="${WORKDIR}/iotedge"
    prepare_repo "https://github.com/Azure/iotedge.git" "${IOTEDGE_DIR}" "${IOTEDGE_REV}"
    normalize_iotedge_cargo_config "${IOTEDGE_DIR}"

    pushd "${IOTEDGE_DIR}/edgelet/aziot-edged" >/dev/null
    CARGO_HOME="${CARGO_HOME_DIR}" cargo bitbake
    AZIOT_EDGED_BB=$(ls aziot-edged_*.bb | head -n 1)
    popd >/dev/null

    pushd "${IOTEDGE_DIR}/edgelet/iotedge" >/dev/null
    CARGO_HOME="${CARGO_HOME_DIR}" cargo bitbake
    IOTEDGE_BB=$(ls iotedge_*.bb | head -n 1)
    popd >/dev/null

    copy_recipe "aziot-edged" "${IOTEDGE_DIR}/edgelet/aziot-edged/${AZIOT_EDGED_BB}" \
        "${ROOT_DIR}/recipes-core/aziot-edged" "${IOTEDGE_VERSION}"
    copy_recipe "iotedge" "${IOTEDGE_DIR}/edgelet/iotedge/${IOTEDGE_BB}" \
        "${ROOT_DIR}/recipes-core/iotedge" "${IOTEDGE_VERSION}"

    if [[ "${SYNC_CHECKSUMS}" == "true" ]]; then
        add_checksums_from_cargo_lock "aziot-edged" "${IOTEDGE_VERSION}" "${IOTEDGE_DIR}/edgelet/Cargo.lock"
        add_checksums_from_cargo_lock "iotedge" "${IOTEDGE_VERSION}" "${IOTEDGE_DIR}/edgelet/Cargo.lock"
        sync_checksums_from_previous "aziot-edged" "${IOTEDGE_VERSION}"
        sync_checksums_from_previous "iotedge" "${IOTEDGE_VERSION}"
    fi
fi

if [[ -n "${IIS_REV}" || -n "${IIS_VERSION}" ]]; then
    if [[ -z "${IIS_REV}" || -z "${IIS_VERSION}" ]]; then
        echo "Both --iis-rev and --iis-version are required when updating IoT Identity Service recipes."
        exit 1
    fi

    IIS_DIR="${WORKDIR}/iot-identity-service"
    prepare_repo "https://github.com/Azure/iot-identity-service.git" "${IIS_DIR}" "${IIS_REV}"
    normalize_iis_cargo_config "${IIS_DIR}"

    pushd "${IIS_DIR}/key/aziot-keys" >/dev/null
    CARGO_HOME="${CARGO_HOME_DIR}" cargo bitbake
    AZIOT_KEYS_BB=$(ls aziot-keys_*.bb | head -n 1)
    popd >/dev/null

    pushd "${IIS_DIR}/aziotd" >/dev/null
    CARGO_HOME="${CARGO_HOME_DIR}" cargo bitbake
    AZIOTD_BB=$(ls aziotd_*.bb | head -n 1)
    popd >/dev/null

    pushd "${IIS_DIR}/aziotctl" >/dev/null
    CARGO_HOME="${CARGO_HOME_DIR}" cargo bitbake
    AZIOTCTL_BB=$(ls aziotctl_*.bb | head -n 1)
    popd >/dev/null

    copy_recipe "aziot-keys" "${IIS_DIR}/key/aziot-keys/${AZIOT_KEYS_BB}" \
        "${ROOT_DIR}/recipes-core/aziot-keys" "${IIS_VERSION}"
    copy_recipe "aziotd" "${IIS_DIR}/aziotd/${AZIOTD_BB}" \
        "${ROOT_DIR}/recipes-core/aziotd" "${IIS_VERSION}"
    copy_recipe "aziotctl" "${IIS_DIR}/aziotctl/${AZIOTCTL_BB}" \
        "${ROOT_DIR}/recipes-core/aziotctl" "${IIS_VERSION}"

    if [[ "${SYNC_CHECKSUMS}" == "true" ]]; then
        add_checksums_from_cargo_lock "aziot-keys" "${IIS_VERSION}" "${IIS_DIR}/Cargo.lock"
        add_checksums_from_cargo_lock "aziotd" "${IIS_VERSION}" "${IIS_DIR}/Cargo.lock"
        add_checksums_from_cargo_lock "aziotctl" "${IIS_VERSION}" "${IIS_DIR}/Cargo.lock"
        sync_checksums_from_previous "aziot-keys" "${IIS_VERSION}"
        sync_checksums_from_previous "aziotd" "${IIS_VERSION}"
        sync_checksums_from_previous "aziotctl" "${IIS_VERSION}"
    fi
fi

echo "Recipe update complete. Review and commit changes."
