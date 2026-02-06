FROM crops/poky:ubuntu-22.04

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        openssh-client \
        python3 \
        python3-pip \
        qemu-system-x86 \
        qemu-utils \
        sshpass \
    && rm -rf /var/lib/apt/lists/* \
    && if ! getent group "${USER_GID}" >/dev/null; then groupadd --gid "${USER_GID}" "${USERNAME}"; fi \
    && if ! id -u "${USERNAME}" >/dev/null 2>&1; then useradd -m -s /bin/bash --uid "${USER_UID}" --gid "${USER_GID}" "${USERNAME}"; fi \
    && if command -v sudo >/dev/null 2>&1; then echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}" && chmod 0440 "/etc/sudoers.d/${USERNAME}"; fi
USER ${USERNAME}

# Environment for Yocto/BitBake builds
ENV BB_SERVER_TIMEOUT=600
ENV BB_COMMAND_TIMEOUT=300
ENV DEVCONTAINER=1

# Rust toolchain is no longer needed in the dev container since we
# adopted cargo-update-recipe-crates (crates.inc files are generated
# by scripts/recipe_helpers.py from Cargo.lock without cargo-bitbake).
