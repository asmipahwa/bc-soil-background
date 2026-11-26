"""One place for file locations and the study area, so every step agrees on them."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
RAW = ROOT / "data" / "raw"
STAGING = ROOT / "data" / "staging"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "docs" / "results"

# Nanaimo–Cowichan study area (WGS84 lon/lat): south, west, north, east.
BBOX = {"south": 48.6, "west": -124.3, "north": 49.3, "east": -123.6}

# BC Albers: the province's standard equal-area projection, in metres.
# Buffers are only meaningful in a metric CRS, so all geometry work happens here.
CRS_ALBERS = "EPSG:3005"
CRS_WGS84 = "EPSG:4326"
