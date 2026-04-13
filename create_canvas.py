"""
create_canvas.py
Run this ONCE to attach the MIDA canvas to a specific Benchling notebook entry.
"""
import requests
import os
import base64
from dotenv import load_dotenv

load_dotenv()

BENCHLING_URL   = os.getenv("BENCHLING_TENANT_URL")
CLIENT_ID       = os.getenv("BENCHLING_CLIENT_ID")
CLIENT_SECRET   = os.getenv("BENCHLING_CLIENT_SECRET")
APP_ID          = os.getenv("BENCHLING_APP_ID")
BENCHLING_KEY   = os.getenv("BENCHLING_API_KEY")

print(f"App ID: {APP_ID}")
print(f"Client ID: {CLIENT_ID}")

# Step 1 — Get OAuth access token using Client ID + Secret
token_resp = requests.post(
    f"{BENCHLING_URL}/api/v2/token",
    data={
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)

print(f"Token response: {token_resp.status_code}")

if token_resp.status_code == 200:
    access_token = token_resp.json().get("access_token")
    print(f"Got access token: {access_token[:20]}...")
    HEADERS = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json"
    }
else:
    print(f"Token error: {token_resp.text}")
    print("Falling back to API key auth...")
    # Fallback to personal API key
    creds = base64.b64encode(f"{BENCHLING_KEY}:".encode()).decode()
    HEADERS = {
        "Authorization": f"Basic {creds}",
        "Content-Type":  "application/json"
    }

ENTRY_ID = "etr_mmBKEKwO7xojhdT3vgI8"

canvas_payload = {
    "appId":      APP_ID,
    "featureId":  "mida_audit_canvas",
    "resourceId": ENTRY_ID,
    "enabled":    True,
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
            "type":    "BUTTON",
            "id":      "run_btn",
            "text":    "Run Audit",
            "enabled": True
        }
    ]
}

resp = requests.post(
    f"{BENCHLING_URL}/api/v2/app-canvases",
    headers=HEADERS,
    json=canvas_payload
)

print(f"Canvas status: {resp.status_code}")
print(resp.json())