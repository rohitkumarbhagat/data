# Validation Rationale

This import contains multiple source tables and mixed statvar families, so the custom checks focus on structural correctness.

## Why these rules

- `check_deleted_records_percent` with threshold `10`
  - Tolerates moderate revision churn across many tables.
- `check_stats_non_empty`
  - Ensures the run produced StatVar summary rows.
- `check_all_statvars_have_observations` (`NumObservations > 0`)
  - Detects empty series regressions.
- `check_date_range_consistency` (`MinDate <= MaxDate`)
  - Guards against malformed or reversed date bounds.

## Base rules still enforced

- `check_missing_refs_count` (threshold `0`)
- `check_lint_error_count` (threshold `0`)
