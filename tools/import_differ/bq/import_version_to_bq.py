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
"""Orchestrates end-to-end conversion from an import GCS version to BigQuery tables.

Usage:
  .env/bin/python tools/import_differ/bq/import_version_to_bq.py \
    --version-gcs-dir=gs://bucket/path/to/import/2026_08_14T22_03_06_397467_07_00 \
    --project=my-project \
    --dataset=my_dataset \
    [--replace-bq-table] \
    [--ttl-seconds=86400]
"""

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable, Optional

from absl import logging

_SCRIPT_DIR = Path(__file__).resolve().parent
_GCS_MCF_TO_PARQUET_SH = _SCRIPT_DIR / 'gcs_mcf_to_parquet.sh'
_LOAD_PARQUET_TO_BQ_SH = _SCRIPT_DIR / 'load_gcs_parquet_to_bigquery.sh'

_DEFAULT_TTL_SECONDS = 86400


def sanitize_identifier(name: str) -> str:
    """Sanitizes a string to contain only valid BigQuery identifier characters."""
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    return sanitized.strip('_') or 'table'


def parse_version_from_gcs_dir(version_gcs_dir: str) -> str:
    """Extracts the version name from the trailing component of a GCS URI."""
    clean_dir = version_gcs_dir.rstrip('/')
    version = clean_dir.rsplit('/', 1)[-1]
    if not version:
        raise ValueError(f'Invalid GCS version directory: {version_gcs_dir}')
    return version


