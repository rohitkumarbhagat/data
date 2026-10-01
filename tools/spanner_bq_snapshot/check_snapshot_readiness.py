#!/usr/bin/env python3
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tells whether *now* is a safe time to snapshot the Spanner -> BQ mirror.

Terms:
  SP = Spanner (prod dc_graph), DS = Datastream, BQ = BigQuery mirror.
  C  = CompletionTimestamp of the last SUCCESS ingestion run. While no new run
       has started, mixer serves SP's state as of C.
  T  = BQ time at which the BQ checks are evaluated. If all checks pass,
       BQ(T) == SP(C), i.e. BQ at T holds exactly what mixer serves, so a
       snapshot FOR SYSTEM_TIME AS OF T is consistent.

Checks (all read-only):
  SP1 SP: ingestion lock is free.
      Nobody is writing to SP now; also catches runs created before C
      that are still writing (overlapping runs).
  SP2 SP: no IngestionHistory run created after C.
      Mixer's own rule: with no run after C, mixer serves latest data, which
      is SP(C).
  DS1 DS: stream is RUNNING.
      A paused or failed stream also shows zero events and stale metrics,
      which would make DS2/DS3 pass falsely.
  DS2 DS: stream/freshness is recent and has read past C.
      read_up_to = metric_point_time - freshness must be > C, i.e. DS has
      read every SP change committed up to C. BQ can't see unread changes.
  DS3 DS: no per-table events in the last --quiet_minutes.
      DS2 covers reading only; DS buffers before writing to BQ. SP is quiet
      after C, so any recent event is the last run still in flight.
  BQ1 BQ: every table's last Write API append is older than --settle_minutes.
      INFORMATION_SCHEMA can lag a few minutes; waiting ensures BQ2 sees all
      writes.
  BQ2 BQ: every table's apply watermark >= its last append (nothing pending).
      Snapshots contain only applied data; with nothing pending there is also
      no runtime merge, so snapshot creation can't fail on that.
  SP3 SP re-read AFTER T: same C, lock still free, still no new run.
      BQ only receives changes after SP commits them, so if nothing was
      committed after C by this read, BQ(T) holds nothing newer than C.
      With DS2/DS3/BQ2 (everything up to C present): BQ(T) == SP(C).

Nothing is created, modified or deleted on any server. Progress is logged with
absl logging (stderr); the final report (or JSON with --json) is printed to
stdout.

Usage (from repo root):
  python -m tools.spanner_bq_snapshot.check_snapshot_readiness [--json]
Exit code: 0 = YES, 1 = NO, 2 = error.
"""

import dataclasses
import datetime
import json
import time

from absl import app
from absl import flags
from absl import logging
from google.cloud import bigquery
from google.cloud import datastream_v1
from google.cloud import monitoring_v3
from google.cloud import spanner

_FLAGS = flags.FLAGS

_LOCK_ID = 'global_ingestion_lock'
_ONE_MINUTE = datetime.timedelta(minutes=1)

_LEGEND = """\
Legend:
  SP = Spanner (prod dc_graph), DS = Datastream, BQ = BigQuery mirror
  C  = completion time of the last SUCCESS ingestion run (SP IngestionHistory).
       While no new run has started, mixer serves SP's state as of C.
  T  = BQ time at which the BQ checks were evaluated. If all checks pass,
       BQ at T == SP at C == what mixer serves, so it is safe to snapshot
       FOR SYSTEM_TIME AS OF T."""


@dataclasses.dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _define_flags():
    try:
        flags.DEFINE_string('project', 'datcom-store', 'GCP project.')
        flags.DEFINE_string('spanner_instance', 'dc-graph-prod',
                            'SP instance.')
        flags.DEFINE_string('spanner_database', 'dc_graph', 'SP database.')
        flags.DEFINE_string('bq_dataset', 'spanner_dc_graph_prod_DEFAULT',
                            'BQ mirror dataset.')
        flags.DEFINE_string('bq_region', 'region-us',
                            'BQ region qualifier for INFORMATION_SCHEMA.')
        flags.DEFINE_string('stream_location', 'us-central1', 'DS location.')
        flags.DEFINE_string('stream', 'ds-spanner-dc-graph-prod-to-bq',
                            'DS stream ID.')
        flags.DEFINE_integer('quiet_minutes', 30,
                             'DS3: no DS events for this long.')
        flags.DEFINE_integer('settle_minutes', 15,
                             'BQ1: last BQ append must be older than this.')
        flags.DEFINE_integer(
            'freshness_max_age_minutes', 10,
            'DS2: latest freshness metric point must be this recent.')
        flags.DEFINE_boolean('json', False, 'Print JSON output.')
    except flags.DuplicateFlagError:
        pass


class _Step:
    """Logs start and duration of a step."""

    def __init__(self, msg):
        self._msg = msg

    def __enter__(self):
        logging.info('%s ...', self._msg)
        self._start = time.monotonic()

    def __exit__(self, exc_type, *_):
        status = 'FAILED' if exc_type else 'done'
        logging.info('%s: %s in %.1fs', self._msg, status,
                     time.monotonic() - self._start)


def _fmt(ts):
    return ts.strftime('%Y-%m-%d %H:%M:%S UTC') if ts else 'NULL'


def _minutes(delta):
    return round(delta.total_seconds() / 60, 1)


# --------------------------------------------------------------------- SP --

_SPANNER_SQL = """
SELECT
  (SELECT COUNT(*) FROM IngestionLock WHERE LockID = @lock_id) AS lock_rows,
  (SELECT LockOwner FROM IngestionLock WHERE LockID = @lock_id) AS lock_owner,
  (SELECT AcquiredTimestamp FROM IngestionLock WHERE LockID = @lock_id) AS acquired,
  (SELECT MAX(CompletionTimestamp) FROM IngestionHistory
   WHERE Status = 'SUCCESS') AS c,
  ARRAY(SELECT WorkflowExecutionID FROM IngestionHistory
        WHERE CreationTimestamp > (SELECT MAX(CompletionTimestamp)
                                   FROM IngestionHistory
                                   WHERE Status = 'SUCCESS')
        ORDER BY CreationTimestamp) AS runs_after_c
