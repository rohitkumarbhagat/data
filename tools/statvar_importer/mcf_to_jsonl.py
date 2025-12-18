#!/usr/bin/env python3
"""Convert an MCF file to JSONL (one node per line).

Usage:
  python3 mcf_to_jsonl.py --input_mcf=<file.mcf> --output_jsonl=<file.jsonl>

This script uses `mcf_file_util.load_mcf_nodes` and requires `absl-py`.
"""

import json
import os
import sys

from absl import app
from absl import flags
from absl import logging

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_SCRIPT_DIR)
sys.path.append(os.path.dirname(_SCRIPT_DIR))
sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(_SCRIPT_DIR)), 'util'))

from counters import Counters
from mcf_file_util import get_node_dcid, load_mcf_nodes

_FLAGS = flags.FLAGS

flags.DEFINE_string('input', '', 'Input MCF file path.')
flags.DEFINE_string(
    'output',
    '',
    'Output JSONL file path. If not provided, defaults to <input>.jsonl.',
)


def main(_) -> None:
    if not _FLAGS.input:
        raise ValueError('Please provide --input.')

    output_path = _FLAGS.output
    if not output_path:
        if _FLAGS.input.endswith('.mcf'):
            output_path = _FLAGS.input[:-4] + '.jsonl'
        else:
            output_path = _FLAGS.input + '.jsonl'

    counters = Counters()
    nodes = load_mcf_nodes(_FLAGS.input, normalize=True, counters=counters)

    if '' in nodes:
        raise ValueError(f'Found MCF node without dcid in: {_FLAGS.input}')

    merge_errors = counters.get_counter('error-mcf-node-merge')
    if merge_errors:
        raise ValueError(
            f'Found {merge_errors} MCF node merge error(s) in: {_FLAGS.input}'
        )

    seen_dcids = set()
    if os.path.exists(output_path):
        logging.warning('Overwriting existing output file: %s', output_path)
    with open(output_path, 'w', encoding='utf-8') as out:
        for _, node in nodes.items():
            dcid = get_node_dcid(node)
            if not dcid:
                raise ValueError(
                    f'Found MCF node without dcid in: {_FLAGS.input}')
            if dcid in seen_dcids:
                raise ValueError(
                    f'Found duplicate dcid "{dcid}" in: {_FLAGS.input}')
            seen_dcids.add(dcid)
            out.write(
                json.dumps({
                    '_dcid': dcid,
                    **node
                }, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    app.run(main)
