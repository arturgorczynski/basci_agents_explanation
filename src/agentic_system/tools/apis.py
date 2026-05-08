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


def search_internet(
    query: str,
    max_results: int = 3,
    search_depth: str = "advanced",
    include_answer: bool = True,
):
    """
    Search the web using Tavily and return concise links with descriptions.

    Parameters:
        query (str): Search query text.
        max_results (int): Number of results to return, capped at 10.
        search_depth (str): Tavily search depth ("basic" or "advanced").
        include_answer (bool): Whether Tavily should include its short answer.

    Returns:
        ToolResult:
            - data (dict): Search answer and normalized list of results.
            - summary (str): Short explanation of result count.
            - error (str | None): Failure reason when request/configuration fails.
    """
    if requests is None:
        return ToolResult.failure(
            "requests package is required for internet search.",
            summary="Could not run internet search because HTTP dependencies are missing.",
        )

    normalized_query = str(query).strip()
    if not normalized_query:
        return ToolResult.failure("Query cannot be empty.", summary="Could not run internet search.")

    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return ToolResult.failure(
            "Missing TAVILY_API_KEY in environment.",
            summary="Could not run internet search because API key is missing.",
        )

    limit = max(1, min(int(max_results), 10))
    payload = {
        "api_key": api_key,
        "query": normalized_query,
        "search_depth": search_depth,
        "max_results": limit,
        "include_answer": bool(include_answer),
        "include_raw_content": False,
    }

    try:
        response = requests.post("https://api.tavily.com/search", json=payload, timeout=20)
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        return ToolResult.failure(
            f"Tavily search failed: {exc}",
            summary="Could not run internet search.",
        )

    raw_results = body.get("results", [])
    if not isinstance(raw_results, list):
        raw_results = []

    results = []
    for item in raw_results[:limit]:
        description = str(item.get("content") or "").strip()
        if len(description) > 420:
            description = f"{description[:417]}..."
        results.append(
            {
                "title": item.get("title") or item.get("url"),
                "url": item.get("url"),
                "description": description,
            }
        )

    return ToolResult.ok(
        data={
            "query": normalized_query,
            "answer": body.get("answer"),
            "results": results,
        },
        summary=f"Tavily returned {len(results)} result(s).",
    )


TOOLS = {
    "address_to_geolocation": address_to_geolocation,
    "get_weather_forecast": get_weather_forecast,
    "search_internet": search_internet,
}
