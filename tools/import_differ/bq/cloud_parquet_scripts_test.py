# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

_SCRIPT_DIR = Path(__file__).parent
_GCS_SCRIPT = _SCRIPT_DIR / 'gcs_mcf_to_parquet.sh'
_BQ_SCRIPT = _SCRIPT_DIR / 'load_gcs_parquet_to_bigquery.sh'

_GCLOUD_MOCK = r'''#!/bin/bash
printf '%s\n' "$*" >> "$COMMAND_LOG"
if [[ "$1" == "storage" && "$2" == "objects" && "$3" == "describe" ]]; then
  [[ "${MOCK_GCS_INPUT_EXISTS:-1}" == "1" ]]
  exit $?
fi
if [[ "$1" == "storage" && "$2" == "buckets" && "$3" == "describe" ]]; then
  [[ "${MOCK_GCS_OUTPUT_BUCKET_EXISTS:-1}" == "1" ]]
  exit $?
fi
if [[ "$1" == "storage" && "$2" == "ls" ]]; then
  if [[ "$3" == *"/*.parquet" ]]; then
    if [[ "${MOCK_PARQUET_EXISTS:-1}" == "1" ]]; then
      echo "gs://output/parquet/part-00000.parquet"
      exit 0
    fi
    echo "One or more URLs matched no objects." >&2
    exit 1
  fi
  if [[ "${MOCK_GCS_HAS_FILES:-}" == "1" ]]; then
    echo "gs://output/parquet/part-00000.parquet"
    exit 0
  fi
  echo "One or more URLs matched no objects." >&2
  exit 1
fi
if [[ "$1" == "storage" && "$2" == "cp" && "$3" == gs://* ]]; then
  printf '%s\n' \
    'Node: dcid:observation1' \
    'typeOf: dcid:StatVarObservation' \
    'variableMeasured: dcid:Count_Person' \
    'observationAbout: dcid:country/USA' \
    'value: 100' \
    '' \
    'Node: dcid:observation2' \
    'typeOf: dcid:StatVarObservation' \
    'variableMeasured: dcid:Count_Person' \
    'observationAbout: dcid:country/IND' \
    'value: 200' \
    '' > "${@: -1}"
fi
'''

_BQ_MOCK = r'''#!/bin/bash
printf '%s\n' "$*" >> "$COMMAND_LOG"
if [[ " $* " == *" show --dataset "* ]]; then
  [[ "${MOCK_BQ_DATASET_EXISTS:-1}" == "1" ]]
  exit $?
fi
if [[ " $* " == *" show "* ]]; then
  [[ "${MOCK_BQ_TABLE_EXISTS:-}" == "1" ]]
  exit $?
fi
'''


