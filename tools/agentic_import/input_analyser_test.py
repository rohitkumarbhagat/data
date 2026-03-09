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

import os
import tempfile
import unittest
from pathlib import Path

from tools.agentic_import.input_analyser import Config, InputAnalyser


class InputAnalyserTest(unittest.TestCase):

    def setUp(self):
        self._cwd = os.getcwd()
        self._temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self._temp_dir.name)

        self._data_file = Path('input.csv')
        self._data_file.write_text('place,time,value\ngeoId/06,2024,10\n')
        self._metadata_file = Path('metadata.json')
        self._metadata_file.write_text('{"title": "Sample dataset"}')
        self._previous_analysis = Path('previous_analysis.json')
        self._previous_analysis.write_text('{"feedback_context": {}}')
        self._category_taxonomy = Path('category_taxonomy.json')
        self._category_taxonomy.write_text('{"categories": []}')

    def tearDown(self):
        os.chdir(self._cwd)
        self._temp_dir.cleanup()

    def _make_analyser(self,
                       *,
                       is_sdmx: bool,
                       include_optional_inputs: bool = True,
                       working_dir: str = None) -> InputAnalyser:
        return InputAnalyser(
            Config(
                input_data=[str(self._data_file)],
                input_metadata=[str(self._metadata_file)],
                output_path='output/demo',
                is_sdmx_dataset=is_sdmx,
                previous_analysis=(str(self._previous_analysis)
                                   if include_optional_inputs else None),
                category_taxonomy_json=(str(self._category_taxonomy)
                                        if include_optional_inputs else None),
                dry_run=True,
                working_dir=working_dir,
            ))

    def _read_prompt_text(self, analyser: InputAnalyser) -> str:
        result = analyser.analyse()
        self.assertTrue(result.run_dir.is_dir())
        self.assertTrue(result.prompt_path.is_file())
        self.assertTrue(result.gemini_log_path.is_absolute())
        self.assertIn(str(result.prompt_path), result.gemini_command)
        self.assertIn(str(result.gemini_log_path), result.gemini_command)
        return result.prompt_path.read_text()

    def test_generate_prompt_csv(self):
        analyser = self._make_analyser(is_sdmx=False)
        prompt_text = self._read_prompt_text(analyser)
        self.assertIn(str(self._data_file.resolve()), prompt_text)
        self.assertIn(str(self._metadata_file.resolve()), prompt_text)
        self.assertIn('demo_analysis.json', prompt_text)
        self.assertIn('dc_kb_prompts', prompt_text)
        self.assertIn('matched_existing', prompt_text)
        self.assertNotIn('NotebookLM', prompt_text)
        self.assertIn(str(self._previous_analysis.resolve()), prompt_text)
        self.assertIn(str(self._category_taxonomy.resolve()), prompt_text)
        self.assertIn('"dataset_type": "csv"', prompt_text)

    def test_generate_prompt_sdmx(self):
        analyser = self._make_analyser(is_sdmx=True)
        prompt_text = self._read_prompt_text(analyser)
        self.assertIn('"dataset_type": "sdmx"', prompt_text)
        self.assertIn('SDMX DATASET DETECTED', prompt_text)
        self.assertIn('extracted SDMX JSON', prompt_text)

    def test_generate_prompt_without_optional_inputs(self):
        analyser = self._make_analyser(is_sdmx=False,
                                       include_optional_inputs=False)
        prompt_text = self._read_prompt_text(analyser)
        self.assertIn('"previous_analysis": ""', prompt_text)
        self.assertIn('"category_taxonomy_json": ""', prompt_text)

    def test_rejects_multiple_input_files(self):
        extra_file = Path('input2.csv')
        extra_file.write_text('header\nvalue')
        with self.assertRaises(ValueError):
            InputAnalyser(
                Config(
                    input_data=[str(self._data_file),
                                str(extra_file)],
                    input_metadata=[str(self._metadata_file)],
                    output_path='output/demo',
                    dry_run=True,
                ))

    def test_rejects_paths_outside_working_directory(self):
        with tempfile.TemporaryDirectory() as other_dir:
            external_file = Path(other_dir) / 'external.csv'
            external_file.write_text('header\nvalue')
            with self.assertRaises(ValueError):
                InputAnalyser(
                    Config(
                        input_data=[str(external_file)],
                        input_metadata=[str(self._metadata_file)],
                        output_path='output/demo',
                        dry_run=True,
                    ))

    def test_generate_prompt_with_relative_working_dir(self):
        sub_dir = Path(self._temp_dir.name) / 'sub_working_dir'
        sub_dir.mkdir()

        data_file = sub_dir / 'input.csv'
        data_file.write_text('place,time,value\ngeoId/06,2024,10\n')
        metadata_file = sub_dir / 'metadata.json'
        metadata_file.write_text('{"title": "Sample dataset"}')

        analyser = InputAnalyser(
            Config(
                input_data=['input.csv'],
                input_metadata=['metadata.json'],
                output_path='output/demo',
                dry_run=True,
                working_dir='sub_working_dir',
            ))

        prompt_text = self._read_prompt_text(analyser)
        self.assertIn(str(data_file.resolve()), prompt_text)
        self.assertIn(str(metadata_file.resolve()), prompt_text)
        self.assertIn(str(sub_dir.resolve()), prompt_text)

    def test_rejects_invalid_output_path(self):
        with self.assertRaises(ValueError):
            InputAnalyser(
                Config(
                    input_data=[str(self._data_file)],
                    input_metadata=[str(self._metadata_file)],
                    output_path='',
                    dry_run=True,
                ))
        with self.assertRaises(ValueError):
            InputAnalyser(
                Config(
                    input_data=[str(self._data_file)],
                    input_metadata=[str(self._metadata_file)],
                    output_path='output',
                    dry_run=True,
                ))


if __name__ == '__main__':
    unittest.main()
