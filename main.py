import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# =============================================
# Helpers
# =============================================
def _mask(value: str):
    """Mask sensitive env variable values."""
    if not value:
        return None
    if len(value) <= 8:
        return "****"
    return value[:4] + "..." + value[-4:]


# =============================================
# TRAIN (required by CrewAI CLI)
# =============================================
def train():
    print("Training mode not implemented for OptiTrade (live trading analysis system)")


def replay():
    print("Replay mode not implemented for OptiTrade")


# =============================================
# TEST (runs API diagnostics)
# =============================================
def test():
    from .tools import test_all_apis

    print("\n" + "=" * 70)
    print("  OPTITRADE - API TEST MODE")
    print("=" * 70 + "\n")

    result = test_all_apis.func()
    print("\nTest Result:", result.get("status", "unknown"))
    return result


# =============================================
# RUN (main entry point)
# =============================================
def run():
    from .crew import OptiTradeCrew
    from .tools import authenticate_angel, find_nifty_expiry_dates

    print("\n" + "="*70)
    print("  ╔═══════════════════════════════════════════════════════════╗")
    print("  ║         OPTITRADE - AI OPTIONS TRADING SYSTEM              ║")
    print("  ║              Nifty50 Options Analysis & Strategy           ║")
    print("  ║              Powered by Angel One SmartAPI                 ║")
    print("  ╚═══════════════════════════════════════════════════════════╝")
    print("="*70 + "\n")

    print("🔍 Checking prerequisites...\n")

    required_vars = [
        "OPENAI_API_KEY",
        "ANGEL_API_KEY",
        "ANGEL_CLIENT_ID",
        "ANGEL_MPIN",
        "ANGEL_TOTP_SECRET"
    ]

    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            print(f"❌ {var}: NOT FOUND")
            missing.append(var)
        else:
            print(f"✅ {var}: {_mask(value)}")

    print()

    if missing:
        print(f"⚠️  Missing {len(missing)} required environment variable(s)")
        print("\n📋 Setup Instructions:")
        print("1. Copy .env.example to .env")
        print("2. Add your credentials:")
        print("   - OPENAI_API_KEY")
        print("   - ANGEL_API_KEY")
        print("   - ANGEL_CLIENT_ID")
        print("   - ANGEL_MPIN (your trading password/MPIN)")
        print("   - ANGEL_TOTP_SECRET (base32 secret from authenticator app)")
        print("\n💡 Tip: Enable 2FA, click 'Can't scan QR?' to get TOTP secret\n")

        allow_sim = os.getenv("OPTITRADE_ALLOW_SIMULATED", "0") == "1"

        if not sys.stdin.isatty() and not allow_sim:
            print("❌ Non-interactive environment detected — cannot prompt user.")
            print("   Set OPTITRADE_ALLOW_SIMULATED=1 to proceed with simulated data.")
            sys.exit(1)

        response = "y" if allow_sim else input("❓ Continue with simulated data? (y/N): ")

        if response.lower() != "y":
            print("\n❌ Exiting. Please fix missing credentials and try again.")
            sys.exit(1)

        print("\n⚠️  Proceeding with simulated data (option chain will be simulated)\n")

    # =============================================
    # Angel Authentication
    # =============================================
    print("🔌 Testing Angel One SmartAPI connection...\n")

    auth_result = authenticate_angel.func()

    if auth_result.get("status") == "success":
        print("✅ Angel One connection successful!")
        print("   • Access token acquired\n")
    else:
        print("⚠️  Authentication failed")
        print("   Reason:", auth_result.get("error"))
        print("   Message:", auth_result.get("message"))
        print("\n🔧 Troubleshooting:")
        print("   - Verify API key, Client ID, MPIN, TOTP secret")
        print("   - Ensure 2FA enabled in Angel One app\n")

        allow_sim = os.getenv("OPTITRADE_ALLOW_SIMULATED", "0") == "1"

        if not sys.stdin.isatty() and not allow_sim:
            print("❌ Cannot prompt in non-interactive mode — aborting.")
            sys.exit(1)

        response = "y" if allow_sim else input("❓ Continue with simulated data instead? (y/N): ")
        if response.lower() != "y":
            print("\n❌ Exiting. Fix authentication and retry.")
            sys.exit(1)

        print("\n⚠️  Using simulated data for option chain and greeks.\n")

    # =============================================
    # Prepare Template Variables (INPUTS)
    # =============================================
    expiries = find_nifty_expiry_dates.func(3)
    next_expiry = expiries[0] if expiries else (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    inputs = {
        'expiry_date': next_expiry,
        'lookback_days': 30,
        'backtest_period': 60,
        'sentiment_window': 4,
        'lot_size': int(os.getenv("OPTITRADE_LOT_SIZE", 50))
    }
    
    print("📅 Next Nifty50 expiry dates:")
    for idx, exp in enumerate(expiries, 1):
        print(f"   {idx}. {exp}")
    print()
    
    print("📊 Analysis Parameters:")
    print(f"   Target Expiry: {inputs['expiry_date']}")
    print(f"   Lookback Days: {inputs['lookback_days']}")
    print(f"   Backtest Period: {inputs['backtest_period']} days")
    print(f"   Lot Size: {inputs['lot_size']}\n")

    # =============================================
    # Run crew - SIMPLE WAY
    # =============================================
    print("="*70)
    print("Starting OptiTrade Analysis Crew")
    print("="*70 + "\n")

    os.makedirs("output", exist_ok=True)

    start_time = datetime.now()
    print(f"⏰ Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    print("="*70 + "\n")

    try:
        # SIMPLE - Just like your working projects!
        result = OptiTradeCrew().crew().kickoff(inputs=inputs)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
        print("Partial output may be available in output/")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR running crew: {e}")
        print("🔍 See traceback below:\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "="*70)
    print("✅ ANALYSIS COMPLETE!")
    print("="*70)
    print(f"⏰ Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Total duration: {duration:.1f} sec ({duration/60:.1f} min)\n")

    # =============================================
    # Output summary
    # =============================================
    print("📁 Output Files:")
    output_files = [
        'output/market_data.json',
        'output/technical_analysis.json',
        'output/sentiment_analysis.json',
        'output/market_regime.json',
        'output/greeks_volatility.json',
        'output/backtest_results.json',
        'output/advanced_strategies.json',
        'output/strategy_synthesis.json',
        'output/risk_assessment.json',
        'output/portfolio_status.json',
        'output/performance_analysis.json',
        'output/final_decision.json',
        'output/trading_report.md'
    ]

    missing_files = []
    for file in output_files:
        if os.path.exists(file):
            size = os.path.getsize(file)
            print(f"   ✅ {file} ({size:,} bytes)")
        else:
            print(f"   ⚠️  {file} (not found)")
            missing_files.append(file)

    print()

    if missing_files:
        print(f"⚠️  {len(missing_files)} file(s) missing — check logs for agent errors\n")

    print("="*70)
    print("📄 VIEW YOUR REPORT:")
    print("="*70)

    if os.path.exists('output/trading_report.md'):
        print("✅ Main Report: output/trading_report.md\n")
        print("💡 Quick View:")
        print("   Linux/Mac: cat output/trading_report.md")
        print("   Windows:   type output\\trading_report.md")
        print("   VS Code:   code output/trading_report.md")
        
        # Display final decision summary
        try:
            import json
            if os.path.exists('output/final_decision.json'):
                with open('output/final_decision.json', 'r') as f:
                    decision = json.load(f)
                print("\n" + "="*70)
                print("📊 FINAL TRADING DECISION")
                print("="*70)
                print(f"Decision:   {decision.get('final_decision', 'N/A')}")
                print(f"Strike:     {decision.get('strike', 'N/A')}")
                print(f"Expiry:     {decision.get('expiry', 'N/A')}")
                print(f"Confidence: {decision.get('confidence', 0)*100:.1f}%")
                print(f"Entry:      ₹{decision.get('entry_price', 'N/A')}")
                print(f"Stop Loss:  ₹{decision.get('stop_loss', 'N/A')}")
                print(f"Target:     ₹{decision.get('target', 'N/A')}")
                print(f"Lot Size:   {decision.get('lot_size', 'N/A')}")
                print("="*70)
        except Exception as e:
            print(f"\n⚠️  Could not display decision summary: {e}")
    else:
        print("⚠️  No report generated. Review final_decision.json.\n")

    print()
    return result


# =============================================
# Direct execution
# =============================================
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test()
    else:
        run()