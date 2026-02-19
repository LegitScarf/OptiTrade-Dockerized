import streamlit as st
import os
import json
import time
import threading
from datetime import datetime, timedelta
from src.crew import OptiTradeCrew
from src.tools import authenticate_angel, find_nifty_expiry_dates

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="OptiTrade v2.1 | AI Options Strategist",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  GLOBAL STYLES  (Syne + DM Mono + DM Sans)
# ─────────────────────────────────────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">

<style>
/* ── ROOT TOKENS ── */
:root {
    --white:        #FFFFFF;
    --off-white:    #F8F9FC;
    --surface:      #F2F4F8;
    --border:       #E2E6EE;
    --border-light: #EEF1F7;
    --txt-primary:  #0D1117;
    --txt-secondary:#4A5568;
    --txt-muted:    #8896AB;
    --accent:       #0057FF;
    --accent-dim:   rgba(0,87,255,0.10);
    --accent-glow:  rgba(0,87,255,0.18);
    --green:        #00C48C;
    --green-dim:    rgba(0,196,140,0.10);
    --red:          #FF3B5C;
    --red-dim:      rgba(255,59,92,0.10);
    --amber:        #FFB800;
    --amber-dim:    rgba(255,184,0,0.10);
    --font-display: 'Syne', sans-serif;
    --font-body:    'DM Sans', sans-serif;
    --font-mono:    'DM Mono', monospace;
    --r-sm: 8px;
    --r-md: 12px;
    --r-lg: 16px;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    --shadow-md: 0 4px 16px rgba(0,0,0,0.08), 0 2px 6px rgba(0,0,0,0.04);
    --shadow-accent: 0 4px 20px rgba(0,87,255,0.22);
}

/* ── GLOBAL RESET ── */
html, body, [class*="css"] {
    font-family: var(--font-body) !important;
    color: var(--txt-primary) !important;
}
.stApp { background: var(--white) !important; }

/* ── HIDE STREAMLIT CHROME ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding: 0 2.5rem 2rem !important;
    max-width: 1200px !important;
}

/* ── SIDEBAR ── */
section[data-testid="stSidebar"] {
    background: var(--white) !important;
    border-right: 1px solid var(--border) !important;
    padding-top: 0 !important;
}
section[data-testid="stSidebar"] > div:first-child {
    padding-top: 0 !important;
}

/* ── SIDEBAR LABELS ── */
.stSidebar .stMarkdown h3 {
    font-family: var(--font-display) !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px !important;
    color: var(--txt-muted) !important;
    text-transform: uppercase !important;
    margin-bottom: 0 !important;
}
.stSidebar .stMarkdown p,
.stSidebar .stMarkdown strong {
    font-family: var(--font-body) !important;
    font-size: 13px !important;
    color: var(--txt-secondary) !important;
}

/* ── SELECTBOX ── */
.stSelectbox > label {
    font-family: var(--font-body) !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    color: var(--txt-secondary) !important;
    letter-spacing: 0.2px !important;
}
.stSelectbox [data-baseweb="select"] > div {
    background: var(--off-white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    font-family: var(--font-mono) !important;
    font-size: 13px !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}
.stSelectbox [data-baseweb="select"] > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-dim) !important;
}

/* ── SLIDERS ── */
.stSlider > label {
    font-family: var(--font-body) !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    color: var(--txt-secondary) !important;
}
.stSlider [data-baseweb="slider"] [role="slider"] {
    background: var(--accent) !important;
    border: 3px solid white !important;
    box-shadow: 0 0 0 1px var(--accent), 0 2px 4px rgba(0,87,255,0.3) !important;
}
.stSlider [data-baseweb="slider"] div[class*="Track"] {
    background: var(--border) !important;
}
.stSlider [data-baseweb="slider"] div[class*="Track"]:first-child {
    background: var(--accent) !important;
}

/* ── NUMBER INPUT ── */
.stNumberInput > label {
    font-family: var(--font-body) !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    color: var(--txt-secondary) !important;
}
.stNumberInput input {
    background: var(--off-white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    font-family: var(--font-mono) !important;
    font-size: 13px !important;
    color: var(--txt-primary) !important;
}
.stNumberInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-dim) !important;
}

