"""Build the extraction accuracy check sheet.

Picks a fixed random sample of extracted values per report (seeded, so it is
repeatable) and saves an image of each value's PDF cell with a red box around it.
A person then compares the image to the extracted value and records the result in
docs/results/extraction_check.csv. The images are rendered from the PDF itself,
so the check doesn't rely on the table parser being right.

Usage: uv run python scripts/make_extraction_check.py [--per-report 20]
"""

from __future__ import annotations

import argparse

import pandas as pd
import pdfplumber

from bc_soil_background.extract.pdf_tables import ReportConfig
from bc_soil_background.paths import RAW, RESULTS, STAGING

FOCUS = r"(?i)^(?:arsenic|copper|zinc)"


def find_cell(page, sample_id: str, value_raw: str, analyte: str):
    """Locate the value's cell, its analyte label cell and its sample-ID header cell."""
    for table in page.find_tables():
        text = table.extract()
        hdr = next(((r, c) for r, row in enumerate(text[:12]) for c, cell in enumerate(row)
                    if cell and cell.strip().split("\n")[0].strip() == sample_id), None)
        if hdr is None:
            continue
        col = hdr[1]
        start = next((i for i, r in enumerate(text) if r[0] and r[0].strip() == analyte), None)
        if start is None:
            continue
        for i in range(start, len(text)):
            if i > start and text[i][0] is not None:
                break
            if (text[i][col] or "").strip() == value_raw:
                return {
                    "cell": table.rows[i].cells[col],
                    "label": table.rows[start].cells[0],
                    "header": table.rows[hdr[0]].cells[col],
                    "table": table.bbox,
                }
    return None


def render_check_image(page, found: dict, path) -> None:
    """Stack the sample-ID header above a strip showing [analyte label | value cell].

    Middle columns are cut out, so the image is small but still shows the three
    things a reviewer needs: which sample, which analyte, and the printed value.
    """
    from PIL import Image

    res = 200  # R3 uses ~6 pt text; lower resolutions blur the digits

    def outside(box, pad=2.5):
        # Draw boxes just outside the cell so the outline never covers the printed value.
        return (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
    cx0, ctop, cx1, cbot = found["cell"]
    tx0, ttop, tx1, tbot = found["table"]
    hx0, htop, hx1, hbot = found["header"]
    lx0, ltop, lx1, lbot = found["label"]
    pad_x = 60
    band = (max(ttop, min(ctop, ltop) - 12), min(tbot, max(cbot, lbot) + 12))
    value_box = (max(tx0, cx0 - pad_x), band[0], min(tx1, cx1 + pad_x), band[1])
    label_box = (tx0, band[0], min(lx1 + 40, cx0 - pad_x), band[1])
    header_box = (value_box[0], max(ttop, htop - 30), value_box[2], hbot + 2)

    im_val = page.crop(value_box).to_image(resolution=res)
    im_val.draw_rect(outside(found["cell"]), stroke="red", stroke_width=2, fill=(0, 0, 0, 0))
    im_lab = page.crop(label_box).to_image(resolution=res)
    im_lab.draw_rect(outside(found["label"]), stroke="blue", stroke_width=2, fill=(0, 0, 0, 0))
    im_hdr = page.crop(header_box).to_image(resolution=res)
    im_hdr.draw_rect(outside(found["header"]), stroke="red", stroke_width=2, fill=(0, 0, 0, 0))
    a, b, h = im_lab.annotated, im_val.annotated, im_hdr.annotated
    out = Image.new("RGB", (a.width + b.width, h.height + max(a.height, b.height) + 6), "white")
    out.paste(h, (a.width, 0))
    out.paste(a, (0, h.height + 6))
    out.paste(b, (a.width, h.height + 6))
    out.save(path)


def main(per_report: int) -> None:
    out_dir = RESULTS / "extraction_check"
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(STAGING / "report_results.csv", dtype={"value_raw": str})
    df = df[~df.unit_raw.isin(["pH", "pH Units", "%"])]
    rows = []
    for cfg in ReportConfig.load_all():
        sub = df[df.report_id == cfg.report_id]
        focus = sub[sub.analyte_raw.str.contains(FOCUS, regex=True)]
        # Half the check goes to As/Cu/Zn (what the statistics use), half to other metals.
        pick = pd.concat([
            focus.sample(per_report // 2, random_state=42),
            sub.drop(focus.index).sample(per_report - per_report // 2, random_state=42),
        ])
        with pdfplumber.open(RAW / "reports" / cfg.file) as pdf:
            for _, r in pick.iterrows():
                page = pdf.pages[int(r.page) - 1]
                found = find_cell(page, r.sample_id, r.value_raw, r.analyte_raw)
                img_name = ""
                if found:
                    img_name = f"{cfg.report_id}_p{int(r.page)}_{r.sample_id}_{r.analyte_raw}.png"
                    img_name = img_name.replace(" ", "_").replace("/", "-").replace("\n", "_")
                    render_check_image(page, found, out_dir / img_name)
                rows.append({
                    "report_id": cfg.report_id, "page": int(r.page), "sample_id": r.sample_id,
                    "analyte": r.analyte_raw, "extracted_value": r.value_raw,
                    "image": f"extraction_check/{img_name}" if img_name else "(cell not located)",
                    "pdf_value": "", "match": "", "checked_by": "",
                })
    sheet = pd.DataFrame(rows)
    sheet.to_csv(RESULTS / "extraction_check_blank.csv", index=False)
    print(f"{len(sheet)} values to check; images in {out_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-report", type=int, default=20)
    main(ap.parse_args().per_report)
