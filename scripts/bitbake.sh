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

source ${DIR}/poky/oe-init-build-env build

bitbake ${targets}
