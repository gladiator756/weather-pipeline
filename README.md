# 🌦️ Greece Weather Data Pipeline

An end-to-end, fully automated ELT pipeline that collects live weather data for three Greek
cities, models it into a star schema with dbt, tests it, and serves it on a public dashboard.
It runs entirely on free cloud services, with no server to maintain.

[![CI](https://github.com/gladiator756/weather-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/gladiator756/weather-pipeline/actions/workflows/ci.yml)
[![Weather pipeline](https://github.com/gladiator756/weather-pipeline/actions/workflows/pipeline.yml/badge.svg)](https://github.com/gladiator756/weather-pipeline/actions/workflows/pipeline.yml)

**[▶ Live dashboard](https://greece-weather.streamlit.app)** · Python · PostgreSQL · dbt · GitHub Actions · Streamlit

<!-- Add a screenshot once a few days of data have been collected:
![Dashboard screenshot](docs/dashboard.png)
-->

---

## Architecture

```mermaid
flowchart LR
    A[Open-Meteo API] -->|Python extractor| B[(raw.weather_raw<br/>JSONB)]
    B -->|dbt| C[stg_weather<br/>view]
    C -->|dbt| D[fact_weather]
    C -->|dbt| E[dim_location]
    C -->|dbt| F[dim_date]
    D & E & F --> G[Streamlit dashboard]

    subgraph Neon[PostgreSQL on Neon]
        B
        C
        D
        E
        F
    end

    H[GitHub Actions<br/>every ~30 min] -.runs.-> A
    H -.runs.-> C
```

Every ~30 minutes a GitHub Actions job:

1. **Extracts** current conditions for Athens, Thessaloniki and Ioannina from the
   [Open-Meteo API](https://open-meteo.com/) and loads the untouched JSON response into a raw table.
2. **Transforms** it with `dbt run`: JSON parsing, typing and de-duplication in staging, then a star schema.
3. **Tests** it with `dbt test`. If a test fails, the run turns red and the problem is visible straight away.
4. **Checks freshness** with `dbt source freshness`: a warning after 2 hours without new raw data,
   a failure after 6.

The Streamlit dashboard reads only from the modelled tables, and caches query results for 10 minutes.

## Data model

```mermaid
erDiagram
    fact_weather }o--|| dim_location : location_id
    fact_weather }o--|| dim_date : date_id

    fact_weather {
        text observation_id PK
        text location_id FK
        date date_id FK
        timestamp observed_at
        numeric temperature_c
        numeric feels_like_c
        numeric humidity_pct
        numeric precipitation_mm
        numeric wind_speed_kmh
        int weather_code
    }
    dim_location {
        text location_id PK
        text location_name
        numeric latitude
        numeric longitude
    }
    dim_date {
        date date_id PK
        int year
        int month
        int day
        int day_of_week
        text day_name
        bool is_weekend
    }
```

| Layer | Schema | Materialization | Purpose |
|---|---|---|---|
| Raw | `raw` | table | Exact API responses as JSONB, so the history can be reprocessed if the parsing logic changes |
| Staging | `public_staging` | view | Parse JSON, cast types, keep one row per city and observation time |
| Marts | `public_marts` | incremental (fact), table (dimensions) | Star schema used by the dashboard |

**Grain of `fact_weather`:** one row per city per observation time. Open-Meteo updates every
15 minutes and the job may fetch the same observation twice, so staging de-duplicates with
`row_number()` over `(location_name, observed_at)`.

**Incremental loading:** `fact_weather` is an incremental model. Each run only processes
observations from the last day before the newest one already in the table, and replaces rows
with the same `observation_id` (`delete+insert`). The table no longer has to be rebuilt as
history grows, and the one-day lookback picks up late re-fetches of recent observations.
The small dimensions are still rebuilt in full.

## Data quality

The tests run on every pipeline run:

- **Keys:** `unique` and `not_null` on every primary key.
- **Referential integrity:** `relationships` tests from the fact table to both dimensions.
- **Completeness:** `not_null` on temperature.
- **Plausibility:** a custom singular test fails if humidity is outside 0–100 %, temperature
  outside −60…60 °C, or wind and rain are negative.
- **Freshness:** `dbt source freshness` on the raw table, warning after 2 hours and failing after
  6. It runs even when an earlier step failed, so the run also reports how stale the data is.
- **No silent failures:** the extractor exits with an error if none of the cities could be fetched.

### Continuous integration

Every pull request (and every push to `main`) runs the [CI workflow](.github/workflows/ci.yml):

- **Lint:** `ruff check` on the Python code.
- **Pipeline test:** the whole pipeline runs against a throwaway PostgreSQL service container:
  extract → `dbt build` → extract again → `dbt build` → `dbt source freshness`. Running the build
  twice tests both the first full build and the incremental path of `fact_weather`, without
  touching the production database.

## Design decisions

| Choice | Why |
|---|---|
| **ELT with a raw JSONB layer** | Loading first and transforming in the warehouse keeps the original data. A modelling bug can be fixed and replayed without calling the API again. |
| **dbt** | SQL transformations under version control, with dependencies, tests and documentation in one place. |
| **Star schema** | A simple, standard shape for analytics: one fact table and small dimensions that any BI tool understands. |
| **Neon (serverless Postgres)** | Real PostgreSQL on a free tier that scales to zero between runs. |
| **GitHub Actions as scheduler** | No server or Airflow instance to run for a single small job. Credentials are stored as encrypted repository secrets. |
| **Streamlit Community Cloud** | A shareable public URL, deployed directly from this repo. |

## Lessons learned

- **Dependency drift breaks deployments.** The dashboard failed after deployment with
  `ModuleNotFoundError: psycopg`. SQLAlchemy 2.1 changed the default PostgreSQL driver for
  `postgresql://` URLs from `psycopg2` to `psycopg` (v3). The fix was to add the new driver.
  The diagnosis was helped by logging the full error to the app logs while showing visitors
  only a generic message, so connection details never reach the page.
- **Pooled versus direct connections.** dbt and the extractor use Neon's direct host instead of the
  pooler endpoint, which avoids issues with session-level features that poolers don't support.
- **Scheduled CI is best effort.** GitHub may delay or skip scheduled runs. The de-duplication
  and daily aggregates make the data tolerant of occasional gaps.

## Possible next steps

- Add more cities, or hourly forecasts next to observations.
- Send a notification (e.g. email or Slack) when the scheduled run fails.
- Publish the dbt documentation site (`dbt docs generate`) with GitHub Pages.

---

## Run it yourself

### Project layout

```
extractor/extract.py             Open-Meteo -> raw.weather_raw
dbt_weather/                     staging view, star schema and tests
streamlit_app.py                 dashboard
.github/workflows/pipeline.yml   scheduled extract + dbt run + dbt test + freshness
.github/workflows/ci.yml         lint + full pipeline test on a throwaway Postgres
docker-compose.yml               local Postgres + Metabase
requirements.txt                 dashboard dependencies
requirements-pipeline.txt        extractor + dbt dependencies
```

### Locally with Docker

```bash
docker compose up -d
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-pipeline.txt
python extractor/extract.py --once
cd dbt_weather && dbt run --profiles-dir . && dbt test --profiles-dir .
```

Metabase is then available on http://localhost:3000. To run the dashboard locally, copy
`.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, then run `pip install -r requirements.txt`
and `streamlit run streamlit_app.py`.

### In the cloud (free)

1. **Neon:** create a project and copy the direct connection details (connection pooling off).
2. **GitHub:** push this repo (public repos get free Actions minutes) and add the repository secrets
   `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB`.
3. **Run once:** Actions → *Weather pipeline* → *Run workflow*. After that it runs on its own.
4. **Streamlit Community Cloud:** create an app from this repo with `streamlit_app.py` and Python 3.12,
   and add this secret:
   ```toml
   [connections.weather_db]
   url = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
   ```

**Free-tier notes:** scheduled workflows pause after 60 days without repository activity, and
Streamlit apps sleep after about 12 hours without visitors (the first visitor wakes the app).
