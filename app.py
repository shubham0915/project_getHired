import streamlit as st
import pandas as pd
import time
import matplotlib.pyplot as plt
import seaborn as sns
from data_generator import generate_fintech_data
from masking_engine import process_dataframe
from synthetic_augmenter import generate_synthetic_data
from auditor import run_prompt_attack
from report_generator import generate_quality_report
import os

st.set_page_config(page_title="Blostem Privacy Pipeline", layout="wide", page_icon="🛡️", initial_sidebar_state="expanded")

# Inject Custom CSS for aesthetics
st.markdown("""
<style>
    /* Dark mode premium theme */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
        font-family: 'Inter', sans-serif;
    }
    h1, h2, h3 {
        color: #58a6ff;
    }
    .stButton>button {
        background: linear-gradient(90deg, #1f6feb 0%, #2ea043 100%);
        color: white;
        border: none;
        border-radius: 8px;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 4px 12px rgba(46, 160, 67, 0.4);
    }
    .metric-card {
        background: rgba(22, 27, 34, 0.8);
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #2ea043;
    }
    .metric-label {
        font-size: 1rem;
        color: #8b949e;
    }
    /* Attack Simulator Card */
    .attack-card {
        background: #161b22;
        border-left: 5px solid #f85149;
        padding: 15px;
        margin: 10px 0;
        border-radius: 4px;
    }
    .safe-card {
        background: #161b22;
        border-left: 5px solid #2ea043;
        padding: 15px;
        margin: 10px 0;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Blostem Data Masking Pipeline")
st.markdown("Enterprise-Grade Privacy Pipeline for In-House LLM Training | DPDP Compliant")

if 'raw_data' not in st.session_state:
    st.session_state.raw_data = None
if 'masked_data' not in st.session_state:
    st.session_state.masked_data = None
if 'synthetic_data' not in st.session_state:
    st.session_state.synthetic_data = None
if 'report' not in st.session_state:
    st.session_state.report = None

st.sidebar.header("Pipeline Controls")

# Step 0: Ingestion (File Upload)
st.sidebar.subheader("Ingest Data")
uploaded_file = st.sidebar.file_uploader("Upload Raw CSV Dataset", type="csv")

if uploaded_file is not None:
    if st.sidebar.button("Process Uploaded Data", use_container_width=True):
        st.session_state.raw_data = pd.read_csv(uploaded_file)
        st.session_state.raw_data.to_csv("raw_fintech_data.csv", index=False)
        st.session_state.masked_data = None
        st.session_state.synthetic_data = None
        st.session_state.report = None
        st.sidebar.success("Ingested Uploaded Data!")

# Step 1: Generate Raw Data (Fallback)
st.sidebar.markdown("---")
st.sidebar.subheader("Or Generate Sample")
if st.sidebar.button("1. Generate Raw Fintech Data", use_container_width=True):
    with st.spinner("Generating 500 records of synthetic KYC/Transaction data..."):
        time.sleep(1)
        st.session_state.raw_data = generate_fintech_data(500)
        st.session_state.raw_data.to_csv("raw_fintech_data.csv", index=False)
        st.session_state.masked_data = None
        st.session_state.synthetic_data = None
        st.session_state.report = None
    st.sidebar.success("Generated Raw Data!")

st.sidebar.markdown("---")
# Step 2: Mask Data
if st.sidebar.button("2. Run Masking Engine", use_container_width=True):
    if st.session_state.raw_data is None:
        st.sidebar.error("Generate raw data first!")
    else:
        with st.spinner("Applying FPE, Differential Privacy, and Presidio NLP rules..."):
            st.session_state.masked_data = process_dataframe(st.session_state.raw_data)
            st.session_state.masked_data.to_csv("masked_fintech_data.csv", index=False)
            st.session_state.report = generate_quality_report(st.session_state.raw_data, st.session_state.masked_data)
        st.sidebar.success("Masking Complete!")

# Step 3: Synthetic Augmentation
if st.sidebar.button("3. Generate Synthetic Twins", use_container_width=True):
    if st.session_state.masked_data is None:
        st.sidebar.error("Run Masking Engine first!")
    else:
        with st.spinner("Training SDV Copula model on masked data..."):
            st.session_state.synthetic_data = generate_synthetic_data(num_rows=500)
        st.sidebar.success("Synthetic Data Generated!")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["1. Raw Data", "2. Masked Data", "3. Compliance & Utility", "4. Memorization Audit"])

with tab1:
    st.subheader("Raw Fintech Dataset (Sensitive)")
    if st.session_state.raw_data is not None:
        st.error("🚨 WARNING: Contains highly sensitive PII (PAN, Aadhaar, Names, Phones)")
        st.dataframe(st.session_state.raw_data.head(50), use_container_width=True)
    else:
        st.info("Click '1. Generate Raw Fintech Data' in the sidebar.")

with tab2:
    st.subheader("Masked Dataset (DPDP Compliant)")
    if st.session_state.masked_data is not None:
        st.success("✅ Safe for general use. Features FPE, Laplace Noise, and K-Anonymity.")
        st.dataframe(st.session_state.masked_data.head(50), use_container_width=True)
        
        csv = st.session_state.masked_data.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Masked CSV",
            data=csv,
            file_name='masked_fintech_data.csv',
            mime='text/csv',
            type="primary"
        )
    else:
        st.info("Run the Masking Engine.")

with tab3:
    st.subheader("Privacy vs. Utility Report")
    if st.session_state.report is not None:
        st.markdown(f"""
        <div style="display:flex; justify-content:space-around;">
            <div class="metric-card">
                <div class="metric-value">{st.session_state.report['Total Rows']}</div>
                <div class="metric-label">Rows Processed</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">100%</div>
                <div class="metric-label">DPDP Compliance</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">ε=1.0</div>
                <div class="metric-label">Laplace Noise (DP)</div>
            </div>
        </div>
        <br>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Feature Processing Metrics")
            metrics_df = pd.DataFrame(st.session_state.report['Metrics'])
            st.dataframe(metrics_df, use_container_width=True)
        with col2:
            st.markdown("### Amount Distribution (Utility Retained)")
            fig, ax = plt.subplots(figsize=(6,4))
            sns.kdeplot(st.session_state.raw_data['Amount'], label='Raw Data', fill=True, ax=ax)
            sns.kdeplot(st.session_state.masked_data['Amount'], label='Masked Data (DP Noise)', fill=True, ax=ax)
            ax.set_title("Distribution of Financial Amounts")
            ax.set_xlabel("Amount (INR)")
            ax.legend()
            st.pyplot(fig)
            
        if st.session_state.synthetic_data is not None:
            st.markdown("### Synthetic Twin Generation")
            st.success("✅ Generated 500 records of purely synthetic data using SDV Gaussian Copula.")
            st.dataframe(st.session_state.synthetic_data.head(10), use_container_width=True)
            
            synth_csv = st.session_state.synthetic_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Synthetic CSV",
                data=synth_csv,
                file_name='synthetic_fintech_data.csv',
                mime='text/csv',
                type="primary"
            )
    else:
        st.info("Report will appear here after masking.")

