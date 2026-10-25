select distinct
    observed_at::date                          as date_id,
    extract(year  from observed_at)::int      as year,
    extract(month from observed_at)::int      as month,
    extract(day   from observed_at)::int      as day,
    extract(isodow from observed_at)::int     as day_of_week,
    to_char(observed_at, 'FMDay')             as day_name,
    extract(isodow from observed_at) in (6, 7) as is_weekend
from {{ ref('stg_weather') }}
