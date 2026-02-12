import os
import json
import logging
import pyotp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from crewai.tools import tool
from SmartApi import SmartConnect
import requests

# =============================================
# Logger Configuration
# =============================================
logger = logging.getLogger("OptiTrade.Tools")
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s — %(levelname)s — %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(ch)
logger.setLevel(logging.INFO)

# =============================================
# Global Angel One SmartAPI Instance
# =============================================
_smart_api = None
_auth_token = None
_feed_token = None
_refresh_token = None
_instrument_master = None

# =============================================
# Constants
# =============================================
NIFTY_SYMBOL_TOKEN = "99926000"  # NSE Nifty50 token
NIFTY_EXCHANGE = "NSE"
NIFTY_TRADING_SYMBOL = "Nifty 50"
NIFTY_LOT_SIZE = 50

# =============================================
# HELPER: Safe API Response Parser
# =============================================
def _is_valid_response(response: Any) -> bool:
    """Check if API response is a valid dictionary"""
    return isinstance(response, dict)

# =============================================
# AUTHENTICATION
# =============================================

@tool("Angel One Authentication Tool")
def authenticate_angel() -> Dict[str, Any]:
    """Authenticate with Angel One SmartAPI."""
    global _smart_api, _auth_token, _feed_token, _refresh_token
    
    try:
        api_key = os.getenv("ANGEL_API_KEY")
        client_id = os.getenv("ANGEL_CLIENT_ID")
        mpin = os.getenv("ANGEL_MPIN")
        totp_secret = os.getenv("ANGEL_TOTP_SECRET")
        
        if not all([api_key, client_id, mpin, totp_secret]):
            return {"status": "failed", "error": "missing_credentials", "message": "Check .env file"}
        
        totp = pyotp.TOTP(totp_secret).now()
        _smart_api = SmartConnect(api_key=api_key)
        
        session_data = _smart_api.generateSession(client_id, mpin, totp)
        
        # Safe check
        if _is_valid_response(session_data) and session_data.get("status"):
            data = session_data.get("data", {})
            _auth_token = data.get("jwtToken")
            _feed_token = data.get("feedToken")
            _refresh_token = data.get("refreshToken")
            logger.info("✅ Angel One authentication successful")
            return {"status": "success", "message": "Authentication successful"}
        else:
            # Handle if session_data is a string or invalid dict
            msg = session_data if isinstance(session_data, str) else session_data.get("message", "Unknown error")
            return {"status": "failed", "error": "auth_failed", "message": str(msg)}
            
    except Exception as e:
        logger.exception(f"Auth Exception: {e}")
        return {"status": "failed", "error": "exception", "message": str(e)}

# =============================================
# INSTRUMENT MASTER
# =============================================

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
                    if inst.get('exch_seg') in ['NSE', 'NFO'] and 
                    'NIFTY' in inst.get('name', '').upper()
                ]
                logger.info(f"✅ Downloaded {len(_instrument_master)} Nifty instruments")
                return {"status": "success", "count": len(_instrument_master)}
            else:
                return {"status": "failed", "error": "download_failed"}
                
        except Exception as e:
            logger.warning(f"Download failed: {e}")
            _instrument_master = []
            return {"status": "success", "message": "Using fallback", "count": 0}
            
    except Exception as e:
        return {"status": "failed", "error": "exception", "message": str(e)}

# =============================================
# NIFTY EXPIRY DATES
# =============================================

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
            expiry_date = next_expiry + timedelta(weeks=i)
            expiries.append(expiry_date.strftime("%Y-%m-%d"))
        return expiries
    except Exception:
        return [(datetime.now() + timedelta(days=7*i)).strftime("%Y-%m-%d") for i in range(1, count+1)]

# =============================================
# MARKET DATA - LTP
# =============================================

@tool("Get Angel One LTP")
def get_angel_ltp() -> Dict[str, Any]:
    """Get Last Traded Price (LTP) for Nifty50 index."""
    global _smart_api, _auth_token
    
    try:
        if not _smart_api or not _auth_token:
            auth_result = authenticate_angel.func()
            if auth_result.get("status") != "success":
                return {"status": "failed", "error": "auth_failed"}
        
        ltp_data = _smart_api.ltpData(NIFTY_EXCHANGE, NIFTY_TRADING_SYMBOL, NIFTY_SYMBOL_TOKEN)
        
        # FIX: Ensure response is a dict before calling .get()
        if _is_valid_response(ltp_data) and ltp_data.get("status"):
            data = ltp_data.get("data", {})
            return {
                "status": "success",
                "ltp": float(data.get("ltp", 0)),
                "timestamp": datetime.now().isoformat()
            }
        else:
            msg = ltp_data if isinstance(ltp_data, str) else ltp_data.get("message", "Unknown API error")
            return {"status": "failed", "error": "api_error", "message": str(msg)}
            
    except Exception as e:
        return {"status": "failed", "error": "exception", "message": str(e)}

# =============================================
# MARKET DATA - QUOTE
# =============================================

@tool("Get Angel One Quote")
def get_angel_quote() -> Dict[str, Any]:
    """Get full OHLC quote for Nifty50 index."""
    global _smart_api, _auth_token
    
    try:
        if not _smart_api or not _auth_token:
            authenticate_angel.func()
        
        quote_data = _smart_api.getMarketData(mode="FULL", exchangeTokens={NIFTY_EXCHANGE: [NIFTY_SYMBOL_TOKEN]})
        
        # FIX: Validate response type
        if _is_valid_response(quote_data) and quote_data.get("status"):
            data = quote_data.get("data", {}).get("fetched", [])
            if data:
                q = data[0]
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
        return {"status": "failed", "error": "no_data"}
            
    except Exception as e:
        return {"status": "failed", "error": "exception", "message": str(e)}

# =============================================
# MARKET DATA - HISTORICAL
# =============================================

@tool("Get Angel One Historical Data")
def get_angel_historical_data(days: int = 30, interval: str = "ONE_DAY") -> Dict[str, Any]:
    """Get historical OHLC data."""
    global _smart_api, _auth_token
    try:
        if not _smart_api or not _auth_token:
            authenticate_angel.func()
        
        now = datetime.now()
        from_date_str = (now - timedelta(days=days)).strftime("%Y-%m-%d 09:15")
        to_date_str = now.strftime("%Y-%m-%d %H:%M") if now.date() == datetime.today().date() else now.strftime("%Y-%m-%d 15:30")
        
        hist_data = _smart_api.getCandleData({
            "exchange": NIFTY_EXCHANGE, "symboltoken": NIFTY_SYMBOL_TOKEN,
            "interval": interval, "fromdate": from_date_str, "todate": to_date_str
        })
        
        # FIX: Validate response type
        if _is_valid_response(hist_data) and hist_data.get("status"):
            candles = hist_data.get("data", [])
            ohlc = [{"date": c[0], "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]} 
                   for c in candles if len(c) >= 6]
            return {"status": "success", "data": ohlc, "count": len(ohlc)}
            
        return {"status": "failed", "error": "api_error"}
            
    except Exception as e:
        return {"status": "failed", "error": "exception", "message": str(e)}

# =============================================
# OPTION CHAIN
# =============================================

@tool("Get Angel One Option Chain")
def get_angel_option_chain(expiry_date: str) -> Dict[str, Any]:
    """Get Nifty50 option chain using Batch Fetch."""
    global _smart_api, _auth_token, _instrument_master
    
    try:
        if not _smart_api or not _auth_token:
            authenticate_angel.func()
        
        # Get Spot
        ltp_res = get_angel_ltp.func()
        if ltp_res.get("status") != "success":
             # If LTP fails, try simulation immediately
             return _generate_simulated_option_chain(24000, 24000, expiry_date)

        spot_price = ltp_res.get("ltp", 0)
        atm_strike = round(spot_price / 50) * 50
        
        if not _instrument_master:
            download_instrument_master_json.func()

        # Parse Date
        try:
            target_dt = datetime.strptime(expiry_date, "%Y-%m-%d").date()
        except:
            return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)

        # Filter Tokens
        min_s, max_s = atm_strike - 500, atm_strike + 500
        token_map = {}
        
        for inst in _instrument_master:
            if inst.get('instrumenttype') != 'OPTIDX' or 'NIFTY' not in inst.get('name', '').upper(): continue
            try:
                if datetime.strptime(inst.get('expiry', '').title(), "%d%b%Y").date() != target_dt: continue
                strike = float(inst.get('strike', '0'))
                if strike > 50000: strike /= 100
                if min_s <= strike <= max_s:
                    token_map[inst.get('token')] = {
                        "strike": strike, "symbol": inst.get('symbol'), 
                        "type": "CE" if "CE" in inst.get('symbol') else "PE"
                    }
            except: continue

        if not token_map:
            return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)

        # Batch Fetch
        tokens = list(token_map.keys())
        market_data = _smart_api.getMarketData(mode="LTP", exchangeTokens={"NFO": tokens})
        
        option_chain = []
        
        # FIX: The critical fix for your specific error
        if _is_valid_response(market_data) and market_data.get("status"):
            fetched = market_data.get("data", {}).get("fetched", [])
            for item in fetched:
                t = item.get("symbolToken")
                if t in token_map:
                    d = token_map[t]
                    option_chain.append({
                        "strike": d["strike"], "type": d["type"],
                        "last_price": float(item.get("ltp", 0)),
                        "volume": 0, "oi": 0, "symbol": d["symbol"]
                    })
        
        if not option_chain:
            logger.warning("Using simulation due to empty batch data")
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
        logger.exception(f"OC Error: {e}")
        # Only simulate if we have a valid spot, else default to 24000
        s = spot_price if 'spot_price' in locals() else 24000
        a = atm_strike if 'atm_strike' in locals() else 24000
        return _generate_simulated_option_chain(s, a, expiry_date)

