#!/bin/bash
# Prepare only the agent-local downloads/sstate directories, never their contents.
set -euo pipefail

cache_root=${1:-/workspaces/yocto-cache}
while [[ "$cache_root" != / && "$cache_root" == */ ]]; do
    cache_root=${cache_root%/}
done
# Local-only preparation: validate every existing cache directory before writes.
# This does not mount storage or establish pre-container host readiness.
for directory in "$cache_root" "$cache_root/downloads" "$cache_root/sstate-cache"; do
    if [[ -L "$directory" ]]; then
        echo "Cache directory must not be a symlink: $directory" >&2
        exit 1
    fi
    if [[ "$directory" == "$cache_root" || -e "$directory" ]]; then
        case "$(stat -f -c %T -- "$directory")" in
            ext2/ext3|xfs|btrfs|overlayfs|tmpfs) ;;
            *) echo "Unsupported cache filesystem: only agent-local storage is supported" >&2; exit 1 ;;
        esac
    fi
done
# 1001:1001 matches useradd's existing allocation in the CI devcontainer.
if getent passwd 1001 >/dev/null || getent passwd builder >/dev/null; then
    echo "Build user builder/UID 1001 is already in use" >&2
    exit 1
fi
groupadd --gid 1001 builder
useradd -m --uid 1001 --gid 1001 builder
for name in downloads sstate-cache; do
    install -d -o builder -g builder -- "$cache_root/$name"
    sudo -u builder -- bash -euc '
        probe=$(mktemp "$1/.write-test.XXXXXX")
        trap '\''rm -f -- "$probe"'\'' EXIT
        printf "cache readiness\\n" > "$probe"
    ' bash "$cache_root/$name"
done
