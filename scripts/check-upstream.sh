#!/usr/bin/env bash
# Check both maintained upstream LTS products. No repository writes.
# --plans-json: list of plans, newest supported line first. Each contains
# release_version, daemon_version, iis_version, template, line, update_type,
# needs_update, current_release, current_recipe, current_iis, is_significant.
# --json and default key=value retain the legacy single-product interface.
# New callers MUST use --plans-json so the second LTS line is not lost.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODE="${1:-}"
case "$MODE" in
    ""|--json|--plans-json) ;;
    -h|--help) echo "Usage: check-upstream.sh [--json|--plans-json]"; exit 0 ;;
    *) echo "Unknown argument: $MODE" >&2; exit 1 ;;
esac
[[ $# -le 1 ]] || { echo "Too many arguments" >&2; exit 1; }
echo "Fetching product-versions.json (both supported LTS products)..." >&2
curl -fsSL "https://raw.githubusercontent.com/Azure/azure-iotedge/main/product-versions.json" |
    python3 "${SCRIPT_DIR}/release_versions.py" plans "$REPO_ROOT" "$MODE"
