#!/usr/bin/env python3
"""Verify deterministic evidence extraction from Codex JSONL events."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.evals import activation_evidence as evidence


class ActivationEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.name = "sample-skill"
        self.path = self.root / "skills" / self.name / "SKILL.md"
        self.path.parent.mkdir(parents=True)
        self.entry = (
            "---\n"
            "name: sample-skill\n"
            "description: Exercise activation evidence tests.\n"
            "---\n"
            "# Sample Skill\n\n"
            "Follow the sample workflow.\n"
        )
        self.path.write_text(self.entry, encoding="utf-8")

    @staticmethod
    def event(command: str, output: str, exit_code: int = 0) -> str:
        return json.dumps({"type": "item.completed", "item": {
            "type": "command_execution",
            "command": command,
            "aggregated_output": output,
            "exit_code": exit_code,
        }})

    def markers(self) -> list[tuple[str, str, str]]:
        return evidence.build_markers(self.root / "skills")

    def observe(self, output: str) -> dict:
        return evidence.observe(output, self.markers())

    def test_successful_absolute_entrypoint_read(self) -> None:
        result = self.observe(self.event(f"cat {self.path}", self.entry))
        self.assertEqual(result["observed_reads"], [self.name])

    def test_relative_read_and_crlf_output_are_observed(self) -> None:
        command = f"cd .agents/skills/{self.name} && cat SKILL.md"
        result = self.observe(self.event(command, self.entry.replace("\n", "\r\n")))
        self.assertEqual(result["observed_reads"], [self.name])

    def test_multiple_events_ignore_noise_and_deduplicate_reads(self) -> None:
        events = "\n".join([
            "not json",
            json.dumps(["not", "an", "event"]),
            json.dumps({"type": "item.completed", "item": "not an object"}),
            self.event("printf unrelated", "unrelated"),
            self.event(f"cat {self.path}", self.entry),
            self.event(f"cat {self.path}", self.entry),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10}}),
        ])
        result = self.observe(events)
        self.assertEqual(result["observed_reads"], [self.name])
        self.assertTrue(result["turn_completed"])

    def test_self_report_path_mention_and_failed_command_are_not_evidence(self) -> None:
        message = json.dumps({"type": "item.completed", "item": {
            "type": "agent_message",
            "text": f"I used ${self.name} and read {self.path}",
        }})
        path_only = self.event(f"echo {self.path}", str(self.path))
        failed = self.event(f"cat {self.path}", self.entry, exit_code=1)
        for output in (message, path_only, failed):
            with self.subTest(output=output[:30]):
                self.assertEqual(self.observe(output)["observed_reads"], [])

    def test_incomplete_entrypoint_markers_are_not_evidence(self) -> None:
        output = "---\nname: sample-skill\n---\n"
        result = self.observe(self.event(f"head {self.path}", output))
        self.assertEqual(result["observed_reads"], [])

    def test_missing_completion_and_usage_filtering(self) -> None:
        result = self.observe(self.event(f"cat {self.path}", self.entry))
        self.assertFalse(result["turn_completed"])

        completed = json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 10,
            "cached_input_tokens": "4",
            "output_tokens": True,
            "secret": "SECRET_MARKER",
        }})
        result = self.observe(completed)
        self.assertEqual(result["usage"], {"input_tokens": 10})
        self.assertNotIn("SECRET_MARKER", str(result))

    def test_malformed_or_non_utf8_entrypoint_is_controlled(self) -> None:
        for content in (b"# Missing frontmatter\n", b"\xff"):
            with self.subTest(content=content):
                self.path.write_bytes(content)
                with self.assertRaises(RuntimeError):
                    self.markers()

    def test_command_event_matches_requires_exit_code_and_markers(self) -> None:
        markers = self.markers()
        good = json.loads(self.event(f"cat {self.path}", self.entry))
        self.assertTrue(evidence.command_event_matches(good, self.name, markers))

        failed = json.loads(self.event(f"cat {self.path}", self.entry, exit_code=1))
        self.assertFalse(evidence.command_event_matches(failed, self.name, markers))

        partial = json.loads(self.event(f"head {self.path}", "---\nname: sample-skill\n---\n"))
        self.assertFalse(evidence.command_event_matches(partial, self.name, markers))

    def test_printing_entrypoint_markers_without_reading_file_is_not_evidence(self) -> None:
        command = f"printf '%s\\n' 'SKILL.md' 'name: {self.name}' '# Sample Skill'"
        self.assertFalse(self.observe(self.event(command, self.entry))["observed_reads"])
        self.assertFalse(self.observe(self.event(
            f"printf '%s; cat SKILL.md' 'name: {self.name}'", self.entry
        ))["observed_reads"])
        self.assertEqual(self.observe(self.event(
            f"sed -n '1,40p' {self.path}", self.entry
        ))["observed_reads"], [self.name])

    def test_windows_unquoted_path_is_recognized(self) -> None:
        command = r"Get-Content -Raw C:\repo\skills\sample-skill\SKILL.md"
        event = json.loads(self.event(command, self.entry))
        with mock.patch.object(evidence.os, "name", "nt"):
            self.assertTrue(evidence.command_event_matches(event, self.name, self.markers()))

if __name__ == "__main__":
    unittest.main()
