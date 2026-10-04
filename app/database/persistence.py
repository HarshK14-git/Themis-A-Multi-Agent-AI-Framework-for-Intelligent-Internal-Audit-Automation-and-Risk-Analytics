"""
Persistence layer (Phase 10)
Saves a completed audit run's results into PostgreSQL. Only called after
a human has approved the findings - rejected runs are not persisted,
since nothing "official" happened.
"""
import os, json
from pathlib import Path
from dotenv import load_dotenv
import psycopg

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


def save_audit_results(state):
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO audits (department, framework, status) VALUES (%s, %s, %s) RETURNING id",
        (state["department"], "ISO/IEC 27001:2022", "reported")
    )
    audit_id = cur.fetchone()[0]

    finding_id_by_control = {}
    for f in state["compliance_findings"]:
        cur.execute(
            """INSERT INTO findings (audit_id, control_id, control_name, compliance_status, reasoning, risk_note)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (audit_id, f["control_id"], f["control_name"], f["compliance_status"], f["reasoning"], f["risk_note"])
        )
        finding_id_by_control[f["control_id"]] = cur.fetchone()[0]

    for r in state["risk_scores"]:
        finding_id = finding_id_by_control.get(r["control_id"])
        cur.execute(
            """INSERT INTO risk_scores (finding_id, risk_score, risk_level, contributing_factors)
               VALUES (%s, %s, %s, %s)""",
            (finding_id, r["risk_score"], r["risk_level"], json.dumps(r["contributing_factors"]))
        )

    a = state["anomaly_summary"]
    cur.execute(
        """INSERT INTO anomalies (audit_id, total_logins_reviewed, anomalies_detected, anomaly_rate)
           VALUES (%s, %s, %s, %s)""",
        (audit_id, a["total_logins_reviewed"], a["anomalies_detected"], a["anomaly_rate"])
    )

    cur.execute(
        "INSERT INTO approvals (audit_id, decision) VALUES (%s, %s)",
        (audit_id, state["approval_status"])
    )

    cur.execute(
        "INSERT INTO reports (audit_id, executive_summary) VALUES (%s, %s)",
        (audit_id, state["report"]["executive_summary"])
    )

    for run in state.get("agent_run_log", []):
        cur.execute(
            "INSERT INTO agent_runs (audit_id, agent_name, duration_seconds, status) VALUES (%s, %s, %s, %s)",
            (audit_id, run["agent_name"], run["duration_seconds"], run["status"])
        )

    conn.commit()
    cur.close()
    conn.close()
    return audit_id