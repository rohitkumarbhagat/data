# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Search tool for SDMX metadata enrichment."""

import json
import os
from typing import Dict, List

from absl import app
from absl import flags
from absl import logging

import sdmx_metadata_search_providers

_FLAGS = flags.FLAGS


def _define_flags() -> None:
    try:
        flags.DEFINE_string('input_items_json', None,
                            'Path to candidate items JSON file (required).')
        flags.DEFINE_string('output_path', None,
                            'Path to output search results JSON (required).')
        flags.DEFINE_string(
            'search_provider', 'google_custom_search',
            'Search provider name (default: google_custom_search).')
        flags.DEFINE_string('search_api_key',
                            os.environ.get('SEARCH_API_KEY', ''),
                            'Search API key (default: env SEARCH_API_KEY).')
        flags.DEFINE_string(
            'search_engine_id', os.environ.get('SEARCH_ENGINE_ID', ''),
            'Search engine id (default: env SEARCH_ENGINE_ID).')
        flags.DEFINE_integer('num_results', 3,
                             'Max results per query (default: 3).')
        flags.mark_flag_as_required('input_items_json')
        flags.mark_flag_as_required('output_path')
    except flags.DuplicateFlagError:
        pass


def _load_json(path: str) -> Dict:
    with open(path, 'r') as f:
        return json.load(f)


def _write_json(path: str, payload: Dict) -> None:
    with open(path, 'w') as f:
        json.dump(payload, f, indent=2)


def run_search(
    input_items: Dict,
    provider_name: str,
    api_key: str,
    engine_id: str,
    num_results: int,
) -> Dict:
    items = input_items.get('items', [])
    output_items = []

    for item in items:
        queries = item.get('queries', [])
        aggregated_results = []
        for query in queries:
            results = sdmx_metadata_search_providers.run_provider(
                provider_name=provider_name,
                query=query,
                api_key=api_key,
                engine_id=engine_id,
                num_results=num_results,
            )
            aggregated_results.extend(results)

        output_items.append({
            'item_key': item.get('item_key', ''),
            'queries': queries,
            'results': aggregated_results,
        })

    return {'items': output_items}


def main(_: List[str]) -> None:
    input_items = _load_json(_FLAGS.input_items_json)
    output = run_search(
        input_items=input_items,
        provider_name=_FLAGS.search_provider,
        api_key=_FLAGS.search_api_key,
        engine_id=_FLAGS.search_engine_id,
        num_results=_FLAGS.num_results,
    )
    _write_json(_FLAGS.output_path, output)
    logging.info(f"Wrote search results to: {_FLAGS.output_path}")


if __name__ == '__main__':
    _define_flags()
    app.run(main)
