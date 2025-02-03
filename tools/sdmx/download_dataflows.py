import json
import re
import os
import time
from urllib.parse import urljoin

from absl import app
from absl import logging
from requests.exceptions import RequestException
from absl import flags

import requests

FLAGS = flags.FLAGS
flags.DEFINE_string("agency_id", None, "Agency ID to download dataflows from.")
flags.DEFINE_string("download_dir", "./data",
                    "Directory to download dataflows to.")
flags.mark_flag_as_required("agency_id", "download_dir")


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


def make_request(url: str, headers: dict = None, params: dict = None):
    """Makes an HTTP request to the given URL.

    Args:
        url: The URL to make the request to.
        headers: The headers to include in the request.
        params: The parameters to include in the request.

    Returns:
        A dictionary containing the response data.

    Raises:
        RequestException: If there was an error making the request.
    """
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response
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
    url = urljoin(base_url, f"/data/{agency_id},{dataflow_id},{version}")
    save_path = os.path.join(
        download_dir,
        f"dataflow_data__{agency_id}__{dataflow_id}__{version.replace('.', '_')}.csv"
    )
    if os.path.exists(save_path):
        logging.info(
            f"Dataflow data already downloaded at {save_path}. Skip downloading"
        )
    else:
        response = make_request(url,
                                headers={
                                    "Accept": "text/csv",
                                    "Content-Encoding": "gzip"
                                },
                                params={
                                    "detail": "full",
                                    "dimensionAtObservation": "TIME_PERIOD)}"
                                })
        # save to file
        if response.status_code != 200:
            logging.fatal(f'Failed to download datraflow from {url} )')

        save_reponse_to_file(response, save_path)
    return save_path


# http://51.75.253.167/ADMIN/ws/NSI_WS/rest/datastructure/AFDB/DCS_PRV_SECT_DEV_DB/1.0?detail=full&references=all
def download_dsd(base_url: str, agency_id: str, dsd_id: str, version: str,
                 download_dir: str):
    url = urljoin(base_url, f"/datastructure/{agency_id},{dsd_id},{version}")
    save_path = os.path.join(
        download_dir,
        f"dsd__{agency_id}__{dsd_id}__{version.replace('.', '_')}.xml")
    if os.path.exists(save_path):
        logging.info(f"DSD already downloaded at {save_path}. Skip downloading")
    else:
        response = make_request(url,
                                headers={
                                    "Accept": "application/xml",
                                    "Content-Encoding": "gzip"
                                },
                                params={
                                    "detail": "referencepartial",
                                    "references": "children"
                                })
        # save to file
        if response.status_code != 200:
            logging.fatal(f'Failed to download dsd from {url} )')

        save_reponse_to_file(response, save_path)
    return save_path


# http://51.75.253.167/ADMIN/ws/NSI_WS/rest/dataflow/AFDB/DF_DCS_INFR_AIDI/1.0/?detail=Full&references=Descendants
def download_dataflow_structure(base_url: str, agency_id: str, dataflow_id: str,
                                version: str, download_dir: str):
    url = urljoin(base_url, f"/dataflow/{agency_id},{dataflow_id},{version}")
    save_path = os.path.join(
        download_dir,
        f"df_structure__{agency_id}__{dataflow_id}__{version.replace('.', '_')}.json"
    )
    if os.path.exists(save_path):
        logging.info(
            f"Dataflow structure already downloaded at {save_path}. Skip downloading"
        )
    else:
        response = make_request(url,
                                headers={
                                    "Accept": "text/json",
                                    "Content-Encoding": "gzip"
                                },
                                params={
                                    "detail": "full",
                                    "references": "Descendants)}"
                                })
        # save to file
        if response.status_code != 200:
            logging.fatal(
                f'Failed to download datraflow structure from {url} )')

        save_reponse_to_file(response, save_path)
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
    dataflow_download_dir = os.path.join(
        download_dir,
        f"{agency_id}__{dataflow_id}__{version.replace('.', '_')}")
    os.makedirs(dataflow_download_dir, exist_ok=True)
    df_struct_path = download_dataflow_structure(base_url, agency_id,
                                                 dataflow_id, version,
                                                 dataflow_download_dir)
    df_struct = read_file(df_struct_path)
    # download dsd
    # find out dsd path
    # urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=AFDB:DF_DCS_INFR_AIDI(1.0)
    dsd_urn = df_struct["references"][
        f"urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow={create_short_urn(agency_id, dataflow_id, version)}"][
            "structure"]["urn"]
    _, dsd_id, dsd_version = parse_short_urn(dsd_urn)
    dsd_path = download_dsd(base_url, agency_id, dsd_id, dsd_version,
                            dataflow_download_dir)
    # download data
    data_path = download_dataflow_data(base_url, agency_id, dataflow_id,
                                       version, dataflow_download_dir)
    return df_struct_path, dsd_path, data_path


# http://51.75.253.167/ADMIN/ws/NSI_WS/rest/dataflow/AFDB/?detail=Full&references=Descendants
def download_all_dataflows(base_url: str, agency_id: str, download_dir: str):
    agency_download_dir = os.path.join(download_dir, agency_id)
    os.makedirs(agency_download_dir, exist_ok=True)
    save_path = os.path.join(agency_download_dir,
                             f"agency_dfs_{agency_id}.json")
    if os.path.exists(save_path):
        logging.info(
            f"Agency dataflows already downloaded at {save_path}. Skip downloading"
        )
    else:
        url = urljoin(base_url, f"/dataflow/{agency_id}")
        response = make_request(url,
                                headers={
                                    "Accept": "application/json",
                                    "Content-Encoding": "gzip"
                                },
                                params={
                                    "detail": "full",
                                    "references": "Descendants"
                                })
        # save to file
        if response.status_code != 200:
            logging.fatal(
                f'Failed to download all dataflows structure from {url} )')
        save_reponse_to_file(response, save_path)
    # TODO: dsd is also present in this structure. maybe use that instead of downloading for each dataflow
    df_urns = read_json_path(["references"], read_file(save_path)).keys()
    for df_urn in df_urns:
        df_agency, df_id, df_version = parse_short_urn(df_urn)
        assert df_agency == agency_id
        download_dataflow(base_url, agency_id, df_id, df_version,
                          agency_download_dir)
    return save_path


def main(_):
    logging.set_verbosity(logging.INFO)
    start_time = time.time()
    # TODO add flags for all params
    # download_all_dataflows("http://51.75.253.167/ADMIN/ws/NSI_WS/rest",
    #                        FLAGS.agency_id, FLAGS.download_dir)
    download_all_dataflows("http://51.75.253.167/ADMIN/ws/NSI_WS/rest",
                           "AFDB", "/usr/local/google/home/rohitrkumar/Documents/dc/projects/sdmx/afdb/download")
    logging.info(
        f"downloaded all dataflows in {time.time() - start_time} seconds)")


if __name__ == '__main__':
    app.run(main)
