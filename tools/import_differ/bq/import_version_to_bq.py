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
"""Converts an import version's MCF files to BigQuery tables.

Usage:
  .env/bin/python tools/import_differ/bq/import_version_to_bq.py \
    --import-name=US_Urban_Schools_Teachers_And_Staff \
    --version=latest \
    --bq-project=my-project \
    --bq-dataset=my_dataset
"""

import json
from pathlib import Path
import re
import subprocess
from typing import Callable, Optional

from absl import app
from absl import flags
from absl import logging

_FLAGS = flags.FLAGS
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[2]
_GCS_MCF_TO_OUTPUT_SH = _SCRIPT_DIR / 'gcs_mcf_to_bigquery_files.sh'
_LOAD_OUTPUT_TO_BQ_SH = _SCRIPT_DIR / 'load_gcs_files_to_bigquery.sh'

_DEFAULT_GCS_BASE_PATH = 'gs://datcom-prod-imports'
_DEFAULT_TTL_SECONDS = 604800
_IMPORT_ROOTS = ('scripts', 'statvar_imports')
_OUTPUT_FORMATS = ('parquet', 'avro')
_VERSION_MARKERS = {
    'latest': 'latest_version.txt',
    'staging': 'staging_version.txt',
}
_TIMESTAMP_VERSION_RE = re.compile(r'^\d{4}_\d{2}_\d{2}T')


def _define_flags():
    flags.DEFINE_string(
        'import-name', None,
        'Exact import_name from a manifest under scripts or statvar_imports.')
    flags.mark_flag_as_required('import-name')
    flags.DEFINE_string(
        'version', None,
        'Version folder name, or latest, staging, or last_run.')
    flags.mark_flag_as_required('version')
    flags.DEFINE_multi_string(
        'import-input', [],
        'Import input folder to process. Repeat to process multiple inputs.')
    flags.DEFINE_string('gcs-base-path', _DEFAULT_GCS_BASE_PATH,
                        f'Base GCS path (default: {_DEFAULT_GCS_BASE_PATH}).')
    flags.DEFINE_string('bq-project', None, 'GCP project ID for BigQuery.')
    flags.mark_flag_as_required('bq-project')
    flags.DEFINE_string('bq-dataset', None, 'BigQuery dataset ID.')
    flags.mark_flag_as_required('bq-dataset')
    flags.DEFINE_boolean('replace-bq-table', False,
                         'Replace BigQuery table if it already exists.')
    flags.DEFINE_integer(
        'ttl-seconds', _DEFAULT_TTL_SECONDS,
        f'Table TTL in seconds (default: {_DEFAULT_TTL_SECONDS}).')
    flags.DEFINE_integer('shard-size-bytes', None,
                         'Soft MCF shard limit in bytes.')
    flags.DEFINE_integer('workers', None,
                         'Parallel MCF conversion processes. Default: 8.')
    flags.DEFINE_boolean('cleanup-temp', False,
                         'Delete local temporary conversion directories.')
    flags.DEFINE_enum('format', 'parquet', _OUTPUT_FORMATS,
                      'Output format to generate and load. Default: parquet.')
    flags.DEFINE_boolean(
        'dry-run', False,
        'Inspect paths and statuses without generating files or loading BigQuery.'
    )
    flags.DEFINE_boolean(
        'verbose', False,
        'Log manifest checks, resolution attempts, and GCS lookups.')


def sanitize_identifier(name: str) -> str:
    """Sanitizes a string to contain only valid BigQuery identifier characters."""
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    return sanitized.strip('_') or 'table'


