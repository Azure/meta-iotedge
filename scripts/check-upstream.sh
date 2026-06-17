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

# Pick the highest version from stdin (one per line), prerelease-aware.
#
# GNU `sort -V` orders a prerelease ABOVE its final release (1.6.0-rc.1 sorts
# after 1.6.0), which is wrong for picking the "current" recipe during an
# rc -> final overlap. This uses the same semver rule as compare_versions: a
# prerelease sorts BELOW its final release, and rc.1 < rc.2. Pure numeric
# (1.5.x) ordering is unchanged. Empty input yields empty output.
version_max() {
    python3 -c '
import sys, re

def key(v):
    # Split "1.6.0-rc.1" into a release tuple plus a prerelease key where a
    # final release ((1,)) ranks above any prerelease ((0, n)) for the same
    # release. Unrecognized shapes fall back to a numeric-prefix parse so we
    # never crash; trailing junk sorts low.
    m = re.match(r"^(\d+(?:\.\d+)*)(?:[-.]?(?:rc|alpha|beta|pre)[.]?(\d+)?.*)?$", v, re.I)
    if not m:
        nums = re.findall(r"\d+", v)
        return ([int(n) for n in nums] or [0], (1,))
    rel = [int(x) for x in m.group(1).split(".")]
    if re.search(r"(rc|alpha|beta|pre)", v, re.I):
        pre = (0, int(m.group(2)) if m.group(2) else 0)
    else:
        pre = (1,)
    return (rel, pre)

vals = [l.strip() for l in sys.stdin if l.strip()]
if vals:
    # Pad release tuples to equal length so comparisons are well-defined.
    width = max(len(key(v)[0]) for v in vals)
    def padded(v):
        rel, pre = key(v)
        return (rel + [0] * (width - len(rel)), pre)
    print(max(vals, key=padded))
'
}

