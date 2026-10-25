#!/usr/bin/env python3
"""
Extractor: fetches current weather from Open-Meteo (free, no API key)
and loads the RAW JSON response into Postgres (raw.weather_raw).

Usage:
    python extractor/extract.py --once                 # one run
    python extractor/extract.py --interval 900         # every 15 min, forever
"""
import argparse
import os
import time
import logging

import requests
import psycopg2
from psycopg2.extras import Json

API_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "precipitation,wind_speed_10m,weather_code"
)
LOCATIONS = {
    "Ioannina": (39.665, 20.853),
    "Athens": (37.983, 23.727),
    "Thessaloniki": (40.640, 22.944),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("extractor")

DDL = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.weather_raw (
    id            BIGSERIAL PRIMARY KEY,
    location_name TEXT        NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload       JSONB       NOT NULL
);
"""


def get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "weather"),
        password=os.getenv("POSTGRES_PASSWORD", "weather"),
        dbname=os.getenv("POSTGRES_DB", "weather"),
        sslmode=os.getenv("POSTGRES_SSLMODE", "prefer"),  # "require" for Neon
        connect_timeout=30,  # cloud databases can take a few seconds to wake up
    )


def fetch(lat: float, lon: float) -> dict:
    params = {"latitude": lat, "longitude": lon, "current": CURRENT_FIELDS, "timezone": "auto"}
    resp = requests.get(API_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def run_once(conn) -> None:
    with conn.cursor() as cur:
        for name, (lat, lon) in LOCATIONS.items():
            try:
                payload = fetch(lat, lon)
            except requests.RequestException as exc:
                log.error("Fetch failed for %s: %s", name, exc)
                continue
            cur.execute(
                "INSERT INTO raw.weather_raw (location_name, payload) VALUES (%s, %s)",
                (name, Json(payload)),
            )
            log.info("Loaded %s", name)
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="run a single time and exit")
    parser.add_argument("--interval", type=int, default=900, help="seconds between runs")
    args = parser.parse_args()

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()

    while True:
        run_once(conn)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
