from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, description="Username")


class UserRegister(UserBase):
    pass


class UserResponse(UserBase):
    id: int


class CityRequest(BaseModel):
    user_id: int = Field(..., description="ID of user that city is linked to")
    name: str = Field(..., min_length=1, description="City name")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")


class CityResponse(CityRequest):
    id: int


class WeatherInfo(BaseModel):
    temperature: float = Field(..., description="Temperature (C)")
    wind_speed: float = Field(..., description="Wind speed (kmh)")
    pressure: Optional[float] = Field(None, description="Atmospheric pressure (hPa)")
    humidity: Optional[float] = Field(None, description="Humidity (%)")
    precipitation: Optional[float] = Field(None, description="Precipitation (mm)")


class WeatherParam(str, Enum):
    temperature = "temperature"
    wind_speed = "wind_speed"
    pressure = "pressure"
    humidity = "humidity"
    precipitation = "precipitation"
