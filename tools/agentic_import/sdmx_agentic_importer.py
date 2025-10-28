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
"""SDMX agentic import workflow runner.

Orchestrates a multi-step workflow for importing SDMX data: download metadata and
data, sample the data, generate property-value mappings, process the full dataset,
and generate a Custom DC configuration.

Supports resumable execution: if a step completes successfully, it is skipped on
subsequent runs. Use --force to ignore resume state and rerun all steps from start,
or --step/--from_step to run specific steps.

Workflow steps (in order):
  1. download-metadata: Download SDMX metadata
  2. download-data: Download SDMX data
  3. create-sample: Create SDMX data sample
  4. create-schema-mapping: Create schema mapping from sample
  5. process-full-data: Process full SDMX data
  6. create-dc-config: Create Custom DC configuration

Run with:
  python3 -m tools.agentic_import.sdmx_agentic_importer \
      --dataset_prefix=<prefix> \
      --endpoint=<sdmx-rest-api-url> \
      --agency=<agency-id> \
      --dataflow=<dataflow-id>

Example:
  python3 -m tools.agentic_import.sdmx_agentic_importer \
      --dataset_prefix=gdp \
      --endpoint=https://sdmx.example.org/api \
      --agency=OECD \
      --dataflow=ECONOMIC_INDICATORS

Required flags:
  --dataset_prefix: Prefix for naming generated files and directories. Use a unique
    identifier (e.g., dataset name, source acronym) to disambiguate multiple
    datasets processed in the same directory.

SDMX source flags (required for metadata/data download steps):
  --endpoint: SDMX REST API endpoint URL.
  --agency: SDMX agency identifier.
  --dataflow: SDMX dataflow identifier.

Optional flags:
  --key: SDMX key filter (repeatable, format: key:value).
  --param: Additional SDMX query parameter (repeatable, format: key:value).
  --sample_rows: Number of rows to sample (default: 30).
  --step: Run only the specified step (e.g., create-schema-mapping, process-full-data).
  --from_step: Run steps starting from the given step through the final step.
  --skip_confirmation: Skip interactive confirmation prompts.
  --force: Ignore resume state and run all steps from start.
  --gemini_cli: Optional path to Gemini CLI executable for PV map generation.
  --verbose: Print additional execution details.
"""

from __future__ import annotations

import json
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import (Any, ClassVar, Dict, Iterable, List, Literal, Optional,
                    Sequence, Tuple, TypedDict, cast, Final)

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
    "Run steps starting from the given step through the final step.",
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

STATUS_KEY: Final = "status"
STATUS_SUCCESS: Final = "success"
STATUS_FAILED: Final = "failed"
STEPS_KEY: Final = "steps"


@dataclass(frozen=True)
class SdmxSourceConfig:
    endpoint: str | None
    agency: str | None
    dataflow: str | None
    key: Tuple[str, ...]
    param: Tuple[str, ...]


@dataclass(frozen=True)
class WorkflowConfig:
    """Static workflow configuration used by workflow steps."""

    sdmx: SdmxSourceConfig
    sample_rows: int
    verbose: bool
    skip_confirmation: bool
    gemini_cli: str | None


@dataclass(frozen=True)
class ExecutionConfig:
    """Per-execution behavior controlling which steps run and if force applies."""

    step_name: str | None = None
    from_step_name: str | None = None
    force: bool = False


@dataclass
class ExecutionState:
    """Ephemeral state for a single execute() invocation."""

    steps: List["WorkflowStep"]
    skipped: List[str]
    rerun_reasons: List[str]


class FileSig(TypedDict, total=False):
    size: int
    mtime: int
    missing: bool


class InputFileFingerprint(TypedDict):
    path: str
    sig: FileSig


class DownloadMetadataFingerprint(TypedDict):
    endpoint: Optional[str]
    agency: Optional[str]
    dataflow: Optional[str]
    inputs: List[InputFileFingerprint]


