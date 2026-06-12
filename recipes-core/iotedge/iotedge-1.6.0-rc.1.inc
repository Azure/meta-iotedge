export VERSION = "1.6.0-rc.1"
IOTEDGE_RELEASE = "1.6.0-rc.1"
IIS_SRCREV = "1a7a6e70c3a20389fd24090bba201b7fdd7de582"

# Source-compatibility patch for the 1.6 edgelet workspace (panic=abort ->
# unwind, required by the Yocto Rust sysroot). 1.6 no longer needs the old
# Rust 1.78 dead_code lint workaround: lints moved to [workspace.lints] in
# Cargo.toml and `warnings` is no longer denied.
SRC_URI += "file://0001-Remove-panic-abort-from-workspace-profiles.patch"
