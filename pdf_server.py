#pdf_server.py
from flask import Flask, send_file, jsonify, request
from io import BytesIO
from flask_cors import CORS
from algo.runner import generate_pdf_report_full, generate_pdf_for_signal
import os

app = Flask(__name__)

# Enable CORS for all routes
CORS(app, resources={
    r"/*": {
        "origins": "*",  # In production, replace with your actual domain
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept"]
    }
})

# ✅ NEW ENDPOINT: Generate PDF for specific signal
@app.route("/generate-pdf", methods=["POST"])
def generate_pdf():
    """Generate PDF for a specific signal by signal_id"""
    try:
        signal_id = request.args.get("signal_id")
        
        if not signal_id:
            return jsonify({"error": "signal_id parameter is required"}), 400
        
        print(f"Generating PDF for signal_id: {signal_id}")
        
        # Generate PDF for this specific signal
        result = generate_pdf_for_signal(signal_id)
        
        pdf_path = result.get("pdf_path")
        if not pdf_path or not os.path.exists(pdf_path):
            error_msg = result.get("error", "PDF generation failed")
            return jsonify({"error": error_msg}), 500

        return send_file(
            pdf_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=os.path.basename(pdf_path)
        )
        
    except Exception as e:
        print(f"Error in generate_pdf endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ✅ KEEP OLD ENDPOINT: For backward compatibility (symbol-based)
@app.route("/download-pdf/<symbol>")
def download_pdf(symbol):
    """Legacy endpoint: Generate PDF for all signals of a symbol"""
    try:
        print(f"Legacy endpoint called for symbol: {symbol}")
        
        # This will run the full PDF generation (signal + backtest + plots + PDF)
        result = generate_pdf_report_full(symbol)
        pdf_path = result.get("pdf_path")
        
        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify({"error": "PDF not generated"}), 500

        return send_file(
            pdf_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=os.path.basename(pdf_path)
        )
        
    except Exception as e:
        print(f"Error in download_pdf endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8001,
        ssl_context=("/home/ec2-user/certificate.crt", "/home/ec2-user/private.key")
    )

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

