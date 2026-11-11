#!/usr/bin/env python3
"""Regression checks for the decision rules that give the skills practical value."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.packages import lint_skill_packages as lint


ROOT = Path(__file__).resolve().parents[1]
DOMAIN = ROOT / "skills" / "python-domain-modeling"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class DomainModelingContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = read(DOMAIN / "SKILL.md")
        cls.decision_table = read(DOMAIN / "references" / "decision-table.md")
        cls.scenarios = read(DOMAIN / "references" / "scenarios.md")

    def test_separates_boundary_models_from_domain_objects(self) -> None:
        self.assertIn("trust boundary", self.skill)
        self.assertIn("explicit converter", self.skill)
        self.assertIn("Pydantic request model", self.scenarios)

    def test_distinguishes_construction_from_lifetime_invariants(self) -> None:
        self.assertIn("__post_init__", self.skill)
        self.assertIn("does not run again after direct assignment", self.decision_table)
        self.assertIn("preserving one invariant", self.decision_table.lower())

    def test_preserves_key_tool_tradeoffs(self) -> None:
        for term in ("`ABC`", "`Protocol`", "`Enum`", "`Literal`"):
            self.assertIn(term, self.skill + self.decision_table)

    def test_rejects_property_memory_myth(self) -> None:
        self.assertIn("property does not reduce per-instance memory", self.skill)


class FocusedSkillContentTests(unittest.TestCase):
    def test_focused_skills_keep_decision_boundaries(self) -> None:
        expected = {
            "python-matplotlib-config": ("theme before", "Axes methods"),
            "python-loguru-logging": ("logger.catch", "logger.complete"),
            "python-sklearn-workflow": ("GroupKFold", "ColumnTransformer"),
            "python-cli-file-workflows": ("Path(__file__)", "tqdm.write"),
            "python-media-processing": ("setNumThreads", "segment-random sampling"),
            "python-binary-buffers": ("ownership", "memoryview"),
            "python-callable-caching": ("__init_subclass__", "simultaneous misses"),
            "python-domain-modeling": ("deepcopy", "BaseSettings"),
        }
        for name, terms in expected.items():
            content = read(ROOT / "skills" / name / "SKILL.md")
            for term in terms:
                with self.subTest(skill=name, term=term):
                    self.assertIn(term.lower(), content.lower())

    def test_media_runtime_reference_preserves_safety_boundaries(self) -> None:
        content = read(ROOT / "skills" / "python-media-processing" / "references" / "runtime-configuration.md")
        for term in (
            "MAX_IMAGE_PIXELS",
            "LOAD_TRUNCATED_IMAGES",
            "bridge.set_bridge",
            "av.logging.set_level",
            "torchvision.io.read_video",
            "deprecated",
        ):
            with self.subTest(term=term):
                self.assertIn(term.lower(), content.lower())

    def test_sklearn_references_preserve_leakage_and_inspection_boundaries(self) -> None:
        content = read(ROOT / "skills" / "python-sklearn-workflow" / "references" / "model-selection-guide.md")
        content += read(ROOT / "skills" / "python-sklearn-workflow" / "references" / "preprocessing-inspection.md")
        for term in (
            "StratifiedGroupKFold",
            "RandomizedSearchCV",
            "learning_curve",
            "validation_curve",
            "does not scale",
            "permutation_importance",
            "correlated features",
        ):
            with self.subTest(term=term):
                self.assertIn(term.lower(), content.lower())

    def test_cli_file_references_preserve_streaming_and_argument_boundaries(self) -> None:
        content = read(ROOT / "skills" / "python-cli-file-workflows" / "references" / "file-path-guide.md")
        content += read(ROOT / "skills" / "python-cli-file-workflows" / "references" / "progress-cli-guide.md")
        for term in (
            "importlib.resources",
            "single large JSON",
            "progress.update",
            "position",
            "action=\"version\"",
            "hyphen-to-underscore",
        ):
            with self.subTest(term=term):
                self.assertIn(term.lower(), content.lower())

    def test_domain_copy_reference_preserves_graph_boundaries(self) -> None:
        copying = read(ROOT / "skills" / "python-domain-modeling" / "references" / "copy-semantics.md")
        for term in ("copy.copy", "copy.deepcopy", "memoization", "pickle memo"):
            with self.subTest(term=term):
                self.assertIn(term.lower(), copying.lower())

    def test_callable_lifecycle_reference_preserves_cleanup_boundaries(self) -> None:
        lifecycle = read(ROOT / "skills" / "python-callable-caching" / "references" / "object-lifecycle.md")
        for term in ("__new__", "__init_subclass__", "not guaranteed", "ExitStack", "weakref.finalize"):
            with self.subTest(term=term):
                self.assertIn(term.lower(), lifecycle.lower())

    def test_callable_reference_corrects_binding_and_property_myths(self) -> None:
        content = read(ROOT / "skills" / "python-callable-caching" / "references" / "callable-guide.md")
        content += read(ROOT / "skills" / "python-callable-caching" / "references" / "cache-guide.md")
        for term in (
            "never `self`",
            "does not shrink",
            "lambda",
            "captured objects remain alive",
            "writable `__dict__`",
            "python 3.12+",
        ):
            with self.subTest(term=term):
                self.assertIn(term.lower(), content.lower())

    def test_domain_references_cover_pydantic_and_dataclass_boundaries(self) -> None:
        content = read(ROOT / "skills" / "python-domain-modeling" / "references" / "typing-interfaces.md")
        content += read(ROOT / "skills" / "python-domain-modeling" / "references" / "pydantic-v2.md")
        content += read(ROOT / "skills" / "python-domain-modeling" / "references" / "dataclass-guide.md")
        for term in (
            "Any",
            "runtime-checkable protocols",
            "Annotated[T, Field(...)]",
            "env_nested_delimiter",
            "validate_default=True",
            "default_factory",
            "does not recursively freeze",
            "copy.deepcopy()",
        ):
            with self.subTest(term=term):
                self.assertIn(term.lower(), content.lower())


class SkillRoutingTests(unittest.TestCase):
    def test_every_skill_declares_activation_disclosure_and_exit(self) -> None:
        for skill_dir in sorted((ROOT / "skills").iterdir()):
            entrypoint = skill_dir / "SKILL.md"
            if not entrypoint.is_file():
                continue
            content = read(entrypoint)
            frontmatter, diagnostics = lint.parse_skill(entrypoint)
            with self.subTest(skill=skill_dir.name):
                self.assertEqual(diagnostics, [])
                description = frontmatter.get("description")
                self.assertIsInstance(description, str)
                self.assertIn("Use when", description)
                self.assertTrue(
                    "Never activate" in description or "Do not use" in description,
                    "description must state a negative routing boundary",
                )
                self.assertIn("## Activation", content)
                self.assertIn("Disclosure", content)
                self.assertIn("Exit", content)
                self.assertIn("Do not trigger", content)

    def test_skill_instruction_files_are_ascii_english(self) -> None:
        for path in sorted((ROOT / "skills").rglob("*")):
            if path.is_file() and path.suffix in {".md", ".yaml"}:
                content = read(path)
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertTrue(content.isascii())


if __name__ == "__main__":
    unittest.main()
