"""Command-line coordinator for SDMX agentic import steps (skeleton).

Phase 1: argument parsing, step registry, and path resolution only.
Actual subprocess execution is added in later phases.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Tuple, cast

from absl import app
from absl import flags
from absl import logging

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.sdmx_import.sdmx_client import SdmxClient
from tools.statvar_importer import data_sampler
from tools.agentic_import.pvmap_generator import (
    Config as PvmapConfig,
    DataConfig as PvmapDataConfig,
    PVMapGenerator,
)

FLAGS = flags.FLAGS

flags.DEFINE_string(
    "dataset_prefix",
    None,
    "Prefix used to name all generated files.",
)
flags.mark_flag_as_required("dataset_prefix")
flags.DEFINE_string("endpoint", None, "SDMX REST API endpoint URL.")
flags.DEFINE_string("agency", None, "SDMX agency identifier.")
flags.DEFINE_string("dataflow", None, "SDMX dataflow identifier.")
flags.DEFINE_multi_string(
    "key",
    [],
    "SDMX key filter (repeatable).",
)
flags.DEFINE_multi_string(
    "param",
    [],
    "Additional SDMX query parameter (repeatable).",
)
flags.DEFINE_integer(
    "sample_rows",
    30,
    "Rows to include when sampling SDMX data.",
)
flags.DEFINE_string(
    "step",
    None,
    "Run only the specified step (overwrites its outputs).",
)
flags.DEFINE_string(
    "from_step",
    None,
    "Run steps starting from the given step through 'run'.",
)
flags.DEFINE_bool(
    "verbose",
    False,
    "Print additional execution details.",
)
flags.DEFINE_bool(
    "force",
    False,
    "In default mode, ignore resume state and run all steps from start.",
)
flags.DEFINE_bool(
    "skip_confirmation",
    False,
    "Skip interactive confirmation prompts before executing steps.",
)
flags.DEFINE_string(
    "gemini_cli",
    None,
    "Optional path to Gemini CLI executable used during PV map generation.",
)

SAMPLE_OUTPUT_DIR = Path("sample_output")
FINAL_OUTPUT_DIR = Path("output")
STATE_DIR = Path(".datacommons")
STATVAR_PROCESSOR = (REPO_ROOT / "tools" / "statvar_importer" /
                     "stat_var_processor.py")
_RUN_OUTPUT_COLUMNS = (
    "observationDate,observationAbout,variableMeasured,value,"
    "observationPeriod,measurementMethod,unit,scalingFactor")


@dataclass(frozen=True)
class Step:
    name: str
    description: str
    version: int
    fingerprint_fn: Callable[[str, WorkflowContext], Dict[str, Any]]

    def inputs(self, prefix: str) -> List[Path]:
        return STEP_IO[self.name]["inputs"](prefix)

    def outputs(self, prefix: str) -> List[Path]:
        return STEP_IO[self.name]["outputs"](prefix)

    def fingerprint(self, prefix: str,
                    context: WorkflowContext) -> Dict[str, Any]:
        return self.fingerprint_fn(prefix, context)


@dataclass(frozen=True)
class SdmxSourceConfig:
    endpoint: str | None
    agency: str | None
    dataflow: str | None
    key: Tuple[str, ...]
    param: Tuple[str, ...]


@dataclass(frozen=True)
class WorkflowContext:
    sdmx: SdmxSourceConfig
    sample_rows: int
    verbose: bool
    skip_confirmation: bool
    gemini_cli: str | None


def _metadata_inputs(_: str) -> List[Path]:
    return []


def _metadata_outputs(prefix: str) -> List[Path]:
    return [Path(f"{prefix}_metadata.xml")]


def _data_inputs(prefix: str) -> List[Path]:
    # No file dependency: data download uses flags, not metadata.xml
    return []


def _data_outputs(prefix: str) -> List[Path]:
    return [Path(f"{prefix}_data.csv")]


def _sample_inputs(prefix: str) -> List[Path]:
    return _data_outputs(prefix)


def _sample_outputs(prefix: str) -> List[Path]:
    # Sample CSV is written at repo root, parallel to original files
    return [Path(f"{prefix}_sample.csv")]


def _pvmap_inputs(prefix: str) -> List[Path]:
    return [
        Path(f"{prefix}_sample.csv"),
        Path(f"{prefix}_metadata.xml"),
    ]


def _pvmap_outputs(prefix: str) -> List[Path]:
    return [
        SAMPLE_OUTPUT_DIR / f"{prefix}_pvmap.csv",
        SAMPLE_OUTPUT_DIR / f"{prefix}_metadata.csv",
        SAMPLE_OUTPUT_DIR / f"{prefix}.csv",
        SAMPLE_OUTPUT_DIR / f"{prefix}.tmcf",
        SAMPLE_OUTPUT_DIR / f"{prefix}_stat_vars.mcf",
    ]


def _run_inputs(prefix: str) -> List[Path]:
    return [
        Path(f"{prefix}_data.csv"),
        SAMPLE_OUTPUT_DIR / f"{prefix}_pvmap.csv",
        SAMPLE_OUTPUT_DIR / f"{prefix}_metadata.csv",
    ]


def _run_outputs(prefix: str) -> List[Path]:
    return [
        FINAL_OUTPUT_DIR / f"{prefix}.csv",
        FINAL_OUTPUT_DIR / f"{prefix}.tmcf",
        FINAL_OUTPUT_DIR / f"{prefix}_stat_vars.mcf",
    ]


def _fingerprint_sdmx_metadata(_: str,
                               context: WorkflowContext) -> Dict[str, Any]:
    return {
        "endpoint": context.sdmx.endpoint,
        "agency": context.sdmx.agency,
        "dataflow": context.sdmx.dataflow,
    }


def _normalize_multi_args(values: Tuple[str, ...]) -> List[str]:
    normalized = []
    for entry in values:
        parts = entry.split(":", 1)
        if len(parts) == 2:
            key, value = parts
            normalized.append(f"{key.strip()}:{value.strip()}")
        else:
            normalized.append(entry.strip())
    return sorted(normalized)


def _fingerprint_sdmx_data(_: str, context: WorkflowContext) -> Dict[str, Any]:
    return {
        "endpoint": context.sdmx.endpoint,
        "agency": context.sdmx.agency,
        "dataflow": context.sdmx.dataflow,
        "key": _normalize_multi_args(context.sdmx.key),
        "param": _normalize_multi_args(context.sdmx.param),
    }


def _fingerprint_sample(_: str, context: WorkflowContext) -> Dict[str, Any]:
    return {"sample_rows": context.sample_rows}


def _fingerprint_pvmap(prefix: str, context: WorkflowContext) -> Dict[str, Any]:
    return {
        "sample": f"{prefix}_sample.csv",
        "metadata": f"{prefix}_metadata.xml",
        "sdmx_dataset": True,
        "gemini_cli": context.gemini_cli,
    }


def _fingerprint_run(prefix: str, _: WorkflowContext) -> Dict[str, Any]:
    return {
        "data": f"{prefix}_data.csv",
        "pvmap": f"{prefix}_pvmap.csv",
        "metadata": f"{prefix}_metadata.csv",
        "output_columns": _RUN_OUTPUT_COLUMNS,
    }


STEP_SEQUENCE: List[Step] = [
    Step(
        "sdmx-metadata",
        "Download SDMX metadata",
        version=1,
        fingerprint_fn=_fingerprint_sdmx_metadata,
    ),
    Step(
        "sdmx-data",
        "Download SDMX data",
        version=1,
        fingerprint_fn=_fingerprint_sdmx_data,
    ),
    Step(
        "sample",
        "Sample SDMX data",
        version=1,
        fingerprint_fn=_fingerprint_sample,
    ),
    Step(
        "pvmap",
        "Generate PV map from sample",
        version=1,
        fingerprint_fn=_fingerprint_pvmap,
    ),
    Step(
        "run",
        "Process full SDMX data",
        version=1,
        fingerprint_fn=_fingerprint_run,
    ),
]

STEP_IO: Dict[str, Dict[str, callable]] = {
    "sdmx-metadata": {
        "inputs": _metadata_inputs,
        "outputs": _metadata_outputs
    },
    "sdmx-data": {
        "inputs": _data_inputs,
        "outputs": _data_outputs
    },
    "sample": {
        "inputs": _sample_inputs,
        "outputs": _sample_outputs
    },
    "pvmap": {
        "inputs": _pvmap_inputs,
        "outputs": _pvmap_outputs
    },
    "run": {
        "inputs": _run_inputs,
        "outputs": _run_outputs
    },
}


def _parse_key_value_pairs(pairs: Tuple[str, ...]) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for pair in pairs:
        if ":" not in pair:
            raise app.UsageError(f"Expected key:value format, got '{pair}'")
        key, value = pair.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _require_sdmx_source(config: SdmxSourceConfig, step_name: str) -> None:
    missing_flags = []
    if not config.endpoint:
        missing_flags.append("--endpoint")
    if not config.agency:
        missing_flags.append("--agency")
    if not config.dataflow:
        missing_flags.append("--dataflow")
    if missing_flags:
        raise app.UsageError(
            f"{step_name} requires SDMX source flags: {', '.join(missing_flags)}"
        )


def _make_sdmx_client(config: SdmxSourceConfig) -> SdmxClient:
    endpoint = cast(str, config.endpoint)
    agency = cast(str, config.agency)
    return SdmxClient(endpoint=endpoint, agency_id=agency)


def _execute_sdmx_metadata(prefix: str, context: WorkflowContext) -> None:
    config = context.sdmx
    _require_sdmx_source(config, "sdmx-metadata")
    output_path = Path(f"{prefix}_metadata.xml")
    client = _make_sdmx_client(config)
    if context.verbose:
        logging.info(
            "Starting SDMX metadata download: endpoint=%s agency=%s dataflow=%s -> %s",
            config.endpoint,
            config.agency,
            config.dataflow,
            output_path,
        )
    else:
        logging.info("Downloading SDMX metadata to %s", output_path)
    client.download_metadata(cast(str, config.dataflow), str(output_path))


def _execute_sdmx_data(prefix: str, context: WorkflowContext) -> None:
    config = context.sdmx
    _require_sdmx_source(config, "sdmx-data")
    output_path = Path(f"{prefix}_data.csv")
    client = _make_sdmx_client(config)
    key_filters = _parse_key_value_pairs(config.key)
    extra_params = _parse_key_value_pairs(config.param)
    if context.verbose:
        logging.info(
            "Starting SDMX data download: endpoint=%s agency=%s "
            "dataflow=%s key=%s params=%s -> %s",
            config.endpoint,
            config.agency,
            config.dataflow,
            key_filters,
            extra_params,
            output_path,
        )
    else:
        logging.info("Downloading SDMX data to %s", output_path)
    client.download_data_as_csv(
        cast(str, config.dataflow),
        key_filters,
        extra_params,
        str(output_path),
    )


def _execute_sample(prefix: str, context: WorkflowContext) -> None:
    input_path = Path(f"{prefix}_data.csv")
    if not input_path.is_file():
        raise app.UsageError(f"sample requires existing input: {input_path}")
    output_path = Path(f"{prefix}_sample.csv")
    if context.verbose:
        logging.info(
            "Starting sample: input=%s output=%s rows=%d",
            input_path,
            output_path,
            context.sample_rows,
        )
    else:
        logging.info("Sampling SDMX data into %s", output_path)
    data_sampler.sample_csv_file(
        str(input_path),
        str(output_path),
        {
            "sampler_input": str(input_path),
            "sampler_output": str(output_path),
            "sampler_output_rows": context.sample_rows,
        },
    )


def _execute_pvmap(prefix: str, context: WorkflowContext) -> None:
    sample_path = Path(f"{prefix}_sample.csv")
    metadata_path = Path(f"{prefix}_metadata.xml")
    if not sample_path.is_file():
        raise app.UsageError(f"pvmap requires sample output: {sample_path}")
    if not metadata_path.is_file():
        raise app.UsageError(f"pvmap requires metadata file: {metadata_path}")

    SAMPLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_prefix = SAMPLE_OUTPUT_DIR / prefix
    data_config = PvmapDataConfig(
        input_data=[str(sample_path)],
        input_metadata=[str(metadata_path)],
        is_sdmx_dataset=True,
    )
    pvmap_config = PvmapConfig(
        data_config=data_config,
        dry_run=False,
        maps_api_key=None,
        dc_api_key=None,
        max_iterations=10,
        skip_confirmation=context.skip_confirmation,
        enable_sandboxing=False,
        output_path=str(output_prefix),
        gemini_cli=context.gemini_cli,
    )
    if context.verbose:
        logging.info(
            "Starting PV map generation: sample=%s metadata=%s output=%s gemini_cli=%s",
            sample_path,
            metadata_path,
            output_prefix,
            context.gemini_cli,
        )
        logging.debug(
            "PV map parameters: skip_confirmation=%s",
            context.skip_confirmation,
        )
    else:
        logging.info("Generating PV map artifacts under %s", output_prefix)
    generator = PVMapGenerator(pvmap_config)
    generator.generate()


def _execute_run(prefix: str, context: WorkflowContext) -> None:
    data_path = Path(f"{prefix}_data.csv")
    pvmap_path = SAMPLE_OUTPUT_DIR / f"{prefix}_pvmap.csv"
    metadata_path = SAMPLE_OUTPUT_DIR / f"{prefix}_metadata.csv"
    for required in (data_path, pvmap_path, metadata_path):
        if not required.is_file():
            raise app.UsageError(f"run requires existing input: {required}")

    FINAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_prefix = FINAL_OUTPUT_DIR / prefix
    command = [
        sys.executable,
        str(STATVAR_PROCESSOR),
        f"--input_data={data_path}",
        f"--pv_map={pvmap_path}",
        f"--config_file={metadata_path}",
        "--generate_statvar_name=True",
        "--skip_constant_csv_columns=False",
        f"--output_columns={_RUN_OUTPUT_COLUMNS}",
        f"--output_path={output_prefix}",
    ]
    if context.verbose:
        logging.info(
            "Starting stat_var_processor: input=%s pvmap=%s metadata=%s -> %s",
            data_path,
            pvmap_path,
            metadata_path,
            output_prefix,
        )
        logging.debug("Command: %s", " ".join(command))
    else:
        logging.info("Running stat_var_processor for %s", prefix)
        logging.debug("Command: %s", " ".join(command))
    subprocess.run(command, check=True)


STEP_RUNNERS: Dict[str, Callable[[str, WorkflowContext], None]] = {
    "sdmx-metadata": _execute_sdmx_metadata,
    "sdmx-data": _execute_sdmx_data,
    "sample": _execute_sample,
    "pvmap": _execute_pvmap,
    "run": _execute_run,
}


def _state_path(prefix: str) -> Path:
    return STATE_DIR / f"{prefix}.state.json"


def _confirm_step_execution(step: Step, context: WorkflowContext) -> bool:
    if context.skip_confirmation:
        return True
    prompt = (
        f"Proceed with step '{step.name}' ({step.description})? [y/N]: "
    )
    try:
        response = input(prompt)
    except EOFError as exc:  # pragma: no cover
        raise app.UsageError(
            "Interactive confirmation is required; use --skip_confirmation to bypass."
        ) from exc
    decision = response.strip().lower()
    return decision in ("y", "yes")


def _load_state(prefix: str) -> Dict[str, Any]:
    path = _state_path(prefix)
    if not path.is_file():
        return {"steps": {}}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise app.UsageError(
            f"Failed to parse state file {path}: {exc}") from exc
    steps = data.get("steps", {})
    if not isinstance(steps, dict):
        steps = {}
    return {"steps": steps}


def _write_state(prefix: str, state: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_prefix": prefix,
        "updated": datetime.now(timezone.utc).isoformat(),
        "steps": state.get("steps", {}),
    }
    path = _state_path(prefix)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp_path.replace(path)


def _outputs_exist(paths: List[Path]) -> bool:
    return all(path.is_file() for path in paths)


def _step_state_matches(
    step: Step,
    record: Dict[str, Any],
    prefix: str,
    context: WorkflowContext,
) -> Tuple[bool, str | None]:
    if not record:
        return False, "no prior state"
    if record.get("status") != "success":
        return False, "status not success"
    if record.get("step_version") != step.version:
        return False, "step version changed"
    expected_outputs = [str(path) for path in step.outputs(prefix)]
    recorded_outputs = record.get("outputs")
    if not isinstance(recorded_outputs, list):
        return False, "missing outputs list"
    if sorted(recorded_outputs) != sorted(expected_outputs):
        return (
            False,
            "recorded outputs differ from expected list",
        )
    if not _outputs_exist(step.outputs(prefix)):
        return False, "expected output file missing"
    fingerprint = step.fingerprint(prefix, context)
    if record.get("inputs_fingerprint") != fingerprint:
        return False, "inputs fingerprint changed"
    return True, None


def _validate_step_flags(step: str | None, from_step: str | None) -> None:
    """Ensure step selection flags are valid."""
    if step and from_step:
        raise app.UsageError("--step and --from-step cannot be used together.")
    valid_names = [s.name for s in STEP_SEQUENCE]
    if step and step not in valid_names:
        raise app.UsageError(f"--step must be one of {valid_names}")
    if from_step and from_step not in valid_names:
        raise app.UsageError(f"--from-step must be one of {valid_names}")


def determine_steps(
    prefix: str,
    context: WorkflowContext,
    state: Dict[str, Any],
    step_name: str | None,
    from_step_name: str | None,
    force: bool,
) -> Tuple[List[Step], List[str], List[str]]:
    if step_name:
        return ([step for step in STEP_SEQUENCE if step.name == step_name], [],
                [])
    if from_step_name:
        names = [step.name for step in STEP_SEQUENCE]
        start_index = names.index(from_step_name)
        return (STEP_SEQUENCE[start_index:], [], [])
    if force:
        return (STEP_SEQUENCE, [], [])

    skipped: List[str] = []
    rerun_reasons: List[str] = []
    steps_state = state.get("steps", {})
    for index, step in enumerate(STEP_SEQUENCE):
        record = steps_state.get(step.name, {})
        matches, reason = _step_state_matches(step, record, prefix, context)
        if matches:
            skipped.append(step.name)
            continue
        message = f"Starting step: {step.name}"
        if reason:
            message += f". Reason for start -> {reason}"
        rerun_reasons.append(message)
        return (STEP_SEQUENCE[index:], skipped, rerun_reasons)
    return ([], skipped, rerun_reasons)


def execute_steps(
    prefix: str,
    steps: List[Step],
    context: WorkflowContext,
    state: Dict[str, Any],
) -> None:
    steps_state = state.setdefault("steps", {})
    for step in steps:
        logging.info("========================================")
        if context.verbose:
            logging.info(
                ">>> Starting step: %s — %s", step.name, step.description
            )
        else:
            logging.info(">>> Running step: %s", step.name)
        runner = STEP_RUNNERS.get(step.name)
        if not runner:
            raise NotImplementedError(f"Step '{step.name}' is not implemented.")

        missing_inputs = [
            str(path) for path in step.inputs(prefix) if not path.exists()
        ]
        if missing_inputs:
            raise app.UsageError(
                f"{step.name} requires existing inputs: {', '.join(missing_inputs)}; "
                "run prerequisite steps or provide the files."
            )
        if not _confirm_step_execution(step, context):
            logging.info("User declined to run step '%s'; stopping execution.", step.name)
            return

        fingerprint = step.fingerprint(prefix, context)
        outputs = [str(path) for path in step.outputs(prefix)]
        record = {
            "step": step.name,
            "step_version": step.version,
            "inputs_fingerprint": fingerprint,
            "outputs": outputs,
        }
        try:
            runner(prefix, context)
        except Exception as exc:  # noqa: BLE001
            record.update({
                "status": "failed",
                "updated": datetime.now(timezone.utc).isoformat(),
                "error": repr(exc),
            })
            steps_state[step.name] = record
            _write_state(prefix, state)
            logging.info("<<< Completed step: %s (failure)", step.name)
            raise
        else:
            record.update({
                "status": "success",
                "updated": datetime.now(timezone.utc).isoformat(),
            })
            steps_state[step.name] = record
            _write_state(prefix, state)
            logging.info("<<< Completed step: %s (success)", step.name)


def summarize_plan(
    prefix: str,
    steps: List[Step],
    skipped: List[str],
    rerun_reasons: List[str],
    context: WorkflowContext,
) -> None:
    logging.info("Dataset prefix: %s", prefix)
    if skipped:
        logging.info("Skipping (already complete): %s", ", ".join(skipped))
    if rerun_reasons:
        logging.info("Step start summary:")
        for reason in rerun_reasons:
            logging.info("  * %s", reason)
    if context.skip_confirmation:
        logging.info("Confirmation prompts are disabled (--skip_confirmation).")
    else:
        logging.info("Confirmation required before each step.")
    if context.gemini_cli:
        logging.info("Gemini CLI: %s", context.gemini_cli)
    else:
        logging.info("Gemini CLI: default (PV map generator decides)")
    logging.info("Planned steps:")
    for step in steps:
        logging.info("  - %s: %s", step.name, step.description)
        logging.info("    Inputs:")
        for path in step.inputs(prefix):
            logging.info("      * %s", path)
        logging.info("    Outputs:")
        for path in step.outputs(prefix):
            logging.info("      * %s", path)


def main(argv: Iterable[str]) -> None:
    del argv  # Unused.
    verbose = FLAGS.verbose
    step = FLAGS.step
    from_step = FLAGS.from_step
    if FLAGS.force and (step or from_step):
        logging.warning(
            "--force is ignored when used with --step or --from_step.")
    force = FLAGS.force if not (step or from_step) else False
    dataset_prefix = FLAGS.dataset_prefix
    sdmx_config = SdmxSourceConfig(
        endpoint=FLAGS.endpoint,
        agency=FLAGS.agency,
        dataflow=FLAGS.dataflow,
        key=tuple(FLAGS.key),
        param=tuple(FLAGS.param),
    )
    context = WorkflowContext(
        sdmx=sdmx_config,
        sample_rows=FLAGS.sample_rows,
        verbose=verbose,
        skip_confirmation=FLAGS.skip_confirmation,
        gemini_cli=FLAGS.gemini_cli,
    )

    logging.set_verbosity(logging.DEBUG if verbose else logging.INFO)

    _validate_step_flags(step, from_step)
    state = _load_state(dataset_prefix)
    steps_to_run, skipped, rerun_reasons = determine_steps(
        dataset_prefix,
        context,
        state,
        step,
        from_step,
        force,
    )

    summarize_plan(dataset_prefix, steps_to_run, skipped, rerun_reasons, context)
    if not steps_to_run:
        logging.info("Nothing to do; all steps already satisfied.")
        return

    execute_steps(dataset_prefix, steps_to_run, context, state)
    logging.info("Execution complete.")


if __name__ == "__main__":
    app.run(main)