/* ── DATE INPUT ── */
.stDateInput > label {
    font-family: var(--font-body) !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    color: var(--txt-secondary) !important;
}
.stDateInput input {
    background: var(--off-white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    font-family: var(--font-mono) !important;
    font-size: 13px !important;
}

/* ── BUTTONS ── */
.stButton > button {
    font-family: var(--font-display) !important;
    font-weight: 700 !important;
    border-radius: var(--r-md) !important;
    border: none !important;
    transition: all 0.18s !important;
    letter-spacing: 0.2px !important;
}
/* Primary CTA */
.stButton > button[kind="primary"],
.stButton > button[data-testid*="primary"] {
    background: var(--accent) !important;
    color: white !important;
    padding: 0.75rem 1.5rem !important;
    font-size: 15px !important;
    box-shadow: var(--shadow-accent) !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid*="primary"]:hover {
    background: #1060FF !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 28px rgba(0,87,255,0.32) !important;
}
/* Secondary / reset */
.stButton > button:not([kind="primary"]) {
    background: transparent !important;
    color: var(--txt-secondary) !important;
    border: 1px solid var(--border) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    font-family: var(--font-body) !important;
}
.stButton > button:not([kind="primary"]):hover {
    background: var(--surface) !important;
    color: var(--txt-primary) !important;
    border-color: var(--txt-muted) !important;
}

/* ── METRICS ── */
div[data-testid="stMetric"] {
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-lg) !important;
    padding: 20px 22px !important;
    position: relative !important;
    overflow: hidden !important;
    box-shadow: var(--shadow-sm) !important;
    transition: box-shadow 0.2s, border-color 0.2s !important;
}
div[data-testid="stMetric"]:hover {
    box-shadow: var(--shadow-md) !important;
    border-color: rgba(0,87,255,0.15) !important;
}
div[data-testid="stMetricLabel"] > div {
    font-family: var(--font-mono) !important;
    font-size: 10px !important;
    font-weight: 500 !important;
    letter-spacing: 1.2px !important;
    text-transform: uppercase !important;
    color: var(--txt-muted) !important;
}
div[data-testid="stMetricValue"] > div {
    font-family: var(--font-display) !important;
    font-size: 26px !important;
    font-weight: 700 !important;
    color: var(--accent) !important;
    letter-spacing: -0.5px !important;
    line-height: 1.1 !important;
}
div[data-testid="stMetricDelta"] svg { display: none !important; }

/* ── STATUS / SPINNER ── */
div[data-testid="stStatus"] {
    background: var(--off-white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--shadow-sm) !important;
    font-family: var(--font-mono) !important;
    font-size: 13px !important;
    color: var(--txt-secondary) !important;
}
div[data-testid="stStatus"] p {
    font-family: var(--font-mono) !important;
    font-size: 12px !important;
    color: var(--txt-muted) !important;
    line-height: 1.9 !important;
}
div[data-testid="stStatus"] p::before {
    content: "→ ";
    color: var(--accent);
}

/* ── ALERTS ── */
div[data-testid="stAlert"] {
    border-radius: var(--r-md) !important;
    font-family: var(--font-body) !important;
    font-size: 13.5px !important;
}
/* Info */
div[data-testid="stAlert"][class*="info"] {
    background: var(--accent-dim) !important;
    border-left: 3px solid var(--accent) !important;
    color: var(--txt-secondary) !important;
}
/* Warning */
div[data-testid="stAlert"][class*="warning"] {
    background: var(--amber-dim) !important;
    border-left: 3px solid var(--amber) !important;
}
/* Error */
div[data-testid="stAlert"][class*="error"] {
    background: var(--red-dim) !important;
    border-left: 3px solid var(--red) !important;
}
/* Success */
div[data-testid="stAlert"][class*="success"] {
    background: var(--green-dim) !important;
    border-left: 3px solid var(--green) !important;
}

/* ── TABS ── */
div[data-testid="stTabs"] [role="tablist"] {
    background: var(--surface) !important;
    border-radius: var(--r-md) !important;
    padding: 4px !important;
    gap: 2px !important;
    border-bottom: none !important;
    width: fit-content !important;
}
div[data-testid="stTabs"] button[role="tab"] {
    font-family: var(--font-body) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: var(--txt-muted) !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 8px 18px !important;
    transition: all 0.15s !important;
    background: transparent !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: var(--white) !important;
    color: var(--txt-primary) !important;
    font-weight: 600 !important;
    box-shadow: var(--shadow-sm) !important;
}
div[data-testid="stTabs"] button[role="tab"]:hover:not([aria-selected="true"]) {
    color: var(--txt-secondary) !important;
}
/* hide the default tab indicator line */
div[data-testid="stTabs"] [role="tablist"] + div { border-top: none !important; }
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ── JSON VIEWER ── */
div[data-testid="stJson"] {
    background: #0D1117 !important;
    border-radius: var(--r-lg) !important;
    font-family: var(--font-mono) !important;
    font-size: 12.5px !important;
    padding: 16px !important;
    border: none !important;
}

