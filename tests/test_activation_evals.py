#!/usr/bin/env python3
"""Verify that activation evidence comes from successful entrypoint reads."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts.evals import check_skill_discovery as discovery
from scripts.evals import run_activation_evals as activation


ROOT = Path(__file__).resolve().parents[1]


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
            process.stdout = iter([])
            process.stdin = mock.Mock()
            with mock.patch.dict(os.environ, {"UNRELATED_SECRET": "hidden"}), \
                    mock.patch.object(discovery.subprocess, "Popen", return_value=process) as popen, \
                    self.assertRaisesRegex(RuntimeError, "timed out or exited"):
                discovery.check(workspace, codex_home)
            environment = popen.call_args.kwargs["env"]
            self.assertEqual(environment["CODEX_HOME"], str(codex_home))
            self.assertEqual(environment["HOME"], str(codex_home))
            self.assertNotIn("UNRELATED_SECRET", environment)

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
            dataset.write_text(json.dumps({
                "version": 1,
                "split": "train",
                "split_seed": 20261112,
                "queries": [{
                    "id": "sample-skill-positive-01",
                    "skill": "sample-skill",
                    "category": "direct",
                    "query": "Use the sample skill.",
                    "should_trigger": True,
                }],
            }), encoding="utf-8")
            output = root / "nested" / "activation.json"
            argv = [
                "run_activation_evals", str(dataset), "--allow-model-calls", "--runs", "1",
                "--jobs", "1", "--timeout", "1", "--output", str(output),
            ]
            trial = {"status": "pass", "observed_skill_read": True}
            with mock.patch.object(activation, "ROOT", root), mock.patch.object(
                activation, "run_case", return_value=trial
            ), mock.patch.object(
                activation, "detect_codex_version", return_value="codex-cli test"
            ), mock.patch.object(sys, "argv", argv):
                self.assertEqual(activation.main(), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["passes"], 1)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["dataset_split"], "train")
            self.assertEqual(payload["dataset_split_seed"], 20261112)
            self.assertNotIn("result_format_version", payload)
            self.assertEqual(payload["codex_version"], "codex-cli test")
            self.assertEqual(payload["results"][0]["category"], "direct")
            self.assertEqual(payload["skills_sha256"], activation.skills_digest(root))

    def test_codex_environment_uses_existing_login_and_an_allowlist(self) -> None:
        with mock.patch.dict(os.environ, {
            "PATH": "/bin", "HOME": "/home/user", "CODEX_HOME": "/home/user/.codex",
            "OPENAI_API_KEY": "model-key", "UNRELATED_SECRET": "hidden",
            "CUSTOM_PROVIDER_TOKEN": "provider-key",
        }, clear=True):
            environment = activation.codex_env(("CUSTOM_PROVIDER_TOKEN",))
        self.assertEqual(environment["PATH"], "/bin")
        self.assertEqual(environment["HOME"], "/home/user")
        self.assertEqual(environment["CODEX_HOME"], "/home/user/.codex")
        self.assertEqual(environment["OPENAI_API_KEY"], "model-key")
        self.assertEqual(environment["CUSTOM_PROVIDER_TOKEN"], "provider-key")
        self.assertNotIn("UNRELATED_SECRET", environment)

class CodexCommandContractTests(unittest.TestCase):
    def test_command_declares_required_behavior_without_personal_template(self) -> None:
        command = activation.codex_command()
        self.assertEqual(command[0:2], ["codex", "exec"])
        for option in ("--ephemeral", "--json", "--skip-git-repo-check", "--sandbox", "read-only"):
            self.assertIn(option, command)
        self.assertNotIn("--ignore-user-config", command)
        for personal_option in ("--profile", "--model"):
            self.assertNotIn(personal_option, command)

    def test_options_set_model_and_keep_routing_isolation(self) -> None:
        command = activation.codex_command(activation.CodexOptions(
            model="deepseek-flash",
            reasoning_effort="low",
        ))
        self.assertIn("--model", command)
        self.assertEqual(command[command.index("--model") + 1], "deepseek-flash")
        self.assertIn("--config", command)
        self.assertIn("model_reasoning_effort=low", command)
        self.assertIn("features.multi_agent=false", command)
        self.assertIn("skills.bundled.enabled=false", command)
        self.assertEqual(command[-3:-1], ["--config", "shell_environment_policy.inherit=none"])


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
        completed = activation.RunResult(stdout="", returncode=1, triggered=False)
        with mock.patch.object(activation, "run_streaming", return_value=completed):
            result = activation.run_case(self.case, timeout=30)
        self.assertEqual(result["status"], "inconclusive")
        self.assertTrue(result["infrastructure_failure"])
        self.assertEqual(result["reason"], "agent_process_failed")
        self.assertIn("duration_seconds", result)

    def test_timeout_reports_timeout_reason(self) -> None:
        with mock.patch.object(
            activation, "run_streaming",
            side_effect=subprocess.TimeoutExpired("codex", 1),
        ):
            result = activation.run_case(self.case, timeout=1)
        self.assertEqual(result["status"], "inconclusive")
        self.assertTrue(result["infrastructure_failure"])
        self.assertEqual(result["reason"], "timeout")

    def test_missing_executable_reports_evaluation_unavailable(self) -> None:
        with mock.patch.object(
            activation, "run_streaming", side_effect=FileNotFoundError("codex")
        ):
            result = activation.run_case(self.case, timeout=30)
        self.assertEqual(result["reason"], "evaluation_unavailable")

    def test_early_tool_call_trigger_is_a_decisive_outcome(self) -> None:
        triggered = activation.RunResult(stdout="", returncode=0, triggered=True)
        with mock.patch.object(activation, "run_streaming", return_value=triggered):
            positive = activation.run_case(self.case, timeout=30)
        self.assertEqual(positive["status"], "pass")
        self.assertTrue(positive["observed_skill_read"])

        negative = dict(self.case, should_trigger=False)
        with mock.patch.object(activation, "run_streaming", return_value=triggered):
            result = activation.run_case(negative, timeout=30)
        self.assertEqual(result["status"], "fail")

    def test_completed_positive_miss_is_a_failure(self) -> None:
        completed = activation.RunResult(
            stdout=json.dumps({"type": "turn.completed", "usage": {}}) + "\n",
            returncode=0,
            triggered=False,
        )
        with mock.patch.object(activation, "run_streaming", return_value=completed):
            result = activation.run_case(self.case, timeout=30)
        self.assertEqual(result["status"], "fail")
        self.assertFalse(result["observed_skill_read"])


class RunStreamingTests(unittest.TestCase):
    def fake_process(self, stdout_lines: list[str], poll_result: int | None = None) -> mock.Mock:
        process = mock.Mock()
        process.stdin = mock.Mock()
        process.stdout = iter(stdout_lines)
        process.returncode = None
        process.poll.return_value = poll_result
        process.wait.return_value = 0
        process.terminate = mock.Mock()
        process.kill = mock.Mock()
        return process

    def test_stop_callback_terminates_early(self) -> None:
        event = json.dumps({"type": "item.completed", "item": {"type": "command_execution"}})
        process = self.fake_process([event + "\n"])
        with mock.patch.object(activation.subprocess, "Popen", return_value=process):
            result = activation.run_streaming(
                ["codex", "exec"], "query", Path("/tmp"),
                {}, 30, stop=lambda e: e.get("type") == "item.completed",
            )
        self.assertTrue(result.triggered)
        self.assertIn(event, result.stdout)
        process.terminate.assert_called_once()

    def test_timeout_kills_process(self) -> None:
        process = self.fake_process([])
        with mock.patch.object(activation.subprocess, "Popen", return_value=process):
            with self.assertRaises(subprocess.TimeoutExpired):
                activation.run_streaming(
                    ["codex", "exec"], "query", Path("/tmp"), {}, 0,
                    stop=lambda e: False,
                )
        process.kill.assert_called_once()

    def test_streaming_captures_independent_thread_id(self) -> None:
        events = [
            json.dumps({"type": "thread.started", "thread_id": "thread-1"}) + "\n",
            json.dumps({"type": "item.completed", "item": {"type": "command_execution"}}) + "\n",
        ]
        process = self.fake_process(events)
        with mock.patch.object(activation.subprocess, "Popen", return_value=process):
            result = activation.run_streaming(
                ["codex", "exec"], "query", Path("/tmp"), {}, 30,
                stop=lambda e: e.get("type") == "item.completed"
                and e.get("item", {}).get("type") == "command_execution",
            )
        self.assertEqual(result.thread_id, "thread-1")

    def test_non_object_json_does_not_discard_later_events(self) -> None:
        events = ['[]\n', '"noise"\n', json.dumps({"type": "thread.started",
                                                 "thread_id": "thread-2"}) + "\n",
                  json.dumps({"type": "item.completed"}) + "\n"]
        process = self.fake_process(events)
        with mock.patch.object(activation.subprocess, "Popen", return_value=process):
            result = activation.run_streaming(
                ["codex", "exec"], "query", Path("/tmp"), {}, 30,
                stop=lambda event: event["type"] == "item.completed",
            )
        self.assertTrue(result.triggered)
        self.assertEqual(result.thread_id, "thread-2")


class ResumeCompatibilityTests(unittest.TestCase):
    def test_same_codex_skills_and_options_are_compatible(self) -> None:
        options = activation.CodexOptions(model="deepseek-flash", reasoning_effort="low")
        payload = {
            "codex_version": "codex-cli 1.2.3",
            "skills_sha256": "abc123",
            "codex_options": activation.codex_options_dict(options),
        }
        self.assertTrue(activation.resume_is_compatible(
            payload, "abc123", options, "codex-cli 1.2.3"
        ))
        self.assertIs(payload["codex_options"]["multi_agent_enabled"], False)

    def test_previous_delegation_policy_cannot_be_resumed(self) -> None:
        options = activation.CodexOptions()
        payload = {
            "codex_version": "codex-cli 1.2.3",
            "skills_sha256": "abc123",
            "codex_options": {"model": None, "profile": None,
                              "reasoning_effort": None, "pass_env": []},
        }
        self.assertFalse(activation.resume_is_compatible(
            payload, "abc123", options, "codex-cli 1.2.3"
        ))

    def test_unknown_codex_version_cannot_resume(self) -> None:
        options = activation.CodexOptions()
        payload = {"codex_version": None, "skills_sha256": "abc123",
                   "codex_options": activation.codex_options_dict(options)}
        self.assertFalse(activation.resume_is_compatible(payload, "abc123", options, None))

    def test_different_model_or_skills_invalidate_resume(self) -> None:
        options = activation.CodexOptions(model="deepseek-flash")
        payload = {
            "codex_version": "codex-cli 1.2.3",
            "skills_sha256": "abc123",
            "codex_options": activation.codex_options_dict(options),
        }
        self.assertFalse(activation.resume_is_compatible(
            payload, "def456", options, "codex-cli 1.2.3"
        ))
        other = activation.CodexOptions(model="deepseek-v4-pro")
        self.assertFalse(activation.resume_is_compatible(
            payload, "abc123", other, "codex-cli 1.2.3"
        ))
        self.assertFalse(activation.resume_is_compatible(
            payload, "abc123", options, "codex-cli 2.0.0"
        ))

    def test_codex_version_detection_uses_cli_output(self) -> None:
        completed = subprocess.CompletedProcess(
            ["codex", "--version"], 0, stdout="codex-cli 1.2.3\n", stderr=""
        )
        with mock.patch.object(activation.subprocess, "run", return_value=completed) as run:
            self.assertEqual(
                activation.detect_codex_version({"PATH": "/bin"}), "codex-cli 1.2.3"
            )
        self.assertEqual(run.call_args.args[0], ["codex", "--version"])

    def test_case_hash_changes_with_query_text(self) -> None:
        base = {"id": "a-positive-01", "skill": "a", "category": "direct",
                "query": "Use a.", "should_trigger": True}
        changed = dict(base, query="Use a differently.")
        self.assertNotEqual(activation.case_sha256(base), activation.case_sha256(changed))


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
        self.dataset.write_text(json.dumps({
            "version": 1,
            "split": "train",
            "split_seed": 20261112,
            "queries": [
                {"id": "sample-skill-positive-01", "skill": "sample-skill",
                 "category": "direct", "query": "Use the sample skill.", "should_trigger": True},
                {"id": "sample-skill-negative-01", "skill": "sample-skill",
                 "category": "boundary", "query": "Skip the sample skill.", "should_trigger": False},
            ],
        }), encoding="utf-8")
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

    def test_resume_from_output_does_not_rerun_decided_trials(self) -> None:
        good = {"status": "pass", "observed_skill_read": True}
        with mock.patch.object(activation, "detect_codex_version", return_value="codex-cli test"), \
                mock.patch.object(activation, "run_case", return_value=good) as run_case:
            self.assertEqual(self.run_main(), 0)
            self.assertEqual(run_case.call_count, 2)
            argv = ["run_activation_evals", str(self.dataset), "--allow-model-calls",
                    "--runs", "1", "--jobs", "1", "--output", str(self.output),
                    "--resume", str(self.output)]
            with mock.patch.object(activation, "ROOT", self.root), mock.patch.object(sys, "argv", argv):
                self.assertEqual(activation.main(), 0)
            self.assertEqual(run_case.call_count, 2)
        self.assertEqual(json.loads(self.output.read_text(encoding="utf-8"))["completed_trials"], 2)


if __name__ == "__main__":
    unittest.main()
