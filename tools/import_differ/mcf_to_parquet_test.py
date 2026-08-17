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

from tools.import_differ import mcf_to_parquet

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
'''


class McfToParquetTest(unittest.TestCase):

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._root = Path(self._temp_dir.name)
        self._input_path = self._root / 'input.mcf'
        self._input_path.write_bytes(_MCF)

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_converts_small_file_without_mcf_shards(self):
        output_path = self._root / 'output'

        summary = mcf_to_parquet.convert_mcf_to_parquet(str(self._input_path),
                                                        str(output_path),
                                                        len(_MCF) + 1)

        self.assertFalse(summary['was_sharded'])
        self.assertEqual(3, summary['input_nodes'])
        self.assertEqual(3, summary['parquet_nodes'])
        self.assertTrue(summary['node_count_matches'])
        self.assertFalse((output_path / 'mcf_shards').exists())
        table = pq.read_table(output_path / 'parquet' / 'part-00000.parquet')
        self.assertEqual(3, table.num_rows)
        self.assertIn('measurementMethod', table.column_names)

    def test_shards_at_node_boundaries_and_uses_one_parquet_schema(self):
        output_path = self._root / 'output'

        summary = mcf_to_parquet.convert_mcf_to_parquet(str(self._input_path),
                                                        str(output_path),
                                                        shard_threshold_bytes=1,
                                                        shard_size_bytes=1)

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
        self.assertEqual(3, summary['parquet_nodes'])
        self.assertEqual(
            2,
            sum(part['observation_nodes'] for part in summary['parquet_parts']))
        self.assertEqual(
            1, sum(part['schema_nodes'] for part in summary['parquet_parts']))

        with (output_path / 'summary.json').open('r', encoding='utf-8') as file:
            saved_summary = json.load(file)
        self.assertEqual(summary, saved_summary)


if __name__ == '__main__':
    unittest.main()
