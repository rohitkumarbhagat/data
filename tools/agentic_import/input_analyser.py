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
"""Analyze one input dataset and generate structured JSON guidance."""

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = Path(_SCRIPT_DIR).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from absl import app
from absl import flags
from absl import logging

from tools.agentic_import.common.gemini_prompt_runner import (
    GeminiPromptRunner, GeminiRunResult)

_FLAGS = flags.FLAGS


def _define_flags():
    try:
        flags.DEFINE_list('input_data', None,
                          'List of input data file paths (required)')
        flags.mark_flag_as_required('input_data')

        flags.DEFINE_list('input_metadata', [],
                          'List of input metadata file paths (optional)')

        flags.DEFINE_string(
            'output_path', None,
            'Output path prefix for generated analysis artifacts (required)')
        flags.mark_flag_as_required('output_path')

        flags.DEFINE_boolean(
            'sdmx_dataset', False,
            'Whether the dataset is an SDMX dataset using extracted metadata JSON'
        )

        flags.DEFINE_string(
            'previous_analysis', None,
            'Path to a previous analysis JSON to reuse human feedback from')

        flags.DEFINE_string(
            'category_taxonomy_json', None,
            'Path to a category taxonomy JSON used as prior guidance')

        flags.DEFINE_boolean('dry_run', False,
                             'Generate prompt only without calling Gemini CLI')

        flags.DEFINE_boolean(
            'skip_confirmation', False,
            'Skip user confirmation before running Gemini CLI')

        flags.DEFINE_boolean(
            'enable_sandboxing',
            platform.system() == 'Darwin',
            'Enable sandboxing for Gemini CLI (default: True on macOS, False elsewhere)'
        )

        flags.DEFINE_string(
            'gemini_cli', 'gemini',
            'Custom path or command to invoke Gemini CLI. '
            'Example: "/usr/local/bin/gemini". '
            'WARNING: This value is executed in a shell - use only with trusted input.'
        )

        flags.DEFINE_string(
            'working_dir', None,
            'Working directory for the run (default: current directory)')
    except flags.DuplicateFlagError:
        pass


@dataclass
class Config:
    input_data: List[str]
    input_metadata: List[str]
    output_path: str
    is_sdmx_dataset: bool = False
    previous_analysis: Optional[str] = None
    category_taxonomy_json: Optional[str] = None
    dry_run: bool = False
    skip_confirmation: bool = False
    enable_sandboxing: bool = False
    gemini_cli: Optional[str] = None
    working_dir: Optional[str] = None