class CloudParquetScriptsTest(unittest.TestCase):

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._root = Path(self._temp_dir.name)
        self._bin_dir = self._root / 'bin'
        self._bin_dir.mkdir()
        self._command_log = self._root / 'commands.log'
        self._write_command('gcloud', _GCLOUD_MOCK)
        self._write_command('bq', _BQ_MOCK)
        self._env = os.environ.copy()
        self._env['PATH'] = f'{self._bin_dir}:{self._env["PATH"]}'
        self._env['COMMAND_LOG'] = str(self._command_log)

    def tearDown(self):
        self._temp_dir.cleanup()

    def _write_command(self, name: str, contents: str):
        path = self._bin_dir / name
        path.write_text(contents, encoding='utf-8')
        path.chmod(0o755)

    def _run(self, script: Path, *args: str, **env_values):
        env = self._env.copy()
        env.update(env_values)
        return subprocess.run([str(script), *args],
                              env=env,
                              capture_output=True,
                              text=True,
                              check=False)

    def _gcs_args(self):
        return (
            '--input-gcs-file',
            'gs://input/nodes-deleted.mcf',
            '--output-gcs-dir',
            'gs://output/parquet',
            '--shard-size-bytes',
            '1',
        )

    def test_gcs_script_help_is_self_contained(self):
        result = self._run(_GCS_SCRIPT, '--help')

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('Required options:', result.stdout)
        self.assertIn('Preflight checks:', result.stdout)
        self.assertIn('Default: 524288000', result.stdout)

    def test_gcs_script_fails_when_output_contains_files(self):
        result = self._run(_GCS_SCRIPT,
                           *self._gcs_args(),
                           MOCK_GCS_HAS_FILES='1')

        self.assertNotEqual(0, result.returncode)
        self.assertIn('already contains files', result.stderr)
        self.assertNotIn('storage cp', self._command_log.read_text())

    def test_gcs_script_validates_input_before_processing(self):
        result = self._run(_GCS_SCRIPT,
                           *self._gcs_args(),
                           MOCK_GCS_INPUT_EXISTS='0')

        self.assertNotEqual(0, result.returncode)
        self.assertIn('input object does not exist', result.stderr)
        self.assertNotIn('storage cp', self._command_log.read_text())

    def test_gcs_script_retains_temp_directory_by_default(self):
        result = self._run(_GCS_SCRIPT, *self._gcs_args())

        self.assertEqual(0, result.returncode, result.stderr)
        prefix = 'Retained temporary directory: '
        temp_dir = Path(
            next(
                line.removeprefix(prefix)
                for line in result.stdout.splitlines()
                if line.startswith(prefix)))
        self.assertTrue(temp_dir.is_dir())
        self.assertEqual(
            2, len(list((temp_dir / 'output/parquet').glob('*.parquet'))))
        shutil.rmtree(temp_dir)

    def test_gcs_script_cleans_temp_directory_when_requested(self):
        result = self._run(_GCS_SCRIPT, *self._gcs_args(), '--cleanup-temp')

        self.assertEqual(0, result.returncode, result.stderr)
        prefix = 'Temporary directory: '
        temp_dir = Path(
            next(
                line.removeprefix(prefix)
                for line in result.stdout.splitlines()
                if line.startswith(prefix)))
        self.assertFalse(temp_dir.exists())

    def _bq_args(self):
        return (
            '--parquet-gcs-dir',
            'gs://output/parquet',
            '--project',
            'my-project',
            '--dataset',
            'my_dataset',
            '--table',
            'deleted_nodes',
        )

    def test_bq_script_help_is_self_contained(self):
        result = self._run(_BQ_SCRIPT, '--help')

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('Required options:', result.stdout)
        self.assertIn('Preflight checks:', result.stdout)
        self.assertIn('Default: 86400', result.stdout)

    def test_bq_script_fails_when_table_exists(self):
        result = self._run(_BQ_SCRIPT,
                           *self._bq_args(),
                           MOCK_BQ_TABLE_EXISTS='1')

        self.assertNotEqual(0, result.returncode)
        self.assertIn('already exists', result.stderr)
        self.assertNotIn(' load ', f' {self._command_log.read_text()} ')

    def test_bq_script_validates_parquet_before_loading(self):
        result = self._run(_BQ_SCRIPT,
                           *self._bq_args(),
                           MOCK_PARQUET_EXISTS='0')

        self.assertNotEqual(0, result.returncode)
        self.assertIn('No accessible Parquet files', result.stderr)
        self.assertNotIn(' load ', f' {self._command_log.read_text()} ')

    def test_bq_script_validates_dataset_before_loading(self):
        result = self._run(_BQ_SCRIPT,
                           *self._bq_args(),
                           MOCK_BQ_DATASET_EXISTS='0')

        self.assertNotEqual(0, result.returncode)
        self.assertIn('dataset does not exist', result.stderr)
        self.assertNotIn(' load ', f' {self._command_log.read_text()} ')

    def test_bq_script_replaces_table_only_with_replace_flag(self):
        result = self._run(_BQ_SCRIPT,
                           *self._bq_args(),
                           '--replace-bq-table',
                           MOCK_BQ_TABLE_EXISTS='1')

        self.assertEqual(0, result.returncode, result.stderr)
        commands = self._command_log.read_text()
        self.assertIn('--replace=true', commands)
        self.assertIn('update --expiration=86400', commands)

    def test_bq_script_accepts_custom_ttl(self):
        result = self._run(_BQ_SCRIPT, *self._bq_args(), '--ttl-seconds',
                           '172800')

        self.assertEqual(0, result.returncode, result.stderr)
        commands = self._command_log.read_text()
        self.assertNotIn('--replace=true', commands)
        self.assertIn('update --expiration=172800', commands)


if __name__ == '__main__':
    unittest.main()