def _generate_simulated_option_chain(spot_price: float, atm_strike: int, expiry_date: str) -> Dict[str, Any]:
    """Generate simulated data."""
    chain = []
    for s in [atm_strike + (i * 50) for i in range(-10, 11)]:
        for t in ["CE", "PE"]:
            chain.append({
                "strike": s, "type": t, "last_price": 100.0, 
                "volume": 1000, "oi": 50000, "iv": 0.18
            })
    return {
        "status": "success", "spot_price": spot_price, "atm_strike": atm_strike,
        "option_chain": chain, "expiry_date": expiry_date, "data_source": "simulated"
    }

# =============================================
# TECHNICAL INDICATORS
# =============================================

@tool("Calculate Technical Indicators")
def calculate_technical_indicators(historical_data: List[Dict]) -> Dict[str, Any]:
    """Calculate technical indicators."""
    try:
        if not historical_data or len(historical_data) < 20:
            return {"status": "failed", "error": "insufficient_data"}
        
        df = pd.DataFrame(historical_data)
        # Ensure numeric
        cols = ['close', 'high', 'low', 'volume']
        for c in cols: df[c] = pd.to_numeric(df[c])

        # EMA
        for span in [5, 20, 50]:
            df[f'ema_{span}'] = df['close'].ewm(span=span, adjust=False).mean()

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        # BB
        mid = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std()
        df['bb_upper'] = mid + (std * 2)
        df['bb_lower'] = mid - (std * 2)
        
        # ATR
        h, l, c = df['high'], df['low'], df['close']
        tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()

        curr = df.iloc[-1]
        
        # Signal Logic
        trend = "bullish" if curr['ema_5'] > curr['ema_20'] else "bearish"
        signal = "neutral"
        
        if trend == "bullish" and curr['rsi'] < 70: signal = "bullish"
        elif trend == "bearish" and curr['rsi'] > 30: signal = "bearish"

        return {
            "status": "success", "signal": signal, "confidence": 0.75,
            "indicators": {
                "rsi": float(curr['rsi']), "macd": float(curr['macd']),
                "ema_20": float(curr['ema_20']), "atr": float(curr['atr'])
            },
            "key_levels": {"support": float(df['low'].min()), "resistance": float(df['high'].max())},
            "trend": trend
        }
    except Exception as e:
        return {"status": "failed", "error": "exception", "message": str(e)}

# =============================================
# OPTIONS GREEKS
# =============================================

@tool("Calculate Options Greeks")
def calculate_options_greeks(spot: float, strike: float, expiry: str, opt_type: str) -> Dict[str, Any]:
    """Calculate Black-Scholes Greeks."""
    try:
        from scipy.stats import norm
        T = (datetime.strptime(expiry, "%Y-%m-%d") - datetime.now()).days / 365.0
        if T <= 0: T = 0.001
        
        S, K, r, sigma = spot, strike, 0.065, 0.18
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        
        if opt_type == "CE":
            delta = norm.cdf(d1)
        else:
            delta = -norm.cdf(-d1)
            
        return {
            "status": "success", "delta": float(delta), "gamma": float(norm.pdf(d1)/(S*sigma*np.sqrt(T))),
            "iv": sigma
        }
    except Exception as e:
        return {"status": "failed", "message": str(e)}

# =============================================
# BACKTESTING
# =============================================

@tool("Backtest Option Strategy")
def backtest_option_strategy(strategy_type: str, historical_data: List[Dict], strike: int, premium: float) -> Dict[str, Any]:
    """Simple Backtest."""
    try:
        if not historical_data: return {"status": "failed"}
        
        closes = [d['close'] for d in historical_data]
        wins = 0
        for i in range(len(closes)-1):
            pnl = 0
            if strategy_type == "long_call": pnl = max(0, closes[i+1]-strike) - premium
            if pnl > 0: wins += 1
            
        return {
            "status": "success", "win_rate": wins/len(closes), "total_trades": len(closes)
        }
    except Exception as e:
        return {"status": "failed", "message": str(e)}

# =============================================
# SENTIMENT
# =============================================

@tool("Analyze Sentiment from Text")
def analyze_sentiment_from_text(text: str) -> Dict[str, Any]:
    """Keyword Sentiment."""
    try:
        pos = ['bull', 'surge', 'growth', 'up']
        neg = ['bear', 'drop', 'crash', 'down']
        score = sum(1 for w in pos if w in text.lower()) - sum(1 for w in neg if w in text.lower())
        
        return {
            "status": "success", "sentiment_score": float(score),
            "sentiment": "bullish" if score > 0 else "bearish"
        }
    except Exception as e:
        return {"status": "failed", "message": str(e)}

# =============================================
# STRATEGY BUILDER
# =============================================

@tool("Build Multi-Leg Strategy")
def build_multi_leg_strategy(strategy_type: str, spot_price: float, expiry_date: str, strikes: List[int]) -> Dict[str, Any]:
    """Strategy Builder."""
    return {
        "status": "success", "strategy_type": strategy_type,
        "legs": [{"type": "BUY", "strike": strikes[0], "option_type": "CE"}]
    }

# =============================================
# ORDER EXECUTION
# =============================================

@tool("Place Option Order")
def place_option_order(symbol: str, quantity: int, order_type: str = "BUY") -> Dict[str, Any]:
    """Place Order Wrapper."""
    return {"status": "success", "order_id": "SIM_12345", "message": "Simulated Order Placed"}

# import os
# import json
# import logging
# import pyotp
# import pandas as pd
# import numpy as np
# from datetime import datetime, timedelta
# from typing import Dict, List, Any, Optional
# from crewai.tools import tool
# from SmartApi import SmartConnect
# import requests

# # =============================================
# # Logger Configuration
# # =============================================
# logger = logging.getLogger("OptiTrade.Tools")
# if not logger.handlers:
#     ch = logging.StreamHandler()
#     ch.setFormatter(logging.Formatter("%(asctime)s — %(levelname)s — %(message)s", "%Y-%m-%d %H:%M:%S"))
#     logger.addHandler(ch)
# logger.setLevel(logging.INFO)

# # =============================================
# # Global Angel One SmartAPI Instance
# # =============================================
# _smart_api = None
# _auth_token = None
# _feed_token = None
# _refresh_token = None
# _instrument_master = None

# # =============================================
# # Constants
# # =============================================
# NIFTY_SYMBOL_TOKEN = "99926000"  # NSE Nifty50 token
# NIFTY_EXCHANGE = "NSE"
# NIFTY_TRADING_SYMBOL = "Nifty 50"
# NIFTY_LOT_SIZE = 50


# # =============================================
# # AUTHENTICATION
# # =============================================

# @tool("Angel One Authentication Tool")
# def authenticate_angel() -> Dict[str, Any]:
#     """
#     Authenticate with Angel One SmartAPI using credentials from environment variables.
    
#     Returns:
#         Dict with status, message, and tokens if successful
#     """
#     global _smart_api, _auth_token, _feed_token, _refresh_token
    
#     try:
#         api_key = os.getenv("ANGEL_API_KEY")
#         client_id = os.getenv("ANGEL_CLIENT_ID")
#         mpin = os.getenv("ANGEL_MPIN")
#         totp_secret = os.getenv("ANGEL_TOTP_SECRET")
        
#         if not all([api_key, client_id, mpin, totp_secret]):
#             return {
#                 "status": "failed",
#                 "error": "missing_credentials",
#                 "message": "Required environment variables not set: ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_MPIN, ANGEL_TOTP_SECRET"
#             }
        
#         # Generate TOTP
#         totp = pyotp.TOTP(totp_secret).now()
        
#         # Initialize SmartConnect
#         _smart_api = SmartConnect(api_key=api_key)
        
#         # Generate session
#         session_data = _smart_api.generateSession(client_id, mpin, totp)
        
#         if session_data and session_data.get("status"):
#             data = session_data.get("data", {})
#             _auth_token = data.get("jwtToken")
#             _feed_token = data.get("feedToken")
#             _refresh_token = data.get("refreshToken")
            
#             logger.info(" Angel One authentication successful")
            
#             return {
#                 "status": "success",
#                 "message": "Authentication successful",
#                 "auth_token": _auth_token,
#                 "feed_token": _feed_token,
#                 "refresh_token": _refresh_token
#             }
#         else:
#             error_msg = session_data.get("message", "Unknown error")
#             logger.error(f"❌ Authentication failed: {error_msg}")
#             return {
#                 "status": "failed",
#                 "error": "authentication_failed",
#                 "message": error_msg
#             }
            
#     except Exception as e:
#         logger.exception(f"Exception during authentication: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }


# # =============================================
# # INSTRUMENT MASTER
# # =============================================

# # @tool("Download Instrument Master")
# # def download_instrument_master_json() -> Dict[str, Any]:
# #     """
# #     Download and cache the instrument master JSON from Angel One.
# #     Required for token and symbol lookups.
    
# #     Returns:
# #         Dict with status and instrument count
# #     """
# #     global _instrument_master, _smart_api
    
# #     try:
# #         if not _smart_api or not _auth_token:
# #             auth_result = authenticate_angel()
# #             if auth_result.get("status") != "success":
# #                 return {
# #                     "status": "failed",
# #                     "error": "not_authenticated",
# #                     "message": "Authentication required before downloading instruments"
# #                 }
        
