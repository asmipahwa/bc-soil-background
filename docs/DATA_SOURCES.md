# Data sources (Sprint 1 inventory)

Region: **Nanaimo–Cowichan, east Vancouver Island** (working bbox 48.6–49.3°N, 124.3–123.6°W).
All sources below were downloaded and opened on **2026-11-26**. Raw PDFs and large downloads are
git-ignored; this file records where to get them again.

## 1. Public site investigation reports (pdfplumber input)

| # | Report | Site | Author / date | Pages | Soil metals table pages | URL |
|---|---|---|---|---|---|---|
| R1 | Detailed Site Investigation, 1 Port Drive | 1 Port Drive, Nanaimo (filled industrial waterfront) | Tetra Tech EBA for City of Nanaimo, Nov 2015 | 809 | p. 84–92 (Table 2: Soil Analytical Results – Metals), more in later appendices | https://www.nanaimo.ca/docs/your-government/projects/2012-1-port-drive/tetra-tech-detailed-site-investigation---1-port-drive.pdf |
| R2 | Remedial Action Plan annexes, Nanaimo Military Camp / bunker | Former military camp, Nanaimo | SNC-Lavalin data (2015, 2020), posted by DND on CanadaBuys (tender EZ897-220811), 2022 | 195 | p. 36–38 (Table 3: Total Metals) | https://canadabuys.canada.ca/documents/pub/att/2022/03/07/0fd1abd729889be915c968d017ddd696/ez897-220811_-_annexes.pdf |
| R3 | TCH Pathway Soil Assessment Results (T-2023-02) | Trans-Canada Hwy multi-use path, Duncan | Active Earth for Stantec / City of Duncan, Oct 2023 | 76 | p. 15–16 (Table 2: Metals and Salts in Soil); fill vs. native recorded per sample | https://duncan.ca/wp-content/uploads/dlm_uploads/2023/12/T-2023-02-TCH-Pathway-Final-Soil-Assessment-Results.pdf |

Checked and **not usable** (kept for honesty):

| Report | Why not |
|---|---|
| Nanaimo 1 Port Drive Stage 1 PSI (Tetra Tech) | Desktop review, no lab tables |
| Nanaimo 1 Port Drive Detailed Risk Assessment | Same site as R1 (water lot); would duplicate R1 |
| Nanaimo 6 Commercial St desktop review (SLR, 2023) | Summarises older reports, no tables |
| Ladysmith Harbour supplemental PSI/DSI (Golder, 2011) | Posted without Appendix III, so no lab tables |
| CVRD Fisher Road environmental review (EBA, 2010) | Water and compost, not soil |
| Port Alberni McLean Mill (TerraWest, 2018) | Pond sediment, and outside the region |
| MoTI North Cowichan Step B soil characterization | URL now returns 404 |

Licensing: these are consultant reports posted publicly by the City of Nanaimo, the City of Duncan and the Government of Canada.
We store **extracted numbers + citation**, not the PDFs.

## 2. BC open geochemistry

| Dataset | What it is | In-region rows | Licence | URL |
|---|---|---|---|---|
| RGS 2020 database (BCGS / GSC NGR) | Regional Geochemical Survey. **In this region every sample is moss-mat stream sediment (1989, RGS 24/25), not soil.** | 264 sites, As/Cu/Zn by AAS (264) and ICP (261) | Open Government Licence – BC | https://catalogue.data.gov.bc.ca/dataset/49a73c36-4a25-4be5-b6d1-abd020fb031a |
| Assessment report-sourced surface sediment geochemistry (BCGS GeoFile 2026-02) | Exploration samples compiled from mineral assessment reports | **80 soil samples** (all from Assessment Report 29239, 2007), As/Cu/Zn in ppm | BCGS GeoFile: "available, free of charge"; no explicit open licence found (checked 2026-11-26). Derived rows are **not committed** until confirmed | https://cmscontent.nrs.gov.bc.ca/geoscience/PublicationCatalogue/GeoFile/BCGS_GF2026-02.zip |
| 1994 MoE Vancouver Island soil sampling (CDoGS survey 260008) | 9 sites; data only in a consultant report | not downloaded | n/a | https://geochem.nrcan.gc.ca/cdogs/content/svy/svy260008_e.htm |

