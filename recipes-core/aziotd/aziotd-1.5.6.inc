export VERSION = "1.5.6"

# Copy the pre-generated bindgen output into the source tree before building.
# Scarthgap unpacks file:// SRC_URI entries to ${WORKDIR}.
do_compile:prepend () {
    install -m 644 ${WORKDIR}/keys.generated.rs ${S}/key/aziot-keyd/src/keys.generated.rs
}
