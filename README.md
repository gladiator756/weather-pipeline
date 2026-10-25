# Weather Data Pipeline

Open-Meteo API → Python extractor → PostgreSQL → dbt star schema (with tests) → dashboard

Two ways to run it:

| | Database | Scheduler | Dashboard |
|---|---|---|---|
| **Local** | Postgres in Docker | a terminal window | Metabase on localhost:3000 |
| **Cloud (free)** | Neon | GitHub Actions | Streamlit Community Cloud (public URL) |

## Project layout

```
docker-compose.yml           local Postgres + Metabase
extractor/extract.py         fetch Open-Meteo -> raw JSON in raw.weather_raw
dbt_weather/                 staging view + star schema (fact_weather, dim_location, dim_date) + tests
streamlit_app.py             dashboard (reads public_marts.*)
.github/workflows/pipeline.yml   scheduled extract + dbt run + dbt test
requirements.txt             dashboard dependencies (Streamlit Cloud reads this)
requirements-pipeline.txt    extractor + dbt dependencies
```

---

## Local run

```bash
docker compose up -d
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-pipeline.txt
python extractor/extract.py --once
cd dbt_weather && dbt run --profiles-dir . && dbt test --profiles-dir .
```

If port 5432 is taken by another Postgres, change `"5432:5432"` to `"5433:5432"` in
`docker-compose.yml` and set `POSTGRES_HOST=127.0.0.1` and `POSTGRES_PORT=5433` in your terminal.

---

## Free cloud deployment (no server, no cost)

### 1. Create the database on Neon
1. Sign up at https://neon.com (no credit card) and create a project. Pick a nearby region (e.g. Frankfurt).
2. Click **Connect**, turn **connection pooling off** to get the direct host, and note the
   host, user, password and database name.

### 2. Put the project on a PUBLIC GitHub repository
Public repos get unlimited free Actions minutes, and Streamlit Community Cloud deploys from GitHub.
Never commit passwords: `.env` and `.streamlit/secrets.toml` are in `.gitignore`.

```bash
git init
git add .
git commit -m "Weather pipeline"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

### 3. Add the database credentials as GitHub secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**. Create four:

| Secret name | Value |
|---|---|
| `POSTGRES_HOST` | Neon host, e.g. `ep-xxxx.eu-central-1.aws.neon.tech` |
| `POSTGRES_USER` | Neon user |
| `POSTGRES_PASSWORD` | Neon password |
| `POSTGRES_DB` | Neon database name (usually `neondb`) |

### 4. Run the pipeline once by hand
Repo → **Actions → Weather pipeline → Run workflow**. When it turns green, the raw table,
the dbt models and the dbt tests have all run in the cloud. After that it runs by itself
twice an hour.

### 5. Deploy the dashboard on Streamlit Community Cloud
1. Go to https://share.streamlit.io and sign in with GitHub.
2. **Create app** → pick your repo, branch `main`, main file path `streamlit_app.py`.
3. Open **Advanced settings**: choose Python 3.12 and paste into **Secrets**:
   ```toml
   [connections.weather_db]
   url = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
   ```
   (fill in the Neon values; keep only `sslmode=require` in the query string).
4. Click **Deploy**. You get a public `https://<name>.streamlit.app` URL to share.

### Things to know
- **Scheduling is best effort.** GitHub may delay scheduled runs by several minutes or more, so
  expect occasional gaps. Daily trends are not affected.
- **Scheduled workflows pause after 60 days without repository activity.** Push any small commit
  every month or two, or press *Run workflow* again.
- **Streamlit apps sleep after about 12 hours without visitors.** The first visitor sees a
  "wake up" button; the data is unaffected.
- **Neon free plan:** 0.5 GB storage and 100 compute-hours per month. This pipeline stores
  a few MB per month and uses a small fraction of the compute.
- Check each provider's current free-tier terms before relying on them.
