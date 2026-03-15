import pytest
import pytest_asyncio
import os
import aiosqlite
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch


from app.main import app
from app.database import init_db
from app.exceptions import ExternalError


TEST_DB_NAME = "test_weather.db"


@pytest.fixture(scope="session", autouse=True)
def mock_settings():
    with patch("app.database.DB_NAME", TEST_DB_NAME), \
         patch("app.main.weather_updater_loop", return_value=None):
        yield

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)
    
    await init_db()
    
    yield
    
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_register_user(client):
    response = await client.post("/register", json={"username": "test_user"})
    assert response.status_code == 201
    assert response.json()["id"] == 1
    assert response.json()["username"] == "test_user"

@pytest.mark.asyncio
async def test_register_duplicate_user(client):
    await client.post("/register", json={"username": "test_user"})
    response = await client.post("/register", json={"username": "test_user"})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_current_weather_success(client):
    mock_data = {
        "temperature": 20.0,
        "wind_speed": 10.0,
        "pressure": 1013.0
    }
    with patch("app.main.fetch_current_weather", return_value=mock_data):
        response = await client.get("/weather/current", params={"latitude": 55.0, "longitude": 37.0})
        assert response.status_code == 200
        assert response.json() == mock_data

@pytest.mark.asyncio
async def test_get_current_weather_external_error(client):
    with patch("app.main.fetch_current_weather", side_effect=ExternalError("API Error")):
        response = await client.get("/weather/current", params={"latitude": 55.0, "longitude": 37.0})
        assert response.status_code == 502
        assert response.json()["detail"] == "API Error"

@pytest.mark.asyncio
async def test_add_city_success(client):
    await client.post("/register", json={"username": "test_user"})
    with patch("app.main.update_city_weather"):
        response = await client.post("/cities", json={
            "user_id": 1,
            "name": "Moscow",
            "latitude": 55.75,
            "longitude": 37.61
        })
        assert response.status_code == 201
        assert response.json()["id"] == 1

@pytest.mark.asyncio
async def test_add_duplicate_city(client):
    await client.post("/register", json={"username": "test_user"})
    city_data = {
        "user_id": 1,
        "name": "Moscow",
        "latitude": 55.75,
        "longitude": 37.61
    }
    with patch("app.main.update_city_weather"):
        await client.post("/cities", json=city_data)
        response = await client.post("/cities", json=city_data)
        assert response.status_code == 400
        assert "already added" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_cities_list(client):
    await client.post("/register", json={"username": "test_user"})
    with patch("app.main.update_city_weather"):
        await client.post("/cities", json={
            "user_id": 1, 
            "name": "London", 
            "latitude": 51.5, 
            "longitude": -0.12
        })
    response = await client.get("/cities", params={"user_id": 1})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "London"

@pytest.mark.asyncio
async def test_get_forecast_success(client):
    await client.post("/register", json={"username": "test_user"})
    with patch("app.main.update_city_weather"):
        await client.post("/cities", json={"user_id": 1, "name": "Berlin", "latitude": 52.5, "longitude": 13.4})
    
    test_time = "2025-10-10T12:00"
    
    async with aiosqlite.connect(TEST_DB_NAME) as db:
        await db.execute("""
            INSERT INTO forecasts (city_id, time, temperature, wind_speed, pressure, humidity, precipitation)
            VALUES (1, ?, 20.5, 15.0, 1013.0, 60.0, 0.0)
        """, (test_time,))
        await db.commit()
        
    response = await client.get("/weather/forecast", params={
        "user_id": 1,
        "city_name": "Berlin",
        "time": test_time
    })
    assert response.status_code == 200
    assert response.json()["temperature"] == 20.5

@pytest.mark.asyncio
async def test_get_forecast_city_not_found(client):
    await client.post("/register", json={"username": "test_user"})
    response = await client.get("/weather/forecast", params={
        "user_id": 1,
        "city_name": "UnknownCity",
        "time": "2025-10-10T12:00"
    })
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_forecast_time_not_found(client):
    await client.post("/register", json={"username": "test_user"})
    with patch("app.main.update_city_weather"):
        await client.post("/cities", json={"user_id": 1, "name": "Berlin", "latitude": 52.5, "longitude": 13.4})
    
    response = await client.get("/weather/forecast", params={
        "user_id": 1,
        "city_name": "Berlin",
        "time": "2099-01-01T00:00"
    })
    assert response.status_code == 404
    assert "Forecast" in response.json()["detail"]

@pytest.mark.asyncio
async def test_forecast_invalid_param(client):
    await client.post("/register", json={"username": "test_user"})
    with patch("app.main.update_city_weather"):
        await client.post("/cities", json={"user_id": 1, "name": "Berlin", "latitude": 52.5, "longitude": 13.4})
    
    response = await client.get("/weather/forecast", params={
        "user_id": 1,
        "city_name": "Berlin",
        "time": "2025-10-10T12:00",
        "params": ["invalid_param"]
    })
    assert response.status_code == 422
    