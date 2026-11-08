import os
import streamlit as st
from neo4j import GraphDatabase

# Initialize connection
URI = st.secrets.get("NEO4J_URI") or os.getenv("NEO4J_URI", "neo4j+s://5c8337f2.databases.neo4j.io")
USER = st.secrets.get("NEO4J_USER") or os.getenv("NEO4J_USER", "5c8337f2")
PASSWORD = st.secrets.get("NEO4J_PASSWORD") or os.getenv("NEO4J_PASSWORD", "cCXGOVGtM4sHkVddI_5h9bijQvkEn1Wuq2ACQyaT-ek")
DATABASE = st.secrets.get("NEO4J_DATABASE") or os.getenv("NEO4J_DATABASE", "5c8337f2")

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

def init_database():
    with driver.session(database=DATABASE) as session:
        print("Clearing existing data...")
        session.run("MATCH (n) DETACH DELETE n")

        print("Creating indexes and constraints...")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Activity) REQUIRE a.id IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (w:Workstream) REQUIRE w.name IS UNIQUE")

        print("Loading Project Aster (ABC-101) graph...")
        
        # 1. Create Program and Workstreams
        session.run("""
            CREATE (p:Program {id: 'PRG-ASTER', name: 'Project Aster (ABC-101)', status: 'ACTIVE'})
            MERGE (s1:Workstream {name: 'Upstream Process (USP)'})
            MERGE (s2:Workstream {name: 'Downstream Process (DSP)'})
            MERGE (s3:Workstream {name: 'Drug Product (DP)'})
            MERGE (s4:Workstream {name: 'Analytical & QC'})
            MERGE (s5:Workstream {name: 'Regulatory & Quality'})
            
            CREATE (p)-[:HAS_WORKSTREAM]->(s1)
            CREATE (p)-[:HAS_WORKSTREAM]->(s2)
            CREATE (p)-[:HAS_WORKSTREAM]->(s3)
            CREATE (p)-[:HAS_WORKSTREAM]->(s4)
            CREATE (p)-[:HAS_WORKSTREAM]->(s5)
        """)

        # 2. Create Activities
        activities = [
            # Analytical & QC
            {"id": "ACT-101", "name": "Method Transfer & Assay Prep", "ws": "Analytical & QC", "duration": 14, "start": 0, "status": "COMPLETED"},
            {"id": "ACT-102", "name": "Analytical Method Qualification", "ws": "Analytical & QC", "duration": 21, "start": 14, "status": "ON_TRACK"},
            
            # Upstream Process
            {"id": "ACT-201", "name": "Raw Material Procurement", "ws": "Upstream Process (USP)", "duration": 30, "start": 0, "status": "ON_TRACK"},
            {"id": "ACT-202", "name": "USP Inoculum & Media Prep", "ws": "Upstream Process (USP)", "duration": 10, "start": 30, "status": "PLANNED"},
            {"id": "ACT-203", "name": "USP Bioreactor Cultivation (1000L)", "ws": "Upstream Process (USP)", "duration": 14, "start": 40, "status": "PLANNED"},
            {"id": "ACT-204", "name": "USP Harvest & Clarification", "ws": "Upstream Process (USP)", "duration": 5, "start": 54, "status": "PLANNED"},

            # Downstream Process
            {"id": "ACT-301", "name": "DSP Chromatography Capture Step", "ws": "Downstream Process (DSP)", "duration": 12, "start": 59, "status": "PLANNED"},
            {"id": "ACT-302", "name": "DSP Ultrafiltration/Diafiltration (UF/DF)", "ws": "Downstream Process (DSP)", "duration": 8, "start": 71, "status": "PLANNED"},
            {"id": "ACT-303", "name": "Bulk Drug Substance (BDS) Bulk Fill", "ws": "Downstream Process (DSP)", "duration": 4, "start": 79, "status": "PLANNED"},

            # Drug Product & Regulatory
            {"id": "ACT-401", "name": "BDS Quality Control Release Testing", "ws": "Analytical & QC", "duration": 20, "start": 83, "status": "PLANNED"},
            {"id": "ACT-402", "name": "Drug Product (DP) Aseptic Fill & Finish", "ws": "Drug Product (DP)", "duration": 10, "start": 103, "status": "PLANNED"},
            {"id": "ACT-501", "name": "IND / IMPD Dossier Submission", "ws": "Regulatory & Quality", "duration": 15, "start": 113, "status": "PLANNED"}
        ]

        for act in activities:
            session.run("""
                MATCH (ws:Workstream {name: $ws})
                CREATE (a:Activity {
                    id: $id,
                    name: $name,
                    duration: $duration,
                    base_start: $start,
                    base_finish: $start + $duration,
                    curr_start: $start,
                    curr_finish: $start + $duration,
                    delay_days: 0,
                    status: $status
                })
                CREATE (ws)-[:HAS_ACTIVITY]->(a)
            """, act)

        # 3. Dependencies (Hard Finish-to-Start)
        dependencies = [
            ("ACT-101", "ACT-102"),
            ("ACT-201", "ACT-202"),
            ("ACT-202", "ACT-203"),
            ("ACT-203", "ACT-204"),
            ("ACT-204", "ACT-301"),
            ("ACT-102", "ACT-301"), # Qualification must finish before DSP
            ("ACT-301", "ACT-302"),
            ("ACT-302", "ACT-303"),
            ("ACT-303", "ACT-401"),
            ("ACT-401", "ACT-402"),
            ("ACT-402", "ACT-501")
        ]

        for source, target in dependencies:
            session.run("""
                MATCH (src:Activity {id: $source})
                MATCH (tgt:Activity {id: $target})
                CREATE (src)-[:DEPENDS_ON]->(tgt)
            """, source=source, target=target)

        print("Database successfully seeded!")

if __name__ == "__main__":
    init_database()
    driver.close()