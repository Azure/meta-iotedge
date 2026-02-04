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

# Find aziot-edge in stable channel
stable = next((c for c in data.get('channels', []) if c.get('name') == 'stable'), None)
if not stable:
    print("error=No stable channel found", file=sys.stderr)
    sys.exit(1)

aziot_edge = next((p for p in stable.get('products', []) if p.get('id') == 'aziot-edge'), None)
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

# Get current recipe version
CURRENT_RECIPE=$(get_recipe_version "recipes-core/iotedge" "iotedge")
log "📋 Current recipe version: ${CURRENT_RECIPE:-not found}"

# Determine update status
NEEDS_UPDATE=false
IS_SIGNIFICANT=false
UPDATE_TYPE="none"

if [[ -n "$CURRENT_RECIPE" ]]; then
    recipe_vs_release=$(compare_versions "$CURRENT_RECIPE" "$RELEASE_VERSION")
    recipe_vs_daemon=$(compare_versions "$CURRENT_RECIPE" "$DAEMON_VERSION")
    
    if [[ "$recipe_vs_release" == "-1" ]]; then
        # Recipe is behind release version
        if [[ "$recipe_vs_daemon" == "-1" ]]; then
            # Daemon changed → significant update needed
            NEEDS_UPDATE=true
            IS_SIGNIFICANT=true
            UPDATE_TYPE="significant"
            log "   ⚠️ Significant update needed: ${CURRENT_RECIPE} → ${RELEASE_VERSION} (daemon: ${DAEMON_VERSION})"
        else
            # Daemon unchanged → Docker-only
            UPDATE_TYPE="docker-only"
            log "   ℹ️ Docker-only update available: ${CURRENT_RECIPE} → ${RELEASE_VERSION} (daemon unchanged at ${DAEMON_VERSION})"
        fi
    else
        log "✅ Already at latest release version"
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
    echo "needs_update=${NEEDS_UPDATE}"
    echo "is_significant=${IS_SIGNIFICANT}"
    echo "update_type=${UPDATE_TYPE}"
fi
