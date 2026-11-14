#!/usr/bin/env python3
"""Regression checks for the decision rules that give the skills practical value."""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from scripts.packages import lint_skill_packages as lint


ROOT = Path(__file__).resolve().parents[1]
DOMAIN = ROOT / "skills" / "python-domain-modeling"


def read(path: Path) -> str:
    """Read UTF-8 repository text.

    中文：读取仓库中的 UTF-8 文本文件，供内容契约测试复用。
    """
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


class PythonDocumentationTests(unittest.TestCase):
    def test_production_functions_have_bilingual_docstrings(self) -> None:
        for path in sorted((ROOT / "scripts").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            functions = (
                node for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            for function in functions:
                with self.subTest(path=path.relative_to(ROOT), function=function.name):
                    docstring = ast.get_docstring(function, clean=False)
                    self.assertIsNotNone(docstring)
                    self.assertIn("中文：", docstring)


class MarkdownStructureTests(unittest.TestCase):
    def test_artifact_review_template_covers_every_skill_without_claiming_results(self) -> None:
        samples = read(ROOT / "evals" / "artifact-acceptance-samples.md")
        template = read(ROOT / "evals" / "artifact-reviews" / "TEMPLATE.md")
        skills = {path.name for path in (ROOT / "skills").iterdir()
                  if (path / "SKILL.md").is_file()}
        sample_names = re.findall(r"^Skill: `(python-[a-z0-9-]+)`\.$", samples, re.M)
        template_names = re.findall(
            r"^\| [^|]+ / `(python-[a-z0-9-]+)` \| not-run \| Pending \|$",
            template, re.M,
        )
        self.assertEqual(set(sample_names), skills)
        self.assertEqual(set(template_names), skills)
        self.assertEqual(len(sample_names), len(skills))
        self.assertEqual(len(template_names), len(skills))

    def test_main_documents_separate_second_level_sections(self) -> None:
        for relative in ("README.md", "README_zh.md", "CHANGELOG.md", "SECURITY.md",
                         "evals/README.md", "evals/artifact-acceptance-samples.md",
                         "evals/artifact-reviews/TEMPLATE.md"):
            path = ROOT / relative
            inside_fence = False
            previous_nonblank = ""
            headings = 0
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("```"):
                    inside_fence = not inside_fence
                if not inside_fence and line.startswith("## "):
                    if headings:
                        with self.subTest(path=relative, heading=line):
                            self.assertEqual(previous_nonblank, "---")
                    headings += 1
                if line.strip() and not inside_fence:
                    previous_nonblank = line.strip()


if __name__ == "__main__":
    unittest.main()
