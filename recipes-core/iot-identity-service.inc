# IoT Identity Service git dependencies
# These are the IIS library crates needed by IoT Edge recipes
# IIS_SRCREV must be defined by the version-specific .inc file
#
# NOTE (Wrynose/Yocto 6.0): EXTRA_OECARGO_PATHS below use ${UNPACKDIR}, not
# ${WORKDIR}. Modern poky sets UNPACKDIR=${WORKDIR}/sources and unpacks fetched
# crates there, so the cargo path overrides (and the synthetic workspace root)
# must be rooted at ${UNPACKDIR}. ${WORKDIR}/... pointed at non-existent dirs
# and made cargo fail do_compile with "failed to read directory".
#
# Debug buildpaths (Wrynose): the IIS crates above are fetched as siblings of
# the consuming recipe's ${S} (e.g. edgelet at ${UNPACKDIR}/aziot-edged-<ver>,
# IIS crates at ${UNPACKDIR}/key/..., ${UNPACKDIR}/openssl-sys2, ...). cc-rs
# compiles the C build-scripts of openssl-sys2 / aziot-key-openssl-engine with
# -g, embedding their ${UNPACKDIR}/<crate> source path into DWARF. OE's stock
# DEBUG_PREFIX_MAP only remaps ${S} and ${B}, so those sibling-crate paths are
# NOT rewritten and leak into the -dbg package, failing do_package_qa with:
#   QA Issue: File .../.debug/<bin> ... contains reference to TMPDIR [buildpaths]
# (aziotd is unaffected because its CARGO_SRC_DIR makes the IIS tree its own
# ${S}, which IS remapped.) Remap the ${UNPACKDIR} prefix too. This is safe
# alongside the existing more-specific ${S} entry: -ffile-prefix-map uses
# longest-prefix-match (verified), so files under ${S} keep the ${S} mapping
# while only the sibling crates pick up this ${UNPACKDIR} one.
DEBUG_PREFIX_MAP:append = " -ffile-prefix-map=${UNPACKDIR}=${TARGET_DBGSRC_DIR}"

IIS_GIT_URI ?= "git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;"

SRC_URI += " \
    ${IIS_GIT_URI}name=aziot-cert-client-async;destsuffix=cert/aziot-cert-client-async;subpath=cert/aziot-cert-client-async \
    ${IIS_GIT_URI}name=aziot-cert-common-http;destsuffix=cert/aziot-cert-common-http;subpath=cert/aziot-cert-common-http \
    ${IIS_GIT_URI}name=aziot-certd-config;destsuffix=cert/aziot-certd-config;subpath=cert/aziot-certd-config \
    ${IIS_GIT_URI}name=aziot-identity-client-async;destsuffix=identity/aziot-identity-client-async;subpath=identity/aziot-identity-client-async \
    ${IIS_GIT_URI}name=aziot-identity-common-http;destsuffix=identity/aziot-identity-common-http;subpath=identity/aziot-identity-common-http \
    ${IIS_GIT_URI}name=aziot-identity-common;destsuffix=identity/aziot-identity-common;subpath=identity/aziot-identity-common \
    ${IIS_GIT_URI}name=aziot-identityd-config;destsuffix=identity/aziot-identityd-config;subpath=identity/aziot-identityd-config \
    ${IIS_GIT_URI}name=aziot-key-client-async;destsuffix=key/aziot-key-client-async;subpath=key/aziot-key-client-async \
    ${IIS_GIT_URI}name=aziot-key-client;destsuffix=key/aziot-key-client;subpath=key/aziot-key-client \
    ${IIS_GIT_URI}name=aziot-key-common-http;destsuffix=key/aziot-key-common-http;subpath=key/aziot-key-common-http \
    ${IIS_GIT_URI}name=aziot-key-common;destsuffix=key/aziot-key-common;subpath=key/aziot-key-common \
    ${IIS_GIT_URI}name=aziot-key-openssl-engine;destsuffix=key/aziot-key-openssl-engine;subpath=key/aziot-key-openssl-engine \
    ${IIS_GIT_URI}name=aziot-keyd-config;destsuffix=key/aziot-keyd-config;subpath=key/aziot-keyd-config \
    ${IIS_GIT_URI}name=aziot-keys-common;destsuffix=key/aziot-keys-common;subpath=key/aziot-keys-common \
    ${IIS_GIT_URI}name=aziot-tpmd-config;destsuffix=tpm/aziot-tpmd-config;subpath=tpm/aziot-tpmd-config \
    ${IIS_GIT_URI}name=aziotctl-common;destsuffix=aziotctl/aziotctl-common;subpath=aziotctl/aziotctl-common \
    ${IIS_GIT_URI}name=cert-renewal;destsuffix=cert/cert-renewal;subpath=cert/cert-renewal \
    ${IIS_GIT_URI}name=config-common;destsuffix=config-common;subpath=config-common \
    ${IIS_GIT_URI}name=http-common;destsuffix=http-common;subpath=http-common \
    ${IIS_GIT_URI}name=logger;destsuffix=logger;subpath=logger \
    ${IIS_GIT_URI}name=openssl-build;destsuffix=openssl-build;subpath=openssl-build \
    ${IIS_GIT_URI}name=openssl-sys2;destsuffix=openssl-sys2;subpath=openssl-sys2 \
    ${IIS_GIT_URI}name=openssl2;destsuffix=openssl2;subpath=openssl2 \
    ${IIS_GIT_URI}name=pkcs11-sys;destsuffix=pkcs11/pkcs11-sys;subpath=pkcs11/pkcs11-sys \
    ${IIS_GIT_URI}name=pkcs11;destsuffix=pkcs11/pkcs11;subpath=pkcs11/pkcs11 \
    ${IIS_GIT_URI}name=test-common;destsuffix=test-common;subpath=test-common \
"

