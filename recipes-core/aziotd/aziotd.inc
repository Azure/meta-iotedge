DEPENDS += "openssl aziotctl aziot-keys tpm2-tss clang-native"
# aziotctl is required for iotedge check to work properly
# Fixes: https://github.com/Azure/meta-iotedge/issues/134
RDEPENDS:${PN} += "tpm2-tss libtss2-mu libtss2-tcti-device aziot-keys aziotctl"
TOOLCHAIN = "clang"

# file:// SRC_URI assets unpack into the recipe's unpack root, which differs by
# Yocto release: Scarthgap unpacks to ${WORKDIR}, Wrynose (6.0) to ${UNPACKDIR}
# (= ${WORKDIR}/sources). Resolve to whichever applies. (Defined locally here
# because aziotd does not require iot-identity-service.inc.)
UNPACK_ROOT ??= "${@d.getVar('UNPACKDIR') or d.getVar('WORKDIR')}"

# clang (set above) treats unused command-line args as errors under -Werror,
# whereas gcc silently ignores them. cc-rs builds C build-scripts (e.g.
# openssl-sys2, aziot-key-openssl-engine) with -c (compile-only) but the OE
# rust-cc wrapper bakes OE LDFLAGS (-Wl,-O1 -Wl,--hash-style=gnu
# -Wl,--as-needed -Wl,-z,relro,-z,now) into the base CC string. On a -c
# compile those linker flags are unused, so clang fails with:
#   error: -Wl,-O1: 'linker' input unused [-Werror,-Wunused-command-line-argument]
# aziot-keys builds the IDENTICAL crate fine because its TOOLCHAIN defaults to
# gcc. Mirror gcc's tolerance for clang by disabling ONLY that one diagnostic.
# This is scoped to aziotd, flows into cc-rs via cargo_common's CFLAGS/
# TARGET_CFLAGS export, and does NOT weaken -Werror=format-security or any
# other real warning. Ref: Azure/meta-iotedge wrynose iotedge 1.6 rc1.
CFLAGS:append = " -Wno-unused-command-line-argument"

inherit systemd

SYSTEMD_AUTO_ENABLE:${PN} = "enable"
SYSTEMD_SERVICE:${PN} = "aziot-certd.service "
SYSTEMD_SERVICE:${PN} += "aziot-identityd.service "
SYSTEMD_SERVICE:${PN} += "aziot-keyd.service "
SYSTEMD_SERVICE:${PN} += "aziot-tpmd.service "

SRC_URI += "file://aziot-certd.service \
            file://aziot-identityd.service \
            file://aziot-keyd.service \
            file://aziot-tpmd.service \
            file://keys.generated.rs \
            file://0001-Remove-panic.patch \
"

# Copy the pre-generated bindgen output into the source tree before building.
# keys.generated.rs is a file:// SRC_URI asset, so it unpacks into the recipe's
# unpack root; ${UNPACK_ROOT} (set above) resolves to ${WORKDIR} on Scarthgap
# and ${UNPACKDIR} on Wrynose (6.0). Shared by all aziotd versions.
do_compile:prepend () {
    install -m 644 ${UNPACK_ROOT}/keys.generated.rs ${S}/key/aziot-keyd/src/keys.generated.rs
}


