#!/usr/bin/env python3
"""Regression tests for Agent Skills and Codex metadata validation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.packages import lint_skill_packages


ROOT = Path(__file__).resolve().parents[1]


VALID_SKILL = """---
name: sample-skill
description: Validate sample skill packages when testing the repository linter.
metadata:
  author: example
compatibility: Works with Agent Skills clients.
---

# Sample
"""


class SkillPackageLinterTests(unittest.TestCase):
    @staticmethod
    def errors(skill_dir: Path) -> list[str]:
        return [
            item.render()
            for item in lint_skill_packages.validate_skill_diagnostics(skill_dir)
            if item.severity == "error"
        ]

    def make_skill(self, content: str = VALID_SKILL) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        skill_dir = Path(temporary.name) / "sample-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        return temporary, skill_dir

    def test_valid_standard_skill(self) -> None:
        temporary, skill_dir = self.make_skill()
        with temporary:
            self.assertEqual(self.errors(skill_dir), [])

    def test_invalid_yaml_is_reported(self) -> None:
        temporary, skill_dir = self.make_skill("---\nname: [broken\n---\n# Sample\n")
        with temporary:
            errors = self.errors(skill_dir)
            self.assertTrue(any("invalid YAML" in error for error in errors))

    def test_standard_field_constraints_are_reported(self) -> None:
        content = VALID_SKILL.replace("sample-skill", "wrong--name", 1).replace(
            "Works with Agent Skills clients.", "x" * 501
        )
        temporary, skill_dir = self.make_skill(content)
        with temporary:
            errors = self.errors(skill_dir)
            self.assertTrue(any("single hyphens" in error for error in errors))
            diagnostics = lint_skill_packages.validate_skill_diagnostics(skill_dir)
            self.assertTrue(any(item.code == "name.directory-mismatch" and item.severity == "warning" for item in diagnostics))
            self.assertTrue(any("at most 500" in error for error in errors))

    def test_name_and_description_limits_are_reported(self) -> None:
        long_name = "a" * 65
        cases = {
            "name.length": VALID_SKILL.replace("sample-skill", long_name, 1),
            "description.missing": VALID_SKILL.replace(
                "description: Validate sample skill packages when testing the repository linter.\n", ""
            ),
            "description.length": VALID_SKILL.replace(
                "Validate sample skill packages when testing the repository linter.", "x" * 1025
            ),
        }
        for code, content in cases.items():
            temporary, skill_dir = self.make_skill(content)
            with self.subTest(code=code), temporary:
                diagnostics = lint_skill_packages.validate_skill_diagnostics(skill_dir)
                self.assertIn(code, {item.code for item in diagnostics})

    def test_optional_portable_fields_are_typed(self) -> None:
        content = VALID_SKILL.replace(
            "compatibility: Works with Agent Skills clients.",
            "compatibility: ''\nlicense: []\nallowed-tools: 3",
        )
        temporary, skill_dir = self.make_skill(content)
        with temporary:
            codes = {item.code for item in lint_skill_packages.validate_skill_diagnostics(skill_dir)}
            self.assertTrue({"compatibility.format", "license.format", "allowed-tools.format"} <= codes)

    def test_metadata_values_must_be_strings(self) -> None:
        temporary, skill_dir = self.make_skill(VALID_SKILL.replace("author: example", "version: 1"))
        with temporary:
            errors = self.errors(skill_dir)
            self.assertTrue(any("metadata keys and values" in error for error in errors))

    def test_additional_package_directories_are_allowed(self) -> None:
        temporary, skill_dir = self.make_skill()
        with temporary:
            (skill_dir / "vendor-extension").mkdir()
            self.assertEqual(self.errors(skill_dir), [])

    def test_broken_link_is_reported(self) -> None:
        temporary, skill_dir = self.make_skill(VALID_SKILL + "\n[Missing](references/missing.md)\n")
        with temporary:
            errors = self.errors(skill_dir)
            self.assertTrue(any("broken local link" in error for error in errors))

    @unittest.skipIf(os.name == "nt", "directory symlink test")
    def test_linked_package_root_is_rejected(self) -> None:
        temporary, skill_dir = self.make_skill()
        with temporary:
            linked = Path(temporary.name) / "linked-skill"
            linked.symlink_to(skill_dir, target_is_directory=True)
            diagnostics = lint_skill_packages.validate_skill_diagnostics(linked)
            self.assertIn("path.root-symlink", {item.code for item in diagnostics})

    def test_invalid_codex_metadata_is_reported(self) -> None:
        temporary, skill_dir = self.make_skill()
        with temporary:
            agents = skill_dir / "agents"
            agents.mkdir()
            (agents / "openai.yaml").write_text(
                'interface:\n  short_description: "Too short"\n  default_prompt: "Use another skill."\n',
                encoding="utf-8",
            )
            errors = self.errors(skill_dir)
            self.assertTrue(any("25-64" in error for error in errors))
            self.assertTrue(any("reference $sample-skill" in error for error in errors))

    def test_codex_colors_icons_policy_and_dependencies_are_validated(self) -> None:
        temporary, skill_dir = self.make_skill()
        with temporary:
            agents = skill_dir / "agents"
            agents.mkdir()
            (agents / "openai.yaml").write_text(
                "interface:\n"
                "  brand_color: red\n"
                "  icon_small: ../outside.svg\n"
                "  icon_large: assets/missing.svg\n"
                "policy:\n"
                "  allow_implicit_invocation: 'yes'\n"
                "dependencies: []\n",
                encoding="utf-8",
            )
            codes = {item.code for item in lint_skill_packages.validate_skill_diagnostics(skill_dir)}
            self.assertTrue({
                "openai.brand-color",
                "openai.icon-escape",
                "openai.icon-missing",
                "openai.policy-value",
                "openai.dependencies",
            } <= codes)

    def test_unlinked_and_long_references_warn(self) -> None:
        temporary, skill_dir = self.make_skill()
        with temporary:
            references = skill_dir / "references"
            references.mkdir()
            (references / "guide.md").write_text("# Guide\n" + "detail\n" * 101, encoding="utf-8")
            diagnostics = lint_skill_packages.validate_skill_diagnostics(skill_dir)
            codes = {item.code for item in diagnostics}
            self.assertIn("authoring.reference-unlinked", codes)
            self.assertIn("authoring.reference-contents", codes)

    def test_linked_long_reference_with_contents_is_clean(self) -> None:
        content = VALID_SKILL + "\n[Guide](references/guide.md)\n"
        temporary, skill_dir = self.make_skill(content)
        with temporary:
            references = skill_dir / "references"
            references.mkdir()
            (references / "guide.md").write_text(
                "# Guide\n\n## Contents\n\n- Topic\n\n## Topic\n" + "detail\n" * 100,
                encoding="utf-8",
            )
            diagnostics = lint_skill_packages.validate_skill_diagnostics(skill_dir)
            self.assertFalse(any(item.code.startswith("authoring.reference") for item in diagnostics))

    def test_entrypoint_length_and_nested_reference_warn(self) -> None:
        temporary, skill_dir = self.make_skill(VALID_SKILL + "line\n" * 501)
        with temporary:
            nested = skill_dir / "references" / "nested"
            nested.mkdir(parents=True)
            (nested / "guide.md").write_text("# Guide\n", encoding="utf-8")
            codes = {item.code for item in lint_skill_packages.validate_skill_diagnostics(skill_dir)}
            self.assertIn("authoring.entrypoint-length", codes)
            self.assertIn("authoring.reference-depth", codes)

    def test_scripts_require_shebang_and_posix_executable_bit(self) -> None:
        temporary, skill_dir = self.make_skill()
        with temporary:
            scripts = skill_dir / "scripts"
            scripts.mkdir()
            script = scripts / "check.py"
            script.write_text("print('ok')\n", encoding="utf-8")
            script.chmod(0o644)
            codes = {item.code for item in lint_skill_packages.validate_skill_diagnostics(skill_dir)}
            self.assertIn("script.shebang", codes)
            if os.name != "nt":
                self.assertIn("script.executable", codes)

    def test_cli_json_and_strict_warning_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skills_dir = Path(temp) / "skills"
            long_name = "a" * 65
            skill_dir = skills_dir / long_name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                VALID_SKILL.replace("sample-skill", long_name, 1), encoding="utf-8"
            )
            command = [
                sys.executable,
                "-m",
                "scripts.packages.lint_skill_packages",
                "--skills-dir",
                str(skills_dir),
                "--format",
                "json",
            ]
            normal = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
            strict = subprocess.run(
                [*command, "--strict-warnings"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(normal.returncode, 0)
            self.assertEqual(json.loads(normal.stdout)["warnings"], 1)
            self.assertEqual(strict.returncode, 1)


if __name__ == "__main__":
    unittest.main()
