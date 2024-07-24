DEPENDS += "openssl virtual/docker "
RDEPENDS:${PN} += "docker "

do_configure() {
    ping -c 3 sh.rustup.rs
    export CARGO_HOME="${WORKDIR}/cargo_home"
    export RUSTUP_HOME="${WORKDIR}/rustup_home"

    # Install rustup if not already installed
    if [ ! -f "$CARGO_HOME/bin/rustup" ]; then
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path
        mkdir -p $CARGO_HOME/bin
        ln -sf $RUSTUP_HOME/bin/* $CARGO_HOME/bin/
    fi

    source $CARGO_HOME/env
    rustup toolchain install nightly
    rustup default nightly
}

do_compile() {
    export CARGO_HOME="${WORKDIR}/cargo_home"
    source $CARGO_HOME/env
    cargo +nightly build -Z namespaced-features --release --target=${RUST_TARGET_SYS}
}