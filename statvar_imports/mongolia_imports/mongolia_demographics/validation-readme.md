# Validation Rationale

Profile: moderate (slightly tighter).

Evidence: 7 datasets, heterogeneous inputs, mixed place scope (country and region, including urban/rural slices), and mostly annual long-range series.

- `check_deleted_records_percent` (`DELETED_RECORDS_PERCENT`, threshold `8`): keeps cleanup tolerance modest for heterogeneous sources while catching unexpectedly large record drops.
- `check_stats_non_empty` (`SQL_VALIDATOR`): enforces that generated stats are present (`statvar_count > 0`) so empty output does not pass.
- `check_all_statvars_have_observations` (`SQL_VALIDATOR`): requires each stat var to have observations (`NumObservations > 0`) to prevent partial or broken statvar outputs.
- `check_date_range_consistency` (`SQL_VALIDATOR`): validates chronological integrity per stat var (`MinDate <= MaxDate`).

## Base Rules Still Enforced

- `check_missing_refs_count` threshold `0`
- `check_lint_error_count` threshold `0`
