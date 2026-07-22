#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: update-recipes.sh [options]

Options:
    --iotedge-version <ver>   IoT Edge version tag (e.g., 1.5.35)
    --template <name>         Yocto template (kirkstone, scarthgap, or wrynose, default: scarthgap)
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
    ./scripts/update-recipes.sh --iotedge-version 1.6.0-rc.1 --template wrynose
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
if [[ "${TEMPLATE}" != "scarthgap" && "${TEMPLATE}" != "kirkstone" && "${TEMPLATE}" != "wrynose" ]]; then
    echo "Error: --template must be 'scarthgap', 'kirkstone', or 'wrynose'"
    exit 1
fi
echo "Using template: ${TEMPLATE}"

# Recipe shape depends on the Yocto series.
#
# Wrynose (Yocto 6.0) changed two things that the recipe text must follow:
#   1. The default S is now ${UNPACKDIR}/${BP}, and the old explicit
#      S = "${WORKDIR}/git" hard-errors. So on wrynose we omit the S line and
#      let the default apply. On scarthgap/kirkstone we still emit it.
#   2. We carry per-version crates.inc files (<pkg>-<ver>-crates.inc) so the
#      1.5 (scarthgap) and 1.6 (wrynose) recipes can live in the same recipe
#      dir at once. scarthgap/kirkstone keep the legacy shared <pkg>-crates.inc
#      name they have always used.
# Keep both shapes byte-identical to what already ships for each series.
if [[ "${TEMPLATE}" == "wrynose" ]]; then
    PER_VERSION_CRATES=true
    # The 1.6 recipe set lives on `main` and is built by BOTH the Wrynose (6.0)
    # line and the Scarthgap-1.6 (5.0) line, which unpack git source to
    # different paths. A hardcoded S = "${WORKDIR}/git" is correct only on
    # Scarthgap and hard-errors on Wrynose; omitting S is correct only on
    # Wrynose and breaks do_patch/cargo on Scarthgap. Emit an expression that
    # mirrors the git fetcher on either release: source lands at
    # ${UNPACKDIR:-${WORKDIR}}/${BB_GIT_DEFAULT_DESTSUFFIX:-git}, which resolves
    # to ${WORKDIR}/git on Scarthgap and ${WORKDIR}/sources/${BP} on Wrynose.
    S_LINE='# Yocto release-agnostic source dir: mirror the git fetcher so ONE recipe is
# correct on both Yocto lines that build it. git unpacks to
# ${UNPACKDIR:-${WORKDIR}}/${BB_GIT_DEFAULT_DESTSUFFIX:-git}: Scarthgap (5.0)
# leaves both unset -> ${WORKDIR}/git; Wrynose (6.0) sets them -> ${WORKDIR}/
# sources/${BP}. A hardcoded /git breaks Wrynose; omitting S breaks Scarthgap.
S = "${@(d.getVar('"'"'UNPACKDIR'"'"') or d.getVar('"'"'WORKDIR'"'"')) + '"'"'/'"'"' + (d.getVar('"'"'BB_GIT_DEFAULT_DESTSUFFIX'"'"') or '"'"'git'"'"')}"'$'\n'
else
    PER_VERSION_CRATES=false
    # 1.5 (Scarthgap/Kirkstone, Yocto <=5.0): UNPACKDIR is unset and git unpacks
    # to ${WORKDIR}/git, so the legacy explicit S is both correct and required
    # (the default S = ${WORKDIR}/${BP} would point at the wrong dir).
    S_LINE='S = "${WORKDIR}/git"'$'\n'
fi

# Check dependencies early (before first use of curl/git/python3)
for cmd in git python3 curl; do
    command -v "$cmd" >/dev/null || { echo "Missing: $cmd"; exit 1; }
done

# Resolve versions from the IoT Edge release's product-versions.json
echo "Fetching product-versions.json from IoT Edge ${IOTEDGE_VERSION}..."
PRODUCT_VERSIONS_URL="https://raw.githubusercontent.com/Azure/azure-iotedge/${IOTEDGE_VERSION}/product-versions.json"
PRODUCT_VERSIONS=$(curl -fsSL "$PRODUCT_VERSIONS_URL") || {
    echo "Error: Could not fetch product-versions.json for tag ${IOTEDGE_VERSION}"
    exit 1
}

