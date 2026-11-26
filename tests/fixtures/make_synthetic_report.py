"""Build tests/fixtures/synthetic_report.pdf: a FAKE lab table for unit tests only.

SYNTHETIC TEST DATA. Every number here is made up. It never enters data/ and never counts
toward any result. It copies the awkward layouts seen in real reports: merged borehole cells,
a pH-dependent standard that splits one analyte over two rows, a "<DL" value, a duplicate
column marked "Duplicate", and a QA/QC "RPD %" column.
"""

from pathlib import Path

from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

ROWS = [
    ["SYNTHETIC", "", "Borehole", "TB01", "", "", "TB02"],
    ["", "", "Field ID", "TB01-1", "TB01-2", "RPD %", "TB02-1"],
    ["", "", "Depth", "0.5 - 0.7", "0.5 - 0.7", "", "1.2"],
    ["", "", "Date", "01-Jan-2026", "Duplicate", "", "02-Jan-2026"],
    ["Parameter", "Unit", "", "", "", "", ""],
    ["Metals", "", "", "", "", "", ""],
    ["Arsenic", "mg/kg", "", "5.1", "5.3", "4", "<2"],
    ["Copper", "mg/kg", "pH<6", "", "", "", "41.5"],
    ["", "", "pH>=6", "22.0", "23.4", "6", ""],
    ["Zinc", "mg/kg", "", "1,250", "1,190", "5", "60"],
]


def build(path: Path) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=landscape(letter))
    t = Table(ROWS)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "black"), ("SPAN", (3, 0), (5, 0))]))
    doc.build([t])


if __name__ == "__main__":
    build(Path(__file__).with_name("synthetic_report.pdf"))
