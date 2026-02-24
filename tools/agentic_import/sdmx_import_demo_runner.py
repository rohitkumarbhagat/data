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
"""Utilities used by the Streamlit SDMX import demo UI."""

from __future__ import annotations

import dataclasses
import enum
import json
import shlex
import subprocess
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SDMX_PIPELINE_PATH = REPO_ROOT / "tools" / "agentic_import" / "sdmx_import_pipeline.py"

SDMX_STEP_ORDER = [
    "download-data",
    "download-metadata",
    "create-sample",
    "create-schema-mapping",
    "process-full-data",
    "create-dc-config",
]
PRE_MAPPING_STEPS = SDMX_STEP_ORDER[:3]

_STEP_START_PATTERN = re.compile(r"\[STEP START\]\s+([a-zA-Z0-9_.-]+)\s+\(v")
_STEP_END_PATTERN = re.compile(
    r"\[STEP END\]\s+([a-zA-Z0-9_.-]+).*status=(succeeded|failed|aborted)")


@dataclasses.dataclass(frozen=True)
class PipelineRunRequest:
    """All user-provided configuration needed to launch the SDMX pipeline."""
    endpoint: str
    agency: str
    dataflow_id: str
    dataset_prefix: str
    working_dir: str
    sample_rows: int = 1000
    dataflow_key: str | None = None
    dataflow_param: str | None = None
    force: bool = False
    verbose: bool = False
    gemini_cli: str = "gemini"


class ExecutionProfile(str, enum.Enum):
    FULL_AUTO = "full_auto"
    PAUSE_BEFORE_MAPPING = "pause_before_mapping"


@dataclasses.dataclass(frozen=True)
class RunHandle:
    """Serializable metadata about the latest spawned subprocess."""
    pid: int
    command: list[str]
    log_path: str
    started_at: str
    phase: str


@dataclasses.dataclass(frozen=True)
class StepLogProgress:
    running_step: str | None = None
    aborted_step: str | None = None


@dataclasses.dataclass
class RunSession:
    """Mutable session state stored by the Streamlit app."""
    request: PipelineRunRequest
    profile: ExecutionProfile
    handle: RunHandle
    process: subprocess.Popen | None = None
    stage_index: int = 0
    stopped_by_user: bool = False
    last_exit_code: int | None = None

    def is_active(self) -> bool:
        return self.process is not None and self.process.poll() is None


@dataclasses.dataclass(frozen=True)
class ArtifactInfo:
    name: str
    path: Path
    exists: bool


def _resolve_working_dir(value: str) -> Path:
    return Path(value).expanduser().resolve()


def get_state_path(request: PipelineRunRequest) -> Path:
    working_dir = _resolve_working_dir(request.working_dir)
    return working_dir / ".datacommons" / f"{request.dataset_prefix}.state.json"


def get_demo_log_path(request: PipelineRunRequest) -> Path:
    working_dir = _resolve_working_dir(request.working_dir)
    return working_dir / ".datacommons" / f"{request.dataset_prefix}.demo.log"


def build_pipeline_command(
    request: PipelineRunRequest,
    *,
    run_only: str | None = None,
    skip_confirmation: bool = True,
    force: bool | None = None,
) -> list[str]:
    """Builds a command that executes the SDMX pipeline CLI."""
    resolved_force = request.force if force is None else force
    command = [
        sys.executable,
        str(SDMX_PIPELINE_PATH),
        f"--sdmx.endpoint={request.endpoint}",
        f"--sdmx.agency={request.agency}",
        f"--sdmx.dataflow.id={request.dataflow_id}",
        f"--sample.rows={request.sample_rows}",
        f"--dataset_prefix={request.dataset_prefix}",
        f"--working_dir={_resolve_working_dir(request.working_dir)}",
    ]
    if request.dataflow_key:
        command.append(f"--sdmx.dataflow.key={request.dataflow_key}")
    if request.dataflow_param:
        command.append(f"--sdmx.dataflow.param={request.dataflow_param}")
    if request.gemini_cli:
        command.append(f"--gemini_cli={request.gemini_cli}")
    if run_only:
        command.append(f"--run_only={run_only}")
    if resolved_force:
        command.append("--force")
    if request.verbose:
        command.append("--verbose")
    if skip_confirmation:
        command.append("--skip_confirmation")
    return command


