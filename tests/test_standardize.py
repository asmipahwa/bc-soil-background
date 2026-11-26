import pandas as pd
import pytest

from bc_soil_background.extract.locations import dms_to_decimal
from bc_soil_background.transform.standardize import convert_units, parse_date


def test_parse_date_formats_seen_in_sources():
    assert parse_date("15-Sep-2014") == pd.Timestamp("2014-09-15")
    assert parse_date("2015 03 02") == pd.Timestamp("2015-03-02")
    assert parse_date("21-Sep-23") == pd.Timestamp("2023-09-21")
    assert parse_date("1989") == pd.Timestamp("1989-01-01")
    with pytest.raises(ValueError):
        parse_date("sometime")


def test_unit_conversion():
    r = pd.DataFrame(
        {
            "analyte": ["Cu", "Fe", "Hg", "pH"],
            "analyte_kind": ["metal", "metal", "metal", "physical"],
            "unit_raw": ["µg/g", "%", "ppb", "pH Units"],
            "value": [50.0, 2.5, 40.0, 7.1],
            "detection_limit": [None, None, None, None],
        }
    )
    out = convert_units(r)
    assert out.value.tolist() == [50.0, 25_000.0, 0.04, 7.1]
    assert out.unit.tolist() == ["mg/kg", "mg/kg", "mg/kg", "pH"]
    assert out.unit_converted.tolist() == [False, True, True, False]


def test_unknown_unit_is_an_error():
    r = pd.DataFrame(
        {"analyte": ["Cu"], "analyte_kind": ["metal"], "unit_raw": ["mg/L"], "value": [1.0], "detection_limit": [None]}
    )
    with pytest.raises(ValueError, match="no unit conversion"):
        convert_units(r)


def test_dms_from_r3_report():
    assert dms_to_decimal("48 46 24.5 N") == pytest.approx(48.773472, abs=1e-6)
    assert dms_to_decimal("123 41 55.0 W") == pytest.approx(-123.698611, abs=1e-6)
