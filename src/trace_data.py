"""Read raw country tables and resolve expenditure-to-raw trace links."""

import json

import pandas as pd

from src.db import connect, create_tables
from src.ingest_raw import RAW_TABLES
from src.settings import load_source_definitions

ALLOWED_RAW_TABLES = set(RAW_TABLES.values())


def list_raw_countries():
    """Countries that have a raw table defined (CTA, CTB, CTC)."""
    definitions = load_source_definitions()
    return [
        {
            "country_code": code,
            "country_name": definitions[code]["country_name"],
            "raw_table": RAW_TABLES[code],
        }
        for code in ("CTA", "CTB", "CTC")
        if code in RAW_TABLES
    ]


def load_raw_table(country_code):
    """Return the raw table for one country as a DataFrame (original columns)."""
    if country_code not in RAW_TABLES:
        raise ValueError(f"Unknown country_code: {country_code}")
    table_name = RAW_TABLES[country_code]
    create_tables()
    con = connect()
    frame = con.execute(f"SELECT * FROM {table_name}").df()
    con.close()
    return frame


def raw_ingest_meta(frame):
    """Summarise which ingest is on screen (file, time, counts)."""
    if frame is None or frame.empty:
        return {
            "row_count": 0,
            "source_file_name": None,
            "loaded_at": None,
            "ingest_id": None,
        }
    source_file = None
    loaded_at = None
    ingest_id = None
    if "source_file_name" in frame.columns:
        names = frame["source_file_name"].dropna().astype(str).unique().tolist()
        source_file = names[0] if names else None
    if "loaded_at" in frame.columns:
        times = frame["loaded_at"].dropna().tolist()
        loaded_at = times[0] if times else None
    if "ingest_id" in frame.columns:
        ids = frame["ingest_id"].dropna().astype(str).unique().tolist()
        ingest_id = ids[0] if ids else None
    return {
        "row_count": len(frame),
        "source_file_name": source_file,
        "loaded_at": loaded_at,
        "ingest_id": ingest_id,
    }


def get_expenditure(expenditure_id):
    """Return one processed expenditure row as a dict, or None."""
    create_tables()
    con = connect()
    frame = con.execute(
        "SELECT * FROM expenditure WHERE expenditure_id = ?",
        [expenditure_id],
    ).df()
    con.close()
    if frame.empty:
        return None
    return frame.iloc[0].to_dict()


def get_raw_row(raw_table, ingest_id, raw_row_id):
    """Return the matching raw row as a dict, or None."""
    if not raw_table or raw_table not in ALLOWED_RAW_TABLES:
        return None
    if ingest_id is None or (isinstance(ingest_id, float) and pd.isna(ingest_id)):
        return None
    if raw_row_id is None or (isinstance(raw_row_id, float) and pd.isna(raw_row_id)):
        return None
    create_tables()
    con = connect()
    frame = con.execute(
        f"""
        SELECT * FROM {raw_table}
        WHERE ingest_id = ? AND source_row_number = ?
        """,
        [str(ingest_id), int(raw_row_id)],
    ).df()
    con.close()
    if frame.empty:
        return None
    return frame.iloc[0].to_dict()


def get_ingest_batch(ingest_id):
    """Return ingest_batch metadata for one load, or None."""
    if ingest_id is None or (isinstance(ingest_id, float) and pd.isna(ingest_id)):
        return None
    create_tables()
    con = connect()
    frame = con.execute(
        "SELECT * FROM ingest_batch WHERE ingest_id = ?",
        [str(ingest_id)],
    ).df()
    con.close()
    if frame.empty:
        return None
    return frame.iloc[0].to_dict()


def parse_sub_transactions(raw_row):
    """Parse Country C subTransactions JSON into a DataFrame (may be empty)."""
    if not raw_row:
        return pd.DataFrame()
    payload = raw_row.get("subTransactions")
    if payload is None or (isinstance(payload, float) and pd.isna(payload)):
        return pd.DataFrame()
    text = str(payload).strip()
    if not text or text.lower() in {"null", "none", "nan", "[]"}:
        return pd.DataFrame()
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return pd.DataFrame()
    if not isinstance(parsed, list) or not parsed:
        return pd.DataFrame()
    return pd.json_normalize(parsed)


def load_trace(expenditure_id):
    """Bundle processed row + raw row + ingest batch + CTC sub-lines."""
    expenditure = get_expenditure(expenditure_id)
    if expenditure is None:
        return None
    raw_row = None
    raw_table = expenditure.get("raw_table")
    ingest_id = expenditure.get("ingest_id")
    raw_row_id = expenditure.get("raw_row_id")
    if raw_table and ingest_id is not None and raw_row_id is not None:
        raw_row = get_raw_row(raw_table, ingest_id, raw_row_id)
    batch = get_ingest_batch(ingest_id) if ingest_id else None
    subs = (
        parse_sub_transactions(raw_row)
        if expenditure.get("country_code") == "CTC"
        else pd.DataFrame()
    )
    return {
        "expenditure": expenditure,
        "raw_row": raw_row,
        "ingest_batch": batch,
        "sub_transactions": subs,
    }
