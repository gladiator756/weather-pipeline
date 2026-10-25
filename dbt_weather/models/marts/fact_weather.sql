-- Incremental: each run only processes recent observations instead of rebuilding
-- the whole table. The 1-day lookback re-processes recent rows so a late re-fetch
-- of an observation replaces the earlier version (matched on observation_id).
{{
    config(
        materialized='incremental',
        unique_key='observation_id',
        incremental_strategy='delete+insert',
        on_schema_change='append_new_columns'
    )
}}

select
    md5(location_name || '|' || observed_at::text) as observation_id,
    md5(location_name)                             as location_id,
    observed_at::date                              as date_id,
    observed_at,
    temperature_c,
    feels_like_c,
    humidity_pct,
    precipitation_mm,
    wind_speed_kmh,
    weather_code
from {{ ref('stg_weather') }}

{% if is_incremental() %}
where observed_at >= (select max(observed_at) - interval '1 day' from {{ this }})
{% endif %}
