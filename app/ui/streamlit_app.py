"""
Themis Audit Console (Phase 12 + evidence upload + results tracker)
Two modes: run a synthetic-data audit through the full agent pipeline with
human-in-the-loop approval, or upload a real evidence document to have it
masked, assessed against the closest matching ISO 27001 control, and logged
into a running Control Evaluation Results spreadsheet.
"""
import streamlit as st
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workflows.audit_workflow import build_graph
from langgraph.types import Command
from agents.evidence_extraction import extract_evidence_text
from security.pii_masking import mask_evidence_text
from agents.compliance_agent import assess_uploaded_evidence
from agents.results_tracker import append_result, RESULTS_PATH
import tempfile
from agents.anomaly_agent import get_flagged_records
import pandas as pd
import io

st.set_page_config(page_title="Themis Audit Console", layout="wide", page_icon="🛡️")

# ============================================================
# STYLING — dark, animated, futuristic console theme
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }

.stApp {
    background: radial-gradient(circle at 15% 0%, #131A2A 0%, #0B0F1A 55%, #060810 100%);
    background-attachment: fixed;
}

@keyframes borderGlow {
    0%   { border-color: rgba(0,229,255,0.25); box-shadow: 0 0 12px rgba(0,229,255,0.08); }
    50%  { border-color: rgba(124,77,255,0.45); box-shadow: 0 0 22px rgba(124,77,255,0.18); }
    100% { border-color: rgba(0,229,255,0.25); box-shadow: 0 0 12px rgba(0,229,255,0.08); }
}
@keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes pulseDot {
    0%   { box-shadow: 0 0 0 0 rgba(0,229,255,0.5); }
    70%  { box-shadow: 0 0 0 8px rgba(0,229,255,0); }
    100% { box-shadow: 0 0 0 0 rgba(0,229,255,0); }
}
@keyframes shimmer {
    0%   { background-position: -400px 0; }
    100% { background-position: 400px 0; }
}

.themis-header {
    padding: 1.8rem 2.2rem;
    border-radius: 18px;
    background: linear-gradient(120deg, rgba(0,229,255,0.10), rgba(124,77,255,0.05));
    border: 1px solid rgba(0,229,255,0.25);
    margin-bottom: 1.8rem;
    animation: borderGlow 4s ease-in-out infinite, fadeSlideIn 0.6s ease;
    position: relative;
    overflow: hidden;
}
.themis-header::before {
    content: "";
    position: absolute;
    top: 0; left: -50%;
    width: 50%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(0,229,255,0.06), transparent);
    animation: shimmer 6s ease-in-out infinite;
}
.themis-header h1 {
    font-size: 2.3rem;
    font-weight: 700;
    background: linear-gradient(90deg, #00E5FF, #7C4DFF, #00E5FF);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmer 5s linear infinite;
    margin: 0;
}
.themis-header p {
    color: #8FA3C7;
    margin: 0.4rem 0 0 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    letter-spacing: 0.08em;
}
.status-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #00E676;
    margin-right: 6px;
    animation: pulseDot 2s infinite;
}

.themis-card {
    background: rgba(19, 26, 42, 0.65);
    border: 1px solid rgba(0, 229, 255, 0.15);
    border-radius: 14px;
    padding: 1.3rem 1.5rem;
    margin-bottom: 0.9rem;
    backdrop-filter: blur(8px);
    transition: all 0.25s ease;
    animation: fadeSlideIn 0.5s ease;
}
.themis-card:hover {
    border-color: rgba(0, 229, 255, 0.45);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,229,255,0.12);
}