do_install:append  () {
    install -d ${D}${systemd_unitdir}/system

    # Create symbolic links
    ln -s ${bindir}/aziotd ${D}${bindir}/aziot-certd
    ln -s ${bindir}/aziotd ${D}${bindir}/aziot-identityd
    ln -s ${bindir}/aziotd ${D}${bindir}/aziot-keyd
    ln -s ${bindir}/aziotd ${D}${bindir}/aziot-tpmd

    # Install all folders
    install -d ${D}${sysconfdir}/aziot
    install -d -m 700 -o aziotcs -g aziotcs ${D}${sysconfdir}/aziot/certd/config.d
    install -d -m 700 -o aziotid -g aziotid ${D}${sysconfdir}/aziot/identityd/config.d
    install -d -m 700 -o aziotks -g aziotks ${D}${sysconfdir}/aziot/keyd/config.d
    install -d -m 700 -o aziottpm -g aziottpm ${D}${sysconfdir}/aziot/tpmd/config.d

    # Configuration files
    install -m 644 ${S}/cert/aziot-certd/config/unix/default.toml ${D}${sysconfdir}/aziot/certd/config.toml.default
    install -m 644 ${S}/identity/aziot-identityd/config/unix/default.toml ${D}${sysconfdir}/aziot/identityd/config.toml.default
    install -m 644 ${S}/key/aziot-keyd/config/unix/default.toml ${D}${sysconfdir}/aziot/keyd/config.toml.default
    install -m 644 ${S}/tpm/aziot-tpmd/config/unix/default.toml ${D}${sysconfdir}/aziot/tpmd/config.toml.default
    install -m 644 ${S}/aziotctl/config/unix/template.toml ${D}${sysconfdir}/aziot/config.toml.template

    # Data dir
    install -d ${D}${localstatedir}/lib
    install -d ${D}${localstatedir}/lib/aziot
    install -d -m 700 -o aziotks -g aziotks ${D}${localstatedir}/lib/aziot/keyd
    install -d -m 700 -o aziotcs -g aziotcs ${D}${localstatedir}/lib/aziot/certd
    install -d -m 700 -o aziotid -g aziotid ${D}${localstatedir}/lib/aziot/identityd
    install -d -m 700 -o aziottpm -g aziottpm ${D}${localstatedir}/lib/aziot/tpmd


    # Install all required services
    # file:// .service assets live in the recipe's unpack root; see UNPACK_ROOT
    # above (Scarthgap -> ${WORKDIR}, Wrynose/6.0 -> ${UNPACKDIR}).
    install -m 644 ${UNPACK_ROOT}/aziot-certd.service ${D}${systemd_unitdir}/system
    install -m 644 ${UNPACK_ROOT}/aziot-identityd.service ${D}${systemd_unitdir}/system
    install -m 644 ${UNPACK_ROOT}/aziot-keyd.service ${D}${systemd_unitdir}/system
    install -m 644 ${UNPACK_ROOT}/aziot-tpmd.service ${D}${systemd_unitdir}/system

    install -m 644 ${S}/cert/aziot-certd/aziot-certd.socket.in ${D}${systemd_unitdir}/system/aziot-certd.socket
    install -m 644 ${S}/identity/aziot-identityd/aziot-identityd.socket.in ${D}${systemd_unitdir}/system/aziot-identityd.socket
    install -m 644 ${S}/key/aziot-keyd/aziot-keyd.socket.in ${D}${systemd_unitdir}/system/aziot-keyd.socket
    install -m 644 ${S}/tpm/aziot-tpmd/aziot-tpmd.socket.in ${D}${systemd_unitdir}/system/aziot-tpmd.socket

    sed -i \
        -e "s|@user_aziotid@|${USER_AZIOTID}|" \
		-e "s|@user_aziotks@|${USER_AZIOTKS}|" \
		-e "s|@user_aziotcs@|${USER_AZIOTCS}|" \
		-e "s|@user_aziottpm@|${USER_AZIOTTPM}|" \
		-e "s|@socket_dir@|${SOCKET_DIR}|" \
        ${D}${systemd_unitdir}/system/aziot-certd.socket \
        ${D}${systemd_unitdir}/system/aziot-identityd.socket \
        ${D}${systemd_unitdir}/system/aziot-keyd.socket \
        ${D}${systemd_unitdir}/system/aziot-tpmd.socket
}

inherit useradd
USERADD_PACKAGES = "${PN}"

