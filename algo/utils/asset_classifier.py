def classify_asset(symbol):
    """Classify trading pairs by market characteristics"""
    
    MAJOR_PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    
    LARGE_CAP = [
        "ADAUSDT", "SOLUSDT", "XRPUSDT", "DOTUSDT", 
        "LINKUSDT", "LTCUSDT", "BCHUSDT", "AVAXUSDT"
    ]
    
    MID_CAP = [
        "MATICUSDT", "UNIUSDT", "ATOMUSDT", "VETUSDT",
        "FILUSDT", "TRXUSDT", "EOSUSDT", "XLMUSDT"
    ]
    
    if symbol in MAJOR_PAIRS:
        return "major"
    elif symbol in LARGE_CAP:
        return "large_cap"
    elif symbol in MID_CAP:
        return "mid_cap"
    else:
        return "small_cap"


def get_asset_params(symbol):
    """Get asset-specific parameters"""
    asset_type = classify_asset(symbol)
    
    params = {
        "major": {
            "min_volume_threshold": 300,
            "confidence_multiplier": 1.0,
            "max_daily_signals": 3,
            "min_signal_gap_hours": 4
        },
        "large_cap": {
            "min_volume_threshold": 50,
            "confidence_multiplier": 0.95,
            "max_daily_signals": 4,
            "min_signal_gap_hours": 2
        },
        "mid_cap": {
            "min_volume_threshold": 30,
            "confidence_multiplier": 0.90,
            "max_daily_signals": 5,
            "min_signal_gap_hours": 1
        },
        "small_cap": {
            "min_volume_threshold": 20,
            "confidence_multiplier": 0.85,
            "max_daily_signals": 6,
            "min_signal_gap_hours": 1
        }
    }
    
    return params.get(asset_type, params["small_cap"])