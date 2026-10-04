"""
Compliance Agent (Phase 7)
Takes the Evidence Agent's output and produces a grounded compliance finding
per control. LLM only interprets - it never sees or judges controls with
missing evidence; those are hardcoded as "insufficient evidence", never guessed.
"""
import os, json, time
from pathlib import Path
from dotenv import load_dotenv
import psycopg
from groq import Groq

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

client = Groq(api_key=os.getenv("LLM_API_KEY"))

def get_control_description(control_id):
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    with conn.cursor() as cur:
        cur.execute("SELECT description, criticality FROM controls WHERE control_id = %s", (control_id,))
        row = cur.fetchone()
    conn.close()
    return row if row else ("No description available", "Unknown")

def compliance_agent(evidence_register):
    findings = []
    for item in evidence_register:
        control_id = item["control_id"]

        if item["status"] == "missing_evidence":
            findings.append({
                "control_id": control_id,
                "control_name": item["control_name"],
                "compliance_status": "Insufficient Evidence",
                "reasoning": "No evidence was collected for this control - cannot be assessed.",
                "risk_note": "N/A",
                "evidence_record_ids": [],
            })
            continue

        description, criticality = get_control_description(control_id)
        evidence_type = item["evidence_type"]
        population = item.get("population")

        if evidence_type == "violation":
            context = (f"This evidence was gathered by searching specifically for instances that VIOLATE this control. "
                       f"{item['evidence_count']} out of {population} checked records are violations. "
                       f"0 violations means genuinely good compliance evidence; any non-zero count is a confirmed problem, not neutral data.")
        else:
            context = (f"This is a count of {item['evidence_count']} relevant records gathered for review. "
                       f"Their presence alone does not prove compliant or non-compliant - only that evidence exists to review. "
                       f"Be honest that a count alone can only support 'Partially Compliant' at best, since the actual content wasn't reviewed.")

        prompt = f"""You are assessing ISO 27001 compliance for one control, using ONLY the evidence summary below.

Control: {control_id} - {item['control_name']} (Criticality: {criticality})
Description: {description}

{context}

Respond ONLY with valid JSON, no other text, in exactly this format:
{{"compliance_status": "...", "reasoning": "...", "risk_note": "..."}}"""

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        time.sleep(2)   # Groq's free tier is generous, but a small pause keeps things safe
        result = json.loads(response.choices[0].message.content)

        findings.append({
            "control_id": control_id,
            "control_name": item["control_name"],
            "compliance_status": result["compliance_status"],
            "reasoning": result["reasoning"],
            "risk_note": result["risk_note"],
            "evidence_record_ids": item["evidence_record_ids"],
        })
    return findings

if __name__ == "__main__":
    with open("data/processed/evidence_register_IT.json") as f:
        evidence_register = json.load(f)

    findings = compliance_agent(evidence_register)

    with open("data/processed/compliance_findings_IT.json", "w") as f:
        json.dump(findings, f, indent=2)

    print("Compliance findings for IT department:\n")
    for f in findings:
        print(f"  {f['control_id']} - {f['compliance_status']}: {f['reasoning'][:80]}...")

import sys, os as _os
sys.path.append(_os.path.join(_os.path.dirname(__file__), "..", "rag"))
from retrieve_controls import retrieve_relevant_controls

def assess_uploaded_evidence(evidence_text, filename):
    matches = retrieve_relevant_controls(evidence_text, top_k=1, max_distance=1.5)

    if not matches:
        return {"filename": filename, "control_id": None, "compliance_status": "No Matching Control",
                "observations": "No control in the current catalog is topically related to this evidence.",
                "recommendation": "Review scope - this evidence may belong to a control not yet catalogued."}

    match = matches[0]
    confidence = "strong" if match["distance"] < 0.78 else "weak - the evidence may not truly relate to this control, treat with caution"

    prompt = f"""You are a senior IT security auditor documenting a formal control evaluation
in a client audit workpaper. Assess whether this evidence demonstrates compliance.

Control: {match['control_id']} - {match['control_name']} (Domain: {match['category']}, Criticality: {match['criticality']})
Description: {match['description']}
Match confidence: {confidence} (semantic distance: {match['distance']:.3f})

Evidence (from file "{filename}", sensitive info already masked):
{evidence_text[:1500]}

Write this as a professional auditor would in a real workpaper:
- "observations": 2-4 concise bullet points (each starting with "- "), specific to what
  THIS evidence actually shows - not generic boilerplate. If confidence is weak, one
  bullet must state that plainly rather than force a confident-sounding assessment.
- "recommendation": one specific, actionable next step a consultant would hand the
  client - not a vague placeholder like "review further."
- "compliance_status": Compliant / Non-compliant / Partially Compliant / Uncertain

Respond ONLY with valid JSON: {{"compliance_status": "...", "observations": "...", "recommendation": "...", "risk_note": "..."}}"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    result["filename"] = filename
    result["control_id"] = match["control_id"]
    result["control_name"] = match["control_name"]
    result["category"] = match["category"]
    result["description"] = match["description"]
    result["match_distance"] = match["distance"]
    return result

if __name__ == "__main__":
    sys.path.append(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from evidence_extraction import extract_evidence_text
    from security.pii_masking import mask_evidence_text

    for f in ["Evidence_005.xlsx", "Evidence_009.png"]:
        raw = extract_evidence_text(f"data/raw/{f}")
        masked, _ = mask_evidence_text(raw)
        result = assess_uploaded_evidence(masked, f)
        print(f"\n{f}: {result['control_id']} - {result['compliance_status']}")
        print(f"  {result['reasoning']}")        
        