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
"""Orchestrator for SDMX metadata enrichment."""

import json
import os
import re
from typing import Dict, List, Tuple

from absl import app
from absl import flags
from absl import logging

import sdmx_metadata_search
import sdmx_metadata_summarizer

_FLAGS = flags.FLAGS


def _define_flags() -> None:
    try:
        flags.DEFINE_string('input_metadata_json', None,
                            'Path to extractor output JSON (required).')
        flags.DEFINE_string('output_path', None,
                            'Path to enriched JSON output (required).')
        flags.DEFINE_integer('min_name_len', 6,
                             'Minimum name length to skip enrichment.')
        flags.DEFINE_integer('min_desc_len', 30,
                             'Minimum description length to skip enrichment.')
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
        flags.mark_flag_as_required('input_metadata_json')
        flags.mark_flag_as_required('output_path')
    except flags.DuplicateFlagError:
        pass


def _load_json(path: str) -> Dict:
    with open(path, 'r') as f:
        return json.load(f)


def _write_json(path: str, payload: Dict) -> None:
    with open(path, 'w') as f:
        json.dump(payload, f, indent=2)


def _is_opaque_id(value: str) -> bool:
    if not value:
        return False
    return re.fullmatch(r'[A-Z0-9_\-]+', value) is not None


def _needs_enrichment(name: str, description: str, item_id: str,
                      min_name_len: int, min_desc_len: int) -> bool:
    if not name or len(name.strip()) < min_name_len:
        return True
    if not description or len(description.strip()) < min_desc_len:
        return True
    if name.strip() == item_id:
        return True
    if description.strip() == name.strip():
        return True
    if _is_opaque_id(item_id) and not name.strip():
        return True
    return False


def _make_queries(*parts: str) -> List[str]:
    queries = []
    for part in parts:
        if part and part.strip():
            queries.append(part.strip())
    return queries


def _build_code_item(
    dataflow_id: str,
    codelist_id: str,
    codelist_name: str,
    code_id: str,
    code_name: str,
    code_description: str,
) -> Dict:
    item_key = f"code::{codelist_id}::{code_id}"
    base_query = f"SDMX {codelist_name} code {code_id}"
    context_query = f"SDMX {dataflow_id} {codelist_name}"
    return {
        'item_key': item_key,
        'item_type': 'code',
        'id': code_id,
        'name': code_name,
        'description': code_description,
        'parent_id': codelist_id,
        'context': {
            'dataflow_id': dataflow_id,
            'codelist_name': codelist_name,
        },
        'queries': _make_queries(base_query, context_query),
    }


def _build_concept_item(
    dataflow_id: str,
    scheme_id: str,
    scheme_name: str,
    concept_id: str,
    concept_name: str,
    concept_description: str,
) -> Dict:
    item_key = f"concept::{scheme_id}::{concept_id}"
    base_query = f"SDMX {scheme_name} concept {concept_id}"
    context_query = f"SDMX {dataflow_id} {scheme_name}"
    return {
        'item_key': item_key,
        'item_type': 'concept',
        'id': concept_id,
        'name': concept_name,
        'description': concept_description,
        'parent_id': scheme_id,
        'context': {
            'dataflow_id': dataflow_id,
            'concept_scheme_name': scheme_name,
        },
        'queries': _make_queries(base_query, context_query),
    }


def _collect_code_items(dataflow: Dict, min_name_len: int,
                        min_desc_len: int) -> List[Dict]:
    items = []
    dataflow_id = dataflow.get('id', '')
    dsd = dataflow.get('data_structure_definition') or {}
    for component_group in ('dimensions', 'attributes', 'measures'):
        components = dsd.get(component_group, []) or []
        for component in components:
            representation = component.get('representation') or {}
            if representation.get('type') != 'enumerated':
                continue
            codelist = representation.get('codelist') or {}
            codelist_id = codelist.get('id', '')
            codelist_name = codelist.get('name', '')
            for code in codelist.get('codes', []) or []:
                code_id = code.get('id', '')
                code_name = code.get('name', '')
                code_description = code.get('description', '')
                if not _needs_enrichment(code_name, code_description, code_id,
                                         min_name_len, min_desc_len):
                    continue
                items.append(
                    _build_code_item(
                        dataflow_id=dataflow_id,
                        codelist_id=codelist_id,
                        codelist_name=codelist_name,
                        code_id=code_id,
                        code_name=code_name,
                        code_description=code_description,
                    ))
    return items


