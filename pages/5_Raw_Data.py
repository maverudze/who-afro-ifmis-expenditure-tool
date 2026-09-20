"""Raw data page — original columns as ingested, with CSV download."""

import streamlit as st

from src import dashboard_data
from src import trace_data

st.title("Raw Data")
st.write(
    "Original country extracts as stored after import. "
    "Read-only — use Import Data to replace a country."
)
st.caption("No editing or re-processing from this page.")

countries = trace_data.list_raw_countries()
if not countries:
    st.warning("No raw country definitions found. Check config/source_definitions.yml.")
    st.stop()

labels = {
    item["country_code"]: f"{item['country_code']} — {item['country_name']}"
    for item in countries
}
selected = st.selectbox(
    "Country",
    [item["country_code"] for item in countries],
    format_func=lambda code: labels.get(code, code),
)

try:
    frame = trace_data.load_raw_table(selected)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

meta = trace_data.raw_ingest_meta(frame)

if meta["row_count"] == 0:
    st.warning(
        f"No raw rows for {selected}. "
        "Go to Import Data, upload that country’s file, then Process Data."
    )
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Rows", f"{meta['row_count']:,}")
with m2:
    st.caption("Source file")
    st.markdown(
        f"<p style='font-size:0.85rem; margin:0; word-break:break-all;'>"
        f"<code>{meta['source_file_name'] or '—'}</code></p>",
        unsafe_allow_html=True,
    )
with m3:
    st.caption("Last updated")
    loaded = str(meta["loaded_at"]) if meta["loaded_at"] is not None else "—"
    st.markdown(
        f"<p style='font-size:0.85rem; margin:0; word-break:break-all;'>"
        f"<code>{loaded}</code></p>",
        unsafe_allow_html=True,
    )
with m4:
    st.caption("Ingest id")
    st.markdown(
        f"<p style='font-size:0.85rem; margin:0; word-break:break-all;'>"
        f"<code>{meta['ingest_id'] or '—'}</code></p>",
        unsafe_allow_html=True,
    )

if not meta["source_file_name"] or meta["loaded_at"] is None:
    st.info("Ingest metadata incomplete for some rows — table below is still the raw store.")

table_name = next(
    (c["raw_table"] for c in countries if c["country_code"] == selected),
    "?",
)
st.caption(
    f"Table `{table_name}` — original columns. "
    "**last_updated** = when this extract was last imported."
)
display = frame.copy()
if "loaded_at" in display.columns:
    display = display.rename(columns={"loaded_at": "last_updated"})
    cols = list(display.columns)
    if "last_updated" in cols:
        cols.remove("last_updated")
        if "source_file_name" in cols:
            cols.insert(cols.index("source_file_name") + 1, "last_updated")
        else:
            cols.insert(0, "last_updated")
        display = display[cols]
st.dataframe(display, use_container_width=True, hide_index=True)

st.download_button(
    label=f"Download raw CSV ({selected}, {meta['row_count']:,} rows)",
    data=dashboard_data.dataframe_to_csv_bytes(display),
    file_name=dashboard_data.csv_filename(f"raw_{selected}"),
    mime="text/csv",
    key=f"download_raw_{selected}",
)
