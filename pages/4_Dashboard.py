"""Dashboard — summary metrics and one-currency charts."""

import plotly.express as px
import streamlit as st

from src import dashboard_data

st.title("Dashboard")
st.write(
    "Quick overview of processed expenditure. "
    "For the combined table use **Expenditure list**; for audit use **Row detail / trace**. "
    "Amounts are never mixed across currencies."
)

frame = dashboard_data.load_expenditure_frame()
summary = dashboard_data.summary_counts(frame)

if summary["total"] == 0:
    st.warning(
        "No processed expenditure yet. Import and Process Data for Countries A, B and C first."
    )
    st.stop()

st.subheader("Overview")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total records", f"{summary['total']:,}")
c2.metric("Mapped", f"{summary['mapped']:,}")
c3.metric("Unmapped", f"{summary['unmapped']:,}")
c4.metric("Needs review", f"{summary['needs_review']:,}")
c5.metric("Quality flags", f"{summary['quality_issues']:,}")

st.write("**Records by country**")
country_cols = st.columns(max(len(summary["by_country"]), 1))
for index, (country, count) in enumerate(sorted(summary["by_country"].items())):
    country_cols[index].metric(country, f"{count:,}")

currencies = dashboard_data.available_currencies(frame)
selected_currency = st.selectbox(
    "Currency for charts (one at a time)",
    currencies,
    index=0,
)
currency_frame = frame[frame["currency_original"] == selected_currency].copy()
st.caption(
    f"Charts below use **{selected_currency}** only "
    f"({len(currency_frame):,} rows). Totals are not converted."
)

if not currency_frame.empty:
    plot_frame = currency_frame.dropna(subset=["amount_original"]).copy()
    plot_frame["amount_abs"] = plot_frame["amount_original"].abs()

    st.subheader(f"Charts — {selected_currency}")
    left, right = st.columns(2)

    with left:
        sha = (
            plot_frame.groupby("sha_code", dropna=False)["amount_abs"]
            .sum()
            .reset_index()
        )
        sha["sha_code"] = sha["sha_code"].replace("", "(blank)")
        fig_sha = px.bar(
            sha,
            x="sha_code",
            y="amount_abs",
            title=f"SHA mix ({selected_currency})",
            labels={"sha_code": "SHA", "amount_abs": f"Amount ({selected_currency})"},
        )
        st.plotly_chart(fig_sha, use_container_width=True)

    with right:
        srhr = (
            plot_frame.groupby("srhr_code", dropna=False)["amount_abs"]
            .sum()
            .reset_index()
        )
        srhr["srhr_code"] = srhr["srhr_code"].replace("", "(blank)")
        fig_srhr = px.bar(
            srhr,
            x="srhr_code",
            y="amount_abs",
            title=f"SRHR categories ({selected_currency})",
            labels={"srhr_code": "SRHR", "amount_abs": f"Amount ({selected_currency})"},
        )
        st.plotly_chart(fig_srhr, use_container_width=True)

    coverage = (
        currency_frame["classification_method"]
        .fillna("unmapped")
        .value_counts()
        .reset_index()
    )
    coverage.columns = ["classification_method", "rows"]
    fig_cov = px.pie(
        coverage,
        names="classification_method",
        values="rows",
        title=f"Classification coverage ({selected_currency})",
    )
    st.plotly_chart(fig_cov, use_container_width=True)
