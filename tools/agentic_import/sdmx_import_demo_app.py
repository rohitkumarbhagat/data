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
"""Streamlit wizard demo for the SDMX agentic import pipeline."""

from __future__ import annotations

import csv
import os
import shutil
import sys
import time
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.agentic_import.sdmx_import_demo_runner import (  # pylint: disable=import-error
    ExecutionProfile, PipelineRunRequest, RunSession, advance_run,
    collect_artifacts, get_demo_log_path, load_state, normalize_step_statuses,
    resume_run, start_run, stop_run, tail_log,
)

_STEP_LABELS = [
    "Environment Checks",
    "SDMX Configuration",
    "Execution Options",
    "Run Monitor",
    "Results",
]

_STATUS_STYLE = {
    "not_started": "Not started",
    "running": "Running",
    "succeeded": "Succeeded",
    "failed": "Failed",
    "aborted": "Aborted",
}


def _init_session_state() -> None:
    defaults = {
        "wizard_step": 1,
        "working_dir": os.getcwd(),
        "gemini_cli": "gemini",
        "endpoint": "",
        "agency": "",
        "dataflow_id": "",
        "dataflow_key": "",
        "dataflow_param": "",
        "dataset_prefix": "",
        "sample_rows": 1000,
        "force": False,
        "verbose": False,
        "auto_confirm": True,
        "run_session": None,
        "last_stop_outcome": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _set_step(step_index: int) -> None:
    st.session_state["wizard_step"] = max(1, min(len(_STEP_LABELS), step_index))


def _has_dc_api_key() -> bool:
    return bool(os.environ.get("DC_API_KEY", "").strip())


def _is_gemini_available(gemini_cli: str) -> bool:
    if not gemini_cli.strip():
        return False
    candidate = Path(gemini_cli).expanduser()
    if candidate.exists():
        return candidate.is_file() and os.access(candidate, os.X_OK)
    return shutil.which(gemini_cli) is not None


def _working_dir_error(working_dir: str) -> str | None:
    path = Path(working_dir).expanduser()
    if path.exists() and not path.is_dir():
        return f"Working directory points to a file: {path}"
    nearest_existing_parent = path if path.exists() else path.parent
    while (not nearest_existing_parent.exists() and
           nearest_existing_parent != nearest_existing_parent.parent):
        nearest_existing_parent = nearest_existing_parent.parent
    if not nearest_existing_parent.exists():
        return f"Cannot resolve a writable parent directory for: {path}"
    if not os.access(nearest_existing_parent, os.W_OK):
        return f"No write access to parent path: {nearest_existing_parent}"
    return None


def _environment_errors() -> list[str]:
    errors = []
    working_dir_error = _working_dir_error(st.session_state["working_dir"])
    if working_dir_error:
        errors.append(working_dir_error)
    if not _has_dc_api_key():
        errors.append("`DC_API_KEY` is missing from the environment.")
    if not _is_gemini_available(st.session_state["gemini_cli"]):
        errors.append(
            "Gemini CLI is not executable from the provided path/command.")
    return errors


def _config_errors() -> list[str]:
    errors = []
    required_fields = {
        "SDMX endpoint": st.session_state["endpoint"],
        "SDMX agency": st.session_state["agency"],
        "SDMX dataflow ID": st.session_state["dataflow_id"],
        "Dataset prefix": st.session_state["dataset_prefix"],
    }
    for label, value in required_fields.items():
        if not value.strip():
            errors.append(f"{label} is required.")
    sample_rows = st.session_state["sample_rows"]
    if int(sample_rows) <= 0:
        errors.append("Sample rows must be greater than 0.")
    return errors


def _all_validation_errors() -> list[str]:
    return _environment_errors() + _config_errors()


def _build_request() -> PipelineRunRequest:
    return PipelineRunRequest(
        endpoint=st.session_state["endpoint"].strip(),
        agency=st.session_state["agency"].strip(),
        dataflow_id=st.session_state["dataflow_id"].strip(),
        dataset_prefix=st.session_state["dataset_prefix"].strip(),
        working_dir=st.session_state["working_dir"].strip(),
        sample_rows=int(st.session_state["sample_rows"]),
        dataflow_key=st.session_state["dataflow_key"].strip() or None,
        dataflow_param=st.session_state["dataflow_param"].strip() or None,
        force=bool(st.session_state["force"]),
        verbose=bool(st.session_state["verbose"]),
        gemini_cli=st.session_state["gemini_cli"].strip(),
    )


def _selected_profile() -> ExecutionProfile:
    if st.session_state["auto_confirm"]:
        return ExecutionProfile.FULL_AUTO
    return ExecutionProfile.PAUSE_BEFORE_MAPPING


def _request_for_display() -> PipelineRunRequest:
    run_session: RunSession | None = st.session_state["run_session"]
    if run_session:
        return run_session.request
    return _build_request()


def _render_navigation(*, can_continue: bool) -> None:
    step_index = st.session_state["wizard_step"]
    left_col, right_col = st.columns(2)
    if step_index > 1:
        if left_col.button("Back", use_container_width=True):
            _set_step(step_index - 1)
            st.rerun()
    if step_index < len(_STEP_LABELS):
        if right_col.button("Next",
                            use_container_width=True,
                            disabled=not can_continue):
            _set_step(step_index + 1)
            st.rerun()


def _render_step_header() -> None:
    step_index = st.session_state["wizard_step"]
    st.title("SDMX Import Pipeline Demo")
    st.caption(
        "Wizard-style UI for the SDMX agentic pipeline (live execution mode).")
    st.progress(step_index / len(_STEP_LABELS))
    st.subheader(f"Step {step_index}: {_STEP_LABELS[step_index - 1]}")


def _render_environment_step() -> bool:
    st.text_input("Working directory", key="working_dir")
    st.text_input("Gemini CLI path or command", key="gemini_cli")

    working_dir_error = _working_dir_error(st.session_state["working_dir"])
    checks = [{
        "Check":
            "Working directory path",
        "Status":
            "OK" if not working_dir_error else "Needs attention",
        "Details":
            "Directory is valid and writable."
            if not working_dir_error else working_dir_error,
    }, {
        "Check":
            "DC_API_KEY",
        "Status":
            "OK" if _has_dc_api_key() else "Missing",
        "Details":
            "Environment variable is set."
            if _has_dc_api_key() else "Set `DC_API_KEY` before running.",
    }, {
        "Check":
            "Gemini CLI",
        "Status":
            "OK" if _is_gemini_available(st.session_state["gemini_cli"]) else
            "Missing",
        "Details":
            "CLI executable is available."
            if _is_gemini_available(st.session_state["gemini_cli"]) else
            "Provide an executable path or command in PATH.",
    }]
    st.dataframe(checks, use_container_width=True, hide_index=True)

    errors = _environment_errors()
    if errors:
        for error in errors:
            st.error(error)
    else:
        st.success("Environment checks passed.")
    return not errors


def _render_config_step() -> bool:
    left_col, right_col = st.columns(2)
    left_col.text_input("SDMX endpoint", key="endpoint")
    right_col.text_input("SDMX agency", key="agency")
    left_col.text_input("SDMX dataflow ID", key="dataflow_id")
    right_col.text_input("Dataset prefix", key="dataset_prefix")
    left_col.text_input("SDMX dataflow key (optional)", key="dataflow_key")
    right_col.text_input("SDMX dataflow param (optional)", key="dataflow_param")
    st.number_input("Sample rows",
                    min_value=1,
                    step=1,
                    key="sample_rows",
                    help="Number of rows used in the sample for mapping.")

    errors = _config_errors()
    if errors:
        for error in errors:
            st.error(error)
    else:
        st.success("Configuration looks valid.")
    return not errors


def _render_options_step() -> bool:
    st.checkbox("Force rerun all steps", key="force")
    st.checkbox("Verbose logging", key="verbose")
    st.checkbox("Auto-confirm schema mapping step", key="auto_confirm")
    profile = _selected_profile()
    st.info(f"Execution profile: `{profile.value}`")
    if profile == ExecutionProfile.PAUSE_BEFORE_MAPPING:
        st.warning(
            "Auto-confirm is OFF. The run will pause after `create-sample`.\n"
            "Use Resume to continue from schema mapping onward.")

    errors = _all_validation_errors()
    if errors:
        st.error("Resolve prior step errors before starting a run.")
        return False
    return True


def _render_step_timeline(request: PipelineRunRequest,
                          run_session: RunSession | None) -> None:
    step_statuses = normalize_step_statuses(request, session=run_session)
    rows = [{
        "Step": step_name,
        "Status": _STATUS_STYLE.get(status, status),
    } for step_name, status in step_statuses.items()]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_run_controls(request: PipelineRunRequest,
                         profile: ExecutionProfile) -> None:
    run_session: RunSession | None = st.session_state["run_session"]
    if run_session is not None:
        st.session_state["run_session"] = advance_run(run_session)
        run_session = st.session_state["run_session"]

    has_errors = bool(_all_validation_errors())
    is_active = bool(run_session and run_session.is_active())
    can_resume = bool(run_session and not run_session.is_active())

    start_col, stop_col, resume_col, refresh_col = st.columns(4)
    if start_col.button("Start",
                        disabled=has_errors or is_active,
                        use_container_width=True):
        st.session_state["run_session"] = start_run(request, profile)
        st.session_state["last_stop_outcome"] = ""
        st.rerun()

    if stop_col.button("Stop", disabled=not is_active,
                       use_container_width=True):
        outcome = stop_run(st.session_state["run_session"])
        st.session_state["last_stop_outcome"] = outcome
        st.rerun()

    if resume_col.button("Resume",
                         disabled=not can_resume,
                         use_container_width=True):
        st.session_state["run_session"] = resume_run(
            st.session_state["run_session"])
        st.session_state["last_stop_outcome"] = ""
        st.rerun()

    if refresh_col.button("Refresh", use_container_width=True):
        st.rerun()

    run_session = st.session_state["run_session"]
    if not run_session:
        st.info("No run started in this session.")
        return

    last_stop_outcome = st.session_state["last_stop_outcome"]
    if last_stop_outcome:
        st.warning(f"Latest stop outcome: `{last_stop_outcome}`")

    details = {
        "phase": run_session.handle.phase,
        "pid": run_session.handle.pid,
        "started_at": run_session.handle.started_at,
        "active": run_session.is_active(),
        "last_exit_code": run_session.last_exit_code,
    }
    st.json(details)
    st.code(" ".join(run_session.handle.command))


def _render_log_view(request: PipelineRunRequest) -> None:
    log_text = tail_log(get_demo_log_path(request), max_lines=200)
    st.text_area("Live run logs (tail)",
                 value=log_text,
                 height=280,
                 disabled=True)


def _read_csv_preview(path: Path, max_rows: int = 20) -> list[dict[str, str]]:
    preview_rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for index, row in enumerate(reader):
            if index >= max_rows:
                break
            preview_rows.append({k: v for k, v in row.items()})
    return preview_rows


def _render_monitor_step() -> bool:
    run_session: RunSession | None = st.session_state["run_session"]
    errors = _all_validation_errors()
    if errors and run_session is None:
        for error in errors:
            st.error(error)
        st.info("Fix the errors above to enable pipeline execution.")
        return False

    request = _request_for_display()
    profile = _selected_profile()
    _render_run_controls(request, profile)

    st.markdown("#### Step Timeline")
    _render_step_timeline(request, st.session_state["run_session"])
    st.markdown("#### Log Output")
    _render_log_view(request)

    state = load_state(request)
    if state is None:
        st.caption("State file not available yet.")
    else:
        st.caption("State file loaded from `.datacommons` directory.")

    if run_session and run_session.is_active():
        time.sleep(1)
        st.rerun()
    return True


def _render_results_step() -> bool:
    run_session: RunSession | None = st.session_state["run_session"]
    errors = _all_validation_errors()
    if errors and run_session is None:
        for error in errors:
            st.error(error)
        return False

    request = _request_for_display()
    artifacts = collect_artifacts(request)
    rows = [{
        "Artifact": artifact.name,
        "Status": "Found" if artifact.exists else "Missing",
        "Path": str(artifact.path),
    } for artifact in artifacts]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("#### Downloads")
    for artifact in artifacts:
        if not artifact.exists:
            continue
        size = artifact.path.stat().st_size
        if size > 25 * 1024 * 1024:
            st.caption(
                f"Skipping download button for large file: {artifact.path}")
            continue
        with artifact.path.open("rb") as artifact_file:
            st.download_button(
                label=f"Download {artifact.name}",
                data=artifact_file.read(),
                file_name=artifact.path.name,
                mime="application/octet-stream",
                key=f"download-{artifact.path}",
            )

    csv_artifacts = [
        artifact for artifact in artifacts
        if artifact.exists and artifact.path.suffix.lower() == ".csv"
    ]
    if csv_artifacts:
        selected_path = st.selectbox(
            "Preview CSV artifact",
            options=[str(artifact.path) for artifact in csv_artifacts],
        )
        preview = _read_csv_preview(Path(selected_path), max_rows=20)
        if preview:
            st.dataframe(preview, use_container_width=True, hide_index=True)
        else:
            st.info("Selected CSV has no data rows.")
    else:
        st.info("No CSV artifacts available for preview.")

    if run_session and run_session.is_active():
        time.sleep(1)
        st.rerun()
    return True


def _render_step_content() -> bool:
    step_index = st.session_state["wizard_step"]
    if step_index == 1:
        return _render_environment_step()
    if step_index == 2:
        return _render_config_step()
    if step_index == 3:
        return _render_options_step()
    if step_index == 4:
        return _render_monitor_step()
    return _render_results_step()


def main() -> None:
    st.set_page_config(layout="wide", page_title="SDMX Import Demo")
    _init_session_state()
    _render_step_header()
    can_continue = _render_step_content()
    _render_navigation(can_continue=can_continue)


if __name__ == "__main__":
    main()
