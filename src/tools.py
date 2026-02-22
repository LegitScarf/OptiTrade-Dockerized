import os as _os
import builtins as _builtins

# FIX: SmartConnect.__init__ executes:
#   log_folder_path = os.path.join("logs", time.strftime("%Y-%m-%d"))  e.g. "logs/2026-02-22"
#   os.makedirs(log_folder_path, exist_ok=True)
#   logzero.logfile(os.path.join(log_folder_path, "app.log"))
# Under a non-owner container UID the relative "logs/" path is not writable,
# causing [Errno 13] Permission denied: 'logs'. We patch os.makedirs AND
# logzero.logfile BEFORE SmartApi is imported to redirect all writes to /tmp.
_original_makedirs = _os.makedirs

def _patched_makedirs(name, mode=0o777, exist_ok=False):
    name_str = str(name)
    if name_str == 'logs' or name_str.startswith('logs' + _os.sep) or name_str.startswith('logs/'):
        name = _os.path.join('/tmp', 'smartapi_logs', name_str.split('logs' + _os.sep, 1)[-1].split('logs/', 1)[-1])
        exist_ok = True
    return _original_makedirs(name, mode=mode, exist_ok=exist_ok)

_os.makedirs = _patched_makedirs

# Also patch logzero.logfile before SmartApi import since __init__ calls it too
import logzero as _logzero
_logzero.logfile = lambda *args, **kwargs: None

from SmartApi import SmartConnect  # SmartConnect.__init__ now writes safely to /tmp
import json
import logging
import threading
import pyotp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from crewai.tools import tool
import requests

logger = logging.getLogger("OptiTrade.Tools")
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s — %(levelname)s — %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(ch)
logger.setLevel(logging.INFO)

_smart_api = None
_auth_token = None
_feed_token = None
_refresh_token = None
_instrument_master = None

# FIX: Added threading lock to prevent race conditions when async tasks
# (analyze_technicals, analyze_sentiment, compute_greeks_volatility) trigger
# re-authentication simultaneously and overwrite each other's tokens.
_auth_lock = threading.Lock()

NIFTY_SYMBOL_TOKEN = "99926000"
NIFTY_EXCHANGE = "NSE"
NIFTY_TRADING_SYMBOL = "Nifty 50"
NIFTY_LOT_SIZE = 50


# FIX: Replaces the original _is_valid_response() helper.
# The Angel One SmartAPI inconsistently returns dicts, JSON-encoded strings,
# or plain error strings like "Invalid Token". The original code called .get()
# directly on the raw response, causing 'str object has no attribute get'
# whenever the API returned a string. This function normalises all response
# types into a dict before any .get() call is made anywhere in this file.
def _safe_parse_response(response: Any) -> Optional[Dict]:
    if response is None:
        return None
    if isinstance(response, dict):
        return response
    if isinstance(response, str):
        stripped = response.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        logger.warning(f"Angel API returned raw string (not JSON): '{stripped[:120]}'")
        return {"status": False, "message": stripped}
    logger.error(f"Unexpected API response type: {type(response)} — value: {str(response)[:120]}")
    return None


def _is_success(parsed: Optional[Dict]) -> bool:
    if not parsed:
        return False
    status = parsed.get("status")
    return status is True or str(status).lower() == "true"


