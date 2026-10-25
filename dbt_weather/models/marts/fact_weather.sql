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