"""


def read_spanner_state(database):
    """Strong read of lock + ingestion history."""
    with database.snapshot() as snap:  # Default snapshot is a strong read.
        rows = list(
            snap.execute_sql(_SPANNER_SQL,
                             params={'lock_id': _LOCK_ID},
                             param_types={'lock_id': spanner.param_types.STRING}))
    lock_rows, lock_owner, acquired, c, runs_after_c = rows[0]
    return {
        'lock_rows': lock_rows,
        'lock_owner': lock_owner,
        'acquired': acquired,
        'c': c,
        'runs_after_c': list(runs_after_c or []),
    }


def spanner_checks(state):
    checks = []
    if state['lock_rows'] != 1:
        checks.append(Check('SP1 lock free', False,
                            f'expected 1 {_LOCK_ID} row in SP IngestionLock, '
                            f'found {state["lock_rows"]}'))
    elif state['lock_owner'] is None:
        checks.append(Check('SP1 lock free', True,
                            'ingestion lock is free (no ingestion writing to SP)'))
    else:
        checks.append(Check('SP1 lock free', False,
                            f'ingestion lock held by run {state["lock_owner"]} '
                            f'since {_fmt(state["acquired"])} (ingestion running)'))
    if state['c'] is None:
        checks.append(Check('SP2 no run after C', False,
                            'no SUCCESS run in SP IngestionHistory, C undefined'))
    elif state['runs_after_c']:
        checks.append(Check('SP2 no run after C', False,
                            f'{len(state["runs_after_c"])} run(s) created after '
                            f'C ({_fmt(state["c"])}): {state["runs_after_c"]}'))
    else:
        checks.append(Check('SP2 no run after C', True,
                            f'no run created after C ({_fmt(state["c"])})'))
    return checks


# --------------------------------------------------------------------- DS --

def check_stream_running(dsclient, project, stream_location, stream):
    s = dsclient.get_stream(
        name=f'projects/{project}/locations/{stream_location}/streams/{stream}')
    state = datastream_v1.Stream.State(s.state).name
    return Check('DS1 stream running',
                 s.state == datastream_v1.Stream.State.RUNNING and not s.errors,
                 f'DS stream {stream}: state={state}, errors={len(s.errors)}')


def _interval(now, minutes):
    return monitoring_v3.TimeInterval(
        end_time=now, start_time=now - datetime.timedelta(minutes=minutes))


def check_freshness(mclient, project, stream, now, c, max_age_minutes):
    series = list(mclient.list_time_series(request=monitoring_v3.ListTimeSeriesRequest(
        name=f'projects/{project}',
        filter=('metric.type = "datastream.googleapis.com/stream/freshness"'
                f' AND resource.labels.stream_id = "{stream}"'),
        interval=_interval(now, 60),
        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL)))
    points = [p for s in series for p in s.points]
    if not points:
        return Check('DS2 DS read past C', False,
                     'no DS freshness metric points in the last 60 min')
    latest = max(points, key=lambda p: p.interval.end_time)
    point_t = latest.interval.end_time
    lag_s = latest.value.int64_value
    read_up_to = point_t - datetime.timedelta(seconds=lag_s)
    age = now - point_t
    detail = (f'DS read lag={lag_s}s per latest freshness metric point '
              f'({_fmt(point_t)}, {_minutes(age)} min old) -> DS has read SP '
              f'changes up to {_fmt(read_up_to)}; required > C ({_fmt(c)})')
    if age > datetime.timedelta(minutes=max_age_minutes):
        return Check('DS2 DS read past C', False,
                     f'metric point older than {max_age_minutes} '
                     f'min, cannot trust it; {detail}')
    return Check('DS2 DS read past C', c is not None and read_up_to > c, detail)


def check_no_recent_events(mclient, project, stream, now, quiet_minutes):
    window_s = quiet_minutes * 60
    series = mclient.list_time_series(request=monitoring_v3.ListTimeSeriesRequest(
        name=f'projects/{project}',
        filter=('metric.type = "datastream.googleapis.com/streamobject/event_count"'
                f' AND resource.labels.stream_id = "{stream}"'),
        interval=_interval(now, quiet_minutes),
        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
        aggregation=monitoring_v3.Aggregation(
            alignment_period={'seconds': window_s},
            per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_DELTA)))
    busy = {}
    for s in series:
        total = sum(p.value.int64_value for p in s.points)
        if total:
            obj = s.resource.labels.get('object_name', '?')
            busy[obj] = busy.get(obj, 0) + total
    if busy:
        return Check('DS3 no recent DS events', False,
                     f'DS sent change events in the last {quiet_minutes} min '
                     f'for {len(busy)} table(s) (table: events): {busy}')
    return Check('DS3 no recent DS events', True,
                 f'no DS change events in the last {quiet_minutes} min '
                 f'for any table')


# --------------------------------------------------------------------- BQ --

_BQ_SQL = """
WITH tbl AS (
  SELECT table_name, upsert_stream_apply_watermark AS watermark
  FROM `{p}.{ds}.INFORMATION_SCHEMA.TABLES`
  WHERE table_type = 'BASE TABLE'
),
app AS (
  SELECT table_id AS table_name, MAX(start_timestamp) AS last_append_minute
  FROM `{p}.{region}.INFORMATION_SCHEMA.WRITE_API_TIMELINE_BY_PROJECT`
  WHERE dataset_id = @ds
    AND start_timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  GROUP BY 1
)
SELECT CURRENT_TIMESTAMP() AS t, table_name, watermark, last_append_minute
FROM tbl LEFT JOIN app USING (table_name)
ORDER BY table_name
"""


def bq_checks(bq, project, bq_dataset, bq_region, settle_minutes):
    """Returns (T, checks, per-table info). T is BQ's CURRENT_TIMESTAMP()."""
    sql = _BQ_SQL.format(p=project, ds=bq_dataset, region=bq_region)
    job = bq.query(sql, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter('ds', 'STRING', bq_dataset)]))
    rows = list(job.result())
    if not rows:
        raise RuntimeError(f'no tables found in {project}.{bq_dataset}')
    t = rows[0].t
    settle_cutoff = t - datetime.timedelta(minutes=settle_minutes)

    unsettled, pending, tables = [], [], []
    for r in rows:
        # last_append_minute is the start of a 1-minute bucket.
        last_append_end = (r.last_append_minute + _ONE_MINUTE
                           if r.last_append_minute else None)
        unapplied_min = None
        if last_append_end and last_append_end > settle_cutoff:
            unsettled.append(f'{r.table_name} (last append {_fmt(r.last_append_minute)})')
        if last_append_end and (r.watermark is None or r.watermark < last_append_end):
            if r.watermark is None:
                pending.append(f'{r.table_name} (no watermark, last append '
                               f'{_fmt(r.last_append_minute)})')
            else:
                unapplied_min = _minutes(last_append_end - r.watermark)
                pending.append(f'{r.table_name} (unapplied span {unapplied_min} min: '
                               f'watermark {_fmt(r.watermark)}, last append '
                               f'{_fmt(r.last_append_minute)})')
        tables.append({
            'table': r.table_name,
            'last_append_minute': _fmt(r.last_append_minute),
            'watermark': _fmt(r.watermark),
            'unapplied_span_min': unapplied_min,
        })

    n = len(rows)
    if unsettled:
        bq1 = Check('BQ1 BQ appends settled', False,
                    f'{len(unsettled)} of {n} tables got BQ appends within the '
                    f'settle window ({settle_minutes} min, i.e. after '
                    f'{_fmt(settle_cutoff)}): {unsettled}')
    else:
        bq1 = Check('BQ1 BQ appends settled', True,
                    f'none of {n} tables got BQ appends within the settle window '
                    f'({settle_minutes} min, i.e. after {_fmt(settle_cutoff)})')
    if pending:
        bq2 = Check('BQ2 nothing pending in BQ', False,
                    f'{len(pending)} of {n} tables have received changes not yet '
                    f'applied (watermark < last append): {pending}')
    else:
        bq2 = Check('BQ2 nothing pending in BQ', True,
                    f'all {n} tables have applied every received change '
                    f'(watermark >= last append)')
    return t, [bq1, bq2], tables


