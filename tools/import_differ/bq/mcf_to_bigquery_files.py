# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Converts a local MCF file into CSV and Parquet or Avro parts.

Usage from the repository root:

  .env/bin/python tools/import_differ/bq/mcf_to_bigquery_files.py \
    --input=/path/to/nodes-deleted.mcf \
    --output-dir=/path/to/output

Files larger than 500 MiB are split at blank-line boundaries. Override the
soft shard limit when needed:

  --shard-size-bytes=268435456

CSV intermediates are retained by default. Pass `--delete-csv` to remove each
CSV after its corresponding output part is written successfully. Parquet is the
default output format; pass `--format=avro` to write Avro instead.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import json
import os
from pathlib import Path
import sys
from typing import Callable

from absl import logging
import fastavro
import pyarrow as pa
import pyarrow.parquet as pq

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR)))
sys.path.append(_DATA_DIR)
sys.path.append(os.path.join(_DATA_DIR, 'tools', 'statvar_importer'))

import mcf_file_util

_MIB = 1024 * 1024
_DEFAULT_SHARD_SIZE_BYTES = 500 * _MIB
_DEFAULT_WORKERS = 8
_PARQUET_BATCH_SIZE = 100_000
_OUTPUT_FORMATS = ('parquet', 'avro')
_PARQUET_COLUMNS = (
    '_node_key',
    'Node',
    'dcid',
    'typeOf',
    'name',
    'variableMeasured',
    'observationAbout',
    'observationDate',
    'observationPeriod',
    'measurementMethod',
    'unit',
    'scalingFactor',
    'value',
    'extra_properties_json',
)
_GENERATED_COLUMNS = {'_node_key', 'extra_properties_json'}
_CSV_KEY_COLUMN = 'key'
# BigQuery maps an Avro string annotated with sqlType JSON to its native JSON
# type when the file is loaded with source_format=AVRO.
_AVRO_SCHEMA = {
    'type':
        'record',
    'name':
        'McfNode',
    'fields': [{
        'name': column,
        'type': ['null', 'string'],
        'default': None,
    } for column in _PARQUET_COLUMNS if column != 'extra_properties_json'] + [{
        'name': 'extra_properties_json',
        'type': [
            'null',
            {
                'type': 'string',
                'sqlType': 'JSON',
            },
        ],
        'default': None,
    }],
}


class BinaryShardingWriter:
    """Writes bytes to MCF shards without splitting node blocks."""

    def __init__(self, base_path: Path, shard_size: int):
        self._base_path = base_path
        self._shard_size = shard_size
        self._shard_index = 0
        self._shard_bytes = 0
        self._shard_file = None
        self._shard_path = None

    def write(self, data: bytes) -> Path | None:
        if self._shard_file is None:
            self._shard_path = Path(
                f'{self._base_path}_{self._shard_index}.mcf')
            self._shard_file = self._shard_path.open('wb')

        self._shard_file.write(data)
        self._shard_bytes += len(data)
        if self._shard_bytes > self._shard_size:
            return self.close()
        return None

    def close(self) -> Path | None:
        if self._shard_file is None:
            return None

        self._shard_file.close()
        closed_path = self._shard_path
        self._shard_file = None
        self._shard_path = None
        self._shard_bytes = 0
        self._shard_index += 1
        return closed_path


def _write_node_block(shard_writer: BinaryShardingWriter,
                      node_block: list[bytes]) -> Path | None:
    return shard_writer.write(b''.join(node_block))


def _scan_and_shard(
        input_path: Path, shards_dir: Path, shard_size_bytes: int,
        on_source_ready: Callable[[int, Path],
                                  None]) -> tuple[list[Path], dict]:
    input_size = input_path.stat().st_size
    should_shard = input_size > shard_size_bytes
    input_node_blocks = 0
    node_block = []
    has_content = False
    at_node_boundary = False
    shard_writer = None
    closed_shard = None
    source_paths = []

    def source_ready(source_path: Path):
        source_paths.append(source_path)
        on_source_ready(len(source_paths) - 1, source_path)

    if should_shard:
        shards_dir.mkdir(parents=True)
        shard_writer = BinaryShardingWriter(shards_dir / 'part',
                                            shard_size_bytes)

    try:
        with input_path.open('rb') as input_file:
            for raw_line in input_file:
                is_blank = not raw_line.strip()

                if not is_blank and at_node_boundary:
                    input_node_blocks += 1
                    if should_shard:
                        closed_shard = _write_node_block(
                            shard_writer, node_block)
                        if closed_shard:
                            source_ready(closed_shard)
                    node_block = []
                    has_content = False
                    at_node_boundary = False

                if should_shard:
                    node_block.append(raw_line)

                if is_blank:
                    if has_content:
                        at_node_boundary = True
                else:
                    has_content = True

        if has_content:
            input_node_blocks += 1
        if should_shard and node_block:
            closed_shard = _write_node_block(shard_writer, node_block)
            if closed_shard:
                source_ready(closed_shard)
    finally:
        if shard_writer:
            closed_shard = shard_writer.close()

    if closed_shard:
        source_ready(closed_shard)

    if not should_shard:
        source_ready(input_path)

    shard_summaries = [{
        'file': str(path),
        'bytes': path.stat().st_size,
    } for path in source_paths] if should_shard else []
    return source_paths, {
        'input_bytes': input_size,
        'input_node_blocks': input_node_blocks,
        'was_sharded': should_shard,
        'shards': shard_summaries,
    }


