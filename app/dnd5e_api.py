import requests
import json

BASE_URL = "https://www.dnd5eapi.co/api"

def _make_request(endpoint: str) -> dict:
    """
    Makes a request to the D&D 5e API.

    Args:
        endpoint: The API endpoint to request (e.g., '/spells/fireball').

    Returns:
        A dictionary containing the JSON response from the API.

    Raises:
        requests.exceptions.RequestException: If an error occurs while making the request.
        json.JSONDecodeError: If an error occurs while decoding the JSON response.
    """
    url = BASE_URL + endpoint
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for non-200 status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        # Handle request exceptions (e.g., network errors, timeouts)
        raise e
    except json.JSONDecodeError as e:
        # Handle JSON decoding errors
        raise e


def get_resources() -> dict:
    """
    Fetches the list of available resource categories from the D&D 5e API.

    Returns:
        A dictionary where keys are resource types (e.g., 'spells', 'monsters')
        and values are their corresponding API endpoints.

    Raises:
        requests.exceptions.RequestException: If an error occurs while making the request.
        json.JSONDecodeError: If an error occurs while decoding the JSON response.
    """
    return _make_request("/")


def get_resource_details(resource_type: str, resource_index: str) -> dict:
    """
    Fetches detailed information for a specific resource from the D&D 5e API.

    Args:
        resource_type: The type of resource (e.g., 'spells', 'monsters').
        resource_index: The index or name of the specific resource (e.g., 'fireball', 'goblin').

    Returns:
        A dictionary containing the detailed JSON data for the specified resource.

    Raises:
        requests.exceptions.RequestException: If an error occurs while making the request.
        json.JSONDecodeError: If an error occurs while decoding the JSON response.
    """
    endpoint = f"/{resource_type}/{resource_index}"
    return _make_request(endpoint)


def get_all_races() -> list:
    """
    Fetches the list of all races from the D&D 5e API.

    Returns:
        A list of race data obtained from the API.
        Each race object in the list is a dictionary with 'index', 'name', and 'url'.
        Returns an empty list if the 'results' key is not found in the API response.

    Raises:
        requests.exceptions.RequestException: If an error occurs while making the request.
        json.JSONDecodeError: If an error occurs while decoding the JSON response.
    """
    data = _make_request("/races")
    return data.get('results', [])