class DownloadDataFingerprint(TypedDict):
    endpoint: Optional[str]
    agency: Optional[str]
    dataflow: Optional[str]
    key: Sequence[str]
    param: Sequence[str]
    inputs: List[InputFileFingerprint]


class CreateSampleFingerprint(TypedDict):
    sample_rows: int
    inputs: List[InputFileFingerprint]


class CreateSchemaMappingFingerprint(TypedDict):
    inputs: List[InputFileFingerprint]
    sdmx_dataset: Literal[True]
    gemini_cli: Optional[str]


class ProcessFullDataFingerprint(TypedDict):
    inputs: List[InputFileFingerprint]
    output_columns: str


class CreateDcConfigFingerprint(TypedDict):
    inputs: List[InputFileFingerprint]
    output_config: str


_FILE_SIG_CACHE: Dict[str, FileSig] = {}


def file_sig(path: Path) -> FileSig:
    """Return cached lightweight file metadata for fingerprints.

    Path.stat() issues an os.stat(2) call without reading file contents. Using
    seconds granularity avoids hashing while remaining fast for large files.
    """

    resolved = path.resolve(strict=False)
    key = str(resolved)
    cached = _FILE_SIG_CACHE.get(key)
    if cached is not None:
        return cached

    try:
        stat_result = resolved.stat()
    except FileNotFoundError:
        sig: FileSig = {"missing": True}
    else:
        sig = {
            "size": int(stat_result.st_size),
            "mtime": int(stat_result.st_mtime),
        }

    _FILE_SIG_CACHE[key] = sig
    return sig


def fingerprint_inputs(paths: List[Path]) -> List[InputFileFingerprint]:
    """Return canonicalized file fingerprints for the given paths."""

    entries: List[InputFileFingerprint] = [{
        "path": str(path),
        "sig": file_sig(path),
    } for path in paths]
    # Sorting ensures equality checks ignore the original input order.
    return sorted(entries, key=lambda entry: entry["path"])


