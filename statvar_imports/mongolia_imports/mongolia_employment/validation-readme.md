# Validation Rationale

Profile: moderate (upper moderate tolerance).

Evidence summary: This import combines 6 datasets, includes mixed annual and monthly date patterns, covers many StatVars, uses a semi-automated/manual source handoff, and includes a ratio table with percent units.

- `check_deleted_records_percent` (`DELETED_RECORDS_PERCENT`, threshold `10`): allows moderate churn from upstream schema/value updates while still catching high unexpected loss.
- `check_stats_non_empty` (`SQL_VALIDATOR`): enforces that the generated stats table contains at least one StatVar (`statvar_count > 0`).
- `check_all_statvars_have_observations` (`SQL_VALIDATOR`): ensures every StatVar has observations (`NumObservations > 0`) so no empty series pass through.
- `check_date_range_consistency` (`SQL_VALIDATOR`): validates temporal integrity by requiring `MinDate <= MaxDate` for each StatVar.
- `check_percent_values_range` (`SQL_VALIDATOR`): for rows with percent-like units, constrains values to `0..100` to catch scaling/unit errors in ratio outputs.

## Base Rules Still Enforced

- `check_missing_refs_count` threshold `0`
- `check_lint_error_count` threshold `0`
