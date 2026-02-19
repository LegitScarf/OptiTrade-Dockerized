import streamlit as st
import os
import json
import time
import threading
from datetime import datetime, timedelta
from src.crew import OptiTradeCrew
from src.tools import authenticate_angel, find_nifty_expiry_dates

st.set_page_config(
    page_title="OptiTrade v2.1 (Patched) | AI Options Strategist",
    page_icon="📈",
    layout="wide"
)

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; font-family: 'Inter', sans-serif; color: #2C3E50; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #1E88E5; font-weight: 700; }
    div[data-testid="stMetricLabel"] { font-size: 14px; color: #7F8C8D; }
    .stMetric { background-color: #F8F9FA; padding: 15px; border-radius: 8px; border: 1px solid #E0E0E0; }
    h1 { color: #1a1a1a; font-weight: 800; letter-spacing: -1px; }
    h2, h3 { color: #34495E; font-weight: 600; }
    section[data-testid="stSidebar"] { background-color: #F7F9FC; border-right: 1px solid #E0E0E0; }
    div[data-testid="stStatus"] { border: 1px solid #E1E4E8; background-color: #FFFFFF; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { background-color: #1E88E5; color: white; border-radius: 6px; font-weight: 600; padding: 0.5rem 1rem; border: none; }
    .stButton>button:hover { background-color: #1976D2; border: none; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------
# Sidebar
# ---------------------------
with st.sidebar:
    st.markdown("### ⚙️ Configuration")

    # FIX: The original bare except swallowed all errors silently and left the user
    # with a date_input fallback that could produce an invalid expiry for the API.
    # We now log the error, show it in the sidebar, and provide a clearly-labelled
    # manual fallback so the user knows something went wrong.
    try:
        expiries = find_nifty_expiry_dates.func(3)
        if not expiries:
            raise ValueError("find_nifty_expiry_dates returned an empty list")
        expiry_date = st.selectbox("Expiry Date", expiries, index=0)
    except Exception as e:
        st.warning(f"Could not auto-fetch expiry dates: {e}\nUsing manual input.")
        expiry_date = st.date_input(
            "Expiry Date (manual)",
            datetime.now() + timedelta(days=7)
        )
        expiry_date = expiry_date.strftime("%Y-%m-%d")

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
# Header & Auth
# ---------------------------
col1, col2 = st.columns([3, 1])
with col1:
    st.title("OptiTrade v2.1 (Patched)")
    st.markdown(f"#### Multi-Agent Nifty50 Strategist • Target: **{expiry_date}**")

# FIX: The original code re-authenticated on every page render if angel_auth was
# missing from session_state, but never re-authenticated if the token silently
# expired during a long session. We now also store a timestamp and force a
# re-auth if the token is older than 60 minutes (Angel One sessions expire).
AUTH_TTL_SECONDS = 3600

def _should_reauthenticate() -> bool:
    if "angel_auth" not in st.session_state:
        return True
    if st.session_state.angel_auth.get("status") != "success":
        return True
    auth_time = st.session_state.get("angel_auth_time", 0)
    return (time.time() - auth_time) > AUTH_TTL_SECONDS

if _should_reauthenticate():
    with st.spinner("Connecting to Angel One..."):
        auth = authenticate_angel.func()
        st.session_state.angel_auth = auth
        # FIX: Record the time of successful auth so TTL check works correctly.
        st.session_state.angel_auth_time = time.time()

auth_status = st.session_state.angel_auth.get("status")
with col2:
    if auth_status == "success":
        st.success("● System Online")
    else:
        # FIX: Show the actual auth error message so the user can diagnose
        # credential problems instead of just seeing "System Offline".
        auth_msg = st.session_state.angel_auth.get("message", "Unknown error")
        st.error(f"● System Offline\n{auth_msg}")

st.divider()

# ---------------------------
# Execution
# ---------------------------

# FIX: The original code called crew.kickoff() directly on the Streamlit main thread,
# which blocked the entire UI — including the status box updates — for the full
# analysis duration (often several minutes). We now run the crew in a background
# thread and poll for completion, keeping the UI responsive and allowing the
# status messages to actually render.
def _run_crew(inputs: dict, result_container: dict) -> None:
    try:
        result = OptiTradeCrew().crew().kickoff(inputs=inputs)
        result_container["result"] = result
        result_container["error"] = None
    except Exception as e:
        result_container["result"] = None
        result_container["error"] = str(e)


def _load_json_output(path: str) -> dict:
    # FIX: Centralised loader with an explicit error key so the UI can
    # distinguish between "file not written yet" and "file has bad content",
    # rather than silently falling back to an empty dict in both cases.
    if not os.path.exists(path):
        return {"_missing": True}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {"_load_error": str(e)}


if st.button("Analyze Market & Generate Strategy", type="primary", use_container_width=True):

    inputs = {
        "expiry_date": str(expiry_date),
        "lookback_days": lookback,
        "backtest_period": backtest_period,
        "sentiment_window": sentiment_window,
        "lot_size": lot_size
    }

    status_box = st.status("OptiTrade Agents Initializing...", expanded=True)
    result_container: dict = {}

    with status_box:
        st.write("Fetching real-time spot & option chain data...")

        crew_thread = threading.Thread(
            target=_run_crew,
            args=(inputs, result_container),
            daemon=True
        )
        crew_thread.start()

        # FIX: Poll the thread with a timeout instead of blocking forever.
        # If the crew doesn't finish within 10 minutes, we surface an error
        # rather than leaving the user staring at a frozen spinner indefinitely.
        CREW_TIMEOUT_SECONDS = 600
        poll_interval = 2
        elapsed = 0

        while crew_thread.is_alive():
            time.sleep(poll_interval)
            elapsed += poll_interval
            if elapsed % 30 == 0:
                st.write(f"Still running... ({elapsed}s elapsed)")
            if elapsed >= CREW_TIMEOUT_SECONDS:
                result_container["error"] = (
                    f"Analysis timed out after {CREW_TIMEOUT_SECONDS}s. "
                    "Check logs for the last completed task."
                )
                break

        if result_container.get("error"):
            status_box.update(label="System Error", state="error", expanded=True)
            st.error(f"Execution failed: {result_container['error']}")
            st.stop()

        st.write("Synthesizing multi-leg strategies...")
        status_box.update(label="Analysis Complete", state="complete", expanded=False)

    # ---------------------------
    # Dashboard Output
    # ---------------------------
    decision_data = _load_json_output("output/final_decision.json")

    # FIX: Surface load errors to the user rather than silently showing
    # empty/default values that look like real analysis results.
    if decision_data.get("_missing"):
        st.warning("final_decision.json was not written — the decision agent may have failed. Check logs.")
    elif decision_data.get("_load_error"):
        st.warning(f"Could not parse final_decision.json: {decision_data['_load_error']}")

    # FIX: Added simulation_warning passthrough — if the option chain fell back
    # to simulated data, warn the user prominently before showing any metrics.
    market_data = _load_json_output("output/market_data.json")
    if market_data.get("simulation_warning") or market_data.get("data_source") == "simulated":
        st.warning(
            "⚠️ Live option chain data was unavailable. "
            "Analysis was performed on **simulated** prices. "
            "Do not act on this output with real capital."
        )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Recommendation", decision_data.get("final_decision", "HOLD"))
    m2.metric("Strike", decision_data.get("strike", "N/A"))
    m3.metric("Entry Price", f"₹{decision_data.get('entry_price', 0)}")
    conf = decision_data.get("confidence", 0)
    m4.metric("AI Confidence", f"{conf * 100:.0f}%", delta_color="normal")

    st.info(f"**Strategy Rationale:** {decision_data.get('rationale', 'See full report for details.')}")

    tab_report, tab_tech, tab_json = st.tabs(["📄 Strategy Report", "📈 Technical Data", "🔍 Raw Output"])

    with tab_report:
        report_path = "output/trading_report.md"
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                st.markdown(f.read())
        else:
            st.warning("Trading report was not generated. Check agent logs.")

    with tab_tech:
        tech_data = _load_json_output("output/technical_analysis.json")
        if tech_data.get("_missing") or tech_data.get("_load_error"):
            st.warning("No technical analysis data found.")
        else:
            st.json(tech_data)

    with tab_json:
        st.json(decision_data)