# #         # Angel One API method to get all instruments
# #         instruments = _smart_api.getAllInstruments()
        
# #         if instruments:
# #             _instrument_master = instruments
# #             logger.info(f"✅ Downloaded {len(instruments)} instruments")
# #             return {
# #                 "status": "success",
# #                 "message": f"Downloaded {len(instruments)} instruments",
# #                 "count": len(instruments)
# #             }
# #         else:
# #             return {
# #                 "status": "failed",
# #                 "error": "no_data",
# #                 "message": "No instruments returned from API"
# #             }
            
# #     except Exception as e:
# #         logger.exception(f"Failed to download instrument master: {e}")
# #         return {
# #             "status": "failed",
# #             "error": "exception",
# #             "message": str(e)
# #         }

# @tool("Download Instrument Master")
# def download_instrument_master_json() -> Dict[str, Any]:
#     """
#     Download and cache the instrument master data from Angel One.
#     Uses searchScrip API to find Nifty options.
    
#     Returns:
#         Dict with status and instrument count
#     """
#     global _instrument_master, _smart_api
    
#     try:
#         if not _smart_api or not _auth_token:
#             auth_result = authenticate_angel.func()
#             if auth_result.get("status") != "success":
#                 return {
#                     "status": "failed",
#                     "error": "not_authenticated",
#                     "message": "Authentication required before downloading instruments"
#                 }
        
#         # Angel One doesn't have getAllInstruments, we'll use searchScrip for Nifty
#         # Or we can download the master file from their CDN
#         try:
#             import requests
            
#             # Download instrument master CSV from Angel One CDN
#             url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
#             response = requests.get(url, timeout=30)
            
#             if response.status_code == 200:
#                 instruments = response.json()
                
#                 # Filter only NSE and NFO instruments for Nifty
#                 _instrument_master = [
#                     inst for inst in instruments 
#                     if inst.get('exch_seg') in ['NSE', 'NFO'] and 
#                     'NIFTY' in inst.get('name', '').upper()
#                 ]
                
#                 logger.info(f"✅ Downloaded {len(_instrument_master)} Nifty instruments")
#                 return {
#                     "status": "success",
#                     "message": f"Downloaded {len(_instrument_master)} Nifty instruments",
#                     "count": len(_instrument_master)
#                 }
#             else:
#                 logger.warning(f"Failed to download instruments: HTTP {response.status_code}")
#                 return {
#                     "status": "failed",
#                     "error": "download_failed",
#                     "message": f"HTTP {response.status_code}"
#                 }
                
#         except requests.exceptions.RequestException as e:
#             logger.warning(f"Could not download instrument file: {e}")
#             # Fallback: Use searchScrip for specific instruments
#             _instrument_master = []
#             return {
#                 "status": "success",
#                 "message": "Using on-demand instrument search",
#                 "count": 0
#             }
            
#     except Exception as e:
#         logger.exception(f"Failed to download instrument master: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }

# # =============================================
# # NIFTY EXPIRY DATES
# # =============================================

# @tool("Find Nifty50 Expiry Dates")
# def find_nifty_expiry_dates(count: int = 3) -> List[str]:
#     """
#     Find the next N Nifty50 weekly expiry dates (Thursdays).
    
#     Args:
#         count: Number of expiry dates to return
        
#     Returns:
#         List of expiry dates in YYYY-MM-DD format
#     """
#     try:
#         expiries = []
#         current_date = datetime.now()
        
#         # Nifty expires on Thursdays (weekday 3)
#         days_ahead = (3 - current_date.weekday()) % 7
#         if days_ahead == 0 and current_date.hour >= 15:  # After 3:30 PM on Thursday
#             days_ahead = 7
        
#         next_expiry = current_date + timedelta(days=days_ahead if days_ahead > 0 else 7)
        
#         for i in range(count):
#             expiry_date = next_expiry + timedelta(weeks=i)
#             expiries.append(expiry_date.strftime("%Y-%m-%d"))
        
#         logger.info(f"Next {count} Nifty expiries: {expiries}")
#         return expiries
        
#     except Exception as e:
#         logger.exception(f"Error finding expiry dates: {e}")
#         # Return default dates as fallback
#         return [(datetime.now() + timedelta(days=7*i)).strftime("%Y-%m-%d") for i in range(1, count+1)]


# # =============================================
# # MARKET DATA - LTP
# # =============================================

# @tool("Get Angel One LTP")
# def get_angel_ltp() -> Dict[str, Any]:
#     """
#     Get Last Traded Price (LTP) for Nifty50 index.
    
#     Returns:
#         Dict with status, ltp, and timestamp
#     """
#     global _smart_api, _auth_token
    
#     try:
#         if not _smart_api or not _auth_token:
#             auth_result = authenticate_angel.func()
#             if auth_result.get("status") != "success":
#                 return {
#                     "status": "failed",
#                     "error": "not_authenticated",
#                     "message": "Authentication required"
#                 }
        
#         # Get LTP using ltpData method
#         ltp_data = _smart_api.ltpData(NIFTY_EXCHANGE, NIFTY_TRADING_SYMBOL, NIFTY_SYMBOL_TOKEN)
        
#         if ltp_data and ltp_data.get("status"):
#             data = ltp_data.get("data", {})
#             ltp = data.get("ltp", 0)
            
#             return {
#                 "status": "success",
#                 "ltp": float(ltp),
#                 "timestamp": datetime.now().isoformat(),
#                 "symbol": "NIFTY50",
#                 "exchange": NIFTY_EXCHANGE
#             }
#         else:
#             error_msg = ltp_data.get("message", "Failed to fetch LTP")
#             return {
#                 "status": "failed",
#                 "error": "api_error",
#                 "message": error_msg
#             }
            
#     except Exception as e:
#         logger.exception(f"Error fetching LTP: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }


# # =============================================
# # MARKET DATA - QUOTE
# # =============================================

# @tool("Get Angel One Quote")
# def get_angel_quote() -> Dict[str, Any]:
#     """
#     Get full OHLC quote for Nifty50 index.
    
#     Returns:
#         Dict with status, open, high, low, ltp, volume
#     """
#     global _smart_api, _auth_token
    
#     try:
#         if not _smart_api or not _auth_token:
#             auth_result = authenticate_angel.func()
#             if auth_result.get("status") != "success":
#                 return {
#                     "status": "failed",
#                     "error": "not_authenticated",
#                     "message": "Authentication required"
#                 }
        
#         # Get full quote
#         quote_data = _smart_api.getMarketData(
#             mode="FULL",
#             exchangeTokens={
#                 NIFTY_EXCHANGE: [NIFTY_SYMBOL_TOKEN]
#             }
#         )
        
#         if quote_data and quote_data.get("status"):
#             data = quote_data.get("data", {}).get("fetched", [])
            
#             if data and len(data) > 0:
#                 quote = data[0]
                
#                 return {
#                     "status": "success",
#                     "open": float(quote.get("open", 0)),
#                     "high": float(quote.get("high", 0)),
#                     "low": float(quote.get("low", 0)),
#                     "ltp": float(quote.get("ltp", 0)),
#                     "close": float(quote.get("close", 0)),
#                     "volume": int(quote.get("volume", 0)),
#                     "timestamp": datetime.now().isoformat(),
#                     "symbol": "NIFTY50"
#                 }
#             else:
#                 return {
#                     "status": "failed",
#                     "error": "no_data",
#                     "message": "No quote data returned"
#                 }
#         else:
#             error_msg = quote_data.get("message", "Failed to fetch quote")
#             return {
#                 "status": "failed",
#                 "error": "api_error",
#                 "message": error_msg
#             }
            
#     except Exception as e:
#         logger.exception(f"Error fetching quote: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }


# # =============================================
# # MARKET DATA - HISTORICAL
# # =============================================

# # @tool("Get Angel One Historical Data")
# # def get_angel_historical_data(days: int = 30, interval: str = "ONE_DAY") -> Dict[str, Any]:
# #     """
# #     Get historical OHLC data for Nifty50.
# #     FIXED: Aligns timestamps to 09:15/15:30 to prevent AB1004 errors.
# #     """
# #     global _smart_api, _auth_token
    
# #     try:
# #         if not _smart_api or not _auth_token:
# #             auth_result = authenticate_angel.func()
# #             if auth_result.get("status") != "success":
# #                 return {"status": "failed", "error": "not_authenticated"}
        
# #         # Calculate date range
# #         to_date = datetime.now()
# #         from_date = to_date - timedelta(days=days)
        
# #         # --- CRITICAL FIX: HARDCODE MARKET HOURS ---
# #         # Angel One 'ONE_DAY' interval fails with arbitrary times like 09:43
# #         from_date_str = from_date.strftime("%Y-%m-%d 09:15")
# #         to_date_str = to_date.strftime("%Y-%m-%d 15:30")
# #         # -------------------------------------------
        
# #         hist_data = _smart_api.getCandleData({
# #             "exchange": NIFTY_EXCHANGE,
# #             "symboltoken": NIFTY_SYMBOL_TOKEN,
# #             "interval": interval,
# #             "fromdate": from_date_str,
# #             "todate": to_date_str
# #         })
        
# #         if hist_data and hist_data.get("status"):
# #             candles = hist_data.get("data", [])
# #             historical_ohlc = []
# #             for candle in candles:
# #                 if len(candle) >= 6:
# #                     historical_ohlc.append({
# #                         "date": candle[0],
# #                         "open": float(candle[1]),
# #                         "high": float(candle[2]),
# #                         "low": float(candle[3]),
# #                         "close": float(candle[4]),
# #                         "volume": int(candle[5])
# #                     })
            
