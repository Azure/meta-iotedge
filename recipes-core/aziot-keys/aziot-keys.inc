DEPENDS += "openssl virtual/docker "
RDEPENDS:${PN} += "docker "

# Set the Rust toolchain to nightly
export RUSTUP_TOOLCHAIN="nightly"

do_compile() {
    export CARGO_HOME="${WORKDIR}/cargo_home"
    rustup toolchain install nightly
    rustup default nightly
    cargo +nightly build -Z namespaced-features --release --target=${RUST_TARGET_SYS}
}