"""Load YAML and path settings for source extracts."""

import yaml

from src.db import PROJECT_ROOT

CONFIG_DIR = PROJECT_ROOT / "config"
CANDIDATE_DATA = PROJECT_ROOT / "candidate_data"
SOURCE_DEFINITIONS_PATH = CONFIG_DIR / "source_definitions.yml"

FILE_TYPE_LABELS = {
    "csv": "CSV",
    "xlsx": "Excel",
    "json": "JSON",
}

FILE_TYPE_EXTENSIONS = {
    "csv": ["csv"],
    "xlsx": ["xlsx"],
    "json": ["json"],
}

SAMPLE_FILES = {
    "CTA": CANDIDATE_DATA / "country_a_expenditure.csv",
    "CTB": CANDIDATE_DATA / "country_b_depenses.xlsx",
    "CTC": CANDIDATE_DATA / "country_c_expenditure.json",
}

EXPECTED_FILENAMES = {
    "CTA": "country_a_expenditure.csv",
    "CTB": "country_b_depenses.xlsx",
    "CTC": "country_c_expenditure.json",
}


def load_source_definitions():
    with SOURCE_DEFINITIONS_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def country_options():
    definitions = load_source_definitions()
    return [
        {
            "code": code,
            "label": f"{values['country_name']} ({code})",
            "file_type": values["file_type"],
            "file_type_label": FILE_TYPE_LABELS.get(values["file_type"], values["file_type"]),
        }
        for code, values in definitions.items()
    ]
