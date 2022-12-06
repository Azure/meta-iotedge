target = "${@d.getVar('TARGET_SYS',True).replace('-', ' ')}"
BINDGEN_EXTRA_CLANG_ARGS = "${@bb.utils.contains('target', 'arm', \
                              '--sysroot=${WORKDIR}/recipe-sysroot -I${WORKDIR}/recipe-sysroot/usr/include -mfloat-abi=hard', \
                              '--sysroot=${WORKDIR}/recipe-sysroot -I${WORKDIR}/recipe-sysroot/usr/include', \
                              d)}"
export BINDGEN_EXTRA_CLANG_ARGS

# Copy keys.generated.rs
do_compile_prepend () {
    install -m 644 ${WORKDIR}/keys.generated.rs ${WORKDIR}/git/key/aziot-keyd/src/keys.generated.rs
}
