from square.client import Client
from config.settings.common import SQUARE_SETTINGS


def square_init():
    client = Client(
        square_version="2020-11-18",
        access_token=SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],
        environment=SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],
    )

    locations_api = client.locations
    result = locations_api.list_locations()
    return result
