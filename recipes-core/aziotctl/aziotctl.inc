DEPENDS += "openssl virtual/docker"
RDEPENDS:${PN} += "docker"

export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"

# Set the Rust toolchain to nightly
export RUSTUP_TOOLCHAIN="nightly"

do_configure() {
    export CARGO_HOME="${WORKDIR}/cargo_home"

    # Install rustup if not already installed
    if [ ! -x "$(command -v rustup)" ]; then
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source $HOME/.cargo/env
    fi

    rustup toolchain install nightly
    rustup default nightly
}

do_compile() {
    export CARGO_HOME="${WORKDIR}/cargo_home"
    source $HOME/.cargo/env
    cargo +nightly build -Z namespaced-features --release --target=${RUST_TARGET_SYS}
}

do_install () {
    # Binaries
    install -d  "${D}${bindir}"
    install -m 755 "${WORKDIR}/build/target/${RUST_TARGET_SYS}/release/aziotctl" ${D}${bindir}/aziotctl
}