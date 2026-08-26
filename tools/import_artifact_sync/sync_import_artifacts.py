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
"""Synchronizes import-version artifacts from GCS to BigQuery."""

import csv
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
import io
import json
from pathlib import Path
import posixpath
import sys
from typing import Any

from absl import app
from absl import flags
from absl import logging
from google.cloud import bigquery
from google.cloud import storage

_FLAGS = flags.FLAGS

_VERSION_TABLE = 'import_versions'
_ARTIFACT_TABLE = 'import_version_artifacts'
_ROW_TABLE = 'import_artifact_rows'
_SUMMARY_FILENAME = 'import_summary.json'

_ARTIFACTS = {
    'import_summary.json': ('IMPORT_SUMMARY', 'JSON'),
    'summary_report.csv': ('SUMMARY_REPORT', 'CSV'),
    'differ_summary.json': ('DIFFER_SUMMARY', 'JSON'),
    'validation_output.csv': ('VALIDATION_OUTPUT', 'CSV'),
}

_TABLES = {
    _VERSION_TABLE: (
        [
            bigquery.SchemaField('import_name', 'STRING', mode='REQUIRED'),
            bigquery.SchemaField('version', 'STRING', mode='REQUIRED'),
            bigquery.SchemaField('version_uri', 'STRING', mode='REQUIRED'),
            bigquery.SchemaField('import_summary', 'JSON', mode='REQUIRED'),
            bigquery.SchemaField('last_updated_timestamp',
                                 'TIMESTAMP',
                                 mode='REQUIRED'),
        ],
        ['import_name', 'version'],
    ),
    _ARTIFACT_TABLE: (
        [
            bigquery.SchemaField('artifact_id', 'STRING', mode='REQUIRED'),
            bigquery.SchemaField('import_name', 'STRING', mode='REQUIRED'),
            bigquery.SchemaField('version', 'STRING', mode='REQUIRED'),
            bigquery.SchemaField('artifact_type', 'STRING', mode='REQUIRED'),
            bigquery.SchemaField('relative_path', 'STRING', mode='REQUIRED'),
            bigquery.SchemaField('artifact_content', 'JSON'),
            bigquery.SchemaField('last_updated_timestamp',
                                 'TIMESTAMP',
                                 mode='REQUIRED'),
        ],
        ['import_name', 'version', 'artifact_type'],
    ),
    _ROW_TABLE: (
        [
            bigquery.SchemaField('artifact_id', 'STRING', mode='REQUIRED'),
            bigquery.SchemaField('row_number', 'INTEGER', mode='REQUIRED'),
            bigquery.SchemaField('row_data', 'JSON', mode='REQUIRED'),
        ],
        ['artifact_id'],
    ),
}


class ArtifactSyncError(ValueError):
    """Raised when an import version cannot be synchronized safely."""


@dataclass(frozen=True)
class ImportTarget:
    """Resolved manifest import and its GCS prefix."""

    import_name: str
    simple_import_name: str
    gcs_prefix: str


@dataclass(frozen=True)
class VersionSnapshot:
    """Rows to replace for one import version."""

    version_row: dict[str, Any]
    artifact_rows: list[dict[str, Any]]
    csv_rows: list[dict[str, Any]]


def _define_flags() -> None:
    flags.DEFINE_string(
        'manifest_path', None,
        'Path to manifest.json relative to the data repository root.')
    flags.mark_flag_as_required('manifest_path')
    flags.DEFINE_string('import_name', None,
                        'Case-sensitive import_name from the manifest.')
    flags.DEFINE_string('version', None,
                        'Exact version to replace. Requires --import_name.')
    flags.DEFINE_string('gcs_project', None,
                        'Project used to read import artifacts from GCS.')
    flags.mark_flag_as_required('gcs_project')
    flags.DEFINE_string('gcs_bucket', None,
                        'Bucket containing import artifacts.')
    flags.mark_flag_as_required('gcs_bucket')
    flags.DEFINE_string('bq_project', None,
                        'Project containing the destination BigQuery dataset.')
    flags.mark_flag_as_required('bq_project')
    flags.DEFINE_string('bq_dataset', None, 'Destination BigQuery dataset.')
    flags.mark_flag_as_required('bq_dataset')


