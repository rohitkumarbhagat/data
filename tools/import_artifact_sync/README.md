# Import artifact synchronization

This tool copies selected import-version summaries from GCS into queryable
BigQuery tables. Run it from the `data` repository root with the repository
Python environment.

## Tables

The tool creates the destination tables if they do not exist:

| Table | Clustering | Contents |
|---|---|---|
| `import_versions` | `import_name, version` | One completion row per synchronized version. |
| `import_version_artifacts` | `import_name, version, artifact_type` | One row per selected GCS artifact. |
| `import_artifact_rows` | `artifact_id` | One row per CSV record. |

`artifact_id` is the complete GCS URI. JSON files are stored in
`artifact_content`. CSV records are stored as JSON in `row_data` and joined to
their file through `artifact_id`.

The supported artifact mappings are:

| Filename | Artifact type |
|---|---|
| `import_summary.json` | `IMPORT_SUMMARY` |
| `summary_report.csv` | `SUMMARY_REPORT` |
| `differ_summary.json` | `DIFFER_SUMMARY` |
| `validation_output.csv` | `VALIDATION_OUTPUT` |

Artifact discovery uses the exact filename and preserves the complete path
relative to the version. It does not require an `input<N>` directory.

## Usage

Sync unsynchronized versions for every import in one manifest:

```bash
./agents/common/run_python.sh \
  tools/import_artifact_sync/sync_import_artifacts.py \
  --manifest_path=scripts/us_bls/cpi/manifest.json \
  --gcs_project=<GCS_PROJECT> \
  --gcs_bucket=<GCS_BUCKET> \
  --bq_project=<BQ_PROJECT> \
  --bq_dataset=<BQ_DATASET>
```

Select one import from the manifest:

```bash
./agents/common/run_python.sh \
  tools/import_artifact_sync/sync_import_artifacts.py \
  --manifest_path=scripts/us_bls/cpi/manifest.json \
  --import_name=<IMPORT_NAME> \
  --gcs_project=<GCS_PROJECT> \
  --gcs_bucket=<GCS_BUCKET> \
  --bq_project=<BQ_PROJECT> \
  --bq_dataset=<BQ_DATASET>
```

Force replacement of one exact version by also passing `--version`.
`--version` requires `--import_name`.

## Replacement behavior

The tool parses the complete version before changing BigQuery. It removes the
old completion row and children, inserts the replacement artifacts and CSV
records, then inserts `import_versions` last. The version row therefore marks a
completed synchronization. Queries that require complete versions should start
from `import_versions` and join to the child tables.

Missing optional artifacts are allowed. A root `import_summary.json` is
required, and a selected artifact that exists but cannot be parsed fails that
version.

## Permissions

The caller needs permission to list and read the selected GCS import prefix,
create the three tables when absent, run BigQuery jobs, and read and modify rows
in the destination dataset.
