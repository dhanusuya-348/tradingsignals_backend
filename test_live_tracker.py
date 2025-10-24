from algo.backtesting.live_tracker import monitor_live_signal

# Mock signal_info that matches your runner output
mock_signal = {
    "id": 1,
    "symbol": "ADAUSDT",
    "interval": "1h",
    "signal": "BUY",
    "confidence": 75,
    "price": 0.4523,  # simulated current price
    "risk": {
        "suggested_stop_loss": 0.445,
        "suggested_take_profit": 0.46,
        "estimated_duration_minutes": 10
    },
    "decision": "APPROVED"
}

monitor_live_signal("ADA", mock_signal)
