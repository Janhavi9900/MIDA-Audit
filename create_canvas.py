"""
create_canvas.py
Run this ONCE to attach the MIDA canvas to a specific Benchling notebook entry.
Usage: python create_canvas.py
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

BENCHLING_URL = os.getenv("BENCHLING_TENANT_URL")
BENCHLING_KEY = os.getenv("BENCHLING_API_KEY")
APP_ID        = os.getenv("BENCHLING_APP_ID")

HEADERS = {
    "Authorization": f"Basic {BENCHLING_KEY}",
    "Content-Type": "application/json"
}

# The entry ID from your Benchling link
# https://excelra.benchling.com/s/etr-mmBKEKwO7xojhdT3vgI8
ENTRY_ID = "etr_mmBKEKwO7xojhdT3vgI8"

canvas_payload = {
    "appId":     APP_ID,
    "featureId": "mida_audit_canvas",
    "resourceId": ENTRY_ID,
    "enabled":   True,
    "blocks": [
        {
            "type":  "MARKDOWN",
            "id":    "title",
            "value": "## MIDA Audit Engine\nAI-powered lab deviation audit."
        },
        {
            "type":  "MARKDOWN",
            "id":    "info",
            "value": "Click **Run Audit** to analyse all attachments in this entry."
        },
        {
            "type":       "BUTTON",
            "id":         "run_btn",
            "text":       "Run Audit",
            "buttonType": "PRIMARY",
            "enabled":    True
        }
    ]
}

resp = requests.post(
    f"{BENCHLING_URL}/api/v2/app-canvases",
    headers=HEADERS,
    json=canvas_payload
)

print(f"Status: {resp.status_code}")
print(resp.json())