"""Row detail / trace — single processed record back to raw source."""

import pandas as pd
import streamlit as st

from src import dashboard_data
from src import trace_data

st.title("Row detail / trace")
st.write(
    "Audit one harmonised record: classification rationale and the matching raw source. "
    "The full combined table is under **Expenditure list**."
)

frame = dashboard_data.load_expenditure_frame()
if frame is None or frame.empty:
    st.warning(
        "No processed expenditure yet. Import and Process Data for Countries A, B and C first."
    )
    st.stop()

currencies = dashboard_data.available_currencies(frame)
MAX_PICK_OPTIONS = 50

DEFAULT_TRACE_FILTERS = {
    "view_mode": "All",
    "country": "(all)",
    "currency": "(all)",
    "search": "",
}
if "trace_applied" not in st.session_state:
    st.session_state["trace_applied"] = DEFAULT_TRACE_FILTERS.copy()
if "trace_filter_version" not in st.session_state:
    st.session_state["trace_filter_version"] = 0

version = st.session_state["trace_filter_version"]

view_mode = st.radio(
    "View",
    ["All", "Needs review only"],
    horizontal=True,
    key=f"trace_view_{version}",
)

countries = ["(all)"] + sorted(frame["country_code"].dropna().unique().tolist())
row = st.columns([1.0, 1.0, 2.4, 0.7, 0.7], gap="small")
with row[0]:
    draft_country = st.selectbox(
        "Country", countries, key=f"trace_country_{version}"
    )
with row[1]:
    draft_currency = st.selectbox(
        "Currency",
        ["(all)"] + currencies,
        key=f"trace_currency_{version}",
    )
with row[2]:
    draft_search = st.text_input(
        "Search txn id / account code / description",
        key=f"trace_search_{version}",
        placeholder="e.g. KE-2400172 or 2211407 or cleaning",
    )
with row[3]:
    st.write("")
    apply_clicked = st.button(
        "Apply", use_container_width=True, type="primary", key="trace_apply"
    )
with row[4]:
    st.write("")
    clear_clicked = st.button("Clear", use_container_width=True, key="trace_clear")

if apply_clicked:
    st.session_state["trace_applied"] = {
        "view_mode": view_mode,
        "country": draft_country,
        "currency": draft_currency,
        "search": draft_search or "",
    }
    st.rerun()

if clear_clicked:
    st.session_state["trace_applied"] = DEFAULT_TRACE_FILTERS.copy()
    st.session_state["trace_filter_version"] = version + 1
    st.rerun()

applied = st.session_state["trace_applied"]
filtered = frame.copy()
if applied["view_mode"] == "Needs review only":
    filtered = filtered[filtered["needs_review"].fillna(False).astype(bool)]
if applied["country"] != "(all)":
    filtered = filtered[filtered["country_code"] == applied["country"]]
if applied["currency"] != "(all)":
    filtered = filtered[filtered["currency_original"] == applied["currency"]]
if str(applied["search"]).strip():
    term = str(applied["search"]).strip().casefold()
    desc = filtered["account_description"].fillna("").astype(str).str.casefold()
    txn = filtered["source_txn_id"].fillna("").astype(str).str.casefold()
    account = filtered["account_code"].fillna("").astype(str).str.casefold()
    filtered = filtered[
        desc.str.contains(term, regex=False)
        | txn.str.contains(term, regex=False)
        | account.str.contains(term, regex=False)
    ]

st.caption(
    f"{len(filtered):,} records match the **applied** filter / search. "
    "Change fields then click **Apply**."
)

if filtered.empty:
    st.warning("No rows match — click Clear or change search and Apply again.")
    st.stop()

if len(filtered) > MAX_PICK_OPTIONS:
    st.warning(
        f"Not stuck / not loading — {len(filtered):,} rows is too many for the dropdown. "
        f"Enter a search (txn id / account / description), click **Apply**, "
        f"until you have **{MAX_PICK_OPTIONS} or fewer** matches."
    )
    st.markdown(
        """
**What to do**
1. Set Country if needed (e.g. CTA).
2. In **Search**, type something unique, for example:
   - a txn id: `KE-2400000`
   - an account code: `2211407`
   - part of the description: `cleaning` or `hiv`
3. Click **Apply**.
4. When matches ≤ 50, select one row to see the full trace.
        """
    )
    st.stop()

st.success(
    f"{len(filtered)} match(es) — select one row below to open the trace."
)
pick_frame = filtered.copy()
pick_frame["_label"] = (
    pick_frame["country_code"].astype(str)
    + " ("
    + pick_frame["country_name"].fillna("").astype(str)
    + ") | "
    + pick_frame["source_txn_id"].fillna("").astype(str)
    + " | "
    + pick_frame["account_code"].fillna("").astype(str)
    + " | "
    + pick_frame["account_description"].fillna("").astype(str).str.slice(0, 40)
    + " | "
    + pick_frame["amount_original"].map(
        lambda v: "" if pd.isna(v) else f"{v:,.2f}"
    )
    + " "
    + pick_frame["currency_original"].fillna("").astype(str)
)
selected_id = st.selectbox(
    "Select a processed row to trace",
    pick_frame["expenditure_id"].tolist(),
    format_func=lambda eid: pick_frame.loc[
        pick_frame["expenditure_id"] == eid, "_label"
    ].iloc[0],
)

