"""
Themis - Synthetic Data Generator (Phase 2)
Generates realistic synthetic enterprise data with deliberately injected
anomalies, since real audit data isn't available. Run this file once to
create all the CSVs this project needs.
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import os

random.seed(42)
np.random.seed(42)

OUTPUT_DIR = "data/synthetic"
os.makedirs(OUTPUT_DIR, exist_ok=True)

REFERENCE_DATE = datetime(2026, 8, 1)     # "today" for this project's synthetic world
QUARTER_START = datetime(2026, 4, 1)      # Q2 2026 - the audit period we'll use later
QUARTER_END = datetime(2026, 6, 30)

DEPARTMENTS = ["IT", "Finance", "HR", "Operations", "Sales", "Legal"]
ROLES = ["Analyst", "Engineer", "Manager", "Specialist", "Director", "Associate"]
LOCATIONS = ["New York", "London", "Mumbai", "Singapore", "Remote"]
SYSTEMS = ["ERP", "CRM", "Active Directory", "AWS Console", "Payroll System", "File Server"]
PERMISSIONS = ["Read", "Write", "Admin", "Read/Write"]
PRIVILEGE_LEVELS = ["Standard", "Elevated", "Admin"]
COUNTRIES = ["USA", "UK", "India", "Singapore", "Germany", "Canada"]
DEVICES = ["Laptop", "Desktop", "Mobile", "Tablet"]
FIRST_NAMES = ["Aarav","Priya","John","Emma","Wei","Sara","Liam","Noor","Carlos","Mei",
               "Ahmed","Olivia","Ravi","Sofia","David"]
LAST_NAMES = ["Sharma","Smith","Chen","Khan","Garcia","Patel","Müller","Kim","Silva","Nguyen"]

N_EMPLOYEES = 250

# ---------- 1. employees.csv ----------
employees = []
for i in range(1, N_EMPLOYEES + 1):
    status = "Active" if random.random() > 0.05 else "Terminated"   # ~5% terminated
    employees.append({
        "employee_id": f"EMP{i:04d}",
        "name": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
        "department": random.choice(DEPARTMENTS),
        "role": random.choice(ROLES),
        "joining_date": (REFERENCE_DATE - timedelta(days=random.randint(30, 3000))).strftime("%Y-%m-%d"),
        "employment_status": status,
        "location": random.choice(LOCATIONS),
        "manager_id": f"EMP{random.randint(1, N_EMPLOYEES):04d}" if random.random() > 0.05 else "",
    })
employees_df = pd.DataFrame(employees)
employees_df.to_csv(f"{OUTPUT_DIR}/employees.csv", index=False)

# ---------- 2. access_records.csv ----------
access_records = []
record_id = 1
terminated_ids = set(employees_df[employees_df.employment_status == "Terminated"].employee_id)

for _, emp in employees_df.iterrows():
    for system in random.sample(SYSTEMS, random.randint(1, 3)):
        privilege = random.choices(PRIVILEGE_LEVELS, weights=[70, 20, 10])[0]
        mfa_enabled = True
        if privilege in ("Elevated", "Admin") and random.random() < 0.15:   # anomaly: privileged w/o MFA
            mfa_enabled = False
        status = "Active"
        if emp.employee_id in terminated_ids:
            status = "Active" if random.random() < 0.6 else "Revoked"      # anomaly: orphaned access
        access_records.append({
            "record_id": f"ACC{record_id:05d}",
            "employee_id": emp.employee_id,
            "system": system,
            "role": emp.role,
            "permission": random.choice(PERMISSIONS),
            "privilege_level": privilege,
            "mfa_enabled": mfa_enabled,
            "access_granted_date": (REFERENCE_DATE - timedelta(days=random.randint(30, 1500))).strftime("%Y-%m-%d"),
            "last_access_date": (REFERENCE_DATE - timedelta(days=random.randint(0, 200))).strftime("%Y-%m-%d"),
            "status": status,
        })
        record_id += 1
access_df = pd.DataFrame(access_records)
access_df.to_csv(f"{OUTPUT_DIR}/access_records.csv", index=False)

# ---------- 3. login_logs.csv ----------
login_logs = []
log_id = 1
active_employees = employees_df[employees_df.employment_status == "Active"].employee_id.tolist()
n_days = (QUARTER_END - QUARTER_START).days

def random_ip():
    return f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"

for day in range(n_days):
    date = QUARTER_START + timedelta(days=day)
    for _ in range(random.randint(150, 300)):
        emp_id = random.choice(active_employees)
        hour = random.choices(range(24), weights=[1]*6 + [8]*12 + [1]*6)[0]
        timestamp = date.replace(hour=hour, minute=random.randint(0, 59))
        country = random.choices(COUNTRIES, weights=[40, 15, 20, 10, 10, 5])[0]
        roll = random.random()
        if roll < 0.03:                                    # anomaly: after-hours login
            timestamp = timestamp.replace(hour=random.choice([1, 2, 3, 4, 23]))
        if roll < 0.02:                                     # anomaly: unusual/rare country
            country = random.choice(["Nigeria", "Russia", "North Korea", "Unknown"])
        login_logs.append({
            "log_id": f"LOG{log_id:06d}",
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "employee_id": emp_id,
            "ip_address": random_ip(),
            "country": country,
            "device": random.choice(DEVICES),
            "login_status": "Success" if random.random() > 0.05 else "Failed",
            "session_duration": random.randint(5, 480),
            "data_accessed": random.choice(["Low", "Medium", "High"]),
        })
        log_id += 1

for _ in range(max(1, len(active_employees)//100)):        # anomaly: brute-force clusters
    emp_id = random.choice(active_employees)
    date = QUARTER_START + timedelta(days=random.randint(0, n_days - 1))
    base_hour = random.randint(0, 23)
    for _ in range(random.randint(5, 15)):
        timestamp = date.replace(hour=base_hour, minute=random.randint(0, 59))
        login_logs.append({
            "log_id": f"LOG{log_id:06d}", "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "employee_id": emp_id, "ip_address": random_ip(), "country": random.choice(COUNTRIES),
            "device": random.choice(DEVICES), "login_status": "Failed",
            "session_duration": 0, "data_accessed": "None",
        })
        log_id += 1

login_df = pd.DataFrame(login_logs)
login_df.to_csv(f"{OUTPUT_DIR}/login_logs.csv", index=False)

# ---------- 4. compliance_controls.csv (ISO 27001:2022 - Access Control + Identity subset) ----------
controls = [
    ("A.5.15", "Access control", "Organizational", "High"),
    ("A.5.16", "Identity management", "Organizational", "High"),
    ("A.5.17", "Authentication information", "Organizational", "High"),
    ("A.5.18", "Access rights", "Organizational", "High"),
    ("A.8.2", "Privileged access rights", "Technological", "Critical"),
    ("A.8.3", "Information access restriction", "Technological", "High"),
    ("A.8.5", "Secure authentication", "Technological", "Critical"),
    ("A.8.9", "Configuration management", "Technological", "Medium"),
    ("A.8.15", "Logging", "Technological", "Medium"),
    ("A.8.16", "Monitoring activities", "Technological", "Medium"),
    ("A.6.3", "Awareness, education, training", "People", "Low"),
    ("A.6.5", "Termination responsibilities", "People", "High"),
]
controls_df = pd.DataFrame(controls, columns=["control_id", "control_name", "category", "criticality"])
controls_df["framework"] = "ISO 27001:2022"
controls_df["description"] = controls_df["control_name"] + " control within ISO/IEC 27001:2022 Annex A"
controls_df.to_csv(f"{OUTPUT_DIR}/compliance_controls.csv", index=False)

# ---------- 5. audit_findings.csv ----------
finding_types = {"Access Management": 0.37, "Policy Gaps": 0.24,
                  "Employee Onboarding/Offboarding": 0.18, "Configuration": 0.12, "Other": 0.09}
findings = []
for i in range(1, 221):
    control = controls_df.sample(1).iloc[0]
    resolved = random.random() > 0.2
    findings.append({
        "finding_id": f"FND{i:04d}",
        "control_id": control.control_id,
        "department": random.choice(DEPARTMENTS),
        "severity": random.choices(["Low", "Medium", "High", "Critical"], weights=[30, 35, 25, 10])[0],
        "finding_type": random.choices(list(finding_types.keys()), weights=list(finding_types.values()))[0],
        "date": (REFERENCE_DATE - timedelta(days=random.randint(1, 720))).strftime("%Y-%m-%d"),
        "resolution_time_days": random.randint(1, 90) if resolved else "",
        "status": "Resolved" if resolved else "Open",
    })
findings_df = pd.DataFrame(findings)
findings_df.to_csv(f"{OUTPUT_DIR}/audit_findings.csv", index=False)

# ---------- 6. historical_audits.csv (trains the future_high_risk predictive model later) ----------
historical = []
for period in range(1, 17):
    for dept in DEPARTMENTS:
        prev_findings = random.randint(0, 15)
        critical_findings = random.randint(0, 4)
        mfa_adoption_pct = round(random.uniform(50, 100), 1)
        privileged_accounts = random.randint(2, 20)
        failed_logins = random.randint(0, 50)
        risk_signal = (prev_findings*2 + critical_findings*5 + (100-mfa_adoption_pct)*0.5
                       + privileged_accounts*1.5 + failed_logins*0.5)
        future_high_risk = 1 if random.random() < min(0.95, risk_signal/180) else 0
        historical.append({
            "audit_period": f"Q{((period-1)%4)+1}-{2023 + (period-1)//4}",
            "department": dept,
            "previous_findings": prev_findings,
            "critical_findings": critical_findings,
            "mfa_adoption_pct": mfa_adoption_pct,
            "privileged_accounts": privileged_accounts,
            "failed_logins": failed_logins,
            "avg_resolution_days": round(random.uniform(2, 60), 1),
            "future_high_risk": future_high_risk,
        })
historical_df = pd.DataFrame(historical)
historical_df.to_csv(f"{OUTPUT_DIR}/historical_audits.csv", index=False)

print("Done! Generated files in data/synthetic/:")
for f in sorted(os.listdir(OUTPUT_DIR)):
    print(" -", f)