.badge {
    display: inline-block;
    padding: 0.28rem 0.75rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.badge-critical { background: rgba(255,61,113,0.15); color: #FF3D71; border: 1px solid #FF3D71; }
.badge-high     { background: rgba(255,171,0,0.15);  color: #FFAB00; border: 1px solid #FFAB00; }
.badge-ok       { background: rgba(0,230,118,0.15);  color: #00E676; border: 1px solid #00E676; }
.badge-info     { background: rgba(0,229,255,0.15);  color: #00E5FF; border: 1px solid #00E5FF; }

.stButton > button {
    border-radius: 10px;
    border: 1px solid rgba(0,229,255,0.4);
    background: linear-gradient(120deg, rgba(0,229,255,0.15), rgba(124,77,255,0.1));
    color: #E6F1FF;
    font-weight: 600;
    padding: 0.5rem 1.2rem;
    transition: all 0.25s ease;
}
.stButton > button:hover {
    border-color: #00E5FF;
    box-shadow: 0 0 16px rgba(0,229,255,0.4);
    transform: translateY(-1px);
}
.stButton > button:active { transform: translateY(0px); }

section[data-testid="stSidebar"] {
    background: #0D1220;
    border-right: 1px solid rgba(0,229,255,0.1);
}
section[data-testid="stSidebar"] .stRadio label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
}

h3, h4 {
    color: #E6F1FF !important;
    letter-spacing: 0.02em;
}

[data-testid="stMetric"] {
    background: rgba(19,26,42,0.6);
    border: 1px solid rgba(0,229,255,0.15);
    border-radius: 12px;
    padding: 0.8rem 1rem;
}

textarea {
    font-family: 'JetBrains Mono', monospace !important;
    background: #0D1220 !important;
    color: #B8C7E0 !important;
    border: 1px solid rgba(0,229,255,0.15) !important;
}

.stSpinner > div { color: #00E5FF !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="themis-header">
    <h1>🛡️ THEMIS</h1>
    <p><span class="status-dot"></span>AUTONOMOUS AUDIT & COMPLIANCE INTELLIGENCE · ISO/IEC 27001:2022</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("### 🧭 Navigation")
mode = st.sidebar.radio("Mode", ["Run Audit (synthetic data)", "Upload Evidence"], label_visibility="collapsed")
st.sidebar.markdown("---")
st.sidebar.caption("Themis v1.0 · Multi-Agent Audit Engine")
st.sidebar.markdown(
    '<p style="font-family:JetBrains Mono, monospace; font-size:0.7rem; color:#5C6F8E;">'
    'LLM never solely owns a verdict.<br>Human approval required for every finding.</p>',
    unsafe_allow_html=True
)

# ============================================================
# MODE 1: Upload real evidence -> mask -> assess -> log to tracker
# ============================================================
if mode == "Upload Evidence":
    st.markdown("### 📤 Upload Evidence for Review")
    st.caption("Upload one or more files, then click Analyze. Files are masked before any analysis happens.")

    uploaded_files = st.file_uploader(
        "Choose evidence file(s)",
        type=["png", "jpg", "jpeg", "xlsx", "pptx", "pdf"],
        accept_multiple_files=True
    )

    analyze = st.button("🚀 Analyze Evidence", type="primary", disabled=not uploaded_files)

    if analyze and uploaded_files:
        for uploaded_file in uploaded_files:
            with st.expander(f"📄 {uploaded_file.name}", expanded=True):
                suffix = "." + uploaded_file.name.split(".")[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name

                with st.spinner(f"Extracting text from {uploaded_file.name}..."):
                    raw_text = extract_evidence_text(tmp_path)
                with st.spinner("Masking sensitive information..."):
                    masked_text, count = mask_evidence_text(raw_text)

                st.markdown(f"""<div class="themis-card" style="border-color:#00E676;">
                    <span class="badge badge-ok">PROCESSED</span>
                    <span style="margin-left:0.6rem; color:#8FA3C7;">{count} sensitive item(s) masked</span>
                </div>""", unsafe_allow_html=True)

                with st.spinner("Finding the most relevant control..."):
                    result = assess_uploaded_evidence(masked_text, uploaded_file.name)

                if result["control_id"] is None:
                    st.warning("No control in the current catalog relates to this evidence.")
                else:
                    status = result["compliance_status"]
                    badge_class = "badge-ok" if status.lower() == "compliant" else "badge-high" if status.lower() == "uncertain" else "badge-critical"
                    st.markdown(f"""<div class="themis-card">
                        <span class="badge {badge_class}">{status.upper()}</span>
                        <h4 style="margin: 0.7rem 0 0.3rem 0;">{result['control_id']} — {result['control_name']}</h4>
                        <p style="color:#B8C7E0; margin:0; white-space:pre-line;">{result.get('observations', result.get('reasoning', ''))}</p>
                        <p style="color:#5C6F8E; font-family:'JetBrains Mono',monospace; font-size:0.75rem; margin-top:0.7rem;">
                            match confidence · semantic distance {result['match_distance']:.3f}
                        </p>
                    </div>""", unsafe_allow_html=True)

                    append_result(
                        control_id=result["control_id"], control_name=result.get("control_name"),
                        category=result.get("category"), description=result.get("description"),
                        evidence_filename=uploaded_file.name, compliance_status=result["compliance_status"],
                        observations=result.get("observations", result.get("reasoning", "")),
                        recommendation=result.get("recommendation", "Review finding manually."),
                        match_distance=result.get("match_distance"),
                    )
                    st.markdown("""<div class="themis-card" style="border-color:#7C4DFF;">
                        <span class="badge badge-info">LOGGED</span>
                        <span style="margin-left:0.6rem; color:#8FA3C7;">Added to Control Evaluation Results</span>
                    </div>""", unsafe_allow_html=True)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### 📄 Extracted Evidence (masked)")
                    st.text_area("", masked_text, height=250, label_visibility="collapsed", key=f"txt_{uploaded_file.name}")
                with col2:
                    st.markdown("#### 📊 Detection Summary")
                    st.metric("Sensitive items masked", count)

        if os.path.exists(RESULTS_PATH):
            with open(RESULTS_PATH, "rb") as f:
                st.download_button("📥 Download Full Control Evaluation Results", f,
                                    file_name="Control_Evaluation_Results.xlsx")

    st.stop()

# ============================================================
# MODE 2: Run a synthetic-data audit through the full pipeline
# ============================================================
if "graph_app" not in st.session_state:
    st.session_state.graph_app = build_graph()
if "stage" not in st.session_state:
    st.session_state.stage = "idle"

st.markdown("### ⚙️ Run Audit")
department = st.selectbox("Select department", ["IT", "Finance", "HR", "Sales"])

if st.session_state.stage == "idle":
    if st.button("▶ Run Audit", type="primary"):
        config = {"configurable": {"thread_id": f"audit-{department.lower()}-ui"}}
        st.session_state.config = config
        with st.spinner("Running Evidence, Anomaly, Compliance, and Risk agents..."):
            result = st.session_state.graph_app.invoke({"department": department}, config=config)
        if "__interrupt__" in result:
            st.session_state.interrupt_data = result["__interrupt__"][0].value
            st.session_state.stage = "paused"
        st.rerun()

if st.session_state.stage == "paused":
    data = st.session_state.interrupt_data
    st.markdown("""
    <div class="themis-header" style="border-color: rgba(255,171,0,0.4); background: linear-gradient(120deg, rgba(255,171,0,0.1), rgba(255,171,0,0.02));">
        <h1 style="font-size:1.5rem; -webkit-text-fill-color:#FFAB00; background:none; animation:none;">⏸ AUDIT PAUSED — HUMAN REVIEW REQUIRED</h1>
        <p>Findings must be approved before they are recorded as final</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 🎯 Top Risks")
    level_badge = {"Critical": "badge-critical", "High": "badge-high"}
    for r in data["top_risks"]:
        badge = level_badge.get(r["risk_level"], "badge-info")
        st.markdown(f"""
        <div class="themis-card">
            <span class="badge {badge}">{r['risk_level'].upper()}</span>
            <b style="margin-left:0.6rem;">{r['control_id']}</b>
            <span style="float:right; font-family:'JetBrains Mono',monospace; color:#8FA3C7;">{r['risk_score']}/100</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("#### 🚨 Non-Compliant Findings")
    if data["non_compliant_findings"]:
        for f in data["non_compliant_findings"]:
            st.markdown(f"""
            <div class="themis-card">
                <span class="badge badge-critical">NON-COMPLIANT</span>
                <b style="margin-left:0.6rem;">{f['control_id']}</b>
                <p style="color:#B8C7E0; margin-top:0.6rem;">{f['reasoning']}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="themis-card">No non-compliant findings.</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    if col1.button("✅ Approve", type="primary"):
        result = st.session_state.graph_app.invoke(Command(resume="approve"), config=st.session_state.config)
        st.session_state.result = result
        st.session_state.stage = "done"
        st.rerun()
    if col2.button("❌ Reject"):
        result = st.session_state.graph_app.invoke(Command(resume="reject"), config=st.session_state.config)
        st.session_state.result = result
        st.session_state.stage = "done"
        st.rerun()

if st.session_state.stage == "done":
    result = st.session_state.result
    if result.get("approval_status") == "approve":
        anomaly = result.get("anomaly_summary", {})
        risk_scores = result.get("risk_scores", [])
        findings = result.get("findings", [])

        nc = len([f for f in findings if f["compliance_status"] == "Non-compliant"])
        crit = len([r for r in risk_scores if r["risk_level"] == "Critical"])

        st.markdown("""
        <div class="themis-card" style="border-color:#00E676;">
            <span class="badge badge-ok">APPROVED</span>
            <span style="margin-left:0.6rem; color:#8FA3C7;">Audit finalized and saved to database.</span>
        </div>
        """, unsafe_allow_html=True)

        # --- At-a-glance metrics row ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Controls Assessed", len(findings))
        m2.metric("Non-Compliant", nc)
        m3.metric("Critical Risks", crit)
        m4.metric("Anomalous Logins", anomaly.get("anomalies_detected", "—"))

        # --- Flagged records callout ---
        if anomaly.get("anomalies_detected"):
            st.markdown(f"""
            <div class="themis-card" style="border-color:#FFAB00;">
                <span class="badge badge-high">FLAGGED RECORDS</span>
                <p style="color:#E6F1FF; margin-top:0.6rem; font-size:1.05rem;">
                    <b>{anomaly['anomalies_detected']}</b> suspicious login records flagged out of
                    <b>{anomaly['total_logins_reviewed']}</b> reviewed
                    <span style="color:#8FA3C7;">({anomaly.get('anomaly_rate', 0)*100:.1f}% anomaly rate)</span>
                </p>
                <p style="color:#8FA3C7; font-family:'JetBrains Mono',monospace; font-size:0.72rem; margin-top:0.4rem;">
                    Sample flagged log IDs: {', '.join(anomaly.get('sample_anomaly_log_ids', [])[:8])}
                </p>
            </div>
            """, unsafe_allow_html=True)

        # --- Executive summary, rendered section by section ---
        st.markdown("#### 📋 Executive Summary")
        summary = result["report"]["executive_summary"]
        # Convert the ## headers and - bullets into styled HTML
        html_lines = []
        for line in summary.split("\n"):
            s = line.strip()
            if s.startswith("## "):
                html_lines.append(f'<h4 style="color:#00E5FF; margin:1rem 0 0.4rem 0;">{s[3:]}</h4>')
            elif s.startswith("- "):
                html_lines.append(f'<p style="color:#B8C7E0; margin:0.2rem 0 0.2rem 1rem;">• {s[2:]}</p>')
            elif s:
                html_lines.append(f'<p style="color:#B8C7E0; margin:0.3rem 0;">{s}</p>')
        st.markdown(f'<div class="themis-card">{"".join(html_lines)}</div>', unsafe_allow_html=True)

                # --- Downloadable flagged records Excel ---
        if anomaly.get("anomalies_detected"):
            employees_df = pd.read_csv("data/processed/employees_clean.csv")
            logins_df = pd.read_csv("data/processed/login_logs_with_anomalies.csv")
            flagged_df = get_flagged_records(result["department"], employees_df, logins_df)

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                flagged_df.to_excel(writer, index=False, sheet_name="Flagged Records")
            buffer.seek(0)

            st.download_button(
                "📥 Download Flagged Records (Excel)",
                buffer,
                file_name=f"flagged_records_{result['department']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    else:
        st.markdown("""
        <div class="themis-card" style="border-color:#FF3D71;">
            <span class="badge badge-critical">REJECTED</span>
            <p style="margin-top:0.6rem; color:#8FA3C7;">No report was generated.</p>
        </div>
        """, unsafe_allow_html=True)

    if st.button("↻ Run another audit"):
        st.session_state.stage = "idle"
        st.rerun()