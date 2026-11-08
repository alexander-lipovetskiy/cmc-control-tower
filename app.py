import os
import pandas as pd
import plotly.express as px
import streamlit as st
from neo4j import GraphDatabase

# 1. Page configuration
st.set_page_config(
    page_title="CMC Intelligence Platform | Control Tower",
    page_icon="🧬",
    layout="wide",
)


# 2. Neo4j connection initialization
@st.cache_resource
def get_db_driver():
  uri = st.secrets.get("NEO4J_URI") or os.getenv(
      "NEO4J_URI", "neo4j+s://5c8337f2.databases.neo4j.io"
  )
  user = st.secrets.get("NEO4J_USER") or os.getenv("NEO4J_USER", "5c8337f2")
  password = st.secrets.get("NEO4J_PASSWORD") or os.getenv(
      "NEO4J_PASSWORD", "cCXGOVGtM4sHkVddI_5h9bijQvkEn1Wuq2ACQyaT-ek"
  )
  database = st.secrets.get("NEO4J_DATABASE") or os.getenv(
      "NEO4J_DATABASE", "5c8337f2"
  )
  return GraphDatabase.driver(uri, auth=(user, password)), database


driver, db_name = get_db_driver()


# 3. Graph database helper functions
def fetch_activities():
  query = """
    MATCH (ws:Workstream)-[:HAS_ACTIVITY]->(a:Activity)
    RETURN a.id AS id, a.name AS name, ws.name AS workstream,
           a.base_start AS base_start, a.base_finish AS base_finish,
           a.curr_start AS curr_start, a.curr_finish AS curr_finish,
           a.delay_days AS delay_days, a.status AS status
    ORDER BY a.curr_start ASC
    """
  with driver.session(database=db_name) as session:
    result = session.run(query)
    df = pd.DataFrame([record.data() for record in result])
  return df


def apply_delay_and_recalculate(activity_id, added_delay):
  with driver.session(database=db_name) as session:
    session.run(
        """
            MATCH (a:Activity {id: $id})
            SET a.delay_days = $delay,
                a.curr_start = a.base_start + $delay,
                a.curr_finish = a.base_finish + $delay,
                a.status = CASE WHEN $delay > 0 THEN 'DELAYED' ELSE 'ON_TRACK' END
        """,
        id=activity_id,
        delay=added_delay,
    )

    query_cascade = """
        MATCH (src:Activity)-[:DEPENDS_ON*]->(tgt:Activity)
        WHERE src.id = $id
        WITH tgt, src
        MATCH (prev:Activity)-[:DEPENDS_ON]->(tgt)
        WITH tgt, max(prev.curr_finish) AS max_prev_finish
        SET tgt.curr_start = max_prev_finish,
            tgt.curr_finish = max_prev_finish + tgt.duration,
            tgt.delay_days = max_prev_finish - tgt.base_start,
            tgt.status = CASE WHEN (max_prev_finish - tgt.base_start) > 0 THEN 'AT_RISK' ELSE tgt.status END
        """
    session.run(query_cascade, id=activity_id)


def reset_all_delays():
  with driver.session(database=db_name) as session:
    session.run("""
            MATCH (a:Activity)
            SET a.delay_days = 0,
                a.curr_start = a.base_start,
                a.curr_finish = a.base_finish,
                a.status = CASE WHEN a.id = 'ACT-101' THEN 'COMPLETED' ELSE 'ON_TRACK' END
        """)


# --- USER INTERFACE ---

st.title("🧬 CMC Control Tower — Project Aster (ABC-101)")
st.caption(
    "Graph-driven Impact Analysis Engine for Pharmaceutical Development"
)

# Sidebar (What-If Simulation)
st.sidebar.header("🕹️ What-If Delay Simulation")
st.sidebar.markdown(
    "Select a predefined delay scenario or set custom parameters:"
)

scenario = st.sidebar.selectbox(
    "Predefined PRD Scenarios (v0.3):",
    [
        "-- Select Scenario --",
        "Scenario 1: Analytical Delay (+5 days)",
        "Scenario 2: Raw Material Delay (+7 days)",
        "Scenario 3: DSP Delay (+8 days)",
    ],
)

if scenario == "Scenario 1: Analytical Delay (+5 days)":
  apply_delay_and_recalculate("ACT-102", 5)
