select distinct
    md5(location_name)  as location_id,
    location_name,
    latitude,
    longitude
from {{ ref('stg_weather') }}
