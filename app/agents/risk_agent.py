"""
Risk Assessment Agent (Phase 7)
Deterministic 0-100 risk score per finding - NOT an LLM call. Combines
compliance status, control criticality, and (where relevant) anomaly severity
into a traceable score, so an auditor can see exactly why a number came out
the way it did.
"""
import json

CRITICALITY_WEIGHT = {"Critical": 40, "High": 25, "Medium": 15, "Low": 5}
STATUS_WEIGHT = {"Non-compliant": 50, "Partially Compliant": 25, "Compliant": 0, "Insufficient Evidence": 15}

def risk_agent(compliance_findings, evidence_register):
    evidence_by_control = {e["control_id"]: e for e in evidence_register}
    risk_scores = []

    for finding in compliance_findings:
        cid = finding["control_id"]
        evidence = evidence_by_control.get(cid, {})

        status_score = STATUS_WEIGHT.get(finding["compliance_status"], 15)

        # We don't have criticality on the finding itself - pull proportion of
        # violations as a severity multiplier where evidence_type is "violation"
        severity_bonus = 0
        contributing_factors = [f"Compliance status: {finding['compliance_status']} (+{status_score})"]

        if evidence.get("evidence_type") == "violation" and evidence.get("population"):
            ratio = evidence["evidence_count"] / evidence["population"]
            severity_bonus = round(ratio * 30)
            contributing_factors.append(
                f"Violation ratio: {evidence['evidence_count']}/{evidence['population']} = {ratio:.1%} (+{severity_bonus})"
            )

        raw_score = status_score + severity_bonus
        score = min(100, raw_score)

        if score >= 70:
            level = "Critical"
        elif score >= 45:
            level = "High"
        elif score >= 20:
            level = "Medium"
        else:
            level = "Low"

        risk_scores.append({
            "control_id": cid,
            "control_name": finding["control_name"],
            "compliance_status": finding["compliance_status"],
            "risk_score": score,
            "risk_level": level,
            "contributing_factors": contributing_factors,
        })

    return risk_scores

if __name__ == "__main__":
    with open("data/processed/compliance_findings_IT.json") as f:
        findings = json.load(f)
    with open("data/processed/evidence_register_IT.json") as f:
        evidence_register = json.load(f)

    scores = risk_agent(findings, evidence_register)
    scores_sorted = sorted(scores, key=lambda x: x["risk_score"], reverse=True)

    with open("data/processed/risk_scores_IT.json", "w") as f:
        json.dump(scores_sorted, f, indent=2)

    print("Risk scores for IT department (highest risk first):\n")
    for s in scores_sorted:
        print(f"  {s['control_id']} - {s['risk_level']} ({s['risk_score']}/100): {s['control_name']}")