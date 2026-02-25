# Validation Rationale

Selected profile: `moderate`.

## Why these rules

- `check_deleted_records_percent` with threshold `10`
  - Allows moderate source refresh churn while flagging large unexpected drops.
- `check_stats_non_empty`
  - Verifies the run produced at least one StatVar summary row.
- `check_all_statvars_have_observations` (`NumObservations > 0`)
  - Prevents empty StatVar series from passing validation.
- `check_date_range_consistency` (`MinDate <= MaxDate`)
  - Catches malformed or reversed date ranges.
- `check_non_negative_values` (`MinValue >= 0`)
  - Ensures diabetes mortality values are not negative.

## Base rules still enforced

- `check_missing_refs_count` (threshold `0`)
- `check_lint_error_count` (threshold `0`)
