"""Command-line coordinator for SDMX agentic import steps (skeleton).

Phase 1: argument parsing, step registry, and path resolution only.
Actual subprocess execution is added in later phases.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


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


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Coordinate SDMX agentic import workflow (skeleton)."
    )
    parser.add_argument(
        "--dataset-prefix",
        required=True,
        help="Prefix used to name all generated files.",
    )
    parser.add_argument("--endpoint", help="SDMX REST API endpoint URL.")
    parser.add_argument("--agency", help="SDMX agency identifier.")
    parser.add_argument("--dataflow", help="SDMX dataflow identifier.")
    parser.add_argument(
        "--key",
        action="append",
        default=[],
        help="SDMX key filter (repeatable).",
    )
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        help="Additional SDMX query parameter (repeatable).",
    )
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=30,
        help="Rows to include when sampling SDMX data.",
    )
    parser.add_argument(
        "--step",
        choices=[step.name for step in STEP_SEQUENCE],
        help="Run only the specified step (overwrites its outputs).",
    )
    parser.add_argument(
        "--from-step",
        choices=[step.name for step in STEP_SEQUENCE],
        help="Run steps starting from the given step through 'run'.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print additional execution details.",
    )
    args = parser.parse_args(argv)
    if args.step and args.from_step:
        parser.error("--step and --from-step cannot be used together.")
    return args


def determine_steps(args: argparse.Namespace) -> List[Step]:
    if args.step:
        return [step for step in STEP_SEQUENCE if step.name == args.step]
    if args.from_step:
        names = [step.name for step in STEP_SEQUENCE]
        start_index = names.index(args.from_step)
        return STEP_SEQUENCE[start_index:]
    return STEP_SEQUENCE


def summarize_plan(prefix: str, steps: List[Step]) -> None:
    print(f"Dataset prefix: {prefix}")
    print("Planned steps:")
    for step in steps:
        print(f"  - {step.name}: {step.description}")
        print("    Inputs:")
        for path in step.inputs(prefix):
            print(f"      * {path}")
        print("    Outputs:")
        for path in step.outputs(prefix):
            print(f"      * {path}")


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    steps_to_run = determine_steps(args)
    summarize_plan(args.dataset_prefix, steps_to_run)
    print("\nPhase 1 skeleton complete. Execution wiring will follow in later phases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

