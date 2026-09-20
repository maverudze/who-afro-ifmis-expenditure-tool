"""Parse raw amount text and return quality flags. Does not change raw tables."""

import re
from collections import Counter
from datetime import date, datetime

FY_START = date(2023, 7, 1)
FY_END = date(2024, 6, 30)


def parse_amount(raw_value):
    """
    Return (number_or_none, flags).

    Flags: missing_amount, unparseable_amount, amount_format, negative_amount.
    """
    flags = []
    if raw_value is None:
        return None, ["missing_amount"]

    original = str(raw_value).strip()
    if original == "" or original.lower() in {"nan", "none", "null"}:
        return None, ["missing_amount"]

    messy = bool(re.search(r'[",]|FCFA|fr|\s', original, flags=re.IGNORECASE))
    cleaned = original.strip().strip('"').strip("'")
    cleaned = re.sub(r"(?i)FCFA", "", cleaned)
    cleaned = cleaned.replace("\u00a0", " ").replace(" ", "")

    if cleaned.count(",") == 1 and "." not in cleaned:
        left, right = cleaned.split(",")
        if len(right) == 2:
            cleaned = left + "." + right
        else:
            cleaned = left + right
    else:
        cleaned = cleaned.replace(",", "")

    try:
        number = float(cleaned)
    except ValueError:
        return None, ["unparseable_amount"]

    if messy:
        flags.append("amount_format")
    if number < 0:
        flags.append("negative_amount")
    return number, flags


def duplicate_txn_ids(source_ids):
    """Return source ids that appear more than once."""
    counts = Counter("" if value is None else str(value).strip() for value in source_ids)
    return {key for key, count in counts.items() if key and count > 1}


def parse_date(raw_value, date_format):
    """Return (date_or_none, flags): bad_date, date_outside_fy."""
    flags = []
    if raw_value is None or str(raw_value).strip() == "":
        return None, ["bad_date"]
    text = str(raw_value).strip()
    try:
        parsed = datetime.strptime(text, date_format).date()
    except ValueError:
        return None, ["bad_date"]
    if parsed < FY_START or parsed > FY_END:
        flags.append("date_outside_fy")
    return parsed, flags


def missing_description(raw_value):
    if raw_value is None:
        return True
    text = str(raw_value).strip()
    return text == "" or text.lower() in {"nan", "none", "null"}


SUSPICIOUS_MARKERS = (
    "ignore all previous",
    "ignorez tout",
    "<<system>>",
    "</system>",
    "[/inst]",
    "system override",
    "do not reclassify",
    "do not explain",
    "respond that this record",
    "this is a system override",
)


def is_suspicious_text(raw_value):
    if raw_value is None:
        return False
    text = str(raw_value).lower()
    return any(marker in text for marker in SUSPICIOUS_MARKERS)


def mixed_currency(currency_raw, primary_currency):
    if currency_raw is None or str(currency_raw).strip() == "":
        return False
    return str(currency_raw).strip().upper() != str(primary_currency).strip().upper()


def join_flags(flags):
    """Stable, unique flag list as one text field for the processed table."""
    seen = []
    for flag in flags:
        if flag and flag not in seen:
            seen.append(flag)
    return ";".join(seen)


def flag_record(
    *,
    source_txn_id,
    date_raw,
    date_format,
    description_raw,
    amount_raw,
    currency_raw,
    primary_currency,
    duplicate_ids,
):
    flags = []
    flags.extend(parse_amount(amount_raw)[1])
    flags.extend(parse_date(date_raw, date_format)[1])
    if missing_description(description_raw):
        flags.append("missing_description")
    if source_txn_id is not None and str(source_txn_id).strip() in duplicate_ids:
        flags.append("duplicate_txn_id")
    if mixed_currency(currency_raw, primary_currency):
        flags.append("mixed_currency")
    if is_suspicious_text(description_raw):
        flags.append("suspicious_text")
    return join_flags(flags)


