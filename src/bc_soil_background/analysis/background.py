"""Estimate 95th-percentile background levels for As, Cu and Zn, per region, with SciPy.

Steps, following BC Protocol 4 v15 s.4.2.1 ("Calculation of Local Background Concentrations"):

1. Keep soil samples that passed screening for that metal (data/processed/screening.csv).
2. Duplicates: "the average concentration of the duplicates should be used ... and counted as
   one sample". A field/lab duplicate is averaged with its parent.
3. Non-detects: replaced by half the detection limit (DL/2) for the main estimate. A
   sensitivity check repeats everything with ND = 0 and ND = DL.
4. Outliers: "Outliers must be identified using statistical methods and removed". Values are
   log10-transformed (soil metals are right-skewed) and Tukey's IQR rule is applied:
   outside [Q1 - 1.5 IQR, Q3 + 1.5 IQR] on the log scale -> outlier (scipy.stats.iqr).
5. Summary statistics with scipy.stats: n, % non-detect, median, 95th percentile
   (scipy.stats.scoreatpercentile), a bootstrap 95% CI for the P95 (scipy.stats.bootstrap),
   and a Shapiro-Wilk test on the log values as a single-population check.

Regions: Protocol 4 Region 1 (Vancouver Island, the whole study area) and each BC regional
district inside it. RGS moss-mat sediment gets the same statistics as a separate,
labelled comparison ("sediment, not soil"); it is not screened and never mixed into soil.
"""

from __future__ import annotations

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from bc_soil_background.extract.activities import load_regional_districts
from bc_soil_background.paths import CRS_ALBERS, PROCESSED, RESULTS

METALS = {"As": "arsenic", "Cu": "copper", "Zn": "zinc"}
# Protocol 4 v15 Table 1, Region 1 Vancouver Island (µg/g = mg/kg), p.9 of the PDF.
# Arsenic is printed as "(4)" in parentheses; v15 has no footnote explaining parentheses, so it is
# shown as printed and not used as a number.
P4_REGION1 = {"As": "(4)", "Cu": 100.0, "Zn": 150.0}
ND_METHODS = {"DL/2": 0.5, "ND=0": 0.0, "ND=DL": 1.0}
SEDIMENT = "moss-mat sediment (sediment, not soil)"
SOIL_COLOR, SED_COLOR, INK, INK2 = "#257de0", "#f47230", "#191919", "#666666"


def load_values() -> pd.DataFrame:
    """One row per sample x metal, with region, media and screening decision attached."""
    samples = pd.read_csv(PROCESSED / "samples.csv")
    results = pd.read_csv(PROCESSED / "results.csv")
    results = results[results.analyte.isin(METALS)]
    df = results.merge(samples, on="sample_uid")
    scr = pd.read_csv(PROCESSED / "screening.csv")[["sample_uid", "analyte", "decision"]]
    df = df.merge(scr, on=["sample_uid", "analyte"], how="left")
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.x_albers, df.y_albers), crs=CRS_ALBERS)
    gdf = gpd.sjoin(gdf, load_regional_districts(), how="left", predicate="within").drop(columns="index_right")
    df = pd.DataFrame(gdf.drop(columns="geometry"))
    df = df[~df.duplicated(["sample_uid", "analyte"])]
    df["media"] = np.where(df.sample_media == "soil", "soil", SEDIMENT)
    soil_kept = (df.media == "soil") & (df.decision == "include")
    return df[soil_kept | (df.media == SEDIMENT)].copy()


def apply_nd(df: pd.DataFrame, factor: float) -> pd.Series:
    return df.value.where(~df.non_detect, df.detection_limit * factor)


def average_duplicates(df: pd.DataFrame, conc: pd.Series) -> pd.DataFrame:
    """Average each duplicate with its parent and count the pair as one sample (P4 s.4.2.1)."""
    parent = np.where(
        df.is_duplicate.fillna(False).astype(bool), df.source_id + ":" + df.duplicate_of.astype(str), df.sample_uid
    )
    g = df.assign(conc=conc.to_numpy(), parent=parent).groupby("parent")
    return pd.DataFrame({"conc": g.conc.mean(), "non_detect": g.non_detect.all(), "n_averaged": g.size()})


