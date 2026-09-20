"""Classify expenditure rows to SHA and SRHR. CoA map is primary."""

from pathlib import Path

import pandas as pd

from src.db import PROJECT_ROOT

ACCOUNT_MAPPINGS_PATH = PROJECT_ROOT / "config" / "account_mappings.csv"
KEYWORD_RULES_PATH = PROJECT_ROOT / "config" / "keyword_rules.csv"


def load_account_mappings(path: Path | None = None):
    """Load country + account → SHA/SRHR maps from CSV."""
    csv_path = path or ACCOUNT_MAPPINGS_PATH
    frame = pd.read_csv(csv_path, dtype=str).fillna("")
    mapping = {}
    for row in frame.itertuples(index=False):
        key = (str(row.country_code).strip(), str(row.account_code).strip())
        mapping[key] = {
            "sha_code": str(row.sha_code).strip(),
            "srhr_code": str(row.srhr_code).strip(),
            "status": str(row.status).strip().lower(),
        }
    return mapping


def load_keyword_rules(path: Path | None = None):
    """Load description keyword → SHA/SRHR fallback rules."""
    csv_path = path or KEYWORD_RULES_PATH
    frame = pd.read_csv(csv_path, dtype=str).fillna("")
    rules = []
    for row in frame.itertuples(index=False):
        rules.append(
            {
                "pattern": str(row.pattern).strip().casefold(),
                "sha_code": str(row.sha_code).strip(),
                "srhr_code": str(row.srhr_code).strip(),
                "confidence": str(row.confidence).strip().lower() or "medium",
            }
        )
    return rules


def _normalise_text(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).casefold()


def classify_by_coa(country_code, account_code, mappings=None):
    """
    Primary classification: look up country + account code.

    Returns dict with sha_code, srhr_code, classification_method,
    confidence, needs_review, rationale — or None if no CoA map.
    """
    if mappings is None:
        mappings = load_account_mappings()
    key = (str(country_code).strip(), str(account_code).strip())
    hit = mappings.get(key)
    if hit is None:
        return None

    status = hit["status"] or "approved"
    sha_code = hit["sha_code"]
    srhr_code = hit["srhr_code"]

    if status == "review":
        confidence = "low"
        needs_review = True
        rationale = (
            f"Mapped from CoA {key[1]} (status=review; SHA may be incomplete)."
        )
    elif sha_code == "HC.7":
        confidence = "medium"
        needs_review = True
        rationale = (
            f"Mapped from CoA {key[1]} "
            "(HC.7 salaries/admin/support - kept for review)."
        )
    else:
        confidence = "high"
        needs_review = False
        rationale = f"Mapped from CoA {key[1]}."

    return {
        "sha_code": sha_code,
        "srhr_code": srhr_code,
        "classification_method": "coa_map",
        "confidence": confidence,
        "needs_review": needs_review,
        "rationale": rationale,
    }


def classify_by_keyword(description, rules=None):
    """Fallback only: match normalised description to keyword_rules.csv."""
    if rules is None:
        rules = load_keyword_rules()
    text = _normalise_text(description)
    if not text:
        return None
    for rule in rules:
        pattern = rule["pattern"]
        if pattern and pattern in text:
            return {
                "sha_code": rule["sha_code"],
                "srhr_code": rule["srhr_code"],
                "classification_method": "keyword",
                "confidence": rule["confidence"],
                "needs_review": True,
                "rationale": f"Keyword fallback matched '{rule['pattern']}'.",
            }
    return None


def unmapped_result(reason):
    return {
        "sha_code": "",
        "srhr_code": "",
        "classification_method": "unmapped",
        "confidence": "none",
        "needs_review": True,
        "rationale": reason,
    }


def has_suspicious_text(quality_flags):
    flags = "" if quality_flags is None else str(quality_flags)
    return "suspicious_text" in flags.split(";")


def classify_record(
    country_code,
    account_code,
    description,
    quality_flags="",
    mappings=None,
    rules=None,
):
    """
    Full classify path for one row.
    CoA map wins. Keywords only if no CoA map and text is not suspicious.
    """
    if mappings is None:
        mappings = load_account_mappings()
    if rules is None:
        rules = load_keyword_rules()

    coa = classify_by_coa(country_code, account_code, mappings=mappings)
    if coa is not None:
        return coa

    if has_suspicious_text(quality_flags):
        return unmapped_result(
            "No CoA map; keyword rules skipped because description is suspicious."
        )

    keyword = classify_by_keyword(description, rules=rules)
    if keyword is not None:
        return keyword

    return unmapped_result("No CoA map and no keyword match.")


def classify_expenditure_country(country_code):
    """Update SHA/SRHR fields on expenditure rows for one country."""
    from src.db import connect, create_tables

    create_tables()
    mappings = load_account_mappings()
    rules = load_keyword_rules()
    con = connect()
    rows = con.execute(
        """
        SELECT expenditure_id, country_code, account_code,
               account_description, quality_flags
        FROM expenditure
        WHERE country_code = ?
        """,
        [country_code],
    ).fetchall()

    method_counts = {"coa_map": 0, "keyword": 0, "unmapped": 0}
    for expenditure_id, country, account_code, description, quality_flags in rows:
        result = classify_record(
            country,
            account_code,
            description,
            quality_flags=quality_flags or "",
            mappings=mappings,
            rules=rules,
        )
        method_counts[result["classification_method"]] = (
            method_counts.get(result["classification_method"], 0) + 1
        )
        con.execute(
            """
            UPDATE expenditure
            SET sha_code = ?,
                srhr_code = ?,
                classification_method = ?,
                confidence = ?,
                needs_review = ?,
                rationale = ?
            WHERE expenditure_id = ?
            """,
            [
                result["sha_code"],
                result["srhr_code"],
                result["classification_method"],
                result["confidence"],
                result["needs_review"],
                result["rationale"],
                expenditure_id,
            ],
        )
    con.close()
    return {"updated": len(rows), "methods": method_counts}
