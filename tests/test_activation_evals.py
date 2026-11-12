#!/usr/bin/env python3
"""Verify that activation evidence comes from successful entrypoint reads."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts.evals import check_skill_discovery as discovery
from scripts.evals import run_activation_evals as activation


ROOT = Path(__file__).resolve().parents[1]


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
        self.root_patch = mock.patch.object(activation, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    @staticmethod
    def event(command: str, output: str, exit_code: int = 0) -> str:
        return json.dumps({"type": "item.completed", "item": {
            "type": "command_execution",
            "command": command,
            "aggregated_output": output,
            "exit_code": exit_code,
        }})

    def test_successful_absolute_entrypoint_read(self) -> None:
        result = activation.observe(self.event(f"cat {self.path}", self.entry))
        self.assertEqual(result["observed_reads"], [self.name])

    def test_relative_read_and_crlf_output_are_observed(self) -> None:
        command = f"cd .agents/skills/{self.name} && cat SKILL.md"
        result = activation.observe(self.event(command, self.entry.replace("\n", "\r\n")))
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
        result = activation.observe(events)
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
                self.assertEqual(activation.observe(output)["observed_reads"], [])

    def test_incomplete_entrypoint_markers_are_not_evidence(self) -> None:
        output = "---\nname: sample-skill\n---\n"
        result = activation.observe(self.event(f"head {self.path}", output))
        self.assertEqual(result["observed_reads"], [])

    def test_missing_completion_and_usage_filtering(self) -> None:
        result = activation.observe(self.event(f"cat {self.path}", self.entry))
        self.assertFalse(result["turn_completed"])

        completed = json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 10,
            "cached_input_tokens": "4",
            "output_tokens": True,
            "secret": "SECRET_MARKER",
        }})
        result = activation.observe(completed)
        self.assertEqual(result["usage"], {"input_tokens": 10})
        self.assertNotIn("SECRET_MARKER", str(result))

    def test_malformed_or_non_utf8_entrypoint_is_controlled(self) -> None:
        for content in (b"# Missing frontmatter\n", b"\xff"):
            with self.subTest(content=content):
                self.path.write_bytes(content)
                with self.assertRaises(RuntimeError):
                    activation.observe(self.event(f"cat {self.path}", "output"))


class SampleCaseSelectionTests(unittest.TestCase):
    def make_case(self, skill: str, label: str, number: int) -> dict:
        return {
            "id": f"{skill}-{label}-{number:02d}",
            "skill": skill,
            "query": f"{skill} {label} {number}",
            "should_trigger": label == "positive",
        }

    def test_none_keeps_all_cases(self) -> None:
        cases = [self.make_case("skill-a", "positive", 1), self.make_case("skill-a", "negative", 1)]
        self.assertEqual(activation.sample_cases(cases, None), cases)

    def test_one_positive_and_one_negative_per_skill(self) -> None:
        cases = [
            self.make_case("skill-b", "negative", 2),
            self.make_case("skill-a", "positive", 3),
            self.make_case("skill-a", "positive", 1),
            self.make_case("skill-a", "negative", 1),
            self.make_case("skill-b", "positive", 1),
        ]
        sampled = activation.sample_cases(cases, 1)
        self.assertEqual(
            [case["id"] for case in sampled],
            ["skill-a-negative-01", "skill-a-positive-01", "skill-b-negative-02", "skill-b-positive-01"],
        )

    def test_sample_larger_than_available_keeps_available(self) -> None:
        cases = [self.make_case("skill-a", "positive", 1)]
        self.assertEqual(activation.sample_cases(cases, 10**100), cases)

    def test_cli_rejects_non_positive_and_non_integer_sample_limits(self) -> None:
        for value in ("0", "-1", "not-an-integer"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "result.json"
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "scripts.evals.run_activation_evals",
                        "evals/train_queries.json",
                        "--allow-model-calls",
                        "--sample-per-label",
                        value,
                        "--output",
                        str(output),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(completed.returncode, 2)
                self.assertFalse(output.exists())


class OutputPathTests(unittest.TestCase):
    def test_discovery_creates_output_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "nested" / "discovery.json"
            result = {"expected": 0, "found": [], "duplicate_names": [],
                      "discovery_errors": 0, "complete": True}
            with mock.patch.object(discovery, "check", return_value=result), mock.patch.object(
                sys, "argv", ["check_skill_discovery", "--output", str(output)]
            ):
                self.assertEqual(discovery.main(), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)

    def test_discovery_uses_empty_temporary_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            codex_home = root / "codex-home"
            workspace.mkdir()
            process = mock.Mock()
            process.stdout = mock.Mock()
            process.stdin = mock.Mock()
            with mock.patch.object(discovery.subprocess, "Popen", return_value=process) as popen, mock.patch.object(
                discovery.selectors, "DefaultSelector", side_effect=RuntimeError("stop after launch")
            ), self.assertRaisesRegex(RuntimeError, "stop after launch"):
                discovery.check(workspace, codex_home)
            environment = popen.call_args.kwargs["env"]
            self.assertEqual(environment["CODEX_HOME"], str(codex_home))
            self.assertEqual(environment["HOME"], str(codex_home))

    def test_activation_creates_output_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "skills" / "sample-skill"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: sample-skill\ndescription: Test activation.\n---\n# Sample\n",
                encoding="utf-8",
            )
            dataset = root / "cases.json"
            dataset.write_text(json.dumps([{
                "id": "sample-skill-positive-01",
                "skill": "sample-skill",
                "query": "Use the sample skill.",
                "should_trigger": True,
            }]), encoding="utf-8")
            output = root / "nested" / "activation.json"
            argv = [
                "run_activation_evals", str(dataset), "--allow-model-calls", "--runs", "1",
                "--jobs", "1", "--timeout", "1", "--output", str(output),
            ]
            trial = {"status": "pass", "observed_skill_read": True}
            with mock.patch.object(activation, "ROOT", root), mock.patch.object(
                activation, "run_case", return_value=trial
            ), mock.patch.object(sys, "argv", argv):
                self.assertEqual(activation.main(), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["passes"], 1)


class CodexCommandContractTests(unittest.TestCase):
    def test_command_declares_required_behavior_without_personal_template(self) -> None:
        command = activation.codex_command()
        self.assertEqual(command[0:2], ["codex", "exec"])
        for option in ("--ephemeral", "--json", "--skip-git-repo-check", "--sandbox", "read-only"):
            self.assertIn(option, command)
        for personal_option in ("--profile", "--model", "--config", "--ignore-user-config"):
            self.assertNotIn(personal_option, command)


class RunCaseFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "skills").mkdir()
        self.root_patch = mock.patch.object(activation, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.case = {"id": "sample-positive-01", "skill": "sample",
                     "query": "Use the sample skill.", "should_trigger": True}

    def test_nonzero_exit_reports_agent_process_failed(self) -> None:
        completed = mock.Mock(returncode=1, stdout="", stderr="")
        with mock.patch.object(activation.subprocess, "run", return_value=completed):
            result = activation.run_case(self.case, timeout=30)
        self.assertEqual(result["status"], "inconclusive")
        self.assertTrue(result["infrastructure_failure"])
        self.assertEqual(result["reason"], "agent_process_failed")
        self.assertIn("duration_seconds", result)

    def test_timeout_reports_timeout_reason(self) -> None:
        with mock.patch.object(
            activation.subprocess, "run",
            side_effect=subprocess.TimeoutExpired("codex", 1),
        ):
            result = activation.run_case(self.case, timeout=1)
        self.assertEqual(result["status"], "inconclusive")
        self.assertTrue(result["infrastructure_failure"])
        self.assertEqual(result["reason"], "timeout")

    def test_missing_executable_reports_evaluation_unavailable(self) -> None:
        with mock.patch.object(
            activation.subprocess, "run", side_effect=FileNotFoundError("codex")
        ):
            result = activation.run_case(self.case, timeout=30)
        self.assertEqual(result["reason"], "evaluation_unavailable")


class PreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        skill = self.root / "skills" / "sample-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: sample-skill\ndescription: Test preflight.\n---\n# Sample\n",
            encoding="utf-8",
        )
        self.dataset = self.root / "cases.json"
        self.dataset.write_text(json.dumps([
            {"id": "sample-skill-positive-01", "skill": "sample-skill",
             "query": "Use the sample skill.", "should_trigger": True},
            {"id": "sample-skill-negative-01", "skill": "sample-skill",
             "query": "Skip the sample skill.", "should_trigger": False},
        ]), encoding="utf-8")
        self.output = self.root / "result.json"

    def run_main(self) -> int:
        argv = ["run_activation_evals", str(self.dataset), "--allow-model-calls",
                "--runs", "1", "--jobs", "1", "--timeout", "1",
                "--output", str(self.output)]
        with mock.patch.object(activation, "ROOT", self.root), mock.patch.object(
            sys, "argv", argv
        ):
            return activation.main()

    def test_hard_preflight_failure_stops_remaining_calls(self) -> None:
        hard = {"status": "inconclusive", "infrastructure_failure": True,
                "reason": "agent_process_failed"}
        with mock.patch.object(activation, "run_case", return_value=hard) as run_case:
            self.assertEqual(self.run_main(), 2)
            self.assertEqual(run_case.call_count, 1)
        payload = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(payload["completed_trials"], 1)
        self.assertEqual(payload["expected_trials"], 2)
        self.assertEqual(payload["inconclusive"], 1)

    def test_soft_timeout_preflight_continues_run(self) -> None:
        soft = {"status": "inconclusive", "infrastructure_failure": True,
                "reason": "timeout"}
        good = {"status": "pass", "observed_skill_read": True}
        with mock.patch.object(
            activation, "run_case", side_effect=[soft, good]
        ) as run_case:
            self.assertEqual(self.run_main(), 1)
            self.assertEqual(run_case.call_count, 2)
        payload = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(payload["completed_trials"], 2)
        self.assertEqual(payload["passes"], 1)
        self.assertEqual(payload["inconclusive"], 1)


if __name__ == "__main__":
    unittest.main()
