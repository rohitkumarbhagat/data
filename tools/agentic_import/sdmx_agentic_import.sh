#!/bin/bash

# Copyright 2025 Google LLC
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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ORIG_DIR="$(pwd)"

# Toggle to start Custom DC after importer (default: false)
START_CDC=${START_CDC:-false}
WEBSITE_REPO=${WEBSITE_REPO:-}
REST_ARGS=()
CUSTOM_DC_ENV_DEST=""

run_repository_setup() {
  cd "${REPO_ROOT}"
  echo "Setting up virtual env..."
  ./run_tests.sh -r
  echo "Activating virtual environment..."
  source .env/bin/activate
  cd "${ORIG_DIR}"
}

run_importer() {
  echo "Starting SDMX agentic importer..."
  python "${SCRIPT_DIR}/sdmx_agentic_importer.py" "${REST_ARGS[@]}"
}

prepare_custom_dc_env() {
  local env_sample="${WEBSITE_REPO}/custom_dc/env.list.sample"
  local output_dir_path="${ORIG_DIR}/output"
  CUSTOM_DC_ENV_DEST="${output_dir_path}/env.list"

  echo "Preparing Custom DC environment file..."
  if [[ ! -f "$env_sample" ]]; then
    echo "Error: Expected env sample at $env_sample" >&2
    exit 2
  fi

  mkdir -p "$output_dir_path"
  cp "$env_sample" "$CUSTOM_DC_ENV_DEST"
  sed -i "s|^INPUT_DIR=.*|INPUT_DIR=${output_dir_path}|" "$CUSTOM_DC_ENV_DEST"
  sed -i "s|^OUTPUT_DIR=.*|OUTPUT_DIR=${output_dir_path}|" "$CUSTOM_DC_ENV_DEST"
  echo "Custom DC env configured with INPUT_DIR and OUTPUT_DIR at ${output_dir_path}"
}

start_custom_dc() {
  echo "Starting Custom DC..."
  cd "$WEBSITE_REPO"
  ./run_cdc_dev_docker.sh -e "$CUSTOM_DC_ENV_DEST"
}

while (($#)); do
  case "$1" in
    --start-custom-dc|--start-custom-dc=*)
      value="${1#*=}"
      if [[ "$value" == "$1" || "$value" == "true" ]]; then
        START_CDC=true
      elif [[ "$value" == "false" ]]; then
        START_CDC=false
      else
        echo "Error: --start-custom-dc expects true or false." >&2
        exit 2
      fi
      shift
      ;;
    --website-repo|--website-repo=*)
      if [[ "$1" == "--website-repo" ]]; then
        if [[ $# -lt 2 ]]; then
          echo "Error: --website-repo requires a path." >&2
          exit 2
        fi
        WEBSITE_REPO="$2"
        shift 2
      else
        WEBSITE_REPO="${1#*=}"
        shift
      fi
      ;;
    *)
      REST_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$START_CDC" == "true" ]]; then
  if [[ -z "$WEBSITE_REPO" ]]; then
    echo "Error: --website-repo is required when --start-custom-dc is set." >&2
    exit 2
  fi
  if [[ ! -d "$WEBSITE_REPO" ]]; then
    echo "Error: Custom DC repo not found at $WEBSITE_REPO" >&2
    exit 2
  fi
fi

run_repository_setup
run_importer

# Start Custom DC after importer completes if enabled
if [[ "$START_CDC" == "true" ]]; then
  prepare_custom_dc_env
  start_custom_dc
fi

