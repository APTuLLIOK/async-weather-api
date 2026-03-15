import httpx
import asyncio
from typing import Any
from fastapi import status
from app.database import DB_NAME, save_forecast_to_db
from app.exceptions import ExternalError
import aiosqlite


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


async def fetch_current_weather(lat: float, lon: float) -> dict[str, float]:
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,wind_speed_10m,surface_pressure",
        "wind_speed_unit": "kmh"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(OPEN_METEO_URL, params=params)
            if response.status_code != status.HTTP_200_OK:
                raise ExternalError(msg=f"External API returned status {response.status_code}")
            data = response.json()
            if "error" in data:
                raise ExternalError(msg=f"External API error: '{data['reason']}'")
            return {
                "temperature": data["current"]["temperature_2m"],
                "wind_speed": data["current"]["wind_speed_10m"],
                "pressure": data["current"]["surface_pressure"]
            }
    except httpx.HTTPError as e:
        raise ExternalError(msg=f"Network connection failed: {str(e)}")

async def fetch_daily_forecast(lat: float, lon: float) -> list[dict[str, Any]]:
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,surface_pressure",
        "wind_speed_unit": "kmh", "forecast_days": 1, "timezone": "auto"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(OPEN_METEO_URL, params=params)
        data = response.json()
        hourly = data.get("hourly", {})
        
        return[{
            "time": hourly["time"][i], 
            "temperature": hourly["temperature_2m"][i],
            "wind_speed": hourly["wind_speed_10m"][i],
            "pressure": hourly["surface_pressure"][i],
            "humidity": hourly["relative_humidity_2m"][i],
            "precipitation": hourly["precipitation"][i]
        } for i in range(len(hourly.get("time",[])))]

async def update_city_weather(city_id: int, lat: float, lon: float):
    try:
        forecast_data = await fetch_daily_forecast(lat, lon)
        await save_forecast_to_db(city_id, forecast_data)
        print(f"Updated weather for city ID {city_id}")
    except Exception as e:
        print(f"Error updating city {city_id}: {e}")

async def weather_updater_loop():
    while True:
        async with aiosqlite.connect(DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT id, latitude, longitude FROM cities") as cursor:
                cities = await cursor.fetchall()
        for city in cities:
            await update_city_weather(city['id'], city['latitude'], city['longitude'])
        await asyncio.sleep(900)
        