# #             return {
# #                 "status": "success",
# #                 "data": historical_ohlc,
# #                 "count": len(historical_ohlc),
# #                 "interval": interval
# #             }
# #         else:
# #             return {
# #                 "status": "failed", 
# #                 "error": "api_error", 
# #                 "message": hist_data.get("message", "Unknown error")
# #             }
            
# #     except Exception as e:
# #         logger.exception(f"Error fetching historical data: {e}")
# #         return {"status": "failed", "error": "exception", "message": str(e)}

# # 

# @tool("Get Angel One Historical Data")
# def get_angel_historical_data(days: int = 30, interval: str = "ONE_DAY") -> Dict[str, Any]:
#     """
#     Get historical OHLC data for Nifty50.
#     FIXED: Clamps 'todate' to current time to prevent AB1004 (Future Data) errors.
#     """
#     global _smart_api, _auth_token
    
#     try:
#         # 1. Authenticate
#         if not _smart_api or not _auth_token:
#             auth_result = authenticate_angel.func()
#             if auth_result.get("status") != "success":
#                 return {"status": "failed", "error": "not_authenticated"}
        
#         # 2. Calculate Dates
#         now = datetime.now()
#         from_date = now - timedelta(days=days)
        
#         # --- CRITICAL FIX: PREVENT FUTURE TIMESTAMP ---
#         # If 'to_date' is today, use current time (e.g., 14:15) instead of 15:30
#         if now.date() == datetime.today().date():
#              # Use current time, formatted strictly
#             to_date_str = now.strftime("%Y-%m-%d %H:%M")
#         else:
#             # For past days, 15:30 is fine
#             to_date_str = now.strftime("%Y-%m-%d 15:30")
            
#         from_date_str = from_date.strftime("%Y-%m-%d 09:15")
#         # -----------------------------------------------

#         # 3. Fetch Data
#         hist_data = _smart_api.getCandleData({
#             "exchange": NIFTY_EXCHANGE,
#             "symboltoken": NIFTY_SYMBOL_TOKEN,
#             "interval": interval,
#             "fromdate": from_date_str,
#             "todate": to_date_str
#         })
        
#         if hist_data and hist_data.get("status"):
#             candles = hist_data.get("data", [])
#             historical_ohlc = []
#             for candle in candles:
#                 # Angel One returns: [Timestamp, Open, High, Low, Close, Volume]
#                 if len(candle) >= 6:
#                     historical_ohlc.append({
#                         "date": candle[0],
#                         "open": float(candle[1]),
#                         "high": float(candle[2]),
#                         "low": float(candle[3]),
#                         "close": float(candle[4]),
#                         "volume": int(candle[5])
#                     })
            
#             return {
#                 "status": "success",
#                 "data": historical_ohlc,
#                 "count": len(historical_ohlc),
#                 "interval": interval
#             }
#         else:
#             return {
#                 "status": "failed", 
#                 "error": "api_error", 
#                 "message": hist_data.get("message", "Unknown error"),
#                 "debug_params": f"{from_date_str} to {to_date_str}"
#             }
            
#     except Exception as e:
#         logger.exception(f"Error fetching historical data: {e}")
#         return {"status": "failed", "error": "exception", "message": str(e)}


# # =============================================
# # OPTION CHAIN
# # =============================================

# # @tool("Get Angel One Option Chain")
# # def get_angel_option_chain(expiry_date: str) -> Dict[str, Any]:
# #     """
# #     Get Nifty50 option chain for a specific expiry date.
# #     FIXED: Uses metadata matching to handle symbol formats correctly.
# #     """
# #     global _smart_api, _auth_token, _instrument_master
    
# #     try:
# #         if not _smart_api or not _auth_token:
# #             authenticate_angel.func()
        
# #         # 1. Get Spot Price
# #         ltp_result = get_angel_ltp.func()
# #         if ltp_result.get("status") != "success":
# #             return {"status": "failed", "error": "ltp_fetch_failed"}
        
# #         spot_price = ltp_result.get("ltp", 0)
# #         atm_strike = round(spot_price / 50) * 50
        
# #         # 2. Download Master if needed
# #         if not _instrument_master:
# #             download_instrument_master_json.func()

# #         # 3. Parse Target Expiry
# #         try:
# #             target_dt = datetime.strptime(expiry_date, "%Y-%m-%d").date()
# #         except ValueError:
# #             return {"status": "failed", "error": "invalid_date_format"}

# #         option_chain = []
# #         min_strike = atm_strike - 500
# #         max_strike = atm_strike + 500

# #         # 4. Robust Metadata Matching
# #         for inst in _instrument_master:
# #             if inst.get('instrumenttype') != 'OPTIDX': continue
# #             if 'NIFTY' not in inst.get('name', '').upper(): continue
            
# #             # Check Strike
# #             try:
# #                 strike = float(inst.get('strike', '0'))
# #                 if strike > 50000: strike /= 100  # Handle paise format
# #                 if not (min_strike <= strike <= max_strike): continue
# #             except: continue

# #             # Check Expiry (matches 05FEB2026 format)
# #             try:
# #                 inst_exp = datetime.strptime(inst.get('expiry', ''), "%d%b%Y").date()
# #                 if inst_exp != target_dt: continue
# #             except: continue
                
# #             # Fetch Data
# #             try:
# #                 token = inst.get('token')
# #                 symbol = inst.get('symbol')
# #                 data = _smart_api.ltpData("NFO", symbol, token).get("data", {})
                
# #                 option_chain.append({
# #                     "strike": strike,
# #                     "type": "CE" if "CE" in symbol else "PE",
# #                     "last_price": float(data.get("ltp", 0)),
# #                     "volume": int(data.get("volume", 0)),
# #                     "oi": int(data.get("oi", 0)),
# #                     "symbol": symbol
# #                 })
# #             except: continue

# #         if not option_chain:
# #             logger.warning("No live data found. Using simulation.")
# #             return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)

# #         return {
# #             "status": "success",
# #             "spot_price": spot_price,
# #             "atm_strike": atm_strike,
# #             "option_chain": option_chain,
# #             "expiry_date": expiry_date,
# #             "data_source": "live"
# #         }

# #     except Exception as e:
# #         logger.exception(f"Error: {e}")
# #         return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)

# # @tool("Get Angel One Option Chain")
# # def get_angel_option_chain(expiry_date: str) -> Dict[str, Any]:
# #     """
# #     Get Nifty50 option chain for a specific expiry date.
# #     FIXED: Handles UPPERCASE months (FEB -> Feb) and strict strike filtering.
# #     """
# #     global _smart_api, _auth_token, _instrument_master
    
# #     try:
# #         # 1. Authenticate if needed
# #         if not _smart_api or not _auth_token:
# #             authenticate_angel.func()
        
# #         # 2. Get Spot Price
# #         ltp_result = get_angel_ltp.func()
# #         if ltp_result.get("status") != "success":
# #             return {"status": "failed", "error": "ltp_fetch_failed"}
        
# #         spot_price = ltp_result.get("ltp", 0)
# #         atm_strike = round(spot_price / 50) * 50
        
# #         # 3. Download Master if needed
# #         if not _instrument_master:
# #             download_instrument_master_json.func()

# #         # 4. Parse Target Expiry
# #         try:
# #             target_dt = datetime.strptime(expiry_date, "%Y-%m-%d").date()
# #         except ValueError:
# #             return {"status": "failed", "error": "invalid_date_format"}

# #         option_chain = []
# #         min_strike = atm_strike - 500
# #         max_strike = atm_strike + 500

# #         # 5. Filter Instruments
# #         for inst in _instrument_master:
# #             # Quick filters
# #             if inst.get('instrumenttype') != 'OPTIDX': continue
# #             if 'NIFTY' not in inst.get('name', '').upper(): continue
            
# #             # --- DATE FIX: Handle "05FEB2026" vs "05Feb2026" ---
# #             try:
# #                 # .title() converts "05FEB2026" to "05Feb2026" for %b parsing
# #                 raw_expiry = inst.get('expiry', '')
# #                 inst_exp = datetime.strptime(raw_expiry.title(), "%d%b%Y").date()
# #                 if inst_exp != target_dt: continue
# #             except: continue
# #             # ---------------------------------------------------

# #             # Check Strike (Handle paise issue: 2400000 -> 24000)
# #             try:
# #                 strike = float(inst.get('strike', '0'))
# #                 if strike > 50000: strike /= 100
# #                 if not (min_strike <= strike <= max_strike): continue
# #             except: continue
                
# #             # Valid Match Found - Fetch Data
# #             try:
# #                 token = inst.get('token')
# #                 symbol = inst.get('symbol')
                
# #                 # Use lightweight ltpData call
# #                 data = _smart_api.ltpData("NFO", symbol, token).get("data", {})
                
# #                 option_chain.append({
# #                     "strike": strike,
# #                     "type": "CE" if "CE" in symbol else "PE",
# #                     "last_price": float(data.get("ltp", 0)),
# #                     "volume": int(data.get("volume", 0)),
# #                     "oi": int(data.get("oi", 0)),
# #                     "symbol": symbol
# #                 })
# #             except: continue

# #         if not option_chain:
# #             logger.warning(f"No live data found for {expiry_date}. Using simulation.")
# #             return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)

# #         logger.info(f"✅ Successfully fetched {len(option_chain)} options contracts.")
# #         return {
# #             "status": "success",
# #             "spot_price": spot_price,
# #             "atm_strike": atm_strike,
# #             "option_chain": option_chain,
# #             "expiry_date": expiry_date,
# #             "data_source": "live"
# #         }

