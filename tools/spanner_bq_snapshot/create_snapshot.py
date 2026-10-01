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
"""Creates BQ table snapshots of every table in the Spanner -> BQ mirror.

All tables are snapshotted FOR SYSTEM_TIME AS OF the same time T (default:
now, UTC, truncated to the second) into a new dataset
  <project>.spanner_dc_graph_prod_snap_YYYY_MM_DD_HH_MM_SS   (T in UTC)
No readiness check is done; run check_snapshot_readiness first if the snapshot
must match what mixer serves.

Flow:
  1. List source base tables. Tables created after T are skipped (they can't
     be snapshotted AS OF T); the next run picks them up.
  2. CREATE SCHEMA with default_table_expiration_days=--ttl_days and label
     status=incomplete. Fails if the dataset already exists.
  3. CREATE SNAPSHOT TABLE ... CLONE ... FOR SYSTEM_TIME AS OF T, per table.
  4. Set label status=complete.
  On any error in 2-4 the dataset created by this run is dropped. If the drop
  fails too, status=incomplete marks it as failed.
  5. --mark_latest (optional, needs the latest dataset to exist): make the
     views in the latest dataset match the new snapshot (create/replace one
     view per snapshot table, drop views with no table in the snapshot) and set
     label snapshot_dataset=<new dataset> on it. A failure here keeps the
     snapshot.

--dry_run only lists tables (read-only) and prints the statements.
Progress is logged to stderr; the summary is printed to stdout.

Usage (from repo root):
  python -m tools.spanner_bq_snapshot.create_snapshot [--as_of TIME]
      [--ttl_days N] [--mark_latest] [--dry_run]
Exit code: 0 = success, 1 = snapshot failed, 2 = snapshot created but
--mark_latest failed.
"""

import argparse
import datetime
import sys
import time

from google.api_core import exceptions
from google.cloud import bigquery


def _log(msg):
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S')
    print(f'[{now}] {msg}', file=sys.stderr, flush=True)


class _Step:
    """Logs start and duration of a step to stderr."""

    def __init__(self, msg):
        self._msg = msg

    def __enter__(self):
        _log(f'{self._msg} ...')
        self._start = time.monotonic()

    def __exit__(self, exc_type, *_):
        status = 'FAILED' if exc_type else 'done'
        _log(f'{self._msg}: {status} in {time.monotonic() - self._start:.1f}s')


def _parse_as_of(value):
    """Parses an ISO time; a value without a timezone is taken as UTC."""
    ts = datetime.datetime.fromisoformat(value)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts.astimezone(datetime.timezone.utc)


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--project', default='datcom-store')
    p.add_argument('--location', default='US')
    p.add_argument('--source_dataset', default='spanner_dc_graph_prod_DEFAULT')
    p.add_argument('--snapshot_prefix', default='spanner_dc_graph_prod_snap_')
    p.add_argument('--latest_dataset', default='spanner_dc_graph_prod_snap_latest')
    p.add_argument('--as_of', type=_parse_as_of,
                   help='Snapshot time T, ISO format, e.g. "2026-10-01 04:09:17". '
                        'No timezone = UTC. Default: now. Must be within the '
                        'source dataset time-travel window (7 days).')
    p.add_argument('--ttl_days', type=int, default=60,
                   help='Dataset default_table_expiration_days.')
    p.add_argument('--mark_latest', action='store_true',
                   help='Point the views in --latest_dataset at the new snapshot.')
    p.add_argument('--dry_run', action='store_true',
                   help='Only list tables and print the statements.')
    return p.parse_args()


def _fmt(ts):
    return ts.strftime('%Y-%m-%d %H:%M:%S UTC')


def _labels_sql(labels):
    return '[' + ', '.join(f"('{k}', '{v}')" for k, v in labels.items()) + ']'


def _list_tables(bq, args, dataset, table_type):
    rows = bq.query(
        f'SELECT table_name, creation_time '
        f'FROM `{args.project}.{dataset}.INFORMATION_SCHEMA.TABLES` '
        f'WHERE table_type = @t ORDER BY table_name',
        location=args.location,
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter('t', 'STRING', table_type)])).result()
    return list(rows)


def _run(bq, args, sql):
    _log(f'  SQL: {sql}')
    if not args.dry_run:
        bq.query(sql, location=args.location).result()


def create_snapshot(bq, args, t, dataset, tables):
    """Steps 2-4. Drops the dataset on any error, then re-raises."""
    ds = f'`{args.project}.{dataset}`'
    description = (f'Snapshot of {args.project}.{args.source_dataset} '
                   f'FOR SYSTEM_TIME AS OF {_fmt(t)}.')
    created = False
    try:
        with _Step(f'Creating dataset {dataset} (status=incomplete, '
                   f'ttl {args.ttl_days} days)'):
            _run(bq, args,
                 f'CREATE SCHEMA {ds} OPTIONS('
                 f"location='{args.location}', "
                 f'default_table_expiration_days={args.ttl_days}, '
                 f'description="{description}", '
                 f"labels={_labels_sql({'status': 'incomplete'})})")
        created = True
        for i, name in enumerate(tables, 1):
            with _Step(f'[{i}/{len(tables)}] Snapshotting {name}'):
                _run(bq, args,
                     f'CREATE SNAPSHOT TABLE `{args.project}.{dataset}.{name}` '
                     f'CLONE `{args.project}.{args.source_dataset}.{name}` '
                     f"FOR SYSTEM_TIME AS OF TIMESTAMP '{t.isoformat()}'")
        with _Step('Marking dataset status=complete'):
            _run(bq, args,
                 f'ALTER SCHEMA {ds} SET OPTIONS('
                 f"labels={_labels_sql({'status': 'complete'})})")
    except BaseException:  # Also KeyboardInterrupt: never leave a partial snapshot.
        if created and not args.dry_run:
            _log(f'Snapshot failed; dropping dataset {dataset}')
            try:
                bq.query(f'DROP SCHEMA IF EXISTS {ds} CASCADE',
                         location=args.location).result()
                _log(f'Dropped dataset {dataset}')
            except Exception as e:  # pylint: disable=broad-except
                _log(f'Could not drop dataset {dataset} ({type(e).__name__}: '
                     f'{e}); it stays labeled status=incomplete')
        raise


