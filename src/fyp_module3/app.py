"""Interactive Local Web App for live manual testing, account overrides, and custom export (Streamlit)."""

import os
import tempfile
from pathlib import Path
import streamlit as st

from fyp_module3.core.pipeline import PipelineOptions, run_compilation
from fyp_module3.core.taxonomy import get_line_items

# st.stop() and st.rerun() signal control flow by raising. They must travel
# through the error handler below rather than be reported as a failure.
try:
    from streamlit.runtime.scriptrunner.exceptions import RerunException, StopException
    _CONTROL_FLOW = (RerunException, StopException)
except ImportError:  # pragma: no cover - depends on the Streamlit version
    _CONTROL_FLOW = ()


st.set_page_config(
    page_title="LedgerIQ — Statutory Statement Compiler",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 26px;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 2px;
    }
    .sub-header {
        font-size: 14px;
        color: #64748B;
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding-top: 10px;
        padding-bottom: 10px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="main-header">📊 LedgerIQ — Autonomous Statutory Statement &amp; Dynamic Notes Compiler</div>',
    unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Module 3 &amp; 9 (M3-M9-COMPOUND) · Companies Act 2017 (Fifth Schedule) &amp; IFRS for SMEs</div>',
    unsafe_allow_html=True)

# -------------------------------------------------------------
# Sidebar: Controls & Inputs
# -------------------------------------------------------------
st.sidebar.header("📁 Input Selection")

sample_dir = Path(__file__).parent.parent.parent / "data" / "sample_tbs"
sample_files = list(sample_dir.glob("*.xlsx")) if sample_dir.exists() else []

input_mode = st.sidebar.radio("Choose Input Source:", ["Upload Excel File", "Use Sample Trial Balance"])

uploaded_bytes = None
file_name = "Trial_Balance.xlsx"

if input_mode == "Upload Excel File":
    uploaded_file = st.sidebar.file_uploader(
        "Upload Trial Balance (.xlsx, .xls, .csv)",
        type=["xlsx", "xls", "csv"],
        help="Supports 3-column or 4-column trial balances with or without account codes."
    )
    if uploaded_file is not None:
        uploaded_bytes = uploaded_file.getvalue()
        file_name = uploaded_file.name
else:
    sample_names = [f.name for f in sample_files]
    selected_sample = st.sidebar.selectbox("Select a Sample Trial Balance:", sample_names)
    if selected_sample:
        sample_path = sample_dir / selected_sample
        uploaded_bytes = sample_path.read_bytes()
        file_name = selected_sample

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Statement Settings")
default_entity = Path(file_name).stem.replace("-", " ").replace("_", " ").title()
entity_name = st.sidebar.text_input("Company / Entity Name:", value=default_entity)
period = st.sidebar.text_input("Reporting Period Ended:", value="June 30, 2025")
sheet_name = st.sidebar.text_input(
    "Worksheet Name (optional):", value="",
    help="Leave blank to auto-detect the trial balance sheet.")

st.sidebar.markdown("---")
st.sidebar.header("🛡️ Compilation Guards")
enforce_health_gate = st.sidebar.checkbox(
    "Enforce pre-flight data health gate", value=True,
    help="Refuse to compile statements from data with critical structural defects.")
allow_plug = st.sidebar.checkbox(
    "Allow unsupported balancing entry", value=False,
    help="Permit an unexplained residual variance to be posted to trade debtors or creditors "
         "to force the balance sheet to balance. The resulting statements are NOT supported "
         "by the ledger and are flagged as such.")

st.sidebar.markdown("---")
st.sidebar.header("💾 Output File & Folder Configuration")
clean_slug = entity_name.replace(" ", "_")
custom_filename = st.sidebar.text_input("Output File Name:", value=f"{clean_slug}_Financial_Statements.xlsx")
if not custom_filename.endswith(".xlsx"):
    custom_filename += ".xlsx"

default_desktop = str(Path.home() / "Desktop")
target_folder = st.sidebar.text_input(
    "Target Folder / Directory Hierarchy:",
    value=default_desktop,
    help="Enter any folder path on your computer. Missing parent folders will be created automatically."
)

save_to_disk_clicked = st.sidebar.button("💾 Save Directly to Target Folder", use_container_width=True)

# -------------------------------------------------------------
# Execution & Rendering
# -------------------------------------------------------------
if uploaded_bytes is None:
    st.info("👈 Please select a sample trial balance or upload an Excel file from the "
            "left sidebar to start live testing.")
    st.stop()

