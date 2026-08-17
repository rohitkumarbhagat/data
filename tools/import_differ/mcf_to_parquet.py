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
"""Converts a local MCF file into a queryable Parquet dataset.

Usage from the repository root:

  .env/bin/python tools/import_differ/mcf_to_parquet.py \
    --input=/path/to/nodes-deleted.mcf \
    --output-dir=/path/to/output

Files larger than 1 GiB are split at MCF node boundaries using
ShardingWriter's default shard size. Override that size when needed:

  --shard-size-bytes=268435456

The output directory must be new or empty. It contains `mcf_shards/` for a
sharded input, `parquet/` for the Parquet parts, and `summary.json`.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterator

import pyarrow as pa
import pyarrow.parquet as pq

from util.sharding_writer import ShardingWriter

_GIB = 1024 * 1024 * 1024
_PARQUET_BATCH_SIZE = 100_000


def _clean_line(raw_line: bytes) -> str:
    line = raw_line.decode('utf-8', errors='ignore').strip()
    if line and line[0] == '"' and line[-1] == '"':
        line = line[1:-1]
    if line == '""':
        return ''
    if line.count('""') > 1:
        line = line.replace('""', '"')
    return line


def _get_property_value(line: str) -> tuple[str, str]:
    separator = line.find(':')
    if separator < 0:
        return '', line
    return line[:separator].strip(), line[separator + 1:].strip()


def _add_property(node: dict, prop: str, value: str):
    existing_value = node.get(prop)
    if existing_value is None:
        node[prop] = value
    elif isinstance(existing_value, list):
        if value not in existing_value:
            existing_value.append(value)
    elif value != existing_value:
        node[prop] = [existing_value, value]


def _get_node_key(node: dict) -> str | None:
    node_id = node.get('dcid') or node.get('Node')
    if not node_id:
        return None
    if isinstance(node_id, list):
        node_id = node_id[0]
    node_id = str(node_id).strip(' "')
    return node_id if ':' in node_id else f'dcid:{node_id}'


def _iter_mcf_nodes(input_path: Path,
                    counters: dict) -> Iterator[dict[str, object]]:
    node = {}
    with input_path.open('rb') as input_file:
        for raw_line in input_file:
            line = _clean_line(raw_line)
            if not line:
                if node:
                    yield node
                    node = {}
                continue
            if line.startswith('#'):
                counters['comment_lines_ignored'] += 1
                continue

            prop, value = _get_property_value(line)
            if not prop:
                counters['malformed_lines_ignored'] += 1
                continue
            _add_property(node, prop, value)

    if node:
        yield node


def _scan_and_shard(
        input_path: Path, shards_dir: Path, shard_threshold_bytes: int,
        shard_size_bytes: int | None) -> tuple[list[Path], list[str], dict]:
    input_size = input_path.stat().st_size
    should_shard = input_size > shard_threshold_bytes
    property_names = []
    seen_properties = set()
    input_hash = hashlib.sha256()
    input_nodes = 0
    has_property = False
    node_block = []
    shard_writer = None

    if should_shard:
        shards_dir.mkdir(parents=True)
        if shard_size_bytes is None:
            shard_writer = ShardingWriter(str(shards_dir / 'part'))
        else:
            shard_writer = ShardingWriter(str(shards_dir / 'part'),
                                          shard_size=shard_size_bytes)

    try:
        with input_path.open('rb') as input_file:
            for raw_line in input_file:
                input_hash.update(raw_line)
                line = _clean_line(raw_line)
                if should_shard:
                    node_block.append(raw_line)

                if not line:
                    if has_property:
                        input_nodes += 1
                        has_property = False
                    if should_shard:
                        shard_writer.write(b''.join(node_block).decode('utf-8'))
                        node_block = []
                    continue

                if line.startswith('#'):
                    continue
                prop, _ = _get_property_value(line)
                if not prop:
                    continue
                has_property = True
                if prop not in seen_properties:
                    seen_properties.add(prop)
                    property_names.append(prop)

        if has_property:
            input_nodes += 1
        if should_shard and node_block:
            shard_writer.write(b''.join(node_block).decode('utf-8'))
    finally:
        if shard_writer:
            shard_writer.close()

    if should_shard:
        source_paths = sorted(shards_dir.glob('part_*.mcf'),
                              key=lambda path: int(path.stem.rsplit('_', 1)[1]))
    else:
        source_paths = [input_path]
    shard_summaries = [{
        'file': str(path),
        'bytes': path.stat().st_size,
    } for path in source_paths] if should_shard else []

    scan_summary = {
        'input_bytes': input_size,
        'input_sha256': input_hash.hexdigest(),
        'input_nodes': input_nodes,
        'was_sharded': should_shard,
        'shards': shard_summaries,
    }
    return source_paths, property_names, scan_summary


def _parquet_value(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _write_parquet_part(source_path: Path, parquet_path: Path,
                        schema: pa.Schema) -> dict:
    counters = {
        'comment_lines_ignored': 0,
        'malformed_lines_ignored': 0,
    }
    batch = []
    node_count = 0
    observation_count = 0
    schema_count = 0
    missing_node_id_count = 0

    with pq.ParquetWriter(parquet_path, schema, compression='zstd') as writer:
        for node in _iter_mcf_nodes(source_path, counters):
            node_key = _get_node_key(node)
            if not node_key:
                missing_node_id_count += 1
            record = {
                prop: _parquet_value(value) for prop, value in node.items()
            }
            record['_node_key'] = node_key
            batch.append(record)
            node_count += 1
            if 'StatVarObservation' in str(node.get('typeOf', '')):
                observation_count += 1
            else:
                schema_count += 1

            if len(batch) >= _PARQUET_BATCH_SIZE:
                writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                batch = []

        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=schema))

    return {
        'source_mcf': str(source_path),
        'source_bytes': source_path.stat().st_size,
        'parquet_file': str(parquet_path),
        'parquet_bytes': parquet_path.stat().st_size,
        'nodes': node_count,
        'observation_nodes': observation_count,
        'schema_nodes': schema_count,
        'missing_node_id_nodes': missing_node_id_count,
        **counters,
    }


def convert_mcf_to_parquet(input_file: str,
                           output_dir: str,
                           shard_threshold_bytes: int = _GIB,
                           shard_size_bytes: int | None = None) -> dict:
    """Converts a local MCF file to Parquet parts and returns its summary."""
    input_path = Path(input_file).expanduser().resolve()
    output_path = Path(output_dir).expanduser().resolve()
    if not input_path.is_file():
        raise ValueError(f'Input MCF file does not exist: {input_path}')
    if shard_threshold_bytes <= 0:
        raise ValueError('Shard threshold must be greater than zero.')
    if shard_size_bytes is not None and shard_size_bytes <= 0:
        raise ValueError('Shard size must be greater than zero.')
    if output_path.exists() and any(output_path.iterdir()):
        raise ValueError(f'Output directory is not empty: {output_path}')

    output_path.mkdir(parents=True, exist_ok=True)
    shards_dir = output_path / 'mcf_shards'
    parquet_dir = output_path / 'parquet'
    parquet_dir.mkdir()

    source_paths, property_names, scan_summary = _scan_and_shard(
        input_path, shards_dir, shard_threshold_bytes, shard_size_bytes)
    parquet_schema = pa.schema([pa.field('_node_key', pa.string())] + [
        pa.field(prop, pa.string())
        for prop in property_names
        if prop != '_node_key'
    ])

    parquet_parts = []
    for part_index, source_path in enumerate(source_paths):
        parquet_path = parquet_dir / f'part-{part_index:05d}.parquet'
        parquet_parts.append(
            _write_parquet_part(source_path, parquet_path, parquet_schema))

    converted_nodes = sum(part['nodes'] for part in parquet_parts)
    summary = {
        'input_file': str(input_path),
        'output_directory': str(output_path),
        'shard_threshold_bytes': shard_threshold_bytes,
        'requested_shard_size_bytes': shard_size_bytes,
        **scan_summary,
        'parquet_schema': parquet_schema.names,
        'parquet_parts': parquet_parts,
        'parquet_nodes': converted_nodes,
        'node_count_matches': converted_nodes == scan_summary['input_nodes'],
    }
    summary_path = output_path / 'summary.json'
    with summary_path.open('w', encoding='utf-8') as summary_file:
        json.dump(summary, summary_file, indent=2)
        summary_file.write('\n')
    return summary


def main():
    parser = argparse.ArgumentParser(
        description='Shard a large local MCF and convert it to Parquet parts.')
    parser.add_argument('--input', required=True, help='Local MCF input file.')
    parser.add_argument(
        '--output-dir',
        required=True,
        help='New or empty directory for MCF shards, Parquet, and summary.',
    )
    parser.add_argument(
        '--shard-size-bytes',
        type=int,
        help=
        'Optional MCF shard size; ShardingWriter default is used if absent.',
    )
    args = parser.parse_args()
    summary = convert_mcf_to_parquet(args.input,
                                     args.output_dir,
                                     shard_size_bytes=args.shard_size_bytes)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
