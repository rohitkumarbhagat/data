# Spanner -> BigQuery mirror snapshot tools

Prod Spanner (`dc-graph-prod/dc_graph`) is mirrored to BigQuery
(`datcom-store.spanner_dc_graph_prod_DEFAULT`) by Datastream using BigQuery CDC.
The mirror is only consistent with what mixer serves when ingestion is idle and
all changes up to the last successful ingestion (`C`) have been delivered and
applied in BigQuery.

| File | Purpose |
|---|---|
| `check_snapshot_readiness.py` | Read-only check: is *now* a safe time to snapshot? Prints PASS/FAIL per check and `YES`/`NO: <reason>`. See the module docstring for the checks. |
| `bq_pending_changes.sql` | Per-table last append vs apply watermark; shows which tables still have unapplied changes. |
| `set_max_staleness_1h.sql` | Sets `max_staleness` to 1 hour on every mirror table currently above 1 hour. |

## Usage

Requires `google-cloud-bigquery`, `google-cloud-spanner` and
`google-cloud-monitoring`, and credentials with read access to Spanner,
BigQuery, Cloud Monitoring and Datastream in `datcom-store`.

Run from the repo root:

```bash
python -m tools.spanner_bq_snapshot.check_snapshot_readiness          # human-readable
python -m tools.spanner_bq_snapshot.check_snapshot_readiness --json   # machine-readable
```

Progress lines (one per step, with timing) go to stderr; the final report goes
to stdout. The report starts with a legend defining `SP` (Spanner), `DS`
(Datastream), `BQ` (BigQuery), `C` (CompletionTimestamp of the last successful
ingestion run) and `T` (the time the BQ checks passed; if the verdict is YES,
BQ as of `T` equals Spanner as of `C`, i.e. what mixer serves). Checks are named
`SP1`, `SP2`, `DS1`-`DS3`, `BQ1`, `BQ2`, `SP3`.

Exit code: `0` = YES, `1` = NO, `2` = error.

## Checking pending BQ changes with SQL

`bq_pending_changes.sql` shows the same per-table data that check BQ2 uses.
It is read-only and needs read access to `datcom-store` (tables and
`region-us` INFORMATION_SCHEMA). Run it from the repo root:

```bash
bq --project_id=datcom-store query --use_legacy_sql=false --format=pretty \
  < tools/spanner_bq_snapshot/bq_pending_changes.sql
```

You can also paste the file into the BigQuery console with `datcom-store` as
the project. The query takes a few seconds.

| Column | Meaning |
|---|---|
| `last_append_minute` | Start of the last minute Datastream appended to the table (Storage Write API). NULL means no appends in the last 30 days. |
| `watermark` | `upsert_stream_apply_watermark`: BQ has applied every change it received before this time. |
| `unapplied_span_min` | Minutes of received changes not yet applied: `(last_append_minute + 1 min) - watermark`, floored at 0. `0` = nothing left to apply. It measures how far behind BQ is, not how long until it catches up (that depends on `max_staleness`). |
| `pending` | `true` if the table has changes BQ received but hasn't applied yet. A snapshot isn't safe while any row is `true`. |
| `appended_last_15min` | `true` if the table got appends in the last 15 minutes. |

Rows are sorted with pending tables first, largest unapplied span first.
Appends are grouped by minute, so
`pending` can be wrongly `true` for up to 1 minute after the last append.
Pending changes are applied within the table's `max_staleness`.