# #     except Exception as e:
# #         logger.exception(f"Error: {e}")
# #         return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)

# @tool("Get Angel One Option Chain")
# def get_angel_option_chain(expiry_date: str) -> Dict[str, Any]:
#     """
#     Get Nifty50 option chain for a specific expiry date.
#     FIXED: Uses BATCH FETCHING to avoid Rate Limit (429) errors.
#     """
#     global _smart_api, _auth_token, _instrument_master
    
#     try:
#         # 1. Authenticate & Get Spot Price
#         if not _smart_api or not _auth_token:
#             authenticate_angel.func()
        
#         ltp_result = get_angel_ltp.func()
#         if ltp_result.get("status") != "success":
#             return {"status": "failed", "error": "ltp_fetch_failed"}
        
#         spot_price = ltp_result.get("ltp", 0)
#         atm_strike = round(spot_price / 50) * 50
        
#         # 2. Download Master if needed
#         if not _instrument_master:
#             download_instrument_master_json.func()

#         # 3. Parse Target Expiry
#         try:
#             target_dt = datetime.strptime(expiry_date, "%Y-%m-%d").date()
#         except ValueError:
#             return {"status": "failed", "error": "invalid_date_format"}

#         # 4. Filter Tokens (No API calls here)
#         min_strike = atm_strike - 500
#         max_strike = atm_strike + 500
#         token_map = {} # Store token -> instrument details
        
#         for inst in _instrument_master:
#             if inst.get('instrumenttype') != 'OPTIDX': continue
#             if 'NIFTY' not in inst.get('name', '').upper(): continue
            
#             # Date Match (Handle "05FEB2026")
#             try:
#                 raw_expiry = inst.get('expiry', '')
#                 inst_exp = datetime.strptime(raw_expiry.title(), "%d%b%Y").date()
#                 if inst_exp != target_dt: continue
#             except: continue

#             # Strike Match
#             try:
#                 strike = float(inst.get('strike', '0'))
#                 if strike > 50000: strike /= 100
#                 if min_strike <= strike <= max_strike:
#                     token_map[inst.get('token')] = {
#                         "strike": strike,
#                         "symbol": inst.get('symbol'),
#                         "type": "CE" if "CE" in inst.get('symbol') else "PE"
#                     }
#             except: continue

#         if not token_map:
#             logger.warning(f"No instruments found for {expiry_date}")
#             return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)

#         # 5. BATCH FETCH (The Critical Fix)
#         # We fetch all ~40 tokens in ONE API call
#         tokens_list = list(token_map.keys())
#         logger.info(f"Fetching live data for {len(tokens_list)} contracts...")
        
#         # getMarketData allows fetching multiple tokens
#         market_data = _smart_api.getMarketData(
#             mode="LTP", 
#             exchangeTokens={"NFO": tokens_list}
#         )
        
#         option_chain = []
#         if market_data and market_data.get("status"):
#             fetched_data = market_data.get("data", {}).get("fetched", [])
            
#             for item in fetched_data:
#                 token = item.get("symbolToken") # Note: API returns 'symbolToken'
#                 if token in token_map:
#                     details = token_map[token]
#                     option_chain.append({
#                         "strike": details["strike"],
#                         "type": details["type"],
#                         "last_price": float(item.get("ltp", 0)),
#                         "volume": 0, # LTP mode doesn't return volume, trade-off for speed
#                         "oi": 0,     # LTP mode doesn't return OI
#                         "symbol": details["symbol"]
#                     })
        
#         # If batch fetch failed, return simulated but log error
#         if not option_chain:
#             logger.error("Batch fetch returned empty data")
#             return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)

#         return {
#             "status": "success",
#             "spot_price": spot_price,
#             "atm_strike": atm_strike,
#             "option_chain": option_chain,
#             "expiry_date": expiry_date,
#             "data_source": "live"
#         }

#     except Exception as e:
#         logger.exception(f"Error: {e}")
#         return _generate_simulated_option_chain(spot_price, atm_strike, expiry_date)


# def _generate_simulated_option_chain(spot_price: float, atm_strike: int, expiry_date: str) -> Dict[str, Any]:
#     """
#     Generate simulated option chain when live data is unavailable.
#     Uses Black-Scholes approximation for pricing.
#     """
#     option_chain = []
    
#     # Calculate days to expiry
#     try:
#         exp_dt = datetime.strptime(expiry_date, "%Y-%m-%d")
#         days_to_expiry = (exp_dt - datetime.now()).days
#         days_to_expiry = max(1, days_to_expiry)
#     except:
#         days_to_expiry = 7
    
#     # Simulated IV and risk-free rate
#     iv = 0.18  # 18% volatility
#     r = 0.065  # 6.5% risk-free rate
    
#     strikes = [atm_strike + (i * 50) for i in range(-10, 11)]
    
#     for strike in strikes:
#         # Simple Black-Scholes approximation
#         moneyness = spot_price / strike
#         time_value = np.sqrt(days_to_expiry / 365) * iv * spot_price * 0.4
        
#         # CE price
#         intrinsic_ce = max(0, spot_price - strike)
#         ce_price = intrinsic_ce + time_value * (1 - abs(1 - moneyness))
        
#         # PE price
#         intrinsic_pe = max(0, strike - spot_price)
#         pe_price = intrinsic_pe + time_value * (1 - abs(1 - moneyness))
        
#         option_chain.append({
#             "strike": strike,
#             "type": "CE",
#             "last_price": round(ce_price, 2),
#             "volume": int(np.random.randint(1000, 50000)),
#             "oi": int(np.random.randint(10000, 500000)),
#             "iv": round(iv + np.random.uniform(-0.02, 0.02), 4)
#         })
        
#         option_chain.append({
#             "strike": strike,
#             "type": "PE",
#             "last_price": round(pe_price, 2),
#             "volume": int(np.random.randint(1000, 50000)),
#             "oi": int(np.random.randint(10000, 500000)),
#             "iv": round(iv + np.random.uniform(-0.02, 0.02), 4)
#         })
    
#     return {
#         "status": "success",
#         "spot_price": spot_price,
#         "atm_strike": atm_strike,
#         "option_chain": option_chain,
#         "expiry_date": expiry_date,
#         "data_source": "simulated",
#         "warning": "Using simulated option chain data"
#     }


# # =============================================
# # TECHNICAL INDICATORS
# # =============================================

# @tool("Calculate Technical Indicators")
# def calculate_technical_indicators(historical_data: List[Dict]) -> Dict[str, Any]:
#     """
#     Calculate technical indicators from historical OHLC data.
    
#     Args:
#         historical_data: List of OHLC dicts with date, open, high, low, close, volume
        
#     Returns:
#         Dict with calculated indicators
#     """
#     try:
#         if not historical_data or len(historical_data) < 30:
#             return {
#                 "status": "failed",
#                 "error": "insufficient_data",
#                 "message": "Need at least 30 data points for technical analysis"
#             }
        
#         # Convert to DataFrame
#         df = pd.DataFrame(historical_data)
#         df['close'] = pd.to_numeric(df['close'])
#         df['high'] = pd.to_numeric(df['high'])
#         df['low'] = pd.to_numeric(df['low'])
#         df['volume'] = pd.to_numeric(df['volume'])
        
#         # EMA
#         df['ema_5'] = df['close'].ewm(span=5, adjust=False).mean()
#         df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
#         df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
#         # RSI
#         delta = df['close'].diff()
#         gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
#         loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
#         rs = gain / loss
#         df['rsi'] = 100 - (100 / (1 + rs))
        
#         # MACD
#         exp1 = df['close'].ewm(span=12, adjust=False).mean()
#         exp2 = df['close'].ewm(span=26, adjust=False).mean()
#         df['macd'] = exp1 - exp2
#         df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        
#         # Bollinger Bands
#         df['bb_middle'] = df['close'].rolling(window=20).mean()
#         bb_std = df['close'].rolling(window=20).std()
#         df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
#         df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        
#         # ATR
#         df['tr'] = df[['high', 'low', 'close']].apply(
#             lambda x: max(x['high'] - x['low'], 
#                          abs(x['high'] - x['close']), 
#                          abs(x['low'] - x['close'])), 
#             axis=1
#         )
#         df['atr'] = df['tr'].rolling(window=14).mean()
        
#         # Get latest values
#         latest = df.iloc[-1]
        
#         # Support and Resistance
#         support = df['low'].rolling(window=20).min().iloc[-1]
#         resistance = df['high'].rolling(window=20).max().iloc[-1]
        
#         # Determine trend
#         if latest['ema_5'] > latest['ema_20'] > latest['ema_50']:
#             trend = "bullish"
#         elif latest['ema_5'] < latest['ema_20'] < latest['ema_50']:
#             trend = "bearish"
#         else:
#             trend = "neutral"
        
#         # Generate signal
#         signal = "neutral"
#         confidence = 0.5
        
#         if trend == "bullish" and latest['rsi'] < 70 and latest['macd'] > latest['macd_signal']:
#             signal = "bullish"
#             confidence = 0.75
#         elif trend == "bearish" and latest['rsi'] > 30 and latest['macd'] < latest['macd_signal']:
#             signal = "bearish"
#             confidence = 0.75
        
