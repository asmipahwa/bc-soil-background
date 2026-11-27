"""Unit tests for screening and statistics, on small made-up inputs (not project data)."""

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

from bc_soil_background.analysis.background import average_duplicates, iqr_outliers, summarize
from bc_soil_background.analysis.screening import spatial_hits
from bc_soil_background.extract.activities import classify_osm


def test_classify_osm_most_specific_tag_wins():
    assert classify_osm({"landuse": "industrial", "industrial": "sawmill"}) == "sawmill"
    assert classify_osm({"railway": "rail"}) == "railway"
    assert classify_osm({"amenity": "fuel"}) == "fuel_station"
    assert classify_osm({"landuse": "industrial"}) == "industrial_other"
    assert classify_osm({"shop": "bakery"}) is None


def test_buffer_includes_location_uncertainty():
    samples = gpd.GeoDataFrame(
        {"sample_uid": ["near", "far"], "location_uncertainty_m": [0.0, 0.0]},
        geometry=[Point(0, 40), Point(0, 200)],
        crs="EPSG:3005",
    )
    rail = gpd.GeoDataFrame(
        {"activity_id": ["r1"], "activity_type": ["railway"]},
        geometry=[LineString([(-100, 0), (100, 0)])],
        crs="EPSG:3005",
    )
    rules = pd.DataFrame({"activity_type": ["railway"], "buffer_m": [50]})
    hits = spatial_hits(samples, rail, rules)
    assert list(hits.sample_uid) == ["near"]
    assert hits.distance_m.iloc[0] == 40
    samples["location_uncertainty_m"] = [0.0, 160.0]  # 50 m buffer + 160 m uncertainty reaches 200 m
    assert set(spatial_hits(samples, rail, rules).sample_uid) == {"near", "far"}


def test_iqr_outlier_on_log_scale():
    values = pd.Series([10, 11, 12, 13, 12, 11, 10, 500.0])
    flagged = iqr_outliers(values)
    assert flagged.tolist() == [False] * 7 + [True]


def test_duplicates_are_averaged_and_counted_once():
    df = pd.DataFrame(
        {
            "sample_uid": ["S:A", "S:DUP"],
            "source_id": ["S", "S"],
            "is_duplicate": [False, True],
            "duplicate_of": [None, "A"],
            "non_detect": [False, False],
        }
    )
    out = average_duplicates(df, pd.Series([10.0, 20.0]))
    assert len(out) == 1
    assert out.conc.iloc[0] == 15.0


def test_p95_and_nondetect_share():
    conc = pd.Series(np.arange(1, 101, dtype=float))
    nd = pd.Series([True] * 10 + [False] * 90)
    s = summarize(conc, nd)
    assert s["n"] == 100 and s["pct_non_detect"] == 10
    assert abs(s["p95"] - 95.05) < 1e-9
