target = "${@d.getVar('TARGET_SYS',True).replace('-', ' ')}"
BINDGEN_EXTRA_CLANG_ARGS = "${@bb.utils.contains('target', 'arm', \
                              '--sysroot=${WORKDIR}/recipe-sysroot -I${WORKDIR}/recipe-sysroot/usr/include -mfloat-abi=hard', \
                              '--sysroot=${WORKDIR}/recipe-sysroot -I${WORKDIR}/recipe-sysroot/usr/include', \
                              d)}"
export BINDGEN_EXTRA_CLANG_ARGS

# The pre-generated keys.generated.rs (bindgen output) is copied into the
# source tree by a do_compile:prepend defined in the shared aziotd.inc. The
# unpack location of file:// SRC_URI entries differs between Yocto releases
# (Scarthgap unpacks to ${WORKDIR}; Wrynose/6.0 unpacks to ${UNPACKDIR} =
# ${WORKDIR}/sources), which aziotd.inc handles via ${UNPACK_ROOT}.
