export VERSION = "1.6.0-rc.1"

# Copy the pre-generated bindgen output into the source tree before building.
# Wrynose (Yocto 6.0) unpacks file:// SRC_URI entries to ${UNPACKDIR}
# (= ${WORKDIR}/sources), not ${WORKDIR}.
# (The panic=abort -> unwind patch is pulled by the shared aziotd.inc; its
# 1.6-specific copy lives in the aziotd-1.6.0-rc.1/ FILESPATH directory.)
do_compile:prepend () {
    install -m 644 ${UNPACKDIR}/keys.generated.rs ${S}/key/aziot-keyd/src/keys.generated.rs
}