def mark_latest(bq, args, t, dataset, tables):
    """Step 5. Returns (created_or_replaced, dropped) view names."""
    latest = f'{args.project}.{args.latest_dataset}'
    if args.dry_run:
        snap_tables = tables  # The snapshot dataset doesn't exist in a dry run.
    else:
        snap_tables = [r.table_name for r in
                       _list_tables(bq, args, dataset, 'SNAPSHOT')]
    try:
        views = [r.table_name for r in
                 _list_tables(bq, args, args.latest_dataset, 'VIEW')]
    except exceptions.NotFound:
        if not args.dry_run:
            raise
        _log(f'  WARNING: {latest} not found; it must be created before a real run')
        views = []
    to_drop = sorted(set(views) - set(snap_tables))

    for name in snap_tables:
        with _Step(f'Pointing view {args.latest_dataset}.{name} at {dataset}'):
            _run(bq, args,
                 f'CREATE OR REPLACE VIEW `{latest}.{name}` AS '
                 f'SELECT * FROM `{args.project}.{dataset}.{name}`')
    for name in to_drop:
        with _Step(f'Dropping view {args.latest_dataset}.{name} '
                   f'(no such table in {dataset})'):
            _run(bq, args, f'DROP VIEW `{latest}.{name}`')

    with _Step(f'Setting label snapshot_dataset={dataset} on {args.latest_dataset}'):
        if not args.dry_run:
            # Read-modify-write keeps any other labels on the dataset.
            ds = bq.get_dataset(latest)
            ds.labels = {**ds.labels, 'snapshot_dataset': dataset}
            ds.description = (f'Views pointing to {args.project}.{dataset} '
                              f'(snapshot AS OF {_fmt(t)}).')
            bq.update_dataset(ds, ['labels', 'description'])
    return snap_tables, to_drop


def main():
    args = _parse_args()
    t = args.as_of or datetime.datetime.now(datetime.timezone.utc)
    t = t.replace(microsecond=0)
    dataset = args.snapshot_prefix + t.strftime('%Y_%m_%d_%H_%M_%S')
    _log(f'T = {_fmt(t)}; target dataset = {args.project}.{dataset}'
         + (' (DRY RUN: nothing will be created)' if args.dry_run else ''))

    bq = bigquery.Client(project=args.project)

    with _Step(f'Listing base tables in {args.source_dataset}'):
        rows = _list_tables(bq, args, args.source_dataset, 'BASE TABLE')
    tables = [r.table_name for r in rows if r.creation_time <= t]
    skipped = [f'{r.table_name} (created {_fmt(r.creation_time)})'
               for r in rows if r.creation_time > t]
    _log(f'{len(tables)} tables to snapshot: {tables}')
    if skipped:
        _log(f'WARNING: skipping tables created after T: {skipped}')
    if not tables:
        raise RuntimeError(f'no tables in {args.source_dataset} existed at T')

    try:
        create_snapshot(bq, args, t, dataset, tables)
    except Exception as e:  # pylint: disable=broad-except
        print(f'FAILED: snapshot {args.project}.{dataset} not created: '
              f'{type(e).__name__}: {e}')
        return 1

    expires = t + datetime.timedelta(days=args.ttl_days)
    prefix = 'DRY RUN: would create' if args.dry_run else 'Created'
    print(f'{prefix} {args.project}.{dataset}: {len(tables)} tables AS OF '
          f'{_fmt(t)}, status=complete, tables expire ~{args.ttl_days} days '
          f'after creation (~{expires:%Y-%m-%d}).')
    if skipped:
        print(f'Skipped (created after T): {skipped}')

    if args.mark_latest:
        try:
            replaced, dropped = mark_latest(bq, args, t, dataset, tables)
        except Exception as e:  # pylint: disable=broad-except
            print(f'FAILED: --mark_latest: {type(e).__name__}: {e}. The snapshot '
                  f'is kept; {args.latest_dataset} may be partly switched '
                  f'(see stderr), its snapshot_dataset label was not updated.')
            return 2
        prefix = 'DRY RUN: would point' if args.dry_run else 'Pointed'
        print(f'{prefix} {len(replaced)} views in {args.project}.'
              f'{args.latest_dataset} at {dataset}; dropped views: '
              f'{dropped or "none"}; label snapshot_dataset={dataset}.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:  # pylint: disable=broad-except
        print(f'ERROR: {type(e).__name__}: {e}', file=sys.stderr)
        sys.exit(1)