class InputAnalyser:
    """Generate dataset analysis guidance with Gemini CLI."""

    def __init__(self, config: Config):
        self._config = config
        self._working_dir = Path(
            config.working_dir).resolve() if config.working_dir else Path.cwd()
        if self._working_dir.exists() and not self._working_dir.is_dir():
            raise ValueError(
                f"working_dir is not a directory: {self._working_dir}")
        self._working_dir.mkdir(parents=True, exist_ok=True)

        if not self._config.input_data:
            raise ValueError("input_data must contain at least one file.")
        if len(self._config.input_data) != 1:
            raise ValueError(
                f"Currently only single input data file is supported. "
                f"Found {len(self._config.input_data)} files.")

        self._input_data = [
            self._resolve_and_validate_path(path)
            for path in self._config.input_data
        ]
        self._input_metadata = [
            self._resolve_and_validate_path(path)
            for path in self._config.input_metadata
        ]
        self._previous_analysis = (self._resolve_and_validate_path(
            self._config.previous_analysis)
                                   if self._config.previous_analysis else None)
        self._category_taxonomy = (
            self._resolve_and_validate_path(self._config.category_taxonomy_json)
            if self._config.category_taxonomy_json else None)

        output_path_raw = self._config.output_path
        if not output_path_raw or not output_path_raw.strip():
            raise ValueError(
                "output_path must be a non-empty string in <dir>/<prefix> format"
            )
        output_prefix = Path(output_path_raw).expanduser()
        if len(output_prefix.parts) < 2:
            raise ValueError("output_path must include a directory and prefix")
        if not output_prefix.is_absolute():
            output_prefix = self._working_dir / output_prefix
        self._output_prefix = output_prefix.resolve()
        self._analysis_output_path = (
            self._output_prefix.parent /
            f"{self._output_prefix.name}_analysis.json")
        self._analysis_output_path.parent.mkdir(parents=True, exist_ok=True)

        self._runner = GeminiPromptRunner(
            dataset_prefix=self._output_prefix.name,
            working_dir=str(self._working_dir),
            dry_run=self._config.dry_run,
            skip_confirmation=self._config.skip_confirmation,
            enable_sandboxing=self._config.enable_sandboxing,
            gemini_cli=self._config.gemini_cli,
        )

    def analyse(self) -> GeminiRunResult:
        prompt_file = self._generate_prompt()
        return self._runner.run(
            prompt_file,
            log_filename='gemini_cli.log',
            confirm_fn=self._get_user_confirmation,
            cancel_log_message="Input analysis cancelled by user.",
        )

    def _resolve_and_validate_path(self, path: str) -> Path:
        resolved = Path(path).expanduser()
        if not resolved.is_absolute():
            resolved = self._working_dir / resolved
        real_path = resolved.resolve()
        working_dir = self._working_dir.resolve()
        try:
            real_path.relative_to(working_dir)
        except ValueError as exc:
            raise ValueError(
                f"Path '{path}' is outside working directory '{working_dir}'")
        return real_path

    def _generate_prompt(self) -> Path:
        template_dir = Path(_SCRIPT_DIR) / 'templates'
        input_metadata_abs = [str(path) for path in self._input_metadata]
        previous_analysis_abs = (str(self._previous_analysis)
                                 if self._previous_analysis else "")
        category_taxonomy_abs = (str(self._category_taxonomy)
                                 if self._category_taxonomy else "")
        dataset_type = 'sdmx' if self._config.is_sdmx_dataset else 'csv'

        return self._runner.render_prompt(
            template_dir=template_dir,
            template_name='input_analysis_prompt.j2',
            context={
                'working_dir_abs': str(self._working_dir),
                'input_data_abs': str(self._input_data[0]),
                'input_metadata_abs': input_metadata_abs,
                'analysis_output_path_abs': str(self._analysis_output_path),
                'output_prefix_abs': str(self._output_prefix),
                'dataset_type': dataset_type,
                'previous_analysis_abs': previous_analysis_abs,
                'category_taxonomy_abs': category_taxonomy_abs,
            },
            prompt_filename='input_analysis_prompt.md',
        )

    def _get_user_confirmation(self, prompt_file: Path) -> bool:
        print("\n" + "=" * 60)
        print("INPUT ANALYSIS SUMMARY")
        print("=" * 60)
        print(f"Input data file: {self._input_data[0]}")
        print(f"Input metadata files: {self._input_metadata}")
        print(
            f"Dataset type: {'SDMX' if self._config.is_sdmx_dataset else 'CSV'}"
        )
        print(f"Analysis output file: {self._analysis_output_path}")
        if self._previous_analysis:
            print(f"Previous analysis: {self._previous_analysis}")
        if self._category_taxonomy:
            print(f"Category taxonomy: {self._category_taxonomy}")
        print(f"Prompt file: {prompt_file}")
        print(f"Working directory: {self._working_dir}")
        print(
            f"Sandboxing: {'Enabled' if self._config.enable_sandboxing else 'Disabled'}"
        )
        if not self._config.enable_sandboxing:
            print(
                "WARNING: Sandboxing is disabled. Gemini will run without safety restrictions."
            )
        print("=" * 60)

        while True:
            try:
                response = input(
                    "Ready to run Gemini for input analysis? (y/n): ").strip(
                    ).lower()
                if response in ['y', 'yes']:
                    return True
                if response in ['n', 'no']:
                    print("Input analysis cancelled by user.")
                    return False
                print("Please enter 'y' or 'n'.")
            except KeyboardInterrupt:
                print("\nInput analysis cancelled by user.")
                return False


def prepare_config() -> Config:
    return Config(input_data=_FLAGS.input_data or [],
                  input_metadata=_FLAGS.input_metadata or [],
                  output_path=_FLAGS.output_path,
                  is_sdmx_dataset=_FLAGS.sdmx_dataset,
                  previous_analysis=_FLAGS.previous_analysis,
                  category_taxonomy_json=_FLAGS.category_taxonomy_json,
                  dry_run=_FLAGS.dry_run,
                  skip_confirmation=_FLAGS.skip_confirmation,
                  enable_sandboxing=_FLAGS.enable_sandboxing,
                  gemini_cli=_FLAGS.gemini_cli,
                  working_dir=_FLAGS.working_dir)


def main(_):
    config = prepare_config()
    logging.info(
        f"Loaded input analysis config with {len(config.input_data)} data files "
        f"and {len(config.input_metadata)} metadata files")

    analyser = InputAnalyser(config)
    analyser.analyse()

    logging.info("Input analysis completed.")
    return 0


if __name__ == '__main__':
    _define_flags()
    app.run(main)
