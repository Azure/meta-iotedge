# Auto-Generated by cargo-bitbake 0.3.16
#
inherit cargo

# If this is git based prefer versioned ones if they exist
# DEFAULT_PREFERENCE = "-1"

# how to get iotedge could be as easy as but default to a git checkout:
# SRC_URI += "crate://crates.io/iotedge/0.1.0"
SRC_URI += "git://github.com/Azure/iotedge;protocol=https;nobranch=1"
SRCREV = "8d5f1d1caadcf28d492fbdbe53eb505e076f28da"
S = "${WORKDIR}/git/edgelet"
CARGO_SRC_DIR = "iotedge"


# please note if you have entries that do not begin with crate://
# you must change them to how that package can be fetched
SRC_URI += " \
    crate://crates.io/addr2line/0.20.0 \
    crate://crates.io/adler/1.0.2 \
    crate://crates.io/aho-corasick/1.0.4 \
    crate://crates.io/android-tzdata/0.1.1 \
    crate://crates.io/android_system_properties/0.1.5 \
    crate://crates.io/anstream/0.3.2 \
    crate://crates.io/anstyle-parse/0.2.1 \
    crate://crates.io/anstyle-query/1.0.0 \
    crate://crates.io/anstyle-wincon/1.0.2 \
    crate://crates.io/anstyle/1.0.1 \
    crate://crates.io/anyhow/1.0.74 \
    crate://crates.io/async-trait/0.1.73 \
    crate://crates.io/atty/0.2.14 \
    crate://crates.io/autocfg/1.1.0 \
    crate://crates.io/backtrace/0.3.68 \
    crate://crates.io/base64/0.13.1 \
    crate://crates.io/base64/0.21.2 \
    crate://crates.io/bitflags/1.3.2 \
    crate://crates.io/bitflags/2.4.0 \
    crate://crates.io/block-buffer/0.10.4 \
    crate://crates.io/bumpalo/3.13.0 \
    crate://crates.io/byte-unit/4.0.19 \
    crate://crates.io/byteorder/1.4.3 \
    crate://crates.io/bytes/1.4.0 \
    crate://crates.io/cc/1.0.82 \
    crate://crates.io/cfg-if/0.1.10 \
    crate://crates.io/cfg-if/1.0.0 \
    crate://crates.io/chrono-humanize/0.2.3 \
    crate://crates.io/chrono/0.4.26 \
    crate://crates.io/clap/4.3.21 \
    crate://crates.io/clap_builder/4.3.21 \
    crate://crates.io/clap_lex/0.5.0 \
    crate://crates.io/colorchoice/1.0.0 \
    crate://crates.io/config/0.13.3 \
    crate://crates.io/core-foundation-sys/0.8.4 \
    crate://crates.io/cpufeatures/0.2.9 \
    crate://crates.io/crc32fast/1.3.2 \
    crate://crates.io/crossbeam-channel/0.5.8 \
    crate://crates.io/crossbeam-deque/0.8.3 \
    crate://crates.io/crossbeam-epoch/0.9.15 \
    crate://crates.io/crossbeam-utils/0.8.16 \
    crate://crates.io/crypto-common/0.1.6 \
    crate://crates.io/darling/0.20.3 \
    crate://crates.io/darling_core/0.20.3 \
    crate://crates.io/darling_macro/0.20.3 \
    crate://crates.io/dashmap/5.5.0 \
    crate://crates.io/deranged/0.3.7 \
    crate://crates.io/digest/0.10.7 \
    crate://crates.io/either/1.9.0 \
    crate://crates.io/env_logger/0.10.0 \
    crate://crates.io/equivalent/1.0.1 \
    crate://crates.io/erased-serde/0.3.28 \
    crate://crates.io/errno-dragonfly/0.1.2 \
    crate://crates.io/errno/0.3.2 \
    crate://crates.io/flate2/1.0.27 \
    crate://crates.io/fnv/1.0.7 \
    crate://crates.io/foreign-types-shared/0.1.1 \
    crate://crates.io/foreign-types/0.3.2 \
    crate://crates.io/form_urlencoded/1.2.0 \
    crate://crates.io/futures-channel/0.3.28 \
    crate://crates.io/futures-core/0.3.28 \
    crate://crates.io/futures-executor/0.3.28 \
    crate://crates.io/futures-io/0.3.28 \
    crate://crates.io/futures-macro/0.3.28 \
    crate://crates.io/futures-sink/0.3.28 \
    crate://crates.io/futures-task/0.3.28 \
    crate://crates.io/futures-util/0.3.28 \
    crate://crates.io/futures/0.3.28 \
    crate://crates.io/generic-array/0.14.7 \
    crate://crates.io/getrandom/0.2.10 \
    crate://crates.io/gimli/0.27.3 \
    crate://crates.io/hashbrown/0.12.3 \
    crate://crates.io/hashbrown/0.14.0 \
    crate://crates.io/headers-core/0.2.0 \
    crate://crates.io/headers/0.3.8 \
    crate://crates.io/hermit-abi/0.1.19 \
    crate://crates.io/hermit-abi/0.3.2 \
    crate://crates.io/hex/0.4.3 \
    crate://crates.io/http-body/0.4.5 \
    crate://crates.io/http/0.2.9 \
    crate://crates.io/httparse/1.8.0 \
    crate://crates.io/httpdate/1.0.3 \
    crate://crates.io/humantime-serde/1.1.1 \
    crate://crates.io/humantime/2.1.0 \
    crate://crates.io/hyper-openssl/0.9.2 \
    crate://crates.io/hyper-proxy/0.9.1 \
    crate://crates.io/hyper/0.14.27 \
    crate://crates.io/iana-time-zone-haiku/0.1.2 \
    crate://crates.io/iana-time-zone/0.1.57 \
    crate://crates.io/ident_case/1.0.1 \
    crate://crates.io/idna/0.4.0 \
    crate://crates.io/indexmap/1.9.3 \
    crate://crates.io/indexmap/2.0.0 \
    crate://crates.io/is-terminal/0.4.9 \
    crate://crates.io/itoa/1.0.9 \
    crate://crates.io/js-sys/0.3.64 \
    crate://crates.io/lazy_static/1.4.0 \
    crate://crates.io/libc/0.2.153 \
    crate://crates.io/linked-hash-map/0.5.6 \
    crate://crates.io/linked_hash_set/0.1.4 \
    crate://crates.io/linux-raw-sys/0.4.5 \
    crate://crates.io/lock_api/0.4.10 \
    crate://crates.io/log/0.4.20 \
    crate://crates.io/memchr/2.5.0 \
    crate://crates.io/memoffset/0.7.1 \
    crate://crates.io/memoffset/0.9.0 \
    crate://crates.io/mime/0.3.17 \
    crate://crates.io/minimal-lexical/0.2.1 \
    crate://crates.io/miniz_oxide/0.7.1 \
    crate://crates.io/mio/0.8.11 \
    crate://crates.io/nix/0.26.2 \
    crate://crates.io/nom/7.1.3 \
    crate://crates.io/ntapi/0.4.1 \
    crate://crates.io/num-traits/0.2.16 \
    crate://crates.io/num_cpus/1.16.0 \
    crate://crates.io/object/0.31.1 \
    crate://crates.io/once_cell/1.18.0 \
    crate://crates.io/openssl-errors/0.2.0 \
    crate://crates.io/openssl-macros/0.1.1 \
    crate://crates.io/openssl-sys/0.9.91 \
    crate://crates.io/openssl/0.10.56 \
    crate://crates.io/parking_lot/0.12.1 \
    crate://crates.io/parking_lot_core/0.9.8 \
    crate://crates.io/pathdiff/0.2.1 \
    crate://crates.io/percent-encoding/2.3.0 \
    crate://crates.io/pin-project-lite/0.2.12 \
    crate://crates.io/pin-utils/0.1.0 \
    crate://crates.io/pkg-config/0.3.27 \
    crate://crates.io/ppv-lite86/0.2.17 \
    crate://crates.io/proc-macro-error-attr/1.0.4 \
    crate://crates.io/proc-macro-error/1.0.4 \
    crate://crates.io/proc-macro2/1.0.66 \
    crate://crates.io/quote/1.0.32 \
    crate://crates.io/rand/0.8.5 \
    crate://crates.io/rand_chacha/0.3.1 \
    crate://crates.io/rand_core/0.6.4 \
    crate://crates.io/rayon-core/1.11.0 \
    crate://crates.io/rayon/1.7.0 \
    crate://crates.io/redox_syscall/0.3.5 \
    crate://crates.io/regex-automata/0.3.6 \
    crate://crates.io/regex-syntax/0.7.4 \
    crate://crates.io/regex/1.9.3 \
    crate://crates.io/rustc-demangle/0.1.23 \
    crate://crates.io/rustix/0.38.8 \
    crate://crates.io/ryu/1.0.15 \
    crate://crates.io/scopeguard/1.2.0 \
    crate://crates.io/semver/1.0.22 \
    crate://crates.io/serde/1.0.183 \
    crate://crates.io/serde_derive/1.0.183 \
    crate://crates.io/serde_json/1.0.105 \
    crate://crates.io/serde_spanned/0.6.3 \
    crate://crates.io/serde_with/2.3.3 \
    crate://crates.io/serde_with_macros/2.3.3 \
    crate://crates.io/serial_test/1.0.0 \
    crate://crates.io/serial_test_derive/1.0.0 \
    crate://crates.io/sha1/0.10.5 \
    crate://crates.io/sha2/0.10.7 \
    crate://crates.io/signal-hook-registry/1.4.1 \
    crate://crates.io/slab/0.4.8 \
    crate://crates.io/smallvec/1.11.0 \
    crate://crates.io/socket2/0.4.9 \
    crate://crates.io/socket2/0.5.3 \
    crate://crates.io/static_assertions/1.1.0 \
    crate://crates.io/strsim/0.10.0 \
    crate://crates.io/syn/1.0.109 \
    crate://crates.io/syn/2.0.28 \
    crate://crates.io/sysinfo/0.28.4 \
    crate://crates.io/tabwriter/1.2.1 \
    crate://crates.io/termcolor/1.2.0 \
    crate://crates.io/test-case-macros/2.2.2 \
    crate://crates.io/test-case/2.2.2 \
    crate://crates.io/thiserror-impl/1.0.46 \
    crate://crates.io/thiserror/1.0.46 \
    crate://crates.io/time-core/0.1.1 \
    crate://crates.io/time-macros/0.2.11 \
    crate://crates.io/time/0.1.45 \
    crate://crates.io/time/0.3.25 \
    crate://crates.io/tinyvec/1.6.0 \
    crate://crates.io/tinyvec_macros/0.1.1 \
    crate://crates.io/tokio-macros/2.1.0 \
    crate://crates.io/tokio-openssl/0.6.3 \
    crate://crates.io/tokio/1.31.0 \
    crate://crates.io/toml/0.7.6 \
    crate://crates.io/toml_datetime/0.6.3 \
    crate://crates.io/toml_edit/0.19.14 \
    crate://crates.io/tower-layer/0.3.2 \
    crate://crates.io/tower-service/0.3.2 \
    crate://crates.io/tracing-attributes/0.1.26 \
    crate://crates.io/tracing-core/0.1.31 \
    crate://crates.io/tracing/0.1.37 \
    crate://crates.io/try-lock/0.2.4 \
    crate://crates.io/typenum/1.16.0 \
    crate://crates.io/unicode-bidi/0.3.13 \
    crate://crates.io/unicode-ident/1.0.11 \
    crate://crates.io/unicode-normalization/0.1.22 \
    crate://crates.io/unicode-width/0.1.10 \
    crate://crates.io/url/2.4.0 \
    crate://crates.io/utf8-width/0.1.6 \
    crate://crates.io/utf8parse/0.2.1 \
    crate://crates.io/vcpkg/0.2.15 \
    crate://crates.io/version_check/0.9.4 \
    crate://crates.io/want/0.3.1 \
    crate://crates.io/wasi/0.10.0+wasi-snapshot-preview1 \
    crate://crates.io/wasi/0.11.0+wasi-snapshot-preview1 \
    crate://crates.io/wasm-bindgen-backend/0.2.87 \
    crate://crates.io/wasm-bindgen-macro-support/0.2.87 \
    crate://crates.io/wasm-bindgen-macro/0.2.87 \
    crate://crates.io/wasm-bindgen-shared/0.2.87 \
    crate://crates.io/wasm-bindgen/0.2.87 \
    crate://crates.io/winapi-i686-pc-windows-gnu/0.4.0 \
    crate://crates.io/winapi-util/0.1.5 \
    crate://crates.io/winapi-x86_64-pc-windows-gnu/0.4.0 \
    crate://crates.io/winapi/0.3.9 \
    crate://crates.io/windows-sys/0.48.0 \
    crate://crates.io/windows-targets/0.48.2 \
    crate://crates.io/windows/0.48.0 \
    crate://crates.io/windows_aarch64_gnullvm/0.48.2 \
    crate://crates.io/windows_aarch64_msvc/0.48.2 \
    crate://crates.io/windows_i686_gnu/0.48.2 \
    crate://crates.io/windows_i686_msvc/0.48.2 \
    crate://crates.io/windows_x86_64_gnu/0.48.2 \
    crate://crates.io/windows_x86_64_gnullvm/0.48.2 \
    crate://crates.io/windows_x86_64_msvc/0.48.2 \
    crate://crates.io/winnow/0.5.12 \
    crate://crates.io/yaml-rust/0.4.5 \
    crate://crates.io/zip/0.6.6 \
"

LIC_FILES_CHKSUM = " \
    file://../LICENSE;md5=0f7e3b1308cb5c00b372a6e78835732d \
    file://../THIRDPARTYNOTICES;md5=11604c6170b98c376be25d0ca6989d9b \
"

SUMMARY = "The iotedge tool is used to manage the IoT Edge runtime."
HOMEPAGE = "https://aka.ms/iotedge"
LICENSE = "MIT"

# includes this file if it exists but does not fail
# this is useful for anything you may want to override from
# what cargo-bitbake generates.
include iotedge-${PV}.inc
include iotedge.inc
