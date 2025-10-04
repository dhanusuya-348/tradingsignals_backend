# algo/runner.py
import datetime
import os
import sys
import pandas as pd
import concurrent.futures

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use relative imports since we're inside the algo folder
from .data.fetch_price import get_price_data
from .data.fetch_sentiment import get_sentiment_score
from .indicators.macd import calculate_macd
from .indicators.rsi import calculate_rsi
from .indicators.bollinger import calculate_bollinger_bands
from .indicators.volatility import calculate_volatility
from .indicators.volume import calculate_volume_metrics
from .logic.signal_engine import generate_live_signal as core_generate_live_signal
from .logic.risk_manager import calculate_risk_management
from .logic.signal_timer import estimate_signal_duration
from .backtesting.backtester import run_backtest
from .backtesting.evaluator import evaluate_backtest_results
from .data.fetch_news_utils import fetch_rss_headlines
from .reports.visualization import plot_backtest_results, plot_price_with_indicators
from .reports.generate_pdf import create_pdf_report

# Ensure directories exist
os.makedirs("reports/plots", exist_ok=True)
os.makedirs("reports/generated_pdfs", exist_ok=True)


# -------------------- Timeout Helper --------------------
def run_with_timeout(func, *args, timeout=20, default=None, **kwargs):
    """Runs a function with a timeout. If it exceeds, returns default."""
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        print(f"Timeout in {func.__name__}, returning default")
        return default
    except Exception as e:
        print(f"Error in {func.__name__}: {e}")
        return default


# -------------------- Timeframe selection --------------------
def get_timeframes_for_symbol(symbol: str):
    """
    Return (ltf, main_tf, htf) depending on symbol.
    - BTC/ETH use larger main timeframe (30m) for better stability:
        -> (30m, 1h, 4h)  OR (30m main? see below)
      The user wanted BTC/ETH to be (30m, 1h, 4h) — we interpret main_tf as the middle timeframe.
    - Others use (15m, 1h, 4h) where main_tf = 15m.
    NOTE: We return (ltf, main_tf, htf) where main_tf is the timeframe used as base.
    """
    s = (symbol or "").upper()
    # Accept common suffixes like BTC, BTCUSDT, ETH, ETHUSDT
    if s.startswith("BTC") or s.startswith("ETH"):
        # For BTC/ETH: choose main 1h with LTF 30m and HTF 4h (better for volatile coins)
        return "30m", "1h", "4h"
    else:
        # Default: quick intraday signals
        return "5m", "15m", "1h"


