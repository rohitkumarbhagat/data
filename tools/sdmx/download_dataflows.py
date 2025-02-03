import json
import re
import os
import time

from absl import app
from absl import logging
from requests.exceptions import RequestException
from absl import flags
from dataclasses import dataclass, asdict
import requests
from pprint import pprint
from concurrent.futures import ThreadPoolExecutor

FLAGS = flags.FLAGS
flags.DEFINE_string("agency_id", None, "Agency ID to download dataflows from.")
flags.DEFINE_string("download_dir", "./data",
                    "Directory to download dataflows to.")
flags.DEFINE_integer("timeout", 300, "Timeout for HTTP requests in seconds.")
flags.DEFINE_integer("max_executors", 5,
                     "Maximum number of parallel executors.")
# flags.mark_flag_as_required("agency_id", "download_dir")

_HTTP_FAILURE_CODES_TO_SKIP = [404]

SDMX_JSON_SCHEMA_VERSION = "2.0.0"
# SDMX_JSON_SCHEMA_VERSION = "1.0.0"


@dataclass
class Counters:
    successful_data_download_count: int = 0
    failed_data_download_count: int = 0
    successful_dsd_download_count: int = 0
    failed_dsd_download_count: int = 0
    successful_df_structure_download_count: int = 0
    failed_df_structure_download_count: int = 0
    total_df_count: int = 0
    total_df_processed: int = 0


counter = Counters()

# pprint(counter)
# print(asdict(counter))


def read_json_path(path: list, json: dict):
    value = None
    json_root = json
    for part in path:
        if part in json_root:
            value = json_root[part]
            json_root = value
        else:
            return None
    return value


# def test_read_json_path():
#     json_data = {
#         "a": {
#             "b": {
#                 "c": 1,
#                 "d": 2,
#             },
#             "e": 3,
#         },
#         "f": 4,
#     }
#     assert read_json_path(["a", "b", "c"], json_data) == 1
#     assert read_json_path(["a", "e"], json_data) == 3
#     assert read_json_path(["f"], json_data) == 4
#     assert read_json_path(["a", "b", "x"], json_data) is None
#     assert read_json_path(["x"], json_data) is None
#     assert read_json_path([], json_data) is None

# test_read_json_path()


def make_request(url: str,
                 headers: dict = None,
                 params: dict = None,
                 timeout: int = 300):
    """Makes an HTTP request to the given URL.

    Args:
        url: The URL to make the request to.
        headers: The headers to include in the request.
        params: The parameters to include in the request.

        timeout: Timeout for the request in seconds.
    Returns:
        A dictionary containing the response data.

    Raises:
        RequestException: If there was an error making the request.
    """
    try:
        # timeout = 300secs
        response = requests.get(url,
                                headers=headers,
                                params=params,
                                timeout=timeout)
        return response
        # response.raise_for_status()  # Raise an exception for bad status codes
        # return response
    except RequestException as e:
        raise RequestException(f"Error making request to {url}: {e}")


def save_reponse_to_file(response, file_path):
    with open(file_path, 'wb') as file:
        file.write(response.content)


def read_file(file_path):
    with open(file_path, 'r') as file:
        if (file_path.endswith('.json')):
            return json.load(file)
        return file.read()


def download_dataflow_data(base_url: str, agency_id: str, dataflow_id: str,
                           version: str, download_dir: str):
    """Retrieves dataflows from the given agency ID.

    Args:
        base_url: The base URL for the SDMX API.
        agency_id: The ID of the agency to retrieve dataflows from.
        headers: The headers to include in the request.

    Returns:
        A dictionary containing the dataflows.

    Raises:
        RequestException: If there was an error making the request.
        http://51.75.253.167/ADMIN/ws/NSI_WS/rest/data/AFDB,DF_DCS_INFR_AIDI,1.0?detail=full&dimensionAtObservation=TIME_PERIOD
    """
    url = base_url + f"/data/{agency_id},{dataflow_id},{version}"
    save_path = os.path.join(
        download_dir,
        f"dataflow_data__{agency_id}__{dataflow_id}__{version.replace('.', '_')}.csv"
    )
    if os.path.exists(save_path):
        logging.info(
            f"Dataflow {dataflow_id} data already downloaded at {save_path}. Skip downloading"
        )
    else:
        logging.info(f"Starting download of dataflow data from {url}")
        start_time = time.time()
        response = make_request(url,
                                timeout=FLAGS.timeout,
                                headers={
                                    "Accept": "text/csv",
                                    "Content-Encoding": "gzip"
                                },
                                params={
                                    "detail": "full",
                                    "dimensionAtObservation": "TIME_PERIOD"
                                })
        # save to file
        if response.status_code != 200:
            counter.failed_data_download_count += 1
            error_message = f'Failed to download dataflow data from {url} with status code {response.status_code}'
            logging.error(error_message)
            # Raise exception unless status code is in skip list
            if response.status_code in _HTTP_FAILURE_CODES_TO_SKIP:
                return None
            raise RequestException(error_message)
        else:
            save_reponse_to_file(response, save_path)
            logging.info(
                f"Downloaded dataflow data from {url} in {time.time() - start_time} seconds"
            )
    counter.successful_data_download_count += 1
    return save_path


