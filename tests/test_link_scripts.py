#!/usr/bin/env python3
"""Integration tests for project-scoped skill link scripts."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "Bash link integration tests run on Linux")
class LinkIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="skill project ")
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name)

    def run_script(self, filename: str, *args: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / "links" / filename), *map(str, args)],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_idempotence_and_uninstall(self) -> None:
        name = "python-domain-modeling"
        first = self.run_script("install.sh", self.target, name)
        second = self.run_script("install.sh", self.target, name)
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertIn(f"keep  {name}", second.stdout)
        link = self.target / ".agents/skills" / name
        self.assertTrue(link.is_symlink())
        self.assertEqual(self.run_script("uninstall.sh", self.target, name).returncode, 0)
        self.assertFalse(link.is_symlink())
        self.assertTrue((ROOT / "skills" / name / "SKILL.md").is_file())

    def test_target_path_is_required(self) -> None:
        self.assertEqual(self.run_script("install.sh").returncode, 2)
        self.assertEqual(self.run_script("uninstall.sh").returncode, 2)

    def test_invalid_name_and_existing_directory_preserved(self) -> None:
        self.assertNotEqual(self.run_script("install.sh", self.target, "../escape").returncode, 0)
        destination = self.target / ".agents/skills/python-domain-modeling"
        destination.mkdir(parents=True)
        self.assertNotEqual(
            self.run_script("install.sh", self.target, destination.name).returncode, 0
        )
        self.assertTrue(destination.is_dir())

    def test_install_preflights_all_names_before_mutation(self) -> None:
        completed = self.run_script(
            "install.sh", self.target, "python-domain-modeling", "unknown-skill"
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse((self.target / ".agents").exists())

    def test_uninstall_preflights_all_names_before_mutation(self) -> None:
        name = "python-domain-modeling"
        self.assertEqual(self.run_script("install.sh", self.target, name).returncode, 0)
        link = self.target / ".agents/skills" / name
        completed = self.run_script("uninstall.sh", self.target, name, "../escape")
        self.assertNotEqual(completed.returncode, 0)
        self.assertTrue(link.is_symlink())

    def test_linked_destination_rejected_on_install_and_remove(self) -> None:
        outside = self.target / "outside"
        outside.mkdir()
        (self.target / ".agents").symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.run_script("install.sh", self.target).returncode, 0)
        self.assertNotEqual(self.run_script("uninstall.sh", self.target).returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_broken_link_requires_explicit_removal(self) -> None:
        name = "python-domain-modeling"
        link = self.target / ".agents/skills" / name
        link.parent.mkdir(parents=True)
        link.symlink_to(self.target / "missing-source", target_is_directory=True)

        install = self.run_script("install.sh", self.target, name)
        self.assertNotEqual(install.returncode, 0)
        self.assertIn("broken symbolic link", install.stderr)

        conservative = self.run_script("uninstall.sh", self.target, name)
        self.assertEqual(conservative.returncode, 0)
        self.assertIn("broken symbolic link", conservative.stdout)
        self.assertTrue(link.is_symlink())

        remove = self.run_script("uninstall.sh", "--remove-broken", self.target, name)
        self.assertEqual(remove.returncode, 0)
        self.assertFalse(link.is_symlink())


if __name__ == "__main__":
    unittest.main()