# ------------------------------------------------------------------- main --

def run(project, spanner_instance, spanner_database, bq_dataset, bq_region,
        stream_location, stream, quiet_minutes, settle_minutes,
        freshness_max_age_minutes, as_json):
    """Runs all checks and prints the report. Returns the exit code."""
    checks = []

    # Credentials come from the environment (ADC).
    # disable_builtin_metrics: the Spanner client otherwise exports its own
    # metrics to Cloud Monitoring, which is a write.
    database = spanner.Client(
        project=project, disable_builtin_metrics=True).instance(
            spanner_instance).database(spanner_database)
    dsclient = datastream_v1.DatastreamClient()
    mclient = monitoring_v3.MetricServiceClient()
    bq = bigquery.Client(project=project)

    # 1. SP gate.
    with _Step('SP1/SP2: strong read of SP IngestionLock + IngestionHistory'):
        first = read_spanner_state(database)
    checks += spanner_checks(first)
    c = first['c']
    logging.info('C = %s', _fmt(c))

    # 2. DS.
    now = datetime.datetime.now(datetime.timezone.utc)
    with _Step('DS1: reading DS stream state'):
        checks.append(check_stream_running(dsclient, project, stream_location,
                                           stream))
    with _Step('DS2: reading DS freshness metric'):
        checks.append(check_freshness(mclient, project, stream, now, c,
                                      freshness_max_age_minutes))
    with _Step(f'DS3: reading DS per-table event counts '
               f'(last {quiet_minutes} min)'):
        checks.append(check_no_recent_events(mclient, project, stream, now,
                                             quiet_minutes))

    # 3. BQ, evaluated at T.
    with _Step('BQ1/BQ2: querying BQ INFORMATION_SCHEMA (appends, watermarks)'):
        t, bq_result, tables = bq_checks(bq, project, bq_dataset, bq_region,
                                         settle_minutes)
    checks += bq_result
    logging.info('T = %s', _fmt(t))

    # 4. Authoritative SP re-read, strictly after T.
    with _Step('SP3: strong re-read of SP after T'):
        second = read_spanner_state(database)
    changed = []
    if second['c'] != c:
        changed.append(f'C moved from {_fmt(c)} to {_fmt(second["c"])}')
    if second['lock_rows'] != 1 or second['lock_owner'] is not None:
        changed.append(f'lock now held by {second["lock_owner"]}')
    if second['runs_after_c']:
        changed.append(f'runs after C: {second["runs_after_c"]}')
    checks.append(Check(
        'SP3 SP unchanged after T', not changed,
        '; '.join(changed) if changed else
        'SP re-read after T: C unchanged, lock free, no new run'))

    failed = [ch for ch in checks if not ch.ok]
    verdict = 'YES' if not failed else 'NO'
    if failed:
        summary = f'NO: {failed[0].name}: {failed[0].detail}'
    else:
        summary = (f'YES: BQ at T ({_fmt(t)}) == SP at C ({_fmt(c)}) == what '
                   f'mixer serves. Safe to snapshot FOR SYSTEM_TIME AS OF T.')

    if as_json:
        print(json.dumps({
            'verdict': verdict,
            'summary': summary,
            'legend': _LEGEND,
            'C': _fmt(c),
            'T': _fmt(t),
            'checks': [dataclasses.asdict(ch) for ch in checks],
            'tables': tables,
        }, indent=2, default=str))
    else:
        print(_LEGEND)
        print(f'  C = {_fmt(c)}')
        print(f'  T = {_fmt(t)}')
        print()
        for ch in checks:
            print(f'[{"PASS" if ch.ok else "FAIL"}] {ch.name}: {ch.detail}')
        print()
        print(summary)
    return 0 if not failed else 1


def main(_):
    try:
        return run(
            project=_FLAGS.project,
            spanner_instance=_FLAGS.spanner_instance,
            spanner_database=_FLAGS.spanner_database,
            bq_dataset=_FLAGS.bq_dataset,
            bq_region=_FLAGS.bq_region,
            stream_location=_FLAGS.stream_location,
            stream=_FLAGS.stream,
            quiet_minutes=_FLAGS.quiet_minutes,
            settle_minutes=_FLAGS.settle_minutes,
            freshness_max_age_minutes=_FLAGS.freshness_max_age_minutes,
            as_json=_FLAGS.json)
    except Exception as e:  # pylint: disable=broad-except
        logging.error('%s: %s', type(e).__name__, e)
        return 2


if __name__ == '__main__':
    _define_flags()
    app.run(main)
