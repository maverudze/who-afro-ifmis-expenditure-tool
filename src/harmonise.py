"""Map country raw tables into one common expenditure shape."""

from uuid import uuid4

import pandas as pd

from src.db import connect, create_tables
from src.quality import duplicate_txn_ids, flag_record, parse_amount, parse_date
from src.settings import load_source_definitions

COMMON_COLUMNS = [
    "expenditure_id",
    "ingest_id",
    "country_code",
    "source_txn_id",
    "txn_date",
    "fiscal_year",
    "ministry_code",
    "ministry_name",
    "account_code",
    "account_description",
    "vendor",
    "amount_original",
    "currency_original",
    "sha_code",
    "srhr_code",
    "classification_method",
    "confidence",
    "needs_review",
    "rationale",
    "quality_flags",
    "raw_table",
    "raw_row_id",
]


def _text(value):
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalise_description(value):
    text = _text(value)
    if not text:
        return ""
    return " ".join(text.split()).casefold()


def _fiscal_year_from_date(txn_date):
    if txn_date is None:
        return ""
    # FY runs 1 Jul – 30 Jun
    if txn_date.month >= 7:
        return f"FY{txn_date.year}/{str(txn_date.year + 1)[2:]}"
    return f"FY{txn_date.year - 1}/{str(txn_date.year)[2:]}"


def _empty_classification():
    return {
        "sha_code": "",
        "srhr_code": "",
        "classification_method": "",
        "confidence": "",
        "needs_review": None,
        "rationale": "",
    }


def _base_row(
    *,
    ingest_id,
    country_code,
    source_txn_id,
    txn_date,
    fiscal_year,
    ministry_code,
    ministry_name,
    account_code,
    account_description,
    vendor,
    amount_original,
    currency_original,
    quality_flags,
    raw_table,
    raw_row_id,
):
    row = {
        "expenditure_id": str(uuid4()),
        "ingest_id": ingest_id,
        "country_code": country_code,
        "source_txn_id": _text(source_txn_id),
        "txn_date": txn_date,
        "fiscal_year": fiscal_year or "",
        "ministry_code": _text(ministry_code),
        "ministry_name": _text(ministry_name),
        "account_code": _text(account_code),
        "account_description": _normalise_description(account_description),
        "vendor": _text(vendor),
        "amount_original": amount_original,
        "currency_original": _text(currency_original),
        "quality_flags": quality_flags or "",
        "raw_table": raw_table,
        "raw_row_id": int(raw_row_id) if raw_row_id is not None else None,
    }
    row.update(_empty_classification())
    return row


def map_country_a(rows, date_format, primary_currency):
    """Map raw_country_a rows to common fields. Keep all ministries."""
    duplicate_ids = duplicate_txn_ids([row[5] for row in rows])  # TXN_ID
    mapped = []
    for row in rows:
        (
            ingest_id,
            _source_file_name,
            _loaded_at,
            source_row_number,
            txn_id,
            date_raw,
            ministry_code,
            ministry_name,
            account_code,
            description,
            vendor,
            amount_raw,
            _payment_method,
        ) = row
        amount, _ = parse_amount(amount_raw)
        txn_date, _ = parse_date(date_raw, date_format)
        quality_flags = flag_record(
            source_txn_id=txn_id,
            date_raw=date_raw,
            date_format=date_format,
            description_raw=description,
            amount_raw=amount_raw,
            currency_raw=primary_currency,
            primary_currency=primary_currency,
            duplicate_ids=duplicate_ids,
        )
        mapped.append(
            _base_row(
                ingest_id=ingest_id,
                country_code="CTA",
                source_txn_id=txn_id,
                txn_date=txn_date,
                fiscal_year=_fiscal_year_from_date(txn_date),
                ministry_code=ministry_code,
                ministry_name=ministry_name,
                account_code=account_code,
                account_description=description,
                vendor=vendor,
                amount_original=amount,
                currency_original=primary_currency,
                quality_flags=quality_flags,
                raw_table="raw_country_a",
                raw_row_id=source_row_number,
            )
        )
    return mapped


