import os
import json
import time
import threading
from datetime import datetime, timedelta
import streamlit as st
import streamlit.components.v1 as components
from src.crew import OptiTradeCrew
from src.tools import authenticate_angel, find_nifty_expiry_dates

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="OptiTrade v2.1 | AI Options Strategist",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  DESIGN SYSTEM
#  Aesthetic: "Luxury Quant Terminal"
#  Crisp white canvas · obsidian sidebar · signal-green/red accents
#  Fonts: Cormorant Garamond (headlines) · IBM Plex Mono (data) · Plus Jakarta Sans (body)
#  Signature: 4px top rule · numbered pipeline tracker · italic serif rationale quote
# ─────────────────────────────────────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400;1,600&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">

<style>
/* ════════════════════════════════════════════
   DESIGN TOKENS
════════════════════════════════════════════ */
:root {
    --canvas:         #FFFFFF;
    --canvas-warm:    #FAFAF7;
    --canvas-cool:    #F6F7FA;
    --ink-900:        #0C0C0E;
    --ink-700:        #2E2E35;
    --ink-500:        #6B6B78;
    --ink-300:        #AEAEBA;
    --ink-100:        #E8E8EF;
    --ink-50:         #F4F4F8;
    --bull:           #0A6640;
    --bull-mid:       #12A05C;
    --bull-bg:        #F0FBF5;
    --bull-border:    rgba(18,160,92,0.18);
    --bear:           #8B1A1A;
    --bear-mid:       #D93025;
    --bear-bg:        #FFF5F5;
    --bear-border:    rgba(217,48,37,0.18);
    --neutral:        #7A5C00;
    --neutral-mid:    #C49A00;
    --neutral-bg:     #FFFBEB;
    --neutral-border: rgba(196,154,0,0.20);
    --brand:          #1400FF;
    --brand-dim:      rgba(20,0,255,0.07);
    --brand-border:   rgba(20,0,255,0.15);
    --sidebar-bg:     #0C0C0E;
    --sidebar-rule:   rgba(255,255,255,0.07);
    --sidebar-muted:  rgba(255,255,255,0.28);
    --sidebar-faint:  rgba(255,255,255,0.08);
    --f-display:      'Cormorant Garamond', Georgia, serif;
    --f-body:         'Plus Jakarta Sans', sans-serif;
    --f-mono:         'IBM Plex Mono', 'Courier New', monospace;
    --r-xs: 3px; --r-sm: 6px; --r-md: 10px; --r-lg: 16px;
    --sh-xs: 0 1px 2px rgba(0,0,0,0.04);
    --sh-sm: 0 2px 6px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    --sh-md: 0 4px 16px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
    --sh-lg: 0 12px 40px rgba(0,0,0,0.10), 0 4px 12px rgba(0,0,0,0.06);
}

/* ════════════════════════════════════════════
   GLOBAL
════════════════════════════════════════════ */
html, body, [class*="css"] {
    font-family: var(--f-body) !important;
    color: var(--ink-900) !important;
    -webkit-font-smoothing: antialiased !important;
}
.stApp { background: var(--canvas) !important; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 2.5rem 3rem !important; max-width: 1280px !important; }
div[data-testid="column"] { gap: 0 !important; }
hr { border: none !important; border-top: 1px solid var(--ink-100) !important; margin: 1.25rem 0 !important; }
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--ink-100); border-radius: 8px; }

/* ════════════════════════════════════════════
   SIDEBAR — obsidian
════════════════════════════════════════════ */
section[data-testid="stSidebar"] {
    background: var(--sidebar-bg) !important;
    border-right: none !important;
    box-shadow: 4px 0 24px rgba(0,0,0,0.18) !important;
}
section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
section[data-testid="stSidebar"] * { color: rgba(255,255,255,0.82) !important; }

section[data-testid="stSidebar"] .stSelectbox > label,
section[data-testid="stSidebar"] .stSlider > label,
section[data-testid="stSidebar"] .stNumberInput > label,
section[data-testid="stSidebar"] .stDateInput > label {
    font-family: var(--f-mono) !important;
    font-size: 9px !important; font-weight: 500 !important;
    letter-spacing: 2px !important; text-transform: uppercase !important;
    color: var(--sidebar-muted) !important;
}
section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div {
    background: var(--sidebar-faint) !important;
    border: 1px solid var(--sidebar-rule) !important;
    border-radius: var(--r-sm) !important;
    font-family: var(--f-mono) !important; font-size: 12px !important; color: white !important;
}
section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div:focus-within {
    border-color: var(--brand) !important;
}
section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] [role="slider"] {
    background: white !important; border: 2px solid var(--brand) !important;
    box-shadow: 0 0 0 3px rgba(20,0,255,0.15) !important;
}
section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[class*="Track"]:first-child {
    background: var(--brand) !important;
}
section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[class*="Track"] {
    background: rgba(255,255,255,0.10) !important;
}
section[data-testid="stSidebar"] .stNumberInput input,
section[data-testid="stSidebar"] .stDateInput input {
    background: var(--sidebar-faint) !important;
    border: 1px solid var(--sidebar-rule) !important;
    border-radius: var(--r-sm) !important;
    font-family: var(--f-mono) !important; font-size: 12px !important; color: white !important;
}
section[data-testid="stSidebar"] .stNumberInput input:focus,
section[data-testid="stSidebar"] .stDateInput input:focus {
    border-color: var(--brand) !important;
}

