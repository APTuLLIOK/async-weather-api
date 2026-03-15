import aiosqlite
from typing import List, Any
from app.models import UserRegister, CityRequest, CityResponse, WeatherInfo
from app.exceptions import Missing, Duplicate


DB_NAME = "weather.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                UNIQUE(user_id, name)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS forecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_id INTEGER NOT NULL,
                time TEXT NOT NULL,
                temperature REAL,
                wind_speed REAL,
                pressure REAL,
                humidity REAL,
                precipitation REAL,
                UNIQUE(city_id, time) ON CONFLICT REPLACE,
                FOREIGN KEY(city_id) REFERENCES cities(id)
            )
        """)
        await db.commit()

async def create_user_in_db(user: UserRegister) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        try: 
            cursor = await db.execute("INSERT INTO users (username) VALUES (?)", (user.username,))
            await db.commit()
            return cursor.lastrowid
        except aiosqlite.IntegrityError:
            raise Duplicate(msg=f"User '{user.username}' already exists")

async def add_city_to_db(city: CityRequest) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        async with db.execute("SELECT id FROM users WHERE id = ?", (city.user_id,)) as cursor:
            if not await cursor.fetchone():
                raise Missing(msg=f"User with ID {city.user_id} does not exist")
        try:
            cursor = await db.execute(
                "INSERT INTO cities (user_id, name, latitude, longitude) VALUES (?, ?, ?, ?)",
                (city.user_id, city.name, city.latitude, city.longitude)
            )
            await db.commit()
            return cursor.lastrowid
        except aiosqlite.IntegrityError:
            raise Duplicate(msg=f"City '{city.name}' already added for user with ID {city.user_id}")

async def get_cities_from_db(user_id: int) -> list[CityResponse]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row 
        async with db.execute("SELECT id FROM users WHERE id = ?", (user_id,)) as cursor:
            if not await cursor.fetchone():
                raise Missing(msg=f"User with ID {user_id} does not exist")
        
        async with db.execute("SELECT id, user_id, name, latitude, longitude FROM cities WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [CityResponse(**dict(row)) for row in rows]

async def save_forecast_to_db(city_id: int, forecast_data: list):
    values = [(
        city_id, item['time'], item['temperature'], item['wind_speed'],
        item.get('pressure'), item.get('humidity'), item.get('precipitation')
    ) for item in forecast_data]

    async with aiosqlite.connect(DB_NAME) as db:
        await db.executemany("""
            INSERT INTO forecasts (city_id, time, temperature, wind_speed, pressure, humidity, precipitation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, values)
        await db.commit()

async def get_forecast_from_db(city_id: int, time: str, requested_params: List[str] | None = None) -> WeatherInfo | dict[str, Any]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM forecasts WHERE city_id = ? AND time = ?", (city_id, time)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise Missing(msg=f"Forecast for city with ID {city_id} at {time} not found")
            
            if not requested_params:
                return WeatherInfo(**dict(row))
            
            return {param: row[param] for param in requested_params if param in row.keys()}

async def get_city_id_by_name_from_db(user_id: int, city_name: str) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM cities WHERE user_id = ? AND name = ?", (user_id, city_name)) as cursor:
            row = await cursor.fetchone()
            if row: return row[0]
            raise Missing(msg=f"City '{city_name}' not found for user with ID {user_id}")
        