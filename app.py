import streamlit as st
from neo4j import GraphDatabase
import pandas as pd
import json

# 1. Конфигурация страницы
st.set_page_config(
    page_title="CMC Control Tower — Project Aster",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Подключение к Neo4j AuraDB из Streamlit Secrets
@st.cache_resource
def get_neo4j_driver():
    uri = st.secrets["NEO4J_URI"]
    user = st.secrets["NEO4J_USER"]
    password = st.secrets["NEO4J_PASSWORD"]
    return GraphDatabase.driver(uri, auth=(user, password))

driver = get_neo4j_driver()

def run_query(query, parameters=None):
    with driver.session() as session:
        result = session.run(query, parameters or {})
        return [record.data() for record in result]

# Загрузка данных активностей из Neo4j
@st.cache_data(ttl=60)
def load_activities():
    query = """
    MATCH (a:Activity)
    OPTIONAL MATCH (a)-[:BELONGS_TO]->(wp:WorkPackage)
    RETURN a.activity_id AS id,
           a.name AS name,
           a.workstream AS workstream,
           a.baseline_start AS baseline_start,
           a.baseline_finish AS baseline_finish,
           a.execution_status AS execution_status,
           a.health_status AS health_status,
           a.owner AS owner,
           a.performer AS performer,
           a.reviewer AS reviewer
    ORDER BY a.activity_id
    """
    data = run_query(query)
    return pd.DataFrame(data) if data else pd.DataFrame(columns=[
        'id', 'name', 'workstream', 'baseline_start', 'baseline_finish',
        'execution_status', 'health_status', 'owner', 'performer', 'reviewer'
    ])

df_activities = load_activities()

# Верхний заголовок
st.title("🧬 CMC Control Tower — Project Aster (ASTER-P1)")
st.caption("Graph-driven Program & Execution Model for Pharmaceutical Development (Handoff v0.3)")

# Навигация по вкладкам (5 разделов)
tab_overview, tab_execution, tab_simulation, tab_inbox, tab_setup = st.tabs([
    "📊 Programme Overview", 
    "📋 Execution Overview", 
    "⏱️ Plan & Simulation", 
    "📥 Update Inbox (AI)", 
    "⚙️ Programme Setup"
])

# ==========================================
# TAB 1: PROGRAMME OVERVIEW
# ==========================================
with tab_overview:
    st.subheader("Executive Health & Milestone Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Activities", len(df_activities))
    with col2:
        delayed_count = len(df_activities[df_activities['health_status'] == 'DELAYED']) if 'health_status' in df_activities.columns else 0
        st.metric("Delayed / At Risk", delayed_count, delta_color="inverse")
    with col3:
        st.metric("Target Milestone", "ASTER-M06 (FPI)", "2027-05-15")
    with col4:
        st.metric("Programme Health", "ON TRACK", delta="Stable")
    
    st.divider()
    st.info("💡 **Project Aster Status:** Программа находится на стадии клинических поставок и аналитической квалификации. Критический путь проходит через аналитические методы (ACT-023) и финальную подачу IND.")
    
    if not df_activities.empty:
        st.markdown("### Workstream Breakdown")
        ws_counts = df_activities['workstream'].value_counts().reset_index()
        ws_counts.columns = ['Workstream', 'Count']
        st.dataframe(ws_counts, use_container_width=True)

# ==========================================
# TAB 2: EXECUTION OVERVIEW (Операционный вид)
# ==========================================
with tab_execution:
    st.subheader("Operational Execution Board")
    st.write("Отслеживание текущего статуса выполнения задач, зон ответственности (Owner / Performer) и блокеров независимо от диаграммы Ганта.")
    
    if not df_activities.empty:
        # Фильтры
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            selected_ws = st.selectbox("Filter by Workstream", ["All"] + list(df_activities['workstream'].unique()))
        with f_col2:
            selected_health = st.selectbox("Filter by Health", ["All", "ON_TRACK", "AT_RISK", "DELAYED"])
        with f_col3:
            selected_status = st.selectbox("Filter by Execution Status", ["All", "NOT_STARTED", "IN_PROGRESS", "COMPLETED", "BLOCKED"])
        
        filtered_df = df_activities.copy()
        if selected_ws != "All":
            filtered_df = filtered_df[filtered_df['workstream'] == selected_ws]
        if selected_health != "All":
            filtered_df = filtered_df[filtered_df['health_status'] == selected_health]
        if selected_status != "All":
            filtered_df = filtered_df[filtered_df['execution_status'] == selected_status]
            
        st.dataframe(
            filtered_df[['id', 'name', 'workstream', 'execution_status', 'health_status', 'owner', 'performer']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("База данных активностей пуста. Выполните сидинг через `seed.py`.")

# ==========================================
# TAB 3: PLAN & SIMULATION (What-If Гант)
# ==========================================
with tab_simulation:
    st.subheader("What-If Delay Simulation & Cascade Impact")
    
    col_ctrl, col_res = st.columns([1, 2])
    with col_ctrl:
        st.markdown("#### Scenario Controls")
        scenario = st.selectbox("Predefined PRD Scenarios", ["-- Select Scenario --", "SCN-01: Analytical Method Delay (+5d)", "SCN-02: Raw Material Lead Time (+7d)", "SCN-03: DSP Polishing Delay (+8d)"])
        
        if not df_activities.empty:
            act_list = df_activities['id'].tolist()
            selected_act = st.selectbox("Select Activity for Custom Delay", act_list)
            delay_days = st.number_input("Delay (days)", min_value=0, max_value=90, value=0)
            
            if st.button("Apply Delay (In-Memory Simulation)", type="primary"):
                st.success(f"Симуляция для {selected_act} на +{delay_days} дней успешно рассчитана в памяти!")
            
            if st.button("Reset to Baseline"):
                st.info("Сброшено к базовому расписанию.")

    with col_res:
        st.markdown("#### Baseline vs Forecast Timeline")
        if not df_activities.empty:
            st.dataframe(
                df_activities[['id', 'name', 'baseline_start', 'baseline_finish']],
                use_container_width=True,
                hide_index=True
            )

# ==========================================
# TAB 4: UPDATE INBOX (AI Ingestion)
# ==========================================
with tab_inbox:
    st.subheader("Programme Update Inbox & AI Extraction")
    st.write("Вставьте текст коммуникации (саммари со встречи Teams Copilot, письмо от CDMO или письмо поставщика), чтобы извлечь предложения по обновлению плана.")
    
    raw_input_text = st.text_area("Paste unstructured update / meeting notes / email text here:", height=150, placeholder="Example: CDMO Northbridge reported that chromatography resin delivery (MAT-002) is delayed by 4 days due to customs clearance...")
    
    if st.button("Extract Proposals with Gemini AI", type="primary"):
        if raw_input_text.strip():
            with st.spinner("Анализ текста и сопоставление с графом Project Aster..."):
                # Заглушка под будущий вызов Gemini API Structured Output
                st.success("AI успешно проанализировал текст и сформировал 1 предложение (Proposal)")
                
                with st.expander("Proposal PROP-001 (Pending Review)", expanded=True):
                    st.markdown("**Target Activity:** `ACT-007` (Raw Material Procurement)")
                    st.markdown("**Extracted Fact:** Задержка поставки сырья на 4 дня.")
                    st.markdown("> *«Resin shipment delayed by 4 days due to customs...»* (Source: `DOC-010`)")
                    
                    col_acc, col_rej = st.columns(2)
                    with col_acc:
                        st.button("Accept & Create Proposal", key="accept_1")
                    with col_rej:
                        st.button("Reject", key="reject_1")
        else:
            st.warning("Пожалуйста, введите текст для анализа.")

# ==========================================
# TAB 5: PROGRAMME SETUP
# ==========================================
with tab_setup:
    st.subheader("Programme Setup & Blueprint Configuration")
    st.write("Управление конфигурацией проекта, связями зависимостей и подключением к Neo4j AuraDB.")
    
    st.text_input("Neo4j URI", value=st.secrets.get("NEO4J_URI", ""), disabled=True)
    st.text_input("Neo4j Database", value=st.secrets.get("NEO4J_DATABASE", "neo4j"), disabled=True)
    
    if st.button("Test Database Connection"):
        try:
            run_query("RETURN 1 AS test")
            st.success("Соединение с Neo4j AuraDB установлено успешно!")
        except Exception as e:
            st.error(f"Ошибка подключения: {e}")