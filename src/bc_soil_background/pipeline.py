"""Run the whole pipeline in order: `uv run bcsb` (needs `docker compose up -d` for the load step).

Steps can be skipped with flags, e.g. `uv run bcsb --skip-load` to work without Docker.
"""

import argparse

from bc_soil_background.analysis import background, screening
from bc_soil_background.extract import geochem, locations, pdf_tables
from bc_soil_background.load import to_postgis
from bc_soil_background.transform import standardize


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-load", action="store_true", help="don't load into PostGIS")
    args = ap.parse_args()
    steps = [
        ("extract site report tables (pdfplumber)", pdf_tables.main),
        ("place report sites on the map", locations.main),
        ("import BC open geochemistry", geochem.main),
        ("standardize + data-quality flags", standardize.main),
    ]
    if not args.skip_load:
        steps.append(("load into PostGIS", to_postgis.main))
    steps += [
        ("screen soil samples with GeoPandas buffers", screening.main),
        ("background statistics per region (SciPy)", background.main),
    ]
    for i, (label, fn) in enumerate(steps, 1):
        print(f"\n== [{i}/{len(steps)}] {label}")
        fn()


if __name__ == "__main__":
    main()