# Optionally pin the aziot service users/groups to static UIDs/GIDs.
# Version-dependent default (see aziot-edged.inc and issue #130): 1.6 (new LTS)
# defaults ON so the one-time static-ID move lands with the major upgrade; 1.5.x
# (shipped) stays OFF to avoid changing on-disk ownership for fielded devices.
# Override with IOTEDGE_STATIC_UIDS in your distro or local.conf.
IOTEDGE_STATIC_UIDS ??= "${@'1' if (d.getVar('PV') or '').startswith('1.6') else '0'}"
IOTEDGE_UID_AZIOTCS = "${@'-u 13624 ' if d.getVar('IOTEDGE_STATIC_UIDS') == '1' else ''}"
IOTEDGE_UID_AZIOTKS = "${@'-u 13625 ' if d.getVar('IOTEDGE_STATIC_UIDS') == '1' else ''}"
IOTEDGE_UID_AZIOTID = "${@'-u 13626 ' if d.getVar('IOTEDGE_STATIC_UIDS') == '1' else ''}"
IOTEDGE_UID_AZIOTTPM = "${@'-u 13627 ' if d.getVar('IOTEDGE_STATIC_UIDS') == '1' else ''}"

USERADD_PARAM:${PN} = "-r ${IOTEDGE_UID_AZIOTCS}-g aziotcs -c 'aziot-certd user' -G aziotks -s /sbin/nologin -d ${localstatedir}/lib/aziot/certd aziotcs; "
USERADD_PARAM:${PN} += "-r ${IOTEDGE_UID_AZIOTKS}-g aziotks -c 'aziot-keyd user' -s /sbin/nologin -d ${localstatedir}/lib/aziot/keyd aziotks; "
USERADD_PARAM:${PN} += "-r ${IOTEDGE_UID_AZIOTID}-g aziotid -c 'aziot-identityd user' -G aziotcs,aziotks,aziottpm -s /sbin/nologin -d ${localstatedir}/lib/aziot/identityd aziotid; "
# Add aziottpm to tss group for TPM device access
# Fixes: https://github.com/Azure/meta-iotedge/issues/132
USERADD_PARAM:${PN} += "-r ${IOTEDGE_UID_AZIOTTPM}-g aziottpm -G tss -c 'aziot-tpmd user' -s /sbin/nologin -d ${localstatedir}/lib/aziot/tpmd aziottpm; "

# Group GIDs are static only when IOTEDGE_STATIC_UIDS = "1".
IOTEDGE_GID_AZIOTCS = "${@'-g 13624 ' if d.getVar('IOTEDGE_STATIC_UIDS') == '1' else ''}"
IOTEDGE_GID_AZIOTKS = "${@'-g 13625 ' if d.getVar('IOTEDGE_STATIC_UIDS') == '1' else ''}"
IOTEDGE_GID_AZIOTID = "${@'-g 13626 ' if d.getVar('IOTEDGE_STATIC_UIDS') == '1' else ''}"
IOTEDGE_GID_AZIOTTPM = "${@'-g 13627 ' if d.getVar('IOTEDGE_STATIC_UIDS') == '1' else ''}"
GROUPADD_PARAM:${PN} = "-r ${IOTEDGE_GID_AZIOTCS}aziotcs; "
GROUPADD_PARAM:${PN} += "-r ${IOTEDGE_GID_AZIOTKS}aziotks; "
GROUPADD_PARAM:${PN} += "-r ${IOTEDGE_GID_AZIOTID}aziotid; "
GROUPADD_PARAM:${PN} += "-r ${IOTEDGE_GID_AZIOTTPM}aziottpm; "

export SOCKET_DIR = "/run/aziot"
export USER_AZIOTID = "aziotid"
export USER_AZIOTCS = "aziotcs"
export USER_AZIOTKS = "aziotks"
export USER_AZIOTTPM = "aziottpm"

# Set rpath to the location where aziot-keys installs libaziot_keys.so
# Fixes: https://github.com/Azure/meta-iotedge/issues/182
RUSTFLAGS += "-Clink-arg=-Wl,-rpath,${rustlibdir}"
FILES:${PN} += " \
    ${systemd_unitdir}/system/* \
    ${bindir}/aziot-* \
    ${localstatedir}/lib/ \
   "