def resolve_import_spec(import_name: str,
                        repo_root: Path = _REPO_ROOT) -> tuple[str, dict]:
    """Finds an import specification and returns its repository-relative path."""
    matches = []
    for import_root in _IMPORT_ROOTS:
        root = repo_root / import_root
        logging.debug(f"Looking for manifests under {root}")
        if not root.is_dir():
            logging.debug(f"Import root does not exist: {root}")
            continue
        for manifest_path in sorted(root.rglob('manifest.json')):
            logging.debug(f"Checking manifest: {manifest_path}")
            try:
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"Unable to read manifest {manifest_path}: {exc}") from exc
            for spec in manifest.get('import_specifications', []):
                if spec.get('import_name') == import_name:
                    relative_path = manifest_path.parent.relative_to(repo_root)
                    logging.info(
                        f"Found import {import_name} in {relative_path}/manifest.json"
                    )
                    matches.append((relative_path.as_posix(), spec))

    if not matches:
        raise ValueError(
            f"Import {import_name!r} was not found under scripts or statvar_imports."
        )
    if len(matches) > 1:
        paths = ', '.join(path for path, _ in matches)
        raise ValueError(
            f"Import {import_name!r} is defined more than once: {paths}")
    return matches[0]


def _is_missing_gcs_result(result: subprocess.CompletedProcess) -> bool:
    output = (result.stderr or result.stdout or '').lower()
    return ('matched no objects' in output or 'no urls matched' in output or
            'not found' in output or '404' in output)


def list_gcs_child_directories(
    gcs_dir: str,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None
) -> list[str]:
    """Lists the names of direct child directories under a GCS prefix."""
    if runner is None:
        runner = subprocess.run

    directory_uri = f"{gcs_dir.rstrip('/')}/"
    logging.debug(f"Listing GCS child directories: {directory_uri}")
    result = runner(['gcloud', 'storage', 'ls', directory_uri],
                    capture_output=True,
                    text=True,
                    check=False)
    if result.returncode != 0:
        if _is_missing_gcs_result(result):
            logging.debug(f"No GCS child directories found at {gcs_dir}")
            return []
        output = (result.stderr or result.stdout or '').strip()
        raise RuntimeError(
            f"Failed to list GCS directories at {gcs_dir}: {output}")

    children = sorted({
        line.strip().rstrip('/').rsplit('/', 1)[-1]
        for line in result.stdout.splitlines()
        if line.strip().endswith('/')
    })
    logging.debug(f"GCS child directories at {gcs_dir}: {children}")
    return children


def _read_version_marker(
        import_gcs_dir: str,
        marker_name: str,
        runner: Optional[Callable[...,
                                  subprocess.CompletedProcess]] = None) -> str:
    if runner is None:
        runner = subprocess.run

    marker_uri = f"{import_gcs_dir.rstrip('/')}/{marker_name}"
    logging.debug(f"Reading version marker: {marker_uri}")
    result = runner(['gcloud', 'storage', 'cat', marker_uri],
                    capture_output=True,
                    text=True,
                    check=False)
    if result.returncode != 0:
        output = (result.stderr or result.stdout or '').strip()
        raise RuntimeError(
            f"Failed to read version marker {marker_uri}: {output}")
    version = result.stdout.strip()
    if not version:
        raise ValueError(f"Version marker is empty: {marker_uri}")
    logging.info(f"Version marker {marker_name} resolved to {version}")
    return version


def resolve_version(
        import_gcs_dir: str,
        requested_version: str,
        runner: Optional[Callable[...,
                                  subprocess.CompletedProcess]] = None) -> str:
    """Resolves a literal version or a latest, staging, or last_run alias."""
    if runner is None:
        runner = subprocess.run

    available_versions = list_gcs_child_directories(import_gcs_dir,
                                                    runner=runner)
    if requested_version in _VERSION_MARKERS:
        resolved_version = _read_version_marker(
            import_gcs_dir, _VERSION_MARKERS[requested_version], runner=runner)
    elif requested_version == 'last_run':
        candidates = [
            child for child in available_versions
            if _TIMESTAMP_VERSION_RE.match(child)
        ]
        logging.debug(f"Timestamp version candidates: {candidates}")
        if not candidates:
            raise ValueError(
                f"No timestamp version folders found under {import_gcs_dir}")
        resolved_version = max(candidates)
        logging.info(f"last_run resolved to {resolved_version}")
    else:
        resolved_version = requested_version.strip()
        if not resolved_version or '/' in resolved_version:
            raise ValueError(f"Invalid version: {requested_version!r}")
        logging.info(f"Using literal version {resolved_version}")

    if resolved_version not in available_versions:
        raise ValueError(
            f"Version folder {resolved_version!r} was not found under {import_gcs_dir}"
        )
    return resolved_version


