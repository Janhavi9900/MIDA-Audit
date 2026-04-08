import streamlit as st
import pandas as pd
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Import our universal document processor (RAG layer)
from document_processor import DocumentProcessor

# --- 1. CORE SETUP ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

MODEL_NAME = 'models/gemini-2.5-flash'
model = genai.GenerativeModel(MODEL_NAME)

# --- 2. PAGE CONFIG & UI ---
st.set_page_config(page_title="MIDA: Lab Deviation Audit Engine", layout="wide")

st.markdown("""
    <style>
        [data-testid="stSidebar"] { background-color: #000080; }
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label { color: #FFFFFF !important; }
        [data-testid="stSidebar"] textarea {
            color: #000000 !important;
            background-color: #FFFFFF !important;
        }
        .ingest-box {
            background: #f0f4ff;
            border: 1px solid #c5d0eb;
            border-left: 4px solid #0069CC;
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 13px;
            color: #2d3a5c;
            margin-bottom: 16px;
            line-height: 1.7;
        }
        .clash-card {
            background: #f8f9fc;
            border: 1px solid #dde3ef;
            border-left: 4px solid #e07b39;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 18px;
        }
        .clash-title {
            font-size: 15px;
            font-weight: 700;
            color: #1a2340;
            margin-bottom: 4px;
        }
        .clash-reason {
            font-size: 13px;
            color: #4a5568;
            margin-bottom: 10px;
        }
        .range-box {
            background: #eef2fb;
            border: 1px solid #c5d0eb;
            border-radius: 6px;
            padding: 10px 14px;
            font-size: 13px;
            color: #2d3a5c;
            margin-bottom: 12px;
            line-height: 1.6;
        }
        .range-box strong { color: #1a2340; }
        div[data-testid="stButton"] button[kind="primary"] {
            background-color: #0069CC !important;
            border-color: #0069CC !important;
            color: #ffffff !important;
            border-radius: 6px;
            font-weight: 600;
        }
        div[data-testid="stButton"] button[kind="secondary"] {
            background-color: #e8ecf2 !important;
            border-color: #c5ccd8 !important;
            color: #3a4560 !important;
            border-radius: 6px;
            font-weight: 500;
        }
        .stButton > button { width: 100%; border-radius: 6px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE INIT ---
defaults = {
    'step': 'upload',
    'resolutions': {},
    'clashes': [],
    'raw_df': None,
    'doc_names': [],
    'text_contents': [],
    'images_for_ai': [],
    'processor_summary': '',
    'used_rag': False,
    'csv_headers': [],
    'user_insights': '',
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🧠 Expert Instructions")
    st.session_state.user_insights = st.text_area(
        "Additional Constraints / Expert Notes:",
        value=st.session_state.user_insights,
        height=300,
        help="Any extra rules or context. Treated as a named document source."
    )
    if st.session_state.user_insights.strip():
        st.success("✔ Expert notes will be included as a named source")
    st.markdown("---")
    if st.session_state.processor_summary:
        st.markdown("**📁 Document Status**")
        st.text(st.session_state.processor_summary)

st.title("🧪 MIDA | Value-Aware Audit Engine")
st.caption("Universal lab compliance engine — any assay, any document size, any format.")

# ═══════════════════════════════════════════════════════════════
# STEP 1 — UPLOAD & DOCUMENT PROCESSING
# ═══════════════════════════════════════════════════════════════
if st.session_state.step == 'upload':

    col1, col2 = st.columns(2)
    with col1:
        csv_file = st.file_uploader(
            "📂 Upload Lab Results",
            type=["csv", "xlsx", "xls"],
            help="Any assay results file. CSV or Excel — any column structure."
        )
    with col2:
        doc_files = st.file_uploader(
            "📄 Upload Rule Documents",
            type=["pdf", "png", "jpg", "jpeg", "jfif", "webp", "bmp", "tiff", "docx", "pptx", "txt", "csv", "xlsx", "xls"],
            accept_multiple_files=True,
            help="SOPs, MOMs, client rules, handwritten notes, reference CSVs — any size, any combination."
        )

    if csv_file and doc_files:
        st.info(f"📎 {len(doc_files)} document(s) ready. Expert notes in sidebar count as an additional source.")

    if st.button("🚀 RUN ANALYSIS", type="primary"):
        if not csv_file:
            st.error("Please upload a lab results file.")
        elif not doc_files:
            st.error("Please upload at least one rule document.")
        else:
            progress = st.progress(0, text="Reading lab results...")

            # ── Read results file (CSV or Excel, any column structure) ──
            try:
                if csv_file.name.endswith(('.xlsx', '.xls')):
                    st.session_state.raw_df = pd.read_excel(csv_file)
                else:
                    st.session_state.raw_df = pd.read_csv(csv_file)
            except Exception as e:
                st.error(f"Could not read results file: {str(e)}")
                st.stop()

            st.session_state.csv_headers = list(st.session_state.raw_df.columns)

            progress.progress(15, text="Processing documents...")

            # ── Run document processor (handles RAG automatically) ──
            processor = DocumentProcessor(gemini_api_key=API_KEY)
            ingestion_result = processor.ingest_documents(
                uploaded_files=doc_files,
                expert_notes=st.session_state.user_insights.strip()
            )

            progress.progress(
                45,
                text="Building search index..." if ingestion_result['use_rag'] else "Preparing documents..."
            )

            # Build RAG query from CSV column headers
            rag_query = (
                f"compliance thresholds specifications limits acceptable ranges "
                f"for parameters: {', '.join(st.session_state.csv_headers)}"
            )

            # Get AI-ready content
            text_contents, doc_names = processor.get_content_for_ai(query=rag_query)
            images_for_ai = processor.get_images_for_ai()

            # Store everything in session state
            st.session_state.text_contents = text_contents
            st.session_state.images_for_ai = images_for_ai
            st.session_state.doc_names = doc_names
            st.session_state.used_rag = ingestion_result['use_rag']
            st.session_state.processor_summary = processor.get_status_summary()

            # Show what was ingested
            log_html = "<br>".join(ingestion_result['log'])
            st.markdown(f'<div class="ingest-box">{log_html}</div>', unsafe_allow_html=True)

            progress.progress(60, text="AI analysing clashes...")

            rag_note = (
                "Note: Only the most relevant sections from large documents are provided — use them carefully."
                if ingestion_result['use_rag'] else ""
            )

            clash_prompt = f"""
You are a senior lab compliance auditor. Analyse lab results against all provided rule documents.

DOCUMENT SOURCES: {json.dumps(doc_names)}
{rag_note}

LAB RESULTS (CSV — column names vary by assay, discover their meaning from context):
{st.session_state.raw_df.to_csv(index=False)}

INSTRUCTIONS:
1. Understand what each column represents — infer from data and document context. Do NOT assume names.
2. For each cell value per row, check it against ALL documents.
3. A CLASH exists ONLY when a value PASSES in one or more documents but FAILS in others.
4. If a value passes ALL → NOT a clash. If it fails ALL → NOT a clash (clear fail, handle in final audit).
5. Group documents that agree into the same group.
6. Extract EXACT threshold/rule with numbers and units from each document.
7. The unique identifier column is whichever column holds sample/batch/run IDs — discover it.

Return ONLY a JSON array:
[{{
  "id": "c1",
  "batch_id": "unique ID value",
  "parameter": "exact column name",
  "cell_value": "actual value from CSV",
  "clash_summary": "one sentence explaining the clash",
  "groups": [
    {{
      "documents": ["SOP.docx", "Client_Rules.pptx"],
      "stance": "PASS",
      "rule": "Parameter must be >= 95.0%. Value 95.8 meets this.",
      "threshold": ">= 95.0%"
    }},
    {{
      "documents": ["MOM.pdf"],
      "stance": "FAIL",
      "rule": "Parameter must be >= 96.5%. Value 95.8 does NOT meet this.",
      "threshold": ">= 96.5%"
    }}
  ]
}}]

Return [] if no clashes. No markdown, no explanation — ONLY the JSON array.
"""
            try:
                response = model.generate_content(
                    [clash_prompt] + text_contents + images_for_ai
                )
                raw = response.text.replace("```json", "").replace("```", "").strip()
                st.session_state.clashes = json.loads(raw)
                progress.progress(100, text="Analysis complete.")

                if not st.session_state.clashes:
                    st.session_state.step = 'results'
                else:
                    st.session_state.step = 'clash_check'
                st.rerun()

            except Exception as e:
                st.error(f"Analysis error: {str(e)}")
                progress.empty()

# ═══════════════════════════════════════════════════════════════
# STEP 2 — CLASH RESOLUTION
# ═══════════════════════════════════════════════════════════════
elif st.session_state.step == 'clash_check':

    st.subheader("⚠️ Conflict Resolution Required")
    st.markdown(
        "Values found that **pass in some documents but fail in others**. "
        "Review the ranges and select the **source of truth** for each clash."
    )
    if st.session_state.used_rag:
        st.info("ℹ️ RAG mode active — large documents were searched for relevant sections only.")
    st.markdown("---")

    total = len(st.session_state.clashes)
    resolved = len(st.session_state.resolutions)
    st.progress(
        resolved / total if total > 0 else 0,
        text=f"{resolved} of {total} clashes resolved"
    )
    st.markdown("")

    for clash in st.session_state.clashes:
        cid = clash["id"]
        batch = clash.get("batch_id", "Unknown")
        param = clash.get("parameter", "")
        value = clash.get("cell_value", "")
        summary = clash.get("clash_summary", "")
        groups = clash.get("groups", [])

        st.markdown(f"""
        <div class="clash-card">
            <div class="clash-title">
                {batch} &nbsp;·&nbsp; {param} &nbsp;·&nbsp; Value: <code>{value}</code>
            </div>
            <div class="clash-reason">{summary}</div>
        </div>
        """, unsafe_allow_html=True)

        range_lines = []
        for g in groups:
            docs_str = " + ".join(g.get("documents", []))
            icon = "✅" if g.get("stance") == "PASS" else "❌"
            range_lines.append(
                f"{icon} <strong>{docs_str}</strong> — {g.get('rule', '')} "
                f"<em>(threshold: {g.get('threshold', '')})</em>"
            )
        st.markdown(
            f'<div class="range-box">{"<br>".join(range_lines)}</div>',
            unsafe_allow_html=True
        )

        st.markdown("**Select your source of truth for this clash:**")
        if groups:
            cols = st.columns(len(groups))
            for idx, grp in enumerate(groups):
                btn_label = "Go with " + " + ".join(grp.get("documents", []))
                is_selected = st.session_state.resolutions.get(cid) == btn_label
                with cols[idx]:
                    if st.button(
                        btn_label,
                        key=f"btn_{cid}_{idx}",
                        type="primary" if is_selected else "secondary",
                        use_container_width=True
                    ):
                        if is_selected:
                            st.session_state.resolutions.pop(cid, None)
                        else:
                            st.session_state.resolutions[cid] = btn_label
                        st.rerun()

        if cid in st.session_state.resolutions:
            st.success(f"✔ Selected: {st.session_state.resolutions[cid]}")
        else:
            st.warning("No selection yet — please pick a source of truth above.")
        st.markdown("---")

    all_resolved = len(st.session_state.resolutions) >= total
    col_a, col_b = st.columns([3, 1])
    with col_a:
        if st.button(
            "✅ FINALISE AUDIT & GENERATE REPORT",
            type="primary",
            disabled=not all_resolved
        ):
            st.session_state.step = 'results'
            st.rerun()
    with col_b:
        if st.button("🔄 Start Over", type="secondary"):
            for key in list(defaults.keys()):
                st.session_state.pop(key, None)
            st.rerun()
    if not all_resolved:
        st.warning(f"Please resolve all {total} clashes before finalising.")

# ═══════════════════════════════════════════════════════════════
# STEP 3 — FINAL AUDIT REPORT
# ═══════════════════════════════════════════════════════════════
elif st.session_state.step == 'results':

    st.subheader("📋 MIDA Audit Report")

    with st.spinner("Applying selected rules and generating final audit..."):

        final_prompt = f"""
You are a Lead Lab Auditor generating a final compliance report.

USER RESOLUTIONS (source of truth chosen per clash):
{json.dumps(st.session_state.resolutions)}

LAB RESULTS:
{st.session_state.raw_df.to_csv(index=False)}

EXPERT NOTES:
{st.session_state.user_insights.strip() if st.session_state.user_insights.strip() else "None provided."}

AUDIT RULES:
1. AND LOGIC — A row PASSES only if ALL parameters pass the selected source of truth.
   One failing parameter = whole row FAILS regardless of other parameters.
2. Discover the unique identifier column from the data — do not assume the name.
3. STATUS VALUES:
   - "VERIFIED" — all parameters pass the SOP
   - "JUSTIFIED" — parameter failed SOP but passed selected exception document
   - "FAIL" — one or more parameters fail the selected source of truth
4. MIDA_Inference/Comments must name every parameter that passed and failed,
   with exact values and thresholds. Confirm AND logic was applied.
5. Return ONLY a JSON array, one object per CSV row, same order:
[{{"MIDA_Audit_Status": "VERIFIED"|"JUSTIFIED"|"FAIL", "MIDA_Inference/Comments": "..."}}]

No markdown — ONLY the JSON array.
"""
        try:
            response = model.generate_content(
                [final_prompt] + st.session_state.text_contents + st.session_state.images_for_ai
            )
            raw = response.text.replace("```json", "").replace("```", "").strip()
            results_json = json.loads(raw)

            audit_df = pd.DataFrame(results_json)
            final_df = pd.concat(
                [st.session_state.raw_df.reset_index(drop=True), audit_df],
                axis=1
            )

            total_rows = len(final_df)
            verified = (final_df["MIDA_Audit_Status"] == "VERIFIED").sum()
            justified = (final_df["MIDA_Audit_Status"] == "JUSTIFIED").sum()
            failed = (final_df["MIDA_Audit_Status"] == "FAIL").sum()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Samples", total_rows)
            c2.metric("✅ Verified", int(verified))
            c3.metric("⚠️ Justified", int(justified))
            c4.metric("❌ Failed", int(failed))
            st.markdown("---")

            def colour_status(val):
                if val == "VERIFIED":
                    return "background-color: #d4edda; color: #155724; font-weight: bold;"
                elif val == "JUSTIFIED":
                    return "background-color: #fff3cd; color: #856404; font-weight: bold;"
                elif val == "FAIL":
                    return "background-color: #f8d7da; color: #721c24; font-weight: bold;"
                return ""

            styled = final_df.style.map(colour_status, subset=["MIDA_Audit_Status"])
            st.dataframe(styled, use_container_width=True, hide_index=True)

            if st.session_state.resolutions:
                with st.expander("📌 Clash Resolutions Applied"):
                    for clash in st.session_state.clashes:
                        cid = clash["id"]
                        chosen = st.session_state.resolutions.get(cid, "—")
                        st.markdown(
                            f"**{clash.get('batch_id')} · {clash.get('parameter')}** "
                            f"(value: `{clash.get('cell_value')}`) → {chosen}"
                        )

            with st.expander("⚙️ Processing Details"):
                st.text(st.session_state.processor_summary)

            csv_output = final_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 DOWNLOAD FULL AUDIT TRAIL (CSV)",
                data=csv_output,
                file_name="MIDA_Audit_Report.csv",
                mime="text/csv",
                type="primary"
            )

        except Exception as e:
            st.error(f"Report generation failed: {str(e)}")
            st.info("Try running the analysis again — Gemini occasionally returns malformed JSON.")

    st.markdown("---")
    if st.button("🔄 START NEW AUDIT", type="secondary"):
        for key in list(defaults.keys()):
            st.session_state.pop(key, None)
        st.rerun()