@tool("Angel One Authentication Tool")
def authenticate_angel() -> Dict[str, Any]:
    """Authenticate with Angel One SmartAPI."""
    global _smart_api, _auth_token, _feed_token, _refresh_token

    # FIX: All writes to shared globals are now protected by _auth_lock
    # to prevent concurrent async tasks from overwriting each other's tokens.
    with _auth_lock:
        try:
            api_key = os.getenv("ANGEL_API_KEY")
            client_id = os.getenv("ANGEL_CLIENT_ID")
            mpin = os.getenv("ANGEL_MPIN")
            totp_secret = os.getenv("ANGEL_TOTP_SECRET")

            if not all([api_key, client_id, mpin, totp_secret]):
                return {
                    "status": "failed",
                    "error": "missing_credentials",
                    "message": "Check .env for ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_MPIN, ANGEL_TOTP_SECRET"
                }

            totp = pyotp.TOTP(totp_secret).now()
            _smart_api = SmartConnect(api_key=api_key)

            # FIX: Raw response is normalised via _safe_parse_response before
            # any .get() is called. Previously generateSession could return a
            # plain string which caused the crash seen in the Streamlit error banner.
            session_data = _safe_parse_response(_smart_api.generateSession(client_id, mpin, totp))

            if session_data and _is_success(session_data):
                data = session_data.get("data") or {}
                # FIX: Guard the nested data field — it can also be a string
                # in edge cases where the API partially fails mid-response.
                if isinstance(data, str):
                    data = {}
                _auth_token = data.get("jwtToken")
                _feed_token = data.get("feedToken")
                _refresh_token = data.get("refreshToken")

                if not _auth_token:
                    return {
                        "status": "failed",
                        "error": "missing_jwt",
                        "message": "Session created but jwtToken was empty — verify credentials"
                    }

                logger.info("✅ Angel One authentication successful")
                return {"status": "success", "message": "Authentication successful"}
            else:
                msg = (session_data or {}).get("message", "Unknown authentication error")
                logger.error(f"❌ Authentication failed: {msg}")
                return {"status": "failed", "error": "auth_failed", "message": str(msg)}

        except Exception as e:
            logger.exception(f"Auth Exception: {e}")
            return {"status": "failed", "error": "exception", "message": str(e)}


