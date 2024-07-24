DEPENDS += "curl openssl virtual/docker "
RDEPENDS:${PN} += "docker "

# Path to the script in your layer
SRC_URI += "file://rustup_init.sh"

# Ensure WORKDIR is used for installation
do_configure() {
    export CARGO_HOME="${WORKDIR}/cargo_home"
    export RUSTUP_HOME="${WORKDIR}/rustup_home"

    # Copy the script to WORKDIR
    cp ${WORKDIR}/rustup_init.sh ${S}/rustup_init.sh
    chmod +x ${S}/rustup_init.sh

    # Execute the script
    if ! ${S}/rustup_init.sh; then
        echo "ERROR: Failed to setup Rust"
        exit 1
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