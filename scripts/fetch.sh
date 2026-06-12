#!/bin/bash -x

# Fetch Yocto layers at a specified branch
# Usage: ./scripts/fetch.sh <yocto-branch>
# Examples:
#   ./scripts/fetch.sh wrynose      # For Wrynose release (Yocto 6.0, split repos)
#   ./scripts/fetch.sh scarthgap    # For Scarthgap release (poky combo repo)
#   ./scripts/fetch.sh kirkstone    # For Kirkstone release (poky combo repo)
#
# Layout produced under poky/ (kept stable across releases so bblayers paths
# don't churn):
#   poky/                      oe-core (provides meta, scripts, oe-init-build-env)
#   poky/bitbake               bitbake
#   poky/meta-poky             meta-poky (combo: from poky; wrynose: from meta-yocto)
#   poky/meta-yocto-bsp        meta-yocto-bsp (combo: from poky; wrynose: from meta-yocto)
#   poky/meta-openembedded     meta-openembedded
#   poky/meta-clang            meta-clang
#   poky/meta-virtualization   meta-virtualization
#   poky/meta-security         meta-security
#   poky/meta-iotedge -> ..    symlink to this repo
#
# Wrynose (Yocto 6.0) note: the poky "combo" repo is deprecated upstream, so
# there is no `wrynose` branch in yoctoproject/poky.  For wrynose we assemble
# the equivalent tree from the split upstream repos:
#   - openembedded-core (the `meta` layer + scripts + oe-init-build-env)
#   - bitbake (its own repo)
#   - meta-yocto (provides meta-poky + meta-yocto-bsp)
# meta-rust is NOT needed on wrynose: Rust (1.94.1) and bindgen-cli (0.72.1)
# ship in oe-core.

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <yocto-branch>"
    echo "  yocto-branch: Yocto release branch (e.g., wrynose, scarthgap, kirkstone)"
    echo ""
    echo "Examples:"
    echo "  $0 wrynose      # Fetch layers for Wrynose release (split repos)"
    echo "  $0 scarthgap    # Fetch layers for Scarthgap release (poky combo)"
    echo "  $0 kirkstone    # Fetch layers for Kirkstone release (poky combo)"
    exit 1
fi
branch=${1}

# The poky "combo" repo was deprecated upstream starting with Yocto 6.0
# (Wrynose), so wrynose and later must be assembled from the split repos.
# Scarthgap (5.0) and earlier still ship the combo poky repo.
# Default: combo layout, unless the codename is known to need split repos.
SPLIT_REPO=0
case "${branch}" in
    wrynose) SPLIT_REPO=1 ;;  # Yocto 6.0 LTS: split repos (combo deprecated)
esac
# Explicit override for future codenames / testing: FORCE_SPLIT_REPO=1|0
[[ -n "${FORCE_SPLIT_REPO:-}" ]] && SPLIT_REPO="${FORCE_SPLIT_REPO}"

die() {
	echo "$*" >&2
	exit 1
}

# Optional GitHub mirrors for Yocto repos
# Default to GitHub mirrors for faster fetch; set GIT_MIRROR=yocto to use upstream.
: "${GIT_MIRROR:=github}"

verify_github_mirror() {
	local name="$1"
	local mirror_uri="$2"
	local fallback_uri="$3"
	if git ls-remote --heads "${mirror_uri}" >/dev/null 2>&1; then
		echo "Using GitHub mirror for ${name}: ${mirror_uri}" >&2
		echo "${mirror_uri}"
	else
		echo "GitHub mirror not found for ${name}, using upstream: ${fallback_uri}" >&2
		echo "${fallback_uri}"
	fi
}