def map_country_b(rows, date_format, primary_currency):
    """Map raw_country_b rows to common fields. Keep French names and all ministries."""
    duplicate_ids = duplicate_txn_ids([row[5] for row in rows])  # id_transaction
    mapped = []
    for row in rows:
        (
            ingest_id,
            _source_file_name,
            _loaded_at,
            source_row_number,
            id_transaction,
            date_ecriture,
            ministere_code,
            ministere_nom,
            code_budgetaire,
            libelle,
            tiers,
            montant_xof,
        ) = row
        amount, _ = parse_amount(montant_xof)
        txn_date, _ = parse_date(date_ecriture, date_format)
        quality_flags = flag_record(
            source_txn_id=id_transaction,
            date_raw=date_ecriture,
            date_format=date_format,
            description_raw=libelle,
            amount_raw=montant_xof,
            currency_raw=primary_currency,
            primary_currency=primary_currency,
            duplicate_ids=duplicate_ids,
        )
        mapped.append(
            _base_row(
                ingest_id=ingest_id,
                country_code="CTB",
                source_txn_id=id_transaction,
                txn_date=txn_date,
                fiscal_year=_fiscal_year_from_date(txn_date),
                ministry_code=ministere_code,
                ministry_name=ministere_nom,
                account_code=code_budgetaire,
                account_description=libelle,
                vendor=tiers,
                amount_original=amount,
                currency_original=primary_currency,
                quality_flags=quality_flags,
                raw_table="raw_country_b",
                raw_row_id=source_row_number,
            )
        )
    return mapped


def map_country_c(rows, date_format, primary_currency):
    """Map raw_country_c parent rows only. Do not add subTransactions amounts."""
    duplicate_ids = duplicate_txn_ids([row[5] for row in rows])  # transactionId
    mapped = []
    for row in rows:
        (
            ingest_id,
            _source_file_name,
            _loaded_at,
            source_row_number,
            transaction_id,
            posting_date,
            fiscal_year,
            ministry_code,
            ministry_name,
            coa_code,
            description,
            supplier,
            amount_raw,
            currency_raw,
            _sub_transactions,
        ) = row
        amount, _ = parse_amount(amount_raw)
        txn_date, _ = parse_date(posting_date, date_format)
        currency = _text(currency_raw) or primary_currency
        quality_flags = flag_record(
            source_txn_id=transaction_id,
            date_raw=posting_date,
            date_format=date_format,
            description_raw=description,
            amount_raw=amount_raw,
            currency_raw=currency,
            primary_currency=primary_currency,
            duplicate_ids=duplicate_ids,
        )
        mapped.append(
            _base_row(
                ingest_id=ingest_id,
                country_code="CTC",
                source_txn_id=transaction_id,
                txn_date=txn_date,
                fiscal_year=_text(fiscal_year) or _fiscal_year_from_date(txn_date),
                ministry_code=ministry_code,
                ministry_name=ministry_name,
                account_code=coa_code,
                account_description=description,
                vendor=supplier,
                amount_original=amount,
                currency_original=currency,
                quality_flags=quality_flags,
                raw_table="raw_country_c",
                raw_row_id=source_row_number,
            )
        )
    return mapped


def map_raw_country(country_code):
    """Read one country's raw table and return common-shape rows (not written yet)."""
    definitions = load_source_definitions()
    definition = definitions[country_code]
    date_format = definition["date_format"]
    primary_currency = definition["currency"]
    con = connect()
    if country_code == "CTA":
        rows = con.execute("SELECT * FROM raw_country_a").fetchall()
        mapped = map_country_a(rows, date_format, primary_currency)
    elif country_code == "CTB":
        rows = con.execute("SELECT * FROM raw_country_b").fetchall()
        mapped = map_country_b(rows, date_format, primary_currency)
    elif country_code == "CTC":
        rows = con.execute("SELECT * FROM raw_country_c").fetchall()
        mapped = map_country_c(rows, date_format, primary_currency)
    else:
        con.close()
        raise ValueError(f"Unknown country code: {country_code}")
    con.close()
    return mapped


def replace_expenditure_for_country(country_code):
    """Delete existing processed rows for this country only."""
    create_tables()
    con = connect()
    con.execute("DELETE FROM expenditure WHERE country_code = ?", [country_code])
    con.close()


def write_expenditure_rows(mapped_rows):
    """Insert mapped rows into expenditure. No FX conversion. SHA/SRHR stay empty."""
    if not mapped_rows:
        return 0
    create_tables()
    frame = pd.DataFrame(mapped_rows)[COMMON_COLUMNS]
    con = connect()
    con.register("_exp_tmp", frame)
    con.execute("INSERT INTO expenditure SELECT * FROM _exp_tmp")
    con.unregister("_exp_tmp")
    stored = len(mapped_rows)
    con.close()
    return stored


def save_harmonised_country(country_code):
    """
    Replace this country's expenditure rows with freshly mapped raw rows.
    Keeps quality_flags; leaves classification fields empty.
    """
    replace_expenditure_for_country(country_code)
    mapped = map_raw_country(country_code)
    stored = write_expenditure_rows(mapped)
    return stored
