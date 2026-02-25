# Validation Rationale

Profile: `moderate`

Evidence summary: 6 datasets, mixed dimensions, heterogeneous mapping, unresolved regional aggregates in place resolver, and varied period coverage.

- `check_deleted_records_percent` (`threshold: 10`): Allows limited, expected churn from heterogeneous source-to-schema mapping while flagging unusually high deletion drift.
- `check_stats_non_empty`: Ensures the import produces at least one statvar (`statvar_count > 0`) and prevents silent empty-output runs.
- `check_all_statvars_have_observations`: Requires every statvar to retain observations (`NumObservations > 0`) so partial mapping failures are caught.
- `check_date_range_consistency`: Enforces valid temporal bounds (`MinDate <= MaxDate`) across mixed period coverage and prevents inverted date windows.

## Base Rules Still Enforced

- `check_missing_refs_count` with `threshold: 0`
- `check_lint_error_count` with `threshold: 0`
