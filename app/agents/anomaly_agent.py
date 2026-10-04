"""
Anomaly Detection Agent (Phase 7, completing Phase 4's model)
Wraps the trained Isolation Forest as a callable agent function, matching
the pattern of the other agents. ML does the detecting - this agent never
re-scores or overrides the model's output, only summarizes it.
"""
import pandas as pd
import joblib
import json

def anomaly_agent(department, employees, logins):
    dept_ids = set(employees[employees["department"] == department]["employee_id"])
    dept_logins = logins[logins["employee_id"].isin(dept_ids)]

    anomalies = dept_logins[dept_logins["anomaly_flag"] == "Anomaly"]

    summary = {
        "department": department,
        "total_logins_reviewed": len(dept_logins),
        "anomalies_detected": len(anomalies),
        "anomaly_rate": round(len(anomalies) / len(dept_logins), 4) if len(dept_logins) else 0,
        "sample_anomaly_log_ids": anomalies["log_id"].tolist()[:20],
    }
    return summary

if __name__ == "__main__":
    employees = pd.read_csv("data/processed/employees_clean.csv")
    logins = pd.read_csv("data/processed/login_logs_with_anomalies.csv")

    result = anomaly_agent("IT", employees, logins)

    with open("data/processed/anomaly_summary_IT.json", "w") as f:
        json.dump(result, f, indent=2)

    print("Anomaly summary for IT department:")
    print(f"  {result['anomalies_detected']} anomalies out of {result['total_logins_reviewed']} logins ({result['anomaly_rate']:.1%})")

def get_flagged_records(department, employees, logins):
    """Returns the full flagged anomaly rows for a department, for export."""
    dept_ids = set(employees[employees["department"] == department]["employee_id"])
    dept_logins = logins[logins["employee_id"].isin(dept_ids)]
    anomalies = dept_logins[dept_logins["anomaly_flag"] == "Anomaly"]
    cols = [c for c in ["log_id", "employee_id", "timestamp", "country", "device",
                        "login_status", "is_after_hours", "is_unusual_country",
                        "failed_attempts_same_day", "anomaly_score"] if c in anomalies.columns]
    return anomalies[cols].copy()