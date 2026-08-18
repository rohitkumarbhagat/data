#!/bin/bash
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

# Loads all Parquet files directly under one or more GCS directories into a
# native BigQuery table. The table expires after one week by default.
#
# Usage:
#   tools/import_differ/bq/load_gcs_parquet_to_bigquery.sh \
#     --parquet-gcs-dir gs://bucket/path/parquet \
#     --project my-project \
#     --dataset my_dataset \
#     --table deleted_nodes
#
# Optional:
#   --parquet-gcs-dir gs://bucket/path/another-parquet-directory
#   --ttl-seconds 172800
#   --replace-bq-table

set -euo pipefail

usage() {
  printf '%s\n' \
    'Load GCS Parquet parts into a native BigQuery table.' \
    '' \
    'Usage:' \
    '  load_gcs_parquet_to_bigquery.sh --parquet-gcs-dir GCS_DIR [...]' \
    '      --project PROJECT --dataset DATASET --table TABLE' \
    '      [--ttl-seconds SECONDS] [--replace-bq-table]' \
    '' \
    'Required options:' \
    '  --parquet-gcs-dir GCS_DIR  Prefix containing *.parquet files.' \
    '                             Repeat to load multiple prefixes.' \
    '  --project PROJECT          GCP project ID.' \
    '  --dataset DATASET          Existing BigQuery dataset ID.' \
    '  --table TABLE              Destination BigQuery table ID.' \
    '' \
    'Optional options:' \
    '  --ttl-seconds SECONDS      Table lifetime. Default: 604800 (one week).' \
    '  --replace-bq-table         Replace the table if it already exists.' \
    '                             By default, an existing table causes failure.' \
    '  -h, --help                 Show this help.' \
    '' \
    'Preflight checks:' \
    '  The dataset must exist and every prefix must contain *.parquet objects.' \
    '  The destination table must not exist unless --replace-bq-table is supplied.' \
    '' \
    'Example:' \
    '  tools/import_differ/bq/load_gcs_parquet_to_bigquery.sh \' \
    '    --parquet-gcs-dir gs://bucket/output/deleted-nodes-parquet \' \
    '    --project my-project --dataset my_dataset --table deleted_nodes'
}

require_value() {
  if [[ $# -lt 2 || -z "${2:-}" ]]; then
    echo "Missing value for $1" >&2
    usage >&2
    exit 2
  fi
}

parquet_gcs_dirs=()
project=""
dataset=""
table=""
ttl_seconds=604800
replace_bq_table=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --parquet-gcs-dir)
      require_value "$@"
      parquet_gcs_dirs+=("$2")
      shift 2
      ;;
    --project)
      require_value "$@"
      project="$2"
      shift 2
      ;;
    --dataset)
      require_value "$@"
      dataset="$2"
      shift 2
      ;;
    --table)
      require_value "$@"
      table="$2"
      shift 2
      ;;
    --ttl-seconds)
      require_value "$@"
      ttl_seconds="$2"
      shift 2
      ;;
    --replace-bq-table)
      replace_bq_table=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ${#parquet_gcs_dirs[@]} -eq 0 ]]; then
  echo "At least one --parquet-gcs-dir is required." >&2
  exit 2
fi
for parquet_gcs_dir in "${parquet_gcs_dirs[@]}"; do
  if [[ "$parquet_gcs_dir" != gs://* ]]; then
    echo "--parquet-gcs-dir must be a GCS path: $parquet_gcs_dir" >&2
    exit 2
  fi
done
if [[ -z "$project" || -z "$dataset" || -z "$table" ]]; then
  echo "--project, --dataset, and --table are required." >&2
  exit 2
fi
if [[ ! "$ttl_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "--ttl-seconds must be a positive integer." >&2
  exit 2
fi

command -v gcloud >/dev/null || {
  echo "gcloud is required." >&2
  exit 1
}
command -v bq >/dev/null || {
  echo "bq is required." >&2
  exit 1
}

dataset_ref="$project:$dataset"
if ! bq --project_id="$project" show --dataset "$dataset_ref" >/dev/null; then
  echo "BigQuery dataset does not exist or is not accessible: $dataset_ref" >&2
  exit 1
fi

parquet_sources=()
for parquet_gcs_dir in "${parquet_gcs_dirs[@]}"; do
  parquet_gcs_dir="${parquet_gcs_dir%/}"
  set +e
  parquet_objects="$(gcloud storage ls "$parquet_gcs_dir/*.parquet" 2>&1)"
  parquet_status=$?
  set -e
  if [[ $parquet_status -ne 0 || -z "$parquet_objects" ]]; then
    echo "No accessible Parquet files found at $parquet_gcs_dir/*.parquet" >&2
    if [[ -n "$parquet_objects" ]]; then
      echo "$parquet_objects" >&2
    fi
    exit 1
  fi
  parquet_sources+=("$parquet_gcs_dir/*.parquet")
done
parquet_sources_csv="$(IFS=,; echo "${parquet_sources[*]}")"

table_ref="$project:$dataset.$table"
table_exists=false
if bq --project_id="$project" show "$table_ref" >/dev/null 2>&1; then
  table_exists=true
fi
if [[ "$table_exists" == true && "$replace_bq_table" == false ]]; then
  echo "BigQuery table already exists: $table_ref" >&2
  echo "Pass --replace-bq-table to replace it." >&2
  exit 1
fi

echo "Starting BigQuery load pipeline for $table_ref..."
load_args=(
  --project_id="$project"
  load
  --source_format=PARQUET
)
if [[ "$replace_bq_table" == true ]]; then
  load_args+=(--replace=true)
fi
echo "Loading Parquet files from $parquet_sources_csv into $table_ref..."
bq "${load_args[@]}" "$table_ref" "$parquet_sources_csv"

echo "Setting expiration of $table_ref to $ttl_seconds seconds..."
bq --project_id="$project" update --expiration="$ttl_seconds" "$table_ref"

echo "Loaded $parquet_sources_csv into $table_ref"
echo "Table TTL: $ttl_seconds seconds"
