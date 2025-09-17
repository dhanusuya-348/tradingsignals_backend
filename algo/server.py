# server.py
from flask import Flask, send_file
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Sentiment Logger is Running"

@app.route('/sentiment/csv')
def serve_sentiment_file():
    file_path = "data/sentiment_history.csv"
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=False)
    return "File not found", 404

@app.route('/log-sentiment')
def log_and_return():
    from threading import Thread
    def background_task():
        from sentiment_logger import log_sentiment
        log_sentiment()

    Thread(target=background_task).start()
    return "Sentiment logging started.", 202


def start():
    print("Starting Flask server...")
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    print("Starting Flask server...")
    start()