SRCREV_FORMAT .= "_aziot-cert-client-async"
SRCREV_aziot-cert-client-async = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/cert/aziot-cert-client-async"
SRCREV_FORMAT .= "_aziot-cert-common-http"
SRCREV_aziot-cert-common-http = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/cert/aziot-cert-common-http"
SRCREV_FORMAT .= "_aziot-certd-config"
SRCREV_aziot-certd-config = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/cert/aziot-certd-config"
SRCREV_FORMAT .= "_aziot-identity-client-async"
SRCREV_aziot-identity-client-async = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/identity/aziot-identity-client-async"
SRCREV_FORMAT .= "_aziot-identity-common"
SRCREV_aziot-identity-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/identity/aziot-identity-common"
SRCREV_FORMAT .= "_aziot-identity-common-http"
SRCREV_aziot-identity-common-http = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/identity/aziot-identity-common-http"
SRCREV_FORMAT .= "_aziot-identityd-config"
SRCREV_aziot-identityd-config = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/identity/aziot-identityd-config"
SRCREV_FORMAT .= "_aziot-key-client"
SRCREV_aziot-key-client = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/key/aziot-key-client"
SRCREV_FORMAT .= "_aziot-key-client-async"
SRCREV_aziot-key-client-async = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/key/aziot-key-client-async"
SRCREV_FORMAT .= "_aziot-key-common"
SRCREV_aziot-key-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/key/aziot-key-common"
SRCREV_FORMAT .= "_aziot-key-common-http"
SRCREV_aziot-key-common-http = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/key/aziot-key-common-http"
SRCREV_FORMAT .= "_aziot-key-openssl-engine"
SRCREV_aziot-key-openssl-engine = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/key/aziot-key-openssl-engine"
SRCREV_FORMAT .= "_aziot-keyd-config"
SRCREV_aziot-keyd-config = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/key/aziot-keyd-config"
SRCREV_FORMAT .= "_aziot-keys-common"
SRCREV_aziot-keys-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/key/aziot-keys-common"
SRCREV_FORMAT .= "_aziot-tpmd-config"
SRCREV_aziot-tpmd-config = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/tpm/aziot-tpmd-config"
SRCREV_FORMAT .= "_aziotctl-common"
SRCREV_aziotctl-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/aziotctl/aziotctl-common"
SRCREV_FORMAT .= "_cert-renewal"
SRCREV_cert-renewal = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/cert/cert-renewal"
SRCREV_FORMAT .= "_config-common"
SRCREV_config-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/config-common"
SRCREV_FORMAT .= "_http-common"
SRCREV_http-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/http-common"
SRCREV_FORMAT .= "_logger"
SRCREV_logger = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/logger"
SRCREV_FORMAT .= "_openssl-build"
SRCREV_openssl-build = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/openssl-build"
SRCREV_FORMAT .= "_openssl-sys2"
SRCREV_openssl-sys2 = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/openssl-sys2"
SRCREV_FORMAT .= "_openssl2"
SRCREV_openssl2 = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/openssl2"
SRCREV_FORMAT .= "_pkcs11"
SRCREV_pkcs11 = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/pkcs11/pkcs11"
SRCREV_FORMAT .= "_pkcs11-sys"
SRCREV_pkcs11-sys = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/pkcs11/pkcs11-sys"
SRCREV_FORMAT .= "_test-common"
SRCREV_test-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${UNPACKDIR}/test-common"

