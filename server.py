from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

BENCHLING_URL = os.getenv("BENCHLING_TENANT_URL", "https://excelra.benchling.com")
BENCHLING_KEY = os.getenv("BENCHLING_API_KEY")
HEADERS = {
    "Authorization": f"Basic {BENCHLING_KEY}",
    "Content-Type": "application/json"
}


@app.route("/webhook", methods=["POST"])
def webhook():
    event = request.json
    print(f"Received event: {event}")
    return jsonify({"status": "ok"}), 200


@app.route("/webhook/lifecycle", methods=["POST"])
def webhook_lifecycle():
    print("Lifecycle ping received")
    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running"}), 200


if __name__ == "__main__":
    app.run(port=5000, debug=True)