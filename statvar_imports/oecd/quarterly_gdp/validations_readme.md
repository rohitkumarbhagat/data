# OECD Quarterly GDP Validation Rationale

This import uses the global base validation config (`tools/import_validation/validation_config.json`) and adds import-specific rules via `validation_config_file` in `manifest.json`.

The goal is to keep hard checks for true data-quality regressions, while allowing expected quarterly source revisions.

## Base validations kept

These come from the shared base config and are still enforced:

- `check_missing_refs_count` (`MISSING_REFS_COUNT`, threshold `0`)
- `check_lint_error_count` (`LINT_ERROR_COUNT`, threshold `0`)

Rationale:
- Missing references and lint errors are structural correctness issues.
- They should remain strict for this import.

## Custom/override validations added

### 1) `check_deleted_records_percent` (override)
- Validator: `DELETED_RECORDS_PERCENT`
- Threshold: `5`

Why:
- OECD quarterly series can revise historical points between releases.
- A strict `0%` deletion policy creates false failures for expected backfills/revisions.
- `5%` provides moderate tolerance while still catching large unintended deletions.

### 2) `check_quarter_and_year_series_present`
- Validator: `SQL_VALIDATOR`
- Condition: both `QuarterOnChange` and `YearOnChange` StatVar groups must be present.

Why:
- The import intentionally emits both QoQ and YoY GDP growth series.
- This catches mapping/filter regressions where one transformation path silently drops.

### 3) `check_gdp_growth_value_range`
- Validator: `SQL_VALIDATOR`
- Condition: `MinValue >= -100 AND MaxValue <= 100`

Why:
- GDP growth rates in percent should remain within sane bounds.
- This catches unit/pvmap mistakes and parsing bugs that produce implausible magnitudes.

### 4) `check_units_are_percent`
- Validator: `SQL_VALIDATOR`
- Condition: `Units` contains `percent` (case-insensitive).

Why:
- This import is explicitly percentage growth data (`UNIT_MEASURE:PC` in `pvmap.csv`).
- This guards against unit drift caused by source or mapping changes.

## Why some validators were not added

- `MAX_DATE_CONSISTENT` / `NUM_PLACES_CONSISTENT`: quarterly macro data is often uneven across countries and update cycles; these checks can fail on healthy releases.
- `UNIT_CONSISTENCY_CHECK`: we enforce unit semantics directly with `check_units_are_percent`.
- `NUM_OBSERVATIONS_CHECK` / `NUM_PLACES_COUNT`: hard thresholds can be noisy when country coverage changes naturally.

## Tuning guidance

- If expected revisions exceed tolerance, increase `check_deleted_records_percent.threshold` gradually (for example, from `5` to `8` or `10`) with release evidence.
- If false positives occur for range checks, inspect source units first; only widen bounds if source semantics changed.
