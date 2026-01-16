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
"""Search providers for SDMX metadata enrichment."""

import json
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional


def _google_custom_search(
    query: str,
    api_key: str,
    engine_id: str,
    num_results: int,
) -> List[Dict[str, str]]:
    if not api_key:
        raise ValueError("search api key is required")
    if not engine_id:
        raise ValueError("search engine id is required")

    params = {
        'key': api_key,
        'cx': engine_id,
        'q': query,
        'num': num_results,
    }
    url = 'https://www.googleapis.com/customsearch/v1?' + urllib.parse.urlencode(
        params)

    with urllib.request.urlopen(url) as response:
        payload = json.load(response)

    results = []
    for item in payload.get('items', []):
        results.append({
            'title': item.get('title', ''),
            'snippet': item.get('snippet', ''),
            'url': item.get('link', ''),
        })
    return results


_PROVIDERS: Dict[str, Callable[[str, str, str, int], List[Dict[str, str]]]] = {
    'google_custom_search': _google_custom_search,
}


def list_providers() -> List[str]:
    return sorted(_PROVIDERS.keys())


def run_provider(
    provider_name: str,
    query: str,
    api_key: str,
    engine_id: str,
    num_results: int,
) -> List[Dict[str, str]]:
    provider = _PROVIDERS.get(provider_name)
    if provider is None:
        raise ValueError(f"unknown search provider: {provider_name}")
    return provider(query, api_key, engine_id, num_results)
