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

# Loads all Parquet or Avro files directly under one or more GCS directories
# into a native BigQuery table. The table expires after one week by default.
#
# Usage:
#   tools/import_differ/bq/load_gcs_files_to_bigquery.sh \
#     --gcs-dir gs://bucket/path/parquet \
#     --project my-project \
#     --dataset my_dataset \
#     --table deleted_nodes
#
# Optional:
#   --format avro
#   --gcs-dir gs://bucket/path/another-directory
#   --ttl-seconds 172800
#   --replace-bq-table

set -euo pipefail

usage() {
  printf '%s\n' \
    'Load GCS Parquet or Avro parts into a native BigQuery table.' \
    '' \
    'Usage:' \
    '  load_gcs_files_to_bigquery.sh --gcs-dir GCS_DIR [...]' \
    '      --project PROJECT --dataset DATASET --table TABLE' \
    '      [--format FORMAT] [--ttl-seconds SECONDS] [--replace-bq-table]' \
    '' \
    'Required options:' \
    '  --gcs-dir GCS_DIR          Prefix containing selected-format files.' \
    '                             Repeat to load multiple prefixes.' \
    '  --project PROJECT          GCP project ID.' \
    '  --dataset DATASET          Existing BigQuery dataset ID.' \
    '  --table TABLE              Destination BigQuery table ID.' \
    '' \
    'Optional options:' \
    '  --format FORMAT            parquet or avro. Default: parquet.' \
    '  --parquet-gcs-dir GCS_DIR  Legacy alias for --gcs-dir.' \
    '  --ttl-seconds SECONDS      Table lifetime. Default: 604800 (one week).' \
    '  --replace-bq-table         Replace the table if it already exists.' \
    '                             By default, an existing table causes failure.' \
    '  -h, --help                 Show this help.' \
    '' \
    'Preflight checks:' \
    '  The dataset must exist and every prefix must contain selected-format objects.' \
    '  The destination table must not exist unless --replace-bq-table is supplied.' \
    '' \
    'Example:' \
    '  tools/import_differ/bq/load_gcs_files_to_bigquery.sh \' \
    '    --gcs-dir gs://bucket/output/deleted-nodes-parquet \' \
    '    --project my-project --dataset my_dataset --table deleted_nodes'
}

require_value() {
  if [[ $# -lt 2 || -z "${2:-}" ]]; then
    echo "Missing value for $1" >&2
    usage >&2
    exit 2
  fi
}

gcs_dirs=()
project=""
dataset=""
table=""
ttl_seconds=604800
replace_bq_table=false
output_format="parquet"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gcs-dir|--parquet-gcs-dir)
      require_value "$@"
      gcs_dirs+=("$2")
      shift 2
      ;;
    --format)
      require_value "$@"
      output_format="$2"
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

if [[ ${#gcs_dirs[@]} -eq 0 ]]; then
  echo "At least one --gcs-dir is required." >&2
  exit 2
fi
for gcs_dir in "${gcs_dirs[@]}"; do
  if [[ "$gcs_dir" != gs://* ]]; then
    echo "--gcs-dir must be a GCS path: $gcs_dir" >&2
    exit 2
  fi
done
if [[ "$output_format" != "parquet" && "$output_format" != "avro" ]]; then
  echo "--format must be parquet or avro." >&2
  exit 2
fi
format_label="Parquet"
if [[ "$output_format" == "avro" ]]; then
  format_label="Avro"
fi
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

sources=()
for gcs_dir in "${gcs_dirs[@]}"; do
  gcs_dir="${gcs_dir%/}"
  set +e
  objects="$(gcloud storage ls "$gcs_dir/*.$output_format" 2>&1)"
  object_status=$?
  set -e
  if [[ $object_status -ne 0 || -z "$objects" ]]; then
    echo "No accessible $format_label files found at $gcs_dir/*.$output_format" >&2
    if [[ -n "$objects" ]]; then
      echo "$objects" >&2
    fi
    exit 1
  fi
  sources+=("$gcs_dir/*.$output_format")
done
sources_csv="$(IFS=,; echo "${sources[*]}")"

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
source_format="PARQUET"
if [[ "$output_format" == "avro" ]]; then
  source_format="AVRO"
fi
load_args=(
  --project_id="$project"
  load
  --source_format="$source_format"
)
if [[ "$replace_bq_table" == true ]]; then
  load_args+=(--replace=true)
fi
echo "Loading $format_label files from $sources_csv into $table_ref..."
bq "${load_args[@]}" "$table_ref" "$sources_csv"

echo "Setting expiration of $table_ref to $ttl_seconds seconds..."
bq --project_id="$project" update --expiration="$ttl_seconds" "$table_ref"

echo "Loaded $sources_csv into $table_ref"
echo "Table TTL: $ttl_seconds seconds"
