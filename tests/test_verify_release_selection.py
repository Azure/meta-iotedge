"""Offline regression coverage for the release selection and CI gates."""
import importlib.util
import os
import re
import textwrap
import shutil
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify-release-selection.py"


def verifier():
    spec = importlib.util.spec_from_file_location("verify_release_selection", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.release("1.6.0", "1.6.0", "1.6.0", "edge0", "iis0")
        self.release("1.5.35", "1.5.21", "1.5.6", "edge5", "iis5")

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def release(self, release, edge, iis, edge_ref, iis_ref):
        for package in ("iotedge", "aziot-edged", "aziotd", "aziotctl", "aziot-keys"):
            is_edge = package in ("iotedge", "aziot-edged")
            version = edge if is_edge else iis
            self.put(f"recipes-core/{package}/{package}_{version}.bb", f'SRCREV = "{edge_ref if is_edge else iis_ref}"\n')
            text = f'export VERSION = "{version}"\n'
            if is_edge:
                text += f'IOTEDGE_RELEASE = "{release}"\nIIS_SRCREV = "{iis_ref}"\n'
            self.put(f"recipes-core/{package}/{package}-{version}.inc", text)
        subprocess.run(["git", "-C", str(self.root), "add", "recipes-core"], check=True)

    def test_newest_release_metadata_overrides_stale_template_and_available_recipe(self):
        self.release("1.6.4", "1.6.4", "1.6.0", "edge4", "iis0")
        self.put("conf/templates/wrynose/local.conf.sample", 'PREFERRED_VERSION_iotedge = "1.6.0"\n')
        expected = verifier().expected_selection(self.root, "wrynose")
        self.assertEqual(expected["release"], "1.6.4")
        self.assertEqual(expected["packages"]["iotedge"]["PV"], "1.6.4")
        self.assertEqual(expected["packages"]["aziotd"]["PV"], "1.6.0")
        self.assertEqual(verifier().expected_selection(self.root, "scarthgap")["release"], "1.5.35")

    def test_release_tag_must_match_product_and_template_not_only_artifact_name(self):
        module = verifier()
        expected = module.expected_selection(self.root, "wrynose")
        for valid in ("1.6.0", "1.6.0-1"):
            module.verify_release_tag(expected, valid)
        for invalid in ("1.6.4", "1.6.0-scarthgap", "1.6.0;echo bad"):
            with self.subTest(tag=invalid), self.assertRaises(ValueError):
                module.verify_release_tag(expected, invalid)
        expected["template"] = "scarthgap-1.6"
        module.verify_release_tag(expected, "1.6.0-scarthgap")
        module.verify_release_tag(expected, "1.6.0-scarthgap.2")
        with self.assertRaises(ValueError):
            module.verify_release_tag(expected, "1.6.0")

    def test_release_tag_drives_template_when_checkout_ref_is_immutable_sha(self):
        workflow = (ROOT / ".github/workflows/ci-build.yml").read_text()
        self.assertIn("inputs.release_tag || inputs.ref || github.base_ref", workflow)
        self.assertIn("inputs.release_tag || inputs.ref || github.ref_name", workflow)
        self.assertIn("RELEASE_TAG: ${{ inputs.release_tag", workflow)

    def environments(self, expected):
        result = {}
        for package, values in expected["packages"].items():
            values = {**values, "PN": package, "PKGV": values["PV"]}
            # Preserve the real fetcher scheme: separate IIS providers use
            # gitsm://, while the Edge providers use git://.
            recipe = ROOT / f"recipes-core/{package}/{package}_1.6.0.bb"
            source = re.search(r'SRC_URI\s*\+=\s*"([^"\n]+)"', recipe.read_text())
            self.assertIsNotNone(source, f"Missing upstream URI in {recipe}")
            assert source is not None
            values["SRC_URI"] = source[1]
            if package in ("iotedge", "aziot-edged"):
                values["SRC_URI"] += " git://github.com/Azure/iot-identity-service;protocol=https;name=aziot-key-common;subpath=key/aziot-key-common"
                values["SRCREV_aziot-key-common"] = values["IIS_SRCREV"]
            result[package] = values
        return result

    def test_real_provider_sources_accept_git_and_gitsm_but_reject_other_origins(self):
        module = verifier()
        expected = module.expected_selection(self.root, "wrynose")
        environments = self.environments(expected)
        self.assertTrue(environments["aziotd"]["SRC_URI"].startswith("gitsm://"))
        self.assertEqual(set(module.verify_environments(expected, environments)), set(module.PACKAGES))
        for package in module.PACKAGES:
            for scheme in ("git", "gitsm"):
                with self.subTest(package=package, scheme=scheme):
                    environments = self.environments(expected)
                    environments[package]["SRC_URI"] = re.sub(
                        r"^(?:git|gitsm)://", scheme + "://", environments[package]["SRC_URI"]
                    )
                    module.verify_environments(expected, environments)
            for source in ("https://github.com/Azure/iot-identity-service.git",
                           "gitsm://github.com.evil/Azure/iot-identity-service.git",
                           "gitsm://github.com/Azure/iot-identity-service.git/extra",
                           "gitsm://example.com/Azure/iot-identity-service.git",
                           "gitsm://github.com/Azure/wrong.git"):
                with self.subTest(package=package, source=source):
                    environments = self.environments(expected)
                    environments[package]["SRC_URI"] = source
                    with self.assertRaisesRegex(ValueError, "missing expected upstream"):
                        module.verify_environments(expected, environments)

    def test_actual_provider_fallback_is_rejected_even_when_recipe_available(self):
        module = verifier()
        self.release("1.6.4", "1.6.4", "1.6.0", "edge4", "iis0")
        expected = module.expected_selection(self.root, "wrynose")
        environments = self.environments(expected)
        environments["iotedge"]["PV"] = "1.6.0"
        with self.assertRaisesRegex(ValueError, "iotedge.*PV.*1.6.4.*1.6.0"):
            module.verify_environments(expected, environments)
        environments["iotedge"]["PV"] = "1.6.4"
        self.assertEqual(module.verify_environments(expected, environments)["iotedge"], "1.6.4")

    def test_wrong_source_named_iis_ref_or_rpm_version_cannot_hide_behind_correct_pv(self):
        module = verifier()
        expected = module.expected_selection(self.root, "wrynose")
        for variable, wrong in (("SRCREV", "wrong"), ("IIS_SRCREV", "wrong"),
                                ("SRCREV_aziot-key-common", "wrong"),
                                ("PKGV", "1.5.0"), ("SRC_URI", "git://example.com/wrong.git")):
            with self.subTest(variable=variable):
                environments = self.environments(expected)
                environments["iotedge"][variable] = wrong
                with self.assertRaises(ValueError):
                    module.verify_environments(expected, environments)
        environments = self.environments(expected)
        environments["iotedge"]["SRCREV_aziot-key-common"] = "iis0"
        self.assertEqual(module.verify_environments(expected, environments)["iotedge"], "1.6.0")

    def test_installed_cli_and_all_five_rpm_versions_are_mandatory(self):
        module = verifier()
        expected = module.expected_selection(self.root, "wrynose")
        environments = self.environments(expected)
        versions = module.verify_environments(expected, environments)
        inventory = "".join(f"{p} {v}\\n" for p, v in versions.items())
        module.verify_installed(expected, versions, "iotedge 1.6.0\n", inventory.replace("\\n", "\n"))
        for cli, packages in (("iotedge 1.5.21", inventory),
                              ("iotedge 1.6.0", inventory.replace("aziotd 1.6.0", "aziotd 1.5.6")),
                              ("iotedge 1.6.0", inventory.replace("aziotctl 1.6.0\\n", ""))):
            with self.subTest(cli=cli, inventory=packages):
                with self.assertRaises(ValueError):
                    module.verify_installed(expected, versions, cli, packages.replace("\\n", "\n"))

    def test_cli_queries_real_bitbake_e_for_every_provider_and_fails_closed(self):
        module = verifier()
        expected = module.expected_selection(self.root, "wrynose")
        environments = self.environments(expected)
        for package, values in environments.items():
            self.put(f"env/{package}", "".join(f'{k}="{v}"\n' for k, v in values.items()))
        self.put("bin/bitbake", '#!/bin/sh\n[ "$1" = "-e" ] || exit 9\nprintf "%s\\n" "$2" >> "$FIXTURE/calls"\ncat "$FIXTURE/env/$2"\n')
        (self.root / "bin/bitbake").chmod(0o755)
        env = {**os.environ, "PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"], "FIXTURE": str(self.root)}
        command = [sys.executable, str(SCRIPT), "--root", str(self.root), "--template", "wrynose"]
        result = subprocess.run(command, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "calls").read_text().splitlines(), list(module.PACKAGES))
        self.assertIn('"release": "1.6.0"', result.stdout)
        self.put("env/aziotctl", 'PN="aziotctl"\nPV="1.5.6"\n')
        result = subprocess.run(command, env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("aziotctl", result.stderr)
        (self.root / "env/aziotctl").unlink()
        self.assertNotEqual(subprocess.run(command, env=env, capture_output=True).returncode, 0)

    def test_build_wrapper_blocks_wrong_provider_before_expensive_build(self):
        module = verifier()
        expected = module.expected_selection(self.root, "wrynose")
        environments = self.environments(expected)
        environments["iotedge"]["PV"] = "1.5.21"
        for package, values in environments.items():
            self.put(f"env/{package}", "".join(f'{k}="{v}"\n' for k, v in values.items()))
        self.put("scripts/placeholder", "")
        for script in ("bitbake.sh", "verify-release-selection.py"):
            shutil.copy(ROOT / "scripts" / script, self.root / "scripts" / script)
        self.put("poky/oe-init-build-env", 'mkdir -p "$FIXTURE/build"\ncd "$FIXTURE/build"\n')
        self.put("bin/bitbake", '#!/bin/sh\ncase "$1" in\n-p) exit 0;;\n-e) cat "$FIXTURE/env/$2";;\n*) touch "$FIXTURE/built";;\nesac\n')
        (self.root / "bin/bitbake").chmod(0o755)
        env = {**os.environ, "PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"], "FIXTURE": str(self.root), "TEMPLATECONF": "meta-iotedge/conf/templates/wrynose"}
        result = subprocess.run(["bash", str(self.root / "scripts/bitbake.sh"), "iotedge"], env=env, cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.root / "built").exists())
        self.assertIn("PV expected", result.stderr)

    def test_qemu_image_retains_rpm_database_for_mandatory_inventory(self):
        recipe = (ROOT / "recipes-core/images/iotedge-qemu-image.bb").read_text()
        features = " ".join(re.findall(r'^IMAGE_FEATURES\s*\+?=\s*"([^"]*)"', recipe, re.M)).split()
        self.assertIn("package-management", features,
                      "Without package-management rootfs postprocessing removes the RPM database")
        self.assertIn("ssh-server-dropbear", features)
        values = verifier().assignments(recipe)
        self.assertEqual(values["IMAGE_FSTYPES"], "ext4")
        self.assertEqual(values["QB_DEFAULT_FSTYPE"], "ext4")
        for template in verifier().TEMPLATE_LINES:
            config = (ROOT / f"conf/templates/{template}/local.conf.sample").read_text()
            self.assertRegex(config, r'PACKAGE_CLASSES\s*[?]?=\s*"package_rpm"')
            self.assertNotRegex(config, r'IMAGE_FEATURES.*package-management',
                                "Package management is for the validation image, not a template-wide change")

    def test_qemu_mock_diagnostics_do_not_excuse_wrong_installed_versions(self):
        module = verifier()
        expected = module.expected_selection(self.root, "wrynose")
        for package, values in self.environments(expected).items():
            self.put(f"env/{package}", "".join(f'{k}="{v}"\n' for k, v in values.items()))
        self.put("scripts/placeholder", "")
        for script in ("validate-qemu.sh", "verify-release-selection.py"):
            shutil.copy(ROOT / "scripts" / script, self.root / "scripts" / script)
        self.put("build/tmp/deploy/images/qemux86-64/iotedge-qemu-image-qemux86-64.rootfs.ext4", "fixture")
        self.put("poky/oe-init-build-env", 'cd "$FIXTURE/build"\n')
        commands = {
            "bitbake": 'cat "$FIXTURE/env/$2"',
            "runqemu": 'exec sleep 60',
            "sshpass": '''case "$*" in
*"iotedge --version"*) cat "$FIXTURE/cli";;
*"rpm -q "*) cat "$FIXTURE/rpms";;
*"iotedge check"*) exit 1;;
*"sh -s"*) cat >/dev/null;;
*) exit 0;;
esac''',
        }
        for name, body in commands.items():
            self.put(f"bin/{name}", "#!/bin/sh\n" + body + "\n")
            (self.root / "bin" / name).chmod(0o755)
        self.put("cli", "iotedge 1.5.21\n")
        self.put("rpms", "".join(f"{p} 1.6.0\n" for p in module.PACKAGES))
        env = {**os.environ, "PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"], "FIXTURE": str(self.root)}
        def run():
            return subprocess.run(["bash", str(self.root / "scripts/validate-qemu.sh"), "wrynose"], cwd=self.root, env=env, capture_output=True, text=True, timeout=15)
        result = run()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.put("cli", "iotedge 1.6.0\n")
        result = run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.put("rpms", (self.root / "rpms").read_text().replace("aziotd 1.6.0", "aziotd 1.5.6"))
        result = run()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Installed aziotd", result.stderr)

    def test_consistency_regenerates_every_maintained_template_with_its_release(self):
        self.put("scripts/update-recipes.sh", '#!/bin/sh\nprintf "%s\\n" "$*" >> "$FIXTURE/regenerated"\n')
        (self.root / "scripts/update-recipes.sh").chmod(0o755)
        result = subprocess.run([sys.executable, str(ROOT / "scripts/check-recipe-consistency.py"), "--root", str(self.root)], env={**os.environ, "FIXTURE": str(self.root)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = (self.root / "regenerated").read_text().splitlines()
        self.assertEqual(calls, [
            "--iotedge-version 1.5.35 --template kirkstone --skip-validate",
            "--iotedge-version 1.5.35 --template scarthgap --skip-validate",
            "--iotedge-version 1.6.0 --template wrynose --skip-validate",
            "--iotedge-version 1.6.0 --template scarthgap-1.6 --skip-validate",
        ])

    def test_consistency_fails_on_tracked_and_untracked_recipe_or_template_drift(self):
        script = ROOT / "scripts/check-recipe-consistency.py"
        for path in ("recipes-core/iotedge/iotedge-1.6.0.inc", "recipes-core/aziotd/new.inc", "conf/templates/wrynose/new.sample"):
            with self.subTest(path=path):
                self.put("scripts/update-recipes.sh", f'#!/bin/sh\nmkdir -p "$(dirname "{path}")"\nprintf "# drift\\n" >> "{path}"\n')
                (self.root / "scripts/update-recipes.sh").chmod(0o755)
                result = subprocess.run([sys.executable, str(script), "--root", str(self.root)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(path, result.stderr)
                if path.endswith("iotedge-1.6.0.inc"):
                    subprocess.run(["git", "-C", str(self.root), "restore", path], check=True)
                else:
                    (self.root / path).unlink()

    def test_reusable_workflow_never_skips_docs_only_release_commit(self):
        workflow = (ROOT / ".github/workflows/ci-build.yml").read_text()
        step = workflow.split("      - name: Check if only docs changed\n", 1)[1].split("\n      - name:", 1)[0]
        shell = textwrap.dedent(step.split("        run: |\n", 1)[1])
        shell = shell.replace("${{ github.event_name }}", "workflow_call")
        shell = re.sub(r"\$\{\{.*?\}\}", "main", shell)
        self.put("bin/git", '#!/bin/sh\nprintf "README.md\\n"\n')
        (self.root / "bin/git").chmod(0o755)
        output = self.root / "outputs"
        result = subprocess.run(["bash", "-e", "-c", shell], env={**os.environ, "PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"], "GITHUB_OUTPUT": str(output)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("docs_only=false", output.read_text())

    def test_fast_regressions_are_required_even_for_docs_only_changes(self):
        workflow = (ROOT / ".github/workflows/ci-build.yml").read_text()
        self.assertIn("  regression-tests:\n", workflow)
        job = workflow.split("  regression-tests:\n", 1)[1].split("\n  check-recipes:", 1)[0]
        self.assertIn("python3 -m unittest discover -s tests", job)
        self.assertIn("node --test tests/*.cjs", job)
        status = workflow.split("  status-check:\n", 1)[1]
        self.assertIn("regression-tests", status.split("    steps:", 1)[0])
        shell = textwrap.dedent(status.split("        run: |\n", 1)[1])
        shell = shell.replace("${{ needs.regression-tests.result }}", "failure")
        shell = shell.replace("${{ needs.check-changes.outputs.docs_only }}", "true")
        shell = re.sub(r"\$\{\{.*?\}\}", "success", shell)
        result = subprocess.run(["bash", "-e", "-c", shell], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_ci_uses_per_line_consistency_entrypoint(self):
        workflow = (ROOT / ".github/workflows/ci-build.yml").read_text()
        job = workflow.split("  check-recipes:\n", 1)[1].split("\n  build:\n", 1)[0]
        self.assertIn("python3 scripts/check-recipe-consistency.py", job)
        self.assertNotIn("head -1", job)

    def build_job_shell(self):
        workflow = (ROOT / ".github/workflows/ci-build.yml").read_text()
        job = workflow.split("\n  build:\n", 1)[1].split("\n  status-check:\n", 1)[0]
        # Container run steps default to sh, not the hosted runner's bash.
        defaults = re.search(r'^    defaults:\n      run:\n        shell: ([^\n]+)', job, re.M)
        shell = defaults[1] if defaults else "sh"
        return [shell, "--noprofile", "--norc", "-e", "-o", "pipefail", "-c"] if shell == "bash" else [shell, "-e", "-c"]

    def test_container_build_uses_declared_shell_for_both_skip_qemu_branches(self):
        workflow = (ROOT / ".github/workflows/ci-build.yml").read_text()
        job = workflow.split("\n  build:\n", 1)[1].split("\n  status-check:\n", 1)[0]
        step = job.split("      - name: Build\n", 1)[1].split("\n      - name:", 1)[0]
        shell = textwrap.dedent(step.split("        run: |\n", 1)[1])
        self.put("bin/sudo", '#!/bin/sh\nprintf "%s\\n" "$*" >> "$FIXTURE/build-calls"\n')
        (self.root / "bin/sudo").chmod(0o755)
        for skip in ("true", "false"):
            with self.subTest(skip_qemu=skip):
                result = subprocess.run(
                    self.build_job_shell() + [shell.replace("${{ inputs.skip_qemu }}", skip)],
                    env={**os.environ, "PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"],
                         "FIXTURE": str(self.root), "TEMPLATE": "wrynose"},
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                call = (self.root / "build-calls").read_text().splitlines()[-1]
                self.assertEqual(call, "-E -u builder ./scripts/build.sh wrynose" +
                                 (" --with-qemu" if skip == "false" else ""), result.stderr)
        self.assertEqual(self.build_job_shell()[0], "bash")

    def test_ci_collector_requires_all_runtime_rpms_and_both_qemu_assets(self):
        workflow = (ROOT / ".github/workflows/ci-build.yml").read_text()
        self.assertNotIn("if-no-files-found: warn", workflow)
        step = workflow.split("      - name: Collect IoT Edge RPM packages\n", 1)[1].split("\n      - name:", 1)[0]
        shell = textwrap.dedent(step.split("        run: |\n", 1)[1])
        self.assertIn("scripts/collect-release-artifacts.py", shell)
        shell = shell.replace("${{ inputs.skip_qemu }}", "false").replace("${{ matrix.template }}", "wrynose")
        self.put("scripts/placeholder", "")
        shutil.copy(ROOT / "scripts/collect-release-artifacts.py", self.root / "scripts/collect-release-artifacts.py")
        for package in verifier().PACKAGES:
            self.put(f"build/tmp/deploy/rpm/core2_64/{package}-1.6.0-r0.core2_64.rpm", "rpm fixture")
        image_dir = "build/tmp/deploy/images/qemux86-64/"
        self.put(image_dir + "iotedge-qemu-image-qemux86-64.rootfs.ext4", "ext4 fixture")
        self.put(image_dir + "bzImage", "kernel fixture")
        def run():
            return subprocess.run(self.build_job_shell() + [shell], cwd=self.root, capture_output=True, text=True)
        result = run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list((self.root / "rpm-staging").glob("*.rpm"))), 5)
        shutil.rmtree(self.root / "rpm-staging")
        (self.root / (image_dir + "bzImage")).unlink()
        self.assertNotEqual(run().returncode, 0)
        self.put(image_dir + "bzImage", "kernel fixture")
        if (self.root / "rpm-staging").exists():
            shutil.rmtree(self.root / "rpm-staging")
        (self.root / "build/tmp/deploy/rpm/core2_64/aziotctl-1.6.0-r0.core2_64.rpm").unlink()
        self.assertNotEqual(run().returncode, 0)

    def test_release_metadata_cannot_disguise_old_daemon_under_new_recipe_filename(self):
        self.release("1.6.4", "1.6.4", "1.6.0", "edge4", "iis0")
        self.put("recipes-core/iotedge/iotedge-1.6.4.inc", 'export VERSION = "1.6.0"\nIOTEDGE_RELEASE = "1.6.4"\nIIS_SRCREV = "iis0"\n')
        with self.assertRaisesRegex(ValueError, "filename/VERSION"):
            verifier().expected_selection(self.root, "wrynose")

    def test_crates_include_is_never_a_release_candidate(self):
        self.put("recipes-core/iotedge/iotedge-1.6.0-crates.inc", 'SRC_URI += "crate://crates.io/example/1.0"\n')
        subprocess.run(["git", "-C", str(self.root), "add", "recipes-core"], check=True)
        self.assertEqual(verifier().expected_selection(self.root, "wrynose")["release"], "1.6.0")

    def test_edge_provider_must_really_fetch_its_embedded_iis_source(self):
        module = verifier()
        expected = module.expected_selection(self.root, "wrynose")
        environments = self.environments(expected)
        environments["iotedge"]["SRC_URI"] = environments["iotedge"]["SRC_URI"].split()[0]
        with self.assertRaisesRegex(ValueError, "missing embedded IIS source"):
            module.verify_environments(expected, environments)

    def test_conflicting_newest_release_pairs_fail_instead_of_filename_tiebreak(self):
        self.release("1.6.4", "1.6.4", "1.6.0", "edge4", "iis0")
        self.release("1.6.4", "1.6.5", "1.6.0", "edge5", "iis0")
        with self.assertRaisesRegex(ValueError, "Ambiguous.*1.6.4"):
            verifier().expected_selection(self.root, "wrynose")

    def test_missing_intended_recipe_or_iis_pair_fails_without_old_version_fallback(self):
        self.release("1.6.4", "1.6.4", "1.6.0", "edge4", "iis0")
        intended = self.root / "recipes-core/iotedge/iotedge_1.6.4.bb"
        intended.unlink()
        with self.assertRaises((ValueError, OSError)):
            verifier().expected_selection(self.root, "wrynose")
        self.put("recipes-core/iotedge/iotedge_1.6.4.bb", 'SRCREV = "edge4"\n')
        self.put("recipes-core/iotedge/iotedge-1.6.4.inc", 'export VERSION = "1.6.4"\nIOTEDGE_RELEASE = "1.6.4"\nIIS_SRCREV = "absent-iis"\n')
        self.put("recipes-core/aziot-edged/aziot-edged-1.6.4.inc", 'export VERSION = "1.6.4"\nIOTEDGE_RELEASE = "1.6.4"\nIIS_SRCREV = "absent-iis"\n')
        with self.assertRaisesRegex(ValueError, "matching IIS_SRCREV absent-iis"):
            verifier().expected_selection(self.root, "wrynose")

    def test_prerelease_provider_pv_is_compared_to_rpm_transformed_version(self):
        module = verifier()
        self.release("1.6.4-rc.1", "1.6.4-rc.1", "1.6.0", "edge4rc", "iis0")
        expected = module.expected_selection(self.root, "wrynose")
        versions = module.verify_environments(expected, self.environments(expected))
        self.assertEqual(versions["iotedge"], "1.6.4+rc.1")
        inventory = "".join(f"{p} {v}\n" for p, v in versions.items())
        module.verify_installed(expected, versions, "iotedge 1.6.4-rc.1", inventory)
        with self.assertRaisesRegex(ValueError, "Installed iotedge"):
            module.verify_installed(expected, versions, "iotedge 1.6.4-rc.1", inventory.replace("1.6.4+rc.1", "1.6.4-rc.1"))


if __name__ == "__main__":
    unittest.main()
