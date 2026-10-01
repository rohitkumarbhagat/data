# Spanner -> BigQuery mirror snapshot tools

Prod Spanner (`dc-graph-prod/dc_graph`) is mirrored to BigQuery
(`datcom-store.spanner_dc_graph_prod_DEFAULT`) by Datastream using BigQuery CDC.
The mirror is only consistent with what mixer serves when ingestion is idle and
all changes up to the last successful ingestion (`C`) have been delivered and
applied in BigQuery.

| File | Purpose |
|---|---|
| `check_snapshot_readiness.py` | Read-only check: is *now* a safe time to snapshot? Prints PASS/FAIL per check and `YES`/`NO: <reason>`. See the module docstring for the checks. |
| `create_snapshot.py` | Creates BQ table snapshots of every mirror table AS OF one time into a new dated dataset; optionally points the `_snap_latest` views at it. |
| `bq_pending_changes.sql` | Per-table last append vs apply watermark; shows which tables still have unapplied changes. |

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

## Creating a snapshot

`create_snapshot.py` snapshots every base table of
`spanner_dc_graph_prod_DEFAULT` `FOR SYSTEM_TIME AS OF` one time `T` into a new
dataset. It does **not** run the readiness check; run
`check_snapshot_readiness` first if the snapshot must match what mixer serves.
It needs BigQuery permission to create datasets and tables in `datcom-store`.

```bash
# Snapshot AS OF now (UTC):
python -m tools.spanner_bq_snapshot.create_snapshot
# Snapshot AS OF an earlier time (no timezone = UTC; must be within 7 days):
python -m tools.spanner_bq_snapshot.create_snapshot --as_of "2026-10-01 04:09:17"
# Also point the _snap_latest views at the new snapshot:
python -m tools.spanner_bq_snapshot.create_snapshot --mark_latest
# Print the statements without creating anything:
python -m tools.spanner_bq_snapshot.create_snapshot --dry_run [--mark_latest]
```

Flags: `--as_of` (default now), `--ttl_days` (default 60), `--mark_latest`
(default off), `--dry_run`. Progress goes to stderr, the summary to stdout.
Exit code: `0` = success, `1` = snapshot failed, `2` = snapshot created but
`--mark_latest` failed.

**Naming.** One dataset per snapshot, named after `T` in UTC:
`datcom-store.spanner_dc_graph_prod_snap_YYYY_MM_DD_HH_MM_SS`, location US,
with the same table names as the source. All tables use the same `T`, so they
are consistent with each other. Source tables created after `T` are skipped
(logged) and picked up by the next run.

**Lifecycle.**
- The dataset is created with label `status=incomplete` and
  `default_table_expiration_days=60` (`--ttl_days`). Each snapshot table
  expires 60 days after its own creation; the source tables are not affected.
- When all tables are snapshotted the label becomes `status=complete`.
- On any error (including Ctrl-C) the script drops the dataset it created. If
  that drop fails, `status=incomplete` marks the dataset as failed. The script
  never drops a dataset it didn't create in the same run: if the name already
  exists, `CREATE SCHEMA` fails first.
- Datasets don't expire: once its tables expire, an empty dataset remains.
  The script doesn't delete those; a separate cleanup is planned.

**Latest snapshot (`--mark_latest`).** BigQuery has no dataset aliases, so
`datcom-store.spanner_dc_graph_prod_snap_latest` holds one view per table
(`SELECT * FROM <dated dataset>.<table>`). Create this dataset once by hand
(location US). With `--mark_latest`, after the snapshot is complete the script:
- creates or replaces a view for every table in the new snapshot (new tables
  get a view);
- drops views that have no table in the new snapshot (dropped tables);
- sets label `snapshot_dataset=<dated dataset name>` on the latest dataset
  (other labels are kept).

Notes:
- Switching views is not atomic (one view at a time, a few seconds). Consumers
  that need strict consistency should read the `snapshot_dataset` label and
  query that dated dataset directly.
- Views don't keep snapshots alive. If no snapshot is marked latest for
  `--ttl_days`, the views fail with "Not found" once the old tables expire.
- If `--mark_latest` fails, the snapshot is kept and the label isn't updated;
  some views may already point to the new snapshot (see stderr).
