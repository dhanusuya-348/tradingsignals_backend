# application.py
from flask import Flask, request, jsonify
from models import Base, get_engine_from_env, get_session, Watchlist
from datetime import datetime

app = Flask(__name__)

# Create tables at startup (for dev; in prod you’d use migrations)
engine = get_engine_from_env()
Base.metadata.create_all(engine)

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/watchlist", methods=["POST"])
def add_watchlist():
    """
    Expected JSON:
    {
      "user_sub": "<cognito-sub>",
      "symbol": "BTCUSDT",
      "email": "user@example.com",
      "phone": "+911234567890"   # optional
    }
    """
    data = request.json or {}
    user_sub = data.get("user_sub")   # Cognito user id
    symbol = data.get("symbol")
    email = data.get("email")
    phone = data.get("phone")

    if not user_sub or not symbol or not email:
        return {"error": "missing fields (user_sub, symbol, email required)"}, 400

    session = get_session()
    w = Watchlist(
        user_sub=user_sub,
        email=email,
        symbol=symbol,
        created_at=datetime.utcnow()
    )
    # optional phone column may not exist initially; ensure model has phone if you want to persist it.
    if hasattr(w, "phone") and phone:
        setattr(w, "phone", phone)

    session.add(w)
    session.commit()
    session.close()
    return jsonify({"ok": True})

@app.route("/watchlist/<user_sub>", methods=["GET"])
def get_watchlist(user_sub):
    session = get_session()
    rows = session.query(Watchlist).filter_by(user_sub=user_sub).all()
    out = [{"id": r.id, "symbol": r.symbol, "email": getattr(r, "email", None), "phone": getattr(r, "phone", None)} for r in rows]
    session.close()
    return jsonify(out)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
