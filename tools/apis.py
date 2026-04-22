import os

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency fallback
    requests = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency fallback
    def load_dotenv():
        return None

from runtime.contracts import ToolResult

load_dotenv()


def address_to_geolocation(address_details):
    """
    Get geolocalization of requested address.

    Parameters:
        address_details (str): Address details of location in question.

    Example Parameters To Pass:
        Staszica 4/3, Krakow, Polska

    Returns:
        ToolResult:
            - data (dict): Contains keys for `longitude` and `latitude` when successful.
            - summary (str): Short explanation of what happened.
            - error (str | None): Failure reason if geolocation could not be resolved.
    """
    if requests is None:
        return ToolResult.failure(
            "requests package is required for geolocation lookups.",
            summary="Could not resolve the address because HTTP dependencies are missing.",
        )

    access_key = os.getenv("POSITIONSTACK_API_KEY")
    if not access_key:
        return ToolResult.failure(
            "Missing POSITIONSTACK_API_KEY in environment.",
            summary="Could not resolve the address because the geolocation API key is missing.",
        )

    url = "http://api.positionstack.com/v1/forward"
    params = {"access_key": access_key, "query": address_details}

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json().get("data", [])
        if not data:
            return ToolResult.failure(
                "No geolocation data found for the given address.",
                summary="The geolocation lookup returned no matches.",
            )

        location = {
            "latitude": data[0]["latitude"],
            "longitude": data[0]["longitude"],
        }
        return ToolResult.ok(
            data=location,
            summary=f"Resolved address '{address_details}' to coordinates.",
        )
    except (requests.RequestException, KeyError) as exc:
        return ToolResult.failure(
            f"Geolocation request failed: {exc}",
            summary="The geolocation request failed.",
        )


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
        ToolResult:
            - data (dict): Weather data together with descriptive `_info` fields for each metric.
            - summary (str): Short explanation of the request result.
            - error (str | None): Failure reason if the API call or parsing fails.
    """
    if requests is None:
        return ToolResult.failure(
            "requests package is required for weather lookups.",
            summary="Could not fetch weather because HTTP dependencies are missing.",
        )

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "is_day",
            "precipitation",
            "rain",
            "cloud_cover",
            "pressure_msl",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
        ],
        "timezone": "Europe/Berlin",
        "forecast_days": 1,
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        data = payload["current"]
        desc = payload["current_units"]
        desc["is_day"] = "1 for day, 0 for night"
        desc = {f"{key}_info": value for key, value in desc.items()}
        combined = {
            key: value
            for pair in zip(data.items(), desc.items())
            for key, value in [
                (pair[0][0], pair[0][1]),
                (f"{pair[0][0]}_info", pair[1][1]),
            ]
        }
        return ToolResult.ok(
            data=combined,
            summary=f"Retrieved weather forecast for lat={lat}, lon={lon}.",
        )
    except (requests.RequestException, KeyError) as exc:
        return ToolResult.failure(
            f"Weather request failed: {exc}",
            summary="The weather request failed.",
        )


TOOLS = {
    "address_to_geolocation": address_to_geolocation,
    "get_weather_forecast": get_weather_forecast,
}
