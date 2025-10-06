#pdf_server.py
from flask import Flask, send_file, jsonify
from io import BytesIO
from algo.runner import generate_pdf_report_full
import os

app = Flask(__name__)

@app.route("/download-pdf/<symbol>")
def download_pdf(symbol):
    try:
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
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)  # run on EC2