update_repo() {
	uri=$1
	path=$2
	rev=$3

	# Clone with retries (HTTPS only, no insecure git:// fallback)
	clone_with_retry() {
		local uri="$1"
		local target_path="$2"
		local attempt=1
		local max_attempts=3
		local delay=5

		while [[ $attempt -le $max_attempts ]]; do
			if git clone "${uri}" "${target_path}"; then
				return 0
			fi
			echo "Clone attempt ${attempt}/${max_attempts} failed, retrying in ${delay}s..." >&2
			rm -rf "${target_path}" 2>/dev/null || true
			sleep "$delay"
			((attempt++, delay*=2))
		done
		return 1
	}

	# check if we already have it checked out, if so we just want to update
	if [[ -d ${path}/.git ]]; then
		pushd ${path} > /dev/null
		echo "Updating '${path}'"
		git remote set-url origin "${uri}"
		git fetch origin || die "unable to fetch ${uri}"
	else
		echo "Cloning '${path}'"
		rm -rf "${path}" 2>/dev/null || true
		if [[ -n "${GIT_LOCAL_REF_DIR}" && -d "${GIT_LOCAL_REF_DIR}" ]]; then
			git clone --reference ${GIT_LOCAL_REF_DIR}/`basename ${path}` \
				${uri} ${path} || die "unable to clone ${uri}"
		else
			clone_with_retry "${uri}" "${path}" || die "unable to clone ${uri}"
		fi
		pushd ${path} > /dev/null
	fi

	# The reset steps are taken from Jenkins

	# Reset
	# * drop -d from clean to not nuke build/tmp
	# * add -e to not clear out bitbake bits
	git reset --hard || die "failed reset"
	git clean -fx -e bitbake -e meta/lib/oe || die "failed clean"

	# Call the branch what we're basing it on, otherwise use default
	# if the revision was not a branch.
	branch=$(basename ${rev})
	[[ "${branch}" == "${rev}" ]] && branch="default"

	# Create 'default' branch
	git update-ref refs/heads/${branch} ${rev} || \
		die "unable to get ${rev} of ${uri}"
	git config branch.${branch}.remote origin || die "failed config remote"
	git config branch.${branch}.merge ${rev} || die "failed config merge"
	git symbolic-ref HEAD refs/heads/${branch} || die "failed symbolic-ref"
	git reset --hard || die "failed reset"
	popd > /dev/null
	echo "Updated '${path}' to '${rev}'"
}

# ---- Common repos (same for split and combo) ----

METAOE_URI="https://git.openembedded.org/meta-openembedded.git"
METAOE_UPSTREAM_URI="${METAOE_URI}"
METAOE_PATH="poky/meta-openembedded"
METAOE_REV="${METAOE_REV-refs/remotes/origin/${branch}}"

METAVIRT_URI="https://git.yoctoproject.org/meta-virtualization"
METAVIRT_UPSTREAM_URI="${METAVIRT_URI}"
METAVIRT_PATH="poky/meta-virtualization"
METAVIRT_REV="${METAVIRT_REV-refs/remotes/origin/${branch}}"

METASECURITY_URI="https://git.yoctoproject.org/meta-security"
METASECURITY_UPSTREAM_URI="${METASECURITY_URI}"
METASECURITY_PATH="poky/meta-security"
METASECURITY_REV="${METASECURITY_REV-refs/remotes/origin/${branch}}"

METACLANG_URI="https://github.com/kraj/meta-clang"
METACLANG_UPSTREAM_URI="${METACLANG_URI}"
METACLANG_PATH="poky/meta-clang"
METACLANG_REV="${METACLANG_REV-refs/remotes/origin/${branch}}"

METAIOTEDGE_URI="."
METAIOTEDGE_PATH="poky/meta-iotedge"

if [[ "${GIT_MIRROR}" == "github" ]]; then
	METAOE_URI=$(verify_github_mirror "meta-openembedded" "https://github.com/openembedded/meta-openembedded.git" "${METAOE_UPSTREAM_URI}")
	# meta-virtualization / meta-security do NOT have a yoctoproject GitHub
	# mirror; keep the authoritative git.yoctoproject.org URIs.
	METACLANG_URI=$(verify_github_mirror "meta-clang" "https://github.com/kraj/meta-clang" "${METACLANG_UPSTREAM_URI}")
fi