trace = trace_data.load_trace(selected_id)
if trace is None:
    st.error(
        "No expenditure row found for that id. "
        "Re-run Process Data on Import if the database was cleared."
    )
    st.stop()

exp = trace["expenditure"]
batch = trace["ingest_batch"]
raw = trace["raw_row"]
country_names = dashboard_data.country_name_map()
country_label = country_names.get(
    exp.get("country_code"), exp.get("country_code") or "—"
)

st.write("**Harmonised / processed**")
h1, h2, h3, h4, h5 = st.columns(5)
h1.metric("Country", f"{exp.get('country_code') or '—'} — {country_label}")
h2.metric("Source txn id", exp.get("source_txn_id") or "—")
h3.metric(
    "Amount",
    (
        "—"
        if exp.get("amount_original") is None or pd.isna(exp.get("amount_original"))
        else f"{exp['amount_original']:,.2f}"
    ),
)
h4.metric("Currency", exp.get("currency_original") or "—")
last_updated = None
if batch is not None:
    last_updated = batch.get("loaded_at")
h5.metric(
    "Last updated",
    str(last_updated) if last_updated is not None else "—",
)
st.caption(
    "Last updated = when this country’s extract was last imported "
    "(re-import replaces that country and refreshes the timestamp)."
)
st.dataframe(
    pd.DataFrame(
        [
            {
                "txn_date": exp.get("txn_date"),
                "fiscal_year": exp.get("fiscal_year"),
                "ministry_code": exp.get("ministry_code"),
                "ministry_name": exp.get("ministry_name"),
                "account_code": exp.get("account_code"),
                "account_description": exp.get("account_description"),
                "vendor": exp.get("vendor"),
                "last_updated": last_updated,
            }
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

st.write("**Classification**")
c1, c2, c3, c4 = st.columns(4)
c1.metric("SHA", exp.get("sha_code") or "(blank)")
c2.metric("SRHR", exp.get("srhr_code") or "(blank)")
c3.metric("Method", exp.get("classification_method") or "—")
c4.metric("Confidence", exp.get("confidence") or "—")
st.write(f"Needs review: `{bool(exp.get('needs_review'))}`")
st.write(f"Rationale: {exp.get('rationale') or '—'}")
st.write(f"Quality flags: `{exp.get('quality_flags') or '(none)'}`")

st.write("**Source / ingest**")
if batch is None:
    st.warning(
        "No ingest_batch record for this row "
        f"(ingest_id=`{exp.get('ingest_id') or 'missing'}`)."
    )
    s1, s2, s3 = st.columns(3)
    s1.write("File: `—`")
    s2.write("Last updated: `—`")
    s3.write(f"Ingest id: `{exp.get('ingest_id') or '—'}`")
else:
    s1, s2, s3 = st.columns(3)
    s1.write(f"File: `{batch.get('source_file_name') or '—'}`")
    s2.write(f"Last updated: `{batch.get('loaded_at') or '—'}`")
    s3.write(f"Ingest id: `{exp.get('ingest_id') or '—'}`")
st.caption(
    f"raw_table=`{exp.get('raw_table') or 'missing'}` · "
    f"raw_row_id=`{exp.get('raw_row_id') if exp.get('raw_row_id') is not None else 'missing'}`"
)

st.write("**Matching raw fields**")
if not exp.get("raw_table") or exp.get("raw_row_id") is None or (
    isinstance(exp.get("raw_row_id"), float) and pd.isna(exp.get("raw_row_id"))
):
    st.warning(
        "This expenditure has no raw pointer (raw_table / raw_row_id). "
        "Re-import and Process Data to rebuild links."
    )
elif raw is None:
    st.warning(
        "No matching raw row for this expenditure "
        f"({exp.get('raw_table')}, row {exp.get('raw_row_id')}, "
        f"ingest `{exp.get('ingest_id')}`). "
        "Raw may have been replaced — re-import that country."
    )
else:
    st.dataframe(
        pd.DataFrame([raw]),
        use_container_width=True,
        hide_index=True,
    )
    if exp.get("country_code") == "CTC":
        st.write(
            "**Country C sub-transactions** (context only; parent amount is used)"
        )
        subs = trace["sub_transactions"]
        if subs is None or subs.empty:
            st.info("No subTransactions on this parent row.")
        else:
            st.dataframe(subs, use_container_width=True, hide_index=True)
