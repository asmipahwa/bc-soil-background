"""Fetch the land-use layers used to screen samples, and the regional district boundaries.

* OpenStreetMap (Overpass, ODbL): rail, industrial land, quarries, landfills, fuel stations, works.
* MINFILE mineral occurrences (BC Geological Survey WFS): past/present mines and natural showings.
* Regional districts (BC Administrative Boundaries WFS, OGL-BC): used to group results per region.

Raw responses are saved under data/raw/ (git-ignored) and reused on later runs.
Each feature gets an `activity_type` that config/activity_pcoc.csv maps to its PCOCs.
"""

from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, Point, Polygon

from bc_soil_background.extract.locations import USER_AGENT, overpass
from bc_soil_background.paths import BBOX, CRS_ALBERS, CRS_WGS84, RAW

OSM_FILE = RAW / "activities" / "osm_activities.json"
MINFILE_FILE = RAW / "activities" / "minfile_region_2026-11-26.json"
RD_FILE = RAW / "boundaries" / "regional_districts.json"

WFS = "https://openmaps.gov.bc.ca/geo/pub/wfs"
_BB = f"{BBOX['south']},{BBOX['west']},{BBOX['north']},{BBOX['east']}"
OSM_QUERY = (
    "[out:json][timeout:180];("
    f'nwr["railway"="rail"]({_BB});'
    f'nwr["landuse"~"^(industrial|quarry|landfill|railway)$"]({_BB});'
    f'nwr["amenity"="fuel"]({_BB});'
    f'nwr["man_made"="works"]({_BB});'
    f'nwr["industrial"]({_BB});'
    ");out geom;"
)

# MINFILE status -> activity. Mines are a land use; showings/prospects are natural mineralization.
MINE_STATUS = {"Past Producer", "Producer", "Developed Prospect"}


def _fetch_json(path, fetch) -> dict:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fetch()))
    return json.loads(path.read_text())


def _wfs(type_name: str, extra: dict | None = None) -> dict:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": type_name,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "bbox": f"{_BB},urn:ogc:def:crs:EPSG::4326",
        "count": 2000,
    }
    r = requests.get(WFS, params={**params, **(extra or {})}, headers={"User-Agent": USER_AGENT}, timeout=120)
    r.raise_for_status()
    return r.json()


def classify_osm(tags: dict) -> str | None:
    """Most specific tag wins: e.g. landuse=industrial + industrial=sawmill -> sawmill."""
    ind = tags.get("industrial", "")
    if ind in ("sawmill", "lumber_yard", "forestry"):
        return "sawmill"
    if ind in ("pulp_mill", "paper"):
        return "pulp_mill"
    if ind in ("scrap_yard", "auto_wrecker"):
        return "salvage"
    if tags.get("railway") == "rail" or tags.get("landuse") == "railway":
        return "railway"
    if tags.get("landuse") == "landfill":
        return "landfill"
    if tags.get("landuse") == "quarry":
        return "quarry"
    if tags.get("amenity") == "fuel":
        return "fuel_station"
    if tags.get("landuse") == "industrial" or tags.get("man_made") == "works" or ind:
        return "industrial_other"
    return None


def _osm_geometry(el: dict):
    if el["type"] == "node":
        return Point(el["lon"], el["lat"])
    if el["type"] == "way":
        pts = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        if len(pts) >= 4 and pts[0] == pts[-1]:
            return Polygon(pts)
        return LineString(pts) if len(pts) > 1 else None
    # relation (multipolygon): use its outer ways as lines; buffers make this equivalent for screening
    lines = [
        LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
        for m in el.get("members", [])
        if m.get("geometry") and len(m["geometry"]) > 1
    ]
    return gpd.GeoSeries(lines).union_all() if lines else None


def load_osm() -> gpd.GeoDataFrame:
    data = _fetch_json(OSM_FILE, lambda: overpass(OSM_QUERY))
    rows = []
    for el in data["elements"]:
        tags = el.get("tags", {})
        kind = classify_osm(tags)
        geom = _osm_geometry(el)
        if kind and geom is not None:
            rows.append(
                {
                    "activity_id": f"osm:{el['type']}/{el['id']}",
                    "activity_type": kind,
                    "name": tags.get("name", ""),
                    "source": "OpenStreetMap",
                    "geometry": geom,
                }
            )
    return gpd.GeoDataFrame(rows, crs=CRS_WGS84)


def load_minfile() -> gpd.GeoDataFrame:
    data = _fetch_json(MINFILE_FILE, lambda: _wfs("WHSE_MINERAL_TENURE.MINFIL_MINERAL_FILE"))
    rows = []
    for f in data["features"]:
        p = f["properties"]
        status = (p["STATUS_DESCRIPTION"] or "").strip()
        commodities = [(p[f"COMMODITY_DESCRIPTION{i}"] or "").strip() for i in range(1, 9)]
        rows.append(
            {
                "activity_id": f"minfile:{p['MINFILE_NUMBER'].replace(' ', '')}",
                "activity_type": "mine" if status in MINE_STATUS else "mineral_occurrence",
                "name": f"{(p['MINFILE_NAME1'] or '').strip()} ({status}; {', '.join(c for c in commodities if c)})",
                "source": "MINFILE",
                "geometry": Point(p["LONGITUDE_DECIMAL"], p["LATITUDE_DECIMAL"]),
            }
        )
    return gpd.GeoDataFrame(rows, crs=CRS_WGS84)


def load_activities() -> gpd.GeoDataFrame:
    gdf = pd.concat([load_osm(), load_minfile()], ignore_index=True)
    return gpd.GeoDataFrame(gdf, crs=CRS_WGS84).to_crs(CRS_ALBERS)


def load_regional_districts() -> gpd.GeoDataFrame:
    data = _fetch_json(RD_FILE, lambda: _wfs("WHSE_LEGAL_ADMIN_BOUNDARIES.ABMS_REGIONAL_DISTRICTS_SP"))
    gdf = gpd.GeoDataFrame.from_features(data["features"], crs=CRS_WGS84)
    return (
        gdf[["ADMIN_AREA_NAME", "geometry"]].rename(columns={"ADMIN_AREA_NAME": "regional_district"}).to_crs(CRS_ALBERS)
    )


def main() -> None:
    acts = load_activities()
    print(acts.groupby(["source", "activity_type"]).size().to_string())
    rd = load_regional_districts()
    print("regional districts:", sorted(rd.regional_district))


if __name__ == "__main__":
    main()
