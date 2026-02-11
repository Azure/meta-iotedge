#!/usr/bin/env bash
# Check for new upstream IoT Edge releases
# 
# Usage: ./scripts/check-upstream.sh [--json]
#
# Fetches product-versions.json from Azure/azure-iotedge and compares
# against current recipe versions to determine if an update is needed.
#
# Output (without --json):
#   Prints status messages to stderr, key=value pairs to stdout
#
# Output (with --json):
#   Prints JSON object with all version info and update status
#
# Requirements: curl, python3

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

JSON_OUTPUT=false
if [[ "${1:-}" == "--json" ]]; then
    JSON_OUTPUT=true
fi

log() {
    echo "$@" >&2
}

# Get current recipe version from recipe files
get_recipe_version() {
    local recipe_dir="$1"
    local prefix="$2"
    local full_path="${REPO_ROOT}/${recipe_dir}"
    
    if [[ ! -d "$full_path" ]]; then
        echo ""
        return
    fi
    
    # Find recipe files and extract versions
    local versions=()
    for file in "${full_path}/${prefix}_"*.bb; do
        [[ -e "$file" ]] || continue
        local basename
        basename=$(basename "$file")
        local version="${basename#${prefix}_}"
        version="${version%.bb}"
        versions+=("$version")
    done
    
    if [[ ${#versions[@]} -eq 0 ]]; then
        echo ""
        return
    fi
    
    # Sort versions and return highest
    printf '%s\n' "${versions[@]}" | sort -t. -k1,1n -k2,2n -k3,3n | tail -1
}

# Get IOTEDGE_RELEASE from the version-specific .inc file.
# This tracks the upstream release tag, which may differ from the recipe
# filename version when a release only updates Docker images.
get_recipe_release() {
    local recipe_dir="$1"
    local prefix="$2"
    local full_path="${REPO_ROOT}/${recipe_dir}"
    
    # Find the version .inc file (excludes -crates.inc via glob)
    local inc_file
    inc_file=$(ls "${full_path}/${prefix}"-[0-9]*.inc 2>/dev/null | sort -V | tail -1 || true)
    [[ -n "${inc_file}" ]] || return
    
    # Extract IOTEDGE_RELEASE value
    grep 'IOTEDGE_RELEASE' "${inc_file}" 2>/dev/null | sed 's/.*= *"//;s/".*//' || true
}

# Compare two semver versions
# Returns: -1 if a < b, 0 if a == b, 1 if a > b
compare_versions() {
    local a="$1"
    local b="$2"
    
    if [[ -z "$a" || -z "$b" ]]; then
        echo "0"
        return
    fi
    
    IFS='.' read -r a_maj a_min a_patch <<< "$a"
    IFS='.' read -r b_maj b_min b_patch <<< "$b"
    
    # Compare major
    if (( a_maj < b_maj )); then echo "-1"; return; fi
    if (( a_maj > b_maj )); then echo "1"; return; fi
    
    # Compare minor
    if (( a_min < b_min )); then echo "-1"; return; fi
    if (( a_min > b_min )); then echo "1"; return; fi
    
    # Compare patch
    if (( a_patch < b_patch )); then echo "-1"; return; fi
    if (( a_patch > b_patch )); then echo "1"; return; fi
    
    echo "0"
}

# Fetch product-versions.json
log "🔍 Fetching product-versions.json..."
PRODUCT_VERSIONS_URL="https://raw.githubusercontent.com/Azure/azure-iotedge/main/product-versions.json"
PRODUCT_VERSIONS=$(curl -fsSL "$PRODUCT_VERSIONS_URL")

if [[ -z "$PRODUCT_VERSIONS" ]]; then
    log "❌ Failed to fetch product-versions.json"
    exit 1
fi

# Parse versions using Python (write to temp file to avoid quoting issues)
TEMP_JSON=$(mktemp)
echo "$PRODUCT_VERSIONS" > "$TEMP_JSON"
trap "rm -f $TEMP_JSON" EXIT

read_versions=$(python3 << EOF
import json
import sys

with open("$TEMP_JSON") as f:
    data = json.load(f)

# Find aziot-edge in lts channel (preferred for embedded systems)
# During overlap periods with multiple LTS versions, this returns the latest
lts = next((c for c in data.get('channels', []) if c.get('name') == 'lts'), None)
if not lts:
    print("error=No lts channel found", file=sys.stderr)
    sys.exit(1)

aziot_edge = next((p for p in lts.get('products', []) if p.get('id') == 'aziot-edge'), None)
if not aziot_edge:
    print("error=No aziot-edge product found", file=sys.stderr)
    sys.exit(1)

release_version = aziot_edge.get('version', '')
components = aziot_edge.get('components', [])

daemon_version = next((c.get('version', '') for c in components if c.get('name') == 'aziot-edge'), '')

if not daemon_version:
    print("error=No daemon version found", file=sys.stderr)
    sys.exit(1)

print(f"{release_version}")
print(f"{daemon_version}")
EOF
)

# Read the two lines of output
RELEASE_VERSION=$(echo "$read_versions" | sed -n '1p')
DAEMON_VERSION=$(echo "$read_versions" | sed -n '2p')

log "📦 Upstream versions from product-versions.json:"
log "   Release version: ${RELEASE_VERSION}"
log "   Daemon (aziot-edge) version: ${DAEMON_VERSION}"

# Get current recipe version (daemon version from filename)
CURRENT_RECIPE=$(get_recipe_version "recipes-core/iotedge" "iotedge")
# Get tracked release version from .inc (may differ from recipe version
# when a release only updates Docker images, not daemon binaries)
CURRENT_RELEASE=$(get_recipe_release "recipes-core/iotedge" "iotedge")
# Fall back to recipe version if IOTEDGE_RELEASE is not set (older recipes)
: "${CURRENT_RELEASE:=${CURRENT_RECIPE}}"
log "📋 Current recipe version: ${CURRENT_RECIPE:-not found}"
log "   Tracked release: ${CURRENT_RELEASE:-not found}"

# Determine update status
NEEDS_UPDATE=false
IS_SIGNIFICANT=false
UPDATE_TYPE="none"

if [[ -n "$CURRENT_RECIPE" ]]; then
    # Compare the tracked release against the upstream release to decide
    # whether we've already handled this release.
    release_vs_upstream=$(compare_versions "$CURRENT_RELEASE" "$RELEASE_VERSION")
    recipe_vs_daemon=$(compare_versions "$CURRENT_RECIPE" "$DAEMON_VERSION")
    
    if [[ "$release_vs_upstream" != "-1" ]]; then
        # Already tracking this (or newer) release
        log "✅ Already at latest release version"
    elif [[ "$recipe_vs_daemon" == "-1" ]]; then
        # Daemon changed → significant update needed
        NEEDS_UPDATE=true
        IS_SIGNIFICANT=true
        UPDATE_TYPE="significant"
        log "   ⚠️ Significant update needed: ${CURRENT_RECIPE} → ${DAEMON_VERSION} (release: ${RELEASE_VERSION})"
    else
        # Daemon unchanged → Docker-only
        UPDATE_TYPE="docker-only"
        log "   ℹ️ Docker-only update available: release ${RELEASE_VERSION} (daemon unchanged at ${DAEMON_VERSION})"
    fi
else
    log "⚠️ No current recipe found"
    NEEDS_UPDATE=true
    IS_SIGNIFICANT=true
    UPDATE_TYPE="significant"
fi

# Output results
if [[ "$JSON_OUTPUT" == "true" ]]; then
    # Convert bash booleans to Python booleans
    PY_NEEDS_UPDATE="False"
    PY_IS_SIGNIFICANT="False"
    [[ "$NEEDS_UPDATE" == "true" ]] && PY_NEEDS_UPDATE="True"
    [[ "$IS_SIGNIFICANT" == "true" ]] && PY_IS_SIGNIFICANT="True"
    
    python3 << EOF
import json
print(json.dumps({
    "release_version": "${RELEASE_VERSION}",
    "daemon_version": "${DAEMON_VERSION}",
    "current_recipe": "${CURRENT_RECIPE}",
    "current_release": "${CURRENT_RELEASE}",
    "needs_update": ${PY_NEEDS_UPDATE},
    "is_significant": ${PY_IS_SIGNIFICANT},
    "update_type": "${UPDATE_TYPE}"
}, indent=2))
EOF
else
    # Output as key=value for easy parsing
    echo "release_version=${RELEASE_VERSION}"
    echo "daemon_version=${DAEMON_VERSION}"
    echo "current_recipe=${CURRENT_RECIPE}"
    echo "current_release=${CURRENT_RELEASE}"
    echo "needs_update=${NEEDS_UPDATE}"
    echo "is_significant=${IS_SIGNIFICANT}"
    echo "update_type=${UPDATE_TYPE}"
fi
