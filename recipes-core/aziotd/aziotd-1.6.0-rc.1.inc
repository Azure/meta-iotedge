export VERSION = "1.6.0-rc.1"

# The keys.generated.rs prepend and the panic=abort -> unwind patch both live in
# the shared aziotd.inc now (the prepend uses ${UNPACK_ROOT} so it works on both
# Scarthgap and Wrynose). The 1.6-specific copies of keys.generated.rs and
# 0001-Remove-panic.patch live in the aziotd-1.6.0-rc.1/ FILESPATH directory.