def fetch_import_summary(
    version_gcs_dir: str,
    expected_import_name: str,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None
) -> Optional[dict]:
    """Reads and validates an optional import_summary.json."""
    if runner is None:
        runner = subprocess.run

    summary_uri = f"{version_gcs_dir.rstrip('/')}/import_summary.json"
    logging.debug(f"Checking import summary: {summary_uri}")
    result = runner(['gcloud', 'storage', 'cat', summary_uri],
                    capture_output=True,
                    text=True,
                    check=False)
    if result.returncode != 0:
        if _is_missing_gcs_result(result):
            logging.info(f"No import_summary.json found at {version_gcs_dir}")
            return None
        output = (result.stderr or result.stdout or '').strip()
        raise RuntimeError(f"Failed to read {summary_uri}: {output}")

    try:
        summary = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {summary_uri}: {exc}") from exc
    summary_import_name = summary.get('import_name')
    if not summary_import_name:
        raise ValueError(f"{summary_uri} is missing 'import_name'.")
    if summary_import_name != expected_import_name:
        raise ValueError(
            f"Import name mismatch in {summary_uri}: expected {expected_import_name!r}, "
            f"found {summary_import_name!r}")
    logging.info(f"Validated import_summary.json for {expected_import_name}")
    return summary


def resolve_import_inputs(import_spec: dict, version_gcs_dir: str,
                          requested_inputs: Optional[list[str]],
                          available_inputs: list[str]) -> list[str]:
    """Resolves requested or manifest-defined import input folder names."""
    available = set(available_inputs)
    if requested_inputs:
        if len(requested_inputs) != len(set(requested_inputs)):
            raise ValueError("--import-input values must be unique.")
        for input_name in requested_inputs:
            logging.debug(
                f"Checking requested import input {input_name} under {version_gcs_dir}"
            )
            if input_name not in available:
                raise ValueError(
                    f"Import input folder {input_name!r} was not found under {version_gcs_dir}"
                )
        logging.info(
            f"Using requested import inputs: {', '.join(requested_inputs)}")
        return requested_inputs

    manifest_inputs = import_spec.get('import_inputs')
    if not manifest_inputs:
        raise ValueError(
            f"Manifest import {import_spec.get('import_name')!r} has no import_inputs."
        )

    resolved_inputs = []
    for index, import_input in enumerate(manifest_inputs):
        default_name = f'input{index}'
        template_mcf = import_input.get('template_mcf', '')
        fallback_name = Path(template_mcf).stem if template_mcf else ''
        logging.debug(
            f"Resolving manifest input {index}: trying {default_name!r}, "
            f"then {fallback_name!r}")
        if default_name in available:
            resolved_name = default_name
        elif fallback_name and fallback_name in available:
            resolved_name = fallback_name
        else:
            tried = [default_name]
            if fallback_name:
                tried.append(fallback_name)
            raise ValueError(
                f"Could not resolve manifest input {index} under {version_gcs_dir}; "
                f"tried: {', '.join(tried)}")
        if resolved_name in resolved_inputs:
            raise ValueError(
                f"Import input folder {resolved_name!r} resolved more than once."
            )
        resolved_inputs.append(resolved_name)

    logging.info(f"Resolved import inputs: {', '.join(resolved_inputs)}")
    return resolved_inputs


