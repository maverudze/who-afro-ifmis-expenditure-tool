"""Home / landing page for the prototype."""

import streamlit as st

st.title("WHO AFRO IFMIS Expenditure Tool (Prototype)")

st.write(
    "This prototype ingests expenditure extracts from three countries "
    "(CSV, Excel, JSON), stores raw data, harmonises it into one common structure, "
    "classifies records to SHA and SRHR (with confidence and quality flags), "
    "and lets an analyst review, download, and trace rows back to the source."
)

st.info(
    "Suggested flow: **Import Data** (upload → review summary → Proceed or Cancel) → "
    "**Expenditure list** (combined table, filters, CSV) → "
    "**Row detail / trace** (audit one record) → "
    "**Dashboard** / **Raw Data** as needed."
)
