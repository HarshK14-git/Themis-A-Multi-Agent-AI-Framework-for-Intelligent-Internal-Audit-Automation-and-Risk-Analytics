"""
Audit Workflow (Phases 8, 9, 10, 14)
Full LangGraph orchestration: Evidence, Compliance, and Anomaly run in
parallel (fan-out), converge into Risk, pause for human approval, then
Reporting and persistence (fan-in). Every agent's execution is timed and
logged for Phase 14's evaluation. agent_run_log uses Annotated + operator.add
so LangGraph can merge simultaneous writes from parallel nodes instead of
treating them as a conflict.
"""
from typing import TypedDict, List, Dict, Any, Annotated
import operator
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
import pandas as pd
import sys, os, time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.evidence_agent import evidence_agent, load_data as load_evidence_data
from agents.compliance_agent import compliance_agent
from agents.anomaly_agent import anomaly_agent
from agents.risk_agent import risk_agent
from agents.reporting_agent import reporting_agent
from database.persistence import save_audit_results


class AuditState(TypedDict):
    department: str
    evidence_register: List[Dict[str, Any]]
    compliance_findings: List[Dict[str, Any]]
    anomaly_summary: Dict[str, Any]
    risk_scores: List[Dict[str, Any]]
    report: Dict[str, Any]
    approval_status: str
    agent_run_log: Annotated[List[Dict[str, Any]], operator.add]


def evidence_node(state: AuditState) -> AuditState:
    print(f"[Orchestrator] Running Evidence Agent for {state['department']}...")
    start = time.time()
    employees, access, logins, controls = load_evidence_data()
    register = evidence_agent(state["department"], employees, access, logins, controls)
    return {
        "evidence_register": register,
        "agent_run_log": [{"agent_name": "evidence", "duration_seconds": round(time.time() - start, 2), "status": "success"}]
    }


def anomaly_node(state: AuditState) -> AuditState:
    print(f"[Orchestrator] Running Anomaly Agent for {state['department']}...")
    start = time.time()
    employees = pd.read_csv("data/processed/employees_clean.csv")
    logins = pd.read_csv("data/processed/login_logs_with_anomalies.csv")
    summary = anomaly_agent(state["department"], employees, logins)
    return {
        "anomaly_summary": summary,
        "agent_run_log": [{"agent_name": "anomaly", "duration_seconds": round(time.time() - start, 2), "status": "success"}]
    }


def compliance_node(state: AuditState) -> AuditState:
    print(f"[Orchestrator] Running Compliance Agent for {state['department']}...")
    start = time.time()
    findings = compliance_agent(state["evidence_register"])
    return {
        "compliance_findings": findings,
        "agent_run_log": [{"agent_name": "compliance", "duration_seconds": round(time.time() - start, 2), "status": "success"}]
    }


def risk_node(state: AuditState) -> AuditState:
    print(f"[Orchestrator] Running Risk Agent for {state['department']}...")
    start = time.time()
    scores = risk_agent(state["compliance_findings"], state["evidence_register"])
    scores_sorted = sorted(scores, key=lambda x: x["risk_score"], reverse=True)
    return {
        "risk_scores": scores_sorted,
        "agent_run_log": [{"agent_name": "risk", "duration_seconds": round(time.time() - start, 2), "status": "success"}]
    }


def approval_node(state: AuditState) -> AuditState:
    print(f"[Orchestrator] Findings ready for human review - pausing for approval...")
    decision = interrupt({
        "message": "Please review the risk scores and findings before the report is generated.",
        "top_risks": state["risk_scores"][:3],
        "non_compliant_findings": [f for f in state["compliance_findings"] if f["compliance_status"] == "Non-compliant"],
    })
    return {"approval_status": decision}


def reporting_node(state: AuditState) -> AuditState:
    print(f"[Orchestrator] Running Reporting Agent for {state['department']}...")
    start = time.time()
    report = reporting_agent(state["department"], state["compliance_findings"], state["risk_scores"], state.get("anomaly_summary"))
    return {
        "report": report,
        "agent_run_log": [{"agent_name": "reporting", "duration_seconds": round(time.time() - start, 2), "status": "success"}]
    }


def persist_node(state: AuditState) -> AuditState:
    print(f"[Orchestrator] Persisting results to PostgreSQL...")
    audit_id = save_audit_results(state)
    print(f"[Orchestrator] Saved as audit_id={audit_id}")
    return {}


def build_graph():
    graph = StateGraph(AuditState)
    graph.add_node("evidence", evidence_node)
    graph.add_node("anomaly", anomaly_node)
    graph.add_node("compliance", compliance_node)
    graph.add_node("risk", risk_node)
    graph.add_node("approval", approval_node)
    graph.add_node("reporting", reporting_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("evidence")
    graph.add_edge("evidence", "compliance")
    graph.add_edge("evidence", "anomaly")
    graph.add_edge("compliance", "risk")
    graph.add_edge("anomaly", "risk")
    graph.add_edge("risk", "approval")
    graph.add_conditional_edges(
        "approval",
        lambda state: "reporting" if state.get("approval_status") == "approve" else END,
        {"reporting": "reporting", END: END}
    )
    graph.add_edge("reporting", "persist")
    graph.add_edge("persist", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    app = build_graph()
    department = sys.argv[1] if len(sys.argv) > 1 else "IT"
    config = {"configurable": {"thread_id": f"audit-{department.lower()}-001"}}

    result = app.invoke({"department": department}, config=config)

    if "__interrupt__" in result:
        interrupt_data = result["__interrupt__"][0].value
        print("\n" + "=" * 60)
        print("PAUSED FOR HUMAN APPROVAL")
        print("=" * 60)
        print(interrupt_data["message"])
        print(f"\nTop risks: {[r['control_id'] for r in interrupt_data['top_risks']]}")
        print(f"Non-compliant findings: {[f['control_id'] for f in interrupt_data['non_compliant_findings']]}")

        decision = input("\nType 'approve' to continue, or 'reject' to stop: ").strip().lower()
        result = app.invoke(Command(resume=decision), config=config)

    print("\n" + "=" * 60)
    print("FULL AUDIT WORKFLOW COMPLETE")
    print("=" * 60)
    print(f"Approval status: {result.get('approval_status')}")
    if result.get("approval_status") == "approve":
        print(f"Report generated: {result['report']['executive_summary'][:200]}...")
    else:
        print("Report NOT generated - findings were rejected.")