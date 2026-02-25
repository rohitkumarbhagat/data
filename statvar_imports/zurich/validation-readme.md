# Validation Rationale (Per Import Spec)

This directory now uses one validation config per `import_spec` in `manifest.json`.

Evidence used:
- `README.md` source windows vary by feed (1941-2023, 1993-2023, 1998-2023, 2011-2022).
- PVMAP and test outputs show mixed statvar shapes: 1 statvar (totals), 2 statvars (sex/origin splits), 7 statvars (company/workforce), and 11 statvars (age buckets).
- All mapped metrics are count-like (`populationType` Person/BirthEvent/Company, employed/FTE variants) and expected to be non-negative.
- Place coverage differs by feed in test outputs (1, 3, 4, 12, and 24 places), so place-count assertions were avoided as brittle.

## Shared baseline rules in every config

- `check_stats_non_empty`: `SELECT COUNT(*) AS statvar_count FROM stats`, `statvar_count > 0`
- `check_all_statvars_have_observations`: `SELECT StatVar, NumObservations FROM stats`, `NumObservations > 0`
- `check_date_range_consistency`: `SELECT StatVar, MinDate, MaxDate FROM stats`, `MinDate <= MaxDate`
- `check_non_negative_values`: `SELECT StatVar, MinValue FROM stats`, `MinValue >= 0`
- `check_deleted_records_percent`: tuned per import (see below)
- `check_expected_min_statvar_count`: tuned per import using `COUNT(DISTINCT StatVar)`

## Per-import tuning

| Import spec | Config file | Profile | `deleted_records_percent` | `min distinct statvars` | Rationale |
|---|---|---|---:|---:|---|
| Zurich_Population | `validation_bev_3240_wiki.json` | stricter | 5 | 1 | Single stable total-population statvar over one place in test output; low expected schema churn. |
| Zurich_Population_Number_Of_Birth | `validation_bev_4031_wiki.json` | stricter | 6 | 1 | Single fixed statvar (`Count_BirthEvent` via TMCF) with broad place coverage; keep stricter but allow modest source revisions. |
| Zurich_Population_By_Age | `validation_bev_3903_age10_wiki.json` | moderate | 8 | 11 | Multi-bucket age feed; expect all 10-year buckets plus 100+ to remain present, with moderate revision tolerance. |
| Zurich_Population_By_Origin | `validation_bev_3903_hel_wiki.json` | moderate | 8 | 2 | Two-way nativity split (`Native`, `ForeignBorn`) over multiple places; moderate churn tolerance. |
| Zurich_Population_By_Sex | `validation_bev_3903_sex_wiki.json` | moderate | 8 | 2 | Two-way sex split feed over multiple places; moderate churn tolerance. |
| Zurich_Population_Number_Of_Birth_By_Origin | `validation_bev_4031_hel_wiki.json` | moderate | 8 | 2 | Birth-event nativity split with smaller counts; avoid brittle value-range caps, enforce structural consistency. |
| Zurich_Population_Number_Of_Birth_By_Sex | `validation_bev_4031_sex_wiki.json` | moderate | 8 | 2 | Birth-event sex split with smaller counts; moderate deletion tolerance for annual revisions. |
| Zurich_Population_Number_Of_Company_Workplace_Employees | `validation_wir_2552_wiki.json` | looser-moderate | 10 | 7 | Mixed labor/company statvars (company, employed, FTE, gender splits) and higher heterogeneity; use default-moderate deletion tolerance. |

## Manifest wiring

`manifest.json` now references import-specific validation config files for all 8 Zurich import specs.

## Base rules still enforced globally

- `check_missing_refs_count` (threshold `0`)
- `check_lint_error_count` (threshold `0`)
