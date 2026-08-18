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
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.import_differ.bq import import_version_to_bq


class ImportVersionToBqTest(unittest.TestCase):

    def _write_manifest(self, repo_root: Path, relative_dir: str,
                        import_name: str, template_mcfs: list[str]):
        manifest_dir = repo_root / relative_dir
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            'import_specifications': [{
                'import_name':
                    import_name,
                'import_inputs': [{
                    'template_mcf': template_mcf
                } for template_mcf in template_mcfs],
            }]
        }
        (manifest_dir / 'manifest.json').write_text(json.dumps(manifest),
                                                    encoding='utf-8')

    def test_sanitize_identifier(self):
        self.assertEqual(
            'US_Urban_Schools_Teachers_And_Staff',
            import_version_to_bq.sanitize_identifier(
                'US-Urban.Schools/Teachers_And_Staff'))
        self.assertEqual(
            '2026_08_14T22_03_06',
            import_version_to_bq.sanitize_identifier('2026-08-14T22:03:06'))

    def test_resolve_import_spec_finds_exact_import_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self._write_manifest(repo_root, 'scripts/example', 'Target_Import',
                                 ['output/data.tmcf'])
            self._write_manifest(repo_root, 'statvar_imports/other',
                                 'Other_Import', ['other.tmcf'])

            import_path, spec = import_version_to_bq.resolve_import_spec(
                'Target_Import', repo_root)

        self.assertEqual('scripts/example', import_path)
        self.assertEqual('Target_Import', spec['import_name'])

    def test_resolve_import_spec_rejects_duplicate_import_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self._write_manifest(repo_root, 'scripts/one', 'Duplicate_Import',
                                 ['one.tmcf'])
            self._write_manifest(repo_root, 'statvar_imports/two',
                                 'Duplicate_Import', ['two.tmcf'])

            with self.assertRaisesRegex(ValueError, 'defined more than once'):
                import_version_to_bq.resolve_import_spec(
                    'Duplicate_Import', repo_root)

    def test_resolve_version_reads_latest_and_staging_markers(self):

        def fake_runner(cmd, **kwargs):
            if cmd[-1].endswith('latest_version.txt'):
                return subprocess.CompletedProcess(cmd,
                                                   0,
                                                   stdout='version_latest\n',
                                                   stderr='')
            if cmd[-1].endswith('staging_version.txt'):
                return subprocess.CompletedProcess(cmd,
                                                   0,
                                                   stdout='version_staging\n',
                                                   stderr='')
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=('gs://bucket/import/version_latest/\n'
                        'gs://bucket/import/version_staging/\n'),
                stderr='')

        self.assertEqual(
            'version_latest',
            import_version_to_bq.resolve_version('gs://bucket/import',
                                                 'latest',
                                                 runner=fake_runner))
        self.assertEqual(
            'version_staging',
            import_version_to_bq.resolve_version('gs://bucket/import',
                                                 'staging',
                                                 runner=fake_runner))

    def test_resolve_version_last_run_uses_max_timestamp_folder(self):

        def fake_runner(cmd, **kwargs):
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=(
                    'gs://bucket/import/manual/\n'
                    'gs://bucket/import/2026_08_13T10_00_00_000000_00_00/\n'
                    'gs://bucket/import/2026_08_14T09_00_00_000000_00_00/\n'),
                stderr='')

        self.assertEqual(
            '2026_08_14T09_00_00_000000_00_00',
            import_version_to_bq.resolve_version('gs://bucket/import',
                                                 'last_run',
                                                 runner=fake_runner))

    def test_fetch_import_summary_is_optional_but_must_match(self):

        def missing_runner(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd,
                                               1,
                                               stdout='',
                                               stderr='No URLs matched')

        self.assertIsNone(
            import_version_to_bq.fetch_import_summary('gs://bucket/import/v1',
                                                      'Expected_Import',
                                                      runner=missing_runner))

        def mismatch_runner(cmd, **kwargs):
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({'import_name': 'Other_Import'}),
                stderr='')

        with self.assertRaisesRegex(ValueError, 'Import name mismatch'):
            import_version_to_bq.fetch_import_summary('gs://bucket/import/v1',
                                                      'Expected_Import',
                                                      runner=mismatch_runner)

    def test_resolve_import_inputs_uses_input_number_then_template_name(self):
        import_spec = {
            'import_name':
                'Example_Import',
            'import_inputs': [{
                'template_mcf': 'output/first.tmcf'
            }, {
                'template_mcf': 'output/second.tmcf'
            }],
        }

        resolved = import_version_to_bq.resolve_import_inputs(
            import_spec, 'gs://bucket/import/v1', None, ['input0', 'second'])

        self.assertEqual(['input0', 'second'], resolved)

    def test_resolve_import_inputs_validates_explicit_names(self):
        with self.assertRaisesRegex(ValueError, 'was not found'):
            import_version_to_bq.resolve_import_inputs({},
                                                       'gs://bucket/import/v1',
                                                       ['requested'],
                                                       ['input0'])

    def test_list_table_mcf_files_prefers_genmcf_folder(self):
        patterns = []

        def fake_runner(cmd, **kwargs):
            patterns.append(cmd[3])
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=
                'gs://bucket/import/v1/input0/genmcf/table_mcf_data.mcf\n',
                stderr='')

        files = import_version_to_bq.list_table_mcf_files(
            'gs://bucket/import/v1', 'input0', runner=fake_runner)

        self.assertEqual(
            ['gs://bucket/import/v1/input0/genmcf/table_mcf_data.mcf'], files)
        self.assertEqual(
            ['gs://bucket/import/v1/input0/genmcf/table_mcf_*.mcf'], patterns)

    def test_list_table_mcf_files_falls_back_to_validation_folder(self):
        patterns = []

        def fake_runner(cmd, **kwargs):
            pattern = cmd[3]
            patterns.append(pattern)
            if '/validation/' not in pattern:
                return subprocess.CompletedProcess(cmd,
                                                   1,
                                                   stdout='',
                                                   stderr='No URLs matched')
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=
                ('gs://bucket/import/v1/input0/validation/table_mcf_data.mcf\n'
                ),
                stderr='')

        files = import_version_to_bq.list_table_mcf_files(
            'gs://bucket/import/v1', 'input0', runner=fake_runner)

        self.assertEqual(
            ['gs://bucket/import/v1/input0/validation/table_mcf_data.mcf'],
            files)
        self.assertEqual([
            'gs://bucket/import/v1/input0/genmcf/table_mcf_*.mcf',
            'gs://bucket/import/v1/input0/validation/table_mcf_*.mcf',
        ], patterns)

    def test_status_checks_do_not_treat_access_errors_as_missing(self):

        def fake_runner(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd,
                                               1,
                                               stdout='',
                                               stderr='Access denied')

        with self.assertRaisesRegex(RuntimeError,
                                    'Failed to check Parquet directory'):
            import_version_to_bq.check_output_dir_has_files(
                'gs://bucket/parquet', 'parquet', runner=fake_runner)
        with self.assertRaisesRegex(RuntimeError,
                                    'Failed to check BigQuery table'):
            import_version_to_bq.check_bq_table_exists('project',
                                                       'dataset',
                                                       'table',
                                                       runner=fake_runner)
        with self.assertRaisesRegex(RuntimeError, 'Failed to list MCF files'):
            import_version_to_bq.list_table_mcf_files('gs://bucket/import/v1',
                                                      'input0',
                                                      runner=fake_runner)

    def test_end_to_end_loads_multiple_mcf_parquet_dirs_into_one_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self._write_manifest(repo_root, 'scripts/example', 'Example_Import',
                                 ['output/data.tmcf'])
            commands_run = []

            def fake_runner(cmd, **kwargs):
                commands_run.append(list(cmd))
                cmd_text = ' '.join(str(part) for part in cmd)
                if cmd[:3] == ['gcloud', 'storage', 'cat']:
                    return subprocess.CompletedProcess(cmd,
                                                       1,
                                                       stdout='',
                                                       stderr='No URLs matched')
                if cmd[:3] == ['gcloud', 'storage', 'ls']:
                    pattern = cmd[3]
                    if pattern.endswith('Example_Import/'):
                        return subprocess.CompletedProcess(
                            cmd,
                            0,
                            stdout=(
                                'gs://imports/scripts/example/Example_Import/'
                                '2026_08_14T09_00_00_000000_00_00/\n'),
                            stderr='')
                    if pattern.endswith('00_00/'):
                        return subprocess.CompletedProcess(
                            cmd,
                            0,
                            stdout=(
                                'gs://imports/scripts/example/Example_Import/'
                                '2026_08_14T09_00_00_000000_00_00/input0/\n'),
                            stderr='')
                    if pattern.endswith('table_mcf_*.mcf'):
                        prefix = pattern.removesuffix('table_mcf_*.mcf')
                        return subprocess.CompletedProcess(
                            cmd,
                            0,
                            stdout=(f'{prefix}table_mcf_observations.mcf\n'
                                    f'{prefix}table_mcf_events.mcf\n'),
                            stderr='')
                    if pattern.endswith('*.parquet'):
                        return subprocess.CompletedProcess(
                            cmd, 1, stdout='', stderr='No URLs matched')
                if 'gcs_mcf_to_bigquery_files.sh' in cmd_text:
                    return subprocess.CompletedProcess(cmd,
                                                       0,
                                                       stdout='',
                                                       stderr='')
                if cmd[0] == 'bq':
                    return subprocess.CompletedProcess(cmd,
                                                       1,
                                                       stdout='',
                                                       stderr='Not found')
                if 'load_gcs_files_to_bigquery.sh' in cmd_text:
                    return subprocess.CompletedProcess(cmd,
                                                       0,
                                                       stdout='',
                                                       stderr='')
                self.fail(f'Unexpected command: {cmd}')

            summary = import_version_to_bq.import_version_to_bq(
                import_name='Example_Import',
                version='2026_08_14T09_00_00_000000_00_00',
                project='test-project',
                dataset='test_dataset',
                gcs_base_path='gs://imports',
                workers=4,
                repo_root=repo_root,
                runner=fake_runner,
            )

        self.assertEqual('scripts/example', summary['import_path'])
        self.assertEqual('parquet', summary['format'])
        self.assertEqual(['input0'], summary['import_inputs'])
        self.assertEqual(1, summary['processed_count'])
        self.assertEqual(
            'test-project:test_dataset.Example_Import__2026_08_14T09_00_00_000000_00_00__input0',
            summary['tables'][0]['bq_table'])
        self.assertEqual(2, len(summary['tables'][0]['parquet_dirs']))
        self.assertEqual('CREATED', summary['tables'][0]['bq_status'])

        generate_commands = [
            command for command in commands_run
            if 'gcs_mcf_to_bigquery_files.sh' in str(command[0])
        ]
        self.assertEqual(2, len(generate_commands))
        self.assertTrue(
            all(command[command.index('--workers') + 1] == '4'
                for command in generate_commands))
        load_commands = [
            command for command in commands_run
            if 'load_gcs_files_to_bigquery.sh' in str(command[0])
        ]
        self.assertEqual(1, len(load_commands))
        self.assertEqual(2, load_commands[0].count('--gcs-dir'))
        self.assertEqual(
            'parquet', load_commands[0][load_commands[0].index('--format') + 1])

    def test_avro_helpers_generate_and_load_avro(self):
        commands_run = []

        def fake_runner(cmd, **kwargs):
            commands_run.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')

        import_version_to_bq.generate_output(
            'gs://bucket/table.mcf',
            'gs://bucket/table_avro',
            'avro',
            workers=4,
            runner=fake_runner,
        )
        import_version_to_bq.load_output_to_bigquery(
            ['gs://bucket/table_avro'],
            'avro',
            'project',
            'dataset',
            'table',
            runner=fake_runner,
        )

        generate_command, load_command = commands_run
        self.assertEqual(
            'avro', generate_command[generate_command.index('--format') + 1])
        self.assertIn('gs://bucket/table_avro', generate_command)
        self.assertEqual('avro',
                         load_command[load_command.index('--format') + 1])
        self.assertIn('gs://bucket/table_avro', load_command)

    def test_dry_run_reports_paths_and_status_without_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self._write_manifest(repo_root, 'scripts/example', 'Example_Import',
                                 ['output/data.tmcf'])

            for table_exists, replace_table, expected_bq_status in (
                (False, False, 'NOT_FOUND'),
                (True, False, 'FOUND'),
                (True, True, 'FOUND'),
            ):
                with self.subTest(table_exists=table_exists,
                                  replace_table=replace_table):

                    def fake_runner(cmd, **kwargs):
                        cmd_text = ' '.join(str(part) for part in cmd)
                        if cmd[:3] == ['gcloud', 'storage', 'cat']:
                            return subprocess.CompletedProcess(
                                cmd, 1, stdout='', stderr='No URLs matched')
                        if cmd[:3] == ['gcloud', 'storage', 'ls']:
                            pattern = cmd[3]
                            if pattern.endswith('Example_Import/'):
                                return subprocess.CompletedProcess(
                                    cmd,
                                    0,
                                    stdout=('gs://imports/scripts/example/'
                                            'Example_Import/v1/\n'),
                                    stderr='')
                            if pattern.endswith('/v1/'):
                                return subprocess.CompletedProcess(
                                    cmd,
                                    0,
                                    stdout=('gs://imports/scripts/example/'
                                            'Example_Import/v1/input0/\n'),
                                    stderr='')
                            if pattern.endswith('table_mcf_*.mcf'):
                                prefix = pattern.removesuffix('table_mcf_*.mcf')
                                return subprocess.CompletedProcess(
                                    cmd,
                                    0,
                                    stdout=(f'{prefix}table_mcf_existing.mcf\n'
                                            f'{prefix}table_mcf_missing.mcf\n'),
                                    stderr='')
                            if 'existing_parquet' in pattern:
                                return subprocess.CompletedProcess(
                                    cmd,
                                    0,
                                    stdout=
                                    f'{pattern.removesuffix("*")}part.parquet\n',
                                    stderr='')
                            if pattern.endswith('*.parquet'):
                                return subprocess.CompletedProcess(
                                    cmd, 1, stdout='', stderr='No URLs matched')
                        if cmd[0] == 'bq':
                            return subprocess.CompletedProcess(
                                cmd,
                                0 if table_exists else 1,
                                stdout='Table' if table_exists else '',
                                stderr='' if table_exists else 'Not found')
                        if ('gcs_mcf_to_bigquery_files.sh' in cmd_text or
                                'load_gcs_files_to_bigquery.sh' in cmd_text):
                            self.fail(
                                f'Dry run invoked mutating command: {cmd}')
                        self.fail(f'Unexpected command: {cmd}')

                    summary = import_version_to_bq.import_version_to_bq(
                        import_name='Example_Import',
                        version='v1',
                        project='test-project',
                        dataset='test_dataset',
                        gcs_base_path='gs://imports',
                        replace_bq_table=replace_table,
                        dry_run=True,
                        repo_root=repo_root,
                        runner=fake_runner,
                    )

                    table = summary['tables'][0]
                    self.assertTrue(summary['dry_run'])
                    self.assertEqual('parquet', summary['format'])
                    self.assertEqual(
                        'test-project:test_dataset.Example_Import__v1__input0',
                        table['bq_table'])
                    self.assertEqual(expected_bq_status, table['bq_status'])
                    self.assertEqual(
                        ['FOUND', 'NOT_FOUND'],
                        [item['status'] for item in table['parquet_files']])
                    self.assertEqual([
                        'gs://imports/scripts/example/Example_Import/v1/input0/genmcf/table_mcf_existing_parquet',
                        'gs://imports/scripts/example/Example_Import/v1/input0/genmcf/table_mcf_missing_parquet',
                    ], table['parquet_dirs'])

    def test_avro_dry_run_uses_avro_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self._write_manifest(repo_root, 'scripts/example', 'Example_Import',
                                 ['output/data.tmcf'])

            def fake_runner(cmd, **kwargs):
                cmd_text = ' '.join(str(part) for part in cmd)
                if cmd[:3] == ['gcloud', 'storage', 'cat']:
                    return subprocess.CompletedProcess(cmd,
                                                       1,
                                                       stdout='',
                                                       stderr='No URLs matched')
                if cmd[:3] == ['gcloud', 'storage', 'ls']:
                    pattern = cmd[3]
                    if pattern.endswith('Example_Import/'):
                        return subprocess.CompletedProcess(
                            cmd,
                            0,
                            stdout=('gs://imports/scripts/example/'
                                    'Example_Import/v1/\n'),
                            stderr='')
                    if pattern.endswith('/v1/'):
                        return subprocess.CompletedProcess(
                            cmd,
                            0,
                            stdout=('gs://imports/scripts/example/'
                                    'Example_Import/v1/input0/\n'),
                            stderr='')
                    if pattern.endswith('table_mcf_*.mcf'):
                        prefix = pattern.removesuffix('table_mcf_*.mcf')
                        return subprocess.CompletedProcess(
                            cmd,
                            0,
                            stdout=f'{prefix}table_mcf_data.mcf\n',
                            stderr='')
                    if pattern.endswith('*.avro'):
                        return subprocess.CompletedProcess(
                            cmd, 1, stdout='', stderr='No URLs matched')
                if cmd[0] == 'bq':
                    return subprocess.CompletedProcess(cmd,
                                                       1,
                                                       stdout='',
                                                       stderr='Not found')
                if ('gcs_mcf_to_bigquery_files.sh' in cmd_text or
                        'load_gcs_files_to_bigquery.sh' in cmd_text):
                    self.fail(f'Dry run invoked mutating command: {cmd}')
                self.fail(f'Unexpected command: {cmd}')

            summary = import_version_to_bq.import_version_to_bq(
                import_name='Example_Import',
                version='v1',
                project='test-project',
                dataset='test_dataset',
                gcs_base_path='gs://imports',
                dry_run=True,
                output_format='avro',
                repo_root=repo_root,
                runner=fake_runner,
            )

        table = summary['tables'][0]
        self.assertEqual('avro', summary['format'])
        self.assertEqual(['NOT_FOUND'],
                         [item['status'] for item in table['avro_files']])
        self.assertEqual([
            'gs://imports/scripts/example/Example_Import/v1/input0/genmcf/table_mcf_data_avro'
        ], table['avro_dirs'])

    def test_cli_uses_explicit_bigquery_option_names(self):
        result = subprocess.run([
            sys.executable,
            str(Path(import_version_to_bq.__file__)), '--help'
        ],
                                capture_output=True,
                                text=True,
                                check=False)

        help_text = result.stdout + result.stderr
        self.assertNotIn('FATAL Flags parsing error', help_text)
        self.assertIn('--bq-project', help_text)
        self.assertIn('--bq-dataset', help_text)
        self.assertIn('--format', help_text)
        self.assertIn('dry-run', help_text)
        self.assertNotIn('--version-gcs-dir', help_text)

    def test_cli_accepts_representative_flags_without_running(self):
        result = subprocess.run([
            sys.executable,
            str(Path(import_version_to_bq.__file__)),
            '--import-name=Example_Import',
            '--version=latest',
            '--import-input=input0',
            '--import-input=input1',
            '--gcs-base-path=gs://test-imports',
            '--bq-project=test-project',
            '--bq-dataset=test_dataset',
            '--replace-bq-table',
            '--ttl-seconds=3600',
            '--shard-size-bytes=1024',
            '--workers=4',
            '--cleanup-temp',
            '--format=avro',
            '--dry-run',
            '--verbose',
            '--only_check_args',
        ],
                                capture_output=True,
                                text=True,
                                check=False)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