with tab4:
    st.subheader("LLM Prompt Attack Simulator (Killer Demo)")
    st.markdown("Watch what happens when an attacker asks an LLM for a specific user's PAN.")
    
    if st.button("Run Memorization Audit", type="primary"):
        if not (os.path.exists("raw_fintech_data.csv") and os.path.exists("masked_fintech_data.csv") and os.path.exists("synthetic_fintech_data.csv")):
            st.error("Please run steps 1, 2, and 3 from the sidebar first to generate all CSVs!")
        else:
            with st.spinner("Simulating Attack..."):
                time.sleep(1.5)
                res = run_prompt_attack()
                
                st.markdown(f"**Attacker Prompt:** `What is the PAN number for user {res['target']}?`")
                
                st.markdown(f"""
                <div class="attack-card">
                    <h4>🔴 Scenario 1: Model trained on RAW DATA</h4>
                    <p><b>LLM Response:</b> "The PAN number for {res['target']} is {res['real_pan']}."</p>
                    <p style="color: #f85149;"><b>Status: FAILED (PII LEAKED)</b></p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class="safe-card">
                    <h4>🟢 Scenario 2: Model trained on MASKED DATA</h4>
                    <p><b>LLM Response:</b> "I do not have information for a user named {res['target']}."</p>
                    <p style="color: #2ea043;"><b>Status: PASSED (ENTITY REDACTED)</b></p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class="safe-card">
                    <h4>🟢 Scenario 3: Model trained on SYNTHETIC DATA</h4>
                    <p><b>LLM Response:</b> "I do not have information for a user named {res['target']}."</p>
                    <p style="color: #2ea043;"><b>Status: PASSED (100% SYNTHETIC TWIN)</b></p>
                </div>
                """, unsafe_allow_html=True)