/* ── MARKDOWN IN TABS ── */
.stMarkdown h1 {
    font-family: var(--font-display) !important;
    font-weight: 800 !important;
    font-size: 22px !important;
    letter-spacing: -0.5px !important;
    color: var(--txt-primary) !important;
}
.stMarkdown h2 {
    font-family: var(--font-display) !important;
    font-weight: 700 !important;
    font-size: 16px !important;
    color: var(--txt-primary) !important;
    margin-top: 24px !important;
    padding-top: 16px !important;
    border-top: 1px solid var(--border-light) !important;
}
.stMarkdown p, .stMarkdown li {
    font-family: var(--font-body) !important;
    font-size: 14px !important;
    line-height: 1.8 !important;
    color: var(--txt-secondary) !important;
}
.stMarkdown code {
    font-family: var(--font-mono) !important;
    font-size: 12px !important;
    background: var(--surface) !important;
    color: var(--accent) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
}

/* ── DIVIDER ── */
hr {
    border: none !important;
    border-top: 1px solid var(--border-light) !important;
    margin: 1rem 0 !important;
}

/* ── SUCCESS / ERROR INLINE ── */
div[data-testid="stSuccess"] {
    background: var(--green-dim) !important;
    border-left: 3px solid var(--green) !important;
    border-radius: var(--r-sm) !important;
    font-family: var(--font-mono) !important;
    font-size: 12px !important;
    padding: 8px 14px !important;
}
div[data-testid="stError"] {
    background: var(--red-dim) !important;
    border-left: 3px solid var(--red) !important;
    border-radius: var(--r-sm) !important;
    font-family: var(--font-mono) !important;
    font-size: 12px !important;
}

/* ── COLUMN GAPS ── */
div[data-testid="column"] { gap: 0 !important; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: var(--txt-muted); }