def _convert_mcf_to_csv(source_path: Path, csv_path: Path) -> int:
    logging.info(
        f"Converting MCF to CSV intermediate: {source_path.name} -> {csv_path.name}"
    )
    nodes = mcf_file_util.load_mcf_nodes(str(source_path))
    mcf_file_util.write_mcf_nodes([nodes], str(csv_path))
    if not csv_path.exists():
        csv_path.write_text(f'{_CSV_KEY_COLUMN}\n', encoding='utf-8')
    logging.info(f"Converted {len(nodes)} MCF node(s) to CSV: {csv_path.name}")
    return len(nodes)


def _output_record(csv_row: dict) -> dict:
    record = {
        column: csv_row.get(column) or None
        for column in _PARQUET_COLUMNS
        if column not in _GENERATED_COLUMNS
    }
    record['_node_key'] = (csv_row.get(_CSV_KEY_COLUMN) or
                           csv_row.get('dcid') or csv_row.get('Node') or None)
    extra_properties = {
        key: value
        for key, value in csv_row.items()
        if key not in _PARQUET_COLUMNS and key != _CSV_KEY_COLUMN and value
    }
    record['extra_properties_json'] = (json.dumps(
        extra_properties, ensure_ascii=False, sort_keys=True)
                                       if extra_properties else None)
    return record


def _write_parquet_part(csv_path: Path, parquet_path: Path) -> dict:
    logging.info(
        f"Writing Parquet part from {csv_path.name} -> {parquet_path.name}...")
    schema = pa.schema(
        [pa.field(column, pa.string()) for column in _PARQUET_COLUMNS])
    batch = []
    node_count = 0
    observation_count = 0
    schema_count = 0
    missing_node_id_count = 0

    with csv_path.open('r', encoding='utf-8', newline='') as csv_file:
        reader = csv.DictReader(csv_file)
        with pq.ParquetWriter(parquet_path, schema,
                              compression='zstd') as writer:
            for csv_row in reader:
                record = _output_record(csv_row)
                batch.append(record)
                node_count += 1
                if not record['_node_key']:
                    missing_node_id_count += 1
                if 'StatVarObservation' in str(record['typeOf'] or ''):
                    observation_count += 1
                else:
                    schema_count += 1

                if len(batch) >= _PARQUET_BATCH_SIZE:
                    writer.write_table(
                        pa.Table.from_pylist(batch, schema=schema))
                    batch = []

            if batch:
                writer.write_table(pa.Table.from_pylist(batch, schema=schema))

    logging.info(
        f"Wrote Parquet part {parquet_path.name}: {node_count} nodes "
        f"({observation_count} observations, {schema_count} schema nodes)")
    return {
        'parquet_file': str(parquet_path),
        'parquet_bytes': parquet_path.stat().st_size,
        'parquet_nodes': node_count,
        'observation_nodes': observation_count,
        'schema_nodes': schema_count,
        'missing_node_id_nodes': missing_node_id_count,
    }


def _write_avro_part(csv_path: Path, avro_path: Path) -> dict:
    logging.info(
        f"Writing Avro part from {csv_path.name} -> {avro_path.name}...")
    node_count = 0
    observation_count = 0
    schema_count = 0
    missing_node_id_count = 0

    def records():
        nonlocal node_count
        nonlocal observation_count
        nonlocal schema_count
        nonlocal missing_node_id_count

        with csv_path.open('r', encoding='utf-8', newline='') as csv_file:
            for csv_row in csv.DictReader(csv_file):
                record = _output_record(csv_row)
                node_count += 1
                if not record['_node_key']:
                    missing_node_id_count += 1
                if 'StatVarObservation' in str(record['typeOf'] or ''):
                    observation_count += 1
                else:
                    schema_count += 1
                yield record

    with avro_path.open('wb') as avro_file:
        fastavro.writer(avro_file, _AVRO_SCHEMA, records(), codec='deflate')

    logging.info(
        f"Wrote Avro part {avro_path.name}: {node_count} nodes "
        f"({observation_count} observations, {schema_count} schema nodes)")
    return {
        'avro_file': str(avro_path),
        'avro_bytes': avro_path.stat().st_size,
        'avro_nodes': node_count,
        'observation_nodes': observation_count,
        'schema_nodes': schema_count,
        'missing_node_id_nodes': missing_node_id_count,
    }


def _convert_part(source_path: Path, csv_path: Path, output_path: Path,
                  output_format: str, delete_csv: bool) -> dict:
    mcf_nodes = _convert_mcf_to_csv(source_path, csv_path)
    csv_bytes = csv_path.stat().st_size
    if output_format == 'parquet':
        part_summary = _write_parquet_part(csv_path, output_path)
    else:
        part_summary = _write_avro_part(csv_path, output_path)
    if delete_csv:
        csv_path.unlink()
    return {
        'source_mcf': str(source_path),
        'source_bytes': source_path.stat().st_size,
        'mcf_nodes': mcf_nodes,
        'csv_file': str(csv_path),
        'csv_bytes': csv_bytes,
        'csv_retained': not delete_csv,
        **part_summary,
    }


