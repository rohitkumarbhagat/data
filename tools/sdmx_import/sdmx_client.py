# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
dataflow.py

This module provides a client class for interacting with SDMX APIs.
"""

import logging
import sdmx
import pandas as pd
from requests.exceptions import HTTPError
from typing import Dict, Any


class SdmxClient:
    """A client for fetching data and metadata from an SDMX REST API."""

    def __init__(self,
                 endpoint: str,
                 agency_id: str,
                 sdmx_version: str = '2.1'):
        """
        Initializes the SdmxClient.

        Args:
            endpoint (str): The base URL of the SDMX REST API endpoint.
            agency_id (str): The ID of the agency providing the data.
            sdmx_version (str): SDMX version to use (default: '2.1').
        """
        self.agency_id = agency_id
        self.endpoint = endpoint
        self.sdmx_version = sdmx_version
        self.client = self._new_sdmx_client()

    def _new_sdmx_client(self) -> sdmx.Client:
        """
        Creates and configures an sdmx.Client for the specified endpoint and agency.
        """
        source_id = self.agency_id
        custom_source = {
            'id': source_id,
            'url': self.endpoint,
            'name': f'Custom source for {self.agency_id}'
        }
        sdmx.add_source(custom_source, override=True)
        return sdmx.Client(source_id)

    def download_metadata(self,
                          dataflow_id: str,
                          output_path: str,
                          version: str = None):
        """
        Fetches the complete metadata for a dataflow and saves it to a file as raw SDMX-ML (XML).

        Args:
            dataflow_id: The ID of the dataflow to retrieve
            output_path: Path where the metadata should be saved
            version: Version of the artifact to retrieve (default: latest)
        """
        try:
            logging.info(
                f"Fetching raw metadata for dataflow: {dataflow_id} (version: {version})..."
            )
            flow_msg = self.client.dataflow(dataflow_id,
                                            agency_id=self.agency_id,
                                            params={'references': 'all'},
                                            tofile=output_path,
                                            version=version)
            logging.info(
                f"Successfully received response: {flow_msg.response.url}")

            logging.info(f"Successfully saved metadata to '{output_path}'")

        except HTTPError as e:
            logging.error(
                f"Network error for {self.agency_id}/{dataflow_id}: {e}")
            if e.response:
                safe_df_id = dataflow_id.replace('@', '_')
                error_filename = f"metadata_error_{safe_df_id}.html"
                with open(error_filename, "w", encoding="utf-8") as f:
                    f.write(e.response.text)
                logging.error(f"URL: {e.response.url}")
                logging.error(f"Response saved to '{error_filename}'")
            raise
        except Exception as e:
            logging.error(
                f"Error processing metadata for {self.agency_id}/{dataflow_id}: {e}"
            )
            raise

    def download_data_as_csv(self,
                             dataflow_id: str,
                             key: Dict[str, Any],
                             params: Dict[str, Any],
                             output_path: str,
                             version: str = None):
        """
        Fetches data, converts it to a pandas DataFrame, and saves as CSV.
        """
        try:
            logging.info(
                f"Fetching data for dataflow: {dataflow_id} (version: {version})"
            )
            logging.info(f"with params: {params}")
            logging.info(f"and key: {key}")
            if self.sdmx_version == '2.1':
                # SDMX 2.1 data query workaround:
                # 1. Fetch DSD explicitly using standard structure query (supports separate params)
                #    This prevents client.data() from doing a broken implicit lookup with the combined ID.
                logging.info("Pre-fetching DSD for SDMX 2.1 compatibility...")
                flow_msg = self.client.dataflow(dataflow_id,
                                                agency_id=self.agency_id,
                                                version=version)
                dsd = flow_msg.dataflow[dataflow_id].structure

                # 2. Construct combined ID for the data query: AGENCY,FLOW,VERSION
                id_parts = [self.agency_id, dataflow_id]
                if version:
                    id_parts.append(version)
                resource_id = ','.join(id_parts)

                # 3. Call client.data with combined ID + pre-fetched DSD
                data_msg = self.client.data(resource_id,
                                            key=key,
                                            params=params,
                                            dsd=dsd)
            else:
                # SDMX 3.0 or other: Pass explicitly
                data_msg = self.client.data(dataflow_id,
                                            key=key,
                                            params=params,
                                            agency_id=self.agency_id,
                                            version=version)
            logging.info(
                f"Successfully received response: {data_msg.response.url}")

            # Write to CSV
            logging.info("Converting response to pandas DataFrame...")
            df = sdmx.to_pandas(data_msg).reset_index()
            df.to_csv(output_path, index=False)
            logging.info(f"Successfully saved data to '{output_path}'")

        except HTTPError as e:
            logging.error(
                f"Network error for {self.agency_id}/{dataflow_id}: {e}")
            if e.response:
                safe_df_id = dataflow_id.replace('@', '_')
                error_filename = f"data_error_{safe_df_id}.html"
                with open(error_filename, "w", encoding="utf-8") as f:
                    f.write(e.response.text)
                logging.error(f"URL: {e.response.url}")
                logging.error(f"Response saved to '{error_filename}'")
            raise
        except Exception as e:
            logging.error(
                f"Error processing data for {self.agency_id}/{dataflow_id}: {e}"
            )
            raise