/* ── ANIMATION ── */
@keyframes fadeUp {
    from { opacity: 0; transform: translateY(14px); }
    to   { opacity: 1; transform: translateY(0); }
}
.anim-fadein { animation: fadeUp 0.45s ease both; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  HELPER: load JSON output safely
# ─────────────────────────────────────────────
def _load_json_output(path: str) -> dict:
    """
    FIX: Centralised loader with explicit error keys so the UI can distinguish
    between 'file not written yet' and 'file has bad content', rather than
    silently falling back to an empty dict in both cases.
    """
    if not os.path.exists(path):
        return {"_missing": True}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {"_load_error": str(e)}


# ─────────────────────────────────────────────
#  HELPER: run crew in background thread
# ─────────────────────────────────────────────
def _run_crew(inputs: dict, result_container: dict) -> None:
    """
    FIX: Run crew in a background thread so the Streamlit main thread is never
    blocked — keeping status box updates renderable and the UI responsive.
    """
    try:
        result = OptiTradeCrew().crew().kickoff(inputs=inputs)
        result_container["result"] = result
        result_container["error"] = None
    except Exception as e:
        result_container["result"] = None
        result_container["error"] = str(e)


# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:

    # ── Logo block ──────────────────────────
    st.markdown("""
    <div style="padding: 24px 8px 20px; border-bottom: 1px solid #EEF1F7; margin-bottom: 24px;">
        <div style="display:flex; align-items:center; gap:10px;">
            <div style="width:36px;height:36px;background:#0057FF;border-radius:8px;
                        display:flex;align-items:center;justify-content:center;
                        font-size:18px;flex-shrink:0;">📈</div>
            <div>
                <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:18px;
                            color:#0D1117;letter-spacing:-0.5px;line-height:1.1;">
                    Opti<span style="color:#0057FF;">Trade</span>
                </div>
                <div style="font-family:'DM Mono',monospace;font-size:10px;color:#8896AB;
                            letter-spacing:0.5px;margin-top:2px;">
                    v2.1 PATCHED · AI STRATEGIST
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Expiry Date ──────────────────────────
    st.markdown("""
    <div style="font-family:'DM Mono',monospace;font-size:10px;letter-spacing:1.5px;
                text-transform:uppercase;color:#8896AB;margin-bottom:12px;">
        Configuration
    </div>
    """, unsafe_allow_html=True)

    # FIX: Bare except swallowed errors silently. Now we log the error, show it
    # in sidebar, and provide a clearly-labelled manual fallback.
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

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    st.divider()

    # ── Analysis Params ──────────────────────
    st.markdown("""
    <div style="font-family:'DM Mono',monospace;font-size:10px;letter-spacing:1.5px;
                text-transform:uppercase;color:#8896AB;margin-bottom:8px;">
        Analysis Parameters
    </div>
    """, unsafe_allow_html=True)

    lookback        = st.slider("Lookback Days",            min_value=15,  max_value=60,   value=30)
    backtest_period = st.slider("Backtest Period",          min_value=30,  max_value=90,   value=60)
    sentiment_window = st.number_input("Sentiment Window (Days)", min_value=1, max_value=7, value=4)
    lot_size        = st.number_input("Lot Size",           min_value=25,  max_value=1000, value=50, step=25)

    st.divider()

    if st.button("↺  Reset Session", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # ── Sidebar footer ───────────────────────
    st.markdown("""
    <div style="padding:16px 8px 0;font-family:'DM Mono',monospace;font-size:10px;
                color:#8896AB;line-height:1.8;border-top:1px solid #EEF1F7;margin-top:8px;">
        NIFTY 50 · NSE<br>
        Not financial advice<br>
        © OptiTrade 2025
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  AUTH  (TTL-aware)
# ─────────────────────────────────────────────
AUTH_TTL_SECONDS = 3600

def _should_reauthenticate() -> bool:
    """
    FIX: Original code re-authenticated on every render if angel_auth was absent,
    but never re-authed if the token silently expired. Now we track auth_time and
    force re-auth after AUTH_TTL_SECONDS (Angel One sessions expire in 60 min).
    """
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
        # FIX: Record auth timestamp so TTL check works on subsequent renders.
        st.session_state.angel_auth_time = time.time()

auth_status = st.session_state.angel_auth.get("status")


# ─────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────
col_title, col_status = st.columns([5, 1])

with col_title:
    st.markdown(f"""
    <div class="anim-fadein" style="padding: 32px 0 8px;">
        <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:28px;
                    letter-spacing:-0.8px;color:#0D1117;line-height:1.1;">
            Opti<span style="color:#0057FF;">Trade</span>
            <span style="font-size:14px;font-weight:600;color:#8896AB;
                         letter-spacing:0;margin-left:8px;">v2.1</span>
        </div>
        <div style="font-family:'DM Sans',sans-serif;font-size:14px;color:#4A5568;
                    margin-top:5px;">
            Multi-Agent Nifty50 Strategist &nbsp;·&nbsp;
            Target: <span style="font-family:'DM Mono',monospace;font-weight:500;
                                  color:#0057FF;">{expiry_date}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_status:
    st.markdown("<div style='padding-top:36px'>", unsafe_allow_html=True)
    if auth_status == "success":
        st.markdown("""
        <div style="display:inline-flex;align-items:center;gap:7px;
                    padding:7px 14px;border-radius:99px;
                    background:rgba(0,196,140,0.10);
                    border:1px solid rgba(0,196,140,0.25);
                    font-family:'DM Mono',monospace;font-size:12px;
                    font-weight:500;color:#00C48C;white-space:nowrap;">
            <span style="width:6px;height:6px;border-radius:50%;
                         background:#00C48C;display:inline-block;"></span>
            System Online
        </div>
        """, unsafe_allow_html=True)
    else:
        # FIX: Show actual auth error so the user can diagnose credential issues.
        auth_msg = st.session_state.angel_auth.get("message", "Unknown error")
        st.markdown(f"""
        <div style="display:inline-flex;align-items:center;gap:7px;
                    padding:7px 14px;border-radius:99px;
                    background:rgba(255,59,92,0.10);
                    border:1px solid rgba(255,59,92,0.25);
                    font-family:'DM Mono',monospace;font-size:12px;
                    font-weight:500;color:#FF3B5C;">
            <span style="width:6px;height:6px;border-radius:50%;
                         background:#FF3B5C;display:inline-block;"></span>
            Offline · {auth_msg}
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()


# ─────────────────────────────────────────────
#  ANALYZE BUTTON
# ─────────────────────────────────────────────
st.markdown("<div style='margin-bottom:4px'>", unsafe_allow_html=True)
run_analysis = st.button(
    "⚡  Analyze Market & Generate Strategy",
    type="primary",
    use_container_width=True
)
st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  EXECUTION  (exact original logic, unchanged)
# ─────────────────────────────────────────────
if run_analysis:

    inputs = {
        "expiry_date":       str(expiry_date),
        "lookback_days":     lookback,
        "backtest_period":   backtest_period,
        "sentiment_window":  sentiment_window,
        "lot_size":          lot_size,
    }

    # Status box (styled via CSS above)
    status_box = st.status("⚙️  OptiTrade Agents Initializing...", expanded=True)
    result_container: dict = {}

    with status_box:
        st.write("Fetching real-time spot & option chain data...")

        crew_thread = threading.Thread(
            target=_run_crew,
            args=(inputs, result_container),
            daemon=True,
        )
        crew_thread.start()

        # FIX: Poll with timeout — never blocks forever. Surfaces an error if
        # crew doesn't finish within 10 min instead of leaving a frozen spinner.
        CREW_TIMEOUT_SECONDS = 600
        poll_interval        = 2
        elapsed              = 0

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
            status_box.update(label="❌  System Error", state="error", expanded=True)
            st.error(f"Execution failed: {result_container['error']}")
            st.stop()

        st.write("Synthesizing multi-leg strategies...")
        status_box.update(label="✅  Analysis Complete", state="complete", expanded=False)

    # ─────────────────────────────────────────
    #  DASHBOARD OUTPUT
    # ─────────────────────────────────────────
    decision_data = _load_json_output("output/final_decision.json")

    # FIX: Surface load errors prominently rather than showing empty metrics.
    if decision_data.get("_missing"):
        st.warning(
            "⚠️  `final_decision.json` was not written — "
            "the decision agent may have failed. Check logs."
        )
    elif decision_data.get("_load_error"):
        st.warning(
            f"⚠️  Could not parse `final_decision.json`: "
            f"{decision_data['_load_error']}"
        )

    # FIX: simulation_warning passthrough — warn prominently if on simulated data.
    market_data = _load_json_output("output/market_data.json")
    if (market_data.get("simulation_warning")
            or market_data.get("data_source") == "simulated"):
        st.warning(
            "⚠️ **Simulated Data:** Live option chain data was unavailable. "
            "Analysis was performed on **simulated** prices. "
            "Do not act on this output with real capital."
        )

    # ── Section: Metrics ─────────────────────
    st.markdown("""
    <div style="font-family:'DM Mono',monospace;font-size:10px;letter-spacing:1.5px;
                text-transform:uppercase;color:#8896AB;margin:24px 0 12px;">
        Strategy Output
    </div>
    """, unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4, gap="medium")

    recommendation = decision_data.get("final_decision", "HOLD")
    strike         = decision_data.get("strike", "N/A")
    entry_price    = decision_data.get("entry_price", 0)
    conf           = decision_data.get("confidence", 0)

    with m1:
        st.metric("Recommendation", recommendation)
    with m2:
        st.metric("Strike", str(strike))
    with m3:
        st.metric("Entry Price", f"₹{entry_price}")
    with m4:
        st.metric("AI Confidence", f"{conf * 100:.0f}%")

    # ── Rationale Banner ─────────────────────
    rationale = decision_data.get("rationale", "See full report for details.")
    st.markdown(f"""
    <div style="background:rgba(0,87,255,0.06);border:1px solid rgba(0,87,255,0.12);
                border-left:3px solid #0057FF;border-radius:10px;
                padding:16px 20px;margin:20px 0 28px;
                display:flex;align-items:flex-start;gap:12px;">
        <span style="font-size:16px;flex-shrink:0;margin-top:1px;">💡</span>
        <div style="font-family:'DM Sans',sans-serif;font-size:13.5px;
                    color:#4A5568;line-height:1.7;">
            <strong style="color:#0D1117;">Strategy Rationale:</strong>
            &nbsp;{rationale}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Tabs ─────────────────────────────────
    tab_report, tab_tech, tab_json = st.tabs([
        "📄  Strategy Report",
        "📈  Technical Data",
        "🔍  Raw Output",
    ])

    with tab_report:
        report_path = "output/trading_report.md"
        if os.path.exists(report_path):
            # Wrap in a styled card
            st.markdown("""
            <div style="background:#FFFFFF;border:1px solid #E2E6EE;border-radius:14px;
                        overflow:hidden;margin-top:16px;">
                <div style="padding:16px 24px;border-bottom:1px solid #EEF1F7;
                            background:#F8F9FC;display:flex;align-items:center;
                            justify-content:space-between;">
                    <div style="font-family:'Syne',sans-serif;font-weight:700;
                                font-size:14px;color:#0D1117;">
                        OptiTrade Analysis Report — NIFTY 50
                    </div>
                    <div style="font-family:'DM Mono',monospace;font-size:11px;color:#8896AB;">
                        output/trading_report.md
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            with open(report_path, "r", encoding="utf-8") as f:
                st.markdown(f.read())
        else:
            st.warning("⚠️  Trading report was not generated. Check agent logs.")

    with tab_tech:
        tech_data = _load_json_output("output/technical_analysis.json")
        if tech_data.get("_missing"):
            st.warning("⚠️  `technical_analysis.json` was not found. Check agent logs.")
        elif tech_data.get("_load_error"):
            st.warning(f"⚠️  Could not parse `technical_analysis.json`: {tech_data['_load_error']}")
        else:
            # Styled header for the JSON block
            st.markdown("""
            <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:14px;
                        color:#0D1117;margin:16px 0 10px;">
                Technical Analysis Data
            </div>
            """, unsafe_allow_html=True)
            st.json(tech_data)

    with tab_json:
        st.markdown("""
        <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:14px;
                    color:#0D1117;margin:16px 0 10px;">
            Raw Decision Output
        </div>
        """, unsafe_allow_html=True)
        st.json(decision_data)

else:
    # ─────────────────────────────────────────
    #  EMPTY STATE  (shown before first run)
    # ─────────────────────────────────────────
    st.markdown("""
    <div class="anim-fadein" style="
        display:flex;flex-direction:column;align-items:center;
        justify-content:center;padding:80px 40px;text-align:center;">
        <div style="font-size:52px;margin-bottom:22px;opacity:0.45;">📊</div>
        <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:22px;
                    color:#0D1117;letter-spacing:-0.3px;margin-bottom:12px;">
            Ready to Analyze
        </div>
        <div style="font-family:'DM Sans',sans-serif;font-size:14px;color:#8896AB;
                    max-width:380px;line-height:1.8;">
            Configure your parameters in the sidebar, then click
            <strong style="color:#0057FF;">⚡ Analyze Market &amp; Generate Strategy</strong>
            to run the multi-agent pipeline across live Nifty 50 data.
        </div>
        <div style="margin-top:36px;display:flex;gap:24px;flex-wrap:wrap;justify-content:center;">
            <div style="background:#F8F9FC;border:1px solid #E2E6EE;border-radius:10px;
                        padding:14px 20px;min-width:140px;text-align:center;">
                <div style="font-family:'DM Mono',monospace;font-size:10px;
                            letter-spacing:1px;text-transform:uppercase;
                            color:#8896AB;margin-bottom:6px;">Agents</div>
                <div style="font-family:'Syne',sans-serif;font-weight:700;
                            font-size:20px;color:#0057FF;">5</div>
            </div>
            <div style="background:#F8F9FC;border:1px solid #E2E6EE;border-radius:10px;
                        padding:14px 20px;min-width:140px;text-align:center;">
                <div style="font-family:'DM Mono',monospace;font-size:10px;
                            letter-spacing:1px;text-transform:uppercase;
                            color:#8896AB;margin-bottom:6px;">Data Source</div>
                <div style="font-family:'Syne',sans-serif;font-weight:700;
                            font-size:20px;color:#0D1117;">Live</div>
            </div>
            <div style="background:#F8F9FC;border:1px solid #E2E6EE;border-radius:10px;
                        padding:14px 20px;min-width:140px;text-align:center;">
                <div style="font-family:'DM Mono',monospace;font-size:10px;
                            letter-spacing:1px;text-transform:uppercase;
                            color:#8896AB;margin-bottom:6px;">Exchange</div>
                <div style="font-family:'Syne',sans-serif;font-weight:700;
                            font-size:20px;color:#0D1117;">NSE</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# import streamlit as st
# import os
# import json
# import time
# import threading
# from datetime import datetime, timedelta
# from src.crew import OptiTradeCrew
# from src.tools import authenticate_angel, find_nifty_expiry_dates

# st.set_page_config(
#     page_title="OptiTrade v2.1 (Patched) | AI Options Strategist",
#     page_icon="📈",
#     layout="wide"
# )

# st.markdown("""
#     <style>
#     .stApp { background-color: #FFFFFF; font-family: 'Inter', sans-serif; color: #2C3E50; }
#     div[data-testid="stMetricValue"] { font-size: 24px; color: #1E88E5; font-weight: 700; }
#     div[data-testid="stMetricLabel"] { font-size: 14px; color: #7F8C8D; }
#     .stMetric { background-color: #F8F9FA; padding: 15px; border-radius: 8px; border: 1px solid #E0E0E0; }
#     h1 { color: #1a1a1a; font-weight: 800; letter-spacing: -1px; }
#     h2, h3 { color: #34495E; font-weight: 600; }
#     section[data-testid="stSidebar"] { background-color: #F7F9FC; border-right: 1px solid #E0E0E0; }
#     div[data-testid="stStatus"] { border: 1px solid #E1E4E8; background-color: #FFFFFF; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
#     .stButton>button { background-color: #1E88E5; color: white; border-radius: 6px; font-weight: 600; padding: 0.5rem 1rem; border: none; }
#     .stButton>button:hover { background-color: #1976D2; border: none; }
#     </style>
#     """, unsafe_allow_html=True)

# # ---------------------------
# # Sidebar
# # ---------------------------
# with st.sidebar:
#     st.markdown("### ⚙️ Configuration")

#     # FIX: The original bare except swallowed all errors silently and left the user
#     # with a date_input fallback that could produce an invalid expiry for the API.
#     # We now log the error, show it in the sidebar, and provide a clearly-labelled
#     # manual fallback so the user knows something went wrong.
#     try:
#         expiries = find_nifty_expiry_dates.func(3)
#         if not expiries:
#             raise ValueError("find_nifty_expiry_dates returned an empty list")
#         expiry_date = st.selectbox("Expiry Date", expiries, index=0)
#     except Exception as e:
#         st.warning(f"Could not auto-fetch expiry dates: {e}\nUsing manual input.")
#         expiry_date = st.date_input(
#             "Expiry Date (manual)",
#             datetime.now() + timedelta(days=7)
#         )
#         expiry_date = expiry_date.strftime("%Y-%m-%d")

#     st.markdown("---")
#     st.markdown("**Analysis Params**")

#     lookback = st.slider("Lookback Days", 15, 60, 30)
#     backtest_period = st.slider("Backtest Period", 30, 90, 60)
#     sentiment_window = st.number_input("Sentiment Window (Days)", 1, 7, 4)
#     lot_size = st.number_input("Lot Size", 25, 1000, 50, step=25)

#     st.markdown("---")
#     if st.button("🔄 Reset Session"):
#         st.session_state.clear()
#         st.rerun()

# # ---------------------------
# # Header & Auth
# # ---------------------------
# col1, col2 = st.columns([3, 1])
# with col1:
#     st.title("OptiTrade v2.1 (Patched)")
#     st.markdown(f"#### Multi-Agent Nifty50 Strategist • Target: **{expiry_date}**")

# # FIX: The original code re-authenticated on every page render if angel_auth was
# # missing from session_state, but never re-authenticated if the token silently
# # expired during a long session. We now also store a timestamp and force a
# # re-auth if the token is older than 60 minutes (Angel One sessions expire).
# AUTH_TTL_SECONDS = 3600

# def _should_reauthenticate() -> bool:
#     if "angel_auth" not in st.session_state:
#         return True
#     if st.session_state.angel_auth.get("status") != "success":
#         return True
#     auth_time = st.session_state.get("angel_auth_time", 0)
#     return (time.time() - auth_time) > AUTH_TTL_SECONDS

# if _should_reauthenticate():
#     with st.spinner("Connecting to Angel One..."):
#         auth = authenticate_angel.func()
#         st.session_state.angel_auth = auth
#         # FIX: Record the time of successful auth so TTL check works correctly.
#         st.session_state.angel_auth_time = time.time()

# auth_status = st.session_state.angel_auth.get("status")
# with col2:
#     if auth_status == "success":
#         st.success("● System Online")
#     else:
#         # FIX: Show the actual auth error message so the user can diagnose
#         # credential problems instead of just seeing "System Offline".
#         auth_msg = st.session_state.angel_auth.get("message", "Unknown error")
#         st.error(f"● System Offline\n{auth_msg}")

# st.divider()

# # ---------------------------
# # Execution
# # ---------------------------

# # FIX: The original code called crew.kickoff() directly on the Streamlit main thread,
# # which blocked the entire UI — including the status box updates — for the full
# # analysis duration (often several minutes). We now run the crew in a background
# # thread and poll for completion, keeping the UI responsive and allowing the
# # status messages to actually render.
# def _run_crew(inputs: dict, result_container: dict) -> None:
#     try:
#         result = OptiTradeCrew().crew().kickoff(inputs=inputs)
#         result_container["result"] = result
#         result_container["error"] = None
#     except Exception as e:
#         result_container["result"] = None
#         result_container["error"] = str(e)


# def _load_json_output(path: str) -> dict:
#     # FIX: Centralised loader with an explicit error key so the UI can
#     # distinguish between "file not written yet" and "file has bad content",
#     # rather than silently falling back to an empty dict in both cases.
#     if not os.path.exists(path):
#         return {"_missing": True}
#     try:
#         with open(path, "r", encoding="utf-8") as f:
#             return json.load(f)
#     except (json.JSONDecodeError, OSError) as e:
#         return {"_load_error": str(e)}


# if st.button("Analyze Market & Generate Strategy", type="primary", use_container_width=True):

#     inputs = {
#         "expiry_date": str(expiry_date),
#         "lookback_days": lookback,
#         "backtest_period": backtest_period,
#         "sentiment_window": sentiment_window,
#         "lot_size": lot_size
#     }

#     status_box = st.status("OptiTrade Agents Initializing...", expanded=True)
#     result_container: dict = {}

#     with status_box:
#         st.write("Fetching real-time spot & option chain data...")

#         crew_thread = threading.Thread(
#             target=_run_crew,
#             args=(inputs, result_container),
#             daemon=True
#         )
#         crew_thread.start()

#         # FIX: Poll the thread with a timeout instead of blocking forever.
#         # If the crew doesn't finish within 10 minutes, we surface an error
#         # rather than leaving the user staring at a frozen spinner indefinitely.
#         CREW_TIMEOUT_SECONDS = 600
#         poll_interval = 2
#         elapsed = 0

#         while crew_thread.is_alive():
#             time.sleep(poll_interval)
#             elapsed += poll_interval
#             if elapsed % 30 == 0:
#                 st.write(f"Still running... ({elapsed}s elapsed)")
#             if elapsed >= CREW_TIMEOUT_SECONDS:
#                 result_container["error"] = (
#                     f"Analysis timed out after {CREW_TIMEOUT_SECONDS}s. "
#                     "Check logs for the last completed task."
#                 )
#                 break

#         if result_container.get("error"):
#             status_box.update(label="System Error", state="error", expanded=True)
#             st.error(f"Execution failed: {result_container['error']}")
#             st.stop()

#         st.write("Synthesizing multi-leg strategies...")
#         status_box.update(label="Analysis Complete", state="complete", expanded=False)

#     # ---------------------------
#     # Dashboard Output
#     # ---------------------------
#     decision_data = _load_json_output("output/final_decision.json")

#     # FIX: Surface load errors to the user rather than silently showing
#     # empty/default values that look like real analysis results.
#     if decision_data.get("_missing"):
#         st.warning("final_decision.json was not written — the decision agent may have failed. Check logs.")
#     elif decision_data.get("_load_error"):
#         st.warning(f"Could not parse final_decision.json: {decision_data['_load_error']}")

#     # FIX: Added simulation_warning passthrough — if the option chain fell back
#     # to simulated data, warn the user prominently before showing any metrics.
#     market_data = _load_json_output("output/market_data.json")
#     if market_data.get("simulation_warning") or market_data.get("data_source") == "simulated":
#         st.warning(
#             "⚠️ Live option chain data was unavailable. "
#             "Analysis was performed on **simulated** prices. "
#             "Do not act on this output with real capital."
#         )

#     m1, m2, m3, m4 = st.columns(4)
#     m1.metric("Recommendation", decision_data.get("final_decision", "HOLD"))
#     m2.metric("Strike", decision_data.get("strike", "N/A"))
#     m3.metric("Entry Price", f"₹{decision_data.get('entry_price', 0)}")
#     conf = decision_data.get("confidence", 0)
#     m4.metric("AI Confidence", f"{conf * 100:.0f}%", delta_color="normal")

#     st.info(f"**Strategy Rationale:** {decision_data.get('rationale', 'See full report for details.')}")

#     tab_report, tab_tech, tab_json = st.tabs(["📄 Strategy Report", "📈 Technical Data", "🔍 Raw Output"])

#     with tab_report:
#         report_path = "output/trading_report.md"
#         if os.path.exists(report_path):
#             with open(report_path, "r", encoding="utf-8") as f:
#                 st.markdown(f.read())
#         else:
#             st.warning("Trading report was not generated. Check agent logs.")

#     with tab_tech:
#         tech_data = _load_json_output("output/technical_analysis.json")
#         if tech_data.get("_missing") or tech_data.get("_load_error"):
#             st.warning("No technical analysis data found.")
#         else:
#             st.json(tech_data)

#     with tab_json:
#         st.json(decision_data)