def fetch_import_summary(
    version_gcs_dir: str,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None
) -> dict:
    """Reads import_summary.json from the GCS version directory."""
    if runner is None:
        runner = subprocess.run

    summary_uri = f"{version_gcs_dir.rstrip('/')}/import_summary.json"
    logging.info(f"Reading import summary from {summary_uri}...")
    cmd = ['gcloud', 'storage', 'cat', summary_uri]
    result = runner(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to read {summary_uri}: {result.stderr.strip()}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {summary_uri}: {exc}") from exc


def list_table_mcf_files(
    version_gcs_dir: str,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None
) -> list[str]:
    """Discovers table_mcf_*.mcf files under input*/genmcf/ directories."""
    if runner is None:
        runner = subprocess.run

    pattern = f"{version_gcs_dir.rstrip('/')}/input*/genmcf/table_mcf_*.mcf"
    logging.info(f"Scanning for table MCF files matching {pattern}...")
    cmd = ['gcloud', 'storage', 'ls', pattern]
    result = runner(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        output = (result.stderr or result.stdout or '').strip()
        if 'matched no objects' in output or 'No URLs matched' in output or not output:
            logging.warning(f"No table MCF files found for pattern: {pattern}")
            return []
        raise RuntimeError(f"Failed to list MCF files: {output}")

    files = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and line.strip().endswith('.mcf')
    ]
    return sorted(files)


def check_parquet_dir_has_files(
    parquet_gcs_dir: str,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None
) -> bool:
    """Checks whether the given GCS parquet directory contains *.parquet files."""
    if runner is None:
        runner = subprocess.run

    pattern = f"{parquet_gcs_dir.rstrip('/')}/*.parquet"
    cmd = ['gcloud', 'storage', 'ls', pattern]
    result = runner(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return False
    parquet_files = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and line.strip().endswith('.parquet')
    ]
    return bool(parquet_files)


def check_bq_table_exists(
    project: str,
    dataset: str,
    table: str,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None
) -> bool:
    """Checks whether a BigQuery table exists."""
    if runner is None:
        runner = subprocess.run

    table_ref = f"{project}:{dataset}.{table}"
    cmd = ['bq', f'--project_id={project}', 'show', table_ref]
    result = runner(cmd, capture_output=True, text=True, check=False)
    return result.returncode == 0


def generate_parquet(
    mcf_gcs_file: str,
    parquet_gcs_dir: str,
    shard_size_bytes: Optional[int] = None,
    cleanup_temp: bool = False,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None
) -> None:
    """Runs gcs_mcf_to_parquet.sh to convert GCS MCF to Parquet."""
    if runner is None:
        runner = subprocess.run

    cmd = [
        str(_GCS_MCF_TO_PARQUET_SH),
        '--input-gcs-file',
        mcf_gcs_file,
        '--output-gcs-dir',
        parquet_gcs_dir,
    ]
    if shard_size_bytes:
        cmd.extend(['--shard-size-bytes', str(shard_size_bytes)])
    if cleanup_temp:
        cmd.append('--cleanup-temp')

    logging.info(
        f"Generating Parquet for {mcf_gcs_file} -> {parquet_gcs_dir}...")
    result = runner(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Parquet conversion failed for {mcf_gcs_file}: {result.stderr.strip()}"
        )


def load_parquet_to_bigquery(
    parquet_gcs_dir: str,
    project: str,
    dataset: str,
    table: str,
    replace_bq_table: bool = False,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None
) -> None:
    """Runs load_gcs_parquet_to_bigquery.sh to load Parquet files into BigQuery."""
    if runner is None:
        runner = subprocess.run

    cmd = [
        str(_LOAD_PARQUET_TO_BQ_SH),
        '--parquet-gcs-dir',
        parquet_gcs_dir,
        '--project',
        project,
        '--dataset',
        dataset,
        '--table',
        table,
        '--ttl-seconds',
        str(ttl_seconds),
    ]
    if replace_bq_table:
        cmd.append('--replace-bq-table')

    logging.info(
        f"Loading Parquet from {parquet_gcs_dir} into BigQuery table {project}:{dataset}.{table}..."
    )
    result = runner(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"BigQuery load failed for table {table}: {result.stderr.strip()}")


def import_version_to_bq(
    version_gcs_dir: str,
    project: str,
    dataset: str,
    replace_bq_table: bool = False,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    shard_size_bytes: Optional[int] = None,
    cleanup_temp: bool = False,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None
) -> dict:
    """Orchestrates end-to-end conversion from an import GCS version to BigQuery tables."""
    if runner is None:
        runner = subprocess.run

    clean_version_dir = version_gcs_dir.rstrip('/')
    if not clean_version_dir.startswith('gs://'):
        raise ValueError(
            f"--version-gcs-dir must be a GCS path starting with gs://: {version_gcs_dir}"
        )

    version_str = parse_version_from_gcs_dir(clean_version_dir)
    summary_json = fetch_import_summary(clean_version_dir, runner=runner)
    raw_import_name = summary_json.get('import_name')
    if not raw_import_name:
        raise ValueError(
            f"import_summary.json at {clean_version_dir} missing 'import_name' field."
        )

    sanitized_import_name = sanitize_identifier(raw_import_name)
    sanitized_version = sanitize_identifier(version_str)

    mcf_files = list_table_mcf_files(clean_version_dir, runner=runner)
    logging.info(
        f"Discovered {len(mcf_files)} table MCF file(s) across input folders."
    )

    # Group MCF files by input folder (e.g., 'input0', 'input1')
    input_groups = defaultdict(list)
    for mcf_file in mcf_files:
        # Match .../(input[0-9]+)/genmcf/...
        match = re.search(r'/(input[0-9]+)/genmcf/', mcf_file)
        input_folder = match.group(1) if match else 'input0'
        input_groups[input_folder].append(mcf_file)

    processed_tables = []

    for input_folder, files in sorted(input_groups.items()):
        has_multiple_files = len(files) > 1
        for mcf_file in files:
            mcf_filename = mcf_file.rsplit('/', 1)[-1]
            mcf_stem = mcf_filename.removesuffix('.mcf')
            parent_dir = mcf_file.rsplit('/', 1)[0]
            parquet_dir = f"{parent_dir}/{mcf_stem}_parquet"

            if has_multiple_files:
                table_name = f"{sanitized_import_name}__{sanitized_version}__{input_folder}__{sanitize_identifier(mcf_stem)}"
            else:
                table_name = f"{sanitized_import_name}__{sanitized_version}__{input_folder}"

            # Step 1: Ensure Parquet files exist
            parquet_already_exists = check_parquet_dir_has_files(
                parquet_dir, runner=runner)
            if parquet_already_exists:
                logging.info(
                    f"Parquet directory already contains files: {parquet_dir}. Skipping generation."
                )
                parquet_status = 'SKIPPED_ALREADY_EXISTS'
            else:
                generate_parquet(
                    mcf_file,
                    parquet_dir,
                    shard_size_bytes=shard_size_bytes,
                    cleanup_temp=cleanup_temp,
                    runner=runner,
                )
                parquet_status = 'GENERATED'

            # Step 2: Load into BigQuery
            table_exists = check_bq_table_exists(
                project, dataset, table_name, runner=runner)
            if table_exists and not replace_bq_table:
                logging.info(
                    f"BigQuery table {project}:{dataset}.{table_name} already exists. Skipping load."
                )
                bq_status = 'SKIPPED_ALREADY_EXISTS'
            else:
                load_parquet_to_bigquery(
                    parquet_dir,
                    project,
                    dataset,
                    table_name,
                    replace_bq_table=replace_bq_table,
                    ttl_seconds=ttl_seconds,
                    runner=runner,
                )
                bq_status = 'REPLACED' if table_exists else 'CREATED'

            processed_tables.append({
                'input_folder': input_folder,
                'mcf_file': mcf_file,
                'parquet_dir': parquet_dir,
                'bq_table': f"{project}:{dataset}.{table_name}",
                'parquet_status': parquet_status,
                'bq_status': bq_status,
            })

    result_summary = {
        'import_name': raw_import_name,
        'version': version_str,
        'version_gcs_dir': clean_version_dir,
        'project': project,
        'dataset': dataset,
        'ttl_seconds': ttl_seconds,
        'replace_bq_table': replace_bq_table,
        'processed_count': len(processed_tables),
        'tables': processed_tables,
    }
    return result_summary


def main():
    parser = argparse.ArgumentParser(
        description='End-to-end conversion from import GCS version to BigQuery tables.'
    )
    parser.add_argument(
        '--version-gcs-dir',
        required=True,
        help='GCS version directory containing import_summary.json and input<N> folders.'
    )
    parser.add_argument('--project', required=True, help='GCP project ID.')
    parser.add_argument(
        '--dataset', required=True, help='BigQuery dataset ID.')
    parser.add_argument(
        '--replace-bq-table',
        action='store_true',
        help='Replace BigQuery table if it already exists.')
    parser.add_argument(
        '--ttl-seconds',
        type=int,
        default=_DEFAULT_TTL_SECONDS,
        help=f'Table TTL in seconds (default: {_DEFAULT_TTL_SECONDS}).')
    parser.add_argument(
        '--shard-size-bytes',
        type=int,
        default=None,
        help='Soft MCF shard limit in bytes.')
    parser.add_argument(
        '--cleanup-temp',
        action='store_true',
        help='Delete local temporary conversion directories.')

    args = parser.parse_args()
    summary = import_version_to_bq(
        version_gcs_dir=args.version_gcs_dir,
        project=args.project,
        dataset=args.dataset,
        replace_bq_table=args.replace_bq_table,
        ttl_seconds=args.ttl_seconds,
        shard_size_bytes=args.shard_size_bytes,
        cleanup_temp=args.cleanup_temp,
    )
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
