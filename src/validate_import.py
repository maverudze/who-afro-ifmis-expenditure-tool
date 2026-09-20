"""Check that an uploaded extract matches the expected country structure."""

import json
from io import BytesIO

import pandas as pd

REQUIRED_COLUMNS = {
    "CTA": [
        "TXN_ID",
        "DATE",
        "MINISTRY_CODE",
        "MINISTRY_NAME",
        "ACCOUNT_CODE",
        "DESCRIPTION",
        "VENDOR",
        "AMOUNT_KES",
        "PAYMENT_METHOD",
    ],
    "CTB": [
        "id_transaction",
        "date_ecriture",
        "ministere_code",
        "ministere_nom",
        "code_budgetaire",
        "libelle",
        "tiers",
        "montant_XOF",
    ],
}


def _missing(required, actual):
    return [name for name in required if name not in actual]


def _country_b_header_index(preview):
    for idx, row in preview.iterrows():
        values = [str(value).strip() for value in row.tolist()]
        if not _missing(REQUIRED_COLUMNS["CTB"], values):
            return idx
    return None


def validate_extract(country_code, file_bytes, definition):
    file_type = definition["file_type"]

    if country_code == "CTA":
        if file_type != "csv":
            return False, "Country A file must be a CSV."
        try:
            frame = pd.read_csv(BytesIO(file_bytes), nrows=0)
        except Exception as exc:
            return False, f"Could not read CSV: {exc}"
        missing = _missing(REQUIRED_COLUMNS["CTA"], list(frame.columns))
        if missing:
            return False, "Country A CSV is missing columns: " + ", ".join(missing)
        return True, "Country A CSV structure is valid."

    if country_code == "CTB":
        if file_type != "xlsx":
            return False, "Country B file must be an Excel workbook."
        try:
            workbook = pd.ExcelFile(BytesIO(file_bytes), engine="openpyxl")
        except Exception as exc:
            return False, f"Could not read Excel: {exc}"
        sheet_name = definition["sheet_name"]
        if sheet_name not in workbook.sheet_names:
            return False, f"Excel must contain a sheet named '{sheet_name}'."
        try:
            preview = pd.read_excel(
                workbook,
                sheet_name=sheet_name,
                header=None,
                nrows=15,
                engine="openpyxl",
            )
        except Exception as exc:
            return False, f"Could not read sheet '{sheet_name}': {exc}"
        header_idx = _country_b_header_index(preview)
        if header_idx is None:
            return False, (
                f"Sheet '{sheet_name}' does not contain the Country B column names "
                "(id_transaction, date_ecriture, ...)."
            )
        excel_row = header_idx + 1
        return True, (
            f"Country B Excel structure is valid "
            f"(sheet '{sheet_name}', header on row {excel_row})."
        )

    if country_code == "CTC":
        if file_type != "json":
            return False, "Country C file must be JSON."
        try:
            payload = json.loads(file_bytes.decode("utf-8"))
        except Exception as exc:
            return False, f"Could not read JSON: {exc}"
        if not isinstance(payload, dict):
            return False, "Country C JSON must be an object with a transactions list."
        key = definition["transaction_key"]
        if key not in payload:
            return False, f"JSON must contain a '{key}' list."
        if not isinstance(payload[key], list):
            return False, f"'{key}' must be a list."
        return True, f"Country C JSON structure is valid ('{key}' list found)."

    return False, f"Unknown country code: {country_code}."


def load_preview(country_code, file_bytes, definition, n=8):
    """Return (preview_dataframe, row_count) for a valid extract."""
    buffer = BytesIO(file_bytes)

    if country_code == "CTA":
        frame = pd.read_csv(buffer)
        return frame.head(n), len(frame)

    if country_code == "CTB":
        sheet_name = definition["sheet_name"]
        raw = pd.read_excel(buffer, sheet_name=sheet_name, header=None, engine="openpyxl")
        header_idx = _country_b_header_index(raw.head(15))
        frame = pd.read_excel(
            BytesIO(file_bytes),
            sheet_name=sheet_name,
            header=header_idx,
            engine="openpyxl",
        )
        id_col = "id_transaction"
        if id_col in frame.columns:
            frame = frame[frame[id_col].astype(str).str.startswith("SN-")]
        return frame.head(n), len(frame)

    key = definition["transaction_key"]
    payload = json.loads(file_bytes.decode("utf-8"))
    rows = payload[key]
    preview_rows = []
    for item in rows[:n]:
        preview_rows.append(
            {
                "transactionId": item.get("transactionId"),
                "postingDate": item.get("postingDate"),
                "ministryCode": item.get("ministryCode"),
                "coaCode": item.get("coaCode"),
                "description": item.get("description"),
                "amount": item.get("amount"),
                "currency": item.get("currency"),
            }
        )
    return pd.DataFrame(preview_rows), len(rows)