elif scenario == "Scenario 2: Raw Material Delay (+7 days)":
  apply_delay_and_recalculate("ACT-201", 7)
elif scenario == "Scenario 3: DSP Delay (+8 days)":
  apply_delay_and_recalculate("ACT-301", 8)

st.sidebar.subheader("Custom Delay Input")
selected_act = st.sidebar.selectbox(
    "Select Activity:", ["ACT-102", "ACT-201", "ACT-301", "ACT-401"]
)
custom_delay = st.sidebar.slider("Delay (days):", 0, 30, 0)

if st.sidebar.button("Apply Delay"):
  apply_delay_and_recalculate(selected_act, custom_delay)
  st.sidebar.success(f"Applied +{custom_delay} days delay to {selected_act}")

if st.sidebar.button("🔄 Reset to Baseline"):
  reset_all_delays()
  st.rerun()

# Top Metrics Block (KPIs)
df_data = fetch_activities()

if not df_data.empty:
  total_acts = len(df_data)
  delayed_acts = len(df_data[df_data["delay_days"] > 0])
  max_delay = df_data["delay_days"].max()
  ind_target_finish = df_data[df_data["id"] == "ACT-501"]["curr_finish"].values[
      0
  ]
  ind_base_finish = df_data[df_data["id"] == "ACT-501"]["base_finish"].values[0]
  overall_project_delay = ind_target_finish - ind_base_finish

  col1, col2, col3, col4 = st.columns(4)
  col1.metric("Total Activities", total_acts)
  col2.metric(
      "Impacted by Delay",
      f"{delayed_acts} acts",
      delta=f"{delayed_acts}" if delayed_acts > 0 else "0",
      delta_color="inverse",
  )
  col3.metric(
      "Maximum Shift",
      f"+{max_delay} days" if max_delay > 0 else "0 days",
      delta_color="inverse",
  )
  col4.metric(
      "IND Submission Target",
      f"Day {ind_target_finish}",
      delta=f"+{overall_project_delay} days"
      if overall_project_delay > 0
      else "On Track",
      delta_color="inverse",
  )

  st.markdown("---")

  # Gantt Chart Visualization (Plotly Timeline with real calendar dates)
  st.subheader("📊 Hierarchical Plan & Timeline")

  base_date = pd.Timestamp("2026-11-01")
  gantt_df = []
  for _, row in df_data.iterrows():
    gantt_df.append(
        dict(
            Task=row["name"],
            Start=base_date + pd.Timedelta(days=int(row["base_start"])),
            Finish=base_date + pd.Timedelta(days=int(row["base_finish"])),
            Type="Baseline",
            Workstream=row["workstream"],
            Status=row["status"],
        )
    )
    if row["delay_days"] > 0:
      gantt_df.append(
          dict(
              Task=row["name"],
              Start=base_date + pd.Timedelta(days=int(row["curr_start"])),
              Finish=base_date + pd.Timedelta(days=int(row["curr_finish"])),
              Type="Forecast (With Delay)",
              Workstream=row["workstream"],
              Status=row["status"],
          )
      )

  plot_df = pd.DataFrame(gantt_df)

  fig = px.timeline(
      plot_df,
      x_start="Start",
      x_end="Finish",
      y="Task",
      color="Status",
      pattern_shape="Type",
      title="Baseline vs Forecast Comparison",
      labels={"Task": "Activity", "Workstream": "Workstream"},
  )
  fig.update_yaxes(autorange="reversed")
  st.plotly_chart(fig, use_container_width=True)

  # Detailed Process Table
  st.subheader("📋 Process & Cascade Impact Table")

  def highlight_status(val):
    if val == "DELAYED":
      return "background-color: #ffcccc; color: red; font-weight: bold;"
    elif val == "AT_RISK":
      return "background-color: #fff3cd; color: #856404;"
    elif val == "COMPLETED":
      return "background-color: #d4edda; color: #155724;"
    return ""

  styled_df = df_data[[
      "id",
      "name",
      "workstream",
      "base_start",
      "curr_start",
      "delay_days",
      "status",
  ]].style.map(highlight_status, subset=["status"])
  st.dataframe(styled_df, use_container_width=True)

else:
  st.warning(
      "Database is empty. Run 'python seed.py' to populate the graph with mock"
      " data."
  )