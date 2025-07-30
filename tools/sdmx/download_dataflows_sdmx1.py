#!/usr/bin/env python3
"""Download SDMX dataflows using the native sdmx1 library.

This script uses the sdmx1 library's native functionality to download:
- Dataflow structures
- Data Structure Definitions (DSDs)
- Actual statistical data

Usage:
1. For predefined sources (ECB, IMF, WB, etc.):
   python download_dataflows_sdmx1.py --source=ECB --agency_id=ECB

2. For custom SDMX endpoints:
   python download_dataflows_sdmx1.py --base_url=https://api.example.com/sdmx/rest --agency_id=MYORG

The script automatically uses built-in methods when using predefined sources,
providing cleaner code and better performance.
"""

import os
import time
import logging
import json
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple, Union

from absl import app, flags
import sdmx
import pandas as pd

# Command-line flags
FLAGS = flags.FLAGS
flags.DEFINE_string("base_url", None, "Base URL of the SDMX REST API endpoint (for custom sources).")
flags.DEFINE_string("agency_id", None, "Agency ID to download dataflows from.")
flags.DEFINE_string("source", None, "Predefined source name (e.g., ECB, IMF, WB). If provided, base_url is ignored.")
flags.DEFINE_string("download_dir", "./data",
                    "Directory to download dataflows to.")
flags.DEFINE_integer("timeout", 300, "Timeout for HTTP requests in seconds.")
flags.DEFINE_integer("max_executors", 5,
                     "Maximum number of parallel executors.")

flags.mark_flag_as_required("agency_id")


@dataclass
class Counters:
    """Track download statistics."""
    successful_data_download_count: int = 0
    failed_data_download_count: int = 0
    successful_dsd_download_count: int = 0
    failed_dsd_download_count: int = 0
    successful_df_structure_download_count: int = 0
    failed_df_structure_download_count: int = 0
    total_df_count: int = 0
    total_df_processed: int = 0


counter = Counters()


def create_sdmx_client(source: Optional[str], base_url: Optional[str], 
                      agency_id: str, timeout: int) -> Tuple[sdmx.Client, bool]:
    """Create an SDMX client for predefined or custom sources.
    
    Args:
        source: Predefined source name (e.g., 'ECB', 'IMF') or None.
        base_url: Base URL for custom sources (ignored if source is provided).
        agency_id: Agency identifier.
        timeout: Request timeout in seconds.
        
    Returns:
        Tuple of (configured SDMX client, is_predefined_source).
    """
    if source:
        # Try to use predefined source
        try:
            client = sdmx.Client(source, timeout=timeout)
            logging.info(f"Using predefined source: {source}")
            return client, True
        except ValueError:
            logging.warning(f"Unknown predefined source '{source}', falling back to custom endpoint")
    
    if not base_url:
        raise ValueError("Either --source or --base_url must be provided")
    
    # Create generic client for custom endpoint
    client = sdmx.Client(timeout=timeout)
    
    # Optionally configure as a custom source
    if source:
        custom_source = {
            "id": source.upper(),
            "name": source,
            "url": base_url.rstrip('/'),
            "api_version": "2.1"
        }
        try:
            client.add_source(json.dumps(custom_source))
            logging.info(f"Configured custom source: {source} at {base_url}")
        except Exception as e:
            logging.warning(f"Could not configure custom source: {e}")
    
    return client, False