# Extract daemon version and IIS version from product-versions.json
#
# The release tag (e.g. 1.5.35) may only update Docker images while the
# daemon binaries (aziot-edged, iotedge) stay at an earlier version
# (e.g. 1.5.21).  Recipes must use the daemon version so the built
# binaries reference matching container image tags.
read -r IOTEDGE_DAEMON_VERSION IIS_VERSION < <(echo "$PRODUCT_VERSIONS" | IOTEDGE_VERSION="${IOTEDGE_VERSION}" python3 -c "
import json, os, sys
data = json.load(sys.stdin)
release = os.environ['IOTEDGE_VERSION']
channels = data['channels']

def aziot_of(channel):
    return next((p for p in channel['products'] if p['id'] == 'aziot-edge'), None)

# Pick the channel that ships this exact release. Each channel's aziot-edge
# product carries a 'version' field that is the release tag (e.g. 1.5.35 in
# lts, 1.6.0-rc.1 in prerelease). Match on that so a release tag resolves to
# the channel that actually contains it. If several channels match, prefer
# lts (the embedded default). If none match (older product-versions.json that
# predates the version field, or an unexpected layout), fall back to lts so
# existing 1.5 behavior is unchanged.
matches = [c for c in channels if (aziot_of(c) or {}).get('version') == release]
chosen = next((c for c in matches if c['name'] == 'lts'), None) or (matches[0] if matches else None)
if chosen is None:
    chosen = next((c for c in channels if c['name'] == 'lts'), None)
if not chosen:
    print('Error: No matching channel and no lts channel found', file=sys.stderr)
    sys.exit(1)
aziot = aziot_of(chosen)
if not aziot:
    print('Error: No aziot-edge product found', file=sys.stderr)
    sys.exit(1)
daemon = next((c['version'] for c in aziot['components'] if c['name'] == 'aziot-edge'), '')
if not daemon:
    print('Error: No aziot-edge daemon version found', file=sys.stderr)
    sys.exit(1)
iis = next((c['version'] for c in aziot['components'] if c['name'] == 'aziot-identity-service'), '')
if not iis:
    print('Error: No IIS version found', file=sys.stderr)
    sys.exit(1)
print(f'{daemon} {iis}')
")
echo "  IoT Edge release tag: ${IOTEDGE_VERSION}"
echo "  IoT Edge daemon version: ${IOTEDGE_DAEMON_VERSION}"
echo "  IIS version: ${IIS_VERSION}"
if [[ "${IOTEDGE_DAEMON_VERSION}" != "${IOTEDGE_VERSION}" ]]; then
    echo "  Note: Release ${IOTEDGE_VERSION} is a Docker-image-only update; daemon stays at ${IOTEDGE_DAEMON_VERSION}"
fi

# Resolve SHAs from version tags
# Use the daemon version tag for SRCREV (not the release tag) so the
# built binary version matches the source it was compiled from.
echo "Resolving git SHAs..."
IOTEDGE_REV=$(git ls-remote --tags https://github.com/Azure/iotedge.git "refs/tags/${IOTEDGE_DAEMON_VERSION}^{}" "refs/tags/${IOTEDGE_DAEMON_VERSION}" | head -1 | cut -f1)
if [[ -z "${IOTEDGE_REV}" ]]; then
    echo "Error: Could not resolve SHA for tag ${IOTEDGE_DAEMON_VERSION} in Azure/iotedge"
    exit 1
fi
echo "  IoT Edge SHA: ${IOTEDGE_REV} (tag ${IOTEDGE_DAEMON_VERSION})"

IIS_REV=$(git ls-remote --tags https://github.com/Azure/iot-identity-service.git "refs/tags/${IIS_VERSION}^{}" "refs/tags/${IIS_VERSION}" | head -1 | cut -f1)
if [[ -z "${IIS_REV}" ]]; then
    echo "Error: Could not resolve SHA for tag ${IIS_VERSION} in Azure/iot-identity-service"
    exit 1
fi
echo "  IIS SHA: ${IIS_REV}"

# Clean old recipes if requested.
#
# Scope the clean to the major.minor LINE being regenerated. During 1.5/1.6
# LTS overlap, recipes-core/ holds both lines at once; an unscoped clean would
# delete the OTHER line's .bb/.inc files (the ones this run does not
# regenerate), silently dropping a shipped LTS line. We derive the line from
# the daemon and IIS versions (same major.minor) and only remove files that
# belong to it, so regenerating 1.5 never touches 1.6 and vice versa.
if [[ "${CLEAN}" == true ]]; then
    EDGE_MM=$(echo "${IOTEDGE_DAEMON_VERSION}" | cut -d. -f1,2)
    IIS_MM=$(echo "${IIS_VERSION}" | cut -d. -f1,2)
    echo "Cleaning old recipe files for the ${EDGE_MM}.x / ${IIS_MM}.x line..."
    # iotedge + aziot-edged track the edgelet daemon version; the IIS tools
    # track the IIS version. Both belong to the same product line but can
    # carry different patch numbers, so scope each set to its own version.
    for dir in iotedge aziot-edged; do
        find "${ROOT_DIR}/recipes-core/${dir}" -name "*_${EDGE_MM}.*.bb" -type f -delete 2>/dev/null || true
        find "${ROOT_DIR}/recipes-core/${dir}" -name "*-${EDGE_MM}.*.inc" -type f -delete 2>/dev/null || true
    done
    for dir in aziotd aziotctl aziot-keys; do
        find "${ROOT_DIR}/recipes-core/${dir}" -name "*_${IIS_MM}.*.bb" -type f -delete 2>/dev/null || true
        find "${ROOT_DIR}/recipes-core/${dir}" -name "*-${IIS_MM}.*.inc" -type f -delete 2>/dev/null || true
    done
fi

# Setup directories
[[ -z "${WORKDIR}" ]] && WORKDIR=$(mktemp -d)

cleanup() {
    [[ "${KEEP_WORKDIR}" != true ]] && rm -rf "${WORKDIR}"
}
trap cleanup EXIT

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

# Resolve the patch dir for a package version, mirroring bitbake FILESPATH
# precedence: prefer the version-specific dir recipes-core/<pkg>/<pkg>-<ver>/,
# then the newest same-line (same major.minor) version dir, and only then fall
# back to the shared recipes-core/<pkg>/files/ dir. Prints the dir on stdout, or
# nothing if none have .patch files.
#
# The same-line fallback matters for a fresh upstream GA: when e.g. 1.6.0 GAs
# and no 1.6.0/ patch dir exists yet, the previous 1.6.x dir (e.g. 1.6.0-rc.1/)
# is the right source-compat patch set to try. Without it, resolution fell all
# the way through to files/ (the 1.5.x patches), whose Cargo.toml line anchors
# do not match 1.6 source, so 'git apply' failed and the watch-upstream job
# broke on the GA of 1.6.0. Patches are still applied with strict 'git apply',
# so a genuinely incompatible carried patch still fails loudly (as it should);
# this only stops us from picking the wrong LTS line's patches.
resolve_patch_dir() {
    local recipe_dir="$1" pkg="$2" ver="$3"
    if compgen -G "${recipe_dir}/${pkg}-${ver}/*.patch" >/dev/null; then
        echo "${recipe_dir}/${pkg}-${ver}"
        return 0
    fi
    # Newest same major.minor line dir that carries patches (e.g. for 1.6.0,
    # match 1.6.* dirs like 1.6.0-rc.1). cut on '.' yields 1.6 for both 1.6.0
    # and 1.6.0-rc.1. Sort version-aware and take the highest.
    local line same_line_dir
    line=$(echo "${ver}" | cut -d. -f1,2)
    same_line_dir=$(
        for d in "${recipe_dir}/${pkg}-${line}."*/; do
            [[ -d "${d}" ]] || continue
            compgen -G "${d}*.patch" >/dev/null || continue
            basename "${d}"
        done | sort -V | tail -1
    )
    if [[ -n "${same_line_dir}" ]]; then
        echo "${recipe_dir}/${same_line_dir}"
    elif compgen -G "${recipe_dir}/files/*.patch" >/dev/null; then
        echo "${recipe_dir}/files"
    fi
}

# Apply a package version's source-compatibility patches to a checked-out source
# tree before reading its Cargo.lock for crates.inc generation.
#
# Some patches pin a crate version in Cargo.lock (e.g. the 1.6 sysinfo-0.38 pin
# for the Wrynose Rust toolchain). The cargo build runs with --frozen, so the
# crate set it fetches is the one in the PATCHED lock. The generated crates.inc
# must match that, so we apply the same patches here, then generate crates.inc
# from the resulting lock. Patches that only touch Cargo.toml or source files
# (the 1.5 set) leave the lock unchanged, so 1.5 crates.inc output is identical.
#
# The patch FILES stay hand-crafted on disk; this only applies them to a throw
# away checkout in the work dir. It is called once per source tree, before the
# per-package loop, so a shared workspace lock is patched exactly once.
apply_recipe_patches() {
    local src_dir="$1" recipe_dir="$2" pkg="$3" ver="$4"
    local patch_dir
    patch_dir=$(resolve_patch_dir "${recipe_dir}" "${pkg}" "${ver}")
    [[ -z "${patch_dir}" ]] && return 0

    local p
    for p in $(cd "${patch_dir}" && ls -1 *.patch | sort); do
        if git -C "${src_dir}" apply "${patch_dir}/${p}"; then
            echo "  Applied ${pkg} patch to source: ${p}"
        else
            echo "Error: failed to apply ${patch_dir}/${p} to ${src_dir}" >&2
            return 1
        fi
    done
}

# Append the source-compatibility patch SRC_URI for a package version to its
# version-specific .inc.
#
# The patches an edgelet release needs depend on its upstream Cargo.toml and
# source layout, so they are version-specific. We do not hardcode the list:
# we wire up whatever .patch files already live in the recipe's patch dir for
# this version, and let bitbake resolve each file:// at build time.
#
# Patch FILES are kept by hand in version dirs (the patches themselves are
# crafted per release). This function only writes the SRC_URI wiring, so the
# generated .inc always matches the patch files on disk and the consistency
# check stays green.
#
# Directory lookup mirrors bitbake FILESPATH precedence via resolve_patch_dir:
# the version-specific dir recipes-core/<pkg>/<pkg>-<ver>/ first, then the
# shared recipes-core/<pkg>/files/ dir.
append_patch_src_uri() {
    local recipe_dir="$1" pkg="$2" ver="$3" ver_inc="$4"
    local patch_dir
    patch_dir=$(resolve_patch_dir "${recipe_dir}" "${pkg}" "${ver}")
    [[ -z "${patch_dir}" ]] && return 0

    # Sort by filename for deterministic output (0001 before 0002, ...).
    local patches=()
    local p
    for p in $(cd "${patch_dir}" && ls -1 *.patch | sort); do
        patches+=("${p}")
    done
    [[ ${#patches[@]} -eq 0 ]] && return 0

    {
        echo ""
        echo "# Source-compatibility patches for the ${ver} edgelet workspace. The set is"
        echo "# version-specific (the upstream Cargo.toml and source layout differ by"
        echo "# release), so it is wired here rather than in the shared ${pkg}.inc. This"
        echo "# lets 1.5.x and 1.6.x recipes coexist on the same branch. Generated by"
        echo "# scripts/update-recipes.sh from the patch files in the recipe's patch dir."
        if [[ ${#patches[@]} -eq 1 ]]; then
            echo "SRC_URI += \"file://${patches[0]}\""
        else
            local i
            for i in "${!patches[@]}"; do
                if [[ $i -eq 0 ]]; then
                    echo "SRC_URI += \"file://${patches[$i]} \\"
                else
                    echo "            file://${patches[$i]} \\"
                fi
            done
            echo "\""
        fi
    } >> "${ver_inc}"
}

# --- Generate IoT Edge recipes ---

echo "Updating IoT Edge to ${IOTEDGE_DAEMON_VERSION} (${IOTEDGE_REV:0:8})"

IOTEDGE_DIR="${WORKDIR}/iotedge"
prepare_repo "https://github.com/Azure/iotedge.git" "${IOTEDGE_DIR}" "${IOTEDGE_REV}"

# Compute LIC_FILES_CHKSUM md5s from the fetched source. THIRDPARTYNOTICES is
# regenerated each release (the dependency set changes), so its md5 differs by
# version. Read it from the checked-out tree instead of hardcoding, so the
# generated recipe always matches what bitbake checksums at build time. LICENSE
# is stable across releases but we compute it the same way for consistency.
IOTEDGE_LICENSE_MD5=$(md5sum "${IOTEDGE_DIR}/LICENSE" | cut -d' ' -f1)
IOTEDGE_TPN_MD5=$(md5sum "${IOTEDGE_DIR}/THIRDPARTYNOTICES" | cut -d' ' -f1)

# Apply the edgelet source-compatibility patches before reading Cargo.lock.
# aziot-edged and iotedge share the edgelet workspace and wire identical patch
# sets, so apply once from the iotedge patch dir. On wrynose this pins sysinfo
# in the lock; on scarthgap the 1.5 patches do not touch the lock, so crates.inc
# is unchanged.
apply_recipe_patches "${IOTEDGE_DIR}" "${ROOT_DIR}/recipes-core/iotedge" "iotedge" "${IOTEDGE_DAEMON_VERSION}"

for pkg in aziot-edged iotedge; do
    recipe_dir="${ROOT_DIR}/recipes-core/${pkg}"
    bb="${recipe_dir}/${pkg}_${IOTEDGE_DAEMON_VERSION}.bb"
    ver_inc="${recipe_dir}/${pkg}-${IOTEDGE_DAEMON_VERSION}.inc"
    # Per-version crates.inc on wrynose so 1.5 and 1.6 coexist; shared name on
    # scarthgap/kirkstone (see template switch above).
    if [[ "${PER_VERSION_CRATES}" == true ]]; then
        crates_inc="${recipe_dir}/${pkg}-${IOTEDGE_DAEMON_VERSION}-crates.inc"
        crates_require="\${BPN}-\${PV}-crates.inc"
    else
        crates_inc="${recipe_dir}/${pkg}-crates.inc"
        crates_require="\${BPN}-crates.inc"
    fi
    # S line is series-dependent; computed once above as S_LINE.
    s_line="${S_LINE}"

    # Generate .bb (template — only metadata + SRCREV change between versions)
    cat > "${bb}" <<BBEOF
SUMMARY = "$(if [[ "${pkg}" == "aziot-edged" ]]; then echo "The aziot-edged is the main binary for the IoT Edge daemon."; else echo "The iotedge tool is used to manage the IoT Edge runtime."; fi)"
HOMEPAGE = "https://aka.ms/iotedge"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \\
    file://LICENSE;md5=${IOTEDGE_LICENSE_MD5} \\
    file://THIRDPARTYNOTICES;md5=${IOTEDGE_TPN_MD5} \\
"

inherit cargo cargo-update-recipe-crates$(if [[ "${pkg}" == "aziot-edged" ]]; then echo " pkgconfig"; fi)

SRC_URI += "git://github.com/Azure/iotedge.git;protocol=https;nobranch=1"
SRCREV = "${IOTEDGE_REV}"
${s_line}CARGO_SRC_DIR = "edgelet"
CARGO_BUILD_FLAGS += "-p ${pkg}"
CARGO_LOCK_SRC_DIR = "\${S}/edgelet"
do_compile[network] = "1"

require ${crates_require}
require recipes-core/iot-identity-service.inc

include ${pkg}-\${PV}.inc
include ${pkg}.inc
BBEOF
    echo "  Generated ${bb}"

    # Generate version-specific .inc
    cat > "${ver_inc}" <<INCEOF
export VERSION = "${IOTEDGE_DAEMON_VERSION}"
IOTEDGE_RELEASE = "${IOTEDGE_VERSION}"
IIS_SRCREV = "${IIS_REV}"
INCEOF
    # Wire the version's source-compatibility patches (kept on disk per version).
    append_patch_src_uri "${recipe_dir}" "${pkg}" "${IOTEDGE_DAEMON_VERSION}" "${ver_inc}"
    echo "  Generated ${ver_inc}"

    # Generate crates.inc from Cargo.lock
    python3 "${HELPERS}" generate-crates-inc "${IOTEDGE_DIR}/edgelet/Cargo.lock" "${crates_inc}"
done

# --- Generate IIS recipes ---

echo "Updating IIS to ${IIS_VERSION} (${IIS_REV:0:8})"

IIS_DIR="${WORKDIR}/iot-identity-service"
prepare_repo "https://github.com/Azure/iot-identity-service.git" "${IIS_DIR}" "${IIS_REV}"

# Apply the IIS source-compatibility patches before reading Cargo.lock. aziotd,
# aziotctl and aziot-keys share the IIS workspace and wire identical patch sets,
# so apply once from the aziotd patch dir. The current IIS patches only touch
# Cargo.toml, so crates.inc is unchanged; applying keeps crates.inc honest if a
# future IIS patch pins a crate in the lock.
apply_recipe_patches "${IIS_DIR}" "${ROOT_DIR}/recipes-core/aziotd" "aziotd" "${IIS_VERSION}"

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
    cargo_src="${IIS_PKGS[$pkg]}"
    # Per-version crates.inc on wrynose so 1.5 and 1.6 coexist; shared name on
    # scarthgap/kirkstone (see template switch above).
    if [[ "${PER_VERSION_CRATES}" == true ]]; then
        crates_inc="${recipe_dir}/${pkg}-${IIS_VERSION}-crates.inc"
        crates_require="\${BPN}-\${PV}-crates.inc"
    else
        crates_inc="${recipe_dir}/${pkg}-crates.inc"
        crates_require="\${BPN}-crates.inc"
    fi
    # S line is series-dependent; computed once above as S_LINE.
    s_line="${S_LINE}"

    # aziot-keys builds a cdylib (no binary). On wrynose (Yocto 6.0) the cargo
    # bbclass only installs the .so when CARGO_INSTALL_LIBRARIES is set, so wire
    # that for the wrynose shape only. scarthgap/kirkstone install it without
    # the flag, so their recipe stays as-is.
    keys_block=""
    if [[ "${pkg}" == "aziot-keys" && "${PER_VERSION_CRATES}" == true ]]; then
        keys_block=$'\n# aziot-keys builds libaziot_keys.so as a cdylib (no binary). The Yocto 6.0\n# (Wrynose) cargo.bbclass only installs *.so / *.rlib to ${rustlibdir} when\n# CARGO_INSTALL_LIBRARIES is set; otherwise cargo_do_install finds nothing and\n# fails with "Did not find anything to install". ${rustlibdir} is exactly where\n# aziotd/aziot-edged expect it (RUSTFLAGS rpath, see aziotd.inc / issue #182).\nCARGO_INSTALL_LIBRARIES = "1"\n'
    fi

    # Generate .bb
    cat > "${bb}" <<BBEOF
SUMMARY = "${IIS_SUMMARIES[$pkg]}"
HOMEPAGE = "https://azure.github.io/iot-identity-service/"
LICENSE = "MIT"
LIC_FILES_CHKSUM = " \\
    file://LICENSE;md5=4f9c2c296f77b3096b6c11a16fa7c66e \\
"

inherit ${IIS_INHERIT[$pkg]}
${keys_block}
SRC_URI += "${IIS_PROTO[$pkg]}://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1"
SRCREV = "${IIS_REV}"
${s_line}CARGO_SRC_DIR = "${cargo_src}"

require ${crates_require}

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
