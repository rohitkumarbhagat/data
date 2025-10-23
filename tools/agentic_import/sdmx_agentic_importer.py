"""Command-line coordinator for SDMX agentic import steps (skeleton).

Phase 1: argument parsing, step registry, and path resolution only.
Actual subprocess execution is added in later phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from absl import app
from absl import flags
from absl import logging

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

SAMPLE_OUTPUT_DIR = Path("sample_output")
FINAL_OUTPUT_DIR = Path("output")
STATE_DIR = Path(".datacommons")


@dataclass(frozen=True)
class Step:
    name: str
    description: str

    def inputs(self, prefix: str) -> List[Path]:
        return STEP_IO[self.name]["inputs"](prefix)

    def outputs(self, prefix: str) -> List[Path]:
        return STEP_IO[self.name]["outputs"](prefix)


def _metadata_inputs(_: str) -> List[Path]:
    return []


def _metadata_outputs(prefix: str) -> List[Path]:
    return [Path(f"{prefix}_metadata.xml")]


def _data_inputs(prefix: str) -> List[Path]:
    return _metadata_outputs(prefix)


def _data_outputs(prefix: str) -> List[Path]:
    return [Path(f"{prefix}_data.csv")]


def _sample_inputs(prefix: str) -> List[Path]:
    return _data_outputs(prefix)


def _sample_outputs(prefix: str) -> List[Path]:
    return [SAMPLE_OUTPUT_DIR / f"{prefix}_sample.csv"]


def _pvmap_inputs(prefix: str) -> List[Path]:
    return [
        SAMPLE_OUTPUT_DIR / f"{prefix}_sample.csv",
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


STEP_SEQUENCE: List[Step] = [
    Step("sdmx-metadata", "Download SDMX metadata"),
    Step("sdmx-data", "Download SDMX data"),
    Step("sample", "Sample SDMX data"),
    Step("pvmap", "Generate PV map from sample"),
    Step("run", "Process full SDMX data"),
]


STEP_IO: Dict[str, Dict[str, callable]] = {
    "sdmx-metadata": {"inputs": _metadata_inputs, "outputs": _metadata_outputs},
    "sdmx-data": {"inputs": _data_inputs, "outputs": _data_outputs},
    "sample": {"inputs": _sample_inputs, "outputs": _sample_outputs},
    "pvmap": {"inputs": _pvmap_inputs, "outputs": _pvmap_outputs},
    "run": {"inputs": _run_inputs, "outputs": _run_outputs},
}

def _validate_step_flags(step: str | None, from_step: str | None) -> None:
    """Ensure step selection flags are valid."""
    if step and from_step:
        raise app.UsageError("--step and --from-step cannot be used together.")
    valid_names = [s.name for s in STEP_SEQUENCE]
    if step and step not in valid_names:
        raise app.UsageError(f"--step must be one of {valid_names}")
    if from_step and from_step not in valid_names:
        raise app.UsageError(f"--from-step must be one of {valid_names}")


def determine_steps(step_name: str | None, from_step_name: str | None) -> List[Step]:
    if step_name:
        return [step for step in STEP_SEQUENCE if step.name == step_name]
    if from_step_name:
        names = [step.name for step in STEP_SEQUENCE]
        start_index = names.index(from_step_name)
        return STEP_SEQUENCE[start_index:]
    return STEP_SEQUENCE


def summarize_plan(prefix: str, steps: List[Step]) -> None:
    logging.info("Dataset prefix: %s", prefix)
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
    dataset_prefix = FLAGS.dataset_prefix

    logging.set_verbosity(logging.DEBUG if verbose else logging.INFO)

    _validate_step_flags(step, from_step)
    steps_to_run = determine_steps(step, from_step)
    summarize_plan(dataset_prefix, steps_to_run)
    logging.info(
        "Phase 1 skeleton complete. Execution wiring will follow in later phases."
    )


if __name__ == "__main__":
    app.run(main)