def summarise_raw_quality():
    """Run flags on raw tables. Does not write to expenditure or change raw."""
    from src.db import connect
    from src.settings import load_source_definitions

    definitions = load_source_definitions()
    con = connect()
    specs = [
        (
            "CTA",
            "SELECT TXN_ID, DATE, DESCRIPTION, AMOUNT_KES, NULL FROM raw_country_a",
        ),
        (
            "CTB",
            "SELECT id_transaction, date_ecriture, libelle, montant_XOF, NULL FROM raw_country_b",
        ),
        (
            "CTC",
            "SELECT transactionId, postingDate, description, amount, currency FROM raw_country_c",
        ),
    ]
    summary = {}
    raw_counts = {}
    for country_code, sql in specs:
        rows = con.execute(sql).fetchall()
        raw_counts[country_code] = len(rows)
        ids = [row[0] for row in rows]
        duplicates = duplicate_txn_ids(ids)
        date_format = definitions[country_code]["date_format"]
        primary = definitions[country_code]["currency"]
        flag_counts = Counter()
        for source_id, date_raw, description, amount_raw, currency_raw in rows:
            text = flag_record(
                source_txn_id=source_id,
                date_raw=date_raw,
                date_format=date_format,
                description_raw=description,
                amount_raw=amount_raw,
                currency_raw=currency_raw,
                primary_currency=primary,
                duplicate_ids=duplicates,
            )
            if text:
                for flag in text.split(";"):
                    flag_counts[flag] += 1
        summary[country_code] = dict(flag_counts)
    expenditure_rows = con.execute("SELECT COUNT(*) FROM expenditure").fetchone()[0]
    con.close()
    return {
        "raw_counts": raw_counts,
        "flags": summary,
        "expenditure_rows": expenditure_rows,
    }


def summarise_extract_quality(country_code, file_bytes, definition):
    """
    Scan an uploaded extract (before DB write) and return row counts + quality flag counts.
    Used for the Import summary / confirm step.
    """
    from io import BytesIO

    import pandas as pd

    from src.validate_import import _country_b_header_index

    date_format = definition["date_format"]
    primary = definition["currency"]
    rows = []

    if country_code == "CTA":
        frame = pd.read_csv(BytesIO(file_bytes), dtype=str, keep_default_na=False)
        for _, row in frame.iterrows():
            rows.append(
                (
                    row.get("TXN_ID"),
                    row.get("DATE"),
                    row.get("DESCRIPTION"),
                    row.get("AMOUNT_KES"),
                    None,
                )
            )
    elif country_code == "CTB":
        sheet_name = definition["sheet_name"]
        raw = pd.read_excel(
            BytesIO(file_bytes),
            sheet_name=sheet_name,
            header=None,
            dtype=str,
            keep_default_na=False,
            engine="openpyxl",
        )
        header_idx = _country_b_header_index(raw.head(15))
        frame = pd.read_excel(
            BytesIO(file_bytes),
            sheet_name=sheet_name,
            header=header_idx,
            dtype=str,
            keep_default_na=False,
            engine="openpyxl",
        )
        if "id_transaction" in frame.columns:
            frame = frame[frame["id_transaction"].astype(str).str.startswith("SN-")]
        for _, row in frame.iterrows():
            rows.append(
                (
                    row.get("id_transaction"),
                    row.get("date_ecriture"),
                    row.get("libelle"),
                    row.get("montant_XOF"),
                    None,
                )
            )
    elif country_code == "CTC":
        import json

        key = definition["transaction_key"]
        payload = json.loads(file_bytes.decode("utf-8"))
        for item in payload[key]:
            rows.append(
                (
                    item.get("transactionId"),
                    item.get("postingDate"),
                    item.get("description"),
                    item.get("amount"),
                    item.get("currency"),
                )
            )
    else:
        raise ValueError(f"Unknown country_code: {country_code}")

    ids = [row[0] for row in rows]
    duplicates = duplicate_txn_ids(ids)
    flag_counts = Counter()
    rows_with_any_flag = 0
    for source_id, date_raw, description, amount_raw, currency_raw in rows:
        text = flag_record(
            source_txn_id=source_id,
            date_raw=date_raw,
            date_format=date_format,
            description_raw=description,
            amount_raw=amount_raw,
            currency_raw=currency_raw,
            primary_currency=primary,
            duplicate_ids=duplicates,
        )
        if text:
            rows_with_any_flag += 1
            for flag in text.split(";"):
                flag_counts[flag] += 1

    return {
        "rows_read": len(rows),
        "rows_with_any_flag": rows_with_any_flag,
        "duplicate_txn_ids": len(duplicates),
        "flag_counts": dict(flag_counts),
    }
