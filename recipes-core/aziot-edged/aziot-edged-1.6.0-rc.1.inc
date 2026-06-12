export VERSION = "1.6.0-rc.1"
IOTEDGE_RELEASE = "1.6.0-rc.1"
IIS_SRCREV = "1a7a6e70c3a20389fd24090bba201b7fdd7de582"

# Source-compatibility patch for the 1.6 edgelet workspace (panic=abort ->
# unwind, required by the Yocto Rust sysroot). 1.6 no longer needs the old
# Rust 1.78 dead_code lint workaround: lints moved to [workspace.lints] in
# Cargo.toml and `warnings` is no longer denied.
SRC_URI += "file://0001-Remove-panic-abort-from-workspace-profiles.patch"

# Pin sysinfo to 0.38 (MSRV 1.88) so the edgelet workspace builds with the
# Wrynose poky Rust toolchain (rustc 1.94.1); sysinfo 0.39 requires rustc 1.95.
# Rewrites edgelet/Cargo.toml + Cargo.lock; the --frozen cargo build requires
# the lock to already match, so the lock is fixed up in the same patch.
SRC_URI += "file://0002-Pin-sysinfo-0.38-for-Yocto-Rust-1.94.patch"