# -------------------- Live Signal --------------------
def generate_live_signal_api(symbol: str):
    """
    Full live signal generator using multi-timeframe selection based on symbol.
    Returns JSON-style dict with all signal + risk info.

    Timeframes chosen by get_timeframes_for_symbol():
        returns ltf, main_tf, htf
    """
    try:
        print(f"Generating signal for {symbol}")

        # determine timeframes
        ltf, main_tf, htf = get_timeframes_for_symbol(symbol)
        timeframes = [ltf, main_tf, htf]
        print(f"Using timeframes LTF={ltf}, MTF={main_tf}, HTF={htf}")

        # Fetch price data for all timeframes
        price_data = {}
        for tf in timeframes:
            df = run_with_timeout(get_price_data, symbol, tf, timeout=30, default=None)
            if df is None or df.empty:
                raise RuntimeError(f"Failed to fetch price data for {tf}")
            price_data[tf] = df
            print(f"Fetched {len(df)} data points for {tf}")

        price_df = price_data[main_tf]  # use main_tf as the base timeframe

        # Sentiment (single sentiment score used across TFs)
        sentiment_score, scored_headlines = run_with_timeout(
            get_sentiment_score, symbol, timeout=15, default=("neutral", [])
        )
        sentiment_float = 1.0 if sentiment_score == "bullish" else -1.0 if sentiment_score == "bearish" else 0.0
        print(f"Sentiment: {sentiment_score}")

        # ---------------- Indicators per timeframe ----------------
        indicators_per_tf = {}
        for tf, df in price_data.items():
            try:
                macd_signal = run_with_timeout(calculate_macd, df, timeout=10, default="neutral")
                rsi_val, rsi_signal = run_with_timeout(calculate_rsi, df, timeout=10, default=(50, "neutral"))
                bb_signal = run_with_timeout(calculate_bollinger_bands, df, timeout=10, default="neutral")
                vol = run_with_timeout(calculate_volatility, df, timeout=10, default=0.0)
                vol_metrics = run_with_timeout(calculate_volume_metrics, df, timeout=10, default={})

                indicators_per_tf[tf] = {
                    "macd": macd_signal,
                    "rsi_value": rsi_val,
                    "rsi_signal": rsi_signal,
                    "bb": bb_signal,
                    "volatility": vol,
                    "volume_metrics": vol_metrics,
                }
            except Exception as e:
                print(f"Indicator calculation failed for {tf}: {e}")
                indicators_per_tf[tf] = {
                    "macd": "neutral",
                    "rsi_value": 50,
                    "rsi_signal": "neutral",
                    "bb": "neutral",
                    "volatility": 0.0,
                    "volume_metrics": {}
                }

        # Core signal engine (multi-timeframe input)
        final_signal, confidence, strategies = run_with_timeout(
            core_generate_live_signal, price_data, sentiment_score, symbol,
            timeout=30, default=("HOLD", 0, {})
        )
        print(f"Core signal: {final_signal} (confidence: {confidence}%)")

        # Risk management - run against main_tf price_df (the base)
        # pass main_tf indicators where useful (we pick main_tf indicator values)
        main_indicators = indicators_per_tf.get(main_tf, {})
        indicators_for_risk = {
            "rsi": main_indicators.get("rsi_value", 50),
            "macd": main_indicators.get("macd", "neutral"),
            "bb": main_indicators.get("bb", "neutral"),
            "volatility": main_indicators.get("volatility", 0.0),
            "sentiment": sentiment_float,
            "trend_strength": 0.6,
        }
        risk_result = run_with_timeout(
            calculate_risk_management, price_df, final_signal, indicators_for_risk["volatility"], indicators_for_risk, confidence,
            timeout=15, default={"risk_level": "invalid"}
        )

        # Decision
        final_decision = "REJECTED"
        if final_signal in ["BUY", "SELL"] and risk_result.get('risk_level') not in ['too_weak', 'invalid']:
            final_decision = "APPROVED"
        print(f"Final decision: {final_decision}")

        # Signal duration (use main_tf)
        if final_decision == "APPROVED":
            duration_minutes = run_with_timeout(
                estimate_signal_duration,
                signal_type=final_signal,
                confidence=confidence,
                trend="uptrend" if main_indicators.get("macd") == "bullish" else "downtrend" if main_indicators.get("macd") == "bearish" else "sideways",
                sentiment="bullish" if sentiment_float > 0.3 else "bearish" if sentiment_float < -0.3 else "neutral",
                volatility=main_indicators.get("volatility", 0.0),
                timeframe=main_tf,
                timeout=10,
                default=30
            )
            # derive start from the latest index of the main timeframe df
            try:
                start = price_df.index[-1]
            except Exception:
                start = datetime.datetime.utcnow()
            end = start + datetime.timedelta(minutes=duration_minutes)
            timing_info = {"start": start, "end": end, "duration": f"~{duration_minutes} minutes"}
        else:
            now = datetime.datetime.utcnow()
            timing_info = {"start": now, "end": now + datetime.timedelta(minutes=30), "duration": "No Duration Calculated"}

        # Final result
        result = {
            "symbol": symbol,
            "interval": main_tf,
            "ltf": ltf,
            "htf": htf,
            "signal": final_signal,
            "confidence": confidence,
            "sentiment": sentiment_score,
            "indicators": indicators_per_tf,   # nested indicators per timeframe
            "risk": risk_result,
            "strategies": strategies,
            "decision": final_decision,
            "timing": timing_info,
            "scored_headlines": scored_headlines,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

        print(f"Signal generated successfully: {result['signal']}")
        return result

    except Exception as e:
        print(f"Error in generate_live_signal_api: {e}")
        import traceback
        print(f"Stack trace: {traceback.format_exc()}")
        return {
            "symbol": symbol,
            "interval": None,
            "signal": "HOLD",
            "confidence": 0,
            "error": str(e),
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }


# -------------------- Full PDF Pipeline --------------------
def generate_pdf_report_full(symbol: str):
    """
    Full pipeline (signal + backtest + plots + PDF) using the symbol's main timeframe.
    """
    try:
        # Step 1: Live signal
        result = generate_live_signal_api(symbol)
        main_tf = result.get("interval") or "15m"

        # Step 2: Backtest (base on main_tf)
        price_df = run_with_timeout(get_price_data, symbol, main_tf, timeout=30, default=pd.DataFrame())
        try:
            backtest_df = run_with_timeout(
                run_backtest, price_df, symbol, main_tf, result.get("scored_headlines", []), {main_tf: price_df},
                timeout=60, default=pd.DataFrame()
            )
            summary = run_with_timeout(
                evaluate_backtest_results, backtest_df, timeout=15, default={}
            ) if not backtest_df.empty else {}
        except Exception as e:
            backtest_df = pd.DataFrame()
            summary = {}
            print(f"Backtest failed: {e}")

        # Step 3: Charts
        run_with_timeout(plot_backtest_results, backtest_df, "reports/plots/backtest_chart.png", timeout=20, default=None)
        run_with_timeout(plot_price_with_indicators, price_df, backtest_df, symbol, "reports/plots/price_chart.png", timeout=20, default=None)

        # Step 4: PDF
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = f"reports/generated_pdfs/{symbol}_{main_tf}_{result.get('signal','HOLD')}_{timestamp}_TradingSignals.pdf"

        run_with_timeout(
            create_pdf_report,
            symbol,
            main_tf,
            signal_info=result,
            risk_info=result.get("risk", {}),
            timing_info=result.get("timing", {}),
            summary=summary,
            pdf_path=pdf_path,
            backtest_df=backtest_df,
            scored_headlines=result.get("scored_headlines", []),
            timeout=60,
            default=None
        )

        return {"pdf_path": pdf_path, "summary": summary, "signal": result}

    except Exception as e:
        print(f"Error in generate_pdf_report_full: {e}")
        import traceback
        print(f"Stack trace: {traceback.format_exc()}")
        return {"error": str(e)}



# # algo/runner.py
# import datetime
# import os
# import sys
# import pandas as pd
# import concurrent.futures

# # Add project root to Python path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# # Use relative imports since we're inside the algo folder
# from .data.fetch_price import get_price_data
# from .data.fetch_sentiment import get_sentiment_score
# from .indicators.macd import calculate_macd
# from .indicators.rsi import calculate_rsi
# from .indicators.bollinger import calculate_bollinger_bands
# from .indicators.volatility import calculate_volatility
# from .indicators.volume import calculate_volume_metrics
# from .logic.signal_engine import generate_live_signal as core_generate_live_signal
# from .logic.risk_manager import calculate_risk_management
# from .logic.signal_timer import estimate_signal_duration
# from .backtesting.backtester import run_backtest
# from .backtesting.evaluator import evaluate_backtest_results
# from .reports.visualization import plot_backtest_results, plot_price_with_indicators
# from .reports.generate_pdf import create_pdf_report

# # Ensure directories exist
# os.makedirs("reports/plots", exist_ok=True)
# os.makedirs("reports/generated_pdfs", exist_ok=True)


# # -------------------- Timeout Helper --------------------
# def run_with_timeout(func, *args, timeout=20, default=None, **kwargs):
#     """Runs a function with a timeout. If it exceeds, returns default."""
#     try:
#         with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
#             future = executor.submit(func, *args, **kwargs)
#             return future.result(timeout=timeout)
#     except concurrent.futures.TimeoutError:
#         print(f"Timeout in {func.__name__}, returning default")
#         return default
#     except Exception as e:
#         print(f"Error in {func.__name__}: {e}")
#         return default


# # -------------------- Live Signal --------------------
# def generate_live_signal_api(symbol: str):
#     """
#     Full live signal generator using multi-timeframe (15m main, 5m LTF, 1h HTF).
#     Returns JSON-style dict with all signal + risk info.
#     """
#     try:
#         print(f"Generating signal for {symbol} (15m current timeframe)")

#         # Define timeframes
#         main_tf = "15m"
#         ltf = "5m"
#         htf = "1h"
#         timeframes = [ltf, main_tf, htf]

#         # Fetch price data for all timeframes
#         price_data = {}
#         for tf in timeframes:
#             df = run_with_timeout(get_price_data, symbol, tf, timeout=25, default=None)
#             if df is None or df.empty:
#                 raise RuntimeError(f"Failed to fetch price data for {tf}")
#             price_data[tf] = df
#             print(f"Fetched {len(df)} data points for {tf}")

#         price_df = price_data[main_tf]  # use 15m as the base

#         # Sentiment
#         sentiment_score, scored_headlines = run_with_timeout(
#             get_sentiment_score, symbol, timeout=15, default=("neutral", [])
#         )
#         sentiment_float = 1.0 if sentiment_score == "bullish" else -1.0 if sentiment_score == "bearish" else 0.0
#         print(f"Sentiment: {sentiment_score}")

#         # Indicators (15m base)
#         macd_signal = run_with_timeout(calculate_macd, price_df, timeout=10, default="neutral")
#         rsi_val, rsi_signal = run_with_timeout(calculate_rsi, price_df, timeout=10, default=(50, "neutral"))
#         bb_signal = run_with_timeout(calculate_bollinger_bands, price_df, timeout=10, default="neutral")
#         volatility = run_with_timeout(calculate_volatility, price_df, timeout=10, default=0.0)
#         volume = run_with_timeout(calculate_volume_metrics, price_df, timeout=10, default={})

#         # Core signal engine (multi-timeframe input)
#         final_signal, confidence, strategies = run_with_timeout(
#             core_generate_live_signal, price_data, sentiment_score, symbol,
#             timeout=20, default=("HOLD", 0, {})
#         )
#         print(f"Core signal: {final_signal} (confidence: {confidence}%)")

#         # Risk management
#         indicators = {
#             "rsi": rsi_val,
#             "macd": macd_signal,
#             "bb": bb_signal,
#             "volatility": volatility,
#             "sentiment": sentiment_float,
#             "trend_strength": 0.6,
#         }
#         risk_result = run_with_timeout(
#             calculate_risk_management, price_df, final_signal, volatility, indicators, confidence,
#             timeout=10, default={"risk_level": "invalid"}
#         )

#         # Decision
#         final_decision = "REJECTED"
#         if final_signal in ["BUY", "SELL"] and risk_result.get('risk_level') not in ['too_weak', 'invalid']:
#             final_decision = "APPROVED"
#         print(f"Final decision: {final_decision}")

#         # Signal duration
#         if final_decision == "APPROVED":
#             duration_minutes = run_with_timeout(
#                 estimate_signal_duration,
#                 signal_type=final_signal,
#                 confidence=confidence,
#                 trend="uptrend" if macd_signal == "bullish" else "downtrend" if macd_signal == "bearish" else "sideways",
#                 sentiment="bullish" if sentiment_float > 0.3 else "bearish" if sentiment_float < -0.3 else "neutral",
#                 volatility=volatility,
#                 timeframe=main_tf,
#                 timeout=10,
#                 default=30
#             )
#             start = price_df.index[-1]
#             end = start + datetime.timedelta(minutes=duration_minutes)
#             timing_info = {"start": start, "end": end, "duration": f"~{duration_minutes} minutes"}
#         else:
#             now = datetime.datetime.utcnow()
#             timing_info = {"start": now, "end": now + datetime.timedelta(minutes=30), "duration": "No Duration Calculated"}

#         # Final result
#         result = {
#             "symbol": symbol,
#             "interval": main_tf,
#             "ltf": ltf,
#             "htf": htf,
#             "signal": final_signal,
#             "confidence": confidence,
#             "sentiment": sentiment_score,
#             "indicators": {
#                 "macd": macd_signal,
#                 "rsi": rsi_signal,
#                 "bb": bb_signal,
#                 "volatility": volatility,
#                 "volume": volume,
#             },
#             "risk": risk_result,
#             "strategies": strategies,
#             "decision": final_decision,
#             "timing": timing_info,
#             "scored_headlines": scored_headlines,
#             "timestamp": datetime.datetime.utcnow().isoformat(),
#         }

#         print(f"Signal generated successfully: {result['signal']}")
#         return result

#     except Exception as e:
#         print(f"Error in generate_live_signal_api: {e}")
#         import traceback
#         print(f"Stack trace: {traceback.format_exc()}")
#         return {
#             "symbol": symbol,
#             "interval": "15m",
#             "signal": "HOLD",
#             "confidence": 0,
#             "error": str(e),
#             "timestamp": datetime.datetime.utcnow().isoformat(),
#         }


# # -------------------- Full PDF Pipeline --------------------
# def generate_pdf_report_full(symbol: str):
#     """
#     Full pipeline (signal + backtest + plots + PDF) with timeouts.
#     Runs on 15m main timeframe.
#     """
#     try:
#         # Step 1: Live signal
#         result = generate_live_signal_api(symbol)

#         # Step 2: Backtest (15m base)
#         price_df = run_with_timeout(get_price_data, symbol, "15m", timeout=25, default=pd.DataFrame())
#         try:
#             backtest_df = run_with_timeout(
#                 run_backtest, price_df, symbol, "15m", result.get("scored_headlines", []), {"15m": price_df},
#                 timeout=30, default=pd.DataFrame()
#             )
#             summary = run_with_timeout(
#                 evaluate_backtest_results, backtest_df, timeout=10, default={}
#             ) if not backtest_df.empty else {}
#         except Exception as e:
#             backtest_df = pd.DataFrame()
#             summary = {}
#             print(f"Backtest failed: {e}")

#         # Step 3: Charts
#         run_with_timeout(plot_backtest_results, backtest_df, "reports/plots/backtest_chart.png", timeout=15, default=None)
#         run_with_timeout(plot_price_with_indicators, price_df, backtest_df, symbol, "reports/plots/price_chart.png", timeout=15, default=None)

#         # Step 4: PDF
#         timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
#         pdf_path = f"reports/generated_pdfs/{symbol}_15m_{result['signal']}_{timestamp}_TradingSignals.pdf"

#         run_with_timeout(
#             create_pdf_report,
#             symbol,
#             "15m",
#             signal_info=result,
#             risk_info=result.get("risk", {}),
#             timing_info=result.get("timing", {}),
#             summary=summary,
#             pdf_path=pdf_path,
#             backtest_df=backtest_df,
#             scored_headlines=result.get("scored_headlines", []),
#             timeout=30,
#             default=None
#         )

#         return {"pdf_path": pdf_path, "summary": summary, "signal": result}

#     except Exception as e:
#         print(f"Error in generate_pdf_report_full: {e}")
#         import traceback
#         print(f"Stack trace: {traceback.format_exc()}")
#         return {"error": str(e)}