## 3. Activities / land use (for PCOC screening) and regions

Fetched by `src/bc_soil_background/extract/activities.py` on first run (2026-11-26), saved under `data/raw/`.

| Layer | In-region features | Licence | Access |
|---|---|---|---|
| OpenStreetMap: `railway=rail`, `landuse=industrial/quarry/landfill/railway`, `amenity=fuel`, `man_made=works`, `industrial=*` | 350 (126 rail, 92 other industrial, 73 fuel, 42 quarry, 5 sawmill, 3 landfill, 2 pulp mill, 2 salvage) | ODbL, © OpenStreetMap contributors | Overpass API (`out geom`) |
| MINFILE mineral occurrences | 303 (64 mines: past producer/producer/developed prospect; 239 showings/prospects/anomalies) | Catalogue says "Access Only": fetch at runtime, don't redistribute raw | openmaps.gov.bc.ca WFS `WHSE_MINERAL_TENURE.MINFIL_MINERAL_FILE` |
| BC regional districts | 5 intersect the bbox | OGL-BC | openmaps.gov.bc.ca WFS `WHSE_LEGAL_ADMIN_BOUNDARIES.ABMS_REGIONAL_DISTRICTS_SP` |

PCOC references (local copies in `data/raw/protocols/` and `data/raw/guidance/`, listed in `config/raw_manifest.yaml`):

- BC Protocol 4 v15 (2026): https://www2.gov.bc.ca/assets/gov/environment/air-land-water/site-remediation/docs/protocols/2026-06-10_final_protocol_4_v15_signed.pdf
- CSAP Society, *PCOCs at Select Commercial and Industrial Land Uses*, v1.0 (June 2018): https://csapsociety.bc.ca/wp-content/uploads/r-PCOC-Guidance-June-2018-V1.0-002.pdf

## 4. Local copies (`data/raw/`, git-ignored)

Everything was downloaded on 2026-11-26. To rebuild `data/raw/` on a new machine, download each URL below to the path shown.