# http://51.75.253.167/ADMIN/ws/NSI_WS/rest/datastructure/AFDB/DCS_PRV_SECT_DEV_DB/1.0?detail=full&references=all
def download_dsd(base_url: str, agency_id: str, dsd_id: str, version: str,
                 download_dir: str):
    save_path = os.path.join(
        download_dir,
        f"dsd__{agency_id}__{dsd_id}__{version.replace('.', '_')}.{'json' if SDMX_JSON_SCHEMA_VERSION == '2.0.0' else 'xml'}"
    )
    if os.path.exists(save_path):
        logging.info(
            f"DSD {dsd_id} already downloaded at {save_path}. Skip downloading")
    else:
        start_time = time.time()
        url = base_url + f"/datastructure/{agency_id}/{dsd_id}/{version}"
        logging.info(f"Starting download of dsd from {url}")
        response = make_request(
            url,
            timeout=FLAGS.timeout,
            headers={
                "Accept":
                    "application/json"
                    if SDMX_JSON_SCHEMA_VERSION == "2.0.0" else "text/xml",
                "Content-Encoding":
                    "gzip"
            },
            params={
                "detail": "referencepartial",
                "references": "children"
            })
        # save to file
        if response.status_code != 200:
            counter.failed_dsd_download_count += 1
            err_msg = f'Failed to download dsd from {url} with status code {response.status_code}'
            logging.error(err_msg)
            if response.status_code in _HTTP_FAILURE_CODES_TO_SKIP:
                return None
            raise RequestException(err_msg)
        else:
            save_reponse_to_file(response, save_path)
            logging.info(
                f"Downloaded dsd from {url} in {time.time() - start_time} seconds"
            )
    counter.successful_dsd_download_count += 1
    return save_path


# http://51.75.253.167/ADMIN/ws/NSI_WS/rest/dataflow/AFDB/DF_DCS_INFR_AIDI/1.0/?detail=Full&references=Descendants
def download_dataflow_structure(base_url: str, agency_id: str, dataflow_id: str,
                                version: str, download_dir: str):
    save_path = os.path.join(
        download_dir,
        f"df_structure__{agency_id}__{dataflow_id}__{version.replace('.', '_')}.json"
    )
    if os.path.exists(save_path):
        logging.info(
            f"Dataflow {dataflow_id} structure already downloaded at {save_path}. Skip downloading"
        )
    else:
        start_time = time.time()
        url = base_url + f"/dataflow/{agency_id}/{dataflow_id}/{version}"
        logging.info(f"Starting download of dataflow structure from {url}")
        response = make_request(url,
                                timeout=FLAGS.timeout,
                                headers={
                                    "Accept": "text/json",
                                    "Content-Encoding": "gzip"
                                },
                                params={
                                    "detail": "full",
                                    "references": "Descendants"
                                })
        # save to file
        if response.status_code != 200:
            counter.failed_df_structure_download_count += 1
            error_message = f'Failed to download dataflow structure from {url} with status code {response.status_code}'
            logging.error(error_message)
            # Raise exception unless status code is in skip list
            if response.status_code in _HTTP_FAILURE_CODES_TO_SKIP:
                return None
            raise RequestException(error_message)
        else:
            save_reponse_to_file(response, save_path)
            logging.info(
                f"Downloaded dataflow structure from {url} in {time.time() - start_time} seconds"
            )
    counter.successful_df_structure_download_count += 1
    return save_path


def create_short_urn(agency, resource_id, version):
    return f"{agency}:{resource_id}({version})"


def extract_short_urn(full_urn):
    return full_urn.split("=")[-1]


# AFDB:DF_DCS_INFR_AIDI(1.0)
def parse_short_urn(short_urn):
    match = re.match(r"([^:]+):([^(\)]+)\(([^)]+)\)", short_urn)
    if match:
        return match.group(1), match.group(2), match.group(3)
    raise ValueError(
        f"Invalid short URN format: {short_urn}. valid e.g. AFDB:DF_DCS_INFR_AIDI(1.0)"
    )


# print(parse_short_urn("AFDB:DF_DCS_INFR_AIDI(1.0)"))


