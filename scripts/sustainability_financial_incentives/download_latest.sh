#!/bin/bash

# Download files from the latest directory in GCS bucket
# Usage: ./download_latest.sh gs://bucket-name/path local-folder

set -e

GCS_BUCKET_PATH="$1"
LOCAL_PATH="$2"

if [ -z "$GCS_BUCKET_PATH" ] || [ -z "$LOCAL_PATH" ]; then
    echo "Usage: $0 <gcs-bucket-path> <local-path>"
    echo "Example: $0 gs://my-bucket/data ./downloads"
    exit 1
fi

echo "Finding latest directory in $GCS_BUCKET_PATH..."

# Get latest directory (sorted by name, assuming timestamp-based naming)
LATEST_DIR=$(gsutil ls -d "$GCS_BUCKET_PATH"/*/ | sort -r | head -1)

if [ -z "$LATEST_DIR" ]; then
    echo "No directories found in $GCS_BUCKET_PATH"
    exit 1
fi

echo "Latest directory: $LATEST_DIR"

# Create local directory
mkdir -p "$LOCAL_PATH"

# Download all files from latest directory
echo "Downloading files to $LOCAL_PATH..."
gsutil -m cp -r "$LATEST_DIR"* "$LOCAL_PATH"

echo "Download completed!"