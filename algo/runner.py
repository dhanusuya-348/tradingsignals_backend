# algo\runner.py
import datetime
import os
import sys
import pandas as pd

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


def generate_live_signal_api(symbol: str, interval: str):
    """
    Full live signal generator.
    Mirrors main.py logic but without interactive input.
    Returns JSON-style dict with all signal + risk info.
    """
    try:
        print(f"Generating signal for {symbol} ({interval})")
        
        # Fetch price data
        price_df = get_price_data(symbol, interval)
        print(f"Fetched {len(price_df)} price data points")

        # Sentiment
        sentiment_score, scored_headlines = get_sentiment_score(symbol, print_news=False)
        sentiment_float = 1.0 if sentiment_score == "bullish" else -1.0 if sentiment_score == "bearish" else 0.0
        print(f"Sentiment: {sentiment_score}")

        # Indicators
        macd_signal = calculate_macd(price_df)
        rsi_val, rsi_signal = calculate_rsi(price_df)
        bb_signal = calculate_bollinger_bands(price_df)
        volatility = calculate_volatility(price_df)
        volume = calculate_volume_metrics(price_df)

        # Core engine
        final_signal, confidence, strategies = core_generate_live_signal({interval: price_df}, sentiment_score, symbol)
        print(f"Core signal: {final_signal} (confidence: {confidence}%)")

        # Risk management
        indicators = {
            "rsi": rsi_val,
            "macd": macd_signal,
            "bb": bb_signal,
            "volatility": volatility,
            "sentiment": sentiment_float,
            "trend_strength": 0.6,
        }
        risk_result = calculate_risk_management(price_df, final_signal, volatility, indicators, confidence)

        # Final decision (approved/rejected like main.py)
        final_decision = "REJECTED"
        if final_signal in ["BUY", "SELL"] and risk_result['risk_level'] not in ['too_weak', 'invalid']:
            final_decision = "APPROVED"

        print(f"Final decision: {final_decision}")

        # Signal duration (only if approved)
        timing_info = {}
        if final_decision == "APPROVED":
            duration_minutes = estimate_signal_duration(
                signal_type=final_signal,
                confidence=confidence,
                trend="uptrend" if macd_signal == "bullish" else "downtrend" if macd_signal == "bearish" else "sideways",
                sentiment="bullish" if sentiment_float > 0.3 else "bearish" if sentiment_float < -0.3 else "neutral",
                volatility=volatility,
                timeframe=interval
            )
            start = price_df.index[-1]
            end = start + datetime.timedelta(minutes=duration_minutes)
            timing_info = {
                "start": start,
                "end": end,
                "duration": f"~{duration_minutes} minutes"
            }
        else:
            now = datetime.datetime.utcnow()
            timing_info = {
                "start": now,
                "end": now + datetime.timedelta(minutes=30),
                "duration": "No Duration Calculated"
            }

        result = {
            "symbol": symbol,
            "interval": interval,
            "signal": final_signal,
            "confidence": confidence,
            "sentiment": sentiment_score,
            "indicators": {
                "macd": macd_signal,
                "rsi": rsi_signal,
                "bb": bb_signal,
                "volatility": volatility,
                "volume": volume,
            },
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
        
        # Return a basic response to prevent crashes
        return {
            "symbol": symbol,
            "interval": interval,
            "signal": "HOLD",
            "confidence": 0,
            "error": str(e),
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }


def generate_pdf_report_full(symbol: str, interval: str):
    """
    Full pipeline (signal + backtest + plots + PDF).
    Returns dict with PDF path, summary, and signal data.
    Mirrors main.py end-to-end.
    """
    try:
        # Step 1: Live signal
        result = generate_live_signal_api(symbol, interval)

        # Step 2: Backtest
        price_df = get_price_data(symbol, interval)
        try:
            backtest_df = run_backtest(price_df, symbol, interval, result["scored_headlines"], {interval: price_df})
            summary = evaluate_backtest_results(backtest_df) if not backtest_df.empty else {}
        except Exception as e:
            backtest_df = pd.DataFrame()
            summary = {}
            print(f"Backtest failed: {e}")

        # Step 3: Charts
        plot_backtest_results(backtest_df, "reports/plots/backtest_chart.png")
        plot_price_with_indicators(price_df, backtest_df, symbol, "reports/plots/price_chart.png")

        # Step 4: PDF
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = f"reports/generated_pdfs/{symbol}_{interval}_{result['signal']}_{timestamp}_TradingSignals.pdf"

        create_pdf_report(
            symbol,
            interval,
            signal_info=result,
            risk_info=result.get("risk", {}),
            timing_info=result.get("timing", {}),
            summary=summary,
            pdf_path=pdf_path,
            backtest_df=backtest_df,
            scored_headlines=result.get("scored_headlines", [])
        )

        return {"pdf_path": pdf_path, "summary": summary, "signal": result}
        
    except Exception as e:
        print(f"Error in generate_pdf_report_full: {e}")
        import traceback
        print(f"Stack trace: {traceback.format_exc()}")
        return {"error": str(e)}