def download_dataflow(base_url: str, agency_id: str, dataflow_id: str,
                      version: str, download_dir: str):
    try:
        dataflow_download_dir = os.path.join(
            download_dir,
            f"{agency_id}__{dataflow_id}__{version.replace('.', '_')}")
        os.makedirs(dataflow_download_dir, exist_ok=True)
        # should be part of same agency
        df_struct_path = download_dataflow_structure(base_url, agency_id,
                                                     dataflow_id, version,
                                                     dataflow_download_dir)
        if df_struct_path is None:
            return None
        df_struct = read_file(df_struct_path)
        # download dsd
        # find out dsd path
        # urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=AFDB:DF_DCS_INFR_AIDI(1.0)
        if SDMX_JSON_SCHEMA_VERSION == "2.0.0":
            dsd_urn = df_struct["data"]["dataStructures"][0]["links"][0]["urn"]
        else:
            dsd_urn = df_struct["references"][
                f"urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow={create_short_urn(agency_id, dataflow_id, version)}"][
                    "structure"]["urn"]
        df_agency, dsd_id, dsd_version = parse_short_urn(
            extract_short_urn(dsd_urn))
        # NOTE: dsd_agency can be different from df_agency
        dsd_path = download_dsd(base_url, df_agency, dsd_id, dsd_version,
                                dataflow_download_dir)
        if dsd_path is None:
            return None
        # download data
        # data should be owned by same agency
        data_path = download_dataflow_data(base_url, agency_id, dataflow_id,
                                           version, dataflow_download_dir)
        return df_struct_path, dsd_path, data_path
    finally:
        counter.total_df_processed += 1
        logging.info(
            f"Processed dataflow number {counter.total_df_processed}/{counter.total_df_count}"
        )


# http://51.75.253.167/ADMIN/ws/NSI_WS/rest/dataflow/AFDB/?detail=Full&references=Descendants
def download_all_dataflows(base_url: str, agency_id: str, download_dir: str):
    agency_download_dir = os.path.join(download_dir, agency_id)
    os.makedirs(agency_download_dir, exist_ok=True)
    save_path = os.path.join(agency_download_dir,
                             f"agency_dfs_{agency_id}.json")
    start_time = time.time()
    if os.path.exists(save_path):
        logging.info(
            f"Agency dataflows already downloaded at {save_path}. Skip downloading"
        )
    else:
        logging.info(f"Starting download of all dataflows for {agency_id}")
        start_time = time.time()
        url = base_url + f"/dataflow/{agency_id}"
        logging.info(f"Starting download of all dataflows from {url}")
        response = make_request(
            url,
            timeout=FLAGS.timeout,
            headers={
                "Accept": "application/json",
                "Content-Encoding": "gzip"
            },
            params={
                # "detail": "full",
                # "references": "Descendants"
            })
        # save to file
        if response.status_code != 200:
            err_msg = f'Failed to download all dataflows structure from {url} with status code {response.status_code}'
            logging.error(err_msg)
            raise RequestException(err_msg)
        else:
            save_reponse_to_file(response, save_path)
            logging.info(
                f"Downloaded all dataflows structure from {url} in {time.time() - start_time} seconds"
            )

    # TODO: dsd is also present in this structure. maybe use that instead of downloading for each dataflow
    df_urns = []
    if SDMX_JSON_SCHEMA_VERSION == "2.0.0":
        df_list = read_json_path([
            "data",
            "dataflows",
        ], read_file(save_path))
        for df in df_list:
            df_urns.append(df["links"][0]["urn"])
    else:
        df_urns = read_json_path(["references"], read_file(save_path)).keys()
    logging.info(f"Found {len(df_urns)} dataflows")
    counter.total_df_count = len(df_urns)
    with ThreadPoolExecutor(max_workers=FLAGS.max_executors) as executor:
        for df_urn in df_urns:
            df_agency, df_id, df_version = parse_short_urn(
                extract_short_urn(df_urn))
            # TODO: ideally it should be same, let's see
            assert df_agency == agency_id
            executor.submit(download_dataflow, base_url, agency_id, df_id,
                            df_version, agency_download_dir)
    return save_path


def main(_):
    logging.set_verbosity(logging.INFO)
    logging.info("Starting download")
    start_time = time.time()
    # TODO add flags for all params
    # download_all_dataflows("http://51.75.253.167/ADMIN/ws/NSI_WS/rest",
    #                        FLAGS.agency_id, FLAGS.download_dir)
    # AFDB
    # download_all_dataflows(
    #     "http://51.75.253.167/ADMIN/ws/NSI_WS/rest", "AFDB",
    #     "/usr/local/google/home/rohitrkumar/Documents/dc/projects/sdmx/afdb/download"
    # )
    # ISTAT -a gency - IT1
    download_all_dataflows(
        "https://esploradati.istat.it/SDMXWS/rest", "IT1",
        "/usr/local/google/home/rohitrkumar/Documents/dc/projects/sdmx/IT1/download"
    )

    logging.info(
        f"downloaded all dataflows in {time.time() - start_time} seconds)")
    # pprint(counter)
    # print(asdict(counter))
    logging.info(f"Download metrics:{asdict(counter)}")


if __name__ == '__main__':
    app.run(main)