if [[ "${SPLIT_REPO}" == "1" ]]; then
	# ---- Wrynose (Yocto 6.0) split-repo layout ----
	echo "Using split-repo layout for '${branch}' (Yocto 6.0+)."

	# oe-core provides poky/meta + scripts + oe-init-build-env
	OECORE_URI="https://git.openembedded.org/openembedded-core"
	OECORE_PATH="poky"
	OECORE_REV="${OECORE_REV-refs/remotes/origin/${branch}}"

	# bitbake is its own repo on wrynose. oe-core wrynose pairs with bitbake 2.18.
	BITBAKE_URI="https://git.openembedded.org/bitbake"
	BITBAKE_PATH="poky/bitbake"
	BITBAKE_REV="${BITBAKE_REV-refs/remotes/origin/2.18}"

	# meta-yocto provides meta-poky + meta-yocto-bsp
	METAYOCTO_URI="https://git.yoctoproject.org/meta-yocto"
	METAYOCTO_PATH="poky/meta-yocto"
	METAYOCTO_REV="${METAYOCTO_REV-refs/remotes/origin/${branch}}"

	if [[ "${GIT_MIRROR}" == "github" ]]; then
		OECORE_URI=$(verify_github_mirror "openembedded-core" "https://github.com/openembedded/openembedded-core.git" "${OECORE_URI}")
		BITBAKE_URI=$(verify_github_mirror "bitbake" "https://github.com/openembedded/bitbake.git" "${BITBAKE_URI}")
		# meta-yocto github mirror lives at yoctoproject/meta-yocto
		METAYOCTO_URI=$(verify_github_mirror "meta-yocto" "https://github.com/yoctoproject/meta-yocto.git" "${METAYOCTO_URI}")
	fi

	# Order matters: oe-core (poky) first so poky/ exists, then nested repos.
	update_repo "${OECORE_URI}"      "${OECORE_PATH}"      "${OECORE_REV}"
	update_repo "${BITBAKE_URI}"     "${BITBAKE_PATH}"     "${BITBAKE_REV}"
	update_repo "${METAYOCTO_URI}"   "${METAYOCTO_PATH}"   "${METAYOCTO_REV}"
	update_repo "${METAOE_URI}"      "${METAOE_PATH}"      "${METAOE_REV}"
	update_repo "${METAVIRT_URI}"    "${METAVIRT_PATH}"    "${METAVIRT_REV}"
	update_repo "${METASECURITY_URI}" "${METASECURITY_PATH}" "${METASECURITY_REV}"
	update_repo "${METACLANG_URI}"   "${METACLANG_PATH}"   "${METACLANG_REV}"

	# Expose meta-poky / meta-yocto-bsp at the stable poky/ paths via symlinks
	# so bblayers paths stay identical to the combo layout.
	rm -rf poky/meta-poky poky/meta-yocto-bsp
	ln -sf meta-yocto/meta-poky poky/meta-poky || die "unable to symlink meta-poky"
	ln -sf meta-yocto/meta-yocto-bsp poky/meta-yocto-bsp || die "unable to symlink meta-yocto-bsp"
else
	# ---- Scarthgap / Kirkstone combo poky repo ----
	echo "Using poky combo-repo layout for '${branch}'."

	POKY_URI="https://git.yoctoproject.org/poky.git"
	POKY_UPSTREAM_URI="${POKY_URI}"
	POKY_PATH="poky"
	POKY_REV="${POKY_REV-refs/remotes/origin/${branch}}"

	METARUST_URI="https://github.com/meta-rust/meta-rust"
	METARUST_PATH="poky/meta-rust"
	# Pin to 1c4ef8c (before f067576 which broke kirkstone compatibility by using undefined RUST_VERSION)
	# This provides Rust 1.78.0 which is sufficient for IoT Edge 1.5
	METARUST_REV="${METARUST_REV-1c4ef8cf7dea391b6a967a13abc61e878a8e778d}"

	if [[ "${GIT_MIRROR}" == "github" ]]; then
		POKY_URI=$(verify_github_mirror "poky" "https://github.com/yoctoproject/poky.git" "${POKY_UPSTREAM_URI}")
	fi

	update_repo "${POKY_URI}"        "${POKY_PATH}"        "${POKY_REV}"
	update_repo "${METAOE_URI}"      "${METAOE_PATH}"      "${METAOE_REV}"
	update_repo "${METAVIRT_URI}"    "${METAVIRT_PATH}"    "${METAVIRT_REV}"
	update_repo "${METASECURITY_URI}" "${METASECURITY_PATH}" "${METASECURITY_REV}"
	update_repo "${METACLANG_URI}"   "${METACLANG_PATH}"   "${METACLANG_REV}"
	update_repo "${METARUST_URI}"    "${METARUST_PATH}"    "${METARUST_REV}"
fi

rm -rf "${METAIOTEDGE_PATH}" || die "unable to clear old ${METAIOTEDGE_PATH}"
ln -sf "../${METAIOTEDGE_URI}" "${METAIOTEDGE_PATH}" || \
	die "unable to symlink ${METAIOTEDGE_PATH}"

exit 0
