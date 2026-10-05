import ast
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "retention_recommendations.csv"
RISK_COLORS = {
    "Critical": "#bd493f",
    "High": "#d57b35",
    "Medium": "#3e6c87",
    "Low": "#668653",
}

st.set_page_config(page_title="Workforce Intelligence | Retention Desk", layout="wide")
st.markdown(
    """
    <style>
      :root { color-scheme: light; }
      .stApp {
        color: #202d34;
        background-color: #edf1f1;
        background-image: linear-gradient(rgba(32,45,52,.025) 1px, transparent 1px),
          linear-gradient(90deg, rgba(32,45,52,.025) 1px, transparent 1px);
        background-size: 24px 24px;
      }
      [data-testid="stHeader"] { background: rgba(237,241,241,.92); }
      [data-testid="stSidebar"] { background: #23343b; }
      [data-testid="stSidebar"] * { color: #edf2f1; }
      .block-container { max-width: 1540px; padding-top: 2rem; }
      [data-testid="stMetric"] { padding: 14px 16px; border: 1px solid #d5dddc; border-top: 3px solid #3e6c87; background: #fff; }
      [data-testid="stMetricLabel"] { color: #65757a; font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }
      [data-testid="stMetricValue"] { color: #202d34; font-size: 28px; }
      div[data-testid="stDataFrame"] { border: 1px solid #d5dddc; }
      .stButton > button, .stDownloadButton > button { border-radius: 3px; border: 1px solid #bd493f; background: #bd493f; color: #fff; font-weight: 700; }
      .stButton > button:hover, .stDownloadButton > button:hover { border-color: #98382f; background: #98382f; color: #fff; }
      h1, h2, h3 { color: #202d34; }
    </style>
    """,
    unsafe_allow_html=True,
)

df = pd.read_csv(DATA_PATH).copy()
df.insert(0, "Case", [f"WF-{index + 1:04d}" for index in range(len(df))])

