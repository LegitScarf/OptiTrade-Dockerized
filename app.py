import streamlit as st
import os
import json
import time
from datetime import datetime, timedelta
from src.crew import OptiTradeCrew
from src.tools import authenticate_angel, find_nifty_expiry_dates

# ---------------------------
# 1. Configuration & CSS
# ---------------------------
st.set_page_config(
    page_title="OptiTrade | AI Options Strategist", 
    page_icon="📈", 
    layout="wide"
)

# Modern, clean white design with professional typography
st.markdown("""
    <style>
    /* Global Clean White Theme */
    .stApp { background-color: #FFFFFF; font-family: 'Inter', sans-serif; color: #2C3E50; }
    
    /* Metrics */
    div[data-testid="stMetricValue"] { font-size: 24px; color: #1E88E5; font-weight: 700; }
    div[data-testid="stMetricLabel"] { font-size: 14px; color: #7F8C8D; }
    .stMetric { background-color: #F8F9FA; padding: 15px; border-radius: 8px; border: 1px solid #E0E0E0; }
    
    /* Headers */
    h1 { color: #1a1a1a; font-weight: 800; letter-spacing: -1px; }
    h2, h3 { color: #34495E; font-weight: 600; }
    
    /* Sidebar */
    section[data-testid="stSidebar"] { background-color: #F7F9FC; border-right: 1px solid #E0E0E0; }
    
    /* Status Box */
    div[data-testid="stStatus"] { border: 1px solid #E1E4E8; background-color: #FFFFFF; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    
    /* Button */
    .stButton>button { 
        background-color: #1E88E5; color: white; border-radius: 6px; 
        font-weight: 600; padding: 0.5rem 1rem; border: none;
    }
    .stButton>button:hover { background-color: #1976D2; border: none; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------
# 2. Sidebar Configuration
# ---------------------------
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    # Dynamic Expiry
    try:
        expiries = find_nifty_expiry_dates.func(3)
        expiry_date = st.selectbox("Expiry Date", expiries, index=0)
    except:
        expiry_date = st.date_input("Expiry Date", datetime.now() + timedelta(days=7))

    st.markdown("---")
    st.markdown("**Analysis Params**")
    
    lookback = st.slider("Lookback Days", 15, 60, 30)
    backtest_period = st.slider("Backtest Period", 30, 90, 60)
    sentiment_window = st.number_input("Sentiment Window (Days)", 1, 7, 4)
    lot_size = st.number_input("Lot Size", 25, 1000, 50, step=25)
    
    st.markdown("---")
    if st.button("🔄 Reset Session"):
        st.session_state.clear()
        st.rerun()

# ---------------------------
# 3. Main Header & Auth
# ---------------------------
col1, col2 = st.columns([3, 1])
with col1:
    st.title("OptiTrade")
    st.markdown(f"#### Multi-Agent Nifty50 Strategist • Target: **{expiry_date}**")

# Authentication Check
if "angel_auth" not in st.session_state:
    with st.spinner("Connecting to Angel One..."):
        auth = authenticate_angel.func()
        st.session_state.angel_auth = auth

auth_status = st.session_state.angel_auth.get("status")
with col2:
    if auth_status == "success":
        st.success("● System Online")
    else:
        st.error("● System Offline")

st.divider()

# ---------------------------
# 4. Execution & Visualization
# ---------------------------
if st.button("Analyze Market & Generate Strategy", type="primary", use_container_width=True):
    
    inputs = {
        'expiry_date': str(expiry_date),
        'lookback_days': lookback,
        'backtest_period': backtest_period,
        'sentiment_window': sentiment_window,
        'lot_size': lot_size
    }
    
    # Real-time Status Container
    status_box = st.status("OptiTrade Agents Initializing...", expanded=True)
    
    try:
        with status_box:
            st.write("Fetching real-time spot & option chain data...")
            # Run Crew
            # crew_instance = OptiTradeCrew(inputs=inputs)
            # result = crew_instance.run()

            result = OptiTradeCrew().crew().kickoff(inputs=inputs)
            
            st.write("Synthesizing multi-leg strategies...")
            time.sleep(1) 
            status_box.update(label="Analysis Complete", state="complete", expanded=False)

        # ---------------------------
        # 5. Dashboard Output
        # ---------------------------
        
        # Load Decision JSON
        decision_path = "output/final_decision.json"
        decision_data = {}
        if os.path.exists(decision_path):
            with open(decision_path, 'r') as f:
                decision_data = json.load(f)

        # Top Level Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Recommendation", decision_data.get("final_decision", "HOLD"))
        m2.metric("Strike", decision_data.get("strike", "N/A"))
        m3.metric("Entry Price", f"₹{decision_data.get('entry_price', 0)}")
        
        conf = decision_data.get("confidence", 0)
        m4.metric("AI Confidence", f"{conf*100:.0f}%", delta_color="normal")

        # Rationale Block
        st.info(f"**Strategy Rationale:** {decision_data.get('rationale', 'See full report for details.')}")

        # Content Tabs
        tab_report, tab_tech, tab_json = st.tabs(["📄 Strategy Report", "📈 Technical Data", "🔍 Raw Output"])
        
        with tab_report:
            report_path = "output/trading_report.md"
            if os.path.exists(report_path):
                with open(report_path, "r", encoding="utf-8") as f:
                    st.markdown(f.read())
            else:
                st.write(result)

        with tab_tech:
            tech_path = "output/technical_analysis.json"
            if os.path.exists(tech_path):
                with open(tech_path, "r") as f:
                    st.json(json.load(f))
            else:
                st.warning("No technical analysis data found.")

        with tab_json:
            st.json(decision_data)

    except Exception as e:
        status_box.update(label="System Error", state="error")
        st.error(f"Execution failed: {str(e)}")