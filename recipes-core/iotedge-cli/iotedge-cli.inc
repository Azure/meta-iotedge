DEPENDS += "openssl10"

do_install () {
    local have_installed=false
    for tgt in "${WORKDIR}/git/edgelet/target/${CARGO_TARGET_SUBDIR}/"*; do
        case $tgt in
        *.so|*.rlib)
            install -d "${D}${rustlibdir}"
            install -m755 "$tgt" "${D}${rustlibdir}"
            have_installed=true
            ;;
        *)
            if [ -f "$tgt" ] && [ -x "$tgt" ]; then
                install -d "${D}${bindir}"
                install -m755 "$tgt" "${D}${bindir}"
                have_installed=true
            fi
            ;;
        esac
    done
    if ! $have_installed; then
        die "Did not find anything to install"
    fi
}