#         return {
#             "status": "success",
#             "signal": signal,
#             "confidence": float(confidence),
#             "indicators": {
#                 "ema_5": float(latest['ema_5']),
#                 "ema_20": float(latest['ema_20']),
#                 "ema_50": float(latest['ema_50']),
#                 "rsi": float(latest['rsi']),
#                 "macd": float(latest['macd']),
#                 "macd_signal": float(latest['macd_signal']),
#                 "bb_upper": float(latest['bb_upper']),
#                 "bb_middle": float(latest['bb_middle']),
#                 "bb_lower": float(latest['bb_lower']),
#                 "atr": float(latest['atr'])
#             },
#             "key_levels": {
#                 "support": float(support),
#                 "resistance": float(resistance),
#                 "current_price": float(latest['close'])
#             },
#             "trend": trend,
#             "rationale": f"{trend.capitalize()} trend with RSI at {latest['rsi']:.1f}"
#         }
        
#     except Exception as e:
#         logger.exception(f"Error calculating technical indicators: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }


# # =============================================
# # OPTIONS GREEKS
# # =============================================

# @tool("Calculate Options Greeks")
# def calculate_options_greeks(
#     spot_price: float,
#     strike: float,
#     expiry_date: str,
#     option_type: str,
#     volatility: float = 0.18,
#     risk_free_rate: float = 0.065
# ) -> Dict[str, Any]:
#     """
#     Calculate Black-Scholes Greeks for an option.
    
#     Args:
#         spot_price: Current spot price
#         strike: Option strike price
#         expiry_date: Expiry date (YYYY-MM-DD)
#         option_type: 'CE' or 'PE'
#         volatility: Implied volatility (default 0.18)
#         risk_free_rate: Risk-free rate (default 0.065)
        
#     Returns:
#         Dict with delta, gamma, theta, vega, rho
#     """
#     try:
#         from scipy.stats import norm
        
#         # Calculate time to expiry in years
#         exp_dt = datetime.strptime(expiry_date, "%Y-%m-%d")
#         days_to_expiry = (exp_dt - datetime.now()).days
#         T = max(1, days_to_expiry) / 365.0
        
#         S = spot_price
#         K = strike
#         r = risk_free_rate
#         sigma = volatility
        
#         # Black-Scholes d1 and d2
#         d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
#         d2 = d1 - sigma * np.sqrt(T)
        
#         # Calculate Greeks
#         if option_type == "CE":
#             delta = norm.cdf(d1)
#             theta = (-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) 
#                     - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
#             rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
#         else:  # PE
#             delta = -norm.cdf(-d1)
#             theta = (-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) 
#                     + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
#             rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
        
#         gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
#         vega = S * norm.pdf(d1) * np.sqrt(T) / 100
        
#         return {
#             "status": "success",
#             "strike": strike,
#             "type": option_type,
#             "delta": float(delta),
#             "gamma": float(gamma),
#             "theta": float(theta),
#             "vega": float(vega),
#             "rho": float(rho),
#             "iv": volatility,
#             "days_to_expiry": days_to_expiry
#         }
        
#     except Exception as e:
#         logger.exception(f"Error calculating Greeks: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }


# # =============================================
# # BACKTESTING
# # =============================================

# @tool("Backtest Option Strategy")
# def backtest_option_strategy(
#     strategy_type: str,
#     historical_data: List[Dict],
#     strike: int,
#     premium: float,
#     lot_size: int = 50
# ) -> Dict[str, Any]:
#     """
#     Backtest an option strategy on historical data.
    
#     Args:
#         strategy_type: long_call, long_put, short_call, short_put, straddle
#         historical_data: Historical OHLC data
#         strike: Strike price
#         premium: Option premium
#         lot_size: Lot size (default 50 for Nifty)
        
#     Returns:
#         Dict with backtest metrics
#     """
#     try:
#         if len(historical_data) < 10:
#             return {
#                 "status": "failed",
#                 "error": "insufficient_data",
#                 "message": "Need at least 10 data points for backtesting"
#             }
        
#         df = pd.DataFrame(historical_data)
#         df['close'] = pd.to_numeric(df['close'])
        
#         # Initialize tracking
#         trades = []
#         wins = 0
#         losses = 0
#         total_pnl = 0
        
#         # Simple backtest logic
#         for i in range(len(df) - 1):
#             entry_price = df.iloc[i]['close']
#             exit_price = df.iloc[i + 1]['close']
            
#             if strategy_type == "long_call":
#                 pnl = max(0, exit_price - strike) - premium
#             elif strategy_type == "long_put":
#                 pnl = max(0, strike - exit_price) - premium
#             elif strategy_type == "short_call":
#                 pnl = premium - max(0, exit_price - strike)
#             elif strategy_type == "short_put":
#                 pnl = premium - max(0, strike - exit_price)
#             elif strategy_type == "straddle":
#                 ce_pnl = max(0, exit_price - strike) - premium
#                 pe_pnl = max(0, strike - exit_price) - premium
#                 pnl = ce_pnl + pe_pnl
#             else:
#                 pnl = 0
            
#             pnl_value = pnl * lot_size
#             total_pnl += pnl_value
#             trades.append(pnl_value)
            
#             if pnl_value > 0:
#                 wins += 1
#             else:
#                 losses += 1
        
#         # Calculate metrics
#         total_trades = wins + losses
#         win_rate = wins / total_trades if total_trades > 0 else 0
#         avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
#         expectancy = avg_pnl
        
#         # Max drawdown
#         cumulative = np.cumsum(trades)
#         running_max = np.maximum.accumulate(cumulative)
#         drawdown = running_max - cumulative
#         max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
        
#         # Simple Sharpe (returns / std)
#         returns = np.array(trades)
#         sharpe = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
        
#         return {
#             "status": "success",
#             "strategy": strategy_type,
#             "expectancy": float(expectancy),
#             "win_rate": float(win_rate),
#             "max_drawdown": float(max_drawdown),
#             "sharpe": float(sharpe),
#             "avg_pnl": float(avg_pnl),
#             "total_trades": total_trades,
#             "wins": wins,
#             "losses": losses
#         }
        
#     except Exception as e:
#         logger.exception(f"Error backtesting strategy: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }


# # =============================================
# # SENTIMENT ANALYSIS
# # =============================================

# @tool("Analyze Sentiment from Text")
# def analyze_sentiment_from_text(text: str) -> Dict[str, Any]:
#     """
#     Analyze sentiment from news headlines or text.
    
#     Args:
#         text: Text to analyze (can be multiple headlines separated by newlines)
        
#     Returns:
#         Dict with sentiment score and classification
#     """
#     try:
#         # Simple keyword-based sentiment (can be replaced with ML model)
#         positive_words = [
#             'rally', 'surge', 'gain', 'bull', 'bullish', 'up', 'rise', 'strong',
#             'positive', 'growth', 'profit', 'high', 'record', 'boost', 'optimistic'
#         ]
        
#         negative_words = [
#             'fall', 'drop', 'bear', 'bearish', 'down', 'decline', 'weak', 'negative',
#             'loss', 'low', 'crash', 'sell', 'selloff', 'pessimistic', 'concern'
#         ]
        
#         text_lower = text.lower()
        
#         pos_count = sum(1 for word in positive_words if word in text_lower)
#         neg_count = sum(1 for word in negative_words if word in text_lower)
        
#         total = pos_count + neg_count
        
#         if total == 0:
#             sentiment_score = 0.0
#             sentiment = "neutral"
#         else:
#             sentiment_score = (pos_count - neg_count) / total
            
#             if sentiment_score > 0.2:
#                 sentiment = "positive"
#             elif sentiment_score < -0.2:
#                 sentiment = "negative"
#             else:
#                 sentiment = "neutral"
        
#         confidence = min(0.9, abs(sentiment_score) + 0.3)
        
#         return {
#             "status": "success",
#             "sentiment_score": float(sentiment_score),
#             "sentiment": sentiment,
#             "confidence": float(confidence),
#             "positive_indicators": pos_count,
#             "negative_indicators": neg_count
#         }
        
#     except Exception as e:
#         logger.exception(f"Error analyzing sentiment: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e),
#             "sentiment_score": 0.0,
#             "sentiment": "neutral",
#             "confidence": 0.0
#         }


# # =============================================
# # API TEST SUITE
# # =============================================

