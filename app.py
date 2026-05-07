"""
Blostem Data Masking Pipeline v4 — Streamlit Dashboard

Enterprise-grade multi-layer PII detection & masking with:
- Tab 1: Raw Data viewer
- Tab 2: Masked Data + multi-format export (CSV, JSONL, Parquet)
- Tab 3: PII Manifest visualization  
- Tab 4: Privacy vs Utility Report
- Tab 5: Real PII Leakage Auditor + Attack Simulator
- Tab 6: Free-Text Masking (unstructured data support)
"""

import streamlit as st
import pandas as pd
import time
import json
import io
import matplotlib.pyplot as plt
import seaborn as sns
from data_generator import generate_fintech_data
from core.pipeline import MaskingPipeline, mask_text
from auditor import audit_leakage, run_attack_simulation
from report_generator import generate_quality_report
import os

st.set_page_config(
    page_title="Blostem Privacy Pipeline v4", 
    layout="wide", 
    page_icon="🛡️", 
    initial_sidebar_state="expanded"
)






# --- Premium Dark Theme CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #0d1117; color: #c9d1d9; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { color: #58a6ff; }
    .stButton>button {
        background: linear-gradient(135deg, #1f6feb 0%, #238636 100%);
        color: white; border: none; border-radius: 8px;
        transition: transform 0.2s, box-shadow 0.2s;
        font-weight: 600;
    }
    .stButton>button:hover { transform: scale(1.02); box-shadow: 0 4px 16px rgba(31,111,235,0.4); }
    .metric-card {
        background: rgba(22,27,34,0.9); border: 1px solid #30363d;
        border-radius: 12px; padding: 20px; text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        transition: transform 0.2s;
    }
    .metric-card:hover { transform: translateY(-2px); }
    .metric-value { font-size: 2rem; font-weight: 700; color: #2ea043; }
    .metric-label { font-size: 0.9rem; color: #8b949e; margin-top: 4px; }
    .severity-critical { color: #f85149; font-weight: 700; }
    .severity-high { color: #d29922; font-weight: 600; }
    .severity-medium { color: #58a6ff; }
    .severity-low { color: #8b949e; }
    .manifest-box {
        background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 16px; margin: 8px 0;
    }
    .attack-card {
        background: #161b22; border-left: 5px solid #f85149;
        padding: 15px; margin: 10px 0; border-radius: 4px;
    }
    .safe-card {
        background: #161b22; border-left: 5px solid #2ea043;
        padding: 15px; margin: 10px 0; border-radius: 4px;
    }
    .pipeline-badge {
        display: inline-block; padding: 4px 12px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600; margin: 2px;
    }
    .badge-regex { background: #1f6feb33; color: #58a6ff; border: 1px solid #1f6feb; }
    .badge-gliner { background: #8957e533; color: #d2a8ff; border: 1px solid #8957e5; }
    .badge-clean { background: #2ea04333; color: #2ea043; border: 1px solid #2ea043; }
    .badge-review { background: #d2992233; color: #d29922; border: 1px solid #d29922; }
    .leakage-zero { background: #2ea04322; border: 2px solid #2ea043; border-radius: 12px; padding: 20px; text-align: center; }
    .text-mask-result { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin: 8px 0; font-family: monospace; white-space: pre-wrap; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Blostem Data Masking Pipeline v4")
st.markdown("**Enterprise-Grade Multi-Layer PII Detection** — Regex → GLiNER NER → Validation | DPDP Compliant | Gender-Aware Indian Names")

# --- Session State ---
for key in ['raw_data', 'masked_data', 'manifest', 'report', 'audit_results']:
    if key not in st.session_state:
        st.session_state[key] = None

# --- Sidebar ---
st.sidebar.header("🎛️ Pipeline Controls")

enable_ner = st.sidebar.checkbox("Enable GLiNER NER (Layer 2)", value=False,
    help="Enables context-aware name/address detection. Requires ~1.2GB model download on first run.")

ner_model = st.sidebar.selectbox("NER Model", 
    ["urchade/gliner_multi_pii-v1", "nvidia/gliner-PII"],
    index=0,
    help="Select the GLiNER model to use. NVIDIA model is faster and optimized for English PII.",
    disabled=not enable_ner)

st.sidebar.subheader("📥 Ingest Data")
uploaded_file = st.sidebar.file_uploader("Upload Raw CSV", type="csv")

if uploaded_file is not None:
    if st.sidebar.button("Process Upload", use_container_width=True):
        st.session_state.raw_data = pd.read_csv(uploaded_file)
        for k in ['masked_data', 'report', 'manifest', 'audit_results']:
            st.session_state[k] = None
        st.sidebar.success("✅ Data ingested!")

st.sidebar.markdown("---")
st.sidebar.subheader("📝 Or Paste Data")
pasted_data = st.sidebar.text_area("Paste JSON or CSV (e.g. \"Name\": \"Rajesh\")", height=150)
if st.sidebar.button("Process Pasted Data", use_container_width=True):
    if pasted_data.strip():
        try:
            import io
            import ast
            text = pasted_data.strip()
            df = None
            
            # 1. Try strict JSON (list or object)
            if text.startswith('{') or text.startswith('['):
                parsed = json.loads(text)
                df = pd.DataFrame([parsed] if isinstance(parsed, dict) else parsed)
            
            # 2. Try wrapping in {} (if user pasted raw key-values)
            if df is None and ':' in text:
                try:
                    parsed = json.loads(f"{{{text}}}")
                    df = pd.DataFrame([parsed])
                except:
                    try:
                        # Sometimes it's Python dict format without quotes on keys or with trailing commas
                        parsed = ast.literal_eval(f"{{{text}}}")
                        df = pd.DataFrame([parsed])
                    except:
                        pass
            
            # 3. Fallback to CSV
            if df is None:
                df = pd.read_csv(io.StringIO(text))
                
            st.session_state.raw_data = df
            for k in ['masked_data', 'report', 'manifest', 'audit_results']:
                st.session_state[k] = None
            st.sidebar.success("✅ Pasted data ingested!")
        except Exception as e:
            st.sidebar.error(f"❌ Failed to parse data. Try standard CSV or JSON format. Error: {e}")
    else:
        st.sidebar.warning("Please paste some data first.")

st.sidebar.markdown("---")
st.sidebar.subheader("🎲 Or Generate Sample")
num_records = st.sidebar.slider("Records", 50, 1000, 200, step=50)
if st.sidebar.button("1. Generate Raw Data", use_container_width=True):
    with st.spinner(f"Generating {num_records} records..."):
        st.session_state.raw_data = generate_fintech_data(num_records)
        for k in ['masked_data', 'report', 'manifest', 'audit_results']:
            st.session_state[k] = None
    st.sidebar.success("✅ Generated!")

st.sidebar.markdown("---")
if st.sidebar.button("2. Run Masking Pipeline", use_container_width=True, type="primary"):
    if st.session_state.raw_data is None:
        st.sidebar.error("Generate or upload data first!")
    else:
        with st.spinner("Running multi-layer masking pipeline..."):
            pipeline = MaskingPipeline(enable_ner=enable_ner, gliner_model_override=ner_model)
            masked_df, manifest = pipeline.process(st.session_state.raw_data)
            st.session_state.masked_data = masked_df
            st.session_state.manifest = manifest.to_safe_dict()
            
            # Save CSVs for auditor
            st.session_state.raw_data.to_csv("raw_fintech_data.csv", index=False)
            masked_df.to_csv("masked_fintech_data.csv", index=False)
            
            # Generate report with manifest
            st.session_state.report = generate_quality_report(
                st.session_state.raw_data, masked_df, st.session_state.manifest)
            
            # Run leakage audit automatically
            st.session_state.audit_results = audit_leakage(
                st.session_state.raw_data, masked_df)
        st.sidebar.success("✅ Masking complete!")

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "1. Raw Data", "2. Masked Data", "3. PII Manifest",
    "4. Utility Report", "5. Leakage Audit", "6. Text Masking"
])

# === TAB 1: Raw Data ===
with tab1:
    st.subheader("📋 Raw Dataset (Sensitive)")
    if st.session_state.raw_data is not None:
        st.error("🚨 **WARNING:** Contains PII — PAN, Aadhaar, Names, Phones, Emails")
        st.dataframe(st.session_state.raw_data.head(50), use_container_width=True)
        st.caption(f"Showing 50 of {len(st.session_state.raw_data)} rows")
    else:
        st.info("👈 Generate or upload data from the sidebar.")

# === TAB 2: Masked Data + Multi-Format Export ===
with tab2:
    st.subheader("🔒 Masked Dataset")
    if st.session_state.masked_data is not None:
        m = st.session_state.manifest
        if m and m.get('final_clean'):
            st.success("✅ **Validation CLEAN** — All PII masked, safe for downstream use.")
        else:
            st.warning("⚠️ Validation incomplete — manual review recommended.")
        
        st.dataframe(st.session_state.masked_data.head(50), use_container_width=True)
        
        # --- Gap 6: Multi-format export ---
        st.markdown("### 📥 Export Masked Data")
        exp_col1, exp_col2, exp_col3, exp_col4 = st.columns(4)
        
        with exp_col1:
            csv_data = st.session_state.masked_data.to_csv(index=False).encode('utf-8')
            st.download_button("📄 CSV", data=csv_data,
                file_name='masked_data.csv', mime='text/csv', 
                use_container_width=True)
        
        with exp_col2:
            jsonl_data = st.session_state.masked_data.to_json(
                orient='records', lines=True).encode('utf-8')
            st.download_button("📋 JSONL (LLM Fine-tuning)", data=jsonl_data,
                file_name='masked_data.jsonl', mime='application/jsonl',
                use_container_width=True)
        
        with exp_col3:
            parquet_buffer = io.BytesIO()
            st.session_state.masked_data.to_parquet(parquet_buffer, index=False)
            st.download_button("🗂️ Parquet (Data Eng)", data=parquet_buffer.getvalue(),
                file_name='masked_data.parquet', mime='application/octet-stream',
                use_container_width=True)
        
        with exp_col4:
            if st.session_state.manifest:
                manifest_json = json.dumps(st.session_state.manifest, 
                                          indent=2, default=str).encode('utf-8')
                st.download_button("📊 Manifest JSON", data=manifest_json,
                    file_name='pii_manifest.json', mime='application/json',
                    use_container_width=True)
    else:
        st.info("Run the masking pipeline first.")

# === TAB 3: PII Manifest ===
with tab3:
    st.subheader("📊 PII Detection Manifest")
    if st.session_state.manifest is not None:
        m = st.session_state.manifest
        
        # Top-level metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value">{m.get('total_pii_detected', 0)}</div>
                <div class="metric-label">PII Detected</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            clean = m.get('final_clean', False)
            badge = "badge-clean" if clean else "badge-review"
            label = "CLEAN" if clean else "REVIEW"
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value"><span class="pipeline-badge {badge}">{label}</span></div>
                <div class="metric-label">Validation Status</div>
            </div>""", unsafe_allow_html=True)
        with col3:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value">{m.get('processing_time_seconds', 0)}s</div>
                <div class="metric-label">Processing Time</div>
            </div>""", unsafe_allow_html=True)
        with col4:
            passes = m.get('validation_passes', [])
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value">{len(passes)}</div>
                <div class="metric-label">Validation Passes</div>
            </div>""", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Breakdown charts
        det_col1, det_col2, det_col3 = st.columns(3)
        
        with det_col1:
            st.markdown("### By PII Type")
            by_type = m.get('detection_by_type', {})
            if by_type:
                df_type = pd.DataFrame(list(by_type.items()), columns=['Type', 'Count'])
                df_type = df_type.sort_values('Count', ascending=True)
                fig, ax = plt.subplots(figsize=(6, max(3, len(df_type)*0.4)))
                ax.barh(df_type['Type'], df_type['Count'], color='#1f6feb')
                ax.set_facecolor('#0d1117')
                fig.set_facecolor('#0d1117')
                ax.tick_params(colors='#c9d1d9')
                ax.spines['bottom'].set_color('#30363d')
                ax.spines['left'].set_color('#30363d')
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                st.pyplot(fig)
        
        with det_col2:
            st.markdown("### By Severity")
            by_sev = m.get('detection_by_severity', {})
            if by_sev:
                colors_map = {'CRITICAL': '#f85149', 'HIGH': '#d29922',
                              'MEDIUM': '#58a6ff', 'LOW': '#8b949e'}
                labels = list(by_sev.keys())
                sizes = list(by_sev.values())
                colors = [colors_map.get(l, '#8b949e') for l in labels]
                fig, ax = plt.subplots(figsize=(5, 4))
                ax.pie(sizes, labels=labels, colors=colors, autopct='%1.0f%%',
                       textprops={'color': '#c9d1d9', 'fontsize': 10})
                fig.set_facecolor('#0d1117')
                st.pyplot(fig)
        
        with det_col3:
            st.markdown("### By Detector")
            by_det = m.get('detection_by_detector', {})
            if by_det:
                for det, count in by_det.items():
                    badge_class = "badge-regex" if det == "REGEX" else "badge-gliner"
                    st.markdown(f"""<span class="pipeline-badge {badge_class}">{det}</span> 
                        **{count}** detections""", unsafe_allow_html=True)
            
            st.markdown("### Validation Passes")
            for vp in m.get('validation_passes', []):
                icon = "✅" if vp['is_clean'] else "🔄"
                st.markdown(f"{icon} Pass {vp['pass_number']}: **{vp['pii_found']}** leaks found")
        
        # Raw manifest JSON
        with st.expander("📄 Raw Manifest JSON"):
            st.json(m)
    else:
        st.info("Run the masking pipeline to generate the manifest.")

# === TAB 4: Utility Report ===
with tab4:
    st.subheader("📈 Privacy vs. Utility Report")
    if st.session_state.report is not None:
        report = st.session_state.report
        
        # Score cards
        score_col1, score_col2, score_col3 = st.columns(3)
        with score_col1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value">{report.get('Privacy Score', 0)}%</div>
                <div class="metric-label">Privacy Score (PII Changed)</div>
            </div>""", unsafe_allow_html=True)
        with score_col2:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value">{report.get('Utility Score', 0)}%</div>
                <div class="metric-label">Utility Score (Distribution Preserved)</div>
            </div>""", unsafe_allow_html=True)
        with score_col3:
            shape_ok = "✅" if report.get('Data Shape Preserved') else "❌"
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value">{shape_ok}</div>
                <div class="metric-label">Data Shape Preserved</div>
            </div>""", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Feature Processing Metrics")
            metrics_df = pd.DataFrame(report['Metrics'])
            st.dataframe(metrics_df, use_container_width=True)
        with col2:
            st.markdown("### Amount Distribution (Utility Check)")
            if st.session_state.raw_data is not None and 'Amount' in st.session_state.raw_data.columns:
                fig, ax = plt.subplots(figsize=(6, 4))
                sns.kdeplot(st.session_state.raw_data['Amount'], label='Raw', fill=True, ax=ax, color='#f85149')
                sns.kdeplot(st.session_state.masked_data['Amount'], label='Masked (DP)', fill=True, ax=ax, color='#2ea043')
                ax.set_facecolor('#0d1117')
                fig.set_facecolor('#0d1117')
                ax.tick_params(colors='#c9d1d9')
                ax.legend(facecolor='#161b22', edgecolor='#30363d', labelcolor='#c9d1d9')
                ax.set_xlabel("Amount (INR)", color='#c9d1d9')
                ax.spines['bottom'].set_color('#30363d')
                ax.spines['left'].set_color('#30363d')
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                st.pyplot(fig)
        
        # Manifest summary if available
        if 'Manifest Summary' in report:
            with st.expander("📊 Manifest Summary"):
                ms = report['Manifest Summary']
                st.json(ms)
    else:
        st.info("Report appears after masking.")

# === TAB 5: Leakage Audit + Attack Simulator ===
with tab5:
    st.subheader("🔍 PII Leakage Audit & Attack Simulator")
    
    if st.session_state.audit_results is not None:
        audit = st.session_state.audit_results
        
        # Verdict banner
        if audit['total_leaks_found'] == 0:
            st.markdown(f"""<div class="leakage-zero">
                <h2 style="color: #2ea043; margin: 0;">🛡️ ZERO LEAKAGE</h2>
                <p style="color: #8b949e; margin: 5px 0 0 0;">
                    {audit['total_pii_values_checked']} PII values checked — none found in masked output
                </p>
            </div>""", unsafe_allow_html=True)
        else:
            st.error(f"⚠️ {audit['total_leaks_found']} leaks found out of {audit['total_pii_values_checked']} values checked")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Per-column breakdown
        st.markdown("### Per-Column Leakage Report")
        audit_rows = []
        for col, stats in audit['columns'].items():
            audit_rows.append({
                "Column": col,
                "Unique Values": stats['total_unique_values'],
                "Leaks": stats['leaks_found'],
                "Effectiveness": stats['masking_effectiveness'],
                "Status": stats['status'],
            })
        st.dataframe(pd.DataFrame(audit_rows), use_container_width=True)
        
        # Attack simulation
        st.markdown("---")
        st.markdown("### 🎯 Targeted Attack Simulation")
        st.markdown("Simulates an attacker querying for a specific person's PII.")
        
        if st.button("🚀 Run Attack Simulation", type="primary"):
            with st.spinner("Simulating targeted attack..."):
                attack = run_attack_simulation()
            
            st.markdown(f"**Target:** `{attack['target_name']}` (Row {attack['target_row']})")
            
            for check in attack['checks']:
                if check['found_in_masked']:
                    st.markdown(f"""<div class="attack-card">
                        <b>{check['field']}</b>: <code>{check['raw_value'][:6]}***</code> — 
                        <span class="severity-critical">❌ FOUND in masked data</span>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""<div class="safe-card">
                        <b>{check['field']}</b>: <code>{check['raw_value'][:6]}***</code> — 
                        <span style="color:#2ea043;">✅ NOT found in masked data</span>
                    </div>""", unsafe_allow_html=True)
            
            if attack['all_passed']:
                st.success("✅ **ALL CHECKS PASSED** — This person's PII is completely unrecoverable from masked data.")
            else:
                st.error("❌ Some PII was found in masked output. Pipeline needs investigation.")
    else:
        st.info("Run the masking pipeline — leakage audit runs automatically.")

# === TAB 6: Free-Text Masking ===
with tab6:
    st.subheader("📝 Free-Text PII Masking")
    st.markdown("""
    Paste any unstructured text — logs, emails, support tickets, documents — and 
    the pipeline will detect and mask all PII in real-time.
    """)
    
    sample_text = """Dear Sir, my name is Rajesh Kumar and my PAN is ABCDE1234F. 
Please transfer Rs 50000 to my account. My Aadhaar is 234567891234 
and email is rajesh.kumar@gmail.com. Call me at +91 9876543210.
My UPI is rajesh@ybl. IFSC code is SBIN0001234."""
    
    input_text = st.text_area(
        "Paste text containing PII:",
        value=sample_text,
        height=150,
        placeholder="Enter text with PII like PAN, Aadhaar, phone, email..."
    )
    
    if st.button("🔒 Mask Text", type="primary"):
        if input_text.strip():
            with st.spinner("Scanning and masking..."):
                result = mask_text(input_text, enable_ner=enable_ner, gliner_model_override=ner_model)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 🔴 Original Text")
                st.markdown(f'<div class="text-mask-result" style="border-left: 4px solid #f85149;">{input_text}</div>', 
                           unsafe_allow_html=True)
            with col2:
                st.markdown("### 🟢 Masked Text")
                st.markdown(f'<div class="text-mask-result" style="border-left: 4px solid #2ea043;">{result["masked_text"]}</div>', 
                           unsafe_allow_html=True)
            
            st.markdown(f"### 📊 {result['pii_count']} PII Entities Detected")
            if result['detections']:
                det_df = pd.DataFrame(result['detections'])
                st.dataframe(det_df, use_container_width=True)
        else:
            st.warning("Please enter some text to mask.")