@tool("Download Instrument Master")
def download_instrument_master_json() -> Dict[str, Any]:
    """Download and cache instrument master data."""
    global _instrument_master, _smart_api

    try:
        if not _smart_api or not _auth_token:
            auth_result = authenticate_angel.func()
            if auth_result.get("status") != "success":
                return {"status": "failed", "error": "not_authenticated"}

        try:
            url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                instruments = response.json()
                _instrument_master = [
                    inst for inst in instruments
                    if inst.get("exch_seg") in ["NSE", "NFO"] and
                    "NIFTY" in inst.get("name", "").upper()
                ]
                logger.info(f"✅ Downloaded {len(_instrument_master)} Nifty instruments")
                return {"status": "success", "count": len(_instrument_master)}
            else:
                return {"status": "failed", "error": "download_failed", "message": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.warning(f"Download failed: {e}")
            _instrument_master = []
            return {"status": "success", "message": "Using fallback", "count": 0}

    except Exception as e:
        return {"status": "failed", "error": "exception", "message": str(e)}


@tool("Find Nifty50 Expiry Dates")
def find_nifty_expiry_dates(count: int = 3) -> List[str]:
    """Find the next N Nifty50 weekly expiry dates."""
    try:
        expiries = []
        current_date = datetime.now()
        days_ahead = (3 - current_date.weekday()) % 7
        if days_ahead == 0 and current_date.hour >= 15:
            days_ahead = 7

        next_expiry = current_date + timedelta(days=days_ahead if days_ahead > 0 else 7)
        for i in range(count):
            expiries.append((next_expiry + timedelta(weeks=i)).strftime("%Y-%m-%d"))
        return expiries
    except Exception:
        return [(datetime.now() + timedelta(days=7 * i)).strftime("%Y-%m-%d") for i in range(1, count + 1)]


@tool("Get Angel One LTP")
def get_angel_ltp() -> Dict[str, Any]:
    """Get Last Traded Price (LTP) for Nifty50 index."""
    global _smart_api, _auth_token

    try:
        if not _smart_api or not _auth_token:
            auth_result = authenticate_angel.func()
            if auth_result.get("status") != "success":
                return {"status": "failed", "error": "auth_failed", "message": auth_result.get("message")}

        # FIX: Normalise before .get() — ltpData can return a string on session errors.
        ltp_data = _safe_parse_response(_smart_api.ltpData(NIFTY_EXCHANGE, NIFTY_TRADING_SYMBOL, NIFTY_SYMBOL_TOKEN))

        if ltp_data and _is_success(ltp_data):
            data = ltp_data.get("data") or {}
            if isinstance(data, str):
                data = {}
            return {
                "status": "success",
                "ltp": float(data.get("ltp", 0)),
                "timestamp": datetime.now().isoformat(),
                "symbol": "NIFTY50",
                "exchange": NIFTY_EXCHANGE
            }

        msg = (ltp_data or {}).get("message", "Failed to fetch LTP")
        return {"status": "failed", "error": "api_error", "message": str(msg)}

    except Exception as e:
        logger.exception(f"LTP Exception: {e}")
        return {"status": "failed", "error": "exception", "message": str(e)}


@tool("Get Angel One Quote")
def get_angel_quote() -> Dict[str, Any]:
    """Get full OHLC quote for Nifty50 index."""
    global _smart_api, _auth_token

    try:
        if not _smart_api or not _auth_token:
            auth_result = authenticate_angel.func()
            if auth_result.get("status") != "success":
                return {"status": "failed", "error": "auth_failed"}

        # FIX: Normalise before .get() — getMarketData can return a string on session errors.
        quote_data = _safe_parse_response(
            _smart_api.getMarketData(mode="FULL", exchangeTokens={NIFTY_EXCHANGE: [NIFTY_SYMBOL_TOKEN]})
        )

        if quote_data and _is_success(quote_data):
            fetched = (quote_data.get("data") or {}).get("fetched", [])
            if fetched:
                q = fetched[0]
                return {
                    "status": "success",
                    "open": float(q.get("open", 0)),
                    "high": float(q.get("high", 0)),
                    "low": float(q.get("low", 0)),
                    "ltp": float(q.get("ltp", 0)),
                    "close": float(q.get("close", 0)),
                    "volume": int(q.get("volume", 0)),
                    "timestamp": datetime.now().isoformat()
                }

        return {"status": "failed", "error": "no_data", "message": "No quote data returned"}

    except Exception as e:
        logger.exception(f"Quote Exception: {e}")
        return {"status": "failed", "error": "exception", "message": str(e)}


@tool("Get Angel One Historical Data")
def get_angel_historical_data(days: int = 30, interval: str = "ONE_DAY") -> Dict[str, Any]:
    """Get historical OHLC data."""
    global _smart_api, _auth_token

    try:
        if not _smart_api or not _auth_token:
            auth_result = authenticate_angel.func()
            if auth_result.get("status") != "success":
                return {"status": "failed", "error": "not_authenticated"}

        now = datetime.now()
        from_date_str = (now - timedelta(days=days)).strftime("%Y-%m-%d 09:15")
        to_date_str = now.strftime("%Y-%m-%d %H:%M")

        # FIX: Normalise before .get() — getCandleData can return a string on AB1004 errors.
        hist_data = _safe_parse_response(_smart_api.getCandleData({
            "exchange": NIFTY_EXCHANGE,
            "symboltoken": NIFTY_SYMBOL_TOKEN,
            "interval": interval,
            "fromdate": from_date_str,
            "todate": to_date_str
        }))

        if hist_data and _is_success(hist_data):
            candles = hist_data.get("data") or []
            ohlc = [
                {
                    "date": c[0],
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": int(c[5])
                }
                for c in candles if len(c) >= 6
            ]
            return {"status": "success", "data": ohlc, "count": len(ohlc), "interval": interval}

        msg = (hist_data or {}).get("message", "Unknown error")
        return {
            "status": "failed",
            "error": "api_error",
            "message": str(msg),
            "debug_params": f"{from_date_str} → {to_date_str}"
        }

    except Exception as e:
        logger.exception(f"Historical Data Exception: {e}")
        return {"status": "failed", "error": "exception", "message": str(e)}


@tool("Get Angel One Option Chain")
def get_angel_option_chain(expiry_date: str) -> Dict[str, Any]:
    """Get Nifty50 option chain using Batch Fetch."""
    global _smart_api, _auth_token, _instrument_master

    spot_price = 24000
    atm_strike = 24000

    try:
        if not _smart_api or not _auth_token:
            authenticate_angel.func()

        ltp_res = get_angel_ltp.func()
        if ltp_res.get("status") != "success":
            return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)

        spot_price = ltp_res.get("ltp", spot_price)
        atm_strike = round(spot_price / 50) * 50

        if not _instrument_master:
            download_instrument_master_json.func()

        try:
            target_dt = datetime.strptime(expiry_date, "%Y-%m-%d").date()
        except ValueError:
            return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)

        min_s, max_s = atm_strike - 500, atm_strike + 500
        token_map = {}

        for inst in _instrument_master:
            if inst.get("instrumenttype") != "OPTIDX":
                continue
            if "NIFTY" not in inst.get("name", "").upper():
                continue
            try:
                if datetime.strptime(inst.get("expiry", "").title(), "%d%b%Y").date() != target_dt:
                    continue
                strike = float(inst.get("strike", "0"))
                if strike > 50000:
                    strike /= 100
                if min_s <= strike <= max_s:
                    sym = inst.get("symbol", "")
                    token_map[inst.get("token")] = {
                        "strike": strike,
                        "symbol": sym,
                        "type": "CE" if "CE" in sym else "PE"
                    }
            except Exception:
                continue

        if not token_map:
            logger.warning(f"No instruments matched for expiry {expiry_date}")
            return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)

        # FIX: Normalise before .get() — this was the specific crash point shown in
        # the Streamlit error. getMarketData returned a string on token/session errors
        # and the subsequent .get("status") call on that string raised the exception.
        market_data = _safe_parse_response(
            _smart_api.getMarketData(mode="LTP", exchangeTokens={"NFO": list(token_map.keys())})
        )

        option_chain = []
        if market_data and _is_success(market_data):
            fetched = (market_data.get("data") or {}).get("fetched", [])
            for item in fetched:
                t = item.get("symbolToken")
                if t in token_map:
                    d = token_map[t]
                    option_chain.append({
                        "strike": d["strike"],
                        "type": d["type"],
                        "last_price": float(item.get("ltp", 0)),
                        "volume": 0,
                        "oi": 0,
                        "symbol": d["symbol"]
                    })

        if not option_chain:
            logger.warning("Batch fetch returned empty — using simulation")
            return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)

        return {
            "status": "success",
            "spot_price": spot_price,
            "atm_strike": atm_strike,
            "option_chain": option_chain,
            "expiry_date": expiry_date,
            "data_source": "live"
        }

    except Exception as e:
        logger.exception(f"Option Chain Exception: {e}")
        return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)


