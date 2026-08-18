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

import json
from pathlib import Path
import tempfile
import unittest

import pyarrow.parquet as pq

from tools.import_differ.bq import mcf_to_parquet

_MCF = b'''Node: obs1
typeOf: dcid:StatVarObservation
variableMeasured: dcid:Count_Person
observationAbout: dcid:country/USA
observationDate: "2024"
value: 1

Node: obs2
typeOf: dcid:StatVarObservation
variableMeasured: dcid:Count_Person
observationAbout: dcid:country/CAN
observationDate: "2024"
measurementMethod: dcid:Census
value: 2


Node: Count_Person
typeOf: dcid:StatisticalVariable
name: "Count Person"
populationType: dcid:Person
statType: dcid:measuredValue
'''


class McfToParquetTest(unittest.TestCase):

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._root = Path(self._temp_dir.name)
        self._input_path = self._root / 'input.mcf'
        self._input_path.write_bytes(_MCF)

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_converts_small_file_without_mcf_shards_and_retains_csv(self):
        output_path = self._root / 'output'

        summary = mcf_to_parquet.convert_mcf_to_parquet(
            str(self._input_path),
            str(output_path),
            shard_size_bytes=len(_MCF),
            workers=1)

        self.assertFalse(summary['was_sharded'])
        self.assertEqual(3, summary['input_node_blocks'])
        self.assertEqual(3, summary['mcf_nodes'])
        self.assertEqual(3, summary['parquet_nodes'])
        self.assertTrue(summary['parquet_matches_mcf_nodes'])
        self.assertFalse((output_path / 'mcf_shards').exists())
        self.assertTrue((output_path / 'csv' / 'part-00000.csv').exists())

        table = pq.read_table(output_path / 'parquet' / 'part-00000.parquet')
        self.assertEqual(3, table.num_rows)
        self.assertEqual(list(mcf_to_parquet._PARQUET_COLUMNS),
                         table.column_names)
        rows = table.to_pylist()
        schema_row = next(row for row in rows if row['Node'] == 'Count_Person')
        self.assertEqual('"Count Person"', schema_row['name'])
        self.assertEqual(
            {
                'populationType': 'dcid:Person',
                'statType': 'dcid:measuredValue',
            }, json.loads(schema_row['extra_properties_json']))

    def test_shards_at_blank_boundaries_and_preserves_input_bytes(self):
        output_path = self._root / 'output'

        summary = mcf_to_parquet.convert_mcf_to_parquet(str(self._input_path),
                                                        str(output_path),
                                                        shard_size_bytes=1,
                                                        workers=2)

        self.assertTrue(summary['was_sharded'])
        self.assertEqual(3, len(summary['shards']))
        shard_paths = [Path(shard['file']) for shard in summary['shards']]
        reconstructed = b''.join(path.read_bytes() for path in shard_paths)
        self.assertEqual(_MCF, reconstructed)
        self.assertEqual(len(_MCF),
                         sum(shard['bytes'] for shard in summary['shards']))

        parquet_paths = sorted((output_path / 'parquet').glob('*.parquet'))
        self.assertEqual(3, len(parquet_paths))
        schemas = [pq.read_schema(path) for path in parquet_paths]
        self.assertTrue(all(schema == schemas[0] for schema in schemas))
        self.assertEqual(3, summary['mcf_nodes'])
        self.assertEqual(3, summary['parquet_nodes'])
        self.assertEqual(2, summary['workers'])

    def test_notifies_when_each_shard_is_ready(self):
        shards_dir = self._root / 'shards'
        ready_paths = []

        def on_source_ready(part_index, source_path):
            self.assertEqual(len(ready_paths), part_index)
            if part_index == 0:
                self.assertFalse((shards_dir / 'part_1.mcf').exists())
            ready_paths.append(source_path)

        source_paths, _ = mcf_to_parquet._scan_and_shard(
            self._input_path, shards_dir, 1, on_source_ready)

        self.assertEqual(source_paths, ready_paths)
        self.assertEqual(3, len(ready_paths))

    def test_deletes_csv_only_when_requested(self):
        output_path = self._root / 'output'

        summary = mcf_to_parquet.convert_mcf_to_parquet(
            str(self._input_path),
            str(output_path),
            shard_size_bytes=len(_MCF),
            delete_csv=True,
            workers=1)

        self.assertTrue(summary['delete_csv'])
        self.assertFalse(summary['parts'][0]['csv_retained'])
        self.assertEqual([], list((output_path / 'csv').iterdir()))


if __name__ == '__main__':
    unittest.main()