def data_repo_root(path: Path) -> Path:
    """Requires path to be the data repository root."""
    root = path.resolve()
    required = ('statvar_imports', 'scripts', 'import-automation',
                'requirements_all.txt', 'run_tests.sh')
    missing = [name for name in required if not (root / name).exists()]
    if missing:
        raise ArtifactSyncError(
            f'Run from the data repository root; missing {missing[0]}.')
    return root


def load_import_targets(repo_root: Path, manifest_path: str,
                        import_name: str | None) -> list[ImportTarget]:
    """Loads selected imports from a repository-relative manifest."""
    relative_path = Path(manifest_path)
    if relative_path.is_absolute():
        raise ArtifactSyncError('manifest_path must be repository-relative.')

    resolved_path = (repo_root / relative_path).resolve()
    try:
        relative_path = resolved_path.relative_to(repo_root)
    except ValueError as exc:
        raise ArtifactSyncError(
            'manifest_path must remain inside the data repository.') from exc
    if not resolved_path.is_file():
        raise ArtifactSyncError(f'Manifest does not exist: {relative_path}')

    try:
        manifest = json.loads(resolved_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactSyncError(
            f'Unable to parse {relative_path}: {exc}') from exc
    if not isinstance(manifest, dict):
        raise ArtifactSyncError(
            f'Manifest is not a JSON object: {relative_path}')
    specifications = manifest.get('import_specifications')
    if not isinstance(specifications, list):
        raise ArtifactSyncError(
            f'Manifest has no import_specifications list: {relative_path}')

    import_directory = relative_path.parent.as_posix()
    targets = []
    for specification in specifications:
        if not isinstance(specification, dict):
            continue
        simple_name = specification.get('import_name')
        if not isinstance(simple_name, str) or not simple_name:
            continue
        if import_name is not None and simple_name != import_name:
            continue
        targets.append(
            ImportTarget(import_name=f'{import_directory}:{simple_name}',
                         simple_import_name=simple_name,
                         gcs_prefix=posixpath.join(import_directory,
                                                   simple_name)))

    if import_name is not None and not targets:
        raise ArtifactSyncError(
            f'Import {import_name!r} not found in {relative_path}.')
    if not targets:
        raise ArtifactSyncError(f'No imports found in {relative_path}.')
    return targets


def list_versions(storage_client: Any, bucket: str,
                  target: ImportTarget) -> list[str]:
    """Lists versions that have a root import_summary.json."""
    prefix = f'{target.gcs_prefix}/'
    blobs = storage_client.list_blobs(
        bucket, prefix=prefix, match_glob=f'{prefix}*/{_SUMMARY_FILENAME}')
    versions = set()
    for blob in blobs:
        relative_name = blob.name[len(prefix):]
        parts = relative_name.split('/')
        if len(parts) == 2 and parts[1] == _SUMMARY_FILENAME:
            versions.add(parts[0])
    return sorted(versions)


def _table_ids(bq_project: str, bq_dataset: str) -> dict[str, str]:
    prefix = f'{bq_project}.{bq_dataset}'
    return {name: f'{prefix}.{name}' for name in _TABLES}


def ensure_tables(bq_client: Any, table_ids: dict[str, str]) -> None:
    """Creates the destination tables when they do not exist."""
    for table_name, (schema, clustering_fields) in _TABLES.items():
        table = bigquery.Table(table_ids[table_name], schema=schema)
        table.clustering_fields = clustering_fields
        bq_client.create_table(table, exists_ok=True)


def _query_parameters(import_name: str,
                      version: str | None = None) -> list[Any]:
    parameters = [
        bigquery.ScalarQueryParameter('import_name', 'STRING', import_name)
    ]
    if version is not None:
        parameters.append(
            bigquery.ScalarQueryParameter('version', 'STRING', version))
    return parameters


def synced_versions(bq_client: Any, version_table: str,
                    import_name: str) -> set[str]:
    """Returns versions whose completion marker exists."""
    job_config = bigquery.QueryJobConfig(
        query_parameters=_query_parameters(import_name))
    rows = bq_client.query(
        f'SELECT version FROM `{version_table}` '
        'WHERE import_name = @import_name',
        job_config=job_config).result()
    return {row.version for row in rows}


def versions_to_sync(available_versions: list[str], existing_versions: set[str],
                     exact_version: str | None) -> list[str]:
    """Selects missing versions, or one explicitly requested version."""
    if exact_version is not None:
        return [exact_version]
    return [
        version for version in available_versions
        if version not in existing_versions
    ]


def _parse_json(text: str, gcs_uri: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ArtifactSyncError(f'Invalid JSON artifact: {gcs_uri}') from exc


def _parse_csv(text: str, artifact_id: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ArtifactSyncError(f'CSV artifact has no header: {artifact_id}')
    return [{
        'artifact_id': artifact_id,
        'row_number': row_number,
        'row_data': row,
    } for row_number, row in enumerate(reader, start=1)]


def build_version_snapshot(storage_client: Any, bucket: str,
                           target: ImportTarget, version: str,
                           updated_at: datetime) -> VersionSnapshot:
    """Reads and parses all selected artifacts for one exact version."""
    version_prefix = posixpath.join(target.gcs_prefix, version)
    object_prefix = f'{version_prefix}/'
    artifacts = []
    csv_rows = []
    import_summary = None
    timestamp = updated_at.isoformat()

    blobs = sorted(storage_client.list_blobs(bucket, prefix=object_prefix),
                   key=lambda blob: blob.name)
    for blob in blobs:
        relative_path = blob.name[len(object_prefix):]
        filename = posixpath.basename(relative_path)
        artifact_definition = _ARTIFACTS.get(filename)
        if artifact_definition is None:
            continue
        if filename == _SUMMARY_FILENAME and relative_path != _SUMMARY_FILENAME:
            continue

        artifact_type, artifact_format = artifact_definition
        artifact_id = f'gs://{bucket}/{blob.name}'
        text = blob.download_as_text()
        artifact_content = None
        if artifact_format == 'JSON':
            artifact_content = _parse_json(text, artifact_id)
        else:
            csv_rows.extend(_parse_csv(text, artifact_id))

        artifacts.append({
            'artifact_id': artifact_id,
            'import_name': target.import_name,
            'version': version,
            'artifact_type': artifact_type,
            'relative_path': relative_path,
            'artifact_content': artifact_content,
            'last_updated_timestamp': timestamp,
        })
        if relative_path == _SUMMARY_FILENAME:
            import_summary = artifact_content

    if not isinstance(import_summary, dict):
        raise ArtifactSyncError(
            f'Missing root {_SUMMARY_FILENAME}: gs://{bucket}/{version_prefix}')
    if import_summary.get('import_name') != target.simple_import_name:
        raise ArtifactSyncError(
            f'Import summary identity mismatch for gs://{bucket}/{version_prefix}'
        )

    return VersionSnapshot(version_row={
        'import_name': target.import_name,
        'version': version,
        'version_uri': f'gs://{bucket}/{version_prefix}',
        'import_summary': import_summary,
        'last_updated_timestamp': timestamp,
    },
                           artifact_rows=artifacts,
                           csv_rows=csv_rows)


def _run_query(bq_client: Any, query: str, query_parameters: list[Any]) -> Any:
    return bq_client.query(query,
                           job_config=bigquery.QueryJobConfig(
                               query_parameters=query_parameters)).result()


def _load_rows(bq_client: Any, table_id: str, rows: list[dict[str,
                                                              Any]]) -> None:
    if rows:
        bq_client.load_table_from_json(rows, table_id).result()


def replace_version(bq_client: Any, table_ids: dict[str,
                                                    str], target: ImportTarget,
                    version: str, snapshot: VersionSnapshot) -> None:
    """Replaces one version, inserting its completion marker last."""
    parameters = _query_parameters(target.import_name, version)
    old_artifacts = _run_query(
        bq_client, f'SELECT artifact_id FROM `{table_ids[_ARTIFACT_TABLE]}` '
        'WHERE import_name = @import_name AND version = @version', parameters)
    old_artifact_ids = [row.artifact_id for row in old_artifacts]

    _run_query(
        bq_client, f'DELETE FROM `{table_ids[_VERSION_TABLE]}` '
        'WHERE import_name = @import_name AND version = @version', parameters)
    if old_artifact_ids:
        _run_query(
            bq_client, f'DELETE FROM `{table_ids[_ROW_TABLE]}` '
            'WHERE artifact_id IN UNNEST(@artifact_ids)', [
                bigquery.ArrayQueryParameter('artifact_ids', 'STRING',
                                             old_artifact_ids)
            ])
    _run_query(
        bq_client, f'DELETE FROM `{table_ids[_ARTIFACT_TABLE]}` '
        'WHERE import_name = @import_name AND version = @version', parameters)

    _load_rows(bq_client, table_ids[_ARTIFACT_TABLE], snapshot.artifact_rows)
    _load_rows(bq_client, table_ids[_ROW_TABLE], snapshot.csv_rows)
    _load_rows(bq_client, table_ids[_VERSION_TABLE], [snapshot.version_row])


def sync_import_artifacts(repo_root: Path,
                          manifest_path: str,
                          import_name: str | None,
                          exact_version: str | None,
                          gcs_project: str,
                          gcs_bucket: str,
                          bq_project: str,
                          bq_dataset: str,
                          storage_client: Any | None = None,
                          bq_client: Any | None = None) -> dict[str, Any]:
    """Synchronizes selected import versions and returns summary counts."""
    if exact_version is not None and import_name is None:
        raise ArtifactSyncError('--version requires --import_name.')

    targets = load_import_targets(repo_root, manifest_path, import_name)
    storage_client = storage_client or storage.Client(project=gcs_project)
    bq_client = bq_client or bigquery.Client(project=bq_project)
    table_ids = _table_ids(bq_project, bq_dataset)
    ensure_tables(bq_client, table_ids)

    summary = {
        'imports_selected': len(targets),
        'versions_discovered': 0,
        'versions_skipped': 0,
        'versions_synced': 0,
        'versions_failed': 0,
        'artifacts_synced': 0,
        'csv_rows_synced': 0,
    }
    for target in targets:
        available_versions = ([exact_version] if exact_version is not None else
                              list_versions(storage_client, gcs_bucket, target))
        existing_versions = (
            set() if exact_version is not None else synced_versions(
                bq_client, table_ids[_VERSION_TABLE], target.import_name))
        selected_versions = versions_to_sync(available_versions,
                                             existing_versions, exact_version)
        summary['versions_discovered'] += len(available_versions)
        summary['versions_skipped'] += len(available_versions) - len(
            selected_versions)

        for version in selected_versions:
            try:
                snapshot = build_version_snapshot(storage_client, gcs_bucket,
                                                  target, version,
                                                  datetime.now(timezone.utc))
                replace_version(bq_client, table_ids, target, version, snapshot)
            except Exception as exc:  # Continue backfilling other versions.
                logging.error(
                    f'Failed to sync {target.import_name} version {version}: {exc}'
                )
                summary['versions_failed'] += 1
                continue
            summary['versions_synced'] += 1
            summary['artifacts_synced'] += len(snapshot.artifact_rows)
            summary['csv_rows_synced'] += len(snapshot.csv_rows)
    return summary


def main(argv: list[str]) -> None:
    if len(argv) > 1:
        raise app.UsageError('Unexpected positional arguments.')
    try:
        summary = sync_import_artifacts(repo_root=data_repo_root(Path.cwd()),
                                        manifest_path=_FLAGS.manifest_path,
                                        import_name=_FLAGS.import_name,
                                        exact_version=_FLAGS.version,
                                        gcs_project=_FLAGS.gcs_project,
                                        gcs_bucket=_FLAGS.gcs_bucket,
                                        bq_project=_FLAGS.bq_project,
                                        bq_dataset=_FLAGS.bq_dataset)
    except ArtifactSyncError as exc:
        print(json.dumps({'error': str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2) from exc
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary['versions_failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    _define_flags()
    app.run(main)
