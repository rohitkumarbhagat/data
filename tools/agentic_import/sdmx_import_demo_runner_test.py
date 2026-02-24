#!/usr/bin/env python3

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unit tests for Streamlit SDMX demo runner helpers."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest import mock

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
_PROJECT_ROOT = os.path.dirname(_REPO_ROOT)
for path in (_PROJECT_ROOT,):
    if path not in sys.path:
        sys.path.append(path)

from tools.agentic_import.sdmx_import_demo_runner import (  # pylint: disable=import-error
    ExecutionProfile, PipelineRunRequest, RunHandle, RunSession,
    build_pipeline_command, build_resume_command, build_stage_commands,
    load_state, normalize_step_statuses, stop_run,
)


class SdmxImportDemoRunnerTest(unittest.TestCase):

    def _build_request(self, working_dir: str) -> PipelineRunRequest:
        return PipelineRunRequest(
            endpoint="https://example.com/sdmx",
            agency="TEST_AGENCY",
            dataflow_id="TEST_FLOW",
            dataflow_key="A.B.C",
            dataflow_param="startPeriod=2020",
            dataset_prefix="demo_prefix",
            sample_rows=42,
            working_dir=working_dir,
            force=True,
            verbose=True,
            gemini_cli="/usr/local/bin/gemini",
        )

    def test_build_pipeline_command_includes_required_and_optional_flags(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = self._build_request(tmpdir)
            command = build_pipeline_command(request, skip_confirmation=True)

        self.assertIn("--sdmx.endpoint=https://example.com/sdmx", command)
        self.assertIn("--sdmx.agency=TEST_AGENCY", command)
        self.assertIn("--sdmx.dataflow.id=TEST_FLOW", command)
        self.assertIn("--sdmx.dataflow.key=A.B.C", command)
        self.assertIn("--sdmx.dataflow.param=startPeriod=2020", command)
        self.assertIn("--sample.rows=42", command)
        self.assertIn("--dataset_prefix=demo_prefix", command)
        self.assertTrue(any(
            arg.startswith("--working_dir=") for arg in command))
        self.assertIn("--gemini_cli=/usr/local/bin/gemini", command)
        self.assertIn("--force", command)
        self.assertIn("--verbose", command)
        self.assertIn("--skip_confirmation", command)

    def test_pause_profile_stage_commands_are_exact_pre_mapping_steps(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = self._build_request(tmpdir)
            commands = build_stage_commands(
                request, ExecutionProfile.PAUSE_BEFORE_MAPPING)

        self.assertEqual(len(commands), 3)
        self.assertIn("--run_only=download-data", commands[0])
        self.assertIn("--run_only=download-metadata", commands[1])
        self.assertIn("--run_only=create-sample", commands[2])
        for command in commands:
            self.assertIn("--skip_confirmation", command)
            self.assertNotIn("--force", command)

    def test_resume_command_for_pause_profile_uses_stateful_incremental_run(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = self._build_request(tmpdir)
            command = build_resume_command(
                request, ExecutionProfile.PAUSE_BEFORE_MAPPING)

        self.assertIn("--skip_confirmation", command)
        self.assertNotIn("--force", command)
        self.assertFalse(any(arg.startswith("--run_only=") for arg in command))

    def test_stop_run_escalates_from_terminate_to_kill(self) -> None:
        process = mock.Mock()
        process.pid = 12345
        process.poll.return_value = None
        process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="demo", timeout=1),
            -9,
        ]
        session = RunSession(
            request=self._build_request("/tmp"),
            profile=ExecutionProfile.FULL_AUTO,
            handle=RunHandle(pid=process.pid,
                             command=["python", "demo.py"],
                             log_path="/tmp/demo.log",
                             started_at="2025-01-01T00:00:00+00:00",
                             phase="full-auto"),
            process=process,
        )

        outcome = stop_run(session, timeout_seconds=1)

        self.assertEqual(outcome, "killed")
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertIsNone(session.process)
        self.assertEqual(session.handle.phase, "stopped")

    def test_load_state_handles_missing_corrupt_and_partial_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = self._build_request(tmpdir)
            self.assertIsNone(load_state(request))

            state_path = Path(
                tmpdir) / ".datacommons" / "demo_prefix.state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text("{bad-json", encoding="utf-8")
            self.assertIsNone(load_state(request))

            partial_state = {
                "steps": {
                    "download-data": {
                        "status": "succeeded"
                    }
                }
            }
            state_path.write_text(json.dumps(partial_state), encoding="utf-8")
            loaded = load_state(request)
            self.assertIsNotNone(loaded)
            statuses = normalize_step_statuses(request, state=loaded)
            self.assertEqual(statuses["download-data"], "succeeded")
            self.assertEqual(statuses["download-metadata"], "not_started")


if __name__ == "__main__":
    unittest.main()
