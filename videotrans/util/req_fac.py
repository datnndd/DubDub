# Define a factory function returning a configured Session
import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry


def custom_session_factory():
    sess = requests.Session()
    # Configure retry strategy
    retries = Retry(
        total=3,  # Total retry count (changed to 3)
        connect=2,  # Connection retry count
        read=2,  # Read retry count
        backoff_factor=2,  # Retry backoff interval (seconds) to prevent burst requests
        status_forcelist=[500, 502, 503, 504]  # Retry only on these status codes
    )

    # Mount retry strategy onto http and https protocols
    adapter = HTTPAdapter(max_retries=retries)
    sess.mount('http://', adapter)
    sess.mount('https://', adapter)
    return sess
