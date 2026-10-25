"""
Streamlit dashboard for the weather pipeline.

Reads the dbt star schema (public_marts.fact_weather + dim_location) from
PostgreSQL. The connection string comes from Streamlit secrets:

    [connections.weather_db]
    url = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"

Run locally:   streamlit run streamlit_app.py
"""
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Greece Weather Dashboard", page_icon="🌦️", layout="wide")

QUERY = """
select
    f.observed_at,
    f.date_id,
    l.location_name,
    f.temperature_c,
    f.feels_like_c,
    f.humidity_pct,
    f.precipitation_mm,
    f.wind_speed_kmh
from public_marts.fact_weather f
join public_marts.dim_location l on l.location_id = f.location_id
order by f.observed_at
"""

NUMERIC_COLUMNS = [
    "temperature_c",
    "feels_like_c",
    "humidity_pct",
    "precipitation_mm",
    "wind_speed_kmh",
]


def load_data() -> pd.DataFrame:
    conn = st.connection("weather_db", type="sql")
    df = conn.query(QUERY, ttl=600)  # cached for 10 minutes
    df["observed_at"] = pd.to_datetime(df["observed_at"])
    df["date_id"] = pd.to_datetime(df["date_id"]).dt.date
    for col in NUMERIC_COLUMNS:  # Postgres numeric arrives as Decimal -> float
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


st.title("🌦️ Greece Weather Dashboard")
st.caption(
    "Open-Meteo API → PostgreSQL (Neon) → dbt star schema → Streamlit. "
    "Refreshed about every 30 minutes by a GitHub Actions job."
)

try:
    df = load_data()
except Exception as exc:  # don't print the message: it may contain connection details
    st.error(
        "Could not load data from the database. Check the connection secret and that "
        "the pipeline has run at least once."
    )
    st.caption(f"Error type: {type(exc).__name__}")
    st.stop()

if df.empty:
    st.info("The database is reachable but has no weather data yet. Run the pipeline first.")
    st.stop()

# ---------- Sidebar filters ----------
all_cities = sorted(df["location_name"].unique())
min_date, max_date = df["date_id"].min(), df["date_id"].max()

with st.sidebar:
    st.header("Filters")
    cities = st.multiselect("Cities", all_cities, default=all_cities)
    date_range = st.date_input(
        "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )

if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
else:  # user has picked only the first date so far
    start, end = min_date, max_date

filtered = df[
    df["location_name"].isin(cities) & (df["date_id"] >= start) & (df["date_id"] <= end)
]

if filtered.empty:
    st.warning("No data for the selected filters.")
    st.stop()

st.caption(f"Latest observation: {df['observed_at'].max():%d %b %Y, %H:%M} (local time of each city)")

# ---------- KPI row: latest reading per city ----------
columns = st.columns(len(cities))
for column, city in zip(columns, cities):
    city_df = filtered[filtered["location_name"] == city].sort_values("observed_at")
    if city_df.empty:
        continue
    last = city_df.iloc[-1]
    delta = None
    if len(city_df) > 1 and pd.notna(last["temperature_c"]):
        previous = city_df.iloc[-2]["temperature_c"]
        if pd.notna(previous):
            delta = f"{last['temperature_c'] - previous:+.1f} °C"
    column.metric(city, f"{last['temperature_c']:.1f} °C", delta)
    column.caption(
        f"Humidity {last['humidity_pct']:.0f}% · Wind {last['wind_speed_kmh']:.0f} km/h · "
        f"Rain {last['precipitation_mm']:.1f} mm"
    )

# ---------- Daily aggregates ----------
daily = (
    filtered.groupby(["date_id", "location_name"])
    .agg(
        avg_temp=("temperature_c", "mean"),
        max_temp=("temperature_c", "max"),
        min_temp=("temperature_c", "min"),
        rain=("precipitation_mm", "sum"),
        avg_wind=("wind_speed_kmh", "mean"),
    )
    .reset_index()
)
daily["date_id"] = pd.to_datetime(daily["date_id"])

tab_temp, tab_rain, tab_data = st.tabs(["🌡️ Temperature", "🌧️ Rain & wind", "📋 Data"])

with tab_temp:
    st.subheader("Average daily temperature (°C)")
    st.line_chart(daily.pivot(index="date_id", columns="location_name", values="avg_temp"))

    st.subheader("All readings (°C)")
    st.line_chart(
        filtered.pivot_table(
            index="observed_at", columns="location_name", values="temperature_c", aggfunc="mean"
        )
    )

with tab_rain:
    left, right = st.columns(2)
    with left:
        st.subheader("Total daily rainfall (mm)")
        st.bar_chart(daily.pivot(index="date_id", columns="location_name", values="rain"))
    with right:
        st.subheader("Average daily wind speed (km/h)")
        st.line_chart(daily.pivot(index="date_id", columns="location_name", values="avg_wind"))

with tab_data:
    st.dataframe(filtered.sort_values("observed_at", ascending=False), width="stretch")
    st.download_button(
        "Download as CSV",
        filtered.to_csv(index=False).encode("utf-8"),
        file_name="weather_readings.csv",
        mime="text/csv",
    )