@tool("Test All APIs")
def test_all_apis() -> Dict[str, Any]:
    """
    Test all Angel One API connections and tools.
    
    Returns:
        Dict with test results for each component
    """
    results = {
        "status": "testing",
        "tests": {}
    }
    
    print("\n" + "="*70)
    print("TESTING ANGEL ONE SMARTAPI INTEGRATION")
    print("="*70 + "\n")
    
    # Test 1: Authentication
    print("1️⃣  Testing Authentication...")
    auth_result = authenticate_angel.func()
    results["tests"]["authentication"] = {
        "status": auth_result.get("status"),
        "message": auth_result.get("message", auth_result.get("error"))
    }
    print(f"   Result: {auth_result.get('status')}")
    print()
    
    if auth_result.get("status") != "success":
        results["status"] = "failed"
        print("❌ Authentication failed. Skipping remaining tests.\n")
        return results
    
    # Test 2: LTP
    print("2️⃣  Testing LTP Fetch...")
    ltp_result = get_angel_ltp.func()
    results["tests"]["ltp"] = {
        "status": ltp_result.get("status"),
        "value": ltp_result.get("ltp")
    }
    print(f"   Result: {ltp_result.get('status')}")
    if ltp_result.get("status") == "success":
        print(f"   Nifty50 LTP: {ltp_result.get('ltp')}")
    print()
    
    # Test 3: Quote
    print("3️⃣  Testing Full Quote...")
    quote_result = get_angel_quote.func()
    results["tests"]["quote"] = {
        "status": quote_result.get("status")
    }
    print(f"   Result: {quote_result.get('status')}")
    print()
    
    # Test 4: Historical Data
    print("4️⃣  Testing Historical Data (30 days)...")
    hist_result = get_angel_historical_data.func(days=30)
    results["tests"]["historical"] = {
        "status": hist_result.get("status"),
        "records": hist_result.get("count", 0)
    }
    print(f"   Result: {hist_result.get('status')}")
    if hist_result.get("status") == "success":
        print(f"   Records: {hist_result.get('count')}")
    print()
    
    # Test 5: Option Chain
    print("5️⃣  Testing Option Chain...")
    expiries = find_nifty_expiry_dates.func(1)
    next_expiry = expiries[0] if expiries else None
    
    if next_expiry:
        chain_result = get_angel_option_chain.func(next_expiry)
        results["tests"]["option_chain"] = {
            "status": chain_result.get("status"),
            "data_source": chain_result.get("data_source"),
            "strikes": len(chain_result.get("option_chain", []))
        }
        print(f"   Result: {chain_result.get('status')}")
        print(f"   Data Source: {chain_result.get('data_source')}")
        print(f"   Strikes: {len(chain_result.get('option_chain', []))}")
    else:
        results["tests"]["option_chain"] = {"status": "failed", "message": "No expiry date"}
    print()
    
    # Test 6: Technical Indicators
    print("6️⃣  Testing Technical Indicators...")
    if hist_result.get("status") == "success":
        tech_result = calculate_technical_indicators.func(hist_result.get("data", []))
        results["tests"]["technical_indicators"] = {
            "status": tech_result.get("status"),
            "signal": tech_result.get("signal")
        }
        print(f"   Result: {tech_result.get('status')}")
        if tech_result.get("status") == "success":
            print(f"   Signal: {tech_result.get('signal')}")
            print(f"   RSI: {tech_result.get('indicators', {}).get('rsi', 0):.2f}")
    else:
        results["tests"]["technical_indicators"] = {"status": "skipped"}
    print()
    
    # Test 7: Greeks
    print("7️⃣  Testing Options Greeks...")
    if ltp_result.get("status") == "success" and next_expiry:
        spot = ltp_result.get("ltp")
        atm_strike = round(spot / 50) * 50
        greeks_result = calculate_options_greeks.func(spot, atm_strike, next_expiry, "CE")
        results["tests"]["greeks"] = {
            "status": greeks_result.get("status"),
            "delta": greeks_result.get("delta")
        }
        print(f"   Result: {greeks_result.get('status')}")
        if greeks_result.get("status") == "success":
            print(f"   Delta: {greeks_result.get('delta', 0):.4f}")
    else:
        results["tests"]["greeks"] = {"status": "skipped"}
    print()
    
    # Final status
    all_success = all(
        test.get("status") in ["success", "skipped"] 
        for test in results["tests"].values()
    )
    
    results["status"] = "success" if all_success else "partial"
    
    print("="*70)
    print(f"TEST SUMMARY: {results['status'].upper()}")
    print("="*70 + "\n")
    
    return results


# # =============================================
# # PORTFOLIO MANAGEMENT
# # =============================================

# @tool("Get Portfolio Positions")
# def get_portfolio_positions() -> Dict[str, Any]:
#     """
#     Get current portfolio positions from Angel One.
    
#     Returns:
#         Dict with status and list of positions
#     """
#     global _smart_api, _auth_token
    
#     try:
#         if not _smart_api or not _auth_token:
#             auth_result = authenticate_angel.func()
#             if auth_result.get("status") != "success":
#                 return {
#                     "status": "failed",
#                     "error": "not_authenticated",
#                     "message": "Authentication required"
#                 }
        
#         # Get positions from Angel One
#         positions_data = _smart_api.position()
#         positions_data = _smart_api.position()
        
#         if positions_data and positions_data.get("status"):
#             positions = positions_data.get("data", [])
            
#             # Calculate total P&L
#             total_pnl = sum(float(pos.get("pnl", 0)) for pos in positions)
            
#             return {
#                 "status": "success",
#                 "positions": positions,
#                 "total_positions": len(positions),
#                 "total_pnl": float(total_pnl),
#                 "timestamp": datetime.now().isoformat()
#             }
#         else:
#             error_msg = positions_data.get("message", "Failed to fetch positions")
#             return {
#                 "status": "failed",
#                 "error": "api_error",
#                 "message": error_msg
#             }
            
#     except Exception as e:
#         logger.exception(f"Error fetching portfolio positions: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }


# @tool("Get Portfolio Holdings")
# def get_portfolio_holdings() -> Dict[str, Any]:
#     """
#     Get current holdings from Angel One.
    
#     Returns:
#         Dict with status and list of holdings
#     """
#     global _smart_api, _auth_token
    
#     try:
#         if not _smart_api or not _auth_token:
#             auth_result = authenticate_angel.func()
#             if auth_result.get("status") != "success":
#                 return {
#                     "status": "failed",
#                     "error": "not_authenticated",
#                     "message": "Authentication required"
#                 }
        
#         # Get holdings from Angel One
#         holdings_data = _smart_api.holding()
#         holdings_data = _smart_api.holding()
        
#         if holdings_data and holdings_data.get("status"):
#             holdings = holdings_data.get("data", [])
            
#             # Calculate total value
#             total_value = sum(float(hold.get("quantity", 0)) * float(hold.get("ltp", 0)) for hold in holdings)
            
#             return {
#                 "status": "success",
#                 "holdings": holdings,
#                 "total_holdings": len(holdings),
#                 "total_value": float(total_value),
#                 "timestamp": datetime.now().isoformat()
#             }
#         else:
#             error_msg = holdings_data.get("message", "Failed to fetch holdings")
#             return {
#                 "status": "failed",
#                 "error": "api_error",
#                 "message": error_msg
#             }
            
#     except Exception as e:
#         logger.exception(f"Error fetching portfolio holdings: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }


# # =============================================
# # ORDER EXECUTION
# # =============================================

# @tool("Place Option Order")
# def place_option_order(
#     symbol: str,
#     exchange: str,
#     order_type: str,
#     product_type: str,
#     quantity: int,
#     price: float = 0,
#     trigger_price: float = 0,
#     validity: str = "DAY"
# ) -> Dict[str, Any]:
#     """
#     Place an option order on Angel One.
    
#     Args:
#         symbol: Trading symbol (e.g., "NIFTY11DEC202524000CE")
#         exchange: Exchange code (NFO for options)
#         order_type: BUY or SELL
#         product_type: INTRADAY, DELIVERY, MARGIN, etc.
#         quantity: Number of lots
#         price: Limit price (0 for market order)
#         trigger_price: Trigger price for SL/SL-M orders
#         validity: DAY or IOC
        
#     Returns:
#         Dict with status and order ID
#     """
#     global _smart_api, _auth_token
    
#     try:
#         if not _smart_api or not _auth_token:
#             auth_result = authenticate_angel.func()
#             if auth_result.get("status") != "success":
#                 return {
#                     "status": "failed",
#                     "error": "not_authenticated",
#                     "message": "Authentication required"
#                 }
        
#         # Place order
#         order_params = {
#             "variety": "NORMAL",
#             "tradingsymbol": symbol,
#             "symboltoken": "",  # Will be fetched from instrument master
#             "transactiontype": order_type,
#             "exchange": exchange,
#             "ordertype": "LIMIT" if price > 0 else "MARKET",
#             "producttype": product_type,
#             "duration": validity,
#             "price": str(price) if price > 0 else "0",
#             "squareoff": "0",
#             "stoploss": str(trigger_price) if trigger_price > 0 else "0",
#             "quantity": str(quantity)
#         }
        
#         order_result = _smart_api.placeOrder(order_params)
        
#         if order_result and order_result.get("status"):
#             return {
#                 "status": "success",
#                 "order_id": order_result.get("data", {}).get("orderid"),
#                 "message": "Order placed successfully",
#                 "timestamp": datetime.now().isoformat()
#             }
#         else:
#             error_msg = order_result.get("message", "Failed to place order")
#             return {
#                 "status": "failed",
#                 "error": "api_error",
#                 "message": error_msg
#             }
            
#     except Exception as e:
#         logger.exception(f"Error placing order: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }


# # =============================================
# # MARKET REGIME DETECTION
# # =============================================

# @tool("Detect Market Regime")
# def detect_market_regime(historical_data: List[Dict], lookback_days: int = 30) -> Dict[str, Any]:
#     """
#     Detect current market regime (trending, ranging, volatile, calm).
    
#     Args:
#         historical_data: Historical OHLC data
#         lookback_days: Number of days to analyze
        
#     Returns:
#         Dict with regime classification and characteristics
#     """
#     try:
#         if not historical_data or len(historical_data) < 20:
#             return {
#                 "status": "failed",
#                 "error": "insufficient_data",
#                 "message": "Need at least 20 data points"
#             }
        
#         df = pd.DataFrame(historical_data)
#         df['close'] = pd.to_numeric(df['close'])
#         df['high'] = pd.to_numeric(df['high'])
#         df['low'] = pd.to_numeric(df['low'])
#         df['volume'] = pd.to_numeric(df['volume'])
        
#         # Calculate returns
#         df['returns'] = df['close'].pct_change()
#         df['volatility'] = df['returns'].rolling(window=10).std()
        
