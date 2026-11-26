"""Place each report's site on the map (one point per site + an uncertainty radius).

Network lookups are cached in data/cache/ so the pipeline re-runs offline and only asks
OpenStreetMap services once. Nominatim's usage policy allows at most 1 request per second
and asks for an identifying User-Agent; we send a generic project name, no personal details.
"""

from __future__ import annotations

import json
import re
import time

import pandas as pd
import requests
import yaml
from shapely.geometry import LineString, MultiLineString
from shapely.ops import unary_union

from bc_soil_background.paths import BBOX, CONFIG, ROOT, STAGING

CACHE = ROOT / "data" / "cache"
USER_AGENT = "bc-soil-background/0.1 (independent student project)"


def _cached(name: str, fetch):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    data = fetch()
    path.write_text(json.dumps(data, indent=1))
    time.sleep(1.1)  # stay under 1 request/second
    return data


def overpass(query: str) -> dict:
    """POST an Overpass query, retrying politely: the public servers often answer 502/504 when busy."""
    for attempt in range(4):
        r = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            headers={"User-Agent": USER_AGENT},
            timeout=180,
        )
        if r.status_code not in (429, 502, 503, 504):
            r.raise_for_status()
            return r.json()
        time.sleep(10 * (attempt + 1))
    r.raise_for_status()
    return {}


def dms_to_decimal(text: str) -> float:
    d, m, s, hemi = re.fullmatch(r"\s*(\d+)\s+(\d+)\s+([\d.]+)\s*([NSEW])\s*", text).groups()
    value = int(d) + int(m) / 60 + float(s) / 3600
    return -value if hemi in "SW" else value


def nominatim(query: str) -> tuple[float, float]:
    def fetch():
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "ca"},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    key = "nominatim_" + re.sub(r"\W+", "_", query.lower()).strip("_")
    hits = _cached(key, fetch)
    if not hits:
        raise ValueError(f"Nominatim found nothing for {query!r}")
    return float(hits[0]["lat"]), float(hits[0]["lon"])


def road_intersection(roads: list[str]) -> tuple[float, float]:
    names = "|".join(re.escape(r) for r in roads)
    q = (
        f'[out:json][timeout:60];way["highway"]["name"~"^({names})$"]'
        f"({BBOX['south']},{BBOX['west']},{BBOX['north']},{BBOX['east']});out geom;"
    )

    key = "overpass_roads_" + re.sub(r"\W+", "_", "_".join(roads).lower())
    data = _cached(key, lambda: overpass(q))
    lines = {name: [] for name in roads}
    for el in data["elements"]:
        coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        if len(coords) > 1:
            lines[el["tags"]["name"]].append(LineString(coords))
    a, b = (unary_union(MultiLineString(lines[n])) for n in roads)
    pts = a.intersection(b)
    if pts.is_empty:
        raise ValueError(f"roads {roads} do not intersect in OSM data")
    c = pts.centroid
    return c.y, c.x


def locate_sites() -> pd.DataFrame:
    cfg = yaml.safe_load((CONFIG / "sites.yaml").read_text())["sites"]
    rows = []
    for report_id, s in cfg.items():
        if s["method"] == "report_coordinates":
            lat, lon = dms_to_decimal(s["lat_dms"]), dms_to_decimal(s["lon_dms"])
        elif s["method"] == "nominatim":
            lat, lon = nominatim(s["query"])
        elif s["method"] == "road_intersection":
            lat, lon = road_intersection(s["roads"])
        else:
            raise ValueError(f"unknown method {s['method']}")
        rows.append(
            {
                "report_id": report_id,
                "site_name": s["name"],
                "lat": lat,
                "lon": lon,
                "location_method": s["method"],
                "location_uncertainty_m": s["uncertainty_m"],
                "location_note": " ".join(s["note"].split()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    df = locate_sites()
    df.to_csv(STAGING / "report_sites.csv", index=False)
    print(df[["report_id", "lat", "lon", "location_method", "location_uncertainty_m"]].to_string(index=False))


if __name__ == "__main__":
    main()
