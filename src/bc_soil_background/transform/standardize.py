"""Combine report and geochemistry data into one clean schema.

Two output tables (the same ones loaded into PostGIS):

* samples: one row per physical sample: where it is (EPSG:3005), what medium it is,
  how it was located, depth, date, duplicate status, and sample-level data-quality flags.
* results: one row per sample x analyte, in mg/kg dry weight, with non-detects kept as
  non-detects (value is NULL, detection_limit is set).

Unit notes: mg/kg = µg/g = ppm for a dry-weight soil result (all are "parts per million
by mass"), so they convert 1:1. Percent becomes mg/kg x 10,000; ppb becomes mg/kg / 1,000.
Labs report soil metals on a dry-weight basis, and so does the RGS. The DQ summary
states this assumption instead of hiding it.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from bc_soil_background.paths import CONFIG, CRS_ALBERS, CRS_WGS84, PROCESSED, RESULTS, STAGING

TO_MG_KG = {"mg/kg": 1.0, "µg/g": 1.0, "μg/g": 1.0, "ug/g": 1.0, "ppm": 1.0, "%": 10_000.0, "ppb": 0.001}
NO_CONVERSION = {"pH", "pH Units"}
DATE_FORMATS = ["%d-%b-%Y", "%Y %m %d", "%d-%b-%y", "%Y-%m-%d", "%Y"]


def parse_date(text) -> pd.Timestamp | None:
    if pd.isna(text):
        return None
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(str(text).strip(), format=fmt)
        except ValueError:
            continue
    raise ValueError(f"unrecognised date {text!r}")


def _analyte_map() -> pd.DataFrame:
    m = pd.read_csv(CONFIG / "analytes.csv", keep_default_na=False)
    m["raw_name"] = m.raw_name.str.replace("\\n", "\n", regex=False)
    return m


def standardize_reports(rep: pd.DataFrame, sites: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    amap = _analyte_map().set_index("raw_name")
    unmapped = set(rep.analyte_raw) - set(amap.index)
    if unmapped:
        raise ValueError(f"analytes missing from config/analytes.csv: {unmapped}")
    rep = rep.merge(sites, on="report_id", how="left")
    rep["sample_uid"] = rep.report_id + ":" + rep.sample_id
    rep["analyte"] = rep.analyte_raw.map(amap.symbol)
    rep["analyte_kind"] = rep.analyte_raw.map(amap.kind)
    # Saturated-paste salts are a different test from total metals: give them their own name.
    satpaste = rep.section.fillna("").str.contains("Sat. Paste", regex=False)
    rep.loc[satpaste, "analyte"] = rep.loc[satpaste, "analyte"] + "_satpaste"
    rep.loc[satpaste, "analyte_kind"] = "salt"

    samples = rep.groupby("sample_uid").first().reset_index()
    samples = pd.DataFrame(
        {
            "sample_uid": samples.sample_uid,
            "source_id": samples.report_id,
            "source_type": "site_report",
            "sample_id": samples.sample_id,
            "location_id": samples.location_id,
            "site_name": samples.site_name,
            "lat": samples.lat,
            "lon": samples.lon,
            "location_method": samples.location_method,
            "location_uncertainty_m": samples.location_uncertainty_m,
            "sample_media": samples.sample_media,
            "media_detail": None,
            "fill_or_native": samples.fill_or_native.fillna("not stated").str.lower(),
            "horizon": None,
            "depth_top_m": samples.depth_top_m,
            "depth_bottom_m": samples.depth_bottom_m,
            "sample_date": samples.sample_date_raw.map(parse_date),
            "is_duplicate": samples.is_duplicate,
            "duplicate_of": np.where(
                samples.is_duplicate, samples.report_id + ":" + samples.duplicate_of.astype(str), None
            ),
            "size_fraction": "not stated (CSR labs normally analyse <2 mm)",
        }
    )
    results = pd.DataFrame(
        {
            "sample_uid": rep.sample_uid,
            "analyte": rep.analyte,
            "analyte_kind": rep.analyte_kind,
            "unit_raw": rep.unit_raw,
            "value_raw": rep.value_raw.astype(str),
            "value": rep.value,
            "non_detect": rep.non_detect.astype(bool),
            "detection_limit": rep.detection_limit,
            "method": "not stated in summary table",
            "source_page": rep.page,
        }
    )
    return samples, results


def standardize_geochem(geo: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    geo = geo.copy()
    geo["sample_uid"] = geo.source_id + ":" + geo.sample_id
    s = geo.groupby("sample_uid").first().reset_index()
    samples = pd.DataFrame(
        {
            "sample_uid": s.sample_uid,
            "source_id": s.source_id,
            "source_type": np.where(s.source_id == "RGS2020", "regional_survey", "assessment_report"),
            "sample_id": s.sample_id,
            "location_id": None,
            "site_name": s.source_reference,
            "lat": s.lat,
            "lon": s.lon,
            "location_method": "survey_coordinates",
            "location_uncertainty_m": np.nan,
            "sample_media": s.sample_media,
            "media_detail": s.media_detail,
            "fill_or_native": np.where(s.sample_media == "soil", "native", "not applicable"),
            "horizon": s.horizon,
            "depth_top_m": s.depth_top_m,
            "depth_bottom_m": s.depth_bottom_m,
            "sample_date": s.sample_date_raw.map(parse_date),
            "is_duplicate": False,
            "duplicate_of": None,
            "size_fraction": s.size_fraction,
        }
    )
    results = pd.DataFrame(
        {
            "sample_uid": geo.sample_uid,
            "analyte": geo.analyte,
            "analyte_kind": "metal",  # both geochem sources report only elements
            "unit_raw": geo.unit_raw,
            "value_raw": np.where(geo.non_detect, "<" + geo.detection_limit.astype(str), geo.value.astype(str)),
            "value": geo.value,
            "non_detect": geo.non_detect.astype(bool),
            "detection_limit": geo.detection_limit,
            "method": geo.method,
            "source_page": np.nan,
        }
    )
    return samples, results


def convert_units(results: pd.DataFrame) -> pd.DataFrame:
    r = results.copy()
    physical = r.analyte_kind.eq("physical") | r.unit_raw.isin(NO_CONVERSION)
    factor = r.unit_raw.map(TO_MG_KG)
    unknown = r[~physical & factor.isna()]
    if len(unknown):
        raise ValueError(f"no unit conversion for {unknown.unit_raw.unique()}")
    factor = factor.where(~physical, 1.0)
    r["unit"] = np.where(physical, r.unit_raw.replace({"pH Units": "pH"}), "mg/kg")
    r["value"] = r.value * factor
    r["detection_limit"] = r.detection_limit * factor
    r["unit_converted"] = ~physical & (factor != 1.0)
    return r


def add_flags(samples: pd.DataFrame, results: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Data-quality flags. Flags describe; they never delete. Screening decides later."""
    s = samples.copy()
    flags = []
    for _, row in s.iterrows():
        f = []
        if row.source_type == "site_report":
            f.append("location_approximate_to_site")
        if row.sample_media != "soil":
            f.append("media_not_soil")
        if row.fill_or_native == "fill":
            f.append("fill")
        if row.fill_or_native == "not stated":
            f.append("fill_or_native_unknown")
        if row.is_duplicate:
            f.append("field_or_lab_duplicate")
        if isinstance(row.size_fraction, str) and "180" in row.size_fraction:
            f.append("fine_fraction_lt180um")
        if row.source_type == "assessment_report":
            f.append("depth_approximate")
        flags.append(";".join(f))
    s["dq_flags"] = flags

    r = results.copy()
    rf = []
    for _, row in r.iterrows():
        f = []
        if row.non_detect:
            f.append("non_detect")
        if row.unit_converted:
            f.append("unit_converted")
        if isinstance(row.method, str) and "AAS" in row.method:
            f.append("method_aas_not_icp")
        rf.append(";".join(f))
    r["dq_flags"] = rf
    return s, r


