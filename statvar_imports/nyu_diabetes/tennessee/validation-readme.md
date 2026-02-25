# Validation Rationale

Selected profile: `moderate`.

## Why these rules

- `check_deleted_records_percent` with threshold `10`
  - Allows moderate refresh churn while catching large, unexpected deletions.
- `check_stats_non_empty`
  - Ensures the generated stats table is not empty.
- `check_all_statvars_have_observations` (`NumObservations > 0`)
  - Prevents empty statvar series from silently passing.
- `check_date_range_consistency` (`MinDate <= MaxDate`)
  - Catches malformed or reversed date bounds.
- `check_non_negative_values` (`MinValue >= 0`)
  - Diabetes mortality/rate series should not contain negative values.
- `check_rate_units_per_100k` (`Units = 'Per100000Persons'` for `%AsAFractionOf%` statvars)
  - Enforces expected unit semantics for rate-style statvars.

## Base rules still enforced

- `check_missing_refs_count` (threshold `0`)
- `check_lint_error_count` (threshold `0`)
