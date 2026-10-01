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

--dry_run only lists tables (read-only) and logs the statements.
Progress is logged with absl logging (stderr); the summary is printed to stdout.

Usage (from repo root):
  python -m tools.spanner_bq_snapshot.create_snapshot [--as_of TIME]
      [--ttl_days N] [--mark_latest] [--dry_run]
Exit code: 0 = success, 1 = snapshot failed, 2 = snapshot created but
--mark_latest failed.
"""

import datetime
import time

from absl import app
from absl import flags
from absl import logging
from google.api_core import exceptions
from google.cloud import bigquery

_FLAGS = flags.FLAGS


def _define_flags():
    try:
        flags.DEFINE_string('project', 'datcom-store', 'GCP project.')
        flags.DEFINE_string('location', 'US', 'BigQuery location.')
        flags.DEFINE_string('source_dataset', 'spanner_dc_graph_prod_DEFAULT',
                            'Dataset to snapshot.')
        flags.DEFINE_string('snapshot_prefix', 'spanner_dc_graph_prod_snap_',
                            'Prefix of the dated snapshot dataset name.')
        flags.DEFINE_string('latest_dataset', 'spanner_dc_graph_prod_snap_latest',
                            'Dataset with the views updated by --mark_latest.')
        flags.DEFINE_string(
            'as_of', None,
            'Snapshot time T, ISO format, e.g. "2026-10-01 04:09:17". '
            'No timezone = UTC. Default: now. Must be within the source '
            'dataset time-travel window (7 days).')
        flags.DEFINE_integer('ttl_days', 60,
                             'Dataset default_table_expiration_days.')
        flags.DEFINE_boolean(
            'mark_latest', False,
            'Point the views in --latest_dataset at the new snapshot.')
        flags.DEFINE_boolean('dry_run', False,
                             'Only list tables and log the statements.')
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


def parse_as_of(value):
    """Parses an ISO time; a value without a timezone is taken as UTC."""
    ts = datetime.datetime.fromisoformat(value)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts.astimezone(datetime.timezone.utc)


def _fmt(ts):
    return ts.strftime('%Y-%m-%d %H:%M:%S UTC')


def _labels_sql(labels):
    return '[' + ', '.join(f"('{k}', '{v}')" for k, v in labels.items()) + ']'


def _list_tables(bq, project, location, dataset, table_type):
    rows = bq.query(
        f'SELECT table_name, creation_time '
        f'FROM `{project}.{dataset}.INFORMATION_SCHEMA.TABLES` '
        f'WHERE table_type = @t ORDER BY table_name',
        location=location,
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter('t', 'STRING', table_type)])).result()
    return list(rows)


def _run(bq, location, dry_run, sql):
    logging.info('  SQL: %s', sql)
    if not dry_run:
        bq.query(sql, location=location).result()


def create_snapshot(bq, project, location, source_dataset, dataset, tables, t,
                    ttl_days, dry_run):
    """Steps 2-4. Drops the dataset on any error, then re-raises."""
    ds = f'`{project}.{dataset}`'
    description = (f'Snapshot of {project}.{source_dataset} '
                   f'FOR SYSTEM_TIME AS OF {_fmt(t)}.')
    created = False
    try:
        with _Step(f'Creating dataset {dataset} (status=incomplete, '
                   f'ttl {ttl_days} days)'):
            _run(bq, location, dry_run,
                 f'CREATE SCHEMA {ds} OPTIONS('
                 f"location='{location}', "
                 f'default_table_expiration_days={ttl_days}, '
                 f'description="{description}", '
                 f"labels={_labels_sql({'status': 'incomplete'})})")
        created = True
        for i, name in enumerate(tables, 1):
            with _Step(f'[{i}/{len(tables)}] Snapshotting {name}'):
                _run(bq, location, dry_run,
                     f'CREATE SNAPSHOT TABLE `{project}.{dataset}.{name}` '
                     f'CLONE `{project}.{source_dataset}.{name}` '
                     f"FOR SYSTEM_TIME AS OF TIMESTAMP '{t.isoformat()}'")
        with _Step('Marking dataset status=complete'):
            _run(bq, location, dry_run,
                 f'ALTER SCHEMA {ds} SET OPTIONS('
                 f"labels={_labels_sql({'status': 'complete'})})")
    except BaseException:  # Also KeyboardInterrupt: never leave a partial snapshot.
        if created and not dry_run:
            logging.error('Snapshot failed; dropping dataset %s', dataset)
            try:
                bq.query(f'DROP SCHEMA IF EXISTS {ds} CASCADE',
                         location=location).result()
                logging.info('Dropped dataset %s', dataset)
            except Exception as e:  # pylint: disable=broad-except
                logging.error('Could not drop dataset %s (%s: %s); it stays '
                              'labeled status=incomplete', dataset,
                              type(e).__name__, e)
        raise


def mark_latest(bq, project, location, latest_dataset, dataset, tables, t,
                dry_run):
    """Step 5. Returns (created_or_replaced, dropped) view names."""
    latest = f'{project}.{latest_dataset}'
    if dry_run:
        snap_tables = tables  # The snapshot dataset doesn't exist in a dry run.
    else:
        snap_tables = [r.table_name for r in
                       _list_tables(bq, project, location, dataset, 'SNAPSHOT')]
    try:
        views = [r.table_name for r in
                 _list_tables(bq, project, location, latest_dataset, 'VIEW')]
    except exceptions.NotFound:
        if not dry_run:
            raise
        logging.warning('%s not found; it must be created before a real run',
                        latest)
        views = []
    to_drop = sorted(set(views) - set(snap_tables))

    for name in snap_tables:
        with _Step(f'Pointing view {latest_dataset}.{name} at {dataset}'):
            _run(bq, location, dry_run,
                 f'CREATE OR REPLACE VIEW `{latest}.{name}` AS '
                 f'SELECT * FROM `{project}.{dataset}.{name}`')
    for name in to_drop:
        with _Step(f'Dropping view {latest_dataset}.{name} '
                   f'(no such table in {dataset})'):
            _run(bq, location, dry_run, f'DROP VIEW `{latest}.{name}`')

    with _Step(f'Setting label snapshot_dataset={dataset} on {latest_dataset}'):
        if not dry_run:
            # Read-modify-write keeps any other labels on the dataset.
            ds = bq.get_dataset(latest)
            ds.labels = {**ds.labels, 'snapshot_dataset': dataset}
            ds.description = (f'Views pointing to {project}.{dataset} '
                              f'(snapshot AS OF {_fmt(t)}).')
            bq.update_dataset(ds, ['labels', 'description'])
    return snap_tables, to_drop


def run(project, location, source_dataset, snapshot_prefix, latest_dataset,
        as_of, ttl_days, do_mark_latest, dry_run):
    """Runs steps 1-5 and prints the summary. Returns the exit code."""
    t = as_of or datetime.datetime.now(datetime.timezone.utc)
    t = t.replace(microsecond=0)
    dataset = snapshot_prefix + t.strftime('%Y_%m_%d_%H_%M_%S')
    logging.info('T = %s; target dataset = %s.%s%s', _fmt(t), project, dataset,
                 ' (DRY RUN: nothing will be created)' if dry_run else '')

    bq = bigquery.Client(project=project)

    with _Step(f'Listing base tables in {source_dataset}'):
        rows = _list_tables(bq, project, location, source_dataset, 'BASE TABLE')
    tables = [r.table_name for r in rows if r.creation_time <= t]
    skipped = [f'{r.table_name} (created {_fmt(r.creation_time)})'
               for r in rows if r.creation_time > t]
    logging.info('%d tables to snapshot: %s', len(tables), tables)
    if skipped:
        logging.warning('Skipping tables created after T: %s', skipped)
    if not tables:
        raise RuntimeError(f'no tables in {source_dataset} existed at T')

    try:
        create_snapshot(bq, project, location, source_dataset, dataset, tables,
                        t, ttl_days, dry_run)
    except Exception as e:  # pylint: disable=broad-except
        print(f'FAILED: snapshot {project}.{dataset} not created: '
              f'{type(e).__name__}: {e}')
        return 1

    expires = t + datetime.timedelta(days=ttl_days)
    prefix = 'DRY RUN: would create' if dry_run else 'Created'
    print(f'{prefix} {project}.{dataset}: {len(tables)} tables AS OF '
          f'{_fmt(t)}, status=complete, tables expire ~{ttl_days} days '
          f'after creation (~{expires:%Y-%m-%d}).')
    if skipped:
        print(f'Skipped (created after T): {skipped}')

    if do_mark_latest:
        try:
            replaced, dropped = mark_latest(bq, project, location,
                                            latest_dataset, dataset, tables, t,
                                            dry_run)
        except Exception as e:  # pylint: disable=broad-except
            print(f'FAILED: --mark_latest: {type(e).__name__}: {e}. The snapshot '
                  f'is kept; {latest_dataset} may be partly switched '
                  f'(see logs), its snapshot_dataset label was not updated.')
            return 2
        prefix = 'DRY RUN: would point' if dry_run else 'Pointed'
        print(f'{prefix} {len(replaced)} views in {project}.{latest_dataset} '
              f'at {dataset}; dropped views: {dropped or "none"}; '
              f'label snapshot_dataset={dataset}.')
    return 0


def main(_):
    try:
        return run(
            project=_FLAGS.project,
            location=_FLAGS.location,
            source_dataset=_FLAGS.source_dataset,
            snapshot_prefix=_FLAGS.snapshot_prefix,
            latest_dataset=_FLAGS.latest_dataset,
            as_of=parse_as_of(_FLAGS.as_of) if _FLAGS.as_of else None,
            ttl_days=_FLAGS.ttl_days,
            do_mark_latest=_FLAGS.mark_latest,
            dry_run=_FLAGS.dry_run)
    except Exception as e:  # pylint: disable=broad-except
        logging.error('%s: %s', type(e).__name__, e)
        return 1


if __name__ == '__main__':
    _define_flags()
    app.run(main)
