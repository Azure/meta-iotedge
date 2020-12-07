# Auto-Generated by cargo-bitbake 0.3.13
#
inherit cargo
SRC_URI += "https://github.com/Azure/azure-iotedge/releases/download/${PV}/iotedge-${PV}.tar.gz"
SRC_URI[md5sum]="fe99f044469fcf9173555d835fdee178"
SRC_URI[sha256sum]="df22d2764a3b0418024e13d15c3476e842c2bef95c23066d9103e33059e20aaf"

S = "${WORKDIR}/iotedge-${PV}/edgelet/iotedged"
CARGO_SRC_DIR = "iotedged"

SRC_URI += " \
    crate://crates.io/adler32/1.0.4 \
    crate://crates.io/aho-corasick/0.6.4 \
    crate://crates.io/ansi_term/0.11.0 \
    crate://crates.io/argon2rs/0.2.5 \
    crate://crates.io/arrayref/0.3.4 \
    crate://crates.io/arrayvec/0.4.7 \
    crate://crates.io/atty/0.2.10 \
    crate://crates.io/autocfg/0.1.6 \
    crate://crates.io/backtrace-sys/0.1.31 \
    crate://crates.io/backtrace/0.3.34 \
    crate://crates.io/base64/0.10.1 \
    crate://crates.io/base64/0.11.0 \
    crate://crates.io/base64/0.9.1 \
    crate://crates.io/bitflags/1.0.3 \
    crate://crates.io/blake2-rfc/0.2.18 \
    crate://crates.io/block-buffer/0.3.3 \
    crate://crates.io/byte-tools/0.2.0 \
    crate://crates.io/byte-unit/3.0.3 \
    crate://crates.io/byteorder/1.3.1 \
    crate://crates.io/bytes/0.4.12 \
    crate://crates.io/bytes/0.5.4 \
    crate://crates.io/bzip2-sys/0.1.7 \
    crate://crates.io/bzip2/0.3.3 \
    crate://crates.io/c2-chacha/0.2.2 \
    crate://crates.io/cc/1.0.37 \
    crate://crates.io/cfg-if/0.1.9 \
    crate://crates.io/chrono-humanize/0.0.11 \
    crate://crates.io/chrono/0.4.9 \
    crate://crates.io/clap/2.31.2 \
    crate://crates.io/cloudabi/0.0.3 \
    crate://crates.io/cmake/0.1.40 \
    crate://crates.io/config/0.9.3 \
    crate://crates.io/consistenttime/0.2.0 \
    crate://crates.io/constant_time_eq/0.1.3 \
    crate://crates.io/core-foundation-sys/0.5.1 \
    crate://crates.io/core-foundation/0.5.1 \
    crate://crates.io/crc32fast/1.2.0 \
    crate://crates.io/crossbeam-deque/0.7.1 \
    crate://crates.io/crossbeam-epoch/0.7.2 \
    crate://crates.io/crossbeam-queue/0.1.2 \
    crate://crates.io/crossbeam-utils/0.6.6 \
    crate://crates.io/crypto-mac/0.5.2 \
    crate://crates.io/digest/0.7.2 \
    crate://crates.io/dirs/1.0.4 \
    crate://crates.io/doc-comment/0.3.1 \
    crate://crates.io/dtoa/0.4.2 \
    crate://crates.io/either/1.5.3 \
    crate://crates.io/env_logger/0.5.9 \
    crate://crates.io/error-chain/0.11.0 \
    crate://crates.io/failure/0.1.2 \
    crate://crates.io/failure_derive/0.1.2 \
    crate://crates.io/fake-simd/0.1.2 \
    crate://crates.io/flate2/1.0.11 \
    crate://crates.io/fnv/1.0.6 \
    crate://crates.io/foreign-types-shared/0.1.1 \
    crate://crates.io/foreign-types/0.3.2 \
    crate://crates.io/fuchsia-zircon-sys/0.3.3 \
    crate://crates.io/fuchsia-zircon/0.3.3 \
    crate://crates.io/futures-cpupool/0.1.8 \
    crate://crates.io/futures/0.1.29 \
    crate://crates.io/generic-array/0.9.0 \
    crate://crates.io/getrandom/0.1.6 \
    crate://crates.io/h2/0.1.26 \
    crate://crates.io/hex/0.3.2 \
    crate://crates.io/hmac/0.5.0 \
    crate://crates.io/http-body/0.1.0 \
    crate://crates.io/http/0.1.18 \
    crate://crates.io/http/0.2.1 \
    crate://crates.io/httparse/1.2.4 \
    crate://crates.io/humantime/1.1.1 \
    crate://crates.io/hyper-proxy/0.5.1 \
    crate://crates.io/hyper-tls/0.3.2 \
    crate://crates.io/hyper/0.12.35 \
    crate://crates.io/hyperlocal/0.6.0 \
    crate://crates.io/idna/0.1.4 \
    crate://crates.io/idna/0.2.0 \
    crate://crates.io/indexmap/1.0.1 \
    crate://crates.io/iovec/0.1.2 \
    crate://crates.io/itoa/0.4.1 \
    crate://crates.io/json-patch/0.2.5 \
    crate://crates.io/k8s-openapi/0.7.1 \
    crate://crates.io/kernel32-sys/0.2.2 \
    crate://crates.io/lazy_static/1.4.0 \
    crate://crates.io/lazycell/0.6.0 \
    crate://crates.io/lazycell/1.2.0 \
    crate://crates.io/libc/0.2.66 \
    crate://crates.io/linked-hash-map/0.5.1 \
    crate://crates.io/log/0.4.5 \
    crate://crates.io/maplit/1.0.1 \
    crate://crates.io/matches/0.1.6 \
    crate://crates.io/memchr/2.0.1 \
    crate://crates.io/memoffset/0.5.1 \
    crate://crates.io/mime/0.3.5 \
    crate://crates.io/miniz_oxide/0.3.2 \
    crate://crates.io/mio-named-pipes/0.1.6 \
    crate://crates.io/mio-uds/0.6.7 \
    crate://crates.io/mio/0.6.14 \
    crate://crates.io/miow/0.2.1 \
    crate://crates.io/miow/0.3.1 \
    crate://crates.io/native-tls/0.2.1 \
    crate://crates.io/net2/0.2.32 \
    crate://crates.io/nix/0.14.1 \
    crate://crates.io/nodrop/0.1.12 \
    crate://crates.io/nom/4.2.3 \
    crate://crates.io/ntapi/0.3.3 \
    crate://crates.io/num-bigint/0.2.3 \
    crate://crates.io/num-complex/0.2.3 \
    crate://crates.io/num-integer/0.1.41 \
    crate://crates.io/num-iter/0.1.39 \
    crate://crates.io/num-rational/0.2.2 \
    crate://crates.io/num-traits/0.2.8 \
    crate://crates.io/num/0.2.0 \
    crate://crates.io/num_cpus/1.8.0 \
    crate://crates.io/objekt/0.1.2 \
    crate://crates.io/once_cell/1.3.1 \
    crate://crates.io/openssl-probe/0.1.2 \
    crate://crates.io/openssl-sys/0.9.36 \
    crate://crates.io/openssl/0.10.12 \
    crate://crates.io/ordered-float/1.0.2 \
    crate://crates.io/parse_duration/2.0.1 \
    crate://crates.io/percent-encoding/1.0.1 \
    crate://crates.io/percent-encoding/2.1.0 \
    crate://crates.io/pkg-config/0.3.11 \
    crate://crates.io/podio/0.1.6 \
    crate://crates.io/ppv-lite86/0.2.5 \
    crate://crates.io/proc-macro2/0.4.19 \
    crate://crates.io/proc-macro2/1.0.6 \
    crate://crates.io/quick-error/1.2.1 \
    crate://crates.io/quote/0.6.8 \
    crate://crates.io/quote/1.0.2 \
    crate://crates.io/rand/0.4.2 \
    crate://crates.io/rand/0.5.4 \
    crate://crates.io/rand/0.7.2 \
    crate://crates.io/rand_chacha/0.2.1 \
    crate://crates.io/rand_core/0.2.1 \
    crate://crates.io/rand_core/0.5.1 \
    crate://crates.io/rand_hc/0.2.0 \
    crate://crates.io/rayon-core/1.6.0 \
    crate://crates.io/rayon/1.2.0 \
    crate://crates.io/redox_syscall/0.1.37 \
    crate://crates.io/redox_termios/0.1.1 \
    crate://crates.io/redox_users/0.2.0 \
    crate://crates.io/regex-syntax/0.5.6 \
    crate://crates.io/regex-syntax/0.6.12 \
    crate://crates.io/regex/0.2.11 \
    crate://crates.io/regex/1.0.2 \
    crate://crates.io/remove_dir_all/0.5.1 \
    crate://crates.io/rustc-demangle/0.1.7 \
    crate://crates.io/rustc_version/0.2.3 \
    crate://crates.io/ryu/0.2.7 \
    crate://crates.io/safemem/0.2.0 \
    crate://crates.io/schannel/0.1.13 \
    crate://crates.io/scoped_threadpool/0.1.9 \
    crate://crates.io/scopeguard/0.3.3 \
    crate://crates.io/scopeguard/1.0.0 \
    crate://crates.io/security-framework-sys/0.2.1 \
    crate://crates.io/security-framework/0.2.1 \
    crate://crates.io/semver-parser/0.7.0 \
    crate://crates.io/semver/0.9.0 \
    crate://crates.io/serde-value/0.6.0 \
    crate://crates.io/serde/1.0.92 \
    crate://crates.io/serde_derive/1.0.92 \
    crate://crates.io/serde_json/1.0.27 \
    crate://crates.io/serde_yaml/0.7.4 \
    crate://crates.io/serde_yaml/0.8.8 \
    crate://crates.io/sha2/0.7.1 \
    crate://crates.io/slab/0.4.1 \
    crate://crates.io/socket2/0.3.5 \
    crate://crates.io/spin/0.5.2 \
    crate://crates.io/string/0.2.1 \
    crate://crates.io/strsim/0.7.0 \
    crate://crates.io/syn/0.14.9 \
    crate://crates.io/syn/0.15.36 \
    crate://crates.io/syn/1.0.11 \
    crate://crates.io/synstructure/0.9.0 \
    crate://crates.io/sysinfo/0.12.0 \
    crate://crates.io/sysinfo/0.9.6 \
    crate://crates.io/tabwriter/1.0.4 \
    crate://crates.io/tempdir/0.3.7 \
    crate://crates.io/tempfile/3.1.0 \
    crate://crates.io/termcolor/0.3.6 \
    crate://crates.io/termion/1.5.1 \
    crate://crates.io/test-case/0.3.3 \
    crate://crates.io/textwrap/0.9.0 \
    crate://crates.io/thread_local/0.3.5 \
    crate://crates.io/time/0.1.39 \
    crate://crates.io/tokio-buf/0.1.1 \
    crate://crates.io/tokio-codec/0.1.0 \
    crate://crates.io/tokio-current-thread/0.1.6 \
    crate://crates.io/tokio-executor/0.1.8 \
    crate://crates.io/tokio-fs/0.1.6 \
    crate://crates.io/tokio-io/0.1.8 \
    crate://crates.io/tokio-reactor/0.1.1 \
    crate://crates.io/tokio-signal/0.2.5 \
    crate://crates.io/tokio-sync/0.1.7 \
    crate://crates.io/tokio-tcp/0.1.0 \
    crate://crates.io/tokio-threadpool/0.1.16 \
    crate://crates.io/tokio-timer/0.2.11 \
    crate://crates.io/tokio-tls/0.2.0 \
    crate://crates.io/tokio-udp/0.1.0 \
    crate://crates.io/tokio-uds/0.2.5 \
    crate://crates.io/tokio/0.1.22 \
    crate://crates.io/treediff/3.0.1 \
    crate://crates.io/try-lock/0.2.2 \
    crate://crates.io/typed-headers/0.1.1 \
    crate://crates.io/typenum/1.10.0 \
    crate://crates.io/ucd-util/0.1.1 \
    crate://crates.io/unicase/2.1.0 \
    crate://crates.io/unicode-bidi/0.3.4 \
    crate://crates.io/unicode-normalization/0.1.5 \
    crate://crates.io/unicode-width/0.1.4 \
    crate://crates.io/unicode-xid/0.1.0 \
    crate://crates.io/unicode-xid/0.2.0 \
    crate://crates.io/unreachable/1.0.0 \
    crate://crates.io/url/1.7.2 \
    crate://crates.io/url/2.1.1 \
    crate://crates.io/url_serde/0.2.0 \
    crate://crates.io/utf8-ranges/1.0.0 \
    crate://crates.io/vcpkg/0.2.3 \
    crate://crates.io/vec_map/0.8.0 \
    crate://crates.io/version_check/0.1.3 \
    crate://crates.io/version_check/0.9.1 \
    crate://crates.io/void/1.0.2 \
    crate://crates.io/want/0.2.0 \
    crate://crates.io/widestring/0.3.0 \
    crate://crates.io/winapi-build/0.1.1 \
    crate://crates.io/winapi-i686-pc-windows-gnu/0.4.0 \
    crate://crates.io/winapi-x86_64-pc-windows-gnu/0.4.0 \
    crate://crates.io/winapi/0.2.8 \
    crate://crates.io/winapi/0.3.8 \
    crate://crates.io/wincolor/0.1.6 \
    crate://crates.io/windows-service/0.1.0 \
    crate://crates.io/winreg/0.5.1 \
    crate://crates.io/ws2_32-sys/0.2.1 \
    crate://crates.io/yaml-rust/0.4.0 \
    crate://crates.io/zip/0.5.3 \
    git://github.com/Azure/hyperlocal-windows;protocol=https;nobranch=1;name=hyperlocal-windows;destsuffix=hyperlocal-windows \
    git://github.com/Azure/mio-uds-windows.git;protocol=https;nobranch=1;name=mio-uds-windows;destsuffix=mio-uds-windows \
    git://github.com/Azure/tokio-uds-windows.git;protocol=https;nobranch=1;name=tokio-uds-windows;destsuffix=tokio-uds-windows \
"

SRCREV_FORMAT .= "_hyperlocal-windows"
SRCREV_hyperlocal-windows = "${AUTOREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/hyperlocal-windows"
SRCREV_FORMAT .= "_mio-uds-windows"
SRCREV_mio-uds-windows = "${AUTOREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/mio-uds-windows"
SRCREV_FORMAT .= "_tokio-uds-windows"
SRCREV_tokio-uds-windows = "${AUTOREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/tokio-uds-windows"

LIC_FILES_CHKSUM = " \
file://../../LICENSE;md5=0f7e3b1308cb5c00b372a6e78835732d \
file://../../THIRDPARTYNOTICES;md5=766e8bf0f17552c5c4cea26775a5b296 \
"

SUMMARY = "IoT Edge Security Daemon"
HOMEPAGE = "https://github.com/azure/iotedge"
LICENSE = "MIT"

include iotedge-daemon-${PV}.inc
include iotedge-daemon.inc