def iqr_outliers(conc: pd.Series) -> pd.Series:
    """Tukey's rule on log10 values: True where the value is an outlier.

    Zeros (only in the ND = 0 sensitivity run) can't be logged: the rule is fitted on the
    positive values and zeros are never flagged.
    """
    pos = conc[conc > 0]
    logv = np.log10(pos)
    q1, q3 = stats.scoreatpercentile(logv, [25, 75])
    spread = stats.iqr(logv)
    flagged = (logv < q1 - 1.5 * spread) | (logv > q3 + 1.5 * spread)
    return flagged.reindex(conc.index, fill_value=False)


def summarize(conc: pd.Series, nd: pd.Series) -> dict:
    v = conc.to_numpy()
    out = {
        "n": len(v),
        "pct_non_detect": 100 * nd.mean(),
        "median": stats.scoreatpercentile(v, 50),
        "p95": stats.scoreatpercentile(v, 95),
        "p95_ci_low": np.nan,
        "p95_ci_high": np.nan,
        "shapiro_p_log": np.nan,
    }
    if len(v) >= 10:
        ci = stats.bootstrap(
            (v,),
            lambda x, axis: np.percentile(x, 95, axis=axis),
            n_resamples=5000,
            method="percentile",
            random_state=np.random.default_rng(42),
        ).confidence_interval
        out["p95_ci_low"], out["p95_ci_high"] = ci.low, ci.high
        out["shapiro_p_log"] = stats.shapiro(np.log10(v[v > 0])).pvalue
    return out


def regions(df: pd.DataFrame):
    """Yield (region label, rows): Protocol 4 Region 1 (all), then each regional district."""
    yield "P4 Region 1 Vancouver Island (study area)", df
    yield from df.groupby("regional_district")


def estimate() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = load_values()
    rows, points = [], []
    for media, dm in df.groupby("media"):
        for metal in METALS:
            dmm = dm[dm.analyte == metal]
            for region, g in regions(dmm):
                for nd_method, factor in ND_METHODS.items():
                    s = average_duplicates(g, apply_nd(g, factor))
                    out = iqr_outliers(s.conc) if len(s) >= 4 else pd.Series(False, index=s.index)
                    kept = s[~out]
                    rows.append(
                        {
                            "analyte": metal,
                            "region": region,
                            "media": media,
                            "nd_method": nd_method,
                            "n_samples_in": len(s),
                            "n_outliers": int(out.sum()),
                            "outlier_values": ", ".join(f"{x:g}" for x in sorted(s.conc[out])),
                            **summarize(kept.conc, kept.non_detect),
                        }
                    )
                    if nd_method == "DL/2" and region.startswith("P4"):
                        points.append(s.assign(analyte=metal, media=media, outlier=out.to_numpy()))
    return pd.DataFrame(rows), pd.concat(points)


