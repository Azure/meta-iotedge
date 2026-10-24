# CI cache preparation (agent-local only)

`prepare-yocto-cache.sh` replaces the build job's automatic account allocation
and recursive cache chown. It does **not** enable shared storage, change the
container orchestration, or require a custom runner VM image.

## Local contract

- Run as root in the existing CI devcontainer, once per fresh job container.
  The existing default remains `/var/cache/yocto` bound to
  `/workspaces/yocto-cache`; an optional first argument selects the container path.
- `builder` is explicitly UID/GID **1001:1001**, verified against the current
  devcontainer (digest below). This matches the old `useradd -m builder`
  allocation, so normal existing local cache ownership stays compatible.
  Existing user/name or group/ID collisions fail instead of choosing another ID.
- The cache root must already exist. Before creating accounts or cache files,
  reject symlinked root/download/sstate directories and remote/unknown backing
  filesystems. The local allowlist is ext2/3/4 (`stat` reports `ext2/ext3`), XFS,
  Btrfs, overlayfs and tmpfs. This type check is **not a trust boundary**.
- Create/update only the `downloads` and `sstate-cache` directory inodes with
  builder ownership and `install -d`'s normal 0755 permissions. Do not walk,
  chown, chmod, delete or migrate existing cache contents. Caches previously
  written with another UID need separately reviewed maintenance, not an
  automatic recursive repair.
- Actually create, write and remove a unique temporary file as builder in each
  directory; any failure stops the job before fetching/building. `TMPDIR`,
  workspace and BitBake working state remain unchanged/local.

## Shared storage is not implemented

There is no shared-mode flag or repository-variable opt-in. NFS/CIFS and unknown
filesystems are rejected before cache writes. Container checks cannot mount
storage, distinguish every possible backing-store topology, or prove that a
host mount existed before Actions created the job container. This helper is not
an authorized mount/bootstrap implementation or cache security boundary.

The live pool executes public PR code with root-capable container access.
Neither repository-controlled code/variables, numeric UID checks, nor a `:ro`
bind can safely authorize writes to a trusted shared cache. An independently
enforced host/network trust-isolation contract must precede any such exposure.
The one-pool public-PR setup does not support trusted shared writes today.
No production mount, filesystem source, bootstrap hook, network, image, or pool
contract is selected here. A custom VM image is not established as necessary;
host setup followed by explicit existing-container execution is a separate
orchestration option to review, not implemented by this change.

## Offline validation

Python workflow assertions run with the existing regression suite. Root-operation
integration tests require an explicitly selected, already-pulled image; otherwise
they are visibly skipped. They use network-disabled disposable containers, a
read-only source bind and private tmpfs fixtures under `$TMPDIR`. No host cache,
Docker socket, host users/groups, mounts or ownership are modified by the tests.
Filesystem-rejection/error cases inject tiny command fixtures; successful paths
exercise real account creation, directory initialization and builder writes.

Verified image:
`ghcr.io/azure/meta-iotedge-devcontainer@sha256:679fe794f4c9ec2fb01e44f541c0766ec37b67d6c8974a3703141108398ee5ea`

```bash
export TMPDIR=/home/jlian/.hermes/cache/scratch
export YOCTO_CACHE_TEST_IMAGE=ghcr.io/azure/meta-iotedge-devcontainer@sha256:679fe794f4c9ec2fb01e44f541c0766ec37b67d6c8974a3703141108398ee5ea
python3 -m unittest discover -s tests -v
node --test tests/*.cjs
bash -n scripts/prepare-yocto-cache.sh
git diff --check
```

These are local/offline checks, not BitBake, QEMU, cross-agent reuse, production
filesystem locking/performance, mount-readiness or CI acceptance evidence.
