# Validation Rationale

This import is heterogeneous (many datasets/statvars in one manifest), so validations are intentionally generic and low-noise.

## Why these rules

- `check_deleted_records_percent` with threshold `10`
  - Allows moderate refresh churn across many source tables while still catching large drops.
- `check_stats_non_empty`
  - Ensures output contains StatVar summary rows.
- `check_all_statvars_have_observations` (`NumObservations > 0`)
  - Prevents silently empty series from passing.
- `check_date_range_consistency` (`MinDate <= MaxDate`)
  - Catches malformed date output and bad parsing.

## Base rules still enforced

- `check_missing_refs_count` (threshold `0`)
- `check_lint_error_count` (threshold `0`)