| Local path | Source URL |
|---|---|
| `reports/nanaimo_portdrive_dsi.pdf` (R1) | https://www.nanaimo.ca/docs/your-government/projects/2012-1-port-drive/tetra-tech-detailed-site-investigation---1-port-drive.pdf |
| `reports/nanaimo_military_camp_annexes.pdf` (R2) | https://canadabuys.canada.ca/documents/pub/att/2022/03/07/0fd1abd729889be915c968d017ddd696/ez897-220811_-_annexes.pdf |
| `reports/duncan_tch_pathway.pdf` (R3) | https://duncan.ca/wp-content/uploads/dlm_uploads/2023/12/T-2023-02-TCH-Pathway-Final-Soil-Assessment-Results.pdf |
| `reports/nanaimo_portdrive_psi1.pdf` (not used) | https://www.nanaimo.ca/docs/your-government/projects/2012-1-port-drive/tetra-tech-stage-1-prelim-investigation---1-port-drive.pdf |
| `reports/nanaimo_portdrive_dra.pdf` (not used) | https://www.nanaimo.ca/docs/your-government/projects/2012-1-port-drive/tetra-tech-detailed-risk-assessment---1-port-drive.pdf |
| `reports/nanaimo_6commercial_review.pdf` (not used) | https://www.nanaimo.ca/docs/real-estate/review-of-historical-site-assessment-reports.pdf |
| `reports/ladysmith_harbour_psi_dsi.pdf` (not used) | https://www.ladysmith.ca/docs/default-source/reports-2021/2011-12-21--ls-harbour-supplem-stage-1-psi-and-dsi-no-appendix-iii.pdf?sfvrsn=518f2abd_10 |
| `reports/cvrd_fisherrd_env_review.pdf` (not used) | https://cvrd.ca/wp-content/uploads/2025/09/FisherRdEnvironmentalRpt-Nov-10.pdf |
| `reports/portalberni_binder6.pdf` (not used) | https://portalberni.ca/sites/default/files/doc_library/Binder6.pdf |
| `geochem/rgs2020_data.xlsx` | https://catalogue.data.gov.bc.ca/dataset/49a73c36-4a25-4be5-b6d1-abd020fb031a/resource/d55bab93-e73e-497a-9cb3-08b579693f42/download/rgs2020_data.xlsx |
| `geochem/rgs2020_metadata.xlsx` | https://catalogue.data.gov.bc.ca/dataset/49a73c36-4a25-4be5-b6d1-abd020fb031a/resource/cda9ab00-dc20-4b7d-95ea-5e4f54abf369/download/rgs2020_metadata.xlsx |
| `geochem/GF2026-02.zip` → `geochem/arssg/arssg_data_release.gpkg` | https://cmscontent.nrs.gov.bc.ca/geoscience/PublicationCatalogue/GeoFile/BCGS_GF2026-02.zip |
| `geochem/GF2026-02.pdf` (report for the zip) | https://cmscontent.nrs.gov.bc.ca/geoscience/PublicationCatalogue/GeoFile/BCGS_GF2026-02.pdf |
| `geochem/GF2019-04.pdf`, `geochem/GF2025-11.pdf`, `geochem/GF2026-11.pdf` (background reading) | https://cmscontent.nrs.gov.bc.ca/geoscience/PublicationCatalogue/GeoFile/BCGS_GF2019-04.pdf, …/BCGS_GF2025-11.pdf, …/BCGS_GF2026-11.pdf |
| `activities/minfile_region_2026-11-26.json` | https://openmaps.gov.bc.ca/geo/pub/wfs?service=WFS&version=2.0.0&request=GetFeature&typeName=WHSE_MINERAL_TENURE.MINFIL_MINERAL_FILE&outputFormat=application/json&srsName=EPSG:4326&bbox=48.6,-124.3,49.3,-123.6,urn:ogc:def:crs:EPSG::4326&count=2000 |
| `activities/osm_activities.json` | Overpass API (https://overpass-api.de/api/interpreter), query `OSM_QUERY` in `extract/activities.py` |
| `boundaries/regional_districts.json` | openmaps.gov.bc.ca WFS, see §3 |
| `protocols/protocol_4_v15.pdf`, `guidance/csap_pcoc_guidance_2018_v1.pdf` | see §3 |

Sprint 2 adds `scripts/download_raw.py`, which rebuilds this folder from the table above.

## 5. How each source is used (Sprint 2)

| Source | Rows in pipeline | Used for |
|---|---|---|
| R1–R3 site reports | 179 soil samples (17 duplicates), 3,592 results | soil background candidates (after screening) |
| GeoFile 2026-02 soil (AR 29239) | 80 soil samples, 2,800 results | soil background candidates (after screening) |
| RGS 2020 | 264 moss-mat sediment sites, 792 As/Cu/Zn results | **comparison only, labelled "sediment, not soil"** |

Site locations: R1 geocoded from its civic address (Nominatim, ODbL); R2 placed at the
Nanaimo Parkway / Nanaimo Lakes Road intersection named as its boundary in the report (Overpass, ODbL);
R3 uses the centre coordinates printed in the report. See `config/sites.yaml`. OSM lookups are cached
in `data/cache/` (© OpenStreetMap contributors, ODbL).

## 6. How each source is used (Sprint 3)

| Source | Used for |
|---|---|
| OSM + MINFILE land uses | GeoPandas buffer screening (`analysis/screening.py`) |
| Report PCOC pages (R1 pp.3–4, 13–15, 20–21; R2 p.3; R3 p.4) | `config/report_site_activities.csv`: each report's own site has metal PCOCs |
| Regional districts | grouping results per region (`analysis/background.py`) |
| Protocol 4 v15 Table 1 (p.9) | comparison values for Region 1 (Cu 100, Zn 150; As printed "(4)") |