def list_table_mcf_files(
    version_gcs_dir: str,
    input_name: str,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None
) -> list[str]:
    """Discovers table_mcf_*.mcf files for one import input."""
    if runner is None:
        runner = subprocess.run

    pattern = f"{version_gcs_dir.rstrip('/')}/{input_name}/genmcf/table_mcf_*.mcf"
    logging.debug(f"Scanning for table MCF files: {pattern}")
    result = runner(['gcloud', 'storage', 'ls', pattern],
                    capture_output=True,
                    text=True,
                    check=False)
    if result.returncode != 0:
        if _is_missing_gcs_result(result):
            raise ValueError(
                f"No table MCF files found for import input {input_name!r}: {pattern}"
            )
        output = (result.stderr or result.stdout or '').strip()
        raise RuntimeError(
            f"Failed to list MCF files for {input_name}: {output}")

    files = sorted({
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().endswith('.mcf')
    })
    if not files:
        raise ValueError(
            f"No table MCF files found for import input {input_name!r}: {pattern}"
        )
    logging.info(
        f"Found {len(files)} MCF file(s) for import input {input_name}")
    logging.debug(f"MCF files for {input_name}: {files}")
    return files


def check_output_dir_has_files(
    output_gcs_dir: str,
    output_format: str,
    runner: Optional[Callable[...,
                              subprocess.CompletedProcess]] = None) -> bool:
    """Checks whether a GCS directory contains selected-format files."""
    if runner is None:
        runner = subprocess.run

    pattern = f"{output_gcs_dir.rstrip('/')}/*.{output_format}"
    format_label = output_format.title()
    logging.debug(f"Checking {format_label} directory: {pattern}")
    result = runner(['gcloud', 'storage', 'ls', pattern],
                    capture_output=True,
                    text=True,
                    check=False)
    if result.returncode != 0:
        if _is_missing_gcs_result(result):
            return False
        output = (result.stderr or result.stdout or '').strip()
        raise RuntimeError(
            f"Failed to check {format_label} directory {output_gcs_dir}: {output}"
        )
    return any(line.strip().endswith(f'.{output_format}')
               for line in result.stdout.splitlines())


def check_bq_table_exists(
    project: str,
    dataset: str,
    table: str,
    runner: Optional[Callable[...,
                              subprocess.CompletedProcess]] = None) -> bool:
    """Checks whether a BigQuery table exists."""
    if runner is None:
        runner = subprocess.run

    table_ref = f"{project}:{dataset}.{table}"
    logging.debug(f"Checking BigQuery table: {table_ref}")
    result = runner(['bq', f'--project_id={project}', 'show', table_ref],
                    capture_output=True,
                    text=True,
                    check=False)
    if result.returncode == 0:
        return True
    output = (result.stderr or result.stdout or '').strip()
    if 'not found' in output.lower() or '404' in output:
        return False
    raise RuntimeError(f"Failed to check BigQuery table {table_ref}: {output}")


def generate_output(
    mcf_gcs_file: str,
    output_gcs_dir: str,
    output_format: str,
    shard_size_bytes: Optional[int] = None,
    workers: Optional[int] = None,
    cleanup_temp: bool = False,
    runner: Optional[Callable[...,
                              subprocess.CompletedProcess]] = None) -> None:
    """Converts a GCS MCF file to the selected output format."""
    if runner is None:
        runner = subprocess.run

    cmd = [
        str(_GCS_MCF_TO_OUTPUT_SH),
        '--input-gcs-file',
        mcf_gcs_file,
        '--output-gcs-dir',
        output_gcs_dir,
        '--format',
        output_format,
    ]
    if shard_size_bytes:
        cmd.extend(['--shard-size-bytes', str(shard_size_bytes)])
    if workers is not None:
        cmd.extend(['--workers', str(workers)])
    if cleanup_temp:
        cmd.append('--cleanup-temp')

    format_label = output_format.title()
    logging.info(
        f"Generating {format_label} for {mcf_gcs_file} -> {output_gcs_dir}")
    result = runner(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"{format_label} conversion failed for {mcf_gcs_file}: {result.stderr.strip()}"
        )