st.markdown(
    """
    <div style="border-top:4px solid #202d34;padding:14px 0 18px;margin-bottom:8px">
      <div style="color:#bd493f;font-size:10px;font-weight:800;letter-spacing:.16em;text-transform:uppercase">Workforce intelligence / People analytics</div>
      <h1 style="font-family:Georgia,serif;font-size:38px;font-weight:600;margin:7px 0;color:#202d34">Retention risk register</h1>
      <p style="max-width:820px;color:#65757a;font-size:13px;line-height:1.6;margin:0">Review prepared attrition-risk estimates, financial exposure, and suggested retention actions across the workforce dataset.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.info("Prepared analysis snapshot · This dashboard reads the supplied CSV; no model is running live.")

with st.sidebar:
    st.markdown("### Review filters")
    st.caption("Filters apply to the register and summary metrics.")
    risk_options = sorted(df["CriticalityLevel"].dropna().unique().tolist())
    priority_options = sorted(df["ActionPriority"].dropna().unique().tolist())
    selected_risks = st.multiselect("Risk level", risk_options, default=risk_options)
    selected_priorities = st.multiselect("Action priority", priority_options, default=priority_options)
    probability_range = st.slider("Attrition probability", 0.0, 1.0, (0.0, 1.0), 0.05)
    overtime_only = st.checkbox("Overtime flag only")
    search = st.text_input("Find case", placeholder="WF-0001")

filtered = df[
    df["CriticalityLevel"].isin(selected_risks)
    & df["ActionPriority"].isin(selected_priorities)
    & df["AttritionProbability"].between(*probability_range)
]
if overtime_only:
    filtered = filtered[filtered["OverTime"] == 1]
if search.strip():
    filtered = filtered[filtered["Case"].str.contains(search.strip(), case=False, na=False)]

high_risk_count = int(filtered["CriticalityLevel"].isin(["Critical", "High"]).sum())
follow_up_count = int((filtered["ActionPriority"] != "Monitor").sum())
financial_exposure = float(filtered["FinancialLoss"].sum())

metric_columns = st.columns(4)
metric_columns[0].metric("Cases in view", f"{len(filtered):,}")
metric_columns[1].metric("High / critical", f"{high_risk_count:,}")
metric_columns[2].metric("Action required", f"{follow_up_count:,}")
metric_columns[3].metric("Estimated exposure", f"${financial_exposure:,.0f}")

chart_column, distribution_column = st.columns([1, 1.2])
with chart_column:
    st.subheader("Risk distribution")
    distribution = filtered["CriticalityLevel"].value_counts().rename_axis("Risk level").reset_index(name="Cases")
    if distribution.empty:
        st.caption("No cases match the selected filters.")
    else:
        figure = px.bar(
            distribution,
            x="Risk level",
            y="Cases",
            color="Risk level",
            color_discrete_map=RISK_COLORS,
            category_orders={"Risk level": ["Critical", "High", "Medium", "Low"]},
        )
        figure.update_layout(showlegend=False, margin=dict(l=0, r=0, t=12, b=0), plot_bgcolor="white", paper_bgcolor="white", font_color="#405158")
        st.plotly_chart(figure, use_container_width=True)

with distribution_column:
    st.subheader("Attrition probability")
    if filtered.empty:
        st.caption("No cases match the selected filters.")
    else:
        figure = px.histogram(filtered, x="AttritionProbability", nbins=18, color_discrete_sequence=["#3e6c87"])
        figure.update_layout(margin=dict(l=0, r=0, t=12, b=0), plot_bgcolor="white", paper_bgcolor="white", font_color="#405158", xaxis_title="Estimated probability", yaxis_title="Cases")
        figure.update_xaxes(tickformat=".0%")
        st.plotly_chart(figure, use_container_width=True)

st.divider()
table_column, case_column = st.columns([1.35, 1])
with table_column:
    st.subheader("Priority review queue")
    st.caption("Records are anonymized case numbers; no employee names are present in this dataset.")
    table = filtered.sort_values("CriticalityScore", ascending=False).head(100)[
        ["Case", "AttritionProbability", "CriticalityLevel", "EmployeeValueScore", "FinancialLoss", "ActionPriority"]
    ].copy()
    table["AttritionProbability"] = (table["AttritionProbability"] * 100).round(1).map(lambda value: f"{value:.1f}%")
    table["EmployeeValueScore"] = table["EmployeeValueScore"].round(1)
    table["FinancialLoss"] = table["FinancialLoss"].map(lambda value: f"${value:,.0f}")
    table = table.rename(columns={
        "AttritionProbability": "Attrition estimate",
        "CriticalityLevel": "Risk level",
        "EmployeeValueScore": "Value score",
        "FinancialLoss": "Estimated exposure",
        "ActionPriority": "Next review",
    })
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.download_button(
        "Export filtered register",
        data=filtered.to_csv(index=False),
        file_name="workforce-risk-register.csv",
        mime="text/csv",
        disabled=filtered.empty,
    )

with case_column:
    st.subheader("Retention action brief")
    if filtered.empty:
        st.caption("Choose broader filters to select a case.")
    else:
        case_options = filtered["Case"].tolist()
        selected_case = st.selectbox("Select anonymized case", case_options)
        record = filtered.loc[filtered["Case"] == selected_case].iloc[0]
        st.markdown(f"**{record['Case']}** · {record['CriticalityLevel']} risk · {record['ActionPriority']}")
        st.metric("Estimated attrition probability", f"{record['AttritionProbability']:.1%}")
        st.metric("Estimated financial exposure", f"${record['FinancialLoss']:,.0f}")
        st.markdown("**Suggested actions**")
        try:
            recommendations = ast.literal_eval(record["Recommendations"])
        except (ValueError, SyntaxError):
            recommendations = [str(record["Recommendations"])]
        for recommendation in recommendations:
            st.markdown(f"- {recommendation}")
        st.caption("Recommendations are prepared dataset outputs, not a live model response.")