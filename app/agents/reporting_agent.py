"""
Reporting Agent (Phase 7, updated)
Assembles the final audit report. The LLM only writes prose around numbers
we already computed - it never regenerates a score or a compliance verdict.
Now also receives the anomaly summary so flagged records appear in the report.
"""
import os, json, time
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

client = Groq(api_key=os.getenv("LLM_API_KEY"))


def _call_with_retry(**kwargs):
    for attempt in range(3):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            if attempt < 2:
                print(f"[reporting_agent] API call failed (attempt {attempt+1}/3), retrying in 5s: {e}")
                time.sleep(5)
            else:
                raise


def reporting_agent(department, findings, risk_scores, anomaly_summary=None):
    non_compliant = [f for f in findings if f["compliance_status"] == "Non-compliant"]
    partial = [f for f in findings if f["compliance_status"] == "Partially Compliant"]
    insufficient = [f for f in findings if f["compliance_status"] == "Insufficient Evidence"]
    critical_risks = [r for r in risk_scores if r["risk_level"] == "Critical"]

    summary_data = {
        "department": department,
        "framework": "ISO/IEC 27001:2022",
        "total_controls_assessed": len(findings),
        "non_compliant_count": len(non_compliant),
        "partially_compliant_count": len(partial),
        "insufficient_evidence_count": len(insufficient),
        "critical_risk_controls": [r["control_name"] for r in critical_risks],
        "top_risks": risk_scores[:3],
        "non_compliant_details": non_compliant,
        "anomaly_summary": anomaly_summary or {},
    }

    prompt = f"""Write a professional internal audit executive summary (250-350 words) for a
{department} department access-control audit against ISO/IEC 27001:2022.

Use ONLY the data below - do not invent any findings, numbers, or controls not listed here.

Data: {json.dumps(summary_data, indent=2)}

Structure your response with these exact section headers on their own lines:
## Overall Posture
(one paragraph)
## Key Findings
(bullet points starting with "- ", each citing a control ID)
## Anomaly Detection
(one or two sentences citing the exact anomaly_summary numbers - how many suspicious
login records were flagged out of how many reviewed, and the anomaly rate. If no
anomaly data is present, state that anomaly detection was not run for this scope.)
## Recommended Priority Actions
(bullet points starting with "- ")

Professional, direct, no fluff."""

    response = _call_with_retry(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
    )
    executive_summary = response.choices[0].message.content

    return {
        "department": department,
        "framework": "ISO/IEC 27001:2022",
        "executive_summary": executive_summary,
        "findings": findings,
        "risk_scores": risk_scores,
        "anomaly_summary": anomaly_summary or {},
    }


if __name__ == "__main__":
    with open("data/processed/compliance_findings_IT.json") as f:
        findings = json.load(f)
    with open("data/processed/risk_scores_IT.json") as f:
        risk_scores = json.load(f)
    anomaly = None
    try:
        with open("data/processed/anomaly_summary_IT.json") as f:
            anomaly = json.load(f)
    except FileNotFoundError:
        pass

    report = reporting_agent("IT", findings, risk_scores, anomaly)
    print(report["executive_summary"])