/* ════════════════════════════════════════════
   BUTTONS
════════════════════════════════════════════ */
.stButton > button {
    font-family: var(--f-body) !important; font-weight: 600 !important;
    border-radius: var(--r-sm) !important; border: none !important;
    transition: all 0.2s cubic-bezier(0.4,0,0.2,1) !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid*="primary"] {
    background: var(--ink-900) !important; color: white !important;
    padding: 0.9rem 2rem !important; font-size: 13px !important;
    font-weight: 600 !important; letter-spacing: 1px !important;
    text-transform: uppercase !important; box-shadow: var(--sh-md) !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--brand) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 32px rgba(20,0,255,0.25) !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: var(--sidebar-faint) !important;
    color: var(--sidebar-muted) !important;
    border: 1px solid var(--sidebar-rule) !important;
    font-family: var(--f-mono) !important; font-size: 10px !important;
    letter-spacing: 1px !important; text-transform: uppercase !important;
    border-radius: var(--r-sm) !important; font-weight: 400 !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.13) !important; color: white !important;
}

/* ════════════════════════════════════════════
   METRICS
════════════════════════════════════════════ */
div[data-testid="stMetric"] {
    background: var(--canvas) !important;
    border: 1px solid var(--ink-100) !important;
    border-top: 3px solid var(--ink-900) !important;
    border-radius: 0 0 var(--r-md) var(--r-md) !important;
    padding: 20px 22px 18px !important;
    box-shadow: var(--sh-sm) !important;
    transition: border-top-color 0.2s, box-shadow 0.2s, transform 0.2s !important;
}
div[data-testid="stMetric"]:hover {
    border-top-color: var(--brand) !important;
    box-shadow: var(--sh-md) !important; transform: translateY(-2px) !important;
}
div[data-testid="stMetricLabel"] > div {
    font-family: var(--f-mono) !important; font-size: 9px !important;
    font-weight: 500 !important; letter-spacing: 2.5px !important;
    text-transform: uppercase !important; color: var(--ink-500) !important;
}
div[data-testid="stMetricValue"] > div {
    font-family: var(--f-display) !important; font-size: 36px !important;
    font-weight: 600 !important; color: var(--ink-900) !important;
    letter-spacing: -1.5px !important; line-height: 1.05 !important; margin-top: 6px !important;
}
div[data-testid="stMetricDelta"] svg { display: none !important; }

/* ════════════════════════════════════════════
   STATUS
════════════════════════════════════════════ */
div[data-testid="stStatus"] {
    background: var(--canvas-warm) !important;
    border: 1px solid var(--ink-100) !important;
    border-radius: var(--r-lg) !important; box-shadow: var(--sh-sm) !important;
    font-family: var(--f-mono) !important; font-size: 12px !important;
}
div[data-testid="stStatus"] p {
    font-family: var(--f-mono) !important; font-size: 11px !important;
    color: var(--ink-500) !important; line-height: 2.2 !important;
}
div[data-testid="stStatus"] p::before { content: "›  "; color: var(--brand); font-weight: 600; }

/* ════════════════════════════════════════════
   ALERTS
════════════════════════════════════════════ */
div[data-testid="stAlert"] {
    border-radius: var(--r-sm) !important; font-family: var(--f-body) !important;
    font-size: 13px !important; border: none !important; border-left: 3px solid !important;
}
div[data-testid="stAlert"][class*="warning"] { background: var(--neutral-bg) !important; border-left-color: var(--neutral-mid) !important; }
div[data-testid="stAlert"][class*="error"]   { background: var(--bear-bg) !important;    border-left-color: var(--bear-mid) !important; }
div[data-testid="stAlert"][class*="success"] { background: var(--bull-bg) !important;    border-left-color: var(--bull-mid) !important; }
div[data-testid="stAlert"][class*="info"]    { background: var(--brand-dim) !important;  border-left-color: var(--brand) !important; }

/* ════════════════════════════════════════════
   TABS
════════════════════════════════════════════ */
div[data-testid="stTabs"] [role="tablist"] {
    background: transparent !important; border-bottom: 1px solid var(--ink-100) !important;
    border-radius: 0 !important; padding: 0 !important; gap: 0 !important;
    width: 100% !important; margin-bottom: 28px !important;
}
div[data-testid="stTabs"] button[role="tab"] {
    font-family: var(--f-mono) !important; font-size: 10px !important;
    font-weight: 500 !important; letter-spacing: 2px !important;
    text-transform: uppercase !important; color: var(--ink-300) !important;
    border-radius: 0 !important; border: none !important;
    border-bottom: 2px solid transparent !important;
    padding: 14px 22px !important; transition: all 0.15s !important;
    background: transparent !important; margin-bottom: -1px !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: transparent !important; color: var(--ink-900) !important;
    border-bottom: 2px solid var(--ink-900) !important;
}
div[data-testid="stTabs"] button[role="tab"]:hover:not([aria-selected="true"]) { color: var(--ink-700) !important; }
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"]    { display: none !important; }

/* ════════════════════════════════════════════
   JSON
════════════════════════════════════════════ */
div[data-testid="stJson"] {
    background: var(--ink-900) !important; border-radius: var(--r-md) !important;
    font-family: var(--f-mono) !important; font-size: 11.5px !important;
    padding: 20px !important; border: none !important;
}