def convert_mcf_to_bigquery_files(
        input_file: str,
        output_dir: str,
        shard_size_bytes: int = _DEFAULT_SHARD_SIZE_BYTES,
        delete_csv: bool = False,
        workers: int = _DEFAULT_WORKERS,
        output_format: str = 'parquet') -> dict:
    """Converts a local MCF file to CSV and Parquet or Avro parts."""
    input_path = Path(input_file).expanduser().resolve()
    output_path = Path(output_dir).expanduser().resolve()
    if not input_path.is_file():
        raise ValueError(f'Input MCF file does not exist: {input_path}')
    if shard_size_bytes <= 0:
        raise ValueError('Shard size must be greater than zero.')
    if workers <= 0:
        raise ValueError('Workers must be greater than zero.')
    if output_format not in _OUTPUT_FORMATS:
        raise ValueError(
            f"Output format must be one of {', '.join(_OUTPUT_FORMATS)}: {output_format}"
        )
    if output_path.exists() and any(output_path.iterdir()):
        raise ValueError(f'Output directory is not empty: {output_path}')

    logging.info(
        f"Starting MCF to {output_format.title()} conversion: {input_path} "
        f"({input_path.stat().st_size} bytes)")
    output_path.mkdir(parents=True, exist_ok=True)
    shards_dir = output_path / 'mcf_shards'
    csv_dir = output_path / 'csv'
    format_dir = output_path / output_format
    csv_dir.mkdir()
    format_dir.mkdir()

    part_futures = {}
    with ProcessPoolExecutor(max_workers=workers) as executor:

        def submit_part(part_index: int, source_path: Path):
            csv_path = csv_dir / f'part-{part_index:05d}.csv'
            format_path = format_dir / f'part-{part_index:05d}.{output_format}'
            part_futures[part_index] = executor.submit(_convert_part,
                                                       source_path, csv_path,
                                                       format_path,
                                                       output_format,
                                                       delete_csv)

        source_paths, scan_summary = _scan_and_shard(input_path, shards_dir,
                                                     shard_size_bytes,
                                                     submit_part)
        logging.info(
            f"MCF scan complete: {scan_summary['input_node_blocks']} node block(s), "
            f"{len(source_paths)} part(s) to convert (sharded: {scan_summary['was_sharded']})"
        )
        parts = [
            part_futures[part_index].result()
            for part_index in range(len(source_paths))
        ]

    mcf_nodes = sum(part['mcf_nodes'] for part in parts)
    output_nodes = sum(part[f'{output_format}_nodes'] for part in parts)
    summary = {
        'input_file': str(input_path),
        'output_directory': str(output_path),
        'shard_size_bytes': shard_size_bytes,
        'delete_csv': delete_csv,
        'workers': workers,
        'format': output_format,
        **scan_summary,
        'parts': parts,
        'mcf_nodes': mcf_nodes,
        f'{output_format}_schema': (list(_PARQUET_COLUMNS) if output_format
                                    == 'parquet' else _AVRO_SCHEMA),
        f'{output_format}_nodes': output_nodes,
        f'{output_format}_matches_mcf_nodes': output_nodes == mcf_nodes,
    }
    summary_path = output_path / 'summary.json'
    with summary_path.open('w', encoding='utf-8') as summary_file:
        json.dump(summary, summary_file, indent=2)
        summary_file.write('\n')
    logging.info(
        f"MCF to {output_format.title()} conversion complete: {output_nodes} "
        f"{output_format.title()} nodes written across {len(parts)} part(s). "
        f"Summary written to {summary_path}")
    return summary


def main():
    parser = argparse.ArgumentParser(
        description='Shard a local MCF and convert it through CSV.')
    parser.add_argument('--input', required=True, help='Local MCF input file.')
    parser.add_argument(
        '--output-dir',
        required=True,
        help='New or empty directory for MCF shards, CSV, output, and summary.',
    )
    parser.add_argument(
        '--shard-size-bytes',
        type=int,
        default=_DEFAULT_SHARD_SIZE_BYTES,
        help='Soft shard size in bytes (default: 500 MiB).',
    )
    parser.add_argument(
        '--delete-csv',
        action='store_true',
        help='Delete each CSV after its output part is written successfully.',
    )
    parser.add_argument(
        '--format',
        choices=_OUTPUT_FORMATS,
        default='parquet',
        help='Output file format (default: parquet).',
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=_DEFAULT_WORKERS,
        help=f'Parallel conversion processes (default: {_DEFAULT_WORKERS}).',
    )
    args = parser.parse_args()
    summary = convert_mcf_to_bigquery_files(
        args.input,
        args.output_dir,
        shard_size_bytes=args.shard_size_bytes,
        delete_csv=args.delete_csv,
        workers=args.workers,
        output_format=args.format)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
