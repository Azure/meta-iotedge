#!/bin/bash

# what container are we using to build this
# default to a public Yocto build image; override with CONTAINER env var if needed
CONTAINER="${CONTAINER:-crops/poky:ubuntu-22.04}"

einfo() {
	echo "$*" >&2
}

die() {
    echo "$*" >&2
    exit 1
}

# Save the commands for future use
TEMPLATE=${1}
cmd=${@:2}

# If no command was specified, just drop us into a shell if we're interactive
[ $# -eq 0 ] && tty -s && cmd="/bin/bash"

# user and group we are running as to ensure files created inside
# the container retain the same permissions
my_uid=$(id -u)
my_gid=$(id -g)

# Some build images require a non-zero gid for the workspace mount.
if [[ "${my_gid}" == "0" ]]; then
    alt_gid=$(id -G | tr ' ' '\n' | grep -v '^0$' | head -n 1)
    if [[ -n "${alt_gid}" ]]; then
        my_gid="${alt_gid}"
    else
        my_gid="1000"
    fi
fi

# Are we in an interactive terminal?
tty -s && termint=t

# Fetch the latest version of the container
einfo "*** Ensuring local container is up to date"
docker pull ${CONTAINER} > /dev/null || die "Failed to update docker container"

# Ensure we've got what we need for SSH_AUTH_SOCK
if [[ -n ${SSH_AUTH_SOCK} ]]; then
	SSH_AUTH_DIR=$(dirname $(readlink -f ${SSH_AUTH_SOCK}))
	SSH_AUTH_NAME=$(basename ${SSH_AUTH_SOCK})
fi

# Kick off Docker
einfo "*** Launching container ..."
exec docker run \
    --cap-add SETFCAP \
    -e BUILD_UID=${my_uid} \
    -e BUILD_GID=${my_gid} \
    -e BB_SERVER_TIMEOUT=${BB_SERVER_TIMEOUT:-600} \
    -e BB_COMMAND_TIMEOUT=${BB_COMMAND_TIMEOUT:-300} \
    -e TEMPLATECONF=meta-iotedge/conf/templates/${TEMPLATE} \
    -e MACHINE=${MACHINE:-qemux86-64} \
    ${SSH_AUTH_SOCK:+-e SSH_AUTH_SOCK="/tmp/ssh-agent/${SSH_AUTH_NAME}"} \
    -v ${HOME}/.ssh:/var/build/.ssh \
    -v ${PWD}:/var/build:rw \
    --workdir=/var/build \
    ${SSH_AUTH_SOCK:+-v "${SSH_AUTH_DIR}":/tmp/ssh-agent} \
    ${EXTRA_CONTAINER_ARGS} \
    -${termint}i --rm -- \
    ${CONTAINER} \
    ${cmd}