def load_output_to_bigquery(
    output_gcs_dirs: list[str],
    output_format: str,
    project: str,
    dataset: str,
    table: str,
    replace_bq_table: bool = False,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    runner: Optional[Callable[...,
                              subprocess.CompletedProcess]] = None) -> None:
    """Loads selected-format directories into one BigQuery table."""
    if runner is None:
        runner = subprocess.run

    cmd = [str(_LOAD_OUTPUT_TO_BQ_SH), '--format', output_format]
    for output_gcs_dir in output_gcs_dirs:
        cmd.extend(['--gcs-dir', output_gcs_dir])
    cmd.extend([
        '--project',
        project,
        '--dataset',
        dataset,
        '--table',
        table,
        '--ttl-seconds',
        str(ttl_seconds),
    ])
    if replace_bq_table:
        cmd.append('--replace-bq-table')

    table_ref = f"{project}:{dataset}.{table}"
    format_label = output_format.title()
    logging.info(
        f"Loading {format_label} from {len(output_gcs_dirs)} GCS source(s) into {table_ref}"
    )
    logging.debug(
        f"{format_label} directories for {table_ref}: {output_gcs_dirs}")
    result = runner(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"BigQuery load failed for table {table}: {result.stderr.strip()}")


def import_version_to_bq(
    import_name: str,
    version: str,
    project: str,
    dataset: str,
    import_inputs: Optional[list[str]] = None,
    gcs_base_path: str = _DEFAULT_GCS_BASE_PATH,
    replace_bq_table: bool = False,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    shard_size_bytes: Optional[int] = None,
    workers: Optional[int] = None,
    cleanup_temp: bool = False,
    dry_run: bool = False,
    output_format: str = 'parquet',
    repo_root: Path = _REPO_ROOT,
    runner: Optional[Callable[...,
                              subprocess.CompletedProcess]] = None) -> dict:
    """Converts the selected import version's MCF files to BigQuery tables."""
    if runner is None:
        runner = subprocess.run
    if not gcs_base_path.startswith('gs://'):
        raise ValueError(
            f"--gcs-base-path must start with gs://: {gcs_base_path}")
    if output_format not in _OUTPUT_FORMATS:
        raise ValueError(
            f"--format must be one of {', '.join(_OUTPUT_FORMATS)}: {output_format}"
        )
    format_label = output_format.title()
    if dry_run:
        logging.info(
            f"Dry run enabled; no {format_label} files or BigQuery tables will be changed"
        )

    import_path, import_spec = resolve_import_spec(import_name, repo_root)
    import_gcs_dir = (
        f"{gcs_base_path.rstrip('/')}/{import_path}/{import_name}")
    logging.info(f"Import GCS directory: {import_gcs_dir}")

    resolved_version = resolve_version(import_gcs_dir, version, runner=runner)
    version_gcs_dir = f"{import_gcs_dir}/{resolved_version}"
    logging.info(f"Resolved version GCS directory: {version_gcs_dir}")
    fetch_import_summary(version_gcs_dir, import_name, runner=runner)

    available_inputs = list_gcs_child_directories(version_gcs_dir,
                                                  runner=runner)
    resolved_inputs = resolve_import_inputs(import_spec, version_gcs_dir,
                                            import_inputs, available_inputs)

    sanitized_import_name = sanitize_identifier(import_name)
    sanitized_version = sanitize_identifier(resolved_version)
    processed_tables = []
    for input_name in resolved_inputs:
        mcf_files = list_table_mcf_files(version_gcs_dir,
                                         input_name,
                                         runner=runner)
        output_files = []
        output_dirs = []
        for mcf_file in mcf_files:
            mcf_stem = mcf_file.rsplit('/', 1)[-1].removesuffix('.mcf')
            parent_dir = mcf_file.rsplit('/', 1)[0]
            output_dir = f"{parent_dir}/{mcf_stem}_{output_format}"
            output_dirs.append(output_dir)
            output_exists = check_output_dir_has_files(output_dir,
                                                       output_format,
                                                       runner=runner)
            if dry_run:
                output_status = 'FOUND' if output_exists else 'NOT_FOUND'
                logging.info(
                    f"Dry run: {format_label} {output_status}: {output_dir}")
            elif output_exists:
                logging.info(
                    f"{format_label} directory already contains files: {output_dir}; skipping generation"
                )
                output_status = 'SKIPPED_ALREADY_EXISTS'
            else:
                generate_output(
                    mcf_file,
                    output_dir,
                    output_format,
                    shard_size_bytes=shard_size_bytes,
                    workers=workers,
                    cleanup_temp=cleanup_temp,
                    runner=runner,
                )
                output_status = 'GENERATED'
            output_files.append({
                'mcf_file': mcf_file,
                f'{output_format}_dir': output_dir,
                'status': output_status,
            })

        table_name = (
            f"{sanitized_import_name}__{sanitized_version}__{sanitize_identifier(input_name)}"
        )
        table_exists = check_bq_table_exists(project,
                                             dataset,
                                             table_name,
                                             runner=runner)
        if dry_run:
            bq_status = 'FOUND' if table_exists else 'NOT_FOUND'
            logging.info(
                f"Dry run: BigQuery table {bq_status}: {project}:{dataset}.{table_name}"
            )
        elif table_exists and not replace_bq_table:
            logging.info(
                f"BigQuery table {project}:{dataset}.{table_name} already exists; skipping load"
            )
            bq_status = 'SKIPPED_ALREADY_EXISTS'
        else:
            load_output_to_bigquery(
                output_dirs,
                output_format,
                project,
                dataset,
                table_name,
                replace_bq_table=replace_bq_table,
                ttl_seconds=ttl_seconds,
                runner=runner,
            )
            bq_status = 'REPLACED' if table_exists else 'CREATED'

        processed_tables.append({
            'import_input': input_name,
            'mcf_files': mcf_files,
            f'{output_format}_dirs': output_dirs,
            f'{output_format}_files': output_files,
            'bq_table': f"{project}:{dataset}.{table_name}",
            'bq_status': bq_status,
        })

    return {
        'import_name': import_name,
        'import_path': import_path,
        'import_gcs_dir': import_gcs_dir,
        'requested_version': version,
        'resolved_version': resolved_version,
        'version_gcs_dir': version_gcs_dir,
        'import_inputs': resolved_inputs,
        'project': project,
        'dataset': dataset,
        'ttl_seconds': ttl_seconds,
        'replace_bq_table': replace_bq_table,
        'format': output_format,
        'dry_run': dry_run,
        'processed_count': len(processed_tables),
        'tables': processed_tables,
    }


def main(_):
    logging.set_verbosity(
        logging.DEBUG if _FLAGS['verbose'].value else logging.INFO)
    summary = import_version_to_bq(
        import_name=_FLAGS['import-name'].value,
        version=_FLAGS['version'].value,
        import_inputs=_FLAGS['import-input'].value or None,
        gcs_base_path=_FLAGS['gcs-base-path'].value,
        project=_FLAGS['bq-project'].value,
        dataset=_FLAGS['bq-dataset'].value,
        replace_bq_table=_FLAGS['replace-bq-table'].value,
        ttl_seconds=_FLAGS['ttl-seconds'].value,
        shard_size_bytes=_FLAGS['shard-size-bytes'].value,
        workers=_FLAGS['workers'].value,
        cleanup_temp=_FLAGS['cleanup-temp'].value,
        dry_run=_FLAGS['dry-run'].value,
        output_format=_FLAGS['format'].value,
    )
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    _define_flags()
    app.run(main)
