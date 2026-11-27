# Extraction accuracy check (pdfplumber → `data/staging/report_results.csv`)

**Result: 60 of 60 sampled values match the PDF (100%), 20 per report.** Half of each report's
sample is arsenic, copper or zinc, the analytes the background statistics use.

| Report | Values checked | Matched | Of which As/Cu/Zn |
|---|---|---|---|
| R1 Nanaimo 1 Port Drive DSI | 20 | 20 | 10 |
| R2 Nanaimo Military Camp annexes | 20 | 20 | 10 |
| R3 Duncan TCH Pathway | 20 | 20 | 10 |

Per-value record: [`extraction_check.csv`](extraction_check.csv). Each row gives the PDF page, the
table row/column and the cell's bounding box in PDF points (`cell_bbox_pt`: x0, top, x1, bottom), so
anyone with the public PDF can find the cell. The check images are crops of consultants' reports, so
they are **kept local only** (git-ignored); `uv run python scripts/make_extraction_check.py` re-renders
them into `docs/results/extraction_check/`.

## How the check works

1. `scripts/make_extraction_check.py` picks 20 extracted values per report with a fixed random seed (42),
   so the same values come up on every run.
2. For each value it renders the PDF page itself into an image showing three things: the
   sample-ID header (red), the analyte label (blue), and the printed value (red). The image comes
   from the PDF's pixels, so the check doesn't depend on the table parser being right.
3. A reviewer compares each image to the extracted value.

**Who checked:** the first pass (2026-11-26) was a visual check of every image by Claude, the AI
assistant used on this project. **The `asmi_check` column is for Asmi to repeat the check by eye.**
Until that column is filled in, treat this as an AI-assisted check, not an independent human one.

## What the check caught

- **A missed duplicate.** The images showed R2 sample `BH20-14-05` with "Duplicate" in its date
  line. The first config had listed only some R2 duplicates by hand. Fix: the extractor now marks
  any sample whose date cell reads "Duplicate" as a duplicate of the sample to its left. It also
  checks that the number of "QA/QC RPD %" columns on each page equals the number of duplicates
  found, and stops with an error if they differ. All 3 R2 pages and R3 p.16 pass that check.
- **Unreadable images.** At 130 dpi R3's ~6 pt digits were blurred and the red box covered them.
  Fix: images are now rendered at 200 dpi, with boxes drawn just outside the cell.

## Limits

- 60 of 3,592 extracted rows were checked (1.7%). This is a sample, not a full proof.
- The check confirms that values were **copied** correctly. It doesn't check whether the labs or
  consultants got them right.
- Automated guards cover the rest: the extractor stops on any cell it can't parse, on an analyte
  with two values for one sample, on a duplicate-looking sample with no parent, and on an RPD/duplicate
  count mismatch.
