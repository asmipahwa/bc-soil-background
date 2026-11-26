"""Import BC open geochemistry for the study area.

Two sources, kept apart because they are different sample media:

* RGS 2020 (BC Geological Survey / GSC Regional Geochemical Survey). In this area every
  site is **moss-mat stream sediment**, not soil. It is used only as a labelled comparison.
* Assessment report-sourced surface sediment geochemistry (BCGS GeoFile 2026-02). In this
  area it holds 80 **soil** samples from Assessment Report 29239 (Maple Mountain, 2007).

Non-detects: both databases store "below detection limit" differently (RGS as a negative
number, -DL; GeoFile 2026-02 as text like "<2"). Both become non_detect=True plus a
detection_limit, the same shape as the report extractor's output.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd
import pyproj

from bc_soil_background.paths import BBOX, RAW, STAGING

RGS_FILE = RAW / "geochem" / "rgs2020_data.xlsx"
ARSSG_FILE = RAW / "geochem" / "arssg" / "arssg_data_release.gpkg"

# RGS 2020 has two aqua regia methods for As/Cu/Zn. ICP-MS (a later re-analysis) is used
# when present because its arsenic detection limit is far lower: in this area the
# AAS column has 47 of 264 arsenic values below detection, the ICP column has 0.
RGS_METHODS = {
    "As": [("As_ICP_PPM", "aqua regia ICP-MS"), ("As_AAS_PPM", "aqua regia hydride AAS")],
    "Cu": [("Cu_ICP_PPM", "aqua regia ICP-MS"), ("Cu_AAS_PPM", "aqua regia AAS")],
    "Zn": [("Zn_ICP_PPM", "aqua regia ICP-MS"), ("Zn_AAS_PPM", "aqua regia AAS")],
}


def in_bbox(lat: pd.Series, lon: pd.Series) -> pd.Series:
    return lat.between(BBOX["south"], BBOX["north"]) & lon.between(BBOX["west"], BBOX["east"])


def load_rgs_moss() -> pd.DataFrame:
    df = pd.read_excel(RGS_FILE, sheet_name="litho")
    df = df[in_bbox(df.LAT, df.LONG)]
    rows = []
    for _, s in df.iterrows():
        for analyte, options in RGS_METHODS.items():
            for col, method in options:
                v = s[col]
                if pd.isna(v):
                    continue  # fall back to the next method
                non_detect = v < 0  # RGS convention: below detection limit stored as -DL
                rows.append(
                    {
                        "source_id": "RGS2020",
                        "sample_id": s.MASTERID,
                        "source_reference": s.ORIGINAL_REP,
                        "sample_date_raw": str(s.YEAR),
                        "lat": s.LAT,
                        "lon": s.LONG,
                        "sample_media": "moss-mat sediment",
                        "media_detail": s.MAT,
                        "horizon": None,
                        "depth_top_m": None,
                        "depth_bottom_m": None,
                        "analyte": analyte,
                        "unit_raw": "ppm",
                        "value": None if non_detect else float(v),
                        "non_detect": bool(non_detect),
                        "detection_limit": abs(float(v)) if non_detect else None,
                        "method": method,
                        "size_fraction": "not recorded in RGS2020 file",
                    }
                )
                break
    return pd.DataFrame(rows)


def _to_wgs84(df: pd.DataFrame) -> pd.DataFrame:
    """Coordinates are stored in each report's original CRS (e.g. NAD27 UTM 10); convert per CRS."""
    out = []
    for epsg, g in df.groupby("epsg_srid"):
        tr = pyproj.Transformer.from_crs(int(epsg), 4326, always_xy=True)
        lon, lat = tr.transform(g.x_coord.to_numpy(), g.y_coord.to_numpy())
        out.append(g.assign(lon=lon, lat=lat))
    return pd.concat(out)


def load_arssg_soil() -> pd.DataFrame:
    con = sqlite3.connect(ARSSG_FILE)
    samples = pd.read_sql(
        """
        select s.sample_id, s.sample_name, s.station_name, s.sample_date, s.ar_number,
               s.x_coord, s.y_coord, s.epsg_srid, s.sample_depth, t.sample_type_name
        from sample s join code_sample_type t on t.sample_type_code = s.sample_type_code
        where t.sample_type_name = 'soil'
        """,
        con,
    )
    samples = _to_wgs84(samples)
    samples = samples[in_bbox(samples.lat, samples.lon)]
    ids = ",".join(str(i) for i in samples.sample_id)
    det = pd.read_sql(
        f"""
        select d.sample_id, a.analyte_abbr as analyte, d.abundance, d.mdl, u.unit_name,
               m.description as method, p.details as prep
        from determin d
        join code_analytes a on a.analyte_code = d.analyte_code
        join code_unit u on u.unit_code = d.unit_code
        left join code_method m on m.method_code = d.method_code
        left join prep pr on pr.cert_id = d.cert_id
        left join code_prep p on p.prep_method_code = pr.prep_method_code
        where d.sample_id in ({ids})
        """,
        con,
    )
    con.close()
    det = det.merge(samples, on="sample_id")
    text = det.abundance.astype(str).str.strip()
    det["non_detect"] = text.str.startswith("<")
    det["detection_limit"] = np.where(det.non_detect, pd.to_numeric(text.str.lstrip("<"), errors="coerce"), np.nan)
    det["value"] = np.where(det.non_detect, np.nan, pd.to_numeric(text, errors="coerce"))
    bad = det[~det.non_detect & det.value.isna()]
    if len(bad):
        raise ValueError(f"unparsed abundance values: {bad.abundance.unique()[:10]}")
    return pd.DataFrame(
        {
            "source_id": "ARSSG_GF2026-02",
            "sample_id": "AR" + det.ar_number.astype(str) + "-" + det.sample_name.astype(str),
            "source_reference": "Assessment Report " + det.ar_number.astype(str),
            "sample_date_raw": det.sample_date,
            "lat": det.lat,
            "lon": det.lon,
            "sample_media": "soil",
            "media_detail": "road-bank soil, glacial till",
            # AR 29239 p.16: "taken as deep as possible (C horizon) ... typically 1 meter".
            "horizon": np.where(det.ar_number == 29239, "C (per AR 29239 p.16)", None),
            "depth_top_m": np.where(det.ar_number == 29239, 1.0, np.nan),
            "depth_bottom_m": np.where(det.ar_number == 29239, 1.0, np.nan),
            "analyte": det.analyte,
            "unit_raw": det.unit_name,
            "value": det.value,
            "non_detect": det.non_detect,
            "detection_limit": det.detection_limit,
            "method": det.method,
            "size_fraction": det.prep,
        }
    )


def main() -> None:
    STAGING.mkdir(parents=True, exist_ok=True)
    rgs = load_rgs_moss()
    soil = load_arssg_soil()
    out = pd.concat([rgs, soil], ignore_index=True)
    out.to_csv(STAGING / "geochem_results.csv", index=False)
    for src, g in out.groupby("source_id"):
        print(f"{src}: {g.sample_id.nunique()} samples, {len(g)} results, media={sorted(g.sample_media.unique())}")


if __name__ == "__main__":
    main()
