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

import json
import subprocess
import unittest

from tools.import_differ.bq import import_version_to_bq


class ImportVersionToBqTest(unittest.TestCase):

    def test_sanitize_identifier(self):
        self.assertEqual(
            'US_Urban_Schools_Teachers_And_Staff',
            import_version_to_bq.sanitize_identifier(
                'US-Urban.Schools/Teachers_And_Staff'))
        self.assertEqual('2026_08_14T22_03_06',
                         import_version_to_bq.sanitize_identifier(
                             '2026-08-14T22:03:06'))

    def test_parse_version_from_gcs_dir(self):
        version_dir = 'gs://datcom-prod-imports/statvar_imports/us_urban_school/teachers/US_Urban_Schools_Teachers_And_Staff/2026_08_14T22_03_06_397467_07_00/'
        self.assertEqual(
            '2026_08_14T22_03_06_397467_07_00',
            import_version_to_bq.parse_version_from_gcs_dir(version_dir))

    def test_fetch_import_summary(self):
        summary_payload = {'import_name': 'US_Urban_Schools_Teachers_And_Staff'}

        def fake_runner(cmd, **kwargs):
            self.assertEqual(['gcloud', 'storage', 'cat',
                              'gs://bucket/import/v1/import_summary.json'], cmd)
            return subprocess.CompletedProcess(
                cmd, 0, stdout=json.dumps(summary_payload), stderr='')

        summary = import_version_to_bq.fetch_import_summary(
            'gs://bucket/import/v1', runner=fake_runner)
        self.assertEqual('US_Urban_Schools_Teachers_And_Staff',
                         summary['import_name'])

    def test_list_table_mcf_files_none_found(self):
        def fake_runner(cmd, **kwargs):
            return subprocess.CompletedProcess(
                cmd, 1, stdout='', stderr='One or more URLs matched no objects.')

        files = import_version_to_bq.list_table_mcf_files(
            'gs://bucket/import/v1', runner=fake_runner)
        self.assertEqual([], files)

    def test_end_to_end_single_mcf_flow(self):
        commands_run = []

        def fake_runner(cmd, **kwargs):
            commands_run.append(list(cmd))
            cmd_str = ' '.join(str(c) for c in cmd)

            # 1. Fetch import_summary.json
            if 'storage cat' in cmd_str:
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout=json.dumps({'import_name': 'US_Urban_Schools'}),
                    stderr='')

            # 2. List MCF files
            if 'storage ls' in cmd_str and '/input*/genmcf/table_mcf_*.mcf' in cmd_str:
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout='gs://bucket/import/2026_08_14/input0/genmcf/table_mcf_data.mcf\n',
                    stderr='')

            # 3. Check Parquet dir (initially empty)
            if 'storage ls' in cmd_str and 'table_mcf_data_parquet/*.parquet' in cmd_str:
                return subprocess.CompletedProcess(
                    cmd, 1, stdout='', stderr='No URLs matched')

            # 4. Generate Parquet script execution
            if 'gcs_mcf_to_parquet.sh' in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')

            # 5. Check BigQuery table exists (initially does not exist)
            if 'bq' in cmd_str and 'show' in cmd_str:
                return subprocess.CompletedProcess(cmd, 1, stdout='', stderr='Not found')

            # 6. Load Parquet to BigQuery script execution
            if 'load_gcs_parquet_to_bigquery.sh' in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')

            return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')

        summary = import_version_to_bq.import_version_to_bq(
            version_gcs_dir='gs://bucket/import/2026_08_14',
            project='test-project',
            dataset='test_dataset',
            replace_bq_table=False,
            workers=4,
            runner=fake_runner,
        )

        self.assertEqual('US_Urban_Schools', summary['import_name'])
        self.assertEqual('2026_08_14', summary['version'])
        self.assertEqual(1, summary['processed_count'])

        table_info = summary['tables'][0]
        self.assertEqual('input0', table_info['input_folder'])
        self.assertEqual(
            'test-project:test_dataset.US_Urban_Schools__2026_08_14__input0',
            table_info['bq_table'])
        self.assertEqual('GENERATED', table_info['parquet_status'])
        self.assertEqual('CREATED', table_info['bq_status'])
        generate_command = next(command for command in commands_run
                                if 'gcs_mcf_to_parquet.sh' in str(command[0]))
        self.assertEqual(
            '4', generate_command[generate_command.index('--workers') + 1])

    def test_multiple_mcfs_in_single_input_generates_distinct_table_names(self):
        def fake_runner(cmd, **kwargs):
            cmd_str = ' '.join(str(c) for c in cmd)
            if 'storage cat' in cmd_str:
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout=json.dumps({'import_name': 'Multi_Table_Import'}),
                    stderr='')
            if 'storage ls' in cmd_str and '/input*/genmcf/table_mcf_*.mcf' in cmd_str:
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout=('gs://bucket/import/v1/input0/genmcf/table_mcf_obs.mcf\n'
                            'gs://bucket/import/v1/input0/genmcf/table_mcf_events.mcf\n'),
                    stderr='')
            if 'storage ls' in cmd_str and '*.parquet' in cmd_str:
                # Parquet already exists
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout='gs://bucket/import/v1/input0/genmcf/table_mcf_obs_parquet/part-00000.parquet\n',
                    stderr='')
            if 'bq' in cmd_str and 'show' in cmd_str:
                # Table already exists
                return subprocess.CompletedProcess(cmd, 0, stdout='Table details', stderr='')
            return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')

        summary = import_version_to_bq.import_version_to_bq(
            version_gcs_dir='gs://bucket/import/v1',
            project='test-project',
            dataset='test_dataset',
            replace_bq_table=False,
            runner=fake_runner,
        )

        self.assertEqual(2, summary['processed_count'])
        table_names = [t['bq_table'] for t in summary['tables']]
        self.assertIn('test-project:test_dataset.Multi_Table_Import__v1__input0__table_mcf_obs',
                      table_names)
        self.assertIn('test-project:test_dataset.Multi_Table_Import__v1__input0__table_mcf_events',
                      table_names)
        self.assertEqual('SKIPPED_ALREADY_EXISTS', summary['tables'][0]['parquet_status'])
        self.assertEqual('SKIPPED_ALREADY_EXISTS', summary['tables'][0]['bq_status'])

    def test_replace_bq_table_forces_load_when_table_exists(self):
        loaded_tables = []

        def fake_runner(cmd, **kwargs):
            cmd_str = ' '.join(str(c) for c in cmd)
            if 'storage cat' in cmd_str:
                return subprocess.CompletedProcess(
                    cmd, 0, stdout=json.dumps({'import_name': 'My_Import'}), stderr='')
            if 'storage ls' in cmd_str and '/input*/genmcf/table_mcf_*.mcf' in cmd_str:
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout='gs://bucket/import/v1/input0/genmcf/table_mcf_data.mcf\n',
                    stderr='')
            if 'storage ls' in cmd_str and '*.parquet' in cmd_str:
                return subprocess.CompletedProcess(
                    cmd, 0, stdout='part-00000.parquet\n', stderr='')
            if 'bq' in cmd_str and 'show' in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout='Table details', stderr='')
            if 'load_gcs_parquet_to_bigquery.sh' in cmd_str:
                loaded_tables.append(cmd)
                return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')
            return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')

        summary = import_version_to_bq.import_version_to_bq(
            version_gcs_dir='gs://bucket/import/v1',
            project='test-project',
            dataset='test_dataset',
            replace_bq_table=True,
            runner=fake_runner,
        )

        self.assertEqual(1, len(loaded_tables))
        self.assertIn('--replace-bq-table', loaded_tables[0])
        self.assertEqual('REPLACED', summary['tables'][0]['bq_status'])


if __name__ == '__main__':
    unittest.main()