# --- IIS workspace root for the 1.6 split-crate layout -----------------------
#
# 1.6 IoT Identity Service adopted Cargo workspace dependency + lints
# inheritance: every sub-crate uses `<dep> = { workspace = true }` and
# `[lints] workspace = true`. We fetch those crates individually (subpath/
# destsuffix), so each lands under ${UNPACKDIR}/<destsuffix> WITHOUT the IIS
# workspace-root Cargo.toml above it. cargo then fails do_compile with:
#   error inheriting `hyper` from workspace root manifest's
#   workspace.dependencies.hyper -> failed to find a workspace root
# (1.5.x never inherited from the workspace, so it never hit this.)
#
# Fix: synthesize a minimal IIS workspace root at ${UNPACKDIR} (the common
# parent of cert/, key/, identity/, ... and of the edgelet source tree). Its
# members are derived from the fetched destsuffix set (single source of truth,
# self-maintaining if crates change). The edgelet tree carries its own
# [workspace], so it is excluded to avoid nested-workspace errors. No
# [profile.*] is emitted: build profiles belong to the build-root workspace,
# and emitting panic = "abort" here would undo the 1.6 edgelet source patch.
#
# [workspace.dependencies] / [workspace.lints] mirror the IIS root Cargo.toml
# at the pinned IIS_SRCREV. They live as a Python literal inside the task below
# (BitBake vars are single-line, so a multi-line heredoc is not expressible as
# a normal variable). Keep in sync on IIS bumps.

