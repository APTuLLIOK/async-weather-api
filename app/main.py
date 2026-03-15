from fastapi import FastAPI, Query, BackgroundTasks, status
from fastapi.responses import JSONResponse
from typing import Optional, List, Any
from contextlib import asynccontextmanager

from app.models import UserRegister, UserResponse, CityRequest, CityResponse, WeatherInfo, WeatherParam
from app.exceptions import Missing, Duplicate, ExternalError
from app.database import (
    init_db, create_user_in_db, add_city_to_db, get_cities_from_db, 
    get_forecast_from_db, get_city_id_by_name_from_db
)
from app.services import fetch_current_weather, update_city_weather, weather_updater_loop
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    updater_task = asyncio.create_task(weather_updater_loop())
    yield
    updater_task.cancel()
    try:
        await updater_task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan, title="Weather API Service")


@app.exception_handler(Missing)
async def missing_handler(request, exc: Missing):
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": exc.msg})

@app.exception_handler(Duplicate)
async def duplicate_handler(request, exc: Duplicate):
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": exc.msg})

@app.exception_handler(ExternalError)
async def external_error_handler(request, exc: ExternalError):
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": exc.msg})

@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: UserRegister) -> UserResponse:
    user_id = await create_user_in_db(user)
    return UserResponse(id=user_id, username=user.username)

@app.get("/weather/current")
async def get_current_weather(latitude: float, longitude: float) -> dict[str, float]:
    return await fetch_current_weather(latitude, longitude)

@app.post("/cities", response_model=CityResponse, status_code=status.HTTP_201_CREATED)
async def add_city(city: CityRequest, background_tasks: BackgroundTasks) -> CityResponse:
    city_id = await add_city_to_db(city)
    background_tasks.add_task(update_city_weather, city_id, city.latitude, city.longitude)
    return CityResponse(id=city_id, **city.model_dump())

@app.get("/cities", response_model=List[CityResponse])
async def get_cities_list(user_id: int) -> List[CityResponse]:
    return await get_cities_from_db(user_id)

@app.get("/weather/forecast")
async def get_forecast(
    user_id: int, city_name: str, time: str, 
    params: Optional[List[WeatherParam]] = Query(None)
) -> WeatherInfo | dict[str, Any]:
    city_id = await get_city_id_by_name_from_db(user_id, city_name)
    params_str_list = [p.value for p in params] if params else None
    forecast = await get_forecast_from_db(city_id, time, params_str_list)
    if params:
        return JSONResponse(content=forecast)
    return forecast
