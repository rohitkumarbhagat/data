# Validation Rationale

profile: moderate

Evidence basis: 6 datasets, mixed monthly and annual series, mixed unit semantics (raw counts and per-1000 rates), and expected revisions in recent windows.

- `check_deleted_records_percent` (threshold `10`): Allows controlled churn from normal source revisions while still flagging unusually large deletions.
- `check_stats_non_empty`: Ensures each run produces at least one statvar-level record and catches empty-output failures early.
- `check_all_statvars_have_observations`: Prevents publishing statvars with zero observations due to mapping or extraction issues.
- `check_date_range_consistency`: Enforces `MinDate <= MaxDate` to catch malformed or inverted temporal coverage.

## Base Rules Still Enforced

- `check_missing_refs_count` threshold `0`
- `check_lint_error_count` threshold `0`