python iis_write_workspace_root() {
    import os

    # [workspace.dependencies] + [workspace.lints] copied from the IIS root
    # Cargo.toml at the pinned IIS_SRCREV. [profile.*] is intentionally omitted.
    iis_workspace_deps = '''
[workspace.dependencies]
anyhow = "1.0.34"
async-recursion = "1"
async-trait = "0.1.42"
backtrace = "0.3"
base64 = "0.22"
bindgen = { version = "0.72", features = ["runtime"], default-features = false }
byte-unit = "5"
bytes = "1"
cc = "1"
chrono = { version = "0.4", features = ["serde"] }
clap = { version = "4", features = ["derive"] }
colored = "3"
env_logger = "0.11"
erased-serde = "0.4"
foreign-types = "0.3"
foreign-types-shared = "0.1"
futures-core = "0.3"
futures-util = "0.3"
headers = "0.4"
hex = "0.4"
hmac = "0.13"
http = "1"
http-body = "1"
http-body-util = "0.1"
httparse = "1"
hyper = { version = "1", features = ["client", "http1", "server"] }
hyper-openssl = { version = "0.10", features = ["client-legacy", "tokio"] }
hyper-proxy2 = { version = "0.1", features = ["openssl-tls"], default-features = false }
hyper-util = { version = "0.1", features = ["client", "client-legacy", "http1", "service", "tokio"] }
itertools = "0.14"
libc = "0.2"
log = { version = "0.4", features = ["std"] }
nix = "0.31"
notify-debouncer-full = "0.7"
openssl = "0.10"
openssl-errors = "0.2"
openssl-sys = "0.9.86"
paste = "1"
percent-encoding = "2"
pkg-config = "0.3.20"
rand = "0.10"
regex = "1"
semver = "1"
serde = { version = "1", features = ["derive"] }
serde_json = "1.0.59"
serde_with = "3"
serial_test = "3"
sha2 = "0.11"
sysinfo = "0.38"
tokio = { version = "1", features = ["fs", "io-util", "macros", "net", "parking_lot", "rt", "rt-multi-thread", "sync", "time"] }
tokio-openssl = "0.6"
toml = "1"
tower-service = "0.3"
tracing = { version = "0.1", features = ["log"] }
url = { version = "2", features = ["serde"] }
uuid = { version = "1", features = ["v4"] }
wildmatch = "2"

[workspace.lints.rust]
rust_2018_idioms = { level = "deny", priority = -1 }

[workspace.lints.clippy]
all = { level = "warn", priority = -1 }
pedantic = { level = "warn", priority = -1 }
default_trait_access = "allow"
let_and_return = "allow"
missing_errors_doc = "allow"
missing_panics_doc = "allow"
must_use_candidate = "allow"
similar_names = "allow"
struct_field_names = "allow"
too_many_arguments = "allow"
too_many_lines = "allow"
type_complexity = "allow"
'''

    unpackdir = d.getVar('UNPACKDIR')
    if not unpackdir:
        return

    # Derive workspace members from the IIS crates we actually fetched, using
    # the destsuffix of each git/gitsm SRC_URI entry. This keeps the members
    # list in lockstep with the fetched set (no hand-maintained duplicate).
    members = []
    excludes = set()
    src_uri = (d.getVar('SRC_URI') or '').split()
    fetcher = bb.fetch2.Fetch(src_uri, d)
    for url in fetcher.urls:
        ud = fetcher.ud[url]
        if ud.type in ('git', 'gitsm'):
            destsuffix = ud.parm.get('destsuffix')
            if not destsuffix:
                continue
            rel = destsuffix.rstrip('/')
            # Only crates that physically live under UNPACKDIR and carry a
            # Cargo.toml are real workspace members.
            if os.path.exists(os.path.join(unpackdir, rel, 'Cargo.toml')):
                members.append(rel)
            else:
                # Top-level dir of a non-crate destsuffix gets excluded so a
                # stray Cargo.toml underneath can't be auto-claimed.
                top = rel.split('/', 1)[0]
                if top:
                    excludes.add(top)

    # The edgelet (and any other source tree) under UNPACKDIR has its own
    # [workspace]; exclude every top-level dir we did not list as a member so
    # cargo never treats them as part of this synthetic IIS workspace.
    member_tops = {m.split('/', 1)[0] for m in members}
    try:
        for entry in os.listdir(unpackdir):
            full = os.path.join(unpackdir, entry)
            if entry in member_tops:
                continue
            if entry in ('cargo_home',):
                continue
            if os.path.isdir(full):
                excludes.add(entry)
    except FileNotFoundError:
        pass

    if not members:
        bb.warn('iot-identity-service.inc: no IIS workspace members found under '
                '%s; skipping synthetic workspace root' % unpackdir)
        return

    members.sort()
    lines = ['# Auto-generated by iot-identity-service.inc (iis_write_workspace_root prefunc).',
             '# Synthetic IoT Identity Service workspace root so detached 1.6',
             '# crates can inherit workspace.dependencies / workspace.lints.',
             '[workspace]',
             'resolver = "2"',
             'members = [']
    lines += ['\t"%s",' % m for m in members]
    lines.append(']')
    if excludes:
        lines.append('exclude = [')
        lines += ['\t"%s",' % e for e in sorted(excludes)]
        lines.append(']')
    lines.append('')
    lines.append(iis_workspace_deps.strip())
    lines.append('')

    root = os.path.join(unpackdir, 'Cargo.toml')
    with open(root, 'w') as f:
        f.write('\n'.join(lines))
    bb.note('iot-identity-service.inc: wrote synthetic IIS workspace root %s '
            'with %d members' % (root, len(members)))
}

# Run the synthetic-root writer just before do_configure. A prefunc (not a
# python do_configure:prepend) is required because the cargo class defines
# do_configure as a shell function, and BitBake cannot inject python into a
# shell task body.
do_configure[prefuncs] += "iis_write_workspace_root"
