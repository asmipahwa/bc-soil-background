# Interview notes

## 30-second pitch

BC sets soil cleanup standards, but some metals occur naturally at high levels. So the question is often
"what's the natural background here?" I built a pipeline for the Nanaimo–Cowichan area that does three
things:
1. It pulls lab tables out of public site-investigation PDFs with pdfplumber and joins them with BC
   geochemistry data into one PostGIS dataset of 523 samples.
2. It screens out samples near land uses whose likely contaminants include each metal, using GeoPandas
   buffers.
3. It follows Protocol 4's steps: average duplicates, handle non-detects, remove outliers on a log scale,
   then take the 95th percentile in SciPy.

Of 259 soil samples, 75 survived screening. Their P95s are As 7, Cu 75 and Zn 64 mg/kg. Cu and Zn are below
the ministry's Region 1 values (100 and 150).

## One sample, start to finish

**A sample that was excluded.** R1 is the Tetra Tech DSI for 1 Port Drive, Nanaimo. On PDF page 89, the
table cell for sample `14BH14-1` (borehole 14BH14, 0.30–0.43 m, 2014-09-18) reads **Arsenic 22.6**.
1. pdfplumber's lattice mode finds the cell from its drawn borders. The extractor reads the sample ID,
   depth and date from the header rows and writes one long-format row with value 22.6 and non_detect False.
   That cell is row 18, column 15 of the table (`docs/results/extraction_check.csv`), and the visual check
   matched it.
2. Standardizing keeps the unit as mg/kg (no conversion). The site is placed by geocoding its civic address
   (300 m uncertainty), converted to BC Albers, and flagged `location_approximate_to_site` and
   `fill_or_native_unknown`.
3. Screening excludes it for all three metals, for three reasons:
   - it's on a site whose own report lists metals as PCOCs (rail yard on coal-waste fill, pp.13–15);
   - rail is 85 m away, inside the 50 m buffer plus 300 m uncertainty;
   - a MINFILE past-producer coal mine is 531 m away, inside 500 m plus 300 m.
4. So it never reaches the statistics. That's the point: 22.6 is a contaminated-site number, not background.

**A sample that was kept.** AR 29239 soil sample `L-1-0+20` (Maple Mountain, C horizon, about 1 m) has
As 4, Cu 27, Zn 51 mg/kg. No feature with metal PCOCs falls inside any buffer. It goes into the Region 1 /
Cowichan Valley group: no duplicates to average, not a non-detect, and inside the log-IQR fences. It's one of
the 75 values the P95 is taken from.

## Five likely questions

**1. Why did you throw out all the site-report samples? Isn't that most of your PDF work?**
Protocol 4 says background samples must be unaffected by contaminant sources. Every report site was
investigated *because* of a land use whose PCOCs include metals, and the reports say so. The extraction
still matters: it's what lets the pipeline show, with evidence, that those samples aren't background. The
same pipeline would keep a report's samples if the report were a reference-site study.

**2. Why a log transform before the IQR test?**
Soil metal concentrations are right-skewed and roughly log-normal. On the raw scale, an IQR rule flags
ordinary high values and misses low ones. On the log scale the distribution is closer to symmetric, so
Tukey's 1.5 × IQR fences behave as intended. Zinc lost one value (120 mg/kg); As and Cu lost none.

**3. How did you handle non-detects, and does it matter?**
The main estimate uses half the detection limit. I reran everything with ND = 0 and ND = DL, and the P95
didn't change for any metal (As stays 7.0). That's because the 27% of arsenic non-detects are all at
DL = 2, well below the 95th percentile. With more non-detects I'd use a censored-data method such as
Kaplan–Meier or ROS.

**4. How did you choose buffer distances and PCOCs?**
The PCOCs come from cited sources: CSAP's PCOC guidance for rail, sawmills, pulp mills and fuel; the
reports' own PCOC tables; and Protocol 4 s.4.2.2 for mined ground. The distances (50 m rail, 100 m
industry, 500 m mines and landfills, 1 km pulp mills) are my assumptions, because no BC rule sets them. The
screening also takes each metal separately: a fuel station's PCOCs are hydrocarbons and lead, so it doesn't
exclude a sample for zinc. Each site's location uncertainty is added to every buffer.

**5. Can these numbers replace Protocol 4 Table 1?**
No. Every kept sample comes from one Cowichan area (Maple Mountain till). The samples were sieved finer
than standard and taken from about 1 m depth rather than near the surface. The data fail a Shapiro-Wilk
single-population test, and there's no qualified professional or director's approval. What the numbers
show is that the method works and gives values in a plausible range (Cu and Zn below Table 1).
