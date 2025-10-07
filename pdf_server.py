# pdf_server.py
import os
from pathlib import Path

# -----------------------------
# ✅ ENV LOADER
# -----------------------------
def load_env_file() -> bool:
    """Load environment variables from .env file"""
    env_file = Path(__file__).parent / '.env'
    if not env_file.exists():
        print(f"[WARN] .env file not found at {env_file}")
        return False
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    if key not in os.environ:
                        os.environ[key] = value
        print(f"[INFO] Loaded environment variables from {env_file}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to load .env file: {e}")
        return False

load_env_file()


import traceback
from typing import Dict
from flask import Flask, jsonify, request
from flask_cors import CORS
from algo.runner import generate_pdf_report_full, generate_pdf_for_signal


# -----------------------------
# ✅ MATPLOTLIB CONFIG
# -----------------------------
import matplotlib
matplotlib.use('Agg')  # Avoid GUI issues

# -----------------------------
# ✅ FLASK APP
# -----------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# -----------------------------
# ✅ ENDPOINT: Generate PDF for specific signal
# -----------------------------
@app.route("/generate-pdf", methods=["POST"])
def generate_pdf() -> Dict:
    try:
        signal_id = request.args.get("signal_id")
        if not signal_id:
            return jsonify({"error": "signal_id parameter is required"}), 400

        print(f"[INFO] Starting PDF generation for signal_id: {signal_id}")
        result = generate_pdf_for_signal(signal_id)

        if "error" in result:
            print(f"[ERROR] PDF generation failed: {result['error']}")
            return jsonify({"error": result["error"]}), 500

        s3_url = result.get("s3_url")
        if not s3_url:
            print(f"[WARN] PDF generated but failed to upload to S3")
            return jsonify({"error": "PDF generated but S3 upload failed"}), 500

        print(f"[SUCCESS] PDF successfully generated and uploaded to S3: {s3_url}")
        return jsonify({
            "signal_id": signal_id,
            "s3_url": s3_url,
            "signal_info": result.get("signal")
        })

    except Exception as e:
        print(f"[ERROR] Exception in generate_pdf endpoint: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# -----------------------------
# ✅ LEGACY ENDPOINT: Generate PDF for a symbol (live signal)
# -----------------------------
@app.route("/download-pdf/<symbol>")
def download_pdf(symbol: str) -> Dict:
    try:
        print(f"[INFO] Legacy endpoint called for symbol: {symbol}")
        result = generate_pdf_report_full(symbol)

        if "error" in result:
            print(f"[ERROR] PDF generation failed for symbol {symbol}: {result['error']}")
            return jsonify({"error": result["error"]}), 500

        s3_url = result.get("s3_url")
        if not s3_url:
            print(f"[WARN] PDF generated but failed to upload to S3")
            return jsonify({"error": "PDF generated but S3 upload failed"}), 500

        print(f"[SUCCESS] PDF successfully generated and uploaded to S3: {s3_url}")
        return jsonify({
            "symbol": symbol,
            "s3_url": s3_url,
            "signal_info": result.get("signal")
        })

    except Exception as e:
        print(f"[ERROR] Exception in download_pdf endpoint: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# -----------------------------
# ✅ MAIN
# -----------------------------
if __name__ == "__main__":
    print("[INFO] Starting PDF server...")

    # ---------- TEMP TEST: PDF generation ----------
    test_signal_id = "701"  # Replace with a valid signal ID
    try:
        print(f"[INFO] Testing PDF generation for signal_id: {test_signal_id}")
        result = generate_pdf_for_signal(test_signal_id)
        if "s3_url" in result and result["s3_url"]:
            print(f"[SUCCESS] PDF successfully uploaded to S3: {result['s3_url']}")
        else:
            print(f"[FAIL] PDF generation/upload failed: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"[ERROR] Exception during test PDF generation: {e}")
        traceback.print_exc()
    # ---------- END TEMP TEST ----------

    app.run(host="0.0.0.0", port=8001)


# #pdf_server.py
# from flask import Flask, send_file, jsonify
# from io import BytesIO
# from flask_cors import CORS
# from algo.runner import generate_pdf_report_full
# import os

# app = Flask(__name__)

# # Enable CORS for all routes
# CORS(app, resources={
#     r"/*": {
#         "origins": "*",  # In production, replace with your actual domain
#         "methods": ["GET", "POST", "OPTIONS"],
#         "allow_headers": ["Content-Type", "Accept"]
#     }
# })

# @app.route("/download-pdf/<symbol>")
# def download_pdf(symbol):
#     try:
#         # This will run the full PDF generation (signal + backtest + plots + PDF)
#         result = generate_pdf_report_full(symbol)
#         pdf_path = result.get("pdf_path")
#         if not pdf_path or not os.path.exists(pdf_path):
#             return jsonify({"error": "PDF not generated"}), 500

#         return send_file(
#             pdf_path,
#             mimetype="application/pdf",
#             as_attachment=True,
#             download_name=os.path.basename(pdf_path)
#         )
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# if __name__ == "__main__":
#     app.run(
#         host="0.0.0.0",
#         port=8001,
#         ssl_context=("/home/ec2-user/certificate.crt", "/home/ec2-user/private.key")
#     )