def plot(metal: str, pts: pd.DataFrame, est: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(7.5, 3.6), sharex=True, gridspec_kw={"hspace": 0.5})
    rng = np.random.default_rng(0)
    for ax, media, color in [(axes[0], "soil", SOIL_COLOR), (axes[1], SEDIMENT, SED_COLOR)]:
        p = pts[(pts.analyte == metal) & (pts.media == media)]
        e = est[
            (est.analyte == metal) & (est.media == media) & (est.nd_method == "DL/2") & est.region.str.startswith("P4")
        ].iloc[0]
        y = rng.uniform(-0.3, 0.3, len(p))
        ax.scatter(p.conc[~p.outlier], y[~p.outlier.to_numpy()], s=14, color=color, alpha=0.75, linewidths=0)
        ax.scatter(p.conc[p.outlier], y[p.outlier.to_numpy()], s=30, facecolors="none", edgecolors=INK2, linewidths=1.2)
        ax.axvline(e.p95, color=INK, lw=1.5)
        ax.text(e.p95, 0.62, f" P95 {e.p95:.3g}", color=INK, fontsize=8, va="bottom")
        if isinstance(P4_REGION1[metal], float):
            ax.axvline(P4_REGION1[metal], color=INK2, lw=1.2, ls="--")
            ax.text(P4_REGION1[metal], -0.62, f" P4 Region 1: {P4_REGION1[metal]:g}", color=INK2, fontsize=8, va="top")
        title = (
            "Soil kept after screening"
            if media == "soil"
            else "Moss-mat stream sediment (sediment, not soil; comparison)"
        )
        ax.set_title(
            f"{title}: n={int(e.n)}, {int(e.n_outliers)} IQR outliers (hollow)", fontsize=9, loc="left", color=INK
        )
        ax.set_yticks([])
        ax.set_ylim(-0.9, 0.9)
        ax.set_xscale("log")
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.tick_params(colors=INK2, labelsize=8)
    axes[1].set_xlabel(f"{METALS[metal]} (mg/kg, log scale)", fontsize=9, color=INK2)
    fig.suptitle(
        f"{METALS[metal].capitalize()}: P4 Region 1 Vancouver Island study area", fontsize=10, x=0.125, ha="left"
    )
    fig.savefig(RESULTS / f"background_{metal}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _fmt(x) -> str:
    return "" if pd.isna(x) else f"{x:.3g}"


def write_results(est: pd.DataFrame) -> None:
    main = est[est.nd_method == "DL/2"]
    lines = [
        "# Background estimates for arsenic, copper and zinc",
        "",
        "Generated by `src/bc_soil_background/analysis/background.py` (`uv run bcsb`). Units: mg/kg (= µg/g).",
        "Not for regulatory use: see the README's limitations.",
        "",
        "## Soil, after screening (main estimate, non-detects = DL/2)",
        "",
    ]

    def table(d: pd.DataFrame, with_p4: bool) -> str:
        t = pd.DataFrame(
            {
                "metal": d.analyte,
                "region": d.region,
                "n": d.n,
                "% non-detect": d.pct_non_detect.map(lambda x: f"{x:.0f}"),
                "median": d["median"].map(_fmt),
                "P95": d.p95.map(_fmt),
                "P95 95% CI (bootstrap)": [
                    f"{_fmt(a)}–{_fmt(b)}" if pd.notna(a) else "n<10"
                    for a, b in zip(d.p95_ci_low, d.p95_ci_high, strict=True)
                ],
                "IQR outliers removed": [
                    f"{n} ({v})" if n else "0" for n, v in zip(d.n_outliers, d.outlier_values, strict=True)
                ],
                "Shapiro p (log)": d.shapiro_p_log.map(_fmt),
            }
        )
        if with_p4:
            t["P4 Table 1 Region 1"] = d.analyte.map(
                lambda m: P4_REGION1[m] if isinstance(P4_REGION1[m], str) else f"{P4_REGION1[m]:g}"
            )
        return t.to_markdown(index=False)

    lines += [table(main[main.media == "soil"], True), ""]
    regions_with_soil = set(main[main.media == "soil"].region)
    lines += [
        "Regions are Protocol 4 Region 1 (Vancouver Island; the whole study area) and the BC regional",
        "districts inside it. "
        + (
            "Regional District of Nanaimo has no soil row because none of its soil samples passed screening "
            "(all came from investigated contaminated-site reports)."
            if "Regional District of Nanaimo" not in regions_with_soil
            else ""
        ),
        "",
        "## Sensitivity to the non-detect method (soil, P4 Region 1)",
        "",
    ]
    sens = est[(est.media == "soil") & est.region.str.startswith("P4")]
    lines += [
        sens.pivot_table(index="analyte", columns="nd_method", values="p95")
        .map(_fmt)
        .reset_index()
        .to_markdown(index=False),
        "",
        "## Comparison: moss-mat stream sediment (sediment, not soil; not screened)",
        "",
        table(main[main.media == SEDIMENT], False),
        "",
        "## Plots",
        "",
    ]
    lines += [f"![{METALS[m]}](background_{m}.png)" for m in METALS]
    lines += [
        "",
        "## Method",
        "",
        "1. Soil samples kept by `screening.py` for that metal (see [screening.md](screening.md)).",
        "2. Duplicates averaged with their parent and counted once (P4 v15 s.4.2.1).",
        "3. Non-detects = half the detection limit; ND = 0 and ND = DL shown above as a sensitivity check.",
        "4. log10 transform, then Tukey IQR rule (1.5 × IQR) with `scipy.stats.iqr` /",
        "   `scipy.stats.scoreatpercentile`; outliers removed (P4 v15 s.4.2.1).",
        "5. n, % non-detect, median and P95 with `scipy.stats.scoreatpercentile`; bootstrap CI with",
        "   `scipy.stats.bootstrap` (5,000 resamples, seed 42); Shapiro-Wilk on log values with",
        "   `scipy.stats.shapiro` (p < 0.05 suggests the data may not be one log-normal population).",
        "",
    ]
    (RESULTS / "RESULTS.md").write_text("\n".join(lines))


def main() -> None:
    est, pts = estimate()
    est.to_csv(RESULTS / "background_estimates.csv", index=False)
    for metal in METALS:
        plot(metal, pts, est)
    write_results(est)
    show = est[est.nd_method == "DL/2"][
        ["media", "analyte", "region", "n", "n_outliers", "pct_non_detect", "median", "p95"]
    ]
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()
