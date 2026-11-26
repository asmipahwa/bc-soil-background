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