def _collect_concept_items(dataflow: Dict, min_name_len: int,
                           min_desc_len: int) -> List[Dict]:
    items = []
    dataflow_id = dataflow.get('id', '')
    schemes = dataflow.get('referenced_concept_schemes', []) or []
    for scheme in schemes:
        scheme_id = scheme.get('id', '')
        scheme_name = scheme.get('name', '')
        for concept in scheme.get('concepts', []) or []:
            concept_id = concept.get('id', '')
            concept_name = concept.get('name', '')
            concept_description = concept.get('description', '')
            if not _needs_enrichment(concept_name, concept_description,
                                     concept_id, min_name_len, min_desc_len):
                continue
            items.append(
                _build_concept_item(
                    dataflow_id=dataflow_id,
                    scheme_id=scheme_id,
                    scheme_name=scheme_name,
                    concept_id=concept_id,
                    concept_name=concept_name,
                    concept_description=concept_description,
                ))
    return items


def _scheme_name_map(dataflow: Dict) -> Dict[str, str]:
    schemes = dataflow.get('referenced_concept_schemes', []) or []
    scheme_map = {}
    for scheme in schemes:
        scheme_id = scheme.get('id', '')
        if not scheme_id:
            continue
        scheme_map[scheme_id] = scheme.get('name', '') or scheme_id
    return scheme_map


def _collect_component_concept_items(dataflow: Dict, min_name_len: int,
                                     min_desc_len: int) -> List[Dict]:
    items = []
    dataflow_id = dataflow.get('id', '')
    scheme_map = _scheme_name_map(dataflow)
    dsd = dataflow.get('data_structure_definition') or {}
    for component_group in ('dimensions', 'attributes', 'measures'):
        components = dsd.get(component_group, []) or []
        for component in components:
            concept = component.get('concept') or {}
            concept_id = concept.get('id', '')
            concept_name = concept.get('name', '')
            concept_description = concept.get('description', '')
            scheme_id = concept.get('concept_scheme_id', '')
            scheme_name = scheme_map.get(scheme_id, scheme_id)
            if not _needs_enrichment(concept_name, concept_description,
                                     concept_id, min_name_len, min_desc_len):
                continue
            items.append(
                _build_concept_item(
                    dataflow_id=dataflow_id,
                    scheme_id=scheme_id,
                    scheme_name=scheme_name,
                    concept_id=concept_id,
                    concept_name=concept_name,
                    concept_description=concept_description,
                ))
    return items


def _build_candidates(metadata: Dict, min_name_len: int,
                      min_desc_len: int) -> Dict:
    items_by_key = {}
    for dataflow in metadata.get('dataflows', []) or []:
        for item in _collect_code_items(dataflow, min_name_len, min_desc_len):
            item_key = item.get('item_key')
            if item_key and item_key not in items_by_key:
                items_by_key[item_key] = item
        for item in _collect_concept_items(dataflow, min_name_len,
                                           min_desc_len):
            item_key = item.get('item_key')
            if item_key and item_key not in items_by_key:
                items_by_key[item_key] = item
        for item in _collect_component_concept_items(dataflow, min_name_len,
                                                     min_desc_len):
            item_key = item.get('item_key')
            if item_key and item_key not in items_by_key:
                items_by_key[item_key] = item
    return {'items': list(items_by_key.values())}


