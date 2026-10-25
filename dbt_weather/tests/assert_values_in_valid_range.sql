-- Singular test: returns rows that violate sanity ranges. Test passes when 0 rows return.
select *
from {{ ref('fact_weather') }}
where humidity_pct not between 0 and 100
   or temperature_c not between -60 and 60
   or wind_speed_kmh < 0
   or precipitation_mm < 0