# Persist the upload so openpyxl can open it, and clean up afterwards rather
# than leaving a temp file behind on every rerun.
with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_name).suffix or ".xlsx") as tmp_in:
    tmp_in.write(uploaded_bytes)
    tmp_in_path = tmp_in.name

tmp_out_path = None
produced_path = None
try:
    if "account_overrides" not in st.session_state:
        st.session_state["account_overrides"] = {}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_out:
        tmp_out_path = tmp_out.name

    # One pipeline, shared with the CLI and the desktop bridge - including the
    # pre-flight health gate, which this app previously skipped entirely.
    outcome = run_compilation(
        tmp_in_path,
        PipelineOptions(
            output_file=tmp_out_path,
            entity_name=entity_name,
            period=period,
            sheet_name=sheet_name or None,
            enforce_health_gate=enforce_health_gate,
            allow_working_capital_plug=allow_plug,
            overrides=dict(st.session_state["account_overrides"]),
        ),
    )
    result = outcome.result
    produced_path = result.output_file
    health = result.health_report

    # ------------------------------------------------------ Data health
    if health.issues:
        with st.expander(f"🩺 Data Health: {health.health_score:.0f}/100 ({health.severity})",
                         expanded=health.severity != "CLEAN"):
            st.write(health.headline)
            for issue in health.issues:
                render = st.error if issue.severity == "CRITICAL" else st.warning
                render(f"**{issue.category}** — {issue.description}\n\nSuggested fix: {issue.remediation_hint}")

    if result.status == "FAILED_CRITICAL":
        st.error(f"❌ {result.message}")
        if result.workbook_audit:
            for failure in result.workbook_audit.failures:
                st.error(f"Workbook audit — {failure}")
        if result.output_file and Path(result.output_file).exists():
            st.download_button(
                "📥 Download the unverified workbook for diagnosis",
                data=Path(result.output_file).read_bytes(),
                file_name=Path(result.output_file).name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        st.stop()

    if result.status == "RECOVERED_WARNING":
        st.warning(f"⚠️ {result.message}")

    report = result.verification_report
    audit = result.workbook_audit
    balanced_accounts = outcome.accounts
    audit_trail = outcome.audit_trail
    exporter = outcome.exporter
    compiled_notes = exporter.notes_compiler.notes
    bs_rows = exporter.bs_compiler.rows
    pl_rows = exporter.pl_compiler.rows

    final_dr = sum(a.debit for a in balanced_accounts)
    final_cr = sum(a.credit for a in balanced_accounts)
    compiled_excel_bytes = Path(result.output_file).read_bytes()

    if save_to_disk_clicked:
        try:
            out_dir = Path(target_folder)
            out_dir.mkdir(parents=True, exist_ok=True)
            target_file_path = out_dir / custom_filename
            target_file_path.write_bytes(compiled_excel_bytes)
            st.success(f"✅ Successfully compiled and saved to disk: `{target_file_path}`")
        except Exception as exc:
            st.error(f"❌ Failed to save file to `{target_folder}`: {exc}")

    # ------------------------------------------------------ Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ledger Accounts", f"{len(balanced_accounts)}")
    col2.metric(
        "Trial Balance Parity",
        "Balanced" if report.is_tb_balanced else "Imbalanced",
        delta=f"Δ = PKR {report.tb_delta:,.2f}" if report.tb_delta else "Dr == Cr",
    )
    col3.metric("Net Profit / (Loss)", f"PKR {report.net_profit:,.2f}")
    col4.metric(
        "Exported Workbook Audit",
        "Verified" if audit and audit.passed else "Not verified",
        delta=(f"A - (L + E) = PKR {audit.balance_sheet_variance:,.2f}" if audit else "not run"),
        delta_color="normal" if audit and audit.passed else "inverse",
    )

    if audit:
        with st.expander("🔎 Workbook audit — formulas evaluated in the exported file", expanded=False):
            st.caption("These checks read the saved .xlsx back and evaluate its own formulas, "
                       "so they describe the file you download rather than values held in memory.")
            for check in audit.checks:
                st.success(check)
            for failure in audit.failures:
                st.error(failure)

    if report.auto_corrections:
        with st.expander("⚡ Autonomous Counter-Checking Self-Corrections Applied", expanded=True):
            for corr in report.auto_corrections:
                st.info(f"✔ {corr}")

    st.markdown("---")

    # ------------------------------------------------------ Download
    d_col1, d_col2 = st.columns([2, 1])
    with d_col1:
        st.download_button(
            label=f"📥 Download '{custom_filename}' via Browser",
            data=compiled_excel_bytes,
            file_name=custom_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )
    with d_col2:
        st.info(f"Target Save Folder: `{target_folder}`")

    tab_bs, tab_pl, tab_notes, tab_audit, tab_tb, tab_overrides = st.tabs([
        "🏛️ Balance Sheet (SOFP)",
        "📈 Profit or Loss",
        "📝 Statutory Notes (4–12)",
        "🔍 Balancing & Mapping Audit",
        "📋 Working Trial Balance",
        "✏️ Interactive Account Overrides"
    ])

    with tab_bs:
        st.subheader(f"Statement of Financial Position as at {period}")
        st.dataframe([
            {
                "Statement Line Item": r["label"],
                "Note": str(r["note"]) if r["note"] else "",
                "Amount (PKR)": f"{r['amount']:,.2f}" if r["amount"] is not None else "",
                "Type": r.get("style", "normal"),
            }
            for r in bs_rows
        ], use_container_width=True, height=450)

    with tab_pl:
        st.subheader(f"Statement of Profit or Loss for the period ended {period}")
        st.dataframe([
            {
                "Particulars": r["label"],
                "Note": str(r["note"]) if r["note"] else "",
                "Amount (PKR)": f"{r['amount']:,.2f}" if r["amount"] is not None else "",
                "Type": r.get("style", "normal"),
            }
            for r in pl_rows
        ], use_container_width=True, height=400)

    with tab_notes:
        st.subheader("Itemized Statutory Disclosure Notes")
        for note in compiled_notes:
            with st.expander(f"Note {note.note_number}: {note.title} "
                             f"(Subtotal Cell: {note.subtotal_cell_ref})", expanded=True):
                items_data = [
                    {"Account Description": itm.account_name, "Amount (PKR)": f"{itm.amount:,.2f}"}
                    for itm in note.items
                ]
                total = sum(itm.amount for itm in note.items)
                items_data.append({"Account Description": f"Total {note.title.title()}",
                                   "Amount (PKR)": f"{total:,.2f}"})
                st.table(items_data)

    with tab_audit:
        st.subheader("Auditor Heuristic Actions & Classification Audit Trail")

        st.markdown("#### 🛡️ Statement Integrity Verification Theorems")
        st.table([
            {"Audit Theorem": "Trial Balance Parity (Dr = Cr)",
             "Value": f"Dr {final_dr:,.2f} | Cr {final_cr:,.2f}",
             "Status": "✅ PASSED" if report.is_tb_balanced else "❌ FAILED"},
            {"Audit Theorem": "Total Assets",
             "Value": f"PKR {report.total_assets:,.2f}", "Status": "COMPUTED"},
            {"Audit Theorem": "Total Equity & Liabilities",
             "Value": f"PKR {report.total_liabilities_and_equity:,.2f}", "Status": "COMPUTED"},
            {"Audit Theorem": "  - Total Non-Current Liabilities",
             "Value": f"PKR {report.total_non_current_liabilities:,.2f}", "Status": "COMPUTED"},
            {"Audit Theorem": "  - Total Current Liabilities",
             "Value": f"PKR {report.total_current_liabilities:,.2f}", "Status": "COMPUTED"},
            {"Audit Theorem": "  - Total Equity (including Net Profit)",
             "Value": f"PKR {report.total_equity:,.2f}", "Status": "COMPUTED"},
            {"Audit Theorem": "Net Profit / (Loss) for the Period",
             "Value": f"PKR {report.net_profit:,.2f}", "Status": "RECONCILED"},
            {"Audit Theorem": "Balance Sheet Identity (A = L + E)",
             "Value": f"Variance: PKR {report.bs_delta:,.2f}",
             "Status": "✅ TIED OUT" if report.is_bs_balanced else "❌ IMBALANCED"},
            {"Audit Theorem": "Zero Leakage (every account rendered)",
             "Value": f"{len(report.unassigned_accounts) + len(report.unrendered_accounts)} missing",
             "Status": "✅ PASSED" if report.zero_leakage_passed else "❌ FAILED"},
            {"Audit Theorem": "Disclosure Note Cross-Referencing",
             "Value": f"{len(compiled_notes)} notes, {len(report.note_mismatches)} mismatch(es)",
             "Status": "✅ PASSED" if report.notes_reconciled else "❌ FAILED"},
        ])

        for name in report.unassigned_accounts + report.unrendered_accounts:
            st.error(f"Leakage: {name}")
        for mismatch in report.note_mismatches:
            st.error(f"Note mismatch: {mismatch}")

        if audit_trail:
            st.markdown("#### ⚖️ Heuristic Balancing Actions Applied")
            st.table([
                {
                    "Heuristic": e.heuristic,
                    "Account": e.account_name,
                    "Action": e.action,
                    "Before (Dr / Cr)": f"{e.before_dr:,.2f} / {e.before_cr:,.2f}",
                    "After (Dr / Cr)": f"{e.after_dr:,.2f} / {e.after_cr:,.2f}",
                    "Explanation": e.explanation,
                }
                for e in audit_trail
            ])
        else:
            st.success("✅ Trial balance was already in parity; no heuristic adjustments were required.")

        st.markdown("#### 🏷️ Account Taxonomy Mappings")
        st.dataframe([
            {
                "Code": str(acc.account_code or ""),
                "Account Name": str(acc.account_name),
                "Mapped Line Item": str(acc.line_item_id or ""),
                "Note": f"Note {acc.note_number}" if acc.note_number else "-",
                "Confidence": f"{acc.confidence * 100:.0f}%",
                "Source": acc.classification_source,
                "Status": "Adjusted" if acc.is_adjusted else "Original",
                "Notes": str(acc.adjustment_reason or "Mapped autonomously"),
            }
            for acc in balanced_accounts
        ], use_container_width=True, height=350)

    with tab_tb:
        st.subheader("Cleaned Working Trial Balance")
        st.dataframe([
            {
                "Source Row": acc.tb_row_index or "",
                "Code": acc.account_code or "",
                "Account Title": acc.account_name,
                "Debit (PKR)": f"{acc.debit:,.2f}",
                "Credit (PKR)": f"{acc.credit:,.2f}",
            }
            for acc in balanced_accounts
        ], use_container_width=True, height=400)

    with tab_overrides:
        st.subheader("✏️ Review & Override Account Classifications")
        st.markdown("Inspect any auto-classified account and re-assign it to a different "
                    "Fifth Schedule line item or statutory Note:")

        line_item_options = {
            f"{li['stmt']} → {li['section']} → {li['label']}": (li["id"], li.get("note_number"))
            for li in get_line_items()
        }

        acc_names = [a.account_name for a in balanced_accounts]
        selected_acc_name = st.selectbox("Select Account to Inspect / Override:", acc_names)
        curr_acc = next((a for a in balanced_accounts if a.account_name == selected_acc_name), None)

        if curr_acc:
            col_ov1, col_ov2 = st.columns(2)
            col_ov1.write(f"**Current Balance:** Dr {curr_acc.debit:,.2f} | Cr {curr_acc.credit:,.2f}")
            col_ov1.write(f"**Current Line Item:** `{curr_acc.line_item_id}`")
            col_ov1.write(f"**Current Note:** Note {curr_acc.note_number or 'None'}")
            col_ov1.write(f"**Confidence:** {curr_acc.confidence * 100:.0f}% "
                          f"({curr_acc.classification_source})")

            selected_target_label = col_ov2.selectbox(
                "Change Target Classification to:", list(line_item_options.keys()))
            if col_ov2.button("Apply Override"):
                st.session_state["account_overrides"][selected_acc_name] = \
                    line_item_options[selected_target_label]
                st.rerun()

            if st.session_state["account_overrides"]:
                st.markdown("#### Active overrides")
                st.table([{"Account": k, "Line Item": v[0], "Note": v[1] or "-"}
                          for k, v in st.session_state["account_overrides"].items()])
                if st.button("Clear all overrides"):
                    st.session_state["account_overrides"] = {}
                    st.rerun()

except _CONTROL_FLOW:
    raise
except Exception as exc:
    st.error(f"Error compiling trial balance: {exc}")
finally:
    # The pipeline renames an unverified workbook, so clean up whichever
    # path actually ended up on disk as well as the ones we created.
    for temp_path in (tmp_in_path, tmp_out_path, produced_path):
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
