"""Small smoke tests for core classification and quality helpers."""

from src.classify import classify_by_coa, classify_record, load_account_mappings
from src.quality import parse_amount


def test_parse_amount_plain():
    value, flags = parse_amount("1767857.37")
    assert value == 1767857.37
    assert flags == []


def test_parse_amount_messy_french_style():
    value, flags = parse_amount('1 234,56')
    assert value == 1234.56
    assert "amount_format" in flags


def test_coa_map_country_a_cleaning_account():
    mappings = load_account_mappings()
    result = classify_by_coa("CTA", "2211407", mappings=mappings)
    assert result is not None
    assert result["sha_code"] == "HC.7"
    assert result["srhr_code"] == "SRHR.NA"
    assert result["classification_method"] == "coa_map"


def test_classify_falls_back_to_keyword_when_no_coa():
    result = classify_record(
        "CTA",
        "9999999",
        "procurement of hiv test kits and arvs",
        quality_flags="",
    )
    assert result["classification_method"] == "keyword"
    assert result["sha_code"] == "HC.5.1"
    assert result["srhr_code"] == "SRHR.HIV"
