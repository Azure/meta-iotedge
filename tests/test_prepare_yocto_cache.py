"""Root operations run only in an opt-in, offline disposable container.

Set YOCTO_CACHE_TEST_IMAGE to an already-pulled devcontainer image to exercise.
No Docker socket, host cache, or writable host directory is mounted in it.
"""
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get("YOCTO_CACHE_TEST_IMAGE")
SCRATCH = os.environ.get("TMPDIR")


@unittest.skipUnless(IMAGE, "set YOCTO_CACHE_TEST_IMAGE to an already-pulled image")
class CachePreparationTests(unittest.TestCase):
    def run_container(self, script):
        assert IMAGE is not None and SCRATCH, "set YOCTO_CACHE_TEST_IMAGE and TMPDIR"
        return subprocess.run(
            ["docker", "run", "--rm", "--pull=never", "--network", "none",
             "--hostname", "cache-test", "--add-host", "cache-test:127.0.0.1",
             "--user", "root", "--cap-drop=ALL", "--cap-add=CHOWN",
             "--cap-add=SETUID", "--cap-add=SETGID", "--cap-add=DAC_OVERRIDE",
             "--cap-add=FOWNER", "--cap-add=AUDIT_WRITE",
             "--tmpfs", f"{SCRATCH}:rw,exec,mode=1777",
             "-e", f"TMPDIR={SCRATCH}", "-v", f"{ROOT}:/source:ro",
             "--entrypoint", "/bin/bash", IMAGE, "-euc", script],
            text=True, capture_output=True, timeout=30,
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_prepares_local_cache_with_stable_builder_identity(self):
        self.assert_success(self.run_container('''
mkdir "$TMPDIR/cache"
bash /source/scripts/prepare-yocto-cache.sh "$TMPDIR/cache"
test "$(id -u builder):$(id -g builder)" = 1001:1001
for name in downloads sstate-cache; do
    test "$(stat -c %u:%g "$TMPDIR/cache/$name")" = 1001:1001
done
'''))

    def test_uid_collision_fails_before_account_or_cache_changes(self):
        self.assert_success(self.run_container('''
mkdir "$TMPDIR/cache"
useradd --uid 1001 --gid users --no-create-home intruder
if bash /source/scripts/prepare-yocto-cache.sh "$TMPDIR/cache"; then exit 1; fi
test -z "$(getent group builder || true)"
test ! -e "$TMPDIR/cache/downloads"
'''))

    def test_builder_name_collision_fails_before_group_creation(self):
        self.assert_success(self.run_container('''
mkdir "$TMPDIR/cache"
useradd --uid 1234 --gid users --no-create-home builder
if bash /source/scripts/prepare-yocto-cache.sh "$TMPDIR/cache"; then exit 1; fi
test -z "$(getent group builder || true)"
test ! -e "$TMPDIR/cache/downloads"
'''))

    def test_nonlocal_filesystem_is_rejected_before_any_cache_write(self):
        self.assert_success(self.run_container('''
mkdir "$TMPDIR/cache" "$TMPDIR/bin"
printf '#!/bin/sh\\necho nfs\\n' > "$TMPDIR/bin/stat"
chmod +x "$TMPDIR/bin/stat"
if PATH="$TMPDIR/bin:$PATH" bash /source/scripts/prepare-yocto-cache.sh "$TMPDIR/cache"; then exit 1; fi
test -z "$(find "$TMPDIR/cache" -mindepth 1 -print -quit)"
test -z "$(getent passwd builder || true)"
'''))

    def test_builder_write_probe_failure_stops_preparation(self):
        self.assert_success(self.run_container('''
mkdir "$TMPDIR/cache" "$TMPDIR/bin"
printf '#!/bin/sh\\nexit 73\\n' > "$TMPDIR/bin/sudo"
chmod +x "$TMPDIR/bin/sudo"
set +e
PATH="$TMPDIR/bin:$PATH" bash /source/scripts/prepare-yocto-cache.sh "$TMPDIR/cache"
result=$?
set -e
test "$result" -eq 73
'''))

    def test_symlinked_cache_directory_is_rejected_before_any_cache_write(self):
        self.assert_success(self.run_container('''
mkdir "$TMPDIR/cache" "$TMPDIR/elsewhere"
ln -s "$TMPDIR/elsewhere" "$TMPDIR/cache/sstate-cache"
if bash /source/scripts/prepare-yocto-cache.sh "$TMPDIR/cache"; then exit 1; fi
test ! -e "$TMPDIR/cache/downloads"
test "$(stat -c %u:%g "$TMPDIR/elsewhere")" = 0:0
test -z "$(getent passwd builder || true)"
'''))

    def test_symlinked_cache_root_with_trailing_slashes_is_rejected_before_changes(self):
        for suffix in ("/", "///"):
            with self.subTest(suffix=suffix):
                self.assert_success(self.run_container('''
mkdir "$TMPDIR/target"
printf keep > "$TMPDIR/target/keep"
ln -s "$TMPDIR/target" "$TMPDIR/cache"
before=$(find "$TMPDIR/target" -printf '%P:%u:%g:%m:%T@:%C@:%l\\n' | sort)
set +e
bash /source/scripts/prepare-yocto-cache.sh "$TMPDIR/cache"''' + suffix + '''
result=$?
set -e
if test "$(find "$TMPDIR/target" -printf '%P:%u:%g:%m:%T@:%C@:%l\\n' | sort)" != "$before"; then
    echo "Symlink target changed during cache preparation" >&2
    exit 1
fi
test "$(cat "$TMPDIR/target/keep")" = keep
test -z "$(getent passwd builder || true)"
test -z "$(getent group builder || true)"
test "$result" -ne 0
'''))

    def test_nonlocal_child_filesystem_is_rejected_before_any_cache_write(self):
        self.assert_success(self.run_container('''
mkdir -p "$TMPDIR/cache/sstate-cache" "$TMPDIR/bin"
printf '#!/bin/sh\\ncase "$*" in *sstate-cache*) echo nfs;; *) echo tmpfs;; esac\\n' > "$TMPDIR/bin/stat"
chmod +x "$TMPDIR/bin/stat"
if PATH="$TMPDIR/bin:$PATH" bash /source/scripts/prepare-yocto-cache.sh "$TMPDIR/cache"; then exit 1; fi
test ! -e "$TMPDIR/cache/downloads"
test "$(stat -c %u:%g "$TMPDIR/cache/sstate-cache")" = 0:0
test -z "$(getent passwd builder || true)"
'''))

    def test_existing_cache_contents_and_ownership_are_not_walked_or_changed(self):
        self.assert_success(self.run_container('''
mkdir -p "$TMPDIR/cache/downloads/nested" "$TMPDIR/cache/sstate-cache"
printf keep > "$TMPDIR/cache/downloads/nested/keep"
chmod 0600 "$TMPDIR/cache/downloads/nested/keep"
ln -s "$TMPDIR" "$TMPDIR/cache/downloads/nested/link"
before=$(stat -c '%u:%g:%a:%Y' "$TMPDIR/cache/downloads/nested/keep")
bash /source/scripts/prepare-yocto-cache.sh "$TMPDIR/cache"
test "$(stat -c '%u:%g:%a:%Y' "$TMPDIR/cache/downloads/nested/keep")" = "$before"
test "$(cat "$TMPDIR/cache/downloads/nested/keep")" = keep
test -z "$(find "$TMPDIR/cache" -name '.write-test.*' -print -quit)"
'''))

    def test_existing_1001_cache_contents_remain_read_write_as_builder(self):
        self.assert_success(self.run_container('''
for name in downloads sstate-cache; do
    mkdir -p "$TMPDIR/cache/$name/nested"
    printf keep > "$TMPDIR/cache/$name/nested/keep"
    chown 1001:1001 "$TMPDIR/cache/$name" "$TMPDIR/cache/$name/nested" "$TMPDIR/cache/$name/nested/keep"
    chmod 0750 "$TMPDIR/cache/$name/nested"
    chmod 0640 "$TMPDIR/cache/$name/nested/keep"
done
before=$(stat -c '%u:%g:%a' "$TMPDIR/cache/"*/nested/keep)
bash /source/scripts/prepare-yocto-cache.sh "$TMPDIR/cache"
test "$(stat -c '%u:%g:%a' "$TMPDIR/cache/"*/nested/keep)" = "$before"
for name in downloads sstate-cache; do
    sudo -u builder -- bash -euc '
        test "$(cat "$1")" = keep
        printf appended >> "$1"
        test "$(cat "$1")" = keepappended
    ' bash "$TMPDIR/cache/$name/nested/keep"
done
test "$(stat -c '%u:%g:%a' "$TMPDIR/cache/"*/nested/keep)" = "$before"
'''))

    def test_gid_collision_leaves_cache_and_user_untouched(self):
        self.assert_success(self.run_container('''
mkdir "$TMPDIR/cache"
groupadd --gid 1001 intruder
if bash /source/scripts/prepare-yocto-cache.sh "$TMPDIR/cache"; then exit 1; fi
test -z "$(getent passwd builder || true)"
test -z "$(find "$TMPDIR/cache" -mindepth 1 -print -quit)"
'''))

    def test_missing_cache_root_is_not_created(self):
        self.assert_success(self.run_container('''
if bash /source/scripts/prepare-yocto-cache.sh "$TMPDIR/missing"; then exit 1; fi
test ! -e "$TMPDIR/missing"
test -z "$(getent passwd builder || true)"
'''))


class CacheWorkflowTests(unittest.TestCase):
    def test_workflow_uses_local_preparation_instead_of_recursive_cache_chown(self):
        workflow = (ROOT / ".github/workflows/ci-build.yml").read_text()
        self.assertIn("run: bash ./scripts/prepare-yocto-cache.sh", workflow)
        self.assertNotIn("chown -R builder:builder /workspaces/yocto-cache", workflow)
        self.assertIn("'/var/cache/yocto'", workflow)


if __name__ == "__main__":
    unittest.main()