class WorkflowStep(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    version: ClassVar[int] = 1

    @abstractmethod
    def inputs(self, prefix: str) -> List[Path]:
        """Return required input paths."""

    @abstractmethod
    def outputs(self, prefix: str) -> List[Path]:
        """Return expected output paths."""

    @abstractmethod
    def fingerprint(self, prefix: str,
                    context: WorkflowConfig) -> Dict[str, Any]:
        """Return values used to detect changes in step dependencies.

        Guidelines:
          * Capture every effective input that influences outputs (normalized
            flags/params, file identifiers, constants).
          * For file inputs, include a lightweight signature via `file_sig` so
            manual edits trigger reruns without hashing file contents.
          * Use `fingerprint_inputs()` to canonicalize file inputs so list
            ordering does not affect comparisons.
          * Keep the key set stable and avoid volatile values (timestamps,
            random IDs, unsorted collections).
          * This method may run before inputs exist; `file_sig` returns a
            `{"missing": True}` sentinel in that case, forcing a rerun later.
        """

    @abstractmethod
    def run(self, prefix: str, context: WorkflowConfig) -> None:
        """Execute the step."""

    def validate_prereqs(self, prefix: str) -> List[str]:
        return [str(path) for path in self.inputs(prefix) if not path.exists()]


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


class DownloadMetadataStep(WorkflowStep):
    name = "download-metadata"
    description = "Download SDMX metadata"

    def inputs(self, _: str) -> List[Path]:
        return []

    def outputs(self, prefix: str) -> List[Path]:
        return [Path(f"{prefix}_metadata.xml")]

    def fingerprint(self, _: str,
                    context: WorkflowConfig) -> DownloadMetadataFingerprint:
        return {
            "endpoint": context.sdmx.endpoint,
            "agency": context.sdmx.agency,
            "dataflow": context.sdmx.dataflow,
            "inputs": [],
        }

    def run(self, prefix: str, context: WorkflowConfig) -> None:
        sdmx_cfg = context.sdmx
        _require_sdmx_source(sdmx_cfg, self.name)
        output_path = Path(f"{prefix}_metadata.xml")
        client = _make_sdmx_client(sdmx_cfg)
        if context.verbose:
            logging.info(
                "Starting SDMX metadata download: endpoint=%s agency=%s dataflow=%s -> %s",
                sdmx_cfg.endpoint,
                sdmx_cfg.agency,
                sdmx_cfg.dataflow,
                output_path,
            )
        else:
            logging.info("Downloading SDMX metadata to %s", output_path)
        client.download_metadata(cast(str, sdmx_cfg.dataflow), str(output_path))


class DownloadDataStep(WorkflowStep):
    name = "download-data"
    description = "Download SDMX data"

    def inputs(self, _: str) -> List[Path]:
        return []

    def outputs(self, prefix: str) -> List[Path]:
        return [Path(f"{prefix}_data.csv")]

    def fingerprint(self, _: str,
                    context: WorkflowConfig) -> DownloadDataFingerprint:
        return {
            "endpoint": context.sdmx.endpoint,
            "agency": context.sdmx.agency,
            "dataflow": context.sdmx.dataflow,
            "key": _normalize_multi_args(context.sdmx.key),
            "param": _normalize_multi_args(context.sdmx.param),
            "inputs": [],
        }

    def run(self, prefix: str, context: WorkflowConfig) -> None:
        sdmx_cfg = context.sdmx
        _require_sdmx_source(sdmx_cfg, self.name)
        output_path = Path(f"{prefix}_data.csv")
        client = _make_sdmx_client(sdmx_cfg)
        key_filters = _parse_key_value_pairs(sdmx_cfg.key)
        extra_params = _parse_key_value_pairs(sdmx_cfg.param)
        if context.verbose:
            logging.info(
                "Starting SDMX data download: endpoint=%s agency=%s "
                "dataflow=%s key=%s params=%s -> %s",
                sdmx_cfg.endpoint,
                sdmx_cfg.agency,
                sdmx_cfg.dataflow,
                key_filters,
                extra_params,
                output_path,
            )
        else:
            logging.info("Downloading SDMX data to %s", output_path)
        client.download_data_as_csv(
            cast(str, sdmx_cfg.dataflow),
            key_filters,
            extra_params,
            str(output_path),
        )


class CreateSampleStep(WorkflowStep):
    name = "create-sample"
    description = "Create SDMX data sample"

    def inputs(self, prefix: str) -> List[Path]:
        return [Path(f"{prefix}_data.csv")]

    def outputs(self, prefix: str) -> List[Path]:
        return [Path(f"{prefix}_sample.csv")]

    def fingerprint(self, prefix: str,
                    context: WorkflowConfig) -> CreateSampleFingerprint:
        return {
            "sample_rows": context.sample_rows,
            "inputs": fingerprint_inputs(self.inputs(prefix)),
        }

    def run(self, prefix: str, context: WorkflowConfig) -> None:
        input_path = Path(f"{prefix}_data.csv")
        if not input_path.is_file():
            raise app.UsageError(
                f"{self.name} requires existing input: {input_path}")
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


class CreateSchemaMappingStep(WorkflowStep):
    name = "create-schema-mapping"
    description = "Create schema mapping from sample"

    def inputs(self, prefix: str) -> List[Path]:
        return [
            Path(f"{prefix}_sample.csv"),
            Path(f"{prefix}_metadata.xml"),
        ]

    def outputs(self, prefix: str) -> List[Path]:
        return [
            SAMPLE_OUTPUT_DIR / f"{prefix}_pvmap.csv",
            SAMPLE_OUTPUT_DIR / f"{prefix}_metadata.csv",
            SAMPLE_OUTPUT_DIR / f"{prefix}.csv",
            SAMPLE_OUTPUT_DIR / f"{prefix}.tmcf",
            SAMPLE_OUTPUT_DIR / f"{prefix}_stat_vars.mcf",
        ]

    def fingerprint(self, prefix: str,
                    context: WorkflowConfig) -> CreateSchemaMappingFingerprint:
        return {
            "inputs": fingerprint_inputs(self.inputs(prefix)),
            "sdmx_dataset": True,
            "gemini_cli": context.gemini_cli,
        }

    def run(self, prefix: str, context: WorkflowConfig) -> None:
        sample_path = Path(f"{prefix}_sample.csv")
        metadata_path = Path(f"{prefix}_metadata.xml")
        if not sample_path.is_file():
            raise app.UsageError(
                f"{self.name} requires sample output: {sample_path}")
        if not metadata_path.is_file():
            raise app.UsageError(
                f"{self.name} requires metadata file: {metadata_path}")

        SAMPLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_prefix = SAMPLE_OUTPUT_DIR / prefix
        data_config = PvmapDataConfig(
            input_data=[str(sample_path)],
            input_metadata=[str(metadata_path)],
            is_sdmx_dataset=True,
        )
        config_kwargs = {
            "data_config": data_config,
            "skip_confirmation": context.skip_confirmation,
            "output_path": str(output_prefix),
        }
        if context.gemini_cli:
            config_kwargs["gemini_cli"] = context.gemini_cli
        pvmap_config = PvmapConfig(**config_kwargs)
        if context.verbose:
            logging.info(
                "Starting PV map generation: sample=%s metadata=%s output=%s gemini_cli=%s",
                sample_path,
                metadata_path,
                output_prefix,
                context.gemini_cli,
            )
            logging.debug(
                "PV map parameters: %s",
                {
                    "data_config": {
                        "input_data": [str(sample_path)],
                        "input_metadata": [str(metadata_path)],
                        "is_sdmx_dataset": True,
                    },
                    "output_path": str(output_prefix),
                    "skip_confirmation": context.skip_confirmation,
                    "gemini_cli": context.gemini_cli,
                },
            )
        else:
            logging.info("Generating PV map artifacts under %s", output_prefix)
        generator = PVMapGenerator(pvmap_config)
        generator.generate()


class ProcessFullDataStep(WorkflowStep):
    PROCESSOR: Final[Path] = (REPO_ROOT / "tools" / "statvar_importer" /
                              "stat_var_processor.py")
    RUN_OUTPUT_COLUMNS: Final[str] = (
        "observationDate,observationAbout,variableMeasured,value,"
        "observationPeriod,measurementMethod,unit,scalingFactor")
    name = "process-full-data"
    description = "Process full SDMX data"

    def inputs(self, prefix: str) -> List[Path]:
        return [
            Path(f"{prefix}_data.csv"),
            SAMPLE_OUTPUT_DIR / f"{prefix}_pvmap.csv",
            SAMPLE_OUTPUT_DIR / f"{prefix}_metadata.csv",
        ]

    def outputs(self, prefix: str) -> List[Path]:
        return [
            FINAL_OUTPUT_DIR / f"{prefix}.csv",
            FINAL_OUTPUT_DIR / f"{prefix}.tmcf",
            FINAL_OUTPUT_DIR / f"{prefix}_stat_vars.mcf",
        ]

    def fingerprint(self, prefix: str,
                    _: WorkflowConfig) -> ProcessFullDataFingerprint:
        return {
            "inputs": fingerprint_inputs(self.inputs(prefix)),
            "output_columns": self.RUN_OUTPUT_COLUMNS,
        }

    def run(self, prefix: str, context: WorkflowConfig) -> None:
        data_path = Path(f"{prefix}_data.csv")
        pvmap_path = SAMPLE_OUTPUT_DIR / f"{prefix}_pvmap.csv"
        metadata_path = SAMPLE_OUTPUT_DIR / f"{prefix}_metadata.csv"
        for required in (data_path, pvmap_path, metadata_path):
            if not required.is_file():
                raise app.UsageError(
                    f"{self.name} requires existing input: {required}")

        FINAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_prefix = FINAL_OUTPUT_DIR / prefix
        command = [
            sys.executable,
            str(self.PROCESSOR),
            f"--input_data={data_path}",
            f"--pv_map={pvmap_path}",
            f"--config_file={metadata_path}",
            "--generate_statvar_name=True",
            "--skip_constant_csv_columns=False",
            f"--output_columns={self.RUN_OUTPUT_COLUMNS}",
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


class CreateDcConfigStep(WorkflowStep):
    GENERATOR: Final[Path] = (REPO_ROOT / "tools" / "agentic_import" /
                              "generate_custom_dc_config.py")
    name = "create-dc-config"
    description = "Create Custom DC configuration"

    def inputs(self, prefix: str) -> List[Path]:
        return [FINAL_OUTPUT_DIR / f"{prefix}.csv"]

    def outputs(self, _: str) -> List[Path]:
        return [FINAL_OUTPUT_DIR / "config.json"]

    def fingerprint(self, prefix: str,
                    _: WorkflowConfig) -> CreateDcConfigFingerprint:
        return {
            "inputs": fingerprint_inputs(self.inputs(prefix)),
            "output_config": str(FINAL_OUTPUT_DIR / "config.json"),
        }

    def run(self, prefix: str, context: WorkflowConfig) -> None:
        input_csv = FINAL_OUTPUT_DIR / f"{prefix}.csv"
        output_config = FINAL_OUTPUT_DIR / "config.json"
        if not input_csv.is_file():
            raise app.UsageError(
                f"{self.name} requires existing input: {input_csv}")

        provenance_name = context.sdmx.dataflow
        source_name = context.sdmx.agency
        data_source_url = context.sdmx.endpoint
        dataset_url = None
        if (context.sdmx.endpoint and context.sdmx.agency and
                context.sdmx.dataflow):
            dataset_url = (f"{context.sdmx.endpoint.rstrip('/')}/data/"
                           f"{context.sdmx.agency},{context.sdmx.dataflow},")

        command = [
            sys.executable,
            str(self.GENERATOR),
            f"--input_csv={input_csv}",
            f"--output_config={output_config}",
        ]
        if provenance_name:
            command.append(f"--provenance_name={provenance_name}")
        if source_name:
            command.append(f"--source_name={source_name}")
        if data_source_url:
            command.append(f"--data_source_url={data_source_url}")
        if dataset_url:
            command.append(f"--dataset_url={dataset_url}")
        if context.verbose:
            logging.info(
                "Starting custom DC config generation: input=%s -> %s",
                input_csv,
                output_config,
            )
            logging.debug("Command: %s", " ".join(command))
        else:
            logging.info("Generating custom DC config at %s", output_config)
        subprocess.run(command, check=True)


STEP_SEQUENCE: List[WorkflowStep] = [
    DownloadMetadataStep(),
    DownloadDataStep(),
    CreateSampleStep(),
    CreateSchemaMappingStep(),
    ProcessFullDataStep(),
    CreateDcConfigStep(),
]


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


def _outputs_exist(paths: List[Path]) -> bool:
    return all(path.is_file() for path in paths)


def _step_state_matches(
    step: WorkflowStep,
    record: Dict[str, Any],
    prefix: str,
    context: WorkflowConfig,
) -> Tuple[bool, str | None]:
    if not record:
        return False, "no prior state"
    if record.get(STATUS_KEY) != STATUS_SUCCESS:
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


class Workflow:

    def __init__(
        self,
        prefix: str,
        config: WorkflowConfig,
        steps: Sequence[WorkflowStep] = STEP_SEQUENCE,
    ) -> None:
        self.prefix = prefix
        self.config = config
        self.steps = list(steps)
        self._step_names = [step.name for step in self.steps]
        self.state = self._load_state()

    def _validate_execution_config(self, exec_config: ExecutionConfig) -> None:
        step = exec_config.step_name
        from_step = exec_config.from_step_name
        if step and from_step:
            raise app.UsageError(
                "--step and --from-step cannot be used together.")
        if step and step not in self._step_names:
            raise app.UsageError(f"--step must be one of {self._step_names}")
        if from_step and from_step not in self._step_names:
            raise app.UsageError(
                f"--from-step must be one of {self._step_names}")

    def _state_path(self) -> Path:
        return STATE_DIR / f"{self.prefix}.state.json"

    def _load_state(self) -> Dict[str, Any]:
        path = self._state_path()
        if not path.is_file():
            return {STEPS_KEY: {}}
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise app.UsageError(
                f"Failed to parse state file {path}: {exc}") from exc
        steps_state = data.get(STEPS_KEY, {})
        if not isinstance(steps_state, dict):
            steps_state = {}
        return {STEPS_KEY: steps_state}

    def _write_state(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "dataset_prefix": self.prefix,
            "updated": datetime.now(timezone.utc).isoformat(),
            STEPS_KEY: self.state.get(STEPS_KEY, {}),
        }
        path = self._state_path()
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp_path.replace(path)

    def _confirm_step_execution(self, step: WorkflowStep) -> bool:
        if self.config.skip_confirmation:
            return True
        prompt = f"Proceed with step '{step.name}' ({step.description})? [y/N]: "
        try:
            response = input(prompt)
        except EOFError as exc:  # pragma: no cover
            raise app.UsageError(
                "Interactive confirmation is required; use --skip_confirmation to bypass."
            ) from exc
        decision = response.strip().lower()
        return decision in ("y", "yes")

    def _determine_steps(
        self,
        exec_config: ExecutionConfig,
        effective_force: bool,
    ) -> Tuple[List[WorkflowStep], List[str], List[str]]:
        if exec_config.step_name:
            selected = [
                step for step in self.steps
                if step.name == exec_config.step_name
            ]
            return (selected, [], [])
        if exec_config.from_step_name:
            start_index = self._step_names.index(exec_config.from_step_name)
            return (self.steps[start_index:], [], [])
        if effective_force:
            return (list(self.steps), [], [])

        skipped: List[str] = []
        rerun_reasons: List[str] = []
        steps_state = self.state.get(STEPS_KEY, {})
        for index, step in enumerate(self.steps):
            record = steps_state.get(step.name, {})
            matches, reason = _step_state_matches(
                step,
                record,
                self.prefix,
                self.config,
            )
            if matches:
                skipped.append(step.name)
                continue
            message = f"Starting step: {step.name}"
            if reason:
                message += f". Reason for start -> {reason}"
            rerun_reasons.append(message)
            return (self.steps[index:], skipped, rerun_reasons)
        return ([], skipped, rerun_reasons)

    def _summarize_plan(
        self,
        steps: List[WorkflowStep],
        skipped: List[str],
        rerun_reasons: List[str],
    ) -> None:
        logging.info("Dataset prefix: %s", self.prefix)
        if skipped:
            logging.info("Skipping (already complete): %s", ", ".join(skipped))
        if rerun_reasons:
            logging.info("Step start summary:")
            for reason in rerun_reasons:
                logging.info("  * %s", reason)
        if self.config.skip_confirmation:
            logging.info(
                "Confirmation prompts are disabled (--skip_confirmation).")
        else:
            logging.info("Confirmation required before each step.")
        if self.config.gemini_cli:
            logging.info("Gemini CLI: %s", self.config.gemini_cli)
        else:
            logging.info("Gemini CLI: default (PV map generator decides)")
        logging.info("Planned steps:")
        for step in steps:
            logging.info("  - %s: %s", step.name, step.description)
            logging.info("    Inputs:")
            for path in step.inputs(self.prefix):
                logging.info("      * %s", path)
            logging.info("    Outputs:")
            for path in step.outputs(self.prefix):
                logging.info("      * %s", path)

    def _execute_steps(self, steps: List[WorkflowStep]) -> bool:
        steps_state = self.state.setdefault(STEPS_KEY, {})
        for step in steps:
            logging.info("========================================")
            if self.config.verbose:
                logging.info(">>> Starting step: %s — %s", step.name,
                             step.description)
            else:
                logging.info(">>> Running step: %s", step.name)
            missing_inputs = step.validate_prereqs(self.prefix)
            if missing_inputs:
                raise app.UsageError(
                    f"{step.name} requires existing inputs: {', '.join(missing_inputs)}; "
                    "run prerequisite steps or provide the files.")
            if not self._confirm_step_execution(step):
                logging.info(
                    "User declined to run step '%s'; stopping execution.",
                    step.name,
                )
                return False

            fingerprint = step.fingerprint(self.prefix, self.config)
            outputs = [str(path) for path in step.outputs(self.prefix)]
            record = {
                "step": step.name,
                "step_version": step.version,
                "inputs_fingerprint": fingerprint,
                "outputs": outputs,
            }
            try:
                step.run(self.prefix, self.config)
            except Exception as exc:  # noqa: BLE001
                record.update({
                    STATUS_KEY: STATUS_FAILED,
                    "updated": datetime.now(timezone.utc).isoformat(),
                    "error": repr(exc),
                })
                steps_state[step.name] = record
                self._write_state()
                logging.info("<<< Completed step: %s (failure)", step.name)
                raise
            else:
                record.update({
                    STATUS_KEY: STATUS_SUCCESS,
                    "updated": datetime.now(timezone.utc).isoformat(),
                })
                steps_state[step.name] = record
                self._write_state()
                logging.info("<<< Completed step: %s (success)", step.name)
        return True

    def execute(self, exec_config: ExecutionConfig) -> bool:
        self._validate_execution_config(exec_config)
        effective_force = exec_config.force
        if exec_config.force and (exec_config.step_name or
                                  exec_config.from_step_name):
            logging.warning(
                "--force is ignored when used with --step or --from_step.")
            effective_force = False

        steps_to_run, skipped, rerun_reasons = self._determine_steps(
            exec_config,
            effective_force,
        )
        state = ExecutionState(
            steps=steps_to_run,
            skipped=skipped,
            rerun_reasons=rerun_reasons,
        )
        self._summarize_plan(
            state.steps,
            state.skipped,
            state.rerun_reasons,
        )
        if not state.steps:
            logging.info("Nothing to do; all steps already satisfied.")
            return True

        ok = self._execute_steps(state.steps)
        if ok:
            logging.info("Execution complete.")
        else:
            logging.info("Execution cancelled by user.")
        return ok


def main(argv: Iterable[str]) -> None:
    del argv  # Unused.
    verbose = FLAGS.verbose
    step = FLAGS.step
    from_step = FLAGS.from_step
    dataset_prefix = FLAGS.dataset_prefix
    sdmx_config = SdmxSourceConfig(
        endpoint=FLAGS.endpoint,
        agency=FLAGS.agency,
        dataflow=FLAGS.dataflow,
        key=tuple(FLAGS.key),
        param=tuple(FLAGS.param),
    )
    workflow_config = WorkflowConfig(
        sdmx=sdmx_config,
        sample_rows=FLAGS.sample_rows,
        verbose=verbose,
        skip_confirmation=FLAGS.skip_confirmation,
        gemini_cli=FLAGS.gemini_cli,
    )

    logging.set_verbosity(logging.DEBUG if verbose else logging.INFO)
    exec_config = ExecutionConfig(
        step_name=step,
        from_step_name=from_step,
        force=FLAGS.force,
    )
    workflow = Workflow(dataset_prefix, workflow_config)
    workflow.execute(exec_config)


if __name__ == "__main__":
    app.run(main)
