# Validation Rationale

This import uses base validation rules plus import-specific overrides from `validation_config.json`.

## Why these rules

- `check_deleted_records_percent` with threshold `5`
  - Moderate tolerance for normal source revisions while catching large regressions.
- `check_stats_non_empty`
  - Ensures the pipeline emitted StatVar summary rows.
- `check_wastewater_values_range` (`MinValue >= 0 AND MaxValue <= 100`)
  - Wastewater treatment metrics are percentage/fraction style in this mapping.
- `check_units_are_percent`
  - Guards against unit drift from source or mapping changes.

## Base rules still enforced

- `check_missing_refs_count` (threshold `0`)
- `check_lint_error_count` (threshold `0`)
