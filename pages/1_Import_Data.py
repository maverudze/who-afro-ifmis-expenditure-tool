"""Import Data — upload, review summary, confirm or cancel import."""

import streamlit as st

from src import classify
from src import harmonise
from src import ingest_raw
from src import quality
from src import settings
from src import validate_import

validate_extract = validate_import.validate_extract
load_preview = validate_import.load_preview

st.title("Import Data")
st.write(
    "Select the country, then upload that country’s expenditure extract "
    "**from any folder on your computer**. Only the file name must match."
)

options = settings.country_options()
labels = [item["label"] for item in options]
selected_label = st.selectbox("Country", labels)
selected = next(item for item in options if item["label"] == selected_label)
country_code = selected["code"]
definition = settings.load_source_definitions()[country_code]
expected_name = settings.EXPECTED_FILENAMES[country_code]

if st.session_state.get("import_country") != country_code:
    st.session_state["import_country"] = country_code
    st.session_state["import_file_name"] = None
    st.session_state["import_file_bytes"] = None
    st.session_state["import_source"] = None
    st.session_state["import_valid"] = False
    st.session_state["import_success"] = None
    st.session_state["import_uploader_version"] = (
        st.session_state.get("import_uploader_version", 0) + 1
    )

if "import_uploader_version" not in st.session_state:
    st.session_state["import_uploader_version"] = 0
if "import_success" not in st.session_state:
    st.session_state["import_success"] = None

st.info(
    f"**{selected['label']}** — expected file: **{expected_name}** "
    f"({selected['file_type_label']}, currency: {definition['currency']}). "
    "You may browse Downloads, Desktop, or any other folder."
)


def clear_staged_file():
    st.session_state["import_file_name"] = None
    st.session_state["import_file_bytes"] = None
    st.session_state["import_source"] = None
    st.session_state["import_valid"] = False
    st.session_state["import_uploader_version"] = (
        st.session_state.get("import_uploader_version", 0) + 1
    )


def store_file(file_name, file_bytes, source):
    if file_name.lower() != expected_name.lower():
        st.error(
            f"File name must be **{expected_name}**. "
            "The folder does not matter — only the name."
        )
        return
    st.session_state["import_file_name"] = file_name
    st.session_state["import_file_bytes"] = file_bytes
    st.session_state["import_source"] = source
    st.session_state["import_valid"] = False
    st.session_state["import_success"] = None


if st.session_state.get("import_success"):
    st.success(st.session_state["import_success"])

uploaded = st.file_uploader(
    "Upload file (any folder)",
    type=settings.FILE_TYPE_EXTENSIONS[selected["file_type"]],
    key=f"uploader_{country_code}_{st.session_state['import_uploader_version']}",
)
if uploaded is not None:
    store_file(uploaded.name, uploaded.getvalue(), "upload")

st.caption("Optional demo shortcut — uses the sample pack in this project:")
if st.button("Load sample file"):
    sample_path = settings.SAMPLE_FILES[country_code]
    store_file(sample_path.name, sample_path.read_bytes(), "sample")
    st.rerun()

file_name = st.session_state.get("import_file_name")
file_bytes = st.session_state.get("import_file_bytes")
if file_name and file_bytes:
    source = st.session_state.get("import_source")
    st.success(f"File ready: **{file_name}** ({source}, {len(file_bytes):,} bytes).")
    is_valid, message = validate_extract(country_code, file_bytes, definition)
    st.session_state["import_valid"] = is_valid
    if is_valid:
        st.success(message)

        summary = quality.summarise_extract_quality(
            country_code, file_bytes, definition
        )
        flag_counts = summary["flag_counts"]

        st.subheader("Import summary")
        st.caption(
            "Review data-quality signals before writing to the database. "
            "Nothing is saved until you confirm."
        )
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Rows in file", f"{summary['rows_read']:,}")
        m2.metric("Rows with any issue", f"{summary['rows_with_any_flag']:,}")
        m3.metric("Duplicate txn ids", f"{summary['duplicate_txn_ids']:,}")
        m4.metric(
            "Missing amount",
            f"{flag_counts.get('missing_amount', 0):,}",
        )

        detail_cols = st.columns(4)
        extra_flags = [
            ("bad_date", "Bad date"),
            ("date_outside_fy", "Date outside FY"),
            ("missing_description", "Missing description"),
            ("amount_format", "Messy amount format"),
            ("unparseable_amount", "Unparseable amount"),
            ("negative_amount", "Negative amount"),
            ("mixed_currency", "Mixed currency"),
            ("suspicious_text", "Suspicious text"),
        ]
        for index, (flag_key, label) in enumerate(extra_flags):
            with detail_cols[index % 4]:
                st.metric(label, f"{flag_counts.get(flag_key, 0):,}")

        preview, row_count = load_preview(country_code, file_bytes, definition)
        with st.expander(f"Preview first rows ({row_count:,} total)", expanded=False):
            st.dataframe(preview, use_container_width=True)

        st.markdown(
            """
            <style>
            div[class*="st-key-proceed_import"] button {
                background-color: #2e7d32 !important;
                border-color: #2e7d32 !important;
                color: #ffffff !important;
            }
            div[class*="st-key-proceed_import"] button:hover {
                background-color: #1b5e20 !important;
                border-color: #1b5e20 !important;
                color: #ffffff !important;
            }
            div[class*="st-key-cancel_import"] button {
                background-color: #c62828 !important;
                border-color: #c62828 !important;
                color: #ffffff !important;
            }
            div[class*="st-key-cancel_import"] button:hover {
                background-color: #8e0000 !important;
                border-color: #8e0000 !important;
                color: #ffffff !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            proceed = st.button(
                "Proceed with import",
                key="proceed_import",
                use_container_width=True,
            )
        with c2:
            cancel = st.button(
                "Cancel import",
                key="cancel_import",
                use_container_width=True,
            )

        if cancel:
            clear_staged_file()
            st.session_state["import_success"] = None
            st.warning("Import cancelled. File was not saved.")
            st.rerun()

        if proceed:
            with st.spinner("Importing, harmonising, and classifying…"):
                ingest_id, table_name, rows_read, rows_stored = ingest_raw.save_raw(
                    country_code, file_name, file_bytes
                )
                harmonised = harmonise.save_harmonised_country(country_code)
                classified = classify.classify_expenditure_country(country_code)
            st.session_state["import_success"] = (
                f"Import successful for **{country_code}**. "
                f"Ingest **{ingest_id[:8]}…** · raw `{table_name}` **{rows_stored:,}** rows · "
                f"harmonised **{harmonised:,}** · "
                f"classified **{classified['updated']:,}** "
                f"(coa_map {classified['methods'].get('coa_map', 0)}, "
                f"keyword {classified['methods'].get('keyword', 0)}, "
                f"unmapped {classified['methods'].get('unmapped', 0)})."
            )
            clear_staged_file()
            st.rerun()
    else:
        st.error(message)
        st.warning("File was not saved to the database.")
        if st.button("Cancel import", key="cancel_invalid"):
            clear_staged_file()
            st.rerun()
else:
    st.caption("Upload a file or load the sample to see the import summary.")
