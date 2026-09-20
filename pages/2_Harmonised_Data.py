"""Harmonised expenditure list — combined data + CSV download."""

import streamlit as st

from src import dashboard_data

st.title("Expenditure list")
st.write(
    "Combined / harmonised expenditure (all countries in one structure) "
    "after ingest, quality flags, and SHA/SRHR classification."
)
st.caption(
    "Parent section: **Harmonised Data**. For audit of one row, open **Row detail / trace**."
)

frame = dashboard_data.load_expenditure_frame()
if frame is None or frame.empty:
    st.warning(
        "No processed expenditure yet. Import and Process Data for Countries A, B and C first."
    )
    st.stop()

currencies = dashboard_data.available_currencies(frame)
countries = ["(all)"] + sorted(frame["country_code"].dropna().unique().tolist())
sha_codes = ["(all)"] + sorted(
    {str(v) for v in frame["sha_code"].fillna("").tolist()}
)
srhr_codes = ["(all)"] + sorted(
    {str(v) for v in frame["srhr_code"].fillna("").tolist()}
)
confidences = ["(all)"] + sorted(
    {str(v) for v in frame["confidence"].fillna("").tolist() if str(v)}
)
quality_options = ["(all)", "Has any quality flag"] + sorted(
    {
        flag
        for flags in frame["quality_flags"].fillna("").tolist()
        for flag in str(flags).split(";")
        if flag
    }
)

DEFAULT_FILTERS = {
    "view_mode": "All",
    "search": "",
    "country": "(all)",
    "currency": "(all)",
    "sha": "(all)",
    "srhr": "(all)",
    "confidence": "(all)",
    "quality": "(all)",
}
if "list_applied" not in st.session_state:
    st.session_state["list_applied"] = DEFAULT_FILTERS.copy()
if "list_filter_version" not in st.session_state:
    st.session_state["list_filter_version"] = 0

version = st.session_state["list_filter_version"]

row = st.columns([2.4, 1.0, 0.9, 0.8, 0.8, 0.9, 1.1, 0.7, 0.7], gap="small")
with row[0]:
    draft_search = st.text_input(
        "Search",
        key=f"exp_search_{version}",
        placeholder="description / txn id",
    )
with row[1]:
    draft_country = st.selectbox(
        "Country",
        countries,
        key=f"exp_country_{version}",
    )
with row[2]:
    draft_currency = st.selectbox(
        "Currency",
        ["(all)"] + currencies,
        key=f"exp_currency_{version}",
    )
with row[3]:
    draft_sha = st.selectbox(
        "SHA",
        sha_codes,
        key=f"exp_sha_{version}",
    )
with row[4]:
    draft_srhr = st.selectbox(
        "SRHR",
        srhr_codes,
        key=f"exp_srhr_{version}",
    )
with row[5]:
    draft_confidence = st.selectbox(
        "Confidence",
        confidences,
        key=f"exp_confidence_{version}",
    )
with row[6]:
    draft_quality = st.selectbox(
        "Quality",
        quality_options,
        key=f"exp_quality_{version}",
    )
with row[7]:
    st.write("")
    apply_clicked = st.button("Apply", use_container_width=True, type="primary")
with row[8]:
    st.write("")
    clear_clicked = st.button("Clear", use_container_width=True)

view_mode = st.radio(
    "View",
    ["All", "Needs review only"],
    horizontal=True,
    key=f"exp_view_{version}",
)

if apply_clicked:
    st.session_state["list_applied"] = {
        "view_mode": view_mode,
        "search": draft_search or "",
        "country": draft_country,
        "currency": draft_currency,
        "sha": draft_sha,
        "srhr": draft_srhr,
        "confidence": draft_confidence,
        "quality": draft_quality,
    }
    st.rerun()

if clear_clicked:
    st.session_state["list_applied"] = DEFAULT_FILTERS.copy()
    st.session_state["list_filter_version"] = version + 1
    st.rerun()

applied = st.session_state["list_applied"]
filtered = frame.copy()
if applied["view_mode"] == "Needs review only":
    filtered = filtered[filtered["needs_review"].fillna(False).astype(bool)]
if applied["country"] != "(all)":
    filtered = filtered[filtered["country_code"] == applied["country"]]
if applied["currency"] != "(all)":
    filtered = filtered[filtered["currency_original"] == applied["currency"]]
if applied["sha"] != "(all)":
    filtered = filtered[filtered["sha_code"].fillna("") == applied["sha"]]
if applied["srhr"] != "(all)":
    filtered = filtered[filtered["srhr_code"].fillna("") == applied["srhr"]]
if applied["confidence"] != "(all)":
    filtered = filtered[filtered["confidence"].fillna("") == applied["confidence"]]
if applied["quality"] == "Has any quality flag":
    filtered = filtered[filtered["quality_flags"].fillna("").astype(str).str.len() > 0]
elif applied["quality"] != "(all)":
    filtered = filtered[
        filtered["quality_flags"]
        .fillna("")
        .astype(str)
        .str.contains(applied["quality"], regex=False)
    ]
if str(applied["search"]).strip():
    term = str(applied["search"]).strip().casefold()
    desc = filtered["account_description"].fillna("").astype(str).str.casefold()
    txn = filtered["source_txn_id"].fillna("").astype(str).str.casefold()
    filtered = filtered[
        desc.str.contains(term, regex=False) | txn.str.contains(term, regex=False)
    ]

display_cols = [
    "country_code",
    "country_name",
    "txn_date",
    "ministry_code",
    "ministry_name",
    "account_code",
    "account_description",
    "amount_original",
    "currency_original",
    "sha_code",
    "srhr_code",
    "confidence",
    "needs_review",
    "quality_flags",
    "source_txn_id",
    "last_updated",
]

filters_active = applied != DEFAULT_FILTERS
st.write(f"**Showing {len(filtered):,} of {len(frame):,} rows**")

st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)
st.caption(
    "Tip: you can also use the **download icon** on the top-right of the table "
    "(Streamlit toolbar) — it downloads the same rows you see on screen."
)

if filtered.empty:
    st.warning("Nothing to download — clear or change filters so at least one row is shown.")
else:
    file_prefix = (
        "expenditure_filtered" if filters_active else "expenditure_all"
    )
    label = (
        f"Download CSV ({len(filtered):,} filtered rows)"
        if filters_active
        else f"Download CSV ({len(filtered):,} rows — full list)"
    )
    st.download_button(
        label=label,
        data=dashboard_data.dataframe_to_csv_bytes(filtered[display_cols]),
        file_name=dashboard_data.csv_filename(file_prefix),
        mime="text/csv",
        key="download_current_csv",
    )
