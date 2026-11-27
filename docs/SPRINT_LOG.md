# Sprint log

## Sprint 1: data hunt (2026-11-26)
- Region chosen: Nanaimo–Cowichan (east Vancouver Island).
- 3 real public PDFs with soil metals tables were found and opened with pdfplumber (see DATA_SOURCES.md §1).
- Geochemistry: the RGS rows here are moss-mat sediment, not soil. Real soil comes from 80 assessment-report samples (one 2007 program).
- Activity layers: OSM (342 features) + MINFILE (303 occurrences) are available for free.

## Sprint 2: extract, clean, load (2026-11-26)
- pdfplumber extractor + per-report config (`config/reports.yaml`): R1 131 samples, R2 36, R3 12 (17 are duplicates).
- Extraction check: 60/60 sampled values match the PDF (AI first pass; Asmi's own check still to do).
  The check found a missed R2 duplicate. Duplicates are now auto-detected and cross-checked against RPD columns.
- Geochemistry: 80 soil samples (AR 29239, Maple Mountain, C-horizon till) + 264 RGS moss-mat sites (comparison only).
- Standardized schema (mg/kg, EPSG:3005, DQ flags), loaded into PostGIS 3.4 (523 samples, 7,184 results).
- `uv run bcsb` reruns everything; a fresh clone reproduced all outputs byte-for-byte.
- Open: GeoFile 2026-02 licence unconfirmed, so its derived rows are git-ignored for now.

## Sprint 3 (2026-11-26), fast mode: only what the three resume bullets need

- Read Protocol 4 v15 section 4 → `docs/PROTOCOL_NOTES.md`.
- `config/activity_pcoc.csv` (cited PCOCs + buffer distances) and `config/report_site_activities.csv`.
- `extract/activities.py`: OSM (Overpass, with geometry), MINFILE, regional districts.
- `analysis/screening.py`: GeoPandas buffers (buffer + location uncertainty) for each sample and metal.
  Result: 75 of 259 soil samples kept (all 179 report samples excluded; 5 GeoFile samples near a quarry).
- `analysis/background.py`: duplicates averaged, ND = DL/2 (sensitivity: 0, DL), log10 + IQR outliers,
  n / %ND / median / P95 / bootstrap CI / Shapiro in SciPy, per region → `docs/results/RESULTS.md` + 3 plots.
- README, INTERVIEW_NOTES, MIT licence. Extraction-check images now git-ignored, with page/cell refs in the CSV.
- Skipped on purpose: Streamlit app, long notebook, CI.
