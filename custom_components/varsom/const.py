"""Constants for the Varsom integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final
from zoneinfo import ZoneInfo

DOMAIN: Final = "varsom"

CONF_MUNICIPALITY_ID: Final = "municipality_id"
CONF_MUNICIPALITY_NAME: Final = "municipality_name"
CONF_COUNTY_NAME: Final = "county_name"
CONF_AVALANCHE_REGION_ID: Final = "avalanche_region_id"
CONF_AVALANCHE_REGION_NAME: Final = "avalanche_region_name"
CONF_WARNING_TYPES: Final = "warning_types"

TYPE_FLOOD: Final = "flood"
TYPE_LANDSLIDE: Final = "landslide"
TYPE_AVALANCHE: Final = "avalanche"
WARNING_TYPES: Final = (TYPE_FLOOD, TYPE_LANDSLIDE, TYPE_AVALANCHE)

# Minimum level for the "active warning" binary sensors.
# Flood and landslide: 1 green, 2 yellow, 3 orange, 4 red.
# Avalanche: 0 not assessed, 1 low, 2 moderate, 3 considerable, 4 high, 5 very high.
WARNING_THRESHOLDS: Final = {
    TYPE_FLOOD: 2,
    TYPE_LANDSLIDE: 2,
    TYPE_AVALANCHE: 3,
}

UPDATE_INTERVAL: Final = timedelta(minutes=30)

# NVE returns local Norwegian time without an offset.
NVE_TIMEZONE: Final = ZoneInfo("Europe/Oslo")

# NVE language keys.
LANG_NORWEGIAN: Final = 1
LANG_ENGLISH: Final = 2

ATTRIBUTION: Final = "Data fra Varsom.no / NVE, lisensiert under NLOD"

VARSOM_URLS: Final = {
    TYPE_FLOOD: "https://www.varsom.no/flom-og-jordskred/varsling/",
    TYPE_LANDSLIDE: "https://www.varsom.no/flom-og-jordskred/varsling/",
    TYPE_AVALANCHE: "https://www.varsom.no/snoskred/varsling/",
}
