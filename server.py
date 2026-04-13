"""
server.py — MIDA Benchling Canvas App webhook server

Routes:
  POST /webhook/canvas  — main Benchling webhook handler
  POST /webhook/lifecycle — Benchling lifecycle ping
  POST /webhook         — fallback
  GET  /health          — health check

Canvas shows two buttons:
  🚀 Open MIDA — opens full Streamlit app with entry_id in URL (full UI + clash resolution)
  ⚡ Quick Audit — runs Gemini silently, writes status back to Benchling result table
"""

import os
import sys
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

# Ensure mida_engine is importable from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

BENCHLING_URL    = os.getenv("BENCHLING_TENANT_URL", "https://excelra.benchling.com")
CLIENT_ID        = os.getenv("BENCHLING_CLIENT_ID")
CLIENT_SECRET    = os.getenv("BENCHLING_CLIENT_SECRET")
APP_ID           = os.getenv("BENCHLING_APP_ID")

# ── Update this to your Streamlit URL once deployed ──────────────────────────
# Local dev:   http://localhost:8501
# Streamlit Cloud: https://your-app-name.streamlit.app
STREAMLIT_URL = os.getenv("STREAMLIT_URL", "http://localhost:8501")


# ══════════════════════════════════════════════════════════════════════════════
# Auth helpers
# ══════════════════════════════════════════════════════════════════════════════

