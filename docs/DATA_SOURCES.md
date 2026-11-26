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
| Assessment report-sourced surface sediment geochemistry (BCGS GeoFile 2026-02) | Exploration samples compiled from mineral assessment reports | **80 soil samples** (all from Assessment Report 29239, 2007), As/Cu/Zn in ppm | BCGS publication, licence still to confirm | https://cmscontent.nrs.gov.bc.ca/geoscience/PublicationCatalogue/GeoFile/BCGS_GF2026-02.zip |
| 1994 MoE Vancouver Island soil sampling (CDoGS survey 260008) | 9 sites; data only in a consultant report | not downloaded | n/a | https://geochem.nrcan.gc.ca/cdogs/content/svy/svy260008_e.htm |

## 3. Activities / land use (for PCOC screening)

| Layer | In-region features | Licence | Access |
|---|---|---|---|
| OpenStreetMap: `railway=rail`, `landuse=industrial/quarry/landfill/railway`, `amenity=fuel`, `man_made=works` | 342 (125 rail, 92 industrial, 73 fuel, 42 quarry, 6 works, 3 landfill, 1 railway landuse) | ODbL, © OpenStreetMap contributors | Overpass API, cached |
| MINFILE mineral occurrences | 303 (101 Cu, 45 Au, 32 coal, 6 Zn; 57 past producers) | Catalogue says "Access Only": fetch at runtime, don't redistribute raw | openmaps.gov.bc.ca WFS `WHSE_MINERAL_TENURE.MINFIL_MINERAL_FILE` |
