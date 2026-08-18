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

# Downloads one GCS MCF file, converts it locally, and uploads every Parquet
# part to an empty GCS prefix. The temporary directory is retained by default.
#
# Usage:
#   tools/import_differ/bq/gcs_mcf_to_parquet.sh \
#     --input-gcs-file gs://bucket/path/nodes-deleted.mcf \
#     --output-gcs-dir gs://bucket/path/parquet
#
# Optional:
#   --shard-size-bytes 268435456
#   --cleanup-temp

set -euo pipefail

usage() {
  printf '%s\n' \
    'Download one MCF file from GCS, convert it locally, and upload Parquet parts.' \
    '' \
    'Usage:' \
    '  gcs_mcf_to_parquet.sh --input-gcs-file GCS_OBJECT --output-gcs-dir GCS_DIR' \
    '                             [--shard-size-bytes BYTES] [--cleanup-temp]' \
    '' \
    'Required options:' \
    '  --input-gcs-file GCS_OBJECT  One source MCF object, such as' \
    '                               gs://bucket/path/nodes-deleted.mcf.' \
    '  --output-gcs-dir GCS_DIR     Empty destination prefix for part-*.parquet.' \
    '' \
    'Optional options:' \
    '  --shard-size-bytes BYTES     Soft MCF shard limit. Default: 524288000.' \
    '  --cleanup-temp               Delete temporary files on success or failure.' \
    '                               By default, the temporary directory is retained.' \
    '  -h, --help                   Show this help.' \
    '' \
    'Preflight checks:' \
    '  The input object and output bucket must exist and be accessible.' \
    '  The output prefix must not contain any files.' \
    '  A missing prefix does not need creation; GCS creates it on first upload.' \
    '' \
    'Example:' \
    '  tools/import_differ/bq/gcs_mcf_to_parquet.sh \' \
    '    --input-gcs-file gs://bucket/input/nodes-deleted.mcf \' \
    '    --output-gcs-dir gs://bucket/output/deleted-nodes-parquet'
}

require_value() {
  if [[ $# -lt 2 || -z "${2:-}" ]]; then
    echo "Missing value for $1" >&2
    usage >&2
    exit 2
  fi
}

input_gcs_file=""
output_gcs_dir=""
shard_size_bytes=""
cleanup_temp=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input-gcs-file)
      require_value "$@"
      input_gcs_file="$2"
      shift 2
      ;;
    --output-gcs-dir)
      require_value "$@"
      output_gcs_dir="$2"
      shift 2
      ;;
    --shard-size-bytes)
      require_value "$@"
      shard_size_bytes="$2"
      shift 2
      ;;
    --cleanup-temp)
      cleanup_temp=true
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

if [[ "$input_gcs_file" != gs://* || "$input_gcs_file" == */ ]]; then
  echo "--input-gcs-file must name one GCS object." >&2
  exit 2
fi
if [[ "$output_gcs_dir" != gs://* ]]; then
  echo "--output-gcs-dir must be a GCS path." >&2
  exit 2
fi
if [[ -n "$shard_size_bytes" && ! "$shard_size_bytes" =~ ^[1-9][0-9]*$ ]]; then
  echo "--shard-size-bytes must be a positive integer." >&2
  exit 2
fi

command -v gcloud >/dev/null || {
  echo "gcloud is required." >&2
  exit 1
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../../.." && pwd)"
python_bin="$repo_root/.env/bin/python"
if [[ ! -x "$python_bin" ]]; then
  echo "Repository Python is missing: $python_bin" >&2
  exit 1
fi

output_gcs_dir="${output_gcs_dir%/}"
if ! gcloud storage objects describe "$input_gcs_file" >/dev/null; then
  echo "GCS input object does not exist or is not accessible: $input_gcs_file" >&2
  exit 1
fi
output_bucket="${output_gcs_dir#gs://}"
output_bucket="gs://${output_bucket%%/*}"
if ! gcloud storage buckets describe "$output_bucket" >/dev/null; then
  echo "GCS output bucket does not exist or is not accessible: $output_bucket" >&2
  exit 1
fi
set +e
existing_output="$(gcloud storage ls "$output_gcs_dir/**" 2>&1)"
list_status=$?
set -e
if [[ $list_status -eq 0 && -n "$existing_output" ]]; then
  echo "GCS output directory already contains files: $output_gcs_dir" >&2
  exit 1
fi
if [[ $list_status -ne 0 &&
      "$existing_output" != *"matched no objects"* &&
      "$existing_output" != *"No URLs matched"* ]]; then
  echo "$existing_output" >&2
  exit $list_status
fi

temp_root="${TMPDIR:-/tmp}"
temp_dir="$(mktemp -d "${temp_root%/}/mcf-to-parquet.XXXXXX")"
cleanup() {
  if [[ "$cleanup_temp" == true && -d "$temp_dir" ]]; then
    rm -rf -- "$temp_dir"
  fi
}
trap cleanup EXIT

echo "Starting MCF to Parquet pipeline."
echo "Input GCS file: $input_gcs_file"
echo "Output GCS directory: $output_gcs_dir"
echo "Temporary directory: $temp_dir"
mkdir -p "$temp_dir/download"
input_name="${input_gcs_file##*/}"
local_input="$temp_dir/download/$input_name"
local_output="$temp_dir/output"

echo "Downloading $input_gcs_file to $local_input..."
gcloud storage cp "$input_gcs_file" "$local_input"

converter_args=(
  --input "$local_input"
  --output-dir "$local_output"
)
if [[ -n "$shard_size_bytes" ]]; then
  converter_args+=(--shard-size-bytes "$shard_size_bytes")
fi
echo "Converting $local_input to Parquet..."
"$python_bin" "$script_dir/mcf_to_parquet.py" "${converter_args[@]}"

parquet_files=("$local_output/parquet/"*.parquet)
if [[ ! -e "${parquet_files[0]}" ]]; then
  echo "Conversion did not produce any Parquet files." >&2
  exit 1
fi
echo "Uploading ${#parquet_files[@]} Parquet part(s) to $output_gcs_dir/..."
gcloud storage cp "${parquet_files[@]}" "$output_gcs_dir/"

echo "Uploaded ${#parquet_files[@]} Parquet file(s) to $output_gcs_dir/"
if [[ "$cleanup_temp" == false ]]; then
  echo "Retained temporary directory: $temp_dir"
fi