def _generate_simulated_option_chain(spot_price: float, atm_strike: int, expiry_date: str) -> Dict[str, Any]:
    chain = []
    for s in [atm_strike + (i * 50) for i in range(-10, 11)]:
        for t in ["CE", "PE"]:
            chain.append({
                "strike": s,
                "type": t,
                "last_price": 100.0,
                "volume": 1000,
                "oi": 50000,
                "iv": 0.18
            })
    return {
        "status": "success",
        "spot_price": spot_price,
        "atm_strike": atm_strike,
        "option_chain": chain,
        "expiry_date": expiry_date,
        "data_source": "simulated",
        # FIX: Added simulation_warning flag so final_decision_agent can detect
        # degraded data and force a HOLD decision instead of acting on fake prices.
        "simulation_warning": True
    }


@tool("Calculate Technical Indicators")
def calculate_technical_indicators(historical_data: str) -> Dict[str, Any]:
    """Calculate EMA, RSI, MACD, Bollinger Bands, ATR and trend signals from historical OHLC data."""
    try:
        # Parse the JSON string input - handles both string and list inputs
        import json
        if isinstance(historical_data, str):
            data_list = json.loads(historical_data)
        else:
            data_list = historical_data
        
        if not data_list or len(data_list) < 20:
            return {"status": "failed", "error": "insufficient_data"}

        df = pd.DataFrame(data_list)
        for col in ["close", "high", "low", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.dropna(subset=["close"], inplace=True)

        # Calculate EMAs
        for span in [5, 20, 50]:
            df[f"ema_{span}"] = df["close"].ewm(span=span, adjust=False).mean()

        # Calculate RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df["rsi"] = 100 - (100 / (1 + gain / loss))

        # Calculate MACD
        df["macd"] = df["close"].ewm(span=12, adjust=False).mean() - df["close"].ewm(span=26, adjust=False).mean()
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

        # Calculate Bollinger Bands
        mid = df["close"].rolling(20).mean()
        std = df["close"].rolling(20).std()
        df["bb_upper"] = mid + std * 2
        df["bb_lower"] = mid - std * 2

        # Calculate ATR
        h, l, c = df["high"], df["low"], df["close"]
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        df["atr"] = tr.rolling(14).mean()

        # Analyze current state
        curr = df.iloc[-1]
        trend = "bullish" if curr["ema_5"] > curr["ema_20"] else "bearish" if curr["ema_5"] < curr["ema_20"] else "neutral"

        # Generate signal
        signal = "neutral"
        confidence = 0.5
        if trend == "bullish" and curr["rsi"] < 70 and curr["macd"] > curr["macd_signal"]:
            signal, confidence = "bullish", 0.75
        elif trend == "bearish" and curr["rsi"] > 30 and curr["macd"] < curr["macd_signal"]:
            signal, confidence = "bearish", 0.75

        return {
            "status": "success",
            "signal": signal,
            "confidence": float(confidence),
            "indicators": {
                "rsi": float(curr["rsi"]),
                "macd": float(curr["macd"]),
                "macd_signal": float(curr["macd_signal"]),
                "ema_5": float(curr["ema_5"]),
                "ema_20": float(curr["ema_20"]),
                "ema_50": float(curr["ema_50"]),
                "bb_upper": float(curr["bb_upper"]),
                "bb_lower": float(curr["bb_lower"]),
                "atr": float(curr["atr"])
            },
            "key_levels": {
                "support": float(df["low"].min()),
                "resistance": float(df["high"].max()),
                "current_price": float(curr["close"])
            },
            "trend": trend,
            "rationale": f"{trend.capitalize()} trend with RSI at {curr['rsi']:.1f}"
        }
    except Exception as e:
        logger.exception(f"Technical Indicator Exception: {e}")
        return {"status": "failed", "error": "exception", "message": str(e)}


@tool("Calculate Options Greeks")
def calculate_options_greeks(spot: float, strike: float, expiry: str, opt_type: str,
                              volatility: float = 0.18, risk_free_rate: float = 0.065) -> Dict[str, Any]:
    """Calculate Black-Scholes Greeks."""
    try:
        from scipy.stats import norm

        T = max(1, (datetime.strptime(expiry, "%Y-%m-%d") - datetime.now()).days) / 365.0
        S, K = spot, strike
        r, sigma = risk_free_rate, volatility

        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if opt_type in ("CE", "call"):
            delta = float(norm.cdf(d1))
            theta = float((-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365)
            rho = float(K * T * np.exp(-r * T) * norm.cdf(d2) / 100)
        else:
            delta = float(-norm.cdf(-d1))
            theta = float((-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365)
            rho = float(-K * T * np.exp(-r * T) * norm.cdf(-d2) / 100)

        gamma = float(norm.pdf(d1) / (S * sigma * np.sqrt(T)))
        vega = float(S * norm.pdf(d1) * np.sqrt(T) / 100)

        return {
            "status": "success",
            "strike": strike,
            "type": opt_type,
            "delta": delta,
            "gamma": gamma,
            "theta": theta,
            "vega": vega,
            "rho": rho,
            "iv": volatility,
            "days_to_expiry": int(T * 365)
        }
    except Exception as e:
        return {"status": "failed", "error": "exception", "message": str(e)}


@tool("Backtest Option Strategy")
def backtest_option_strategy(strategy_type: str, historical_data: List[Dict],
                              strike: int, premium: float, lot_size: int = 50) -> Dict[str, Any]:
    """Simple Backtest."""
    try:
        if not historical_data or len(historical_data) < 10:
            return {"status": "failed", "error": "insufficient_data"}

        df = pd.DataFrame(historical_data)
        closes = pd.to_numeric(df["close"], errors="coerce").dropna().tolist()
        trades = []
        wins = 0

        for i in range(len(closes) - 1):
            exit_p = closes[i + 1]
            if strategy_type == "long_call":
                pnl = max(0, exit_p - strike) - premium
            elif strategy_type == "long_put":
                pnl = max(0, strike - exit_p) - premium
            elif strategy_type == "short_call":
                pnl = premium - max(0, exit_p - strike)
            elif strategy_type == "short_put":
                pnl = premium - max(0, strike - exit_p)
            elif strategy_type == "straddle":
                pnl = max(0, exit_p - strike) + max(0, strike - exit_p) - 2 * premium
            else:
                pnl = 0

            pnl_val = pnl * lot_size
            trades.append(pnl_val)
            if pnl_val > 0:
                wins += 1

        total_trades = len(trades)
        returns = np.array(trades)
        sharpe = float(np.mean(returns) / np.std(returns)) if np.std(returns) > 0 else 0.0
        cumulative = np.cumsum(returns)
        max_drawdown = float(np.max(np.maximum.accumulate(cumulative) - cumulative)) if len(cumulative) else 0.0

        return {
            "status": "success",
            "strategy": strategy_type,
            "win_rate": float(wins / total_trades) if total_trades else 0.0,
            "avg_pnl": float(np.mean(returns)),
            "max_drawdown": max_drawdown,
            "sharpe": sharpe,
            "total_trades": total_trades,
            "wins": wins,
            "losses": total_trades - wins
        }
    except Exception as e:
        logger.exception(f"Backtest Exception: {e}")
        return {"status": "failed", "error": "exception", "message": str(e)}


@tool("Analyze Sentiment from Text")
def analyze_sentiment_from_text(text: str) -> Dict[str, Any]:
    """Keyword Sentiment."""
    try:
        pos = ["rally", "surge", "gain", "bull", "bullish", "up", "rise", "strong",
               "positive", "growth", "profit", "high", "record", "boost", "optimistic"]
        neg = ["fall", "drop", "bear", "bearish", "down", "decline", "weak", "negative",
               "loss", "low", "crash", "sell", "selloff", "pessimistic", "concern"]
        lower = text.lower()
        pc = sum(1 for w in pos if w in lower)
        nc = sum(1 for w in neg if w in lower)
        total = pc + nc
        score = float((pc - nc) / total) if total > 0 else 0.0

        return {
            "status": "success",
            "sentiment_score": score,
            "sentiment": "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral",
            "confidence": min(0.9, abs(score) + 0.3),
            "positive_indicators": pc,
            "negative_indicators": nc
        }
    except Exception as e:
        return {"status": "failed", "message": str(e), "sentiment_score": 0.0,
                "sentiment": "neutral", "confidence": 0.0}


@tool("Build Multi-Leg Strategy")
def build_multi_leg_strategy(strategy_type: str, spot_price: float,
                              expiry_date: str, strikes: List[int]) -> Dict[str, Any]:
    """Strategy Builder."""
    return {
        "status": "success",
        "strategy_type": strategy_type,
        "legs": [{"type": "BUY", "strike": strikes[0], "option_type": "CE"}]
    }


@tool("Place Option Order")
def place_option_order(symbol: str, quantity: int, order_type: str = "BUY") -> Dict[str, Any]:
    """Place Order Wrapper."""
    return {"status": "success", "order_id": "SIM_12345", "message": "Simulated Order Placed"}


@tool("Test All APIs")
def test_all_apis() -> Dict[str, Any]:
    """Test all Angel One API connections and tools."""
    results = {"status": "testing", "tests": {}}

    print("\n" + "=" * 70)
    print("TESTING ANGEL ONE SMARTAPI INTEGRATION")
    print("=" * 70 + "\n")

    auth_result = authenticate_angel.func()
    results["tests"]["authentication"] = {
        "status": auth_result.get("status"),
        "message": auth_result.get("message", auth_result.get("error"))
    }
    if auth_result.get("status") != "success":
        results["status"] = "failed"
        return results

    ltp_result = get_angel_ltp.func()
    results["tests"]["ltp"] = {"status": ltp_result.get("status"), "value": ltp_result.get("ltp")}

    quote_result = get_angel_quote.func()
    results["tests"]["quote"] = {"status": quote_result.get("status")}

    hist_result = get_angel_historical_data.func(days=30)
    results["tests"]["historical"] = {"status": hist_result.get("status"), "records": hist_result.get("count", 0)}

    expiries = find_nifty_expiry_dates.func(1)
    next_expiry = expiries[0] if expiries else None

    if next_expiry:
        chain_result = get_angel_option_chain.func(next_expiry)
        results["tests"]["option_chain"] = {
            "status": chain_result.get("status"),
            "data_source": chain_result.get("data_source"),
            "strikes": len(chain_result.get("option_chain", []))
        }

    if hist_result.get("status") == "success":
        tech_result = calculate_technical_indicators.func(hist_result.get("data", []))
        results["tests"]["technical_indicators"] = {
            "status": tech_result.get("status"),
            "signal": tech_result.get("signal")
        }

    if ltp_result.get("status") == "success" and next_expiry:
        spot = ltp_result.get("ltp")
        atm_strike = round(spot / 50) * 50
        greeks_result = calculate_options_greeks.func(spot, atm_strike, next_expiry, "CE")
        results["tests"]["greeks"] = {
            "status": greeks_result.get("status"),
            "delta": greeks_result.get("delta")
        }

    all_ok = all(t.get("status") in ("success", "skipped") for t in results["tests"].values())
    results["status"] = "success" if all_ok else "partial"

    print("=" * 70)
    print(f"TEST SUMMARY: {results['status'].upper()}")
    print("=" * 70 + "\n")

    return results