# Get current recipe version from recipe files, scoped to a major.minor line.
#
# During 1.5/1.6 LTS overlap, recipes-core/ holds both lines at once. The bot
# must compare against the line that matches the channel it is updating (the
# lts channel's daemon major.minor), not just the highest recipe on disk.
# Pass a major.minor like "1.5" to restrict the match; pass "" to fall back to
# the highest version across all lines (legacy behavior).
get_recipe_version() {
    local recipe_dir="$1"
    local prefix="$2"
    local mm="${3:-}"
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
        # Restrict to the requested major.minor line when one is given.
        if [[ -n "$mm" && "$version" != "${mm}."* ]]; then
            continue
        fi
        versions+=("$version")
    done
    
    if [[ ${#versions[@]} -eq 0 ]]; then
        echo ""
        return
    fi
    
    # Return the highest version (prerelease-aware: rc sorts below final).
    printf '%s\n' "${versions[@]}" | version_max
}

# Get IOTEDGE_RELEASE from the version-specific .inc file, scoped to a line.
# This tracks the upstream release tag, which may differ from the recipe
# filename version when a release only updates Docker images.
# Pass a major.minor like "1.5" to pick the .inc for that line; pass "" to use
# the highest .inc across all lines (legacy behavior).
get_recipe_release() {
    local recipe_dir="$1"
    local prefix="$2"
    local mm="${3:-}"
    local full_path="${REPO_ROOT}/${recipe_dir}"
    
    # Find the version .inc file (excluding the -crates.inc sibling). When a
    # major.minor is given, match only that line's .inc; otherwise take the
    # highest across all lines. A glob + loop avoids ls|grep and stays robust
    # to filenames (recipe names are controlled, but this is cleaner).
    local candidates=()
    local f
    if [[ -n "$mm" ]]; then
        for f in "${full_path}/${prefix}-${mm}."*.inc; do
            [[ -e "$f" ]] || continue
            [[ "$f" == *-crates.inc ]] && continue
            candidates+=("$f")
        done
    else
        for f in "${full_path}/${prefix}"-[0-9]*.inc; do
            [[ -e "$f" ]] || continue
            [[ "$f" == *-crates.inc ]] && continue
            candidates+=("$f")
        done
    fi
    local inc_file=""
    if [[ ${#candidates[@]} -gt 0 ]]; then
        # Pick the candidate with the highest version (prerelease-aware: rc
        # sorts below final). Map each .inc path to its version, choose the
        # max, then resolve back to the file. `sort -V` is wrong here because
        # it orders an rc above its final release.
        local best_ver
        best_ver=$(
            for f in "${candidates[@]}"; do
                local b="${f##*/}"; b="${b%.inc}"; echo "${b#${prefix}-}"
            done | version_max
        )
        for f in "${candidates[@]}"; do
            local b="${f##*/}"; b="${b%.inc}"
            if [[ "${b#${prefix}-}" == "${best_ver}" ]]; then
                inc_file="$f"
                break
            fi
        done
    fi
    [[ -n "${inc_file}" ]] || return
    
    # Extract IOTEDGE_RELEASE value
    grep 'IOTEDGE_RELEASE' "${inc_file}" 2>/dev/null | sed 's/.*= *"//;s/".*//' || true
}

# Compare two semver-ish versions, prerelease/suffix-safe.
# Returns: -1 if a < b, 0 if a == b, 1 if a > b.
#
# The old IFS='.' parse crashed on "1.6.0-rc.1" (a_patch became "0-rc.1", and
# (( ... )) raised an arithmetic syntax error that, under set -e, killed the
# job). This delegates to a tiny dependency-free Python comparator that orders
# by the numeric release first, then applies the semver rule that a prerelease
# sorts BELOW its final release (1.6.0-rc.1 < 1.6.0) and rc.1 < rc.2. Pure
# numeric 1.5.x comparisons are unchanged. We avoid `sort -V` here because GNU
# sort orders a prerelease ABOVE its final release, which would make the bot
# miss an rc -> final upgrade.
compare_versions() {
    local a="$1"
    local b="$2"
    
    if [[ -z "$a" || -z "$b" ]]; then
        echo "0"
        return
    fi
    
    if [[ "$a" == "$b" ]]; then
        echo "0"
        return
    fi
    
    A="$a" B="$b" python3 -c '
import os, re, sys

def parse(v):
    # Split "1.6.0-rc.1" into release tuple (1,6,0) and prerelease key.
    # A missing prerelease ranks ABOVE any prerelease for the same release.
    m = re.match(r"^(\d+(?:\.\d+)*)(?:[-.]?(?:rc|alpha|beta|pre)[.]?(\d+)?.*)?$", v, re.I)
    if not m:
        # Unrecognized shape: fall back to a numeric-prefix parse so we never
        # crash; trailing junk sorts low.
        nums = re.findall(r"\d+", v)
        return ([int(n) for n in nums] or [0], (1,))
    rel = [int(x) for x in m.group(1).split(".")]
    has_pre = bool(re.search(r"(rc|alpha|beta|pre)", v, re.I))
    if has_pre:
        pre_num = int(m.group(2)) if m.group(2) else 0
        # (0, pre_num) sorts below (1,) used for final releases.
        pre_key = (0, pre_num)
    else:
        pre_key = (1,)
    return (rel, pre_key)

def norm(rel_a, rel_b):
    # Pad release tuples to equal length for comparison.
    n = max(len(rel_a), len(rel_b))
    return rel_a + [0] * (n - len(rel_a)), rel_b + [0] * (n - len(rel_b))

ra, ka = parse(os.environ["A"])
rb, kb = parse(os.environ["B"])
ra, rb = norm(ra, rb)
ka_full = (ra, ka)
kb_full = (rb, kb)
print(-1 if ka_full < kb_full else (1 if ka_full > kb_full else 0))
'
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

# Scope the recipe comparison to the LTS channel's line. During 1.5/1.6 LTS
# overlap, recipes-core/ holds both lines; the bot must update the line that
# matches the channel it is tracking (the lts daemon's major.minor), not the
# highest recipe on disk. Derive the major.minor from the daemon version so a
# 1.5.x channel compares against the 1.5 recipe and a future 1.6.x channel
# compares against the 1.6 recipe.
CHANNEL_MM=$(echo "$DAEMON_VERSION" | cut -d. -f1,2)
log "   Tracking LTS line: ${CHANNEL_MM}.x"

# Derive the Yocto template for this line so the workflow can pass --template
# to update-recipes.sh (1.6.* -> wrynose, otherwise scarthgap). The container
# image is release-neutral, so only the template argument changes.
case "$CHANNEL_MM" in
    1.6) TEMPLATE="wrynose" ;;
    *)   TEMPLATE="scarthgap" ;;
esac

# Get current recipe version (daemon version from filename) for THIS line.
CURRENT_RECIPE=$(get_recipe_version "recipes-core/iotedge" "iotedge" "${CHANNEL_MM}")
# Get tracked release version from .inc (may differ from recipe version
# when a release only updates Docker images, not daemon binaries) for THIS line.
CURRENT_RELEASE=$(get_recipe_release "recipes-core/iotedge" "iotedge" "${CHANNEL_MM}")
# Fall back to recipe version if IOTEDGE_RELEASE is not set (older recipes)
: "${CURRENT_RELEASE:=${CURRENT_RECIPE}}"
log "📋 Current recipe version (${CHANNEL_MM}.x line): ${CURRENT_RECIPE:-not found}"
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
    "template": "${TEMPLATE}",
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
    echo "template=${TEMPLATE}"
    echo "needs_update=${NEEDS_UPDATE}"
    echo "is_significant=${IS_SIGNIFICANT}"
    echo "update_type=${UPDATE_TYPE}"
fi
