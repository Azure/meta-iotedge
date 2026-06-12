export VERSION = "1.5.21"
IOTEDGE_RELEASE = "1.5.35"
IIS_SRCREV = "833381accec8d53436cac20fc3fb85303e4504eb"

# Source-compatibility patches for the 1.5 edgelet workspace. These moved here
# from the shared iotedge.inc so that 1.5.x and 1.6.x recipes can coexist on
# the same branch (the upstream Cargo.toml / source layout differs by release).
SRC_URI += "file://0001-Remove-panic-abort-from-workspace-profiles.patch \
            file://0002-Work-around-Rust-1.78-dead_code-lint-issues.patch \
"