def download_dataflow_structure(client: sdmx.Client, base_url: str,
                                agency_id: str, dataflow_id: str, version: str,
                                download_dir: str, is_predefined: bool) -> Optional[str]:
    """Download dataflow structure with all references.
    
    This retrieves the dataflow definition along with its DSD and related structures.
    
    Args:
        client: SDMX client instance.
        base_url: Base URL of the SDMX endpoint.
        agency_id: Agency identifier.
        dataflow_id: Dataflow identifier.
        version: Dataflow version.
        download_dir: Directory to save files.
        is_predefined: Whether using a predefined source.
        
    Returns:
        Path to saved file or None if failed.
    """
    save_path = os.path.join(
        download_dir,
        f"df_structure__{agency_id}__{dataflow_id}__{version.replace('.', '_')}.xml"
    )

    if os.path.exists(save_path):
        logging.info(
            f"Dataflow {dataflow_id} structure already downloaded at {save_path}"
        )
        counter.successful_df_structure_download_count += 1
        return save_path

    try:
        start_time = time.time()
        
        if is_predefined:
            # Use built-in method for predefined sources
            logging.info(f"Downloading dataflow structure using built-in method: {dataflow_id}")
            response = client.dataflow(dataflow_id, tofile=save_path)
        else:
            # Fall back to manual URL construction for custom endpoints
            url = f"{base_url}/dataflow/{agency_id}/{dataflow_id}/{version}"
            logging.info(f"Downloading dataflow structure from {url}")
            
            response = client.get(
                url=url,
                params={
                    'references': 'all',  # Gets DSD, codelists, concepts
                    'detail': 'full'
                },
                tofile=save_path  # Direct file saving
            )

        logging.info(
            f"Downloaded dataflow structure in {time.time() - start_time:.2f} seconds"
        )
        counter.successful_df_structure_download_count += 1
        return save_path

    except Exception as e:
        counter.failed_df_structure_download_count += 1
        logging.error(f"Failed to download dataflow structure: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
            if e.response.status_code == 404:
                return None
        raise


def download_dsd(client: sdmx.Client, base_url: str, agency_id: str,
                 dsd_id: str, version: str, download_dir: str, is_predefined: bool) -> Optional[str]:
    """Download Data Structure Definition.
    
    Note: When using references='all' with dataflow, the DSD is included.
    This method is for cases where you need the DSD separately.
    
    Args:
        client: SDMX client instance.
        base_url: Base URL of the SDMX endpoint.
        agency_id: Agency that maintains the DSD.
        dsd_id: DSD identifier.
        version: DSD version.
        download_dir: Directory to save files.
        
    Returns:
        Path to saved file or None if failed.
    """
    save_path = os.path.join(
        download_dir,
        f"dsd__{agency_id}__{dsd_id}__{version.replace('.', '_')}.xml")

    if os.path.exists(save_path):
        logging.info(f"DSD {dsd_id} already downloaded at {save_path}")
        counter.successful_dsd_download_count += 1
        return save_path

    try:
        start_time = time.time()
        url = f"{base_url}/datastructure/{agency_id}/{dsd_id}/{version}"
        logging.info(f"Downloading DSD from {url}")

        response = client.get(
            url=url,
            params={
                'references': 'children',  # Include codelists, concepts
                'detail': 'referencepartial'
            },
            tofile=save_path)

        logging.info(
            f"Downloaded DSD in {time.time() - start_time:.2f} seconds")
        counter.successful_dsd_download_count += 1
        return save_path

    except Exception as e:
        counter.failed_dsd_download_count += 1
        logging.error(f"Failed to download DSD: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
            if e.response.status_code == 404:
                return None
        raise


def download_dataflow_data(client: sdmx.Client, base_url: str, agency_id: str,
                           dataflow_id: str, version: str,
                           download_dir: str, is_predefined: bool) -> Optional[str]:
    """Download actual statistical data for a dataflow.
    
    Args:
        client: SDMX client instance.
        base_url: Base URL of the SDMX endpoint.
        agency_id: Agency identifier.
        dataflow_id: Dataflow identifier.
        version: Dataflow version.
        download_dir: Directory to save files.
        
    Returns:
        Path to saved CSV file or None if failed.
    """
    save_path = os.path.join(
        download_dir,
        f"dataflow_data__{agency_id}__{dataflow_id}__{version.replace('.', '_')}.csv"
    )

    if os.path.exists(save_path):
        logging.info(
            f"Dataflow {dataflow_id} data already downloaded at {save_path}")
        counter.successful_data_download_count += 1
        return save_path

    try:
        start_time = time.time()
        url = f"{base_url}/data/{agency_id},{dataflow_id},{version}"
        logging.info(f"Downloading dataflow data from {url}")

        # Get data using native SDMX client
        response = client.get(url=url,
                              params={
                                  'detail': 'full',
                                  'dimensionAtObservation': 'TIME_PERIOD'
                              })

        # Convert to pandas and save as CSV
        try:
            df = sdmx.to_pandas(response)
            # Handle different return types from to_pandas
            if isinstance(df, pd.Series):
                df = df.to_frame()
            elif isinstance(df, dict):
                # If multiple datasets, concatenate them
                df = pd.concat(df.values(), ignore_index=True)

            df.to_csv(save_path, index=True)
            logging.info(
                f"Downloaded and converted data in {time.time() - start_time:.2f} seconds"
            )

        except Exception as e:
            logging.warning(
                f"Failed to convert to pandas, saving as SDMX-CSV: {e}")
            # Fallback to SDMX-CSV format
            sdmx.to_csv(response, path=save_path)

        counter.successful_data_download_count += 1
        return save_path

    except Exception as e:
        counter.failed_data_download_count += 1
        logging.error(f"Failed to download dataflow data: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
            if e.response.status_code == 404:
                return None
        raise


def download_dataflow(client: sdmx.Client, base_url: str, agency_id: str,
                      dataflow_id: str, version: str,
                      download_dir: str, is_predefined: bool) -> Optional[Tuple[str, str, str]]:
    """Download complete dataflow: structure, DSD, and data.
    
    Args:
        client: SDMX client instance.
        base_url: Base URL of the SDMX endpoint.
        agency_id: Agency identifier.
        dataflow_id: Dataflow identifier.
        version: Dataflow version.
        download_dir: Directory to save files.
        
    Returns:
        Tuple of (structure_path, dsd_path, data_path) or None if failed.
    """
    try:
        # Create dataflow-specific directory
        dataflow_download_dir = os.path.join(
            download_dir,
            f"{agency_id}__{dataflow_id}__{version.replace('.', '_')}")
        os.makedirs(dataflow_download_dir, exist_ok=True)

        # Download dataflow structure with all references (includes DSD)
        df_struct_path = download_dataflow_structure(client, base_url,
                                                     agency_id, dataflow_id,
                                                     version,
                                                     dataflow_download_dir,
                                                     is_predefined)
        if df_struct_path is None:
            return None

        # Read the structure to get DSD info (if needed separately)
        # Note: With references='all', the DSD is already included in the structure file
        try:
            msg = sdmx.read_sdmx(df_struct_path)
            dataflow = msg.dataflow[f"{agency_id}:{dataflow_id}({version})"]
            dsd_ref = dataflow.structure

            # Extract DSD identifiers from reference
            if hasattr(dsd_ref, 'id'):
                dsd_id = dsd_ref.id
                dsd_version = dsd_ref.version
                dsd_agency = dsd_ref.maintainer.id if hasattr(
                    dsd_ref.maintainer, 'id') else agency_id
            else:
                # Fallback: DSD might have same ID as dataflow
                dsd_id = dataflow_id
                dsd_version = version
                dsd_agency = agency_id

            # Download DSD separately (optional, as it's included in structure with references='all')
            dsd_path = download_dsd(client, base_url, dsd_agency, dsd_id,
                                    dsd_version, dataflow_download_dir, is_predefined)
        except Exception as e:
            logging.warning(
                f"Could not extract DSD info, using dataflow ID: {e}")
            dsd_path = None

        # Download the actual data
        data_path = download_dataflow_data(client, base_url, agency_id,
                                           dataflow_id, version,
                                           dataflow_download_dir, is_predefined)

        return df_struct_path, dsd_path, data_path

    finally:
        counter.total_df_processed += 1
        logging.info(
            f"Processed dataflow {counter.total_df_processed}/{counter.total_df_count}"
        )


def download_all_dataflows(client: sdmx.Client, base_url: str, agency_id: str,
                           download_dir: str, is_predefined: bool) -> str:
    """Download all dataflows for an agency.
    
    Args:
        client: SDMX client instance.
        base_url: Base URL of the SDMX endpoint.
        agency_id: Agency identifier.
        download_dir: Directory to save files.
        is_predefined: Whether using a predefined source.
        
    Returns:
        Path to the saved agency dataflows file.
    """
    agency_download_dir = os.path.join(download_dir, agency_id)
    os.makedirs(agency_download_dir, exist_ok=True)

    save_path = os.path.join(agency_download_dir,
                             f"agency_dataflows_{agency_id}.xml")

    if os.path.exists(save_path):
        logging.info(f"Agency dataflows already downloaded at {save_path}")
    else:
        logging.info(f"Downloading all dataflows for agency {agency_id}")
        start_time = time.time()

        try:
            if is_predefined:
                # Use built-in method for predefined sources
                logging.info("Using built-in dataflow() method")
                response = client.dataflow(tofile=save_path)
            else:
                # Fall back to manual URL for custom endpoints
                url = f"{base_url}/dataflow/{agency_id}"
                response = client.get(url=url, tofile=save_path)
            
            logging.info(
                f"Downloaded all dataflows in {time.time() - start_time:.2f} seconds"
            )
        except Exception as e:
            logging.error(f"Failed to download agency dataflows: {e}")
            raise

    # Read and process dataflows
    logging.info("Processing dataflows list")
    msg = sdmx.read_sdmx(save_path)

    # Extract dataflow information using native SDMX objects
    dataflows = []
    for df_id, dataflow in msg.dataflow.items():
        dataflows.append({
            'id':
                dataflow.id,
            'version':
                dataflow.version,
            'name':
                str(dataflow.name),
            'agency':
                dataflow.maintainer.id
                if hasattr(dataflow.maintainer, 'id') else agency_id
        })

    logging.info(f"Found {len(dataflows)} dataflows")
    counter.total_df_count = len(dataflows)

    # Download each dataflow in parallel
    with ThreadPoolExecutor(max_workers=FLAGS.max_executors) as executor:
        futures = []
        for df_info in dataflows:
            # Verify agency matches (some endpoints return cross-agency dataflows)
            if df_info['agency'] != agency_id:
                logging.warning(
                    f"Skipping dataflow {df_info['id']} from different agency {df_info['agency']}"
                )
                continue

            future = executor.submit(download_dataflow, client, base_url,
                                     agency_id, df_info['id'],
                                     df_info['version'], agency_download_dir, 
                                     is_predefined)
            futures.append(future)

        # Wait for all downloads to complete
        for future in futures:
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error in parallel download: {e}")

    return save_path


def main(_):
    """Main entry point."""
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info("Starting SDMX download using native sdmx1 library")
    start_time = time.time()

    # Create SDMX client (predefined or custom)
    client, is_predefined = create_sdmx_client(
        source=FLAGS.source,
        base_url=FLAGS.base_url,
        agency_id=FLAGS.agency_id,
        timeout=FLAGS.timeout
    )

    # Download all dataflows for the specified agency
    try:
        download_all_dataflows(client, FLAGS.base_url, FLAGS.agency_id,
                               FLAGS.download_dir, is_predefined)

        logging.info(
            f"Download completed in {time.time() - start_time:.2f} seconds")
        logging.info(f"Download metrics: {asdict(counter)}")

    except Exception as e:
        logging.error(f"Download failed: {e}")
        raise


if __name__ == '__main__':
    app.run(main)
