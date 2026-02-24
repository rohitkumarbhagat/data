# Validation Rationale

This import uses base validation rules plus import-specific overrides from `validation_config.json`.

## Why these rules

- `check_deleted_records_percent` with threshold `5`
  - OECD data can revise historical points; small controlled deletions are expected.
- `check_stats_non_empty`
  - Fails fast if processing produced no StatVar rows.
- `check_fractional_values_range` (`MinValue >= 0 AND MaxValue <= 100`)
  - Regional education series here are fraction/percent-style values.
- `check_units_are_percent`
  - Ensures unit semantics stay consistent with the source mapping.

## Base rules still enforced

- `check_missing_refs_count` (threshold `0`)
- `check_lint_error_count` (threshold `0`)
