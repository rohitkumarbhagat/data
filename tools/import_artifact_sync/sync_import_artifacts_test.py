# Copyright 2026 Google LLC
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
"""Tests for import artifact synchronization."""

from datetime import datetime
from datetime import timezone
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from tools.import_artifact_sync import sync_import_artifacts


class _FakeBlob:

    def __init__(self, name, content):
        self.name = name
        self._content = content

    def download_as_text(self):
        return self._content


class _FakeStorageClient:

    def __init__(self, blobs):
        self._blobs = blobs

    def list_blobs(self, unused_bucket, prefix, match_glob=None):
        del match_glob
        return [blob for blob in self._blobs if blob.name.startswith(prefix)]


class _FakeJob:

    def __init__(self, result=None):
        self._result = result or []

    def result(self):
        return self._result


class _FakeBigQueryClient:

    def __init__(self, old_artifact_ids=None):
        self.events = []
        self._old_artifact_ids = old_artifact_ids or []

    def query(self, query, job_config):
        del job_config
        if query.startswith('SELECT artifact_id'):
            self.events.append('select_artifacts')
            rows = [
                SimpleNamespace(artifact_id=artifact_id)
                for artifact_id in self._old_artifact_ids
            ]
            return _FakeJob(rows)
        if 'DELETE FROM `p.d.import_versions`' in query:
            self.events.append('delete_version')
        elif 'DELETE FROM `p.d.import_artifact_rows`' in query:
            self.events.append('delete_csv_rows')
        elif 'DELETE FROM `p.d.import_version_artifacts`' in query:
            self.events.append('delete_artifacts')
        return _FakeJob()

    def load_table_from_json(self, rows, table_id):
        self.events.append(f'load:{table_id}:{len(rows)}')
        return _FakeJob()