/* ════════════════════════════════════════════
   MARKDOWN
════════════════════════════════════════════ */
.stMarkdown h1 { font-family: var(--f-display) !important; font-weight: 600 !important; font-size: 30px !important; letter-spacing: -0.5px !important; color: var(--ink-900) !important; }
.stMarkdown h2 { font-family: var(--f-mono) !important; font-weight: 500 !important; font-size: 10px !important; letter-spacing: 2.5px !important; text-transform: uppercase !important; color: var(--ink-500) !important; margin-top: 32px !important; padding-top: 20px !important; border-top: 1px solid var(--ink-100) !important; }
.stMarkdown h3 { font-family: var(--f-body) !important; font-weight: 600 !important; font-size: 15px !important; color: var(--ink-900) !important; }
.stMarkdown p, .stMarkdown li { font-family: var(--f-body) !important; font-size: 14px !important; line-height: 1.85 !important; color: var(--ink-700) !important; }
.stMarkdown strong { color: var(--ink-900) !important; font-weight: 600 !important; }
.stMarkdown code { font-family: var(--f-mono) !important; font-size: 11px !important; background: var(--ink-50) !important; color: var(--brand) !important; padding: 2px 7px !important; border-radius: var(--r-xs) !important; border: 1px solid var(--ink-100) !important; }