def build_stage_commands(request: PipelineRunRequest,
                         profile: ExecutionProfile) -> list[list[str]]:
    """Returns the command sequence used at run start for each profile."""
    if profile == ExecutionProfile.FULL_AUTO:
        return [
            build_pipeline_command(request,
                                   skip_confirmation=True,
                                   force=request.force)
        ]
    return [
        build_pipeline_command(request,
                               run_only=step_name,
                               skip_confirmation=True,
                               force=False) for step_name in PRE_MAPPING_STEPS
    ]


def build_resume_command(request: PipelineRunRequest,
                         profile: ExecutionProfile) -> list[str]:
    """Builds the command used after pause or stop."""
    if profile == ExecutionProfile.PAUSE_BEFORE_MAPPING:
        # Resume should continue from state, so force stays disabled here.
        return build_pipeline_command(request,
                                      skip_confirmation=True,
                                      force=False)
    return build_pipeline_command(request,
                                  skip_confirmation=True,
                                  force=request.force)


def _append_log_header(log_path: Path, phase: str, command: list[str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    rendered_command = shlex.join(command)
    header = (f"\n===== {timestamp} phase={phase} =====\n"
              f"command: {rendered_command}\n"
              "====================================\n")
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(header)


def _launch_process(command: list[str], log_path: Path,
                    phase: str) -> tuple[RunHandle, subprocess.Popen]:
    _append_log_header(log_path, phase, command)
    log_file = log_path.open("ab")
    try:
        process = subprocess.Popen(command,
                                   stdout=log_file,
                                   stderr=subprocess.STDOUT)
    finally:
        log_file.close()
    handle = RunHandle(pid=process.pid,
                       command=command,
                       log_path=str(log_path),
                       started_at=datetime.now(timezone.utc).isoformat(),
                       phase=phase)
    return handle, process


def start_run(request: PipelineRunRequest,
              profile: ExecutionProfile) -> RunSession:
    """Starts a new run session using the selected execution profile."""
    stage_commands = build_stage_commands(request, profile)
    first_phase = ("full-auto" if profile == ExecutionProfile.FULL_AUTO else
                   f"pre-mapping:{PRE_MAPPING_STEPS[0]}")
    log_path = get_demo_log_path(request)
    handle, process = _launch_process(stage_commands[0], log_path, first_phase)
    return RunSession(
        request=request,
        profile=profile,
        handle=handle,
        process=process,
        stage_index=0,
        stopped_by_user=False,
        last_exit_code=None,
    )


def advance_run(session: RunSession) -> RunSession:
    """Advances the run lifecycle, including staged pause-before-mapping flow."""
    if session.process is None:
        return session
    exit_code = session.process.poll()
    if exit_code is None:
        return session

    session.last_exit_code = exit_code
    if exit_code != 0:
        session.process = None
        final_phase = "aborted" if session.stopped_by_user else "failed"
        session.handle = dataclasses.replace(session.handle, phase=final_phase)
        return session

    if session.profile == ExecutionProfile.PAUSE_BEFORE_MAPPING:
        if session.stage_index < len(PRE_MAPPING_STEPS) - 1:
            session.stage_index += 1
            next_step = PRE_MAPPING_STEPS[session.stage_index]
            next_command = build_pipeline_command(session.request,
                                                  run_only=next_step,
                                                  skip_confirmation=True,
                                                  force=False)
            phase = f"pre-mapping:{next_step}"
            handle, process = _launch_process(next_command,
                                              Path(session.handle.log_path),
                                              phase)
            session.handle = handle
            session.process = process
            return session
        session.process = None
        session.handle = dataclasses.replace(session.handle,
                                             phase="paused-before-mapping")
        return session

    session.process = None
    final_phase = "aborted" if session.stopped_by_user else "completed"
    session.handle = dataclasses.replace(session.handle, phase=final_phase)
    return session


def resume_run(session: RunSession) -> RunSession:
    """Resumes a stopped or paused session using the same request/profile."""
    if session.is_active():
        return session
    command = build_resume_command(session.request, session.profile)
    phase = ("resuming-from-schema-mapping" if session.profile
             == ExecutionProfile.PAUSE_BEFORE_MAPPING else "full-auto")
    handle, process = _launch_process(command, Path(session.handle.log_path),
                                      phase)
    session.handle = handle
    session.process = process
    session.stopped_by_user = False
    session.last_exit_code = None
    session.stage_index = len(PRE_MAPPING_STEPS)
    return session


def stop_run(session: RunSession, timeout_seconds: float = 5.0) -> str:
    """Stops a running session and returns how the process exited."""
    if session.process is None:
        return "not-running"
    process = session.process
    if process.poll() is not None:
        session.process = None
        return "not-running"
    process.terminate()
    outcome = "terminated"
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout_seconds)
        outcome = "killed"
    session.stopped_by_user = True
    session.process = None
    session.handle = dataclasses.replace(session.handle, phase="stopped")
    return outcome


def load_state(request: PipelineRunRequest) -> dict[str, Any] | None:
    """Loads the state json if present and valid."""
    state_path = get_state_path(request)
    if not state_path.exists():
        return None
    try:
        with state_path.open("r", encoding="utf-8") as state_file:
            raw_state = json.load(state_file)
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return None
    if not isinstance(raw_state, dict):
        return None
    return raw_state


def tail_log(log_path: str | Path, max_lines: int = 200) -> str:
    """Returns the last `max_lines` lines from a log file."""
    path = Path(log_path)
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if not lines:
        return ""
    return "\n".join(lines[-max_lines:])


def parse_step_log_progress(log_path: str | Path) -> StepLogProgress:
    """Parses log lines to infer running and aborted step state."""
    log_tail = tail_log(log_path, max_lines=2000)
    if not log_tail:
        return StepLogProgress()

    running_step = None
    aborted_step = None
    for line in log_tail.splitlines():
        start_match = _STEP_START_PATTERN.search(line)
        if start_match:
            running_step = start_match.group(1)
            continue
        end_match = _STEP_END_PATTERN.search(line)
        if not end_match:
            continue
        step_name, status = end_match.group(1), end_match.group(2)
        if running_step == step_name:
            running_step = None
        if status == "aborted":
            aborted_step = step_name
    return StepLogProgress(running_step=running_step, aborted_step=aborted_step)


def _first_pending_step(step_statuses: dict[str, str]) -> str | None:
    for step_name in SDMX_STEP_ORDER:
        if step_statuses[step_name] not in ("succeeded", "failed"):
            return step_name
    return None


def normalize_step_statuses(
    request: PipelineRunRequest,
    *,
    session: RunSession | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Returns normalized per-step statuses for UI rendering."""
    statuses = {step_name: "not_started" for step_name in SDMX_STEP_ORDER}
    loaded_state = load_state(request) if state is None else state
    if loaded_state and isinstance(loaded_state.get("steps"), dict):
        for step_name, step_state in loaded_state["steps"].items():
            if step_name not in statuses or not isinstance(step_state, dict):
                continue
            raw_status = step_state.get("status")
            if raw_status in ("succeeded", "failed"):
                statuses[step_name] = raw_status

    progress = parse_step_log_progress(get_demo_log_path(request))
    if progress.aborted_step and progress.aborted_step in statuses:
        statuses[progress.aborted_step] = "aborted"
    if progress.running_step and progress.running_step in statuses:
        if statuses[progress.running_step] == "not_started":
            statuses[progress.running_step] = "running"

    if session and session.is_active() and "running" not in statuses.values():
        pending = _first_pending_step(statuses)
        if pending:
            statuses[pending] = "running"
    if session and session.stopped_by_user and not session.is_active():
        pending = _first_pending_step(statuses)
        if pending and statuses[pending] in ("not_started", "running"):
            statuses[pending] = "aborted"
    return statuses


def collect_artifacts(request: PipelineRunRequest) -> list[ArtifactInfo]:
    """Returns all known pipeline artifacts for quick results rendering."""
    working_dir = _resolve_working_dir(request.working_dir)
    prefix = request.dataset_prefix
    artifacts = [
        ("Downloaded data CSV", working_dir / f"{prefix}_data.csv"),
        ("Downloaded metadata XML", working_dir / f"{prefix}_metadata.xml"),
        ("Sample CSV", working_dir / f"{prefix}_sample.csv"),
        ("PV map CSV", working_dir / "sample_output" / f"{prefix}_pvmap.csv"),
        ("Sample metadata CSV",
         working_dir / "sample_output" / f"{prefix}_metadata.csv"),
        ("Final observations CSV", working_dir / "output" / f"{prefix}.csv"),
        ("Final TMCF", working_dir / "output" / f"{prefix}.tmcf"),
        ("Final MCF", working_dir / "output" / f"{prefix}.mcf"),
        ("Custom DC config", working_dir / "output" / f"{prefix}_config.json"),
    ]
    return [
        ArtifactInfo(name=name, path=path, exists=path.exists())
        for name, path in artifacts
    ]
