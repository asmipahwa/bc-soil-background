"""Screen soil samples for background use with GeoPandas buffers.

A background sample must be natural soil, away from anything that could have added metals.
For every soil sample and every activity type in config/activity_pcoc.csv:

1. Buffer the sample point by (activity buffer distance + the sample's location uncertainty),
   in BC Albers metres.
2. Spatially join the buffers to that type's land-use features (OSM, MINFILE).
3. If a feature falls inside AND the activity's PCOCs include the metal, the sample is
   excluded for that metal. (A fuel station's PCOCs are hydrocarbons and lead, so it does not
   exclude a sample for As/Cu/Zn.)

Two non-spatial rules come from Protocol 4 v15 s.4.2.1: samples from fill are excluded
("samples must be collected from within native materials"), and samples from a site report
sit on that report's investigated site, whose own PCOCs include metals.

Output: one row per sample and metal (data/processed/screening.csv), and counts by
reason in docs/results/screening.md.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from bc_soil_background.extract.activities import load_activities, load_regional_districts
from bc_soil_background.paths import CONFIG, CRS_ALBERS, PROCESSED, RESULTS

METALS = ["As", "Cu", "Zn"]


def load_soil_samples() -> gpd.GeoDataFrame:
    s = pd.read_csv(PROCESSED / "samples.csv")
    s = s[s.sample_media == "soil"]
    gdf = gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s.x_albers, s.y_albers), crs=CRS_ALBERS)
    # GeoFile soil points were recorded with a handheld GPS (AR 29239 p.16; accuracy not stated): no margin added.
    gdf["location_uncertainty_m"] = gdf.location_uncertainty_m.fillna(0)
    return gdf


def assign_regions(samples: gpd.GeoDataFrame, districts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    joined = gpd.sjoin(samples, districts, how="left", predicate="within").drop(columns="index_right")
    joined = joined[~joined.index.duplicated()]
    # Every study-area sample is on Vancouver Island, Protocol 4 Region 1 (P4 v15 Figure 1).
    joined["p4_region"] = "Region 1 Vancouver Island"
    return joined


def spatial_hits(samples: gpd.GeoDataFrame, activities: gpd.GeoDataFrame, rules: pd.DataFrame) -> pd.DataFrame:
    """Return (sample_uid, activity_type, activity_id, distance_m) for every feature inside a buffer."""
    hits = []
    for rule in rules.itertuples():
        feats = activities[activities.activity_type == rule.activity_type]
        if feats.empty:
            continue
        buffers = samples[["sample_uid", "location_uncertainty_m", "geometry"]].copy()
        buffers["geometry"] = samples.geometry.buffer(rule.buffer_m + samples.location_uncertainty_m)
        j = gpd.sjoin(buffers, feats[["activity_id", "geometry"]], predicate="intersects")
        if j.empty:
            continue
        pts = samples.set_index("sample_uid").geometry
        geoms = feats.set_index("activity_id").geometry
        j["distance_m"] = [pts[u].distance(geoms[a]) for u, a in zip(j.sample_uid, j.activity_id, strict=True)]
        j["activity_type"] = rule.activity_type
        hits.append(j[["sample_uid", "activity_type", "activity_id", "distance_m"]])
    return pd.concat(hits, ignore_index=True) if hits else pd.DataFrame()


def screen() -> pd.DataFrame:
    rules = pd.read_csv(CONFIG / "activity_pcoc.csv")
    samples = assign_regions(load_soil_samples(), load_regional_districts())
    hits = spatial_hits(samples, load_activities(), rules[rules.activity_type != "report_site"])
    rule_by_type = rules.set_index("activity_type")

    rows = []
    for s in samples.itertuples():
        mine = hits[hits.sample_uid == s.sample_uid] if len(hits) else hits
        for metal in METALS:
            reasons, notes = [], []
            if s.source_type == "site_report":
                reasons.append("on investigated site with metal PCOCs (report)")
            if s.fill_or_native == "fill":
                reasons.append("fill, not native (P4 s.4.2.1a)")
            for atype, g in mine.groupby("activity_type") if len(mine) else []:
                closest = g.loc[g.distance_m.idxmin()]
                buf, unc = rule_by_type.loc[atype, "buffer_m"], s.location_uncertainty_m
                label = (
                    f"{atype} within {buf + unc:.0f} m "
                    f"(buffer {buf} m + location uncertainty {unc:.0f} m, nearest {closest.distance_m:.0f} m)"
                )
                if rule_by_type.loc[atype, metal] == "Y":
                    reasons.append(label)
                else:
                    notes.append(label + ": PCOCs exclude " + metal)
            rows.append(
                {
                    "sample_uid": s.sample_uid,
                    "source_id": s.source_id,
                    "p4_region": s.p4_region,
                    "regional_district": s.regional_district,
                    "analyte": metal,
                    "decision": "exclude" if reasons else "include",
                    "reasons": "; ".join(reasons),
                    "notes": "; ".join(notes),
                }
            )
    return pd.DataFrame(rows)


def _reason_key(reason: str) -> str:
    return reason.split(" within ")[0] if " within " in reason else reason


def write_summary(scr: pd.DataFrame) -> None:
    rules = pd.read_csv(CONFIG / "activity_pcoc.csv")
    lines = [
        "# Screening results: which soil samples can be used as background",
        "",
        "Generated by `src/bc_soil_background/analysis/screening.py`. Each soil sample is buffered in",
        "BC Albers (EPSG:3005) by the activity's buffer distance plus the sample's location uncertainty,",
        "and joined to land-use features with GeoPandas. A sample is excluded for a metal when a feature",
        "inside the buffer has that metal among its PCOCs (`config/activity_pcoc.csv`).",
        "",
        "## Decisions by source (sample counts; a sample is counted once per metal)",
        "",
    ]
    tab = scr.pivot_table(index="source_id", columns=["analyte", "decision"], values="sample_uid", aggfunc="count")
    tab = tab.fillna(0).astype(int)
    tab.columns = [f"{a} {d}" for a, d in tab.columns]
    lines += [tab.reset_index().to_markdown(index=False), ""]

    lines += ["## Exclusion reasons (sample-metal pairs; one pair can have several reasons)", ""]
    exploded = scr[scr.decision == "exclude"].assign(reason=lambda d: d.reasons.str.split("; ")).explode("reason")
    exploded["reason"] = exploded.reason.map(_reason_key)
    counts = exploded.groupby(["reason", "analyte"]).size().unstack(fill_value=0).reset_index()
    lines += [counts.to_markdown(index=False), ""]

    lines += ["## Kept per region", ""]
    kept = scr[scr.decision == "include"].groupby(["p4_region", "regional_district", "analyte"]).size()
    lines += [kept.unstack(fill_value=0).reset_index().to_markdown(index=False), ""]

    noted = scr[(scr.decision == "include") & (scr.notes != "")]
    lines += ["## Nearby features that did not exclude a kept sample", ""]
    if noted.empty:
        lines += [
            "None: no kept sample has a feature inside a buffer whose PCOCs leave that metal out",
            "(for example a fuel station, a pulp mill for As/Cu, or a natural mineral showing).",
            "",
        ]
    else:
        notes = noted.assign(n=noted.notes.str.split("; ")).explode("n")
        notes["n"] = notes.n.map(_reason_key)
        counts = notes.groupby(["n", "analyte"]).size().unstack(fill_value=0).reset_index()
        lines += [counts.to_markdown(index=False), ""]

    lines += ["## Rules used", "", rules.to_markdown(index=False), ""]
    lines += [
        "Buffer distances are project assumptions (no BC regulation sets a screening distance); they are",
        "stated here so they can be changed and re-run. Per-sample decisions are written to",
        "`data/processed/screening.csv` (git-ignored, rebuilt by `uv run bcsb`).",
        "",
    ]
    (RESULTS / "screening.md").write_text("\n".join(lines))


def main() -> None:
    scr = screen()
    scr.to_csv(PROCESSED / "screening.csv", index=False)
    write_summary(scr)
    print(scr.groupby(["source_id", "analyte", "decision"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
