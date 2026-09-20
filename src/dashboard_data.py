"""Read expenditure summaries for the analyst dashboard."""

from datetime import datetime
from io import StringIO

from src.db import connect, create_tables
from src.settings import load_source_definitions


def load_expenditure_frame():
    create_tables()
    con = connect()
    frame = con.execute(
        """
        SELECT
            e.*,
            b.loaded_at AS last_updated,
            b.source_file_name AS source_file_name
        FROM expenditure e
        LEFT JOIN ingest_batch b ON e.ingest_id = b.ingest_id
        """
    ).df()
    con.close()
    return attach_country_names(frame)


def country_name_map():
    definitions = load_source_definitions()
    return {
        code: values.get("country_name", code)
        for code, values in definitions.items()
    }


def attach_country_names(frame):
    """Add country_name next to country_code for analyst-friendly display."""
    if frame is None or frame.empty:
        return frame
    out = frame.copy()
    names = country_name_map()
    if "country_code" in out.columns:
        out["country_name"] = out["country_code"].map(names).fillna(out["country_code"])
        cols = list(out.columns)
        if "country_name" in cols:
            cols.remove("country_name")
            if "country_code" in cols:
                insert_at = cols.index("country_code") + 1
                cols.insert(insert_at, "country_name")
                out = out[cols]
    return out


def summary_counts(frame):
    if frame is None or frame.empty:
        return {
            "by_country": {},
            "mapped": 0,
            "unmapped": 0,
            "needs_review": 0,
            "quality_issues": 0,
            "total": 0,
        }
    by_country = frame["country_code"].value_counts().to_dict()
    method = frame["classification_method"].fillna("")
    mapped = int((method != "unmapped").sum())
    unmapped = int((method == "unmapped").sum())
    needs_review = int(frame["needs_review"].fillna(False).astype(bool).sum())
    quality = frame["quality_flags"].fillna("").astype(str)
    quality_issues = int((quality.str.len() > 0).sum())
    return {
        "by_country": by_country,
        "mapped": mapped,
        "unmapped": unmapped,
        "needs_review": needs_review,
        "quality_issues": quality_issues,
        "total": len(frame),
    }


def available_currencies(frame):
    if frame is None or frame.empty:
        return []
    return sorted(
        {
            str(value).strip()
            for value in frame["currency_original"].dropna().tolist()
            if str(value).strip()
        }
    )


def dataframe_to_csv_bytes(frame):
    """UTF-8 CSV bytes suitable for st.download_button (Excel-friendly)."""
    buffer = StringIO()
    if frame is None:
        buffer.write("")
    else:
        frame.to_csv(buffer, index=False)
    # UTF-8 BOM so Excel opens accents correctly.
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def csv_filename(prefix):
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{prefix}_{stamp}.csv"
