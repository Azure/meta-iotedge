#!/bin/bash -x

# Fetch Yocto layers at a specified branch
# Usage: ./scripts/fetch.sh <yocto-branch>
# Examples:
#   ./scripts/fetch.sh scarthgap    # For Scarthgap release
#   ./scripts/fetch.sh kirkstone    # For Kirkstone release

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <yocto-branch>"
    echo "  yocto-branch: Yocto release branch (e.g., scarthgap, kirkstone)"
    echo ""
    echo "Examples:"
    echo "  $0 scarthgap    # Fetch layers for Scarthgap release"
    echo "  $0 kirkstone    # Fetch layers for Kirkstone release"
    exit 1
fi
branch=${1}

# the repos we want to check out, must setup variables below
# NOTE: poky must remain first.
REPOS="poky metaoe metavirt metasecurity metaclang"

POKY_URI="https://git.yoctoproject.org/poky.git"
POKY_UPSTREAM_URI="${POKY_URI}"
POKY_PATH="poky"
POKY_REV="${POKY_REV-refs/remotes/origin/${branch}}"

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

if [[ "${GIT_MIRROR}" == "github" ]]; then
	POKY_URI=$(verify_github_mirror "poky" "https://github.com/yoctoproject/poky.git" "${POKY_UPSTREAM_URI}")
	METAOE_URI=$(verify_github_mirror "meta-openembedded" "https://github.com/openembedded/meta-openembedded.git" "${METAOE_UPSTREAM_URI}")
	METAVIRT_URI=$(verify_github_mirror "meta-virtualization" "https://github.com/yoctoproject/meta-virtualization.git" "${METAVIRT_UPSTREAM_URI}")
	METASECURITY_URI=$(verify_github_mirror "meta-security" "https://github.com/yoctoproject/meta-security.git" "${METASECURITY_UPSTREAM_URI}")
fi

die() {
	echo "$*" >&2
	exit 1
}

update_repo() {
	uri=$1
	path=$2
	rev=$3

	clone_with_fallback() {
		local primary_uri="$1"
		local target_path="$2"
		if git clone "${primary_uri}" "${target_path}"; then
			return 0
		fi

		if [[ "${primary_uri}" == https://git.yoctoproject.org/* ]]; then
			local fallback_uri="${primary_uri/https:\/\/git.yoctoproject.org/git:\/\/git.yoctoproject.org}"
			echo "Retrying with ${fallback_uri}"
			git clone "${fallback_uri}" "${target_path}" && return 0
		fi
		if [[ "${primary_uri}" == https://git.openembedded.org/* ]]; then
			local fallback_uri="${primary_uri/https:\/\/git.openembedded.org/git:\/\/git.openembedded.org}"
			echo "Retrying with ${fallback_uri}"
			git clone "${fallback_uri}" "${target_path}" && return 0
		fi

		return 1
	}

	# check if we already have it checked out, if so we just want to update
	if [[ -d ${path} ]]; then
		pushd ${path} > /dev/null
		echo "Updating '${path}'"
		git remote set-url origin "${uri}"
		git fetch origin || die "unable to fetch ${uri}"
	else
		echo "Cloning '${path}'"
		if [[ -n "${GIT_LOCAL_REF_DIR}" && -d "${GIT_LOCAL_REF_DIR}" ]]; then
			git clone --reference ${GIT_LOCAL_REF_DIR}/`basename ${path}` \
				${uri} ${path} || die "unable to clone ${uri}"
		else
			clone_with_fallback "${uri}" "${path}" || die "unable to clone ${uri}"
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

# For each repo, do the work
for repo in ${REPOS}; do
	# upper case the name
	repo=$(echo ${repo} | tr '[:lower:]' '[:upper:]')

	# expand variables
	expand_uri="${repo}_URI"
	expand_path="${repo}_PATH"
	expand_rev="${repo}_REV"
	repo_uri=${!expand_uri}
	repo_path=${!expand_path}
	repo_rev=${!expand_rev}

	# check that we've got data
	[[ -z ${repo_uri} ]] && die "No revision defined in ${expand_uri}"
	[[ -z ${repo_path} ]] && die "No revision defined in ${expand_path}"
	[[ -z ${repo_rev} ]] && die "No revision defined in ${expand_rev}"

	# now fetch/clone/update repo
	update_repo "${repo_uri}" "${repo_path}" "${repo_rev}"

done

rm -rf "${METAIOTEDGE_PATH}" || die "unable to clear old ${METAIOTEDGE_PATH}"
ln -sf "../${METAIOTEDGE_URI}" "${METAIOTEDGE_PATH}" || \
	die "unable to symlink ${METAIOTEDGE_PATH}"

exit 0

