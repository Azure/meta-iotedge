# Auto-Generated by cargo-bitbake 0.3.16
#
inherit cargo

# If this is git based prefer versioned ones if they exist
# DEFAULT_PREFERENCE = "-1"

# how to get aziot-edged could be as easy as but default to a git checkout:
# SRC_URI += "crate://crates.io/aziot-edged/0.1.0"
SRC_URI += "git://github.com/Azure/iotedge.git;protocol=https;nobranch=1"
SRCREV = "e0f3a9dbdc42d6431f39bc6e60cc4e00bb675127"
S = "${WORKDIR}/git/edgelet"
CARGO_SRC_DIR = "aziot-edged"


# please note if you have entries that do not begin with crate://
# you must change them to how that package can be fetched
SRC_URI += " \
    crate://crates.io/adler/1.0.2 \
    crate://crates.io/aho-corasick/0.7.20 \
    crate://crates.io/android_system_properties/0.1.5 \
    crate://crates.io/ansi_term/0.12.1 \
    crate://crates.io/anyhow/1.0.69 \
    crate://crates.io/async-trait/0.1.66 \
    crate://crates.io/atty/0.2.14 \
    crate://crates.io/autocfg/1.1.0 \
    crate://crates.io/base64/0.13.1 \
    crate://crates.io/base64/0.21.0 \
    crate://crates.io/bitflags/1.3.2 \
    crate://crates.io/block-buffer/0.10.3 \
    crate://crates.io/bumpalo/3.12.0 \
    crate://crates.io/byte-unit/4.0.18 \
    crate://crates.io/byteorder/1.4.3 \
    crate://crates.io/bytes/1.4.0 \
    crate://crates.io/cc/1.0.79 \
    crate://crates.io/cfg-if/0.1.10 \
    crate://crates.io/cfg-if/1.0.0 \
    crate://crates.io/chrono-humanize/0.2.2 \
    crate://crates.io/chrono/0.4.23 \
    crate://crates.io/clap/2.34.0 \
    crate://crates.io/codespan-reporting/0.11.1 \
    crate://crates.io/config/0.13.3 \
    crate://crates.io/core-foundation-sys/0.8.3 \
    crate://crates.io/cpufeatures/0.2.5 \
    crate://crates.io/crc32fast/1.3.2 \
    crate://crates.io/crossbeam-channel/0.5.7 \
    crate://crates.io/crossbeam-deque/0.8.3 \
    crate://crates.io/crossbeam-epoch/0.9.14 \
    crate://crates.io/crossbeam-utils/0.8.15 \
    crate://crates.io/crypto-common/0.1.6 \
    crate://crates.io/cxx-build/1.0.92 \
    crate://crates.io/cxx/1.0.92 \
    crate://crates.io/cxxbridge-flags/1.0.92 \
    crate://crates.io/cxxbridge-macro/1.0.92 \
    crate://crates.io/darling/0.14.3 \
    crate://crates.io/darling_core/0.14.3 \
    crate://crates.io/darling_macro/0.14.3 \
    crate://crates.io/dashmap/5.4.0 \
    crate://crates.io/digest/0.10.6 \
    crate://crates.io/either/1.8.1 \
    crate://crates.io/env_logger/0.10.0 \
    crate://crates.io/erased-serde/0.3.25 \
    crate://crates.io/errno-dragonfly/0.1.2 \
    crate://crates.io/errno/0.2.8 \
    crate://crates.io/flate2/1.0.25 \
    crate://crates.io/fnv/1.0.7 \
    crate://crates.io/foreign-types-shared/0.1.1 \
    crate://crates.io/foreign-types/0.3.2 \
    crate://crates.io/form_urlencoded/1.1.0 \
    crate://crates.io/futures-channel/0.3.26 \
    crate://crates.io/futures-core/0.3.26 \
    crate://crates.io/futures-executor/0.3.26 \
    crate://crates.io/futures-io/0.3.26 \
    crate://crates.io/futures-macro/0.3.26 \
    crate://crates.io/futures-sink/0.3.26 \
    crate://crates.io/futures-task/0.3.26 \
    crate://crates.io/futures-util/0.3.26 \
    crate://crates.io/futures/0.3.26 \
    crate://crates.io/generic-array/0.14.6 \
    crate://crates.io/getrandom/0.2.8 \
    crate://crates.io/h2/0.3.16 \
    crate://crates.io/hashbrown/0.12.3 \
    crate://crates.io/headers-core/0.2.0 \
    crate://crates.io/headers/0.3.8 \
    crate://crates.io/hermit-abi/0.1.19 \
    crate://crates.io/hermit-abi/0.2.6 \
    crate://crates.io/hermit-abi/0.3.1 \
    crate://crates.io/hex/0.4.3 \
    crate://crates.io/http-body/0.4.5 \
    crate://crates.io/http/0.2.9 \
    crate://crates.io/httparse/1.8.0 \
    crate://crates.io/httpdate/1.0.2 \
    crate://crates.io/humantime-serde/1.1.1 \
    crate://crates.io/humantime/2.1.0 \
    crate://crates.io/hyper-openssl/0.9.2 \
    crate://crates.io/hyper-proxy/0.9.1 \
    crate://crates.io/hyper/0.14.24 \
    crate://crates.io/iana-time-zone-haiku/0.1.1 \
    crate://crates.io/iana-time-zone/0.1.53 \
    crate://crates.io/ident_case/1.0.1 \
    crate://crates.io/idna/0.3.0 \
    crate://crates.io/indexmap/1.9.2 \
    crate://crates.io/io-lifetimes/1.0.6 \
    crate://crates.io/is-terminal/0.4.4 \
    crate://crates.io/itoa/1.0.6 \
    crate://crates.io/js-sys/0.3.61 \
    crate://crates.io/lazy_static/1.4.0 \
    crate://crates.io/libc/0.2.139 \
    crate://crates.io/link-cplusplus/1.0.8 \
    crate://crates.io/linked-hash-map/0.5.6 \
    crate://crates.io/linked_hash_set/0.1.4 \
    crate://crates.io/linux-raw-sys/0.1.4 \
    crate://crates.io/lock_api/0.4.9 \
    crate://crates.io/log/0.4.17 \
    crate://crates.io/memchr/2.5.0 \
    crate://crates.io/memoffset/0.7.1 \
    crate://crates.io/memoffset/0.8.0 \
    crate://crates.io/mime/0.3.16 \
    crate://crates.io/minimal-lexical/0.2.1 \
    crate://crates.io/miniz_oxide/0.6.2 \
    crate://crates.io/mio/0.8.6 \
    crate://crates.io/nix/0.26.2 \
    crate://crates.io/nom/7.1.3 \
    crate://crates.io/ntapi/0.4.0 \
    crate://crates.io/num-integer/0.1.45 \
    crate://crates.io/num-traits/0.2.15 \
    crate://crates.io/num_cpus/1.15.0 \
    crate://crates.io/once_cell/1.17.1 \
    crate://crates.io/openssl-errors/0.2.0 \
    crate://crates.io/openssl-macros/0.1.0 \
    crate://crates.io/openssl-sys/0.9.83 \
    crate://crates.io/openssl/0.10.48 \
    crate://crates.io/parking_lot/0.12.1 \
    crate://crates.io/parking_lot_core/0.9.7 \
    crate://crates.io/pathdiff/0.2.1 \
    crate://crates.io/percent-encoding/2.2.0 \
    crate://crates.io/pin-project-lite/0.2.9 \
    crate://crates.io/pin-utils/0.1.0 \
    crate://crates.io/pkg-config/0.3.26 \
    crate://crates.io/ppv-lite86/0.2.17 \
    crate://crates.io/proc-macro-error-attr/1.0.4 \
    crate://crates.io/proc-macro-error/1.0.4 \
    crate://crates.io/proc-macro2/1.0.51 \
    crate://crates.io/quote/1.0.23 \
    crate://crates.io/rand/0.8.5 \
    crate://crates.io/rand_chacha/0.3.1 \
    crate://crates.io/rand_core/0.6.4 \
    crate://crates.io/rayon-core/1.11.0 \
    crate://crates.io/rayon/1.7.0 \
    crate://crates.io/redox_syscall/0.2.16 \
    crate://crates.io/regex-syntax/0.6.28 \
    crate://crates.io/regex/1.7.1 \
    crate://crates.io/rustix/0.36.9 \
    crate://crates.io/ryu/1.0.13 \
    crate://crates.io/scopeguard/1.1.0 \
    crate://crates.io/scratch/1.0.5 \
    crate://crates.io/serde/1.0.152 \
    crate://crates.io/serde_derive/1.0.152 \
    crate://crates.io/serde_json/1.0.94 \
    crate://crates.io/serde_spanned/0.6.1 \
    crate://crates.io/serde_with/2.2.0 \
    crate://crates.io/serde_with_macros/2.2.0 \
    crate://crates.io/serial_test/1.0.0 \
    crate://crates.io/serial_test_derive/1.0.0 \
    crate://crates.io/sha1/0.10.5 \
    crate://crates.io/sha2/0.10.6 \
    crate://crates.io/signal-hook-registry/1.4.1 \
    crate://crates.io/slab/0.4.8 \
    crate://crates.io/smallvec/1.10.0 \
    crate://crates.io/socket2/0.4.9 \
    crate://crates.io/static_assertions/1.1.0 \
    crate://crates.io/strsim/0.10.0 \
    crate://crates.io/strsim/0.8.0 \
    crate://crates.io/syn/1.0.109 \
    crate://crates.io/sysinfo/0.28.2 \
    crate://crates.io/tabwriter/1.2.1 \
    crate://crates.io/termcolor/1.2.0 \
    crate://crates.io/test-case-macros/2.2.2 \
    crate://crates.io/test-case/2.2.2 \
    crate://crates.io/textwrap/0.11.0 \
    crate://crates.io/thiserror-impl/1.0.39 \
    crate://crates.io/thiserror/1.0.39 \
    crate://crates.io/time-core/0.1.0 \
    crate://crates.io/time-macros/0.2.8 \
    crate://crates.io/time/0.1.45 \
    crate://crates.io/time/0.3.20 \
    crate://crates.io/tinyvec/1.6.0 \
    crate://crates.io/tinyvec_macros/0.1.1 \
    crate://crates.io/tokio-macros/1.8.2 \
    crate://crates.io/tokio-openssl/0.6.3 \
    crate://crates.io/tokio-util/0.7.7 \
    crate://crates.io/tokio/1.26.0 \
    crate://crates.io/toml/0.7.2 \
    crate://crates.io/toml_datetime/0.6.1 \
    crate://crates.io/toml_edit/0.19.4 \
    crate://crates.io/tower-layer/0.3.2 \
    crate://crates.io/tower-service/0.3.2 \
    crate://crates.io/tracing-attributes/0.1.23 \
    crate://crates.io/tracing-core/0.1.30 \
    crate://crates.io/tracing/0.1.37 \
    crate://crates.io/try-lock/0.2.4 \
    crate://crates.io/typenum/1.16.0 \
    crate://crates.io/unicode-bidi/0.3.10 \
    crate://crates.io/unicode-ident/1.0.8 \
    crate://crates.io/unicode-normalization/0.1.22 \
    crate://crates.io/unicode-width/0.1.10 \
    crate://crates.io/url/2.3.1 \
    crate://crates.io/utf8-width/0.1.6 \
    crate://crates.io/vcpkg/0.2.15 \
    crate://crates.io/vec_map/0.8.2 \
    crate://crates.io/version_check/0.9.4 \
    crate://crates.io/want/0.3.0 \
    crate://crates.io/wasi/0.10.0+wasi-snapshot-preview1 \
    crate://crates.io/wasi/0.11.0+wasi-snapshot-preview1 \
    crate://crates.io/wasm-bindgen-backend/0.2.84 \
    crate://crates.io/wasm-bindgen-macro-support/0.2.84 \
    crate://crates.io/wasm-bindgen-macro/0.2.84 \
    crate://crates.io/wasm-bindgen-shared/0.2.84 \
    crate://crates.io/wasm-bindgen/0.2.84 \
    crate://crates.io/winapi-i686-pc-windows-gnu/0.4.0 \
    crate://crates.io/winapi-util/0.1.5 \
    crate://crates.io/winapi-x86_64-pc-windows-gnu/0.4.0 \
    crate://crates.io/winapi/0.3.9 \
    crate://crates.io/windows-sys/0.45.0 \
    crate://crates.io/windows-targets/0.42.1 \
    crate://crates.io/windows_aarch64_gnullvm/0.42.1 \
    crate://crates.io/windows_aarch64_msvc/0.42.1 \
    crate://crates.io/windows_i686_gnu/0.42.1 \
    crate://crates.io/windows_i686_msvc/0.42.1 \
    crate://crates.io/windows_x86_64_gnu/0.42.1 \
    crate://crates.io/windows_x86_64_gnullvm/0.42.1 \
    crate://crates.io/windows_x86_64_msvc/0.42.1 \
    crate://crates.io/winnow/0.3.5 \
    crate://crates.io/yaml-rust/0.4.5 \
    crate://crates.io/zip/0.6.4 \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-cert-client-async;destsuffix=aziot-cert-client-async \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-cert-common-http;destsuffix=aziot-cert-common-http \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-certd-config;destsuffix=aziot-certd-config \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-identity-client-async;destsuffix=aziot-identity-client-async \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-identity-common-http;destsuffix=aziot-identity-common-http \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-identity-common;destsuffix=aziot-identity-common \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-identityd-config;destsuffix=aziot-identityd-config \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-key-client-async;destsuffix=aziot-key-client-async \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-key-client;destsuffix=aziot-key-client \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-key-common-http;destsuffix=aziot-key-common-http \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-key-common;destsuffix=aziot-key-common \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-key-openssl-engine;destsuffix=aziot-key-openssl-engine \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-keyd-config;destsuffix=aziot-keyd-config \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-keys-common;destsuffix=aziot-keys-common \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-tpmd-config;destsuffix=aziot-tpmd-config \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziotctl-common;destsuffix=aziotctl-common \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=cert-renewal;destsuffix=cert-renewal \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=config-common;destsuffix=config-common \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=http-common;destsuffix=http-common \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=logger;destsuffix=logger \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=openssl-build;destsuffix=openssl-build \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=openssl-sys2;destsuffix=openssl-sys2 \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=openssl2;destsuffix=openssl2 \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=pkcs11-sys;destsuffix=pkcs11-sys \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=pkcs11;destsuffix=pkcs11 \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=test-common;destsuffix=test-common \
"