def get_access_token() -> str:
    """Get OAuth token using Client ID + Secret."""
    resp = requests.post(
        f"{BENCHLING_URL}/api/v2/token",
        data={
            "grant_type":    "client_credentials",
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    token = resp.json().get("access_token")
    if not token:
        print(f"  Token error: {resp.text[:200]}")
    return token


def get_headers() -> dict:
    token = get_access_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Canvas block builders
# ══════════════════════════════════════════════════════════════════════════════

def idle_blocks(entry_id: str = None) -> list:
    """
    Initial canvas shown when app is loaded into an entry.
    Two buttons:
      - Open MIDA: launches full Streamlit UI pre-loaded with this entry's files
      - Quick Audit: runs Gemini silently and writes status back automatically
    """
    mida_url = f"{STREAMLIT_URL}/?entry_id={entry_id}" if entry_id else STREAMLIT_URL

    return [
        {
            "type":  "MARKDOWN",
            "id":    "header",
            "value": "## 🧪 MIDA Audit Engine\n*Multi-source Intelligent Deviation Analyser*"
        },
        {
            "type":  "MARKDOWN",
            "id":    "description",
            "value": (
                "**What MIDA does:**\n"
                "- Reads lab results + SOP/MOM documents from this entry\n"
                "- Detects deviations and clashing rules between documents\n"
                "- Assigns **VERIFIED / JUSTIFIED / FAIL** per sample\n"
                "- Writes audit status back to the Results table\n\n"
                "---\n"
                "**Choose how to run:**"
            )
        },
        {
            "type":  "MARKDOWN",
            "id":    "option1_label",
            "value": (
                "**🚀 Open MIDA (Full UI)**\n"
                "Opens the MIDA tool with full clash resolution UI. "
                "You review each conflict and choose the source of truth before results are written back."
            )
        },
        {
            "type":    "BUTTON",
            "id":      "open_mida",
            "text":    "🚀 Open MIDA Full UI",
            "enabled": True
        },
        {
            "type":  "MARKDOWN",
            "id":    "divider",
            "value": "---"
        },
        {
            "type":  "MARKDOWN",
            "id":    "option2_label",
            "value": (
                "**⚡ Quick Audit (Automatic)**\n"
                "Gemini AI automatically resolves all clashes and writes "
                "VERIFIED / JUSTIFIED / FAIL directly to the Results table. "
                "No manual review required."
            )
        },
        {
            "type":    "BUTTON",
            "id":      "run_quick",
            "text":    "⚡ Quick Audit (Auto)",
            "enabled": True
        },
        {
            "type":  "MARKDOWN",
            "id":    "entry_info",
            "value": f"*Entry: `{entry_id or 'unknown'}`*"
        },
    ]


def running_blocks() -> list:
    """Shown while Quick Audit is processing."""
    return [
        {
            "type":  "MARKDOWN",
            "id":    "header",
            "value": "## 🧪 MIDA Audit Engine"
        },
        {
            "type":  "MARKDOWN",
            "id":    "status",
            "value": (
                "⏳ **Quick Audit running...**\n\n"
                "- Fetching files from entry\n"
                "- Reading SOP and rule documents\n"
                "- Running Gemini AI audit\n"
                "- Writing results back to table\n\n"
                "*Please wait — do not close this entry.*"
            )
        },
    ]


def mida_link_blocks(entry_id: str, mida_url: str) -> list:
    """
    Shown after user clicks Open MIDA button.
    Displays the Streamlit URL for the user to open.
    """
    return [
        {
            "type":  "MARKDOWN",
            "id":    "header",
            "value": "## 🧪 MIDA Audit Engine"
        },
        {
            "type":  "MARKDOWN",
            "id":    "link_info",
            "value": (
                "✅ **MIDA is ready to open.**\n\n"
                f"Copy this URL and open it in a new tab:\n\n"
                f"```\n{mida_url}\n```\n\n"
                "The tool will automatically load files from this Benchling entry.\n"
                "After completing the audit, results will be written back here."
            )
        },
        {
            "type":    "BUTTON",
            "id":      "run_quick",
            "text":    "⚡ Or run Quick Audit instead",
            "enabled": True
        },
        {
            "type":    "BUTTON",
            "id":      "reset",
            "text":    "↩ Back",
            "enabled": True
        },
    ]


def result_blocks(results: list, written_count: int, entry_id: str = None) -> list:
    """Shown after Quick Audit completes with results table."""
    if not results:
        rows_md = "*No samples processed.*"
    else:
        header   = "| Sample | Status | Comment |\n|--------|--------|---------|"
        rows     = "\n".join([
            f"| {r.get('sample_id', '—')} | "
            f"{'✅ VERIFIED' if r['status'] == 'VERIFIED' else '⚠️ JUSTIFIED' if r['status'] == 'JUSTIFIED' else '❌ FAIL'}"
            f" | {r.get('comment', '')[:80]} |"
            for r in results
        ])
        rows_md  = f"{header}\n{rows}"

    return [
        {
            "type":  "MARKDOWN",
            "id":    "header",
            "value": "## 🧪 MIDA Audit — Results"
        },
        {
            "type":  "MARKDOWN",
            "id":    "summary",
            "value": (
                f"✅ **Audit complete.** {written_count} row(s) updated in Benchling.\n\n"
                f"{rows_md}"
            )
        },
        {
            "type":  "MARKDOWN",
            "id":    "note",
            "value": (
                "*Check the Results table above to see updated MIDA status.*\n\n"
                "Run again if you have updated the documents or results."
            )
        },
        {
            "type":    "BUTTON",
            "id":      "run_quick",
            "text":    "🔄 Run Again",
            "enabled": True
        },
        {
            "type":    "BUTTON",
            "id":      "open_mida",
            "text":    "🚀 Open Full MIDA UI",
            "enabled": True
        },
    ]


def error_blocks(error_msg: str) -> list:
    """Shown when an error occurs."""
    return [
        {
            "type":  "MARKDOWN",
            "id":    "header",
            "value": "## 🧪 MIDA Audit Engine"
        },
        {
            "type":  "MARKDOWN",
            "id":    "error",
            "value": (
                f"❌ **Error:** {error_msg}\n\n"
                "**Common fixes:**\n"
                "- Make sure the MIDA Result table has rows with Samples and Docs filled in\n"
                "- Make sure SOP/rule documents are attached to the Docs field\n"
                "- Check that the server is running correctly"
            )
        },
        {
            "type":    "BUTTON",
            "id":      "run_quick",
            "text":    "Try Again",
            "enabled": True
        },
        {
            "type":    "BUTTON",
            "id":      "reset",
            "text":    "↩ Back to Start",
            "enabled": True
        },
    ]


# ══════════════════════════════════════════════════════════════════════════════
# Canvas API helpers
# ══════════════════════════════════════════════════════════════════════════════

def update_canvas(canvas_id: str, blocks: list, enabled: bool = True) -> int:
    """Patch canvas blocks. Returns status code."""
    headers = get_headers()
    resp = requests.patch(
        f"{BENCHLING_URL}/api/v2/app-canvases/{canvas_id}",
        headers=headers,
        json={"enabled": enabled, "blocks": blocks},
        timeout=15,
    )
    print(f"  Canvas update: {resp.status_code}")
    if resp.status_code not in (200, 201):
        print(f"  Canvas error: {resp.text[:300]}")
    return resp.status_code


def get_canvas_resource_id(canvas_id: str) -> str | None:
    """Fetch the resourceId (entry ID) from a canvas."""
    headers = get_headers()
    resp = requests.get(
        f"{BENCHLING_URL}/api/v2/app-canvases/{canvas_id}",
        headers=headers,
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json().get("resourceId")
    print(f"  Could not get canvas resource: {resp.status_code}")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Core event handler
# ══════════════════════════════════════════════════════════════════════════════

def handle_event(event: dict):
    """Process all incoming Benchling webhook events."""
    message    = event.get("message", {})
    event_type = message.get("type", "")

    print(f"\n{'='*50}")
    print(f"Event: {event_type}")

    # ── Canvas created — user inserted app into entry ──────────────────────
    if event_type == "v2.canvas.created":
        canvas_id   = message.get("canvasId")
        resource_id = message.get("resourceId")
        feature_id  = message.get("featureId", "mida_audit_canvas")

        print(f"  Canvas: {canvas_id} | Resource: {resource_id}")

        if canvas_id:
            # Canvas already exists — patch blocks into it
            update_canvas(canvas_id, idle_blocks(resource_id), enabled=True)
        elif resource_id:
            # Create a new canvas on this resource
            headers = get_headers()
            resp = requests.post(
                f"{BENCHLING_URL}/api/v2/app-canvases",
                headers=headers,
                json={
                    "appId":      APP_ID,
                    "featureId":  feature_id,
                    "resourceId": resource_id,
                    "enabled":    True,
                    "blocks":     idle_blocks(resource_id),
                },
                timeout=15,
            )
            print(f"  Canvas created: {resp.status_code}")

    # ── User clicked a button ──────────────────────────────────────────────
    elif event_type == "v2.canvas.userInteracted":
        canvas_id = message.get("canvasId")
        button_id = message.get("buttonId")
        print(f"  Button: {button_id} | Canvas: {canvas_id}")

        # Get the entry ID this canvas is attached to
        entry_id = get_canvas_resource_id(canvas_id)
        print(f"  Entry ID: {entry_id}")

        # ── Open MIDA full UI ──────────────────────────────────────────
        if button_id == "open_mida":
            mida_url = f"{STREAMLIT_URL}/?entry_id={entry_id}" if entry_id else STREAMLIT_URL
            print(f"  MIDA URL: {mida_url}")
            update_canvas(canvas_id, mida_link_blocks(entry_id, mida_url), enabled=True)

        # ── Quick Audit — run Gemini silently ──────────────────────────
        elif button_id == "run_quick":
            update_canvas(canvas_id, running_blocks(), enabled=False)
            try:
                from mida_engine import run_audit_on_entry, write_results_to_benchling

                print(f"  Running audit on entry: {entry_id}")
                results = run_audit_on_entry(entry_id)
                print(f"  Audit complete: {len(results)} results")

                written = write_results_to_benchling(entry_id, results)
                print(f"  Written back: {written} rows")

                update_canvas(
                    canvas_id,
                    result_blocks(results, written, entry_id),
                    enabled=True
                )

            except Exception as e:
                print(f"  Audit error: {e}")
                import traceback
                traceback.print_exc()
                update_canvas(canvas_id, error_blocks(str(e)), enabled=True)

        # ── Reset to idle ──────────────────────────────────────────────
        elif button_id == "reset":
            update_canvas(canvas_id, idle_blocks(entry_id), enabled=True)


# ══════════════════════════════════════════════════════════════════════════════
# Flask routes
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/webhook/lifecycle", methods=["POST"])
def webhook_lifecycle():
    print("Lifecycle ping")
    return jsonify({"status": "ok"}), 200


@app.route("/webhook/canvas", methods=["POST"])
def webhook_canvas():
    handle_event(request.json or {})
    return jsonify({"status": "ok"}), 200


@app.route("/webhook", methods=["POST"])
def webhook():
    handle_event(request.json or {})
    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status":        "running",
        "streamlit_url": STREAMLIT_URL,
        "app_id":        APP_ID,
    }), 200


if __name__ == "__main__":
    print(f"MIDA Server starting...")
    print(f"Streamlit URL: {STREAMLIT_URL}")
    print(f"App ID: {APP_ID}")
    app.run(port=5000, debug=True)