def _apply_patch(metadata: Dict, patch: Dict) -> Dict:
    patch_map = {
        item.get('item_key'): item
        for item in patch.get('items', []) or []
        if item.get('item_key')
    }
    for dataflow in metadata.get('dataflows', []) or []:
        dsd = dataflow.get('data_structure_definition') or {}
        for component_group in ('dimensions', 'attributes', 'measures'):
            components = dsd.get(component_group, []) or []
            for component in components:
                representation = component.get('representation') or {}
                if representation.get('type') != 'enumerated':
                    continue
                codelist = representation.get('codelist') or {}
                codelist_id = codelist.get('id', '')
                for code in codelist.get('codes', []) or []:
                    code_id = code.get('id', '')
                    item_key = f"code::{codelist_id}::{code_id}"
                    patch_item = patch_map.get(item_key)
                    if patch_item:
                        enriched_name = patch_item.get('enriched_name')
                        if enriched_name:
                            code['enriched_name'] = enriched_name
                        enriched_description = patch_item.get(
                            'enriched_description')
                        if enriched_description:
                            code['enriched_description'] = enriched_description
        schemes = dataflow.get('referenced_concept_schemes', []) or []
        for scheme in schemes:
            scheme_id = scheme.get('id', '')
            for concept in scheme.get('concepts', []) or []:
                concept_id = concept.get('id', '')
                item_key = f"concept::{scheme_id}::{concept_id}"
                patch_item = patch_map.get(item_key)
                if patch_item:
                    enriched_name = patch_item.get('enriched_name')
                    if enriched_name:
                        concept['enriched_name'] = enriched_name
                    enriched_description = patch_item.get(
                        'enriched_description')
                    if enriched_description:
                        concept['enriched_description'] = enriched_description
        for component_group in ('dimensions', 'attributes', 'measures'):
            components = dsd.get(component_group, []) or []
            for component in components:
                concept = component.get('concept') or {}
                scheme_id = concept.get('concept_scheme_id', '')
                concept_id = concept.get('id', '')
                if not scheme_id or not concept_id:
                    continue
                item_key = f"concept::{scheme_id}::{concept_id}"
                patch_item = patch_map.get(item_key)
                if patch_item:
                    enriched_name = patch_item.get('enriched_name')
                    if enriched_name:
                        concept['enriched_name'] = enriched_name
                    enriched_description = patch_item.get(
                        'enriched_description')
                    if enriched_description:
                        concept['enriched_description'] = enriched_description
    return metadata


def enrich_metadata(
    input_path: str,
    output_path: str,
    min_name_len: int,
    min_desc_len: int,
    provider_name: str,
    api_key: str,
    engine_id: str,
    num_results: int,
) -> None:
    metadata = _load_json(input_path)
    candidates = _build_candidates(metadata, min_name_len, min_desc_len)

    base_path = os.path.splitext(input_path)[0]
    items_path = f"{base_path}_items.json"
    search_path = f"{base_path}_search.json"
    patch_path = f"{base_path}_enrichment.json"

    _write_json(items_path, candidates)

    if os.path.exists(search_path):
        logging.info(f"Search results exist. Reusing: {search_path}")
    else:
        search_output = sdmx_metadata_search.run_search(
            input_items=candidates,
            provider_name=provider_name,
            api_key=api_key,
            engine_id=engine_id,
            num_results=num_results,
        )
        _write_json(search_path, search_output)
        logging.info(f"Wrote search results to: {search_path}")

    if os.path.exists(patch_path):
        logging.info(f"Patch file exists. Reusing: {patch_path}")
    else:
        sdmx_metadata_summarizer.run_summarizer(
            input_items_path=items_path,
            input_search_path=search_path,
            output_path=patch_path,
        )

    patch = _load_json(patch_path)
    enriched = _apply_patch(metadata, patch)
    _write_json(output_path, enriched)
    logging.info(f"Wrote enriched metadata to: {output_path}")


def main(_: List[str]) -> None:
    enrich_metadata(
        input_path=_FLAGS.input_metadata_json,
        output_path=_FLAGS.output_path,
        min_name_len=_FLAGS.min_name_len,
        min_desc_len=_FLAGS.min_desc_len,
        provider_name=_FLAGS.search_provider,
        api_key=_FLAGS.search_api_key,
        engine_id=_FLAGS.search_engine_id,
        num_results=_FLAGS.num_results,
    )


if __name__ == '__main__':
    _define_flags()
    app.run(main)