SRCREV_aziot-cert-client-async = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-cert-client-async"
SRCREV_aziot-cert-common-http = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-cert-common-http"
SRCREV_aziot-certd-config = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-certd-config"
SRCREV_aziot-identity-client-async = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-identity-client-async"
SRCREV_aziot-identity-common = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-identity-common"
SRCREV_aziot-identity-common-http = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-identity-common-http"
SRCREV_aziot-identityd-config = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-identityd-config"
SRCREV_aziot-key-client = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-key-client"
SRCREV_aziot-key-client-async = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-key-client-async"
SRCREV_aziot-key-common = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-key-common"
SRCREV_aziot-key-common-http = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-key-common-http"
SRCREV_aziot-key-openssl-engine = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-key-openssl-engine"
SRCREV_aziot-keyd-config = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-keyd-config"
SRCREV_aziot-keys-common = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-keys-common"
SRCREV_aziot-tpmd-config = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziot-tpmd-config"
SRCREV_aziotctl-common = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziotctl-common"
SRCREV_cert-renewal = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/cert-renewal"
SRCREV_config-common = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/config-common"
SRCREV_http-common = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/http-common"
SRCREV_logger = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/logger"
SRCREV_openssl-build = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/openssl-build"
SRCREV_openssl-sys2 = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/openssl-sys2"
SRCREV_openssl2 = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/openssl2"
SRCREV_pkcs11 = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/pkcs11"
SRCREV_pkcs11-sys = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/pkcs11-sys"
SRCREV_test-common = "release/1.4"
EXTRA_OECARGO_PATHS += "${WORKDIR}/test-common"

# FIXME: update generateme with the real MD5 of the license file
LIC_FILES_CHKSUM = " \
    file://../LICENSE;md5=0f7e3b1308cb5c00b372a6e78835732d \
    file://../THIRDPARTYNOTICES;md5=11604c6170b98c376be25d0ca6989d9b \
"

SUMMARY = "The aziot-edged is the main binary for the IoT edge daemon."
HOMEPAGE = "https://aka.ms/iotedge"
LICENSE = "MIT"

# includes this file if it exists but does not fail
# this is useful for anything you may want to override from
# what cargo-bitbake generates.
include aziot-edged-${PV}.inc
include aziot-edged.inc
