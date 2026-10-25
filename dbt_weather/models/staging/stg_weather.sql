-- Parse the raw JSON and de-duplicate: the extractor may poll more often than
-- Open-Meteo updates, so keep one row per location + observation time.
with parsed as (

    select
        id                                                  as raw_id,
        location_name,
        fetched_at,
        (payload ->> 'latitude')::numeric                   as latitude,
        (payload ->> 'longitude')::numeric                  as longitude,
        (payload -> 'current' ->> 'time')::timestamp        as observed_at,
        (payload -> 'current' ->> 'temperature_2m')::numeric       as temperature_c,
        (payload -> 'current' ->> 'apparent_temperature')::numeric as feels_like_c,
        (payload -> 'current' ->> 'relative_humidity_2m')::numeric as humidity_pct,
        (payload -> 'current' ->> 'precipitation')::numeric        as precipitation_mm,
        (payload -> 'current' ->> 'wind_speed_10m')::numeric       as wind_speed_kmh,
        (payload -> 'current' ->> 'weather_code')::int             as weather_code
    from {{ source('raw', 'weather_raw') }}

),

ranked as (

    select
        *,
        row_number() over (
            partition by location_name, observed_at
            order by fetched_at desc
        ) as rn
    from parsed

)

select
    raw_id, location_name, fetched_at, latitude, longitude, observed_at,
    temperature_c, feels_like_c, humidity_pct, precipitation_mm,
    wind_speed_kmh, weather_code
from ranked
where rn = 1
