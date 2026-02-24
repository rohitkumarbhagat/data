# Validation Rationale

Custom validation rules were added in `validation_config.json` for Ethiopia statistics, but manifest wiring is currently pending because this directory has no `manifest.json`.

## Why these rules

- `check_deleted_records_percent` with threshold `10`
  - Reasonable tolerance for revision churn.
- `check_stats_non_empty`
  - Ensures the pipeline output is non-empty.
- `check_all_statvars_have_observations` (`NumObservations > 0`)
  - Prevents empty series from passing.
- `check_date_range_consistency` (`MinDate <= MaxDate`)
  - Catches malformed date range output.

## Pending wiring

When `manifest.json` is added for import-automation, include:

- `"validation_config_file": "validation_config.json"`
