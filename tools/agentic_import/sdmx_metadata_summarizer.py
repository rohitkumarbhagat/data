# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Summarizer tool for SDMX metadata enrichment using Gemini CLI."""

import os
import subprocess
from typing import List

from absl import app
from absl import flags
from absl import logging
from jinja2 import Environment, FileSystemLoader

_FLAGS = flags.FLAGS
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _define_flags() -> None:
    try:
        flags.DEFINE_string('input_items_json', None,
                            'Path to candidate items JSON file (required).')
        flags.DEFINE_string('input_search_json', None,
                            'Path to search results JSON file (required).')
        flags.DEFINE_string('output_path', None,
                            'Path to output patch JSON file (required).')
        flags.mark_flag_as_required('input_items_json')
        flags.mark_flag_as_required('input_search_json')
        flags.mark_flag_as_required('output_path')
    except flags.DuplicateFlagError:
        pass


def _build_prompt(
    input_items_path: str,
    input_search_path: str,
    output_path: str,
) -> str:
    template_dir = os.path.join(_SCRIPT_DIR, 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('enrich_sdmx_metadata_prompt.j2')
    return template.render(
        input_items_path=os.path.abspath(input_items_path),
        input_search_path=os.path.abspath(input_search_path),
        output_path=os.path.abspath(output_path),
    )


def _write_prompt(prompt_text: str, output_path: str) -> str:
    prompt_path = f"{output_path}.prompt.md"
    with open(prompt_path, 'w') as f:
        f.write(prompt_text)
    return prompt_path


def _run_gemini(prompt_path: str) -> None:
    command = f"cat '{prompt_path}' | gemini -y"
    result = subprocess.run(command, shell=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Gemini CLI failed with exit code {result.returncode}")


def run_summarizer(
    input_items_path: str,
    input_search_path: str,
    output_path: str,
) -> None:
    prompt_text = _build_prompt(input_items_path, input_search_path,
                                output_path)
    prompt_path = _write_prompt(prompt_text, output_path)
    logging.info(f"Wrote prompt to: {prompt_path}")
    _run_gemini(prompt_path)
    logging.info(f"Summarizer completed. Output path: {output_path}")


def main(_: List[str]) -> None:
    run_summarizer(
        input_items_path=_FLAGS.input_items_json,
        input_search_path=_FLAGS.input_search_json,
        output_path=_FLAGS.output_path,
    )


if __name__ == '__main__':
    _define_flags()
    app.run(main)
