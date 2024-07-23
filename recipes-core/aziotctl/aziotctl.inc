DEPENDS += "openssl virtual/docker"
RDEPENDS:${PN} += "docker"

export OPENSSL_DIR = "${STAGING_EXECPREFIXDIR}"

# Set the Rust toolchain to nightly
export RUSTUP_TOOLCHAIN="nightly"

do_compile() {
    export CARGO_HOME="${WORKDIR}/cargo_home"
    rustup toolchain install nightly
    rustup default nightly
    cargo +nightly build -Z namespaced-features --release --target=${RUST_TARGET_SYS}
}

do_install () {
    # Binaries
    install -d  "${D}${bindir}"
    install -m 755 "${WORKDIR}/build/target/${RUST_TARGET_SYS}/release/aziotctl" ${D}${bindir}/aziotctl
}