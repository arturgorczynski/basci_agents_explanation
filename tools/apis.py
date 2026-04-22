import os

import requests
from dotenv import load_dotenv

load_dotenv()

def address_to_geolocation(address_details):
    """
    Get geolocalization of requested address.

    Parameters:
        address_details (str): Address details of location in question.

    Example Parameters To Pass:
        Staszica 4/3, Kraków, Polska

    Returns:
        dict: Dict that contains keys for longitude and latitude.
    """
    try:
        access_key = os.getenv("POSITIONSTACK_API_KEY")
        if not access_key:
            raise ValueError(
                "Missing POSITIONSTACK_API_KEY in environment. "
                "It is required for address_to_geolocation."
            )

        url = "http://api.positionstack.com/v1/forward"
        
        # Parameters including the API key and the query address
        params = {
            "access_key": access_key,
            "query": address_details
        }
        
        # Sending the GET request to the API
        response = requests.get(url, params=params)
        
        # Checking if the request was successful
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']:
                lat = data['data'][0]['latitude']
                lon = data['data'][0]['longitude']
                return {'latitude': lat, 'longitude': lon}
            else:
                raise ValueError("No data found for the given address.")
        else:
            # If the status code is not 200, raise an exception with a detailed error message
            response.raise_for_status()
    except requests.RequestException as e:
        # This captures exceptions raised by requests, including HTTPError, Timeout, etc.
        raise Exception(f"API request failed: {e}")
    except KeyError as e:
        # This captures errors like missing 'data' or 'latitude'/'longitude' keys in the response
        raise Exception(f"Data parsing error: Missing key {e}")



def get_weather_forecast(lat, lon):
    """
    Retrieves weather information for a given latitude and longitude.
    Use only if Latitude and Longitude are known.

    Parameters:
    lat (float): Latitude of the location.
    lon (float): Longitude of the location.

    Example Parameters To Pass:
        50.070640, 19.933120

    Returns:
    dict: Dictionary containing weather data and descriptive information for each metric.
    """
    try:
        # Define the API URL and parameters
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "is_day", "precipitation", "rain", "cloud_cover", "pressure_msl", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"],
            "timezone": "Europe/Berlin",
            "forecast_days": 1
        }
        
        # Send the request to the weather API
        response = requests.get(url, params=params)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Extract weather data and descriptions from the response
            data = response.json()['current']
            desc = response.json()['current_units']
            
            # Modify descriptions as needed
            desc['is_day'] = '1 for day, 0 for night'
            desc = {k + '_info': v for k, v in desc.items()}
            
            # Combine data with descriptions
            combined = {k: v for pair in zip(data.items(), desc.items()) for k, v in [(pair[0][0], pair[0][1]), (pair[0][0] + '_info', pair[1][1])]}
            
            return combined
        else:
            # Raise an error if the API call was unsuccessful
            response.raise_for_status()
    
    except requests.RequestException as e:
        raise Exception(f"API request failed: {e}")
    except KeyError as e:
        raise Exception(f"Data parsing error: Missing key {e}")