def to_albers(samples: pd.DataFrame) -> gpd.GeoDataFrame:
    g = gpd.GeoDataFrame(samples, geometry=gpd.points_from_xy(samples.lon, samples.lat), crs=CRS_WGS84)
    g = g.to_crs(CRS_ALBERS)
    g["x_albers"], g["y_albers"] = g.geometry.x.round(1), g.geometry.y.round(1)
    return g


def find_exact_duplicates(results: pd.DataFrame) -> pd.DataFrame:
    """Same sample + analyte reported twice (e.g. a sample printed on two table pages)."""
    key = ["sample_uid", "analyte"]
    return results[results.duplicated(key, keep=False)].sort_values(key)


def write_dq_summary(samples: pd.DataFrame, results: pd.DataFrame, dupes: pd.DataFrame) -> None:
    focus = results[results.analyte.isin(["As", "Cu", "Zn"])].merge(
        samples[["sample_uid", "source_id", "sample_media"]], on="sample_uid"
    )
    by_src = (
        samples.groupby(["source_id", "sample_media"])
        .agg(samples=("sample_uid", "size"), duplicates=("is_duplicate", "sum"))
        .reset_index()
    )
    res_src = (
        results.merge(samples[["sample_uid", "source_id"]], on="sample_uid")
        .groupby("source_id")
        .agg(
            results=("analyte", "size"),
            analytes=("analyte", "nunique"),
            non_detects=("non_detect", "sum"),
            unit_converted=("unit_converted", "sum"),
        )
        .reset_index()
    )
    nd = (
        focus.groupby(["source_id", "analyte"])
        .agg(n=("non_detect", "size"), non_detect=("non_detect", "sum"), max_dl=("detection_limit", "max"))
        .reset_index()
    )
    nulls = samples[["lat", "lon", "sample_date", "depth_top_m", "fill_or_native"]].isna().sum()
    flag_counts = samples.dq_flags.str.split(";").explode().loc[lambda s: s != ""].value_counts()
    lines = [
        "# Data quality summary",
        "",
        "Generated by `src/bc_soil_background/transform/standardize.py`. Every number below is",
        "computed from `data/processed/` on each run; nothing here is typed by hand.",
        "",
        "## Rows by source",
        "",
        by_src.merge(res_src, on="source_id").to_markdown(index=False),
        "",
        "## As / Cu / Zn: non-detects by source",
        "",
        nd.to_markdown(index=False),
        "",
        "## Sample-level flags",
        "",
        flag_counts.rename_axis("flag").reset_index(name="samples").to_markdown(index=False),
        "",
        "## Nulls in sample fields",
        "",
        nulls.rename_axis("field").reset_index(name="null_count").to_markdown(index=False),
        "",
        f"## Same sample + analyte reported twice: {len(dupes)} rows",
        "",
        "## Conventions",
        "",
        "- Units: mg/kg = µg/g = ppm (dry weight); % × 10,000; ppb ÷ 1,000. Rows changed by",
        "  anything other than ×1 are flagged `unit_converted`.",
        "- Non-detects are stored as `non_detect = true` with `detection_limit` set and `value` empty.",
        "  How they are substituted (e.g. ½ DL) is decided in the statistics step, not here.",
        "- Field/lab duplicates are kept and flagged; the statistics step uses the parent sample only.",
        "- RGS2020 rows are **moss-mat stream sediment, not soil**. They are never mixed into soil statistics.",
        "- Report samples are placed at one point per site (see `config/sites.yaml`), not at each borehole.",
    ]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "dq_summary.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    rep = pd.read_csv(STAGING / "report_results.csv", dtype={"value_raw": str, "duplicate_of": str})
    geo = pd.read_csv(STAGING / "geochem_results.csv")
    sites = pd.read_csv(STAGING / "report_sites.csv")
    s1, r1 = standardize_reports(rep, sites)
    s2, r2 = standardize_geochem(geo)
    samples = pd.concat([s1, s2], ignore_index=True)
    results = convert_units(pd.concat([r1, r2], ignore_index=True))
    samples, results = add_flags(samples, results)
    dupes = find_exact_duplicates(results)
    gsamples = to_albers(samples)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    gsamples.drop(columns="geometry").to_csv(PROCESSED / "samples.csv", index=False)
    results.to_csv(PROCESSED / "results.csv", index=False)
    gsamples.to_file(PROCESSED / "samples.gpkg", layer="samples", driver="GPKG")
    write_dq_summary(samples, results, dupes)
    print(f"samples: {len(samples)}  results: {len(results)}  exact duplicate rows: {len(dupes)}")
    print(samples.groupby(["source_id", "sample_media"]).size().to_string())


if __name__ == "__main__":
    main()