class SyncImportArtifactsTest(unittest.TestCase):

    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tempdir.name)
        self.manifest_path = Path('scripts/example/manifest.json')
        full_manifest_path = self.repo_root / self.manifest_path
        full_manifest_path.parent.mkdir(parents=True)
        full_manifest_path.write_text(json.dumps({
            'import_specifications': [{
                'import_name': 'ImportA'
            }, {
                'import_name': 'ImportB'
            }]
        }),
                                      encoding='utf-8')

    def tearDown(self):
        self._tempdir.cleanup()

    def test_load_import_targets_selects_all_or_one(self):
        targets = sync_import_artifacts.load_import_targets(
            self.repo_root, self.manifest_path.as_posix(), None)

        self.assertEqual(['scripts/example:ImportA', 'scripts/example:ImportB'],
                         [target.import_name for target in targets])
        selected = sync_import_artifacts.load_import_targets(
            self.repo_root, self.manifest_path.as_posix(), 'ImportB')
        self.assertEqual('scripts/example/ImportB', selected[0].gcs_prefix)

    def test_load_import_targets_rejects_outside_path_and_unknown_import(self):
        with self.assertRaisesRegex(sync_import_artifacts.ArtifactSyncError,
                                    'repository-relative'):
            sync_import_artifacts.load_import_targets(
                self.repo_root, str(self.repo_root / self.manifest_path), None)
        with self.assertRaisesRegex(sync_import_artifacts.ArtifactSyncError,
                                    'not found'):
            sync_import_artifacts.load_import_targets(
                self.repo_root, self.manifest_path.as_posix(), 'Missing')

    def test_load_import_targets_rejects_non_object_manifest(self):
        (self.repo_root / self.manifest_path).write_text('[]', encoding='utf-8')

        with self.assertRaisesRegex(sync_import_artifacts.ArtifactSyncError,
                                    'not a JSON object'):
            sync_import_artifacts.load_import_targets(
                self.repo_root, self.manifest_path.as_posix(), None)

    def test_list_versions_accepts_all_names_and_only_root_summaries(self):
        target = sync_import_artifacts.ImportTarget(
            import_name='scripts/example:ImportA',
            simple_import_name='ImportA',
            gcs_prefix='scripts/example/ImportA')
        client = _FakeStorageClient([
            _FakeBlob('scripts/example/ImportA/release/import_summary.json',
                      '{}'),
            _FakeBlob(
                'scripts/example/ImportA/2026_01_01/input0/import_summary.json',
                '{}'),
            _FakeBlob('scripts/example/ImportA/v2/import_summary.json', '{}'),
        ])

        self.assertEqual(['release', 'v2'],
                         sync_import_artifacts.list_versions(
                             client, 'bucket', target))

    def test_versions_to_sync_skips_existing_or_forces_exact_version(self):
        self.assertEqual(['v2'],
                         sync_import_artifacts.versions_to_sync(['v1', 'v2'],
                                                                {'v1'}, None))
        self.assertEqual(['v1'],
                         sync_import_artifacts.versions_to_sync(['v1'], {'v1'},
                                                                'v1'))

    def test_build_version_snapshot_supports_legacy_paths_and_duplicate_rows(
            self):
        target = sync_import_artifacts.ImportTarget(
            import_name='scripts/example:ImportA',
            simple_import_name='ImportA',
            gcs_prefix='scripts/example/ImportA')
        prefix = 'scripts/example/ImportA/v1/'
        client = _FakeStorageClient([
            _FakeBlob(prefix + 'import_summary.json',
                      json.dumps({'import_name': 'ImportA'})),
            _FakeBlob(prefix + 'input0/genmcf/summary_report.csv',
                      'StatVar,NumPlaces\nCount_Person,2\nCount_Person,2\n'),
            _FakeBlob(prefix + 'legacy_name/validation/differ_summary.json',
                      '{"obs_diff_count": 1}'),
            _FakeBlob(prefix + 'input1/validation/differ_summary.json',
                      '{"obs_diff_count": 2}'),
            _FakeBlob(prefix + 'input0/validation/validation_output.csv',
                      'Rule,Status\nrule1,PASSED\n'),
            _FakeBlob(prefix + 'source_files/import_summary.json', '{}'),
        ])

        snapshot = sync_import_artifacts.build_version_snapshot(
            client, 'bucket', target, 'v1',
            datetime(2026, 1, 2, tzinfo=timezone.utc))

        self.assertEqual('gs://bucket/scripts/example/ImportA/v1',
                         snapshot.version_row['version_uri'])
        self.assertEqual(5, len(snapshot.artifact_rows))
        self.assertEqual(3, len(snapshot.csv_rows))
        self.assertEqual([1, 2], [
            row['row_number']
            for row in snapshot.csv_rows
            if row['artifact_id'].endswith('summary_report.csv')
        ])
        differ_artifacts = [
            row for row in snapshot.artifact_rows
            if row['artifact_type'] == 'DIFFER_SUMMARY'
        ]
        self.assertEqual(2, len(differ_artifacts))
        self.assertNotEqual(differ_artifacts[0]['artifact_id'],
                            differ_artifacts[1]['artifact_id'])
        self.assertEqual(
            'legacy_name/validation/differ_summary.json',
            next(row['relative_path']
                 for row in differ_artifacts
                 if 'legacy_name' in row['relative_path']))

    def test_build_version_snapshot_allows_missing_optional_artifacts(self):
        target = sync_import_artifacts.ImportTarget(
            import_name='scripts/example:ImportA',
            simple_import_name='ImportA',
            gcs_prefix='scripts/example/ImportA')
        client = _FakeStorageClient([
            _FakeBlob('scripts/example/ImportA/v1/import_summary.json',
                      '{"import_name": "ImportA"}')
        ])

        snapshot = sync_import_artifacts.build_version_snapshot(
            client, 'bucket', target, 'v1', datetime.now(timezone.utc))

        self.assertEqual(1, len(snapshot.artifact_rows))
        self.assertEqual([], snapshot.csv_rows)

    def test_build_version_snapshot_rejects_invalid_artifact(self):
        target = sync_import_artifacts.ImportTarget(
            import_name='scripts/example:ImportA',
            simple_import_name='ImportA',
            gcs_prefix='scripts/example/ImportA')
        client = _FakeStorageClient([
            _FakeBlob('scripts/example/ImportA/v1/import_summary.json',
                      '{"import_name": "ImportA"}'),
            _FakeBlob(
                'scripts/example/ImportA/v1/input0/validation/differ_summary.json',
                '{invalid'),
        ])

        with self.assertRaisesRegex(sync_import_artifacts.ArtifactSyncError,
                                    'Invalid JSON artifact'):
            sync_import_artifacts.build_version_snapshot(
                client, 'bucket', target, 'v1', datetime.now(timezone.utc))

    def test_replace_version_inserts_completion_marker_last(self):
        target = sync_import_artifacts.ImportTarget(
            import_name='scripts/example:ImportA',
            simple_import_name='ImportA',
            gcs_prefix='scripts/example/ImportA')
        snapshot = sync_import_artifacts.VersionSnapshot(
            version_row={'version': 'v1'},
            artifact_rows=[{
                'artifact_id': 'new'
            }],
            csv_rows=[{
                'artifact_id': 'new',
                'row_number': 1
            }])
        client = _FakeBigQueryClient(old_artifact_ids=['old'])
        table_ids = sync_import_artifacts._table_ids('p', 'd')

        sync_import_artifacts.replace_version(client, table_ids, target, 'v1',
                                              snapshot)

        self.assertEqual([
            'select_artifacts', 'delete_version', 'delete_csv_rows',
            'delete_artifacts', 'load:p.d.import_version_artifacts:1',
            'load:p.d.import_artifact_rows:1', 'load:p.d.import_versions:1'
        ], client.events)

    def test_exact_version_requires_import_name(self):
        with self.assertRaisesRegex(sync_import_artifacts.ArtifactSyncError,
                                    '--version requires --import_name'):
            sync_import_artifacts.sync_import_artifacts(
                repo_root=self.repo_root,
                manifest_path=self.manifest_path.as_posix(),
                import_name=None,
                exact_version='v1',
                gcs_project='gcs-project',
                gcs_bucket='bucket',
                bq_project='bq-project',
                bq_dataset='dataset')


if __name__ == '__main__':
    unittest.main()
