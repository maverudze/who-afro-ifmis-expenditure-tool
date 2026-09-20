"""WHO AFRO IFMIS Expenditure Tool (Prototype). Streamlit entry point."""

import streamlit as st

st.set_page_config(
    page_title="WHO AFRO IFMIS Expenditure Tool",
    layout="wide",
)

home = st.Page("pages/0_Home.py", title="Home", default=True)
import_data = st.Page("pages/1_Import_Data.py", title="Import Data")
expenditure_list = st.Page(
    "pages/2_Harmonised_Data.py",
    title="Expenditure list",
)
row_detail = st.Page(
    "pages/3_Row_Detail_Trace.py",
    title="Row detail / trace",
)
dashboard = st.Page("pages/4_Dashboard.py", title="Dashboard")
raw_data = st.Page("pages/5_Raw_Data.py", title="Raw Data")

# Top-level pages with no section label.
pg = st.navigation(
    {
        "": [home, import_data],
        "Harmonised Data": [expenditure_list, row_detail],
        "Review": [dashboard, raw_data],
    }
)
pg.run()
