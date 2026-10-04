"""
Results Tracker (v3 - resilient sheet lookup)
Fills the pre-listed rows in the Security Controls Framework sheet by
matching control_id, rather than appending new rows. Falls back to the
workbook's first sheet if the expected sheet name doesn't match exactly
(handles minor naming differences between template copies).
"""
import os
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

TEMPLATE_PATH = "data/templates/Case_study_Reference_Workbook.xlsx"
RESULTS_PATH = "data/processed/Control_Evaluation_Results_filled.xlsx"
SHEET_NAME = "Security Controls Framework"

COL_DOMAIN, COL_CONTROL_ID, COL_DESCRIPTION = 3, 4, 5
COL_EVIDENCE, COL_RESULT, COL_OBSERVATIONS, COL_RECOMMENDATION = 6, 7, 8, 9

STATUS_TO_RESULT = {
    "compliant": "Pass", "non-compliant": "Fail", "partially compliant": "Partial",
    "insufficient evidence": "Partial", "uncertain": "Partial", "no matching control": "Partial",
}

RESULT_FILLS = {
    "Pass": PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
    "Partial": PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"),
    "Fail": PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
}

def get_sheet(wb):
    if SHEET_NAME in wb.sheetnames:
        return wb[SHEET_NAME]
    print(f"[results_tracker] WARNING: sheet '{SHEET_NAME}' not found. "
          f"Available sheets: {wb.sheetnames}. Using '{wb.sheetnames[0]}' instead.")
    return wb[wb.sheetnames[0]]

def get_or_create_results_workbook():
    if os.path.exists(RESULTS_PATH):
        return load_workbook(RESULTS_PATH)

    wb = load_workbook(TEMPLATE_PATH)
    ws = get_sheet(wb)
    for row in range(1, ws.max_row + 1):
        if ws.cell(row=row, column=COL_CONTROL_ID).value:
            ws.cell(row=row, column=COL_EVIDENCE, value=None)
            ws.cell(row=row, column=COL_RESULT, value=None)
            ws.cell(row=row, column=COL_OBSERVATIONS, value=None)
            ws.cell(row=row, column=COL_RECOMMENDATION, value=None)
    return wb

def append_result(control_id, control_name, category, description, evidence_filename,
                   compliance_status, observations, recommendation, match_distance=None):
    wb = get_or_create_results_workbook()
    ws = get_sheet(wb)
    result_label = STATUS_TO_RESULT.get((compliance_status or "").lower(), "Partial")

    target_row = None
    for row in range(1, ws.max_row + 1):
        if ws.cell(row=row, column=COL_CONTROL_ID).value == control_id:
            target_row = row
            break
    if target_row is None:
        target_row = ws.max_row + 1
        ws.cell(row=target_row, column=COL_CONTROL_ID, value=control_id)
        ws.cell(row=target_row, column=COL_DOMAIN, value=category or "N/A")
        ws.cell(row=target_row, column=COL_DESCRIPTION, value=description or control_name or "N/A")
        for col in [COL_DOMAIN, COL_CONTROL_ID, COL_DESCRIPTION, COL_EVIDENCE, COL_RESULT, COL_OBSERVATIONS, COL_RECOMMENDATION]:
            try:
                ws.cell(row=target_row, column=col).alignment = ws.cell(row=5, column=col).alignment
                ws.cell(row=target_row, column=col).font = ws.cell(row=5, column=col).font
            except Exception:
                pass

    existing_evidence = ws.cell(row=target_row, column=COL_EVIDENCE).value
    note = evidence_filename
    if match_distance is not None:
        note += f" (approx. match closeness: {max(0, 1 - match_distance):.0%})"
    ws.cell(row=target_row, column=COL_EVIDENCE, value=f"{existing_evidence}\n{note}" if existing_evidence else note)

    result_cell = ws.cell(row=target_row, column=COL_RESULT, value=result_label)
    result_cell.fill = RESULT_FILLS.get(result_label, RESULT_FILLS["Partial"])

    ws.cell(row=target_row, column=COL_OBSERVATIONS, value=observations)
    ws.cell(row=target_row, column=COL_RECOMMENDATION, value=recommendation)

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    wb.save(RESULTS_PATH)
    return RESULTS_PATH