/* ════════════════════════════════════════════
   ANIMATIONS
════════════════════════════════════════════ */
@keyframes fadeUp {
    from { opacity:0; transform:translateY(18px); }
    to   { opacity:1; transform:translateY(0); }
}
@keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
@keyframes pulse-live {
    0%,100% { box-shadow: 0 0 0 0 rgba(18,160,92,0.4); }
    60%      { box-shadow: 0 0 0 5px rgba(18,160,92,0); }
}
.anim-up { animation: fadeUp 0.55s cubic-bezier(0.22,1,0.36,1) both; }
.anim-in { animation: fadeIn 0.4s ease both; }
.d1 { animation-delay:0.05s; } .d2 { animation-delay:0.12s; }
.d3 { animation-delay:0.19s; } .d4 { animation-delay:0.26s; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def _load_json_output(path: str) -> dict:
    if not os.path.exists(path):
        return {"_missing": True}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {"_load_error": str(e)}


# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:

    st.markdown("""
    <div style="padding:28px 20px 22px;border-bottom:1px solid rgba(255,255,255,0.07);margin-bottom:24px;">
        <div style="display:flex;align-items:center;gap:11px;margin-bottom:18px;">
            <div style="width:34px;height:34px;border-radius:8px;
                        background:linear-gradient(135deg,#1400FF,#6B00FF);
                        display:flex;align-items:center;justify-content:center;
                        font-size:15px;color:white;flex-shrink:0;
                        box-shadow:0 4px 16px rgba(20,0,255,0.35);">&#9672;</div>
            <div>
                <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:20px;
                            font-weight:600;color:white;letter-spacing:-0.3px;line-height:1;">
                    OptiTrade
                </div>
                <div style="font-family:'IBM Plex Mono',monospace;font-size:8.5px;
                            color:rgba(255,255,255,0.28);letter-spacing:2px;
                            text-transform:uppercase;margin-top:3px;">
                    v2.1 · AI Strategist
                </div>
            </div>
        </div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                    color:rgba(255,255,255,0.20);letter-spacing:1.5px;
                    text-transform:uppercase;line-height:2.2;
                    border-top:1px solid rgba(255,255,255,0.06);padding-top:14px;">
            NSE · NIFTY 50 · Index Derivatives<br>
            Multi-Agent · Sequential Pipeline
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                letter-spacing:2.5px;text-transform:uppercase;color:rgba(255,255,255,0.26);
                padding:0 2px;margin-bottom:10px;">Target Expiry</div>""",
                unsafe_allow_html=True)

    try:
        expiries = find_nifty_expiry_dates.func(3)
        if not expiries:
            raise ValueError("find_nifty_expiry_dates returned an empty list")
        expiry_date = st.selectbox("Expiry Date", expiries, index=0, label_visibility="collapsed")
    except Exception as e:
        st.warning(f"Could not auto-fetch expiry dates: {e}\nUsing manual input.")
        expiry_date = st.date_input("Expiry Date (manual)", datetime.now() + timedelta(days=7))
        expiry_date = expiry_date.strftime("%Y-%m-%d")

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
    st.markdown("""<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                letter-spacing:2.5px;text-transform:uppercase;color:rgba(255,255,255,0.26);
                padding:0 2px;margin-bottom:10px;">Parameters</div>""",
                unsafe_allow_html=True)

    lookback         = st.slider("Lookback Days",            min_value=15,  max_value=60,   value=30)
    backtest_period  = st.slider("Backtest Period",          min_value=30,  max_value=90,   value=60)
    sentiment_window = st.number_input("Sentiment Window (Days)", min_value=1, max_value=7, value=4)
    lot_size         = st.number_input("Lot Size",           min_value=25,  max_value=1000, value=50, step=25)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.divider()
    if st.button("&#8635;  Reset Session", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    st.markdown("""<div style="padding:20px 4px 8px;font-family:'IBM Plex Mono',monospace;
                font-size:8.5px;color:rgba(255,255,255,0.15);line-height:2.2;letter-spacing:0.5px;">
                Not financial advice · &copy; OptiTrade 2025</div>""",
                unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  AUTH  (TTL-aware — logic unchanged)
# ─────────────────────────────────────────────
AUTH_TTL_SECONDS = 3600

def _should_reauthenticate() -> bool:
    if "angel_auth" not in st.session_state:
        return True
    if st.session_state.angel_auth.get("status") != "success":
        return True
    return (time.time() - st.session_state.get("angel_auth_time", 0)) > AUTH_TTL_SECONDS

if _should_reauthenticate():
    with st.spinner("Connecting to Angel One..."):
        auth = authenticate_angel.func()
        st.session_state.angel_auth      = auth
        st.session_state.angel_auth_time = time.time()

auth_status = st.session_state.angel_auth.get("status")


# ─────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────
st.markdown("""
<div style="border-top:4px solid #0C0C0E;padding-top:0;margin-bottom:0;">
    <div style="display:flex;align-items:center;justify-content:space-between;
                padding:9px 0 10px;border-bottom:1px solid #E8E8EF;">
        <div style="display:flex;align-items:center;gap:18px;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                         letter-spacing:3px;text-transform:uppercase;color:#AEAEBA;">
                Multi-Agent Options Intelligence
            </span>
            <span style="width:3px;height:3px;border-radius:50%;background:#AEAEBA;display:inline-block;"></span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                         letter-spacing:2px;text-transform:uppercase;color:#AEAEBA;">
                NSE · NIFTY 50
            </span>
        </div>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#AEAEBA;letter-spacing:1px;">
            9 Agents · Sequential
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

col_title, col_status = st.columns([7, 2])

with col_title:
    st.markdown(f"""
    <div class="anim-up" style="padding:30px 0 6px;">
        <div style="font-family:'Cormorant Garamond',Georgia,serif;font-weight:600;
                    font-size:58px;color:#0C0C0E;line-height:0.95;letter-spacing:-2.5px;">
            Opti<span style="color:#1400FF;">Trade</span>
        </div>
        <div style="display:flex;align-items:center;gap:14px;margin-top:14px;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#AEAEBA;">
                Target expiry
            </span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:500;
                         color:#0C0C0E;background:#F4F4F8;border:1px solid #E8E8EF;
                         padding:3px 11px;border-radius:3px;letter-spacing:0.5px;">
                {expiry_date}
            </span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#AEAEBA;">
                Lot&nbsp;{lot_size}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_status:
    st.markdown("<div style='padding-top:38px;display:flex;justify-content:flex-end;'>",
                unsafe_allow_html=True)
    if auth_status == "success":
        st.markdown("""
        <div style="display:inline-flex;flex-direction:column;align-items:flex-end;gap:6px;">
            <div style="display:inline-flex;align-items:center;gap:8px;padding:7px 14px;
                        border-radius:4px;background:#F0FBF5;border:1px solid rgba(18,160,92,0.20);">
                <span style="width:7px;height:7px;border-radius:50%;background:#12A05C;
                             display:inline-block;animation:pulse-live 2.2s ease infinite;"></span>
                <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;
                             font-weight:500;color:#0A6640;letter-spacing:1px;text-transform:uppercase;">
                    Live
                </span>
            </div>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                         color:#AEAEBA;letter-spacing:0.5px;">Angel One · Connected</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        auth_msg = st.session_state.angel_auth.get("message", "Unknown error")
        st.markdown(f"""
        <div style="display:inline-flex;flex-direction:column;align-items:flex-end;gap:6px;">
            <div style="display:inline-flex;align-items:center;gap:8px;padding:7px 14px;
                        border-radius:4px;background:#FFF5F5;border:1px solid rgba(217,48,37,0.20);">
                <span style="width:7px;height:7px;border-radius:50%;background:#D93025;
                             display:inline-block;"></span>
                <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;
                             font-weight:500;color:#8B1A1A;letter-spacing:1px;text-transform:uppercase;">
                    Offline
                </span>
            </div>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#AEAEBA;">
                {auth_msg[:44]}
            </span>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
st.divider()


# ─────────────────────────────────────────────
#  CTA BUTTON
# ─────────────────────────────────────────────
st.markdown("<div style='margin:16px 0 6px;'>", unsafe_allow_html=True)
run_analysis = st.button("&#9889;  Run Full Analysis", type="primary", use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  EXECUTION  (all data-flow logic unchanged)
# ─────────────────────────────────────────────
if run_analysis:

    inputs = {
        "expiry_date":      str(expiry_date),
        "lookback_days":    lookback,
        "backtest_period":  backtest_period,
        "sentiment_window": sentiment_window,
        "lot_size":         lot_size,
    }

    TASK_LABELS = {
        "fetch_market_data":          ("01", "Market Data",  "Real-time spot & option chain"),
        "analyze_technicals":         ("02", "Technicals",   "EMA · RSI · MACD · Bollinger"),
        "analyze_sentiment":          ("03", "Sentiment",    "News flow & psychology"),
        "compute_greeks_volatility":  ("04", "Greeks & Vol", "&#916; &#915; &#920; V · IV surface"),
        "backtest_strategies":        ("05", "Backtesting",  "Historical simulation"),
        "synthesize_strategy":        ("06", "Synthesis",    "Multi-signal fusion"),
        "assess_risk_hedging":        ("07", "Risk",         "Stress tests · stops"),
        "make_final_decision":        ("08", "Decision",     "Final recommendation"),
        "generate_report":            ("09", "Report",       "Markdown output"),
    }

    live_updates: list        = []
    updates_lock              = threading.Lock()
    result_container: dict    = {}
    completed_tasks_set: list = []
    current_tool_state        = {"tool": ""}

    # ── Callbacks ────────────────────────────────────────────────────
    def _on_step(step_output):
        try:
            if hasattr(step_output, 'tool') and step_output.tool:
                msg = f"tool:{step_output.tool}"
            elif hasattr(step_output, 'thought') and step_output.thought:
                msg = f"thought:{str(step_output.thought)[:110]}"
            elif hasattr(step_output, 'result') and step_output.result:
                msg = f"result:{str(step_output.result)[:90]}"
            else:
                msg = "step:processing"
            with updates_lock:
                live_updates.append(("step", msg))
        except Exception:
            pass

    def _on_task(task_output):
        try:
            task_name = (
                getattr(task_output, 'name', '')
                or getattr(task_output, 'description', '')[:60]
                or 'unknown'
            )
            matched = None
            for key in TASK_LABELS:
                if key in str(task_name).lower().replace(" ", "_"):
                    matched = key
                    break
            with updates_lock:
                live_updates.append(("task", matched or str(task_name)[:40]))
        except Exception:
            pass

    def _run_crew(inputs: dict, result_container: dict) -> None:
        try:
            result = OptiTradeCrew(
                step_callback=_on_step,
                task_callback=_on_task
            ).crew().kickoff(inputs=inputs)
            result_container["result"] = result
            result_container["error"]  = None
        except Exception as e:
            result_container["result"] = None
            result_container["error"]  = str(e)

    # ── Pipeline tracker ─────────────────────────────────────────────
    pipeline_slot = st.empty()

    def _render_pipeline(done: list, active_tool: str = ""):
        total    = len(TASK_LABELS)
        next_idx = len(done)
        rows_html = ""

        for i, (key, (num, name, desc)) in enumerate(TASK_LABELS.items()):
            is_done    = key in done
            is_current = (i == next_idx)

            if is_done:
                row_bg = "#F0FBF5"; row_bd = "rgba(18,160,92,0.15)"
                nb = "#12A05C"; nc = "white"; namec = "#0A6640"; descc = "rgba(10,102,64,0.50)"
                badge = "&#10003;"; extra = ""
            elif is_current:
                row_bg = "#F6F7FF"; row_bd = "rgba(20,0,255,0.15)"
                nb = "#1400FF"; nc = "white"; namec = "#1400FF"; descc = "rgba(20,0,255,0.45)"
                badge = num
                tool_pill = (
                    f' <span style="font-family:\'IBM Plex Mono\',monospace;font-size:9px;'
                    f'color:rgba(20,0,255,0.55);background:rgba(20,0,255,0.06);'
                    f'padding:2px 7px;border-radius:3px;border:1px solid rgba(20,0,255,0.12);'
                    f'margin-left:8px;">{active_tool[:30]}</span>'
                ) if active_tool else ""
                extra = tool_pill
            else:
                row_bg = "transparent"; row_bd = "rgba(12,12,14,0.07)"
                nb = "#F4F4F8"; nc = "#AEAEBA"; namec = "#AEAEBA"; descc = "rgba(12,12,14,0.20)"
                badge = num; extra = ""

            rows_html += f"""
            <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;
                        background:{row_bg};border:1px solid {row_bd};
                        border-radius:6px;margin-bottom:5px;">
                <div style="width:26px;height:26px;border-radius:5px;background:{nb};flex-shrink:0;
                            display:flex;align-items:center;justify-content:center;
                            font-family:'IBM Plex Mono',monospace;font-size:10px;
                            font-weight:600;color:{nc};">{badge}</div>
                <div style="flex:1;min-width:0;">
                    <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:13px;
                                font-weight:500;color:{namec};">{name}{extra}</div>
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:9.5px;
                                color:{descc};margin-top:1px;letter-spacing:0.3px;">{desc}</div>
                </div>
            </div>"""

        pct = int(len(done) / total * 100)
        pipeline_slot.markdown(f"""
        <div style="background:white;border:1px solid #E8E8EF;border-radius:14px;
                    padding:18px;box-shadow:0 2px 8px rgba(0,0,0,0.04);margin:8px 0 16px;">
            <div style="margin-bottom:14px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:7px;">
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                                 letter-spacing:2px;text-transform:uppercase;color:#AEAEBA;">
                        Pipeline Progress
                    </span>
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#6B6B78;">
                        {len(done)}/{total} &middot; {pct}%
                    </span>
                </div>
                <div style="height:3px;background:#E8E8EF;border-radius:2px;overflow:hidden;">
                    <div style="height:100%;width:{pct}%;
                                background:linear-gradient(90deg,#1400FF,#6B00FF);
                                border-radius:2px;transition:width 0.4s ease;"></div>
                </div>
            </div>
            {rows_html}
        </div>
        """, unsafe_allow_html=True)

    _render_pipeline([])

    # ── Status / log box ─────────────────────────────────────────────
    status_box = st.status("&#9881;  Initialising pipeline...", expanded=True)

    with status_box:
        st.write("9 agents queued — sequential execution starting...")

        crew_thread = threading.Thread(
            target=_run_crew, args=(inputs, result_container), daemon=True
        )
        crew_thread.start()

        CREW_TIMEOUT_SECONDS = 900
        poll_interval        = 2
        elapsed              = 0
        last_update_count    = 0

        while crew_thread.is_alive():
            time.sleep(poll_interval)
            elapsed += poll_interval

            with updates_lock:
                new_updates = live_updates[last_update_count:]
                last_update_count = len(live_updates)

            rerender = False
            for kind, msg in new_updates:
                if kind == "task":
                    if msg in TASK_LABELS and msg not in completed_tasks_set:
                        completed_tasks_set.append(msg)
                        _, name, _ = TASK_LABELS[msg]
                        st.write(f"&#10003;  {name} complete")
                    current_tool_state["tool"] = ""
                    rerender = True
                elif kind == "step":
                    if msg.startswith("tool:"):
                        current_tool_state["tool"] = msg[5:]
                        rerender = True
                    elif msg.startswith("thought:"):
                        st.write(f"&#8627;  {msg[8:108]}")
                    elif msg.startswith("result:"):
                        st.write(f"&#8627;  {msg[7:90]}")

            if rerender:
                _render_pipeline(completed_tasks_set, current_tool_state["tool"])

            if elapsed % 30 == 0:
                st.write(f"&#9201;  {elapsed}s &middot; {len(completed_tasks_set)}/9 tasks done")

            if elapsed >= CREW_TIMEOUT_SECONDS:
                result_container["error"] = (
                    f"Timed out after {CREW_TIMEOUT_SECONDS}s — "
                    "check logs for last completed task."
                )
                break

        # Final drain
        with updates_lock:
            final_updates = live_updates[last_update_count:]
        for kind, msg in final_updates:
            if kind == "task" and msg in TASK_LABELS and msg not in completed_tasks_set:
                completed_tasks_set.append(msg)
                _, name, _ = TASK_LABELS[msg]
                st.write(f"&#10003;  {name} complete")
        _render_pipeline(completed_tasks_set)

        if result_container.get("error"):
            status_box.update(label="&#10060;  Pipeline Error", state="error", expanded=True)
            st.error(f"Execution failed: {result_container['error']}")
            st.stop()

        st.write("&#10003;  All 9 agents complete — rendering dashboard...")
        status_box.update(label="&#10003;  Analysis Complete", state="complete", expanded=False)

    # ─────────────────────────────────────────
    #  DASHBOARD  (logic unchanged)
    # ─────────────────────────────────────────
    decision_data = _load_json_output("output/final_decision.json")
    if decision_data.get("_missing"):
        st.warning("&#9888;  `final_decision.json` was not written — decision agent may have failed.")
    elif decision_data.get("_load_error"):
        st.warning(f"&#9888;  Could not parse `final_decision.json`: {decision_data['_load_error']}")

    market_data = _load_json_output("output/market_data.json")
    if market_data.get("simulation_warning") or market_data.get("data_source") == "simulated":
        st.warning(
            "&#9888; **Simulated Data:** Live option chain unavailable. "
            "Do not act on this output with real capital."
        )

    recommendation = decision_data.get("final_decision", "HOLD").upper()
    strike         = decision_data.get("strike", "N/A")
    entry_price    = decision_data.get("entry_price", 0)
    conf           = decision_data.get("confidence", 0)
    rationale      = decision_data.get("rationale", "See full report for details.")

    if recommendation in ("CALL", "BUY"):
        sig_bg, sig_bd, sig_fg, sig_badge = "#F0FBF5", "rgba(18,160,92,0.18)", "#0A6640", "#12A05C"
    elif recommendation in ("PUT", "SELL"):
        sig_bg, sig_bd, sig_fg, sig_badge = "#FFF5F5", "rgba(217,48,37,0.18)", "#8B1A1A", "#D93025"
    else:
        sig_bg, sig_bd, sig_fg, sig_badge = "#FFFBEB", "rgba(196,154,0,0.20)", "#7A5C00", "#C49A00"

    # ── Decision banner ───────────────────────
    st.markdown(f"""
    <div class="anim-up" style="border:1px solid {sig_bd};border-top:4px solid {sig_badge};
                background:{sig_bg};border-radius:0 0 14px 14px;
                padding:30px 32px;margin:28px 0 20px;">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:3px;
                    text-transform:uppercase;color:{sig_fg};opacity:0.55;margin-bottom:16px;">
            Strategy Recommendation &middot; AI-Generated
        </div>
        <div style="display:flex;align-items:flex-start;gap:28px;flex-wrap:wrap;">
            <div style="background:{sig_badge};color:white;
                        font-family:'Cormorant Garamond',serif;font-size:36px;font-weight:600;
                        padding:8px 26px;border-radius:4px;letter-spacing:-0.5px;
                        line-height:1.1;flex-shrink:0;">
                {recommendation}
            </div>
            <div style="display:flex;gap:28px;align-items:flex-start;flex-wrap:wrap;">
                <div>
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                                color:{sig_fg};opacity:0.5;letter-spacing:1.5px;
                                text-transform:uppercase;margin-bottom:4px;">Strike</div>
                    <div style="font-family:'Cormorant Garamond',serif;font-size:30px;
                                font-weight:600;color:#0C0C0E;letter-spacing:-1px;">{strike}</div>
                </div>
                <div>
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                                color:{sig_fg};opacity:0.5;letter-spacing:1.5px;
                                text-transform:uppercase;margin-bottom:4px;">Entry</div>
                    <div style="font-family:'Cormorant Garamond',serif;font-size:30px;
                                font-weight:600;color:#0C0C0E;letter-spacing:-1px;">&#8377;{entry_price}</div>
                </div>
                <div>
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                                color:{sig_fg};opacity:0.5;letter-spacing:1.5px;
                                text-transform:uppercase;margin-bottom:4px;">Confidence</div>
                    <div style="font-family:'Cormorant Garamond',serif;font-size:30px;
                                font-weight:600;color:{sig_badge};letter-spacing:-1px;">
                        {conf*100:.0f}%
                    </div>
                </div>
            </div>
        </div>
        <div style="margin-top:22px;padding-top:18px;border-top:1px solid rgba(12,12,14,0.08);">
            <div style="font-family:'IBM Plex Mono',monospace;font-size:8.5px;letter-spacing:2px;
                        text-transform:uppercase;color:rgba(12,12,14,0.28);margin-bottom:10px;">
                Rationale
            </div>
            <div style="font-family:'Cormorant Garamond',Georgia,serif;font-style:italic;
                        font-size:17px;color:#2E2E35;line-height:1.75;max-width:820px;">
                &ldquo;{rationale}&rdquo;
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Metrics ───────────────────────────────
    st.markdown("""<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                letter-spacing:3px;text-transform:uppercase;color:#AEAEBA;margin:4px 0 14px;">
                Key Figures</div>""", unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4, gap="medium")
    with m1: st.metric("Recommendation", recommendation)
    with m2: st.metric("Strike", str(strike))
    with m3: st.metric("Entry Price", f"\u20b9{entry_price}")
    with m4: st.metric("AI Confidence", f"{conf * 100:.0f}%")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── Tabs ─────────────────────────────────
    tab_report, tab_tech, tab_json = st.tabs(["Strategy Report", "Technical Data", "Raw JSON"])

    with tab_report:
        report_path = "output/trading_report.md"
        if os.path.exists(report_path):
            st.markdown("""
            <div style="background:white;border:1px solid #E8E8EF;border-top:2px solid #0C0C0E;
                        border-radius:0 0 12px 12px;overflow:hidden;margin-top:4px;">
                <div style="padding:13px 24px;background:#FAFAF7;border-bottom:1px solid #E8E8EF;
                            display:flex;align-items:center;justify-content:space-between;">
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                                 letter-spacing:2px;text-transform:uppercase;color:#6B6B78;">
                        NIFTY 50 &middot; Options Analysis Report
                    </span>
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#AEAEBA;">
                        output/trading_report.md
                    </span>
                </div>
                <div style="padding:24px 28px;">
            """, unsafe_allow_html=True)
            with open(report_path, "r", encoding="utf-8") as f:
                st.markdown(f.read())
            st.markdown("</div></div>", unsafe_allow_html=True)
        else:
            st.warning("&#9888;  Trading report was not generated. Check agent logs.")

    with tab_tech:
        tech_data = _load_json_output("output/technical_analysis.json")
        if tech_data.get("_missing"):
            st.warning("&#9888;  `technical_analysis.json` was not found.")
        elif tech_data.get("_load_error"):
            st.warning(f"&#9888;  Parse error: {tech_data['_load_error']}")
        else:
            st.markdown("""<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                        letter-spacing:2px;text-transform:uppercase;color:#AEAEBA;margin-bottom:14px;">
                        Technical Indicators &middot; Raw Output</div>""", unsafe_allow_html=True)
            st.json(tech_data)

    with tab_json:
        st.markdown("""<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                    letter-spacing:2px;text-transform:uppercase;color:#AEAEBA;margin-bottom:14px;">
                    Final Decision &middot; Raw JSON</div>""", unsafe_allow_html=True)
        st.json(decision_data)


else:
    # ─────────────────────────────────────────
    #  EMPTY STATE
    #
    #  PERMANENT FIX: use st.components.v1.html() instead of st.markdown().
    #
    #  Root cause of all previous failures:
    #    - st.markdown() runs content through Streamlit's markdown/sanitizer
    #      pipeline which can silently drop or escape HTML it doesn't like,
    #      especially large blocks or content containing certain character
    #      sequences (curly braces in CSS values, HTML entities, etc.)
    #    - f-strings over large HTML templates fail when CSS values like
    #      rgba(0,0,0,0.04) are misread as incomplete format expressions.
    #    - Splitting HTML across multiple st.markdown() calls creates isolated
    #      rendering islands with no shared DOM, so unclosed tags never close.
    #
    #  st.components.v1.html() renders into a true sandboxed iframe.
    #  It receives a raw string — no sanitizer, no markdown parser, no
    #  f-string interpolation on the final payload. It cannot leak as text.
    #  The font @import and all styles are self-contained inside the iframe.
    # ─────────────────────────────────────────

    # Build pipeline strip in Python — safe f-string over small variables only
    preview_steps = [
        ("01", "Market Data"), ("02", "Technicals"), ("03", "Sentiment"),
        ("04", "Greeks"),      ("05", "Backtest"),   ("06", "Synthesis"),
        ("07", "Risk"),        ("08", "Decision"),   ("09", "Report"),
    ]

    pipeline_strip_html = ""
    for i, (num, name) in enumerate(preview_steps):
        connector = (
            ""
            if i == len(preview_steps) - 1
            else "<div style='width:20px;height:1px;background:#E8E8EF;flex-shrink:0;'></div>"
        )
        pipeline_strip_html += (
            "<div style='display:inline-flex;align-items:center;gap:0;'>"
            "<div style='display:flex;flex-direction:column;align-items:center;gap:5px;"
            "background:white;border:1px solid #E8E8EF;border-radius:6px;"
            "padding:10px 12px;min-width:64px;box-shadow:0 1px 3px rgba(0,0,0,0.04);'>"
            "<span style='font-family:IBM Plex Mono,monospace;font-size:9px;"
            "font-weight:600;color:#1400FF;'>" + num + "</span>"
            "<span style='font-family:Plus Jakarta Sans,sans-serif;font-size:10px;"
            "font-weight:500;color:#6B6B78;text-align:center;white-space:nowrap;'>" + name + "</span>"
            "</div>"
            + connector +
            "</div>"
        )

    # Assemble the full HTML document — plain string concatenation, zero f-string risk
    empty_state_html = (
        "<!DOCTYPE html><html><head>"
        "<link rel='preconnect' href='https://fonts.googleapis.com'>"
        "<link href='https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600"
        "&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Plus+Jakarta+Sans:"
        "wght@400;500;600;700&display=swap' rel='stylesheet'>"
        "<style>"
        "* { box-sizing:border-box; margin:0; padding:0; }"
        "body { background:white; font-family:'Plus Jakarta Sans',sans-serif; "
        "       -webkit-font-smoothing:antialiased; padding:52px 24px 32px; }"
        "@keyframes fadeIn { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }"
        ".wrap { animation:fadeIn 0.5s cubic-bezier(0.22,1,0.36,1) both; }"
        "</style></head><body><div class='wrap'>"

        # ── Hero ──
        "<div style='max-width:740px;margin:0 auto 52px;text-align:center;'>"
        "<div style='font-family:IBM Plex Mono,monospace;font-size:9px;letter-spacing:3.5px;"
        "text-transform:uppercase;color:#AEAEBA;margin-bottom:22px;'>"
        "AI-Powered &middot; 9 Agents &middot; Live NSE Data</div>"
        "<div style='font-family:Cormorant Garamond,Georgia,serif;font-weight:600;"
        "font-size:58px;color:#0C0C0E;line-height:1.0;letter-spacing:-2.5px;margin-bottom:18px;'>"
        "Institutional options<br>"
        "<span style='color:#1400FF;'>intelligence</span>,<br>"
        "<span style='font-style:italic;font-weight:400;color:#6B6B78;font-size:50px;'>automated.</span>"
        "</div>"
        "<div style='font-family:Plus Jakarta Sans,sans-serif;font-size:15px;"
        "color:#6B6B78;line-height:1.85;max-width:480px;margin:0 auto;'>"
        "Configure your parameters in the sidebar and run the full "
        "multi-agent pipeline across live Nifty 50 market data."
        "</div></div>"

        # ── Stat strip ──
        "<div style='display:flex;gap:0;border:1px solid #E8E8EF;border-radius:10px;"
        "overflow:hidden;max-width:680px;margin:0 auto 52px;"
        "box-shadow:0 2px 8px rgba(0,0,0,0.04);'>"

        "<div style='flex:1;padding:22px 24px;border-right:1px solid #E8E8EF;text-align:center;'>"
        "<div style='font-family:IBM Plex Mono,monospace;font-size:9px;letter-spacing:2px;"
        "text-transform:uppercase;color:#AEAEBA;margin-bottom:8px;'>Agents</div>"
        "<div style='font-family:Cormorant Garamond,serif;font-size:40px;font-weight:600;"
        "color:#1400FF;letter-spacing:-1.5px;line-height:1;'>9</div></div>"

        "<div style='flex:1;padding:22px 24px;border-right:1px solid #E8E8EF;text-align:center;'>"
        "<div style='font-family:IBM Plex Mono,monospace;font-size:9px;letter-spacing:2px;"
        "text-transform:uppercase;color:#AEAEBA;margin-bottom:8px;'>Data Source</div>"
        "<div style='font-family:Cormorant Garamond,serif;font-size:40px;font-weight:600;"
        "color:#0C0C0E;letter-spacing:-1.5px;line-height:1;'>Live</div></div>"

        "<div style='flex:1;padding:22px 24px;border-right:1px solid #E8E8EF;text-align:center;'>"
        "<div style='font-family:IBM Plex Mono,monospace;font-size:9px;letter-spacing:2px;"
        "text-transform:uppercase;color:#AEAEBA;margin-bottom:8px;'>Exchange</div>"
        "<div style='font-family:Cormorant Garamond,serif;font-size:40px;font-weight:600;"
        "color:#0C0C0E;letter-spacing:-1.5px;line-height:1;'>NSE</div></div>"

        "<div style='flex:1;padding:22px 24px;text-align:center;'>"
        "<div style='font-family:IBM Plex Mono,monospace;font-size:9px;letter-spacing:2px;"
        "text-transform:uppercase;color:#AEAEBA;margin-bottom:8px;'>Model</div>"
        "<div style='font-family:Cormorant Garamond,serif;font-size:40px;font-weight:600;"
        "color:#0C0C0E;letter-spacing:-1.5px;line-height:1;'>GPT&#8209;4o</div></div>"

        "</div>"

        # ── Pipeline preview ──
        "<div style='max-width:900px;margin:0 auto;'>"
        "<div style='font-family:IBM Plex Mono,monospace;font-size:9px;letter-spacing:2.5px;"
        "text-transform:uppercase;color:#AEAEBA;margin-bottom:14px;text-align:center;'>"
        "Sequential Agent Pipeline</div>"
        "<div style='display:flex;align-items:center;justify-content:center;"
        "flex-wrap:wrap;gap:0;row-gap:8px;'>"
        + pipeline_strip_html +
        "</div></div>"

        "</div></body></html>"
    )

    # components.html renders into a true sandboxed iframe —
    # no markdown parser, no sanitizer, no f-string expansion on the payload.
    # height is set generously; scrolling=False keeps it flush with the page.
    components.html(empty_state_html, height=680, scrolling=False)