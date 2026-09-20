"""Save original extracts into per-country raw tables."""

import json
from datetime import datetime
from io import BytesIO
from uuid import uuid4

import pandas as pd

from src.db import connect, create_tables
from src.settings import load_source_definitions
from src.validate_import import REQUIRED_COLUMNS, _country_b_header_index

RAW_TABLES = {
    "CTA": "raw_country_a",
    "CTB": "raw_country_b",
    "CTC": "raw_country_c",
}

COUNTRY_A_COLUMNS = [
    "TXN_ID",
    "DATE",
    "MINISTRY_CODE",
    "MINISTRY_NAME",
    "ACCOUNT_CODE",
    "DESCRIPTION",
    "VENDOR",
    "AMOUNT_KES",
    "PAYMENT_METHOD",
]


def new_ingest_id():
    return str(uuid4())


def replace_raw_for_country(country_code):
    """Delete existing raw rows for this country only."""
    table_name = RAW_TABLES[country_code]
    create_tables()
    con = connect()
    con.execute(f"DELETE FROM {table_name}")
    con.close()
    return table_name


def record_ingest_batch(
    ingest_id, country_code, source_file_name, loaded_at, rows_read, rows_stored
):
    create_tables()
    con = connect()
    con.execute(
        """
        INSERT INTO ingest_batch (
            ingest_id, country_code, source_file_name, loaded_at, rows_read, rows_stored
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [ingest_id, country_code, source_file_name, loaded_at, rows_read, rows_stored],
    )
    con.close()
    return ingest_id


def insert_raw_country_a(ingest_id, source_file_name, loaded_at, file_bytes):
    """Insert Country A CSV as text. Do not parse or fix amounts."""
    frame = pd.read_csv(BytesIO(file_bytes), dtype=str, keep_default_na=False)
    rows_read = len(frame)
    out = pd.DataFrame(
        {
            "ingest_id": ingest_id,
            "source_file_name": source_file_name,
            "loaded_at": loaded_at,
            "source_row_number": range(2, rows_read + 2),
        }
    )
    for column in COUNTRY_A_COLUMNS:
        out[column] = frame[column].astype(str)
    con = connect()
    con.register("_raw_a", out)
    con.execute("INSERT INTO raw_country_a SELECT * FROM _raw_a")
    con.unregister("_raw_a")
    stored = con.execute("SELECT COUNT(*) FROM raw_country_a").fetchone()[0]
    con.close()
    return rows_read, stored


def insert_raw_country_b(ingest_id, source_file_name, loaded_at, file_bytes):
    """Insert Country B Excel as text. Skip titles and TOTAL. Do not fix amounts."""
    sheet_name = load_source_definitions()["CTB"]["sheet_name"]
    raw = pd.read_excel(
        BytesIO(file_bytes),
        sheet_name=sheet_name,
        header=None,
        dtype=str,
        keep_default_na=False,
    )
    header_idx = _country_b_header_index(raw.head(15))
    if header_idx is None:
        raise ValueError("Country B header row was not found.")
    columns = [str(value).strip() for value in raw.iloc[header_idx].tolist()]
    frame = raw.iloc[header_idx + 1 :].copy()
    frame.columns = columns
    rows_read = len(frame)
    id_col = "id_transaction"
    frame = frame[frame[id_col].astype(str).str.startswith("SN-")].copy()
    out = pd.DataFrame(
        {
            "ingest_id": ingest_id,
            "source_file_name": source_file_name,
            "loaded_at": loaded_at,
            "source_row_number": frame.index + 1,
        }
    )
    for column in REQUIRED_COLUMNS["CTB"]:
        out[column] = frame[column].astype(str)
    con = connect()
    con.register("_raw_b", out)
    con.execute("INSERT INTO raw_country_b SELECT * FROM _raw_b")
    con.unregister("_raw_b")
    stored = con.execute("SELECT COUNT(*) FROM raw_country_b").fetchone()[0]
    con.close()
    return rows_read, stored


def _json_text(value):
    if value is None or value == "":
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def insert_raw_country_c(ingest_id, source_file_name, loaded_at, file_bytes):
    """Insert Country C JSON parents. Keep subTransactions as JSON text."""
    key = load_source_definitions()["CTC"]["transaction_key"]
    payload = json.loads(file_bytes.decode("utf-8"))
    rows = payload[key]
    records = []
    for index, item in enumerate(rows, start=1):
        records.append(
            {
                "ingest_id": ingest_id,
                "source_file_name": source_file_name,
                "loaded_at": loaded_at,
                "source_row_number": index,
                "transactionId": "" if item.get("transactionId") is None else str(item.get("transactionId")),
                "postingDate": "" if item.get("postingDate") is None else str(item.get("postingDate")),
                "fiscalYear": "" if item.get("fiscalYear") is None else str(item.get("fiscalYear")),
                "ministryCode": "" if item.get("ministryCode") is None else str(item.get("ministryCode")),
                "ministryName": "" if item.get("ministryName") is None else str(item.get("ministryName")),
                "coaCode": "" if item.get("coaCode") is None else str(item.get("coaCode")),
                "description": "" if item.get("description") is None else str(item.get("description")),
                "supplier": "" if item.get("supplier") is None else str(item.get("supplier")),
                "amount": "" if item.get("amount") is None else str(item.get("amount")),
                "currency": "" if item.get("currency") is None else str(item.get("currency")),
                "subTransactions": _json_text(item.get("subTransactions")),
            }
        )
    out = pd.DataFrame.from_records(records)
    con = connect()
    con.register("_raw_c", out)
    con.execute("INSERT INTO raw_country_c SELECT * FROM _raw_c")
    con.unregister("_raw_c")
    stored = con.execute("SELECT COUNT(*) FROM raw_country_c").fetchone()[0]
    con.close()
    return len(rows), stored


def save_raw(country_code, source_file_name, file_bytes):
    table_name = replace_raw_for_country(country_code)
    ingest_id = new_ingest_id()
    loaded_at = datetime.now()
    rows_read, rows_stored = 0, 0
    if country_code == "CTA":
        rows_read, rows_stored = insert_raw_country_a(
            ingest_id, source_file_name, loaded_at, file_bytes
        )
    elif country_code == "CTB":
        rows_read, rows_stored = insert_raw_country_b(
            ingest_id, source_file_name, loaded_at, file_bytes
        )
    elif country_code == "CTC":
        rows_read, rows_stored = insert_raw_country_c(
            ingest_id, source_file_name, loaded_at, file_bytes
        )
    record_ingest_batch(
        ingest_id, country_code, source_file_name, loaded_at, rows_read, rows_stored
    )
    return ingest_id, table_name, rows_read, rows_stored
