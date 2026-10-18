from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


DEEPSEEK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DEEPSEEK_ROOT.parent
sys.path.insert(0, str(DEEPSEEK_ROOT))

import doctor  # noqa: E402
import install  # noqa: E402
import runtime_overlay  # noqa: E402


class DeepSeekPrimarySetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)
        self.target = self.base / "primary"
        self.launcher = self.base / "bin" / "dsh-primary"

    def test_install_round_trip_and_rendered_overlay(self) -> None:
        self.assertEqual(
            install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False),
            0,
        )
        self.assertEqual(
            install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=True),
            0,
        )

        manifest = json.loads(
            (self.target / install.MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["schema"], install.MANIFEST_SCHEMA)
        self.assertEqual(
            os.readlink(self.launcher), str(self.target / "bin" / "dsh-primary")
        )
        overlay = (self.target / "primary-overlay.yml").read_text(encoding="utf-8")
        self.assertIn(str(self.target), overlay)
        self.assertNotIn(install.PRIMARY_HOME_TOKEN, overlay)
        self.assertTrue((self.target / "profiles/headless/package.json").is_file())
        self.assertTrue((self.target / "profiles/headless/cordis.patch.yml").is_file())
        self.assertTrue((self.target / "profiles/headless/pnpm-workspace.yaml").is_file())

    def test_unmanaged_collision_is_refused(self) -> None:
        self.target.mkdir(parents=True)
        (self.target / "AGENTS.md").write_text("mine\n", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "unmanaged target"):
            install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False)
        self.assertEqual(
            (self.target / "AGENTS.md").read_text(encoding="utf-8"), "mine\n"
        )

    def test_managed_local_drift_is_refused(self) -> None:
        install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False)
        (self.target / "AGENTS.md").write_text("local change\n", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "local modifications"):
            install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False)
        self.assertEqual(
            (self.target / "AGENTS.md").read_text(encoding="utf-8"),
            "local change\n",
        )

    def test_managed_mode_drift_is_refused(self) -> None:
        install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False)
        agents = self.target / "AGENTS.md"
        agents.chmod(0o644)

        with self.assertRaisesRegex(RuntimeError, "mode has local modifications"):
            install.install(
                self.target, DEEPSEEK_ROOT, self.launcher, check_only=True
            )

        self.assertEqual(agents.stat().st_mode & 0o777, 0o644)

    def test_managed_root_mode_drift_is_refused_and_diagnosed(self) -> None:
        install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False)
        self.target.chmod(0o755)

        with self.assertRaisesRegex(RuntimeError, "target root mode"):
            install.install(
                self.target, DEEPSEEK_ROOT, self.launcher, check_only=True
            )
        report = doctor.managed_check(self.target)

        self.assertEqual(report["status"], "fail")
        self.assertIn("root mode", report["detail"])

    def test_new_managed_artifact_extends_an_existing_manifest(self) -> None:
        install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False)
        manifest_path = self.target / install.MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"].pop("runtime_overlay.py")
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (self.target / "runtime_overlay.py").unlink()

        install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False)

        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIn("runtime_overlay.py", updated["files"])
        self.assertTrue((self.target / "runtime_overlay.py").is_file())

    def test_unmanaged_launcher_link_is_refused(self) -> None:
        self.launcher.parent.mkdir(parents=True)
        self.launcher.symlink_to(self.base / "someone-else")

        with self.assertRaisesRegex(RuntimeError, "launcher path"):
            install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False)
        self.assertEqual(os.readlink(self.launcher), str(self.base / "someone-else"))

    def test_failed_commit_rolls_back_new_files(self) -> None:
        real_replace = os.replace
        calls = 0

        def fail_second_replace(source: str | Path, target: str | Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("controlled commit failure")
            real_replace(source, target)

        with mock.patch("install.os.replace", side_effect=fail_second_replace):
            with self.assertRaisesRegex(OSError, "controlled commit failure"):
                install.install(
                    self.target, DEEPSEEK_ROOT, self.launcher, check_only=False
                )

        if self.target.exists():
            self.assertEqual(list(self.target.rglob("*")), [])
        self.assertFalse(os.path.lexists(self.launcher))

    def test_post_replace_external_bytes_survive_incomplete_rollback(self) -> None:
        real_replace = os.replace

        def replace_then_mutate(source: str | Path, target: str | Path) -> None:
            real_replace(source, target)
            destination = Path(target)
            if destination == self.target / "AGENTS.md":
                destination.write_text("external writer\n", encoding="utf-8")

        with mock.patch("install.os.replace", side_effect=replace_then_mutate):
            with self.assertRaisesRegex(RuntimeError, "rollback incomplete"):
                install.install(
                    self.target, DEEPSEEK_ROOT, self.launcher, check_only=False
                )

        self.assertEqual(
            (self.target / "AGENTS.md").read_text(encoding="utf-8"),
            "external writer\n",
        )

    def test_external_change_before_manifest_survives_rollback(self) -> None:
        real_manifest_bytes = install.manifest_bytes

        def mutate_then_render(source_root: Path, desired: dict[str, str]) -> bytes:
            (self.target / "AGENTS.md").write_text(
                "external after commits\n", encoding="utf-8"
            )
            return real_manifest_bytes(source_root, desired)

        with mock.patch("install.manifest_bytes", side_effect=mutate_then_render):
            with self.assertRaisesRegex(RuntimeError, "rollback incomplete"):
                install.install(
                    self.target, DEEPSEEK_ROOT, self.launcher, check_only=False
                )

        self.assertEqual(
            (self.target / "AGENTS.md").read_text(encoding="utf-8"),
            "external after commits\n",
        )

    def test_unchanged_managed_file_drift_refuses_manifest_publication(self) -> None:
        install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False)
        original_artifact_bytes = install.artifact_bytes
        original_manifest_bytes = install.manifest_bytes
        original_agents = (self.target / "AGENTS.md").read_bytes()
        manifest_before = (self.target / install.MANIFEST_NAME).read_bytes()

        def changed_agents(
            artifact: install.Artifact, target_root: Path
        ) -> bytes:
            content = original_artifact_bytes(artifact, target_root)
            if artifact.target == Path("AGENTS.md"):
                return content + b"\n<!-- controlled source update -->\n"
            return content

        def mutate_unchanged_file(
            source_root: Path, desired: dict[str, str]
        ) -> bytes:
            (self.target / "runtime_overlay.py").write_text(
                "external unchanged-target drift\n", encoding="utf-8"
            )
            return original_manifest_bytes(source_root, desired)

        with (
            mock.patch("install.artifact_bytes", side_effect=changed_agents),
            mock.patch(
                "install.manifest_bytes", side_effect=mutate_unchanged_file
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "managed path changed"):
                install.install(
                    self.target, DEEPSEEK_ROOT, self.launcher, check_only=False
                )

        self.assertEqual((self.target / "AGENTS.md").read_bytes(), original_agents)
        self.assertEqual(
            (self.target / "runtime_overlay.py").read_text(encoding="utf-8"),
            "external unchanged-target drift\n",
        )
        self.assertEqual(
            (self.target / install.MANIFEST_NAME).read_bytes(), manifest_before
        )

    def test_untracked_concurrent_file_survives_failed_first_install(self) -> None:
        real_replace = os.replace
        calls = 0

        def create_external_then_fail(
            source: str | Path, target: str | Path
        ) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                (self.target / "external.txt").write_text(
                    "concurrent\n", encoding="utf-8"
                )
                raise OSError("controlled failure with external file")
            real_replace(source, target)

        with mock.patch("install.os.replace", side_effect=create_external_then_fail):
            with self.assertRaisesRegex(RuntimeError, "rollback incomplete"):
                install.install(
                    self.target, DEEPSEEK_ROOT, self.launcher, check_only=False
                )

        self.assertEqual(
            (self.target / "external.txt").read_text(encoding="utf-8"),
            "concurrent\n",
        )

    def test_malformed_manifest_is_a_total_refusal(self) -> None:
        self.target.mkdir(parents=True)
        (self.target / install.MANIFEST_NAME).write_text("[]\n", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "unsupported shape"):
            install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False)

    def test_manifest_rejects_bool_schema_and_unsafe_target(self) -> None:
        self.target.mkdir(parents=True)
        manifest = self.target / install.MANIFEST_NAME
        manifest.write_text(
            '{"schema":true,"files":{}}\n', encoding="utf-8"
        )
        with self.assertRaisesRegex(RuntimeError, "unsupported shape"):
            install.load_manifest(manifest)

        manifest.write_text(
            '{"schema":1,"files":{"../outside":"'
            + ("0" * 64)
            + '"}}\n',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(RuntimeError, "invalid managed path"):
            install.load_manifest(manifest)

        manifest.write_text(
            '{"schema":1,"schema":1,"files":{}}\n', encoding="utf-8"
        )
        with self.assertRaisesRegex(RuntimeError, "duplicate JSON key"):
            install.load_manifest(manifest)

    def test_doctor_accepts_isolated_primary_and_rejects_shared_home(self) -> None:
        install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False)
        delegated_home = self.base / "driver-home"
        delegated_overlay = self.base / "dsh-agent.yml"
        driver_bin = self.base / "dsh"
        delegated_home.mkdir()
        delegated_overlay.write_text(
            "persona: delegated subagent\n", encoding="utf-8"
        )
        driver_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        driver_bin.chmod(0o700)

        report = doctor.diagnose(
            primary_root=self.target,
            launcher_link=self.launcher,
            delegated_home=delegated_home,
            driver_bin=driver_bin,
            delegated_overlay=delegated_overlay,
            run_composed_config=False,
        )
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["checks"]["authority_isolation"]["status"], "ok")

        shared = doctor.diagnose(
            primary_root=delegated_home,
            launcher_link=self.launcher,
            delegated_home=delegated_home,
            driver_bin=driver_bin,
            delegated_overlay=delegated_overlay,
            run_composed_config=False,
        )
        self.assertFalse(shared["ok"])
        self.assertEqual(shared["checks"]["authority_isolation"]["status"], "fail")

    def test_doctor_accepts_the_exact_per_run_session_root(self) -> None:
        run_root = self.base / "dispatches" / "a1b2c3d4"
        run_root.mkdir(parents=True)
        overlay = run_root / "runtime-overlay.json"
        sessions = run_root / "sessions"
        runtime_overlay.write_overlay(overlay, sessions, "deepseek-v4-pro")
        driver = self.base / "config-driver"
        driver.write_text(
            "#!/usr/bin/bash\n"
            "cat <<EOF\n"
            "- id: agent-default-model\n"
            "  config:\n"
            "    provider: deepseek-official\n"
            "    model: deepseek-v4-pro\n"
            "- id: llm-deepseek\n"
            "  config:\n"
            "    baseURL: https://api.deepseek.com\n"
            "- id: web-search-deepseek\n"
            "  config:\n"
            "    baseURL: https://api.deepseek.com/anthropic/v1\n"
            "- id: agent-instructions\n"
            "  config:\n"
            "    dshHome: ${DSH_HOME}\n"
            "    instructionFileCandidates:\n"
            "      - AGENTS.md\n"
            "- id: skill-filesystem\n"
            "  config:\n"
            "    dshHome: ${DSH_HOME}\n"
            "- id: session-persistence-jsonl\n"
            "  config:\n"
            f"    root: {sessions}\n"
            "- id: system-prompt\n"
            "  config:\n"
            "    persona: root user-facing primary DeepSeek operator\n"
            "EOF\n",
            encoding="utf-8",
        )
        driver.chmod(0o700)

        result = doctor.composed_config_check(
            primary_root=self.target,
            driver_bin=driver,
            model="deepseek-v4-pro",
            runtime_overlay=overlay,
        )

        self.assertEqual(result["status"], "ok", result)

    def test_doctor_rejects_a_divergent_per_run_static_overlay(self) -> None:
        install.install(self.target, DEEPSEEK_ROOT, self.launcher, check_only=False)
        run_root = self.base / "dispatches" / "a1b2c3d4"
        run_root.mkdir(parents=True)
        runtime = run_root / "runtime-overlay.json"
        static = run_root / "primary-overlay.yml"
        runtime_overlay.write_overlay(
            runtime, run_root / "sessions", "deepseek-v4-flash"
        )
        runtime_overlay.copy_static_overlay(
            self.target / "primary-overlay.yml", static
        )
        static.write_text("- id: attacker\n", encoding="utf-8")

        result = doctor.composed_config_check(
            primary_root=self.target,
            driver_bin=self.base / "unused-driver",
            model="deepseek-v4-flash",
            runtime_overlay=runtime,
            static_overlay=static,
        )

        self.assertEqual(result["status"], "fail")
        self.assertIn("does not match", result["detail"])

    def test_doctor_rejects_a_session_root_with_the_expected_prefix(self) -> None:
        driver = self.base / "config-driver"
        driver.write_text(
            "#!/usr/bin/bash\n"
            "cat <<'EOF'\n"
            "- id: agent-default-model\n"
            "  config:\n"
            "    provider: deepseek-official\n"
            "    model: deepseek-v4-flash\n"
            "- id: llm-deepseek\n"
            "  config:\n"
            "    baseURL: https://api.deepseek.com\n"
            "- id: web-search-deepseek\n"
            "  config:\n"
            "    baseURL: https://api.deepseek.com/anthropic/v1\n"
            "- id: agent-instructions\n"
            "  config:\n"
            f"    dshHome: {self.target}\n"
            "    instructionFileCandidates:\n"
            "      - AGENTS.md\n"
            "- id: skill-filesystem\n"
            "  config:\n"
            f"    dshHome: {self.target}\n"
            "- id: session-persistence-jsonl\n"
            "  config:\n"
            f"    root: {self.target}/sessions-attacker\n"
            "- id: system-prompt\n"
            "  config:\n"
            "    persona: root user-facing primary DeepSeek operator\n"
            "EOF\n",
            encoding="utf-8",
        )
        driver.chmod(0o700)

        result = doctor.composed_config_check(
            primary_root=self.target,
            driver_bin=driver,
            model="deepseek-v4-flash",
        )

        self.assertEqual(result["status"], "fail", result)

    def test_doctor_names_a_forbidden_provider_in_composed_config(self) -> None:
        driver = self.base / "config-driver"
        driver.write_text(
            "#!/usr/bin/bash\nprintf '%s\\n' '- id: injected' "
            "'  provider: prime-inference'\n",
            encoding="utf-8",
        )
        driver.chmod(0o700)

        result = doctor.composed_config_check(
            primary_root=self.target,
            driver_bin=driver,
            model="deepseek-v4-flash",
        )

        self.assertEqual(result["status"], "fail", result)
        self.assertIn("forbidden provider", result["detail"])

    def test_contract_keeps_delegates_proposal_only(self) -> None:
        primary = (DEEPSEEK_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        primary_overlay = (DEEPSEEK_ROOT / "primary-overlay.yml").read_text(
            encoding="utf-8"
        )
        delegated = (REPO_ROOT / "delegation" / "wrappers" / "dsh-agent").read_text(encoding="utf-8")
        delegated_overlay = (REPO_ROOT / "delegation" / "wrappers" / "dsh-agent.example.yml").read_text(encoding="utf-8")

        self.assertIn("user-facing primary DeepSeek", primary)
        self.assertIn("Delegated DeepSeek agents never call `memo note`", primary)
        self.assertIn("delegated subagent", delegated_overlay)
        self.assertNotIn("primary DeepSeek may call", delegated)
        self.assertIn("baseURL: https://api.deepseek.com", primary_overlay)
        self.assertIn(
            "baseURL: https://api.deepseek.com/anthropic/v1", primary_overlay
        )
        for identifier in install.NATIVE_CHILD_SURFACES:
            self.assertIn(f"- id: {identifier}\n  disabled: true", primary_overlay)


if __name__ == "__main__":
    unittest.main()
