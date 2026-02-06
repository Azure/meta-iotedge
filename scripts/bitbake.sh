#!/bin/bash
#
# Simple script to set up our build environment and bitbake the desired targets.
#
set -x

# This file should be in the "<repo>/scripts" directory. We put all relevant sources in "<repo>/poky", 
# This finds "<repo>"
SCRIPT_DIR=$(dirname $0)
DIR=${SCRIPT_DIR%/scripts}

# build targets
targets=$@

# allow longer startup for the bitbake server in containerized builds
export BB_SERVER_TIMEOUT="${BB_SERVER_TIMEOUT:-600}"
export BB_COMMAND_TIMEOUT="${BB_COMMAND_TIMEOUT:-300}"

source ${DIR}/poky/oe-init-build-env build

# Ensure BB_COMMAND_TIMEOUT survives BitBake's environment cleanup
export BB_ENV_PASSTHROUGH_ADDITIONS="${BB_ENV_PASSTHROUGH_ADDITIONS:+${BB_ENV_PASSTHROUGH_ADDITIONS} }BB_COMMAND_TIMEOUT"

# remove stale BitBake server state
rm -f bitbake.sock bitbake.lock bitbake-cookerdaemon.log

# ensure patched BitBake server code is loaded (clear pyc cache)
rm -f ${DIR}/poky/bitbake/lib/bb/server/__pycache__/process.*.pyc 2>/dev/null || true

# Parse-check all recipes before starting the build.
# This catches syntax errors and dependency issues cheaply (~1-2 min)
# before committing to an expensive full build.
echo "Validating recipes (bitbake -p)..."
bitbake -p
echo "✓ Recipe parse validation passed"

bitbake -T "${BB_SERVER_TIMEOUT}" ${targets}
