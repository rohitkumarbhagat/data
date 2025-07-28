import requests
import ssl
from urllib3.exceptions import InsecureRequestWarning


def download_with_fallback(url, verify_paths=None):
    if verify_paths is None:
        verify_paths = [
            True,  # System default
            "/usr/local/google/home/rohitrkumar/Documents/dc/github/rohitkumarbhagat/data/statvar_imports/google_sustainability_financial_incentives/custom_cacert.pem",
            "/etc/ssl/certs/ca-certificates.crt",
            # "/etc/pki/tls/certs/ca-bundle.crt"
        ]

    for verify in verify_paths:
        try:
            response = requests.head(url, verify=verify, timeout=30)
            return response
        except requests.exceptions.SSLError as e:
            print("error=" , e)
            continue
    return None
    # Last resort - disable verification with warning
    # requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    # return requests.get(url, verify=False, timeout=30)


print(
    download_with_fallback(
        "https://gaftp.epa.gov/air/nei/2020/data_summaries/2020neiMar_nonpoint.zip"
    ))
