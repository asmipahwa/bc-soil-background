"""Extractor tests on a SYNTHETIC fixture PDF (made-up numbers, see tests/fixtures/make_synthetic_report.py)."""

from pathlib import Path

import pytest

from bc_soil_background.extract.pdf_tables import ReportConfig, extract_report, parse_depth, parse_value

FIXTURES = Path(__file__).parent / "fixtures"


def synthetic_cfg(**overrides) -> ReportConfig:
    base = dict(
        report_id="SYN",
        file="synthetic_report.pdf",
        pages=[1],
        sample_id_pattern=r"TB\d\d-\d",
        rpd_label="RPD",
        duplicate_marker="Duplicate",
        header_labels={"sample_id": "Field ID", "location_id": "Borehole", "depth": "Depth", "date": "Date"},
    )
    base.update(overrides)
    return ReportConfig(**base)


@pytest.fixture(scope="module")
def extracted():
    return extract_report(synthetic_cfg(), raw_dir=FIXTURES)


def test_parse_value_handles_commas_and_non_detects():
    assert parse_value("1,250") == (1250.0, False, None)
    assert parse_value("< 0.1") == (None, True, 0.1)
    assert parse_value("-") is None
    with pytest.raises(ValueError):
        parse_value("AnalyticalResults")


def test_parse_depth():
    assert parse_depth("0.5 - 0.9") == (0.5, 0.9)
    assert parse_depth("1.2") == (1.2, 1.2)
    assert parse_depth(None) == (None, None)


def test_rpd_column_is_not_a_sample(extracted):
    assert set(extracted.sample_id) == {"TB01-1", "TB01-2", "TB02-1"}


def test_ph_split_rows_merge_into_one_value(extracted):
    cu = extracted[extracted.analyte_raw == "Copper"].set_index("sample_id").value
    assert cu.to_dict() == {"TB01-1": 22.0, "TB01-2": 23.4, "TB02-1": 41.5}


def test_non_detect_kept_with_detection_limit(extracted):
    row = extracted[(extracted.sample_id == "TB02-1") & (extracted.analyte_raw == "Arsenic")].iloc[0]
    assert row.non_detect and row.detection_limit == 2.0 and row.value != row.value  # NaN


def test_duplicate_detected_and_inherits_parent_metadata(extracted):
    dup = extracted[extracted.sample_id == "TB01-2"].iloc[0]
    assert dup.is_duplicate and dup.duplicate_of == "TB01-1"
    assert dup.sample_date_raw == "01-Jan-2026"
    assert dup.location_id == "TB01"


def test_merged_borehole_cell_fills_right(extracted):
    loc = extracted.drop_duplicates("sample_id").set_index("sample_id").location_id
    assert loc["TB02-1"] == "TB02"


def test_rpd_count_mismatch_raises():
    with pytest.raises(ValueError, match="RPD columns"):
        extract_report(synthetic_cfg(duplicate_marker=None), raw_dir=FIXTURES)
