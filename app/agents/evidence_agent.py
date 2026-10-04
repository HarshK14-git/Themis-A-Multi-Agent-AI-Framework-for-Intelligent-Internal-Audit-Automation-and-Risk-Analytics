"""
Evidence Agent (Phase 7)
Links relevant evidence records to ISO 27001 controls for a given audit scope.
Pure rule-based matching - no LLM. If no evidence matches a control, that's
reported as an explicit gap, never guessed at or filled in.

Each control's evidence is tagged as:
  - "violation": the query specifically searches for instances that VIOLATE
    the control (e.g. no MFA). A match here IS the problem, not neutral data.
    Zero matches = genuinely good evidence of compliance.
  - "review": a count of relevant records gathered for review. Their presence
    alone doesn't prove compliant or non-compliant - only that evidence exists.
"""
import pandas as pd
import json
import os

def load_data():
    employees = pd.read_csv("data/processed/employees_clean.csv")
    access = pd.read_csv("data/processed/access_records_clean.csv")
    logins = pd.read_csv("data/processed/login_logs_with_anomalies.csv")
    controls = pd.read_csv("data/synthetic/compliance_controls.csv")
    return employees, access, logins, controls

def evidence_agent(department, employees, access, logins, controls):
    dept_ids = set(employees[employees["department"] == department]["employee_id"])
    dept_access = access[access["employee_id"].isin(dept_ids)]
    dept_logins = logins[logins["employee_id"].isin(dept_ids)]
    terminated_ids = set(employees[employees["employment_status"] == "Terminated"]["employee_id"])

    evidence_register = []

    for _, control in controls.iterrows():
        cid = control["control_id"]
        records = []
        evidence_type = "review"
        population = None
        data_available = True

        if cid in ("A.5.17", "A.8.5"):
            records = dept_access[dept_access["mfa_enabled"] == False]["record_id"].tolist()
            evidence_type = "violation"
            population = len(dept_access)
        elif cid == "A.8.2":
            records = dept_access[dept_access["privilege_level"].isin(["Elevated", "Admin"])]["record_id"].tolist()
        elif cid in ("A.5.15", "A.5.18", "A.8.3", "A.5.16"):
            records = dept_access["record_id"].tolist()
        elif cid == "A.6.5":
            terminated_access = dept_access[dept_access["employee_id"].isin(terminated_ids)]
            records = terminated_access[terminated_access["status"] == "Active"]["record_id"].tolist()
            evidence_type = "violation"
            population = len(terminated_access)
        elif cid == "A.8.15":
            records = dept_logins["log_id"].tolist()[:50]
        elif cid == "A.8.16":
            records = dept_logins[dept_logins["anomaly_flag"] == "Anomaly"]["log_id"].tolist()
            evidence_type = "violation"
            population = len(dept_logins)
        else:
            data_available = False   # A.8.9, A.6.3 - nothing in our dataset, genuinely

        if not data_available:
            status = "missing_evidence"
        elif evidence_type == "violation":
            status = "evidence_found"   # 0 or many, we have a real answer either way
        else:
            status = "evidence_found" if records else "missing_evidence"

        evidence_register.append({
            "control_id": cid,
            "control_name": control["control_name"],
            "department": department,
            "evidence_count": len(records),
            "evidence_type": evidence_type,
            "population": population,
            "evidence_record_ids": records[:20],
            "status": status
        })

    return evidence_register

if __name__ == "__main__":
    employees, access, logins, controls = load_data()
    register = evidence_agent("IT", employees, access, logins, controls)

    os.makedirs("data/processed", exist_ok=True)
    with open("data/processed/evidence_register_IT.json", "w") as f:
        json.dump(register, f, indent=2)

    print("Evidence register for IT department:\n")
    for item in register:
        print(f"  {item['control_id']}: {item['status']} ({item['evidence_count']} records, type={item['evidence_type']}, population={item['population']})")