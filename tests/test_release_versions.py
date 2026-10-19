"""Offline regressions for the actual updater and release planning helpers."""
import importlib
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
versions = importlib.import_module("release_versions")
FIXTURE = ROOT / "tests/fixtures/release_versions_products.json"


class ReleaseVersionsTests(unittest.TestCase):
    def resolver(self, release, data=None):
        source = (ROOT / "scripts/update-recipes.sh").read_text()
        section = source[source.index("# Resolve versions from"):source.index("# Resolve SHAs from")]
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(json.dumps(data) if data is not None else FIXTURE.read_text())
            curl = Path(tmp) / "curl"
            curl.write_text('#!/bin/sh\ncat "$TEST_MANIFEST"\n')
            curl.chmod(0o755)
            return subprocess.run(["bash", "-c", "set -euo pipefail\n" + section],
                                  env={**os.environ, "PATH": tmp + ":" + os.environ["PATH"],
                                       "TEST_MANIFEST": str(manifest), "ROOT_DIR": str(ROOT),
                                       "IOTEDGE_VERSION": release, "TEMPLATE": "scarthgap"},
                                  text=True, capture_output=True)

    def test_exact_second_product_not_first_lts_product(self):
        result = self.resolver("1.5.45")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IoT Edge daemon version: 1.5.21", result.stdout)
        self.assertIn("IIS version: 1.5.6", result.stdout)

    def test_conflicting_exact_products_fail_instead_of_preferring_lts(self):
        data = json.loads(FIXTURE.read_text())
        duplicate = json.loads(json.dumps(data["channels"][0]["products"][1]))
        duplicate["components"][0]["version"] = "1.5.22"
        data["channels"][1]["products"].append(duplicate)
        result = self.resolver("1.5.45", data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Conflicting", result.stderr)

    def test_malformed_component_versions_fail_closed(self):
        data = json.loads(FIXTURE.read_text())
        data["channels"][0]["products"][1]["components"][0]["version"] = "1.5.21;bad"
        result = self.resolver("1.5.45", data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid version", result.stderr)

    def test_conflicting_duplicate_components_fail(self):
        data = json.loads(FIXTURE.read_text())
        data["channels"][0]["products"][1]["components"].append(
            {"name": "aziot-edge", "version": "1.5.22"})
        result = self.resolver("1.5.45", data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Conflicting", result.stderr)

    def test_checked_in_templates_select_available_exact_recipes(self):
        for path in sorted((ROOT / "conf/templates").glob("*/local.conf.sample")):
            for package, version in re.findall(r'^PREFERRED_VERSION_([\w-]+) = "([^"]+)"', path.read_text(), re.M):
                with self.subTest(template=path.parent.name, package=package):
                    self.assertTrue((ROOT / "recipes-core" / package / f"{package}_{version}.bb").is_file(),
                                    f"{path.parent.name} selects missing {package} {version}")

    def test_exact_pair_updates_both_16_templates_only_and_is_idempotent(self):
        self.assertTrue(callable(getattr(versions, "update_template_versions", None)),
                        "Missing automatic template selection repair")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "conf", root / "conf")
            old = {p: p.read_bytes() for p in (root / "conf/templates").glob("*/local.conf.sample")}
            versions.update_template_versions(root, "wrynose", "1.6.4", "1.6.0")
            for path, content in old.items():
                if path.parent.name in ("wrynose", "scarthgap-1.6"):
                    self.assertIn('PREFERRED_VERSION_iotedge = "1.6.4"', path.read_text())
                    self.assertIn('PREFERRED_VERSION_aziotd = "1.6.0"', path.read_text())
                else:
                    self.assertEqual(path.read_bytes(), content)
            first = {p: p.read_bytes() for p in old}
            versions.update_template_versions(root, "scarthgap-1.6", "1.6.4", "1.6.0")
            self.assertEqual(first, {p: p.read_bytes() for p in old})

    def generator_fixture(self, root):
        """Tiny real local git source; only transport is substituted, no network/build."""
        shutil.copytree(ROOT / "scripts", root / "scripts")
        shutil.copytree(ROOT / "conf", root / "conf")
        source = root / "source"
        (source / "edgelet").mkdir(parents=True)
        lock = '[[package]]\nname = "fixture"\nversion = "1.0.0"\nsource = "registry+https://github.com/rust-lang/crates.io-index"\nchecksum = "' + 'a' * 64 + '"\n'
        (source / "edgelet/Cargo.lock").write_text(lock)
        (source / "Cargo.lock").write_text(lock)
        (source / "LICENSE").write_text("fixture license\n")
        (source / "THIRDPARTYNOTICES").write_text("fixture notices\n")
        (source / "compat.txt").write_text("before\n")
        def git(*args):
            return subprocess.check_output(["git", "-C", str(source), *args], text=True, stderr=subprocess.DEVNULL).strip()
        git("init")
        git("add", ".")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
        revision = git("rev-parse", "HEAD")
        packages = ("iotedge", "aziot-edged", "aziotd", "aziotctl", "aziot-keys")
        for package in packages:
            directory = root / "recipes-core" / package
            directory.mkdir(parents=True)
            for version in ("1.5.21", "1.6.0"):
                (directory / f"{package}_{version}.bb").write_text("fixture old recipe\n")
                (directory / f"{package}-{version}.inc").write_text(f'export VERSION = "{version}"\nIOTEDGE_RELEASE = "{version}"\n')
            patch_dir = directory / f"{package}-1.6.0"
            patch_dir.mkdir()
            (patch_dir / "0001-compat.patch").write_text('diff --git a/compat.txt b/compat.txt\n--- a/compat.txt\n+++ b/compat.txt\n@@ -1 +1 @@\n-before\n+after\n')
        bin_dir = root / "bin"
        bin_dir.mkdir()
        real_git = shutil.which("git")
        wrapper = bin_dir / "git"
        wrapper.write_text(f'#!/bin/bash\nif [[ "$1" == ls-remote ]]; then printf "%s\\trefs/tags/fixture\\n" "{revision}"; elif [[ "$1" == clone ]]; then exec "{real_git}" clone "{source}" "$3"; else exec "{real_git}" "$@"; fi\n')
        wrapper.chmod(0o755)
        curl = bin_dir / "curl"
        curl.write_text(f'#!/bin/sh\ncat "{FIXTURE}"\n')
        curl.chmod(0o755)
        return {**os.environ, "PATH": str(bin_dir) + ":" + os.environ["PATH"]}

    def run_generator(self, root, env, *extra):
        return subprocess.run(["bash", str(root / "scripts/update-recipes.sh"),
                               "--iotedge-version", "1.6.4", "--template", "wrynose",
                               "--skip-validate", "--workdir", str(root / "work"), *extra],
                              env=env, text=True, capture_output=True)

    def test_generator_advances_exact_selection_from_resolved_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.generator_fixture(root)
            result = self.run_generator(root, env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name in ("wrynose", "scarthgap-1.6"):
                self.assertIn('PREFERRED_VERSION_iotedge = "1.6.4"',
                              (root / f"conf/templates/{name}/local.conf.sample").read_text())

    def test_generator_preserves_shared_files_fallback_without_version_copies(self):
        for clean in ((), ("--clean",)):
            with self.subTest(clean=bool(clean)), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                env = self.generator_fixture(root)
                packages = {"iotedge": "1.5.21", "aziot-edged": "1.5.21",
                            "aziotd": "1.5.6", "aziotctl": "1.5.6", "aziot-keys": "1.5.6"}
                shared = {}
                for package in packages:
                    directory = root / "recipes-core" / package
                    (directory / f"{package}-1.6.0").rename(directory / "files")
                    patch = directory / "files/0001-compat.patch"
                    shared[patch] = patch.read_bytes()
                first = None
                for _ in range(2):
                    result = self.run_generator(root, env, "--iotedge-version", "1.5.45",
                                                "--template", "scarthgap", *clean)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual({p: p.read_bytes() for p in shared}, shared)
                    self.assertEqual(
                        {package: (root / f"recipes-core/{package}/{package}-{version}").exists()
                         for package, version in packages.items()},
                        dict.fromkeys(packages, False),
                        "Shared files/ patches are already in BitBake FILESPATH")
                    for package in ("iotedge", "aziot-edged"):
                        inc = root / f"recipes-core/{package}/{package}-{packages[package]}.inc"
                        self.assertIn('SRC_URI += "file://0001-compat.patch"', inc.read_text())
                    tree = {p.relative_to(root): p.read_bytes() for folder in ("recipes-core", "conf")
                            for p in (root / folder).rglob("*") if p.is_file()}
                    if first is None:
                        first = tree
                    else:
                        self.assertEqual(first, tree)

    def test_generator_materializes_carried_patches_with_scoped_idempotent_clean(self):
        for clean in ((), ("--clean",)):
            with self.subTest(clean=bool(clean)), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                env = self.generator_fixture(root)
                other_line = {p: p.read_bytes() for p in (root / "recipes-core").glob("*/*1.5*") if p.is_file()}
                first = None
                for _ in range(2):
                    result = self.run_generator(root, env, *clean)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    for package in ("iotedge", "aziot-edged"):
                        target = root / f"recipes-core/{package}/{package}-1.6.4/0001-compat.patch"
                        self.assertTrue(target.is_file(), f"Missing BitBake-searchable patch: {target}")
                        original = root / f"recipes-core/{package}/{package}-1.6.0/0001-compat.patch"
                        self.assertEqual(target.read_bytes(), original.read_bytes())
                        applied = subprocess.run(["git", "-C", str(root / "source"), "apply", "--check", str(target)], capture_output=True, text=True)
                        self.assertEqual(applied.returncode, 0, applied.stderr)
                    self.assertEqual(other_line, {p: p.read_bytes() for p in other_line})
                    tree = {p.relative_to(root): p.read_bytes() for folder in ("recipes-core", "conf")
                            for p in (root / folder).rglob("*") if p.is_file()}
                    if _ == 0:
                        first = tree
                    else:
                        self.assertEqual(first, tree)

    def detector(self, data=None, mode="--plans-json"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "scripts", root / "scripts")
            shutil.copytree(ROOT / "recipes-core", root / "recipes-core")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(data) if data is not None else FIXTURE.read_text())
            binary = root / "curl"
            binary.write_text(f'#!/bin/sh\ncat "{manifest}"\n')
            binary.chmod(0o755)
            return subprocess.run(["bash", str(root / "scripts/check-upstream.sh"), mode],
                                  env={**os.environ, "PATH": str(root) + ":" + os.environ["PATH"]},
                                  text=True, capture_output=True)

    def test_detector_enumerates_both_lts_plans_and_preserves_docker_only(self):
        result = self.detector()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.lstrip().startswith("["), "Missing --plans-json list interface")
        plans = json.loads(result.stdout)
        self.assertEqual([p["line"] for p in plans], ["1.6", "1.5"])
        self.assertEqual(plans[0]["daemon_version"], "1.6.4")
        self.assertEqual(plans[0]["iis_version"], "1.6.0")
        self.assertEqual(plans[0]["template"], "wrynose")
        self.assertTrue(plans[0]["needs_update"])
        self.assertEqual(plans[1]["release_version"], "1.5.45")
        self.assertEqual(plans[1]["update_type"], "docker-only")
        self.assertFalse(plans[1]["needs_update"])

    def test_detector_treats_iis_only_source_update_as_significant(self):
        data = json.loads(FIXTURE.read_text())
        data["channels"][0]["products"][1]["components"][1]["version"] = "1.5.7"
        result = self.detector(data)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)[1]
        self.assertEqual(plan["update_type"], "significant")
        self.assertTrue(plan["needs_update"])

    def test_generator_rejects_cross_line_template_before_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.generator_fixture(root)
            before = {p: p.read_bytes() for p in (root / "recipes-core").rglob("*") if p.is_file()}
            result = self.run_generator(root, env, "--template", "scarthgap", "--clean")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("template", result.stderr.lower())
            self.assertEqual(before, {p: p.read_bytes() for p in (root / "recipes-core").rglob("*") if p.is_file()})

    def test_cross_line_component_pair_is_rejected(self):
        data = json.loads(FIXTURE.read_text())
        data["channels"][0]["products"][1]["components"][1]["version"] = "1.6.0"
        result = self.resolver("1.5.45", data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("line", result.stderr.lower())

    def test_detector_rejects_component_downgrade_in_newer_release(self):
        data = json.loads(FIXTURE.read_text())
        data["channels"][0]["products"][1]["components"][0]["version"] = "1.5.20"
        result = self.detector(data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("downgrade", result.stderr.lower())

    def test_generator_materializes_iis_carried_patches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.generator_fixture(root)
            data = json.loads(FIXTURE.read_text())
            data["channels"][0]["products"][0]["components"][1]["version"] = "1.6.1"
            manifest = root / "iis-manifest.json"
            manifest.write_text(json.dumps(data))
            (root / "bin/curl").write_text(f'#!/bin/sh\ncat "{manifest}"\n')
            result = self.run_generator(root, env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for package in ("aziotd", "aziotctl", "aziot-keys"):
                target = root / f"recipes-core/{package}/{package}-1.6.1/0001-compat.patch"
                self.assertTrue(target.is_file(), f"Missing carried IIS patch {target}")

    def test_detector_repairs_iis_mismatch_even_when_release_already_tracked(self):
        data = json.loads(FIXTURE.read_text())
        data["channels"][0]["products"][1]["components"][1]["version"] = "1.5.7"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "recipes-core", root / "recipes-core")
            inc = root / "recipes-core/iotedge/iotedge-1.5.21.inc"
            inc.write_text(inc.read_text().replace('IOTEDGE_RELEASE = "1.5.35"', 'IOTEDGE_RELEASE = "1.5.45"'))
            plan = versions.release_plans(data, root)[1]
            self.assertEqual(plan["current_release"], "1.5.45")
            self.assertEqual(plan["update_type"], "significant")

    def test_daemon_tag_difference_does_not_claim_docker_only(self):
        result = self.resolver("1.5.45")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Docker-image-only", result.stdout)

    def test_resolution_coverage_unknown_missing_and_repeated_channels(self):
        data = json.loads(FIXTURE.read_text())
        with self.assertRaisesRegex(ValueError, "Unknown release"):
            versions.resolve_release(data, "1.5.999")
        self.assertEqual(versions.resolve_release(data, "1.6.0"), ("1.6.0", "1.6.0"))
        data["channels"][1]["products"].append(data["channels"][0]["products"][1])
        self.assertEqual(versions.resolve_release(data, "1.5.45"), ("1.5.21", "1.5.6"))
        data["channels"][0]["products"][1]["components"].pop()
        with self.assertRaises((ValueError, KeyError)):
            versions.resolve_release(data, "1.5.45")

    def test_legacy_output_modes_keep_original_keys(self):
        json_result = self.detector(mode="--json")
        self.assertEqual(json_result.returncode, 0, json_result.stderr)
        plan = json.loads(json_result.stdout)
        keys = ("release_version", "daemon_version", "current_recipe", "current_release",
                "template", "needs_update", "is_significant", "update_type")
        self.assertTrue(set(keys).issubset(plan))
        values = self.detector(mode="")
        self.assertEqual(values.returncode, 0, values.stderr)
        parsed = dict(line.split("=", 1) for line in values.stdout.splitlines())
        for key in keys:
            self.assertEqual(parsed[key], str(plan[key]).lower() if isinstance(plan[key], bool) else plan[key])

    def test_semver_prerelease_ordering_and_invalid_versions(self):
        ordered = ["1.6.0-alpha.1", "1.6.0-beta.1", "1.6.0-rc.1", "1.6.0-rc.2", "1.6.0-rc.10", "1.6.0", "1.6.1"]
        self.assertEqual(sorted(reversed(ordered), key=versions.version_key), ordered)
        for invalid in ("", "1.6", "1.6.0oops", "v1.6.0", "01.6.0", "1.6.0-rc.01"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                versions.version_key(invalid)


if __name__ == "__main__":
    unittest.main()