#         # Trend detection using ADX-like calculation
#         df['high_low'] = df['high'] - df['low']
#         df['high_close'] = abs(df['high'] - df['close'].shift())
#         df['low_close'] = abs(df['low'] - df['close'].shift())
#         df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        
#         df['plus_dm'] = np.where(
#             (df['high'] - df['high'].shift() > df['low'].shift() - df['low']),
#             df['high'] - df['high'].shift(),
#             0
#         )
#         df['minus_dm'] = np.where(
#             (df['low'].shift() - df['low'] > df['high'] - df['high'].shift()),
#             df['low'].shift() - df['low'],
#             0
#         )
        
#         avg_plus_dm = df['plus_dm'].rolling(window=14).mean()
#         avg_minus_dm = df['minus_dm'].rolling(window=14).mean()
#         avg_tr = df['tr'].rolling(window=14).mean()
        
#         trend_strength = abs(avg_plus_dm.iloc[-1] - avg_minus_dm.iloc[-1]) / avg_tr.iloc[-1] if avg_tr.iloc[-1] > 0 else 0
        
#         current_vol = df['volatility'].iloc[-1]
#         avg_vol = df['volatility'].mean()
#         vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1
        
#         price_range = (df['high'].max() - df['low'].min()) / df['close'].mean()
        
#         if trend_strength > 0.3:
#             if vol_ratio > 1.2:
#                 regime = "trending_volatile"
#             else:
#                 regime = "trending_calm"
#         else:
#             if vol_ratio > 1.2:
#                 regime = "ranging_volatile"
#             else:
#                 regime = "ranging_calm"
        
#         # Determine direction if trending
#         direction = "neutral"
#         if trend_strength > 0.3:
#             if avg_plus_dm.iloc[-1] > avg_minus_dm.iloc[-1]:
#                 direction = "bullish"
#             else:
#                 direction = "bearish"
        
#         return {
#             "status": "success",
#             "regime": regime,
#             "direction": direction,
#             "trend_strength": float(trend_strength),
#             "volatility_ratio": float(vol_ratio),
#             "price_range_pct": float(price_range * 100),
#             "confidence": float(min(0.9, trend_strength + 0.3)),
#             "recommended_strategies": {
#                 "trending_volatile": ["momentum", "breakout"],
#                 "trending_calm": ["trend_following", "swing"],
#                 "ranging_volatile": ["straddle", "strangle"],
#                 "ranging_calm": ["iron_condor", "butterfly"]
#             }.get(regime, ["neutral"])
#         }
        
#     except Exception as e:
#         logger.exception(f"Error detecting market regime: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }


# # =============================================
# # ADVANCED STRATEGY BUILDER
# # =============================================

# @tool("Build Multi-Leg Strategy")
# def build_multi_leg_strategy(
#     strategy_type: str,
#     spot_price: float,
#     expiry_date: str,
#     strikes: List[int],
#     lot_size: int = 50
# ) -> Dict[str, Any]:
#     """
#     Build complex multi-leg option strategies.
    
#     Args:
#         strategy_type: iron_condor, butterfly, straddle, strangle, spread
#         spot_price: Current spot price
#         expiry_date: Expiry date (YYYY-MM-DD)
#         strikes: List of strike prices
#         lot_size: Lot size (default 50 for Nifty)
        
#     Returns:
#         Dict with strategy details, max profit, max loss, breakevens
#     """
#     try:
#         # Calculate days to expiry
#         exp_dt = datetime.strptime(expiry_date, "%Y-%m-%d")
#         days_to_expiry = (exp_dt - datetime.now()).days
#         days_to_expiry = max(1, days_to_expiry)
        
#         # Get option chain for strikes
#         chain_result = get_angel_option_chain.func(expiry_date)
#         if chain_result.get("status") != "success":
#             return {
#                 "status": "failed",
#                 "error": "option_chain_failed",
#                 "message": "Could not fetch option chain"
#             }
        
#         option_chain = chain_result.get("option_chain", [])
        
#         # Build strategy based on type
#         legs = []
#         total_cost = 0
#         max_profit = 0
#         max_loss = 0
#         breakevens = []
        
#         if strategy_type == "straddle":
#             # Buy ATM call and put
#             atm_strike = round(spot_price / 50) * 50
#             ce_price = next((opt.get("last_price", 0) for opt in option_chain 
#                            if opt.get("strike") == atm_strike and opt.get("type") == "CE"), 0)
#             pe_price = next((opt.get("last_price", 0) for opt in option_chain 
#                            if opt.get("strike") == atm_strike and opt.get("type") == "PE"), 0)
            
#             total_cost = (ce_price + pe_price) * lot_size
#             max_loss = total_cost
#             max_profit = float('inf')
#             breakevens = [
#                 atm_strike - (ce_price + pe_price),
#                 atm_strike + (ce_price + pe_price)
#             ]
            
#             legs = [
#                 {"type": "BUY", "option_type": "CE", "strike": atm_strike, "premium": ce_price},
#                 {"type": "BUY", "option_type": "PE", "strike": atm_strike, "premium": pe_price}
#             ]
        
#         elif strategy_type == "iron_condor":
#             # Sell OTM call spread and OTM put spread
#             if len(strikes) < 4:
#                 return {
#                     "status": "failed",
#                     "error": "insufficient_strikes",
#                     "message": "Iron condor requires 4 strikes"
#                 }
            
#             strikes = sorted(strikes)
#             # Sell lower put, buy lower put, sell higher call, buy higher call
#             # Simplified calculation
#             max_profit = sum(strikes[i+1] - strikes[i] for i in range(len(strikes)-1)) * lot_size * 0.1
#             max_loss = (strikes[-1] - strikes[0]) * lot_size - max_profit
#             breakevens = [strikes[0] + max_profit/lot_size, strikes[-1] - max_profit/lot_size]
            
#             legs = [
#                 {"type": "SELL", "option_type": "PE", "strike": strikes[0]},
#                 {"type": "BUY", "option_type": "PE", "strike": strikes[1]},
#                 {"type": "SELL", "option_type": "CE", "strike": strikes[2]},
#                 {"type": "BUY", "option_type": "CE", "strike": strikes[3]}
#             ]
        
#         elif strategy_type == "butterfly":
#             # Buy lower strike, sell 2 middle strikes, buy higher strike
#             if len(strikes) < 3:
#                 return {
#                     "status": "failed",
#                     "error": "insufficient_strikes",
#                     "message": "Butterfly requires at least 3 strikes"
#                 }
            
#             strikes = sorted(strikes)
#             # Simplified: max profit at middle strike, max loss is net debit
#             max_profit = (strikes[1] - strikes[0]) * lot_size
#             max_loss = total_cost  # Net premium paid
#             breakevens = [
#                 strikes[0] + total_cost/lot_size,
#                 strikes[-1] - total_cost/lot_size
#             ]
            
#             legs = [
#                 {"type": "BUY", "option_type": "CE", "strike": strikes[0]},
#                 {"type": "SELL", "option_type": "CE", "strike": strikes[1], "quantity": 2},
#                 {"type": "BUY", "option_type": "CE", "strike": strikes[-1]}
#             ]
        
#         else:
#             return {
#                 "status": "failed",
#                 "error": "unsupported_strategy",
#                 "message": f"Strategy type {strategy_type} not supported"
#             }
        
#         return {
#             "status": "success",
#             "strategy_type": strategy_type,
#             "legs": legs,
#             "total_cost": float(total_cost),
#             "max_profit": float(max_profit),
#             "max_loss": float(max_loss),
#             "breakevens": [float(be) for be in breakevens],
#             "risk_reward_ratio": float(max_profit / abs(max_loss)) if max_loss != 0 else 0,
#             "days_to_expiry": days_to_expiry,
#             "lot_size": lot_size
#         }
        
#     except Exception as e:
#         logger.exception(f"Error building multi-leg strategy: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }


# # =============================================
# # PERFORMANCE MONITORING
# # =============================================

# @tool("Calculate Strategy Performance")
# def calculate_strategy_performance(
#     strategy_name: str,
#     entry_date: str,
#     entry_price: float,
#     current_price: float,
#     quantity: int,
#     lot_size: int = 50
# ) -> Dict[str, Any]:
#     """
#     Calculate performance metrics for a strategy.
    
#     Args:
#         strategy_name: Name of the strategy
#         entry_date: Entry date (YYYY-MM-DD)
#         entry_price: Entry price per lot
#         current_price: Current price per lot
#         quantity: Number of lots
#         lot_size: Lot size
        
#     Returns:
#         Dict with performance metrics
#     """
#     try:
#         entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
#         days_held = (datetime.now() - entry_dt).days
        
#         total_investment = entry_price * quantity * lot_size
#         current_value = current_price * quantity * lot_size
#         pnl = current_value - total_investment
#         pnl_pct = (pnl / total_investment * 100) if total_investment > 0 else 0
        
#         # Annualized return
#         annualized_return = (pnl_pct / days_held * 365) if days_held > 0 else 0
        
#         return {
#             "status": "success",
#             "strategy_name": strategy_name,
#             "entry_date": entry_date,
#             "days_held": days_held,
#             "entry_price": float(entry_price),
#             "current_price": float(current_price),
#             "quantity": quantity,
#             "total_investment": float(total_investment),
#             "current_value": float(current_value),
#             "pnl": float(pnl),
#             "pnl_percentage": float(pnl_pct),
#             "annualized_return": float(annualized_return),
#             "timestamp": datetime.now().isoformat()
#         }
        
#     except Exception as e:
#         logger.exception(f"Error calculating strategy performance: {e}")
#         return {
#             "status": "failed",
#             "error": "exception",
#             "message": str(e)
#         }