"""Pull soil metals results tables out of public site investigation report PDFs.

Every consultant formats tables differently, so each report gets a small entry in
config/reports.yaml (file, pages, which header labels to read). The parsing rules
below are shared by all reports:

* pdfplumber's default "lines" strategy finds the table from its drawn cell borders.
* Header rows (sample ID, depth, date...) are found by their label text, not by
  fixed row numbers, because the label column moves between reports.
* pH-dependent standards make one analyte span several rows; the sample values
  are spread across those rows, so the block is merged back into one value per sample.
* "<0.1" means "not detected at a detection limit of 0.1": it is kept as a
  non-detect with its detection limit, never turned into a number silently.

Output is a long table: one row per sample x analyte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pdfplumber
import yaml

from bc_soil_background.paths import CONFIG, RAW, STAGING

NOT_REPORTED = {"", "-", "*", "n/a", "na", "nd"}
HEADER_WORDS = {"parameter", "parameters", "analyte"}
KNOWN_UNITS = re.compile(r"mg/kg|µg/g|μg/g|ug/g|%|pH|pH Units")


@dataclass
class ReportConfig:
    report_id: str
    file: str
    pages: list[int]
    sample_id_pattern: str
    header_labels: dict[str, str] = field(default_factory=dict)
    combined_header: list[str] | None = None
    combined_header_row: int | None = None
    location_row: int | None = None
    default_unit: str | None = None
    duplicates: dict[str, str] = field(default_factory=dict)
    # Text in a sample's date cell that marks it as a duplicate of the sample to its left.
    duplicate_marker: str | None = None
    # Header text of the QA/QC "RPD %" columns. Each RPD column compares one duplicate
    # pair, so the number of RPD columns must equal the number of duplicates found.
    rpd_label: str | None = None
    sample_media: str = "soil"

    @classmethod
    def load_all(cls, path: Path = CONFIG / "reports.yaml") -> list[ReportConfig]:
        raw = yaml.safe_load(path.read_text())
        return [
            cls(report_id=k, **{f: v for f, v in d.items() if f in cls.__dataclass_fields__})
            for k, d in raw["reports"].items()
        ]


def parse_value(cell: str | None) -> tuple[float | None, bool, float | None] | None:
    """Turn a table cell into (value, is_non_detect, detection_limit).

    Returns None for cells that hold no result ("-", "*", blank).
    Raises ValueError for anything else we don't understand, so odd cells
    get looked at instead of being dropped quietly.
    """
    if cell is None:
        return None
    text = cell.strip().replace(",", "").replace(" ", "")
    if text.lower() in NOT_REPORTED:
        return None
    if text.startswith("<"):
        dl = float(text[1:])
        return None, True, dl
    return float(text), False, None


def parse_depth(text: str | None) -> tuple[float | None, float | None]:
    """'0.5 - 0.9' -> (0.5, 0.9); '1.2' -> (1.2, 1.2)."""
    if not text:
        return None, None
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)]
    if not nums:
        return None, None
    return nums[0], nums[-1]


def _clean(cell: str | None) -> str:
    return (cell or "").strip()


def _find_label_row(table: list[list], label: str) -> tuple[int, int] | None:
    """Locate a header label (e.g. 'Field ID') anywhere in the first rows."""
    for r, row in enumerate(table[:12]):
        for c, cell in enumerate(row):
            if _clean(cell).lower() == label.lower():
                return r, c
    return None


def _forward_fill(row: list, start: int) -> list:
    """Merged header cells (e.g. one borehole over 3 samples) only fill the first column."""
    out, last = list(row), None
    for c in range(start, len(out)):
        if _clean(out[c]):
            last = _clean(out[c])
        out[c] = last
    return out


def read_sample_columns(table: list[list], cfg: ReportConfig) -> tuple[dict[int, dict], int]:
    """Return ({column index: sample metadata}, last header row index)."""
    pat = re.compile(cfg.sample_id_pattern)
    samples: dict[int, dict] = {}
    header_rows = [cfg.location_row or 0]

    if cfg.combined_header:
        # One cell holds several lines: e.g. "BH15-01-07\n2015 03 02\n4.3 - 4.6".
        row = table[cfg.combined_header_row]
        for c, cell in enumerate(row):
            parts = [p.strip() for p in _clean(cell).split("\n")]
            if parts and pat.fullmatch(parts[0]):
                samples[c] = dict(zip(cfg.combined_header, parts, strict=False))  # missing lines stay unset
        header_rows.append(cfg.combined_header_row)
    else:
        found = _find_label_row(table, cfg.header_labels["sample_id"])
        if not found:
            raise ValueError(f"{cfg.report_id}: no '{cfg.header_labels['sample_id']}' header row")
        id_row, label_col = found
        header_rows.append(id_row)
        for c in range(label_col + 1, len(table[id_row])):
            sid = _clean(table[id_row][c])
            if pat.fullmatch(sid):
                samples[c] = {"sample_id": sid}
        for key, label in cfg.header_labels.items():
            if key == "sample_id":
                continue
            hit = _find_label_row(table, label)
            if not hit:
                continue
            header_rows.append(hit[0])
            row = table[hit[0]]
            if key == "location_id":
                row = _forward_fill(row, label_col + 1)
            for c in samples:
                samples[c][key] = _clean(row[c]) if c < len(row) else ""

    if cfg.location_row is not None:
        row = _forward_fill(table[cfg.location_row], 0)
        for c in samples:
            samples[c]["location_id"] = row[c]

    previous = None
    for c in sorted(samples):
        meta = samples[c]
        if cfg.duplicate_marker and meta.get("date", "").lower() == cfg.duplicate_marker.lower():
            meta["duplicate_of"] = previous
        elif meta["sample_id"] in cfg.duplicates:
            meta["duplicate_of"] = cfg.duplicates[meta["sample_id"]]
        previous = meta["sample_id"]
    return samples, max(header_rows)


def check_rpd_columns(
    table: list[list], samples: dict[int, dict], header_end: int, cfg: ReportConfig, page: int
) -> None:
    """Every QA/QC RPD column compares one duplicate pair, so the counts must agree."""
    if not cfg.rpd_label:
        return
    rpd_cols = {
        c
        for row in table[: header_end + 1]
        for c, cell in enumerate(row)
        if cfg.rpd_label.lower() in _clean(cell).lower()
    }
    n_dups = sum(1 for m in samples.values() if m.get("duplicate_of"))
    if len(rpd_cols) != n_dups:
        raise ValueError(f"{cfg.report_id} p{page}: {len(rpd_cols)} RPD columns but {n_dups} duplicates found")


def _analyte_blocks(table: list[list], first_data_row: int):
    """Yield (analyte name, unit, [rows]) with pH-split continuation rows merged in."""
    block = None
    for row in table[first_data_row:]:
        name = row[0]
        if not _clean(name):  # continuation row of the previous analyte (pH-dependent standards)
            if block:
                block[2].append(row)
            continue
        if block:
            yield block
        if _clean(name).lower() in HEADER_WORDS:  # e.g. "Parameter | Units | Analytical Results"
            block = None
            continue
        unit = _clean(row[1]) if len(row) > 1 else ""
        block = (_clean(name), unit, [row])
    if block:
        yield block


def extract_table(table: list[list], cfg: ReportConfig, page: int, section_unit: str | None) -> list[dict]:
    samples, header_end = read_sample_columns(table, cfg)
    if not samples:
        return []
    check_rpd_columns(table, samples, header_end, cfg, page)
    first_data_row = header_end + 1
    out, unit_from_section, section = [], section_unit, ""
    for name, unit, rows in _analyte_blocks(table, first_data_row):
        # Section headers like "Total Metals (μg/g)" carry the unit for the rows below.
        m = re.search(r"\((?:μ|µ|u)g/g\)|\(mg/kg\)", name)
        if all(not _clean(r[c]) for r in rows for c in samples if c < len(r)):
            if m:
                unit_from_section = m.group(0).strip("()")
            section = name  # e.g. "Metals", "Salts (μg/g) via Sat. Paste."
            continue
        analyte_unit = unit if KNOWN_UNITS.fullmatch(unit) else (unit_from_section or cfg.default_unit)
        for c, meta in samples.items():
            cells = [_clean(r[c]) for r in rows if c < len(r) and _clean(r[c]).lower() not in NOT_REPORTED]
            if not cells:
                continue
            if len(cells) > 1:
                raise ValueError(f"{cfg.report_id} p{page} {name} {meta['sample_id']}: several values {cells}")
            try:
                parsed = parse_value(cells[0])
            except ValueError as err:
                raise ValueError(f"{cfg.report_id} p{page} {name} {meta['sample_id']}: {cells[0]!r}") from err
            if parsed is None:
                continue
            value, non_detect, dl = parsed
            top, bottom = parse_depth(meta.get("depth"))
            out.append(
                {
                    "report_id": cfg.report_id,
                    "page": page,
                    "location_id": meta.get("location_id"),
                    "sample_id": meta["sample_id"],
                    "depth_top_m": top,
                    "depth_bottom_m": bottom,
                    "sample_date_raw": meta.get("date"),
                    "fill_or_native": meta.get("fill_native"),
                    "is_duplicate": bool(meta.get("duplicate_of")),
                    "duplicate_of": meta.get("duplicate_of"),
                    "sample_media": cfg.sample_media,
                    "section": section,
                    "analyte_raw": name,
                    "unit_raw": analyte_unit,
                    "value_raw": cells[0],
                    "value": value,
                    "non_detect": non_detect,
                    "detection_limit": dl,
                }
            )
    return out


def extract_report(cfg: ReportConfig, raw_dir: Path = RAW / "reports") -> pd.DataFrame:
    rows = []
    with pdfplumber.open(raw_dir / cfg.file) as pdf:
        for page in cfg.pages:
            for table in pdf.pages[page - 1].extract_tables():
                if len(table) < 5:
                    continue  # legend boxes ("SHADED", "UNDERLINE")
                rows += extract_table(table, cfg, page, cfg.default_unit)
    df = pd.DataFrame(rows)
    _fill_duplicate_metadata(df, cfg)
    looks_dup = df.sample_id.str.contains("DUP|BHX", regex=True) | df.sample_date_raw.eq("Duplicate")
    unknown = set(df.loc[looks_dup & ~df.is_duplicate, "sample_id"])
    if unknown:
        raise ValueError(f"{cfg.report_id}: duplicate-looking samples missing from config: {unknown}")
    return df


def _fill_duplicate_metadata(df: pd.DataFrame, cfg: ReportConfig) -> None:
    """Lab duplicates often have blank depth/date; they share them with the parent sample."""
    pairs = df.loc[df.is_duplicate, ["sample_id", "duplicate_of"]].drop_duplicates()
    for dup, parent in pairs.itertuples(index=False):
        p = df[df.sample_id == parent]
        if p.empty:
            raise ValueError(f"{cfg.report_id}: duplicate {dup} points at missing parent {parent}")
        first = p.iloc[0]
        mask = df.sample_id == dup
        for col in ["location_id", "depth_top_m", "depth_bottom_m", "sample_date_raw", "fill_or_native"]:
            blank = df[col].isna() | df[col].astype("string").isin(["", "Duplicate"])
            df.loc[mask & blank, col] = first[col]


def main() -> None:
    STAGING.mkdir(parents=True, exist_ok=True)
    frames = []
    for cfg in ReportConfig.load_all():
        df = extract_report(cfg)
        print(f"{cfg.report_id}: {df.sample_id.nunique()} samples, {len(df)} results from pages {cfg.pages}")
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(STAGING / "report_results.csv", index=False)
    print(f"wrote {STAGING / 'report_results.csv'} ({len(out)} rows)")


if __name__ == "__main__":
    main()
