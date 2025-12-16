import os
import json
import hashlib
from datetime import datetime, date

from flask import Flask, request, jsonify, render_template
import gspread
from google.oauth2.service_account import Credentials

# -----------------------
# Flask App
# -----------------------
app = Flask(__name__)

# -----------------------
# Konfiguration
# -----------------------
VALID_TOKEN = "QR2025-ZUTRITT"
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")

# -----------------------
# Google Credentials laden
# -----------------------
if "GOOGLE_CREDENTIALS_JSON" not in os.environ:
    raise RuntimeError(
        "GOOGLE_CREDENTIALS_JSON fehlt. Bitte in Render → Environment → Secrets setzen."
    )

try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
except json.JSONDecodeError:
    raise RuntimeError("GOOGLE_CREDENTIALS_JSON ist kein gültiges JSON")

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)

sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# -----------------------
# Hilfsfunktionen
# -----------------------
def hash_device(device_id: str) -> str:
    return hashlib.sha256(device_id.encode()).hexdigest()


def already_checked_in_today(device_hash: str) -> bool:
    today = date.today().isoformat()
    rows = sheet.get_all_records()

    for row in rows:
        if (
            row.get("device_hash") == device_hash
            and str(row.get("date")) == today
        ):
            return True
    return False


# -----------------------
# Routes
# -----------------------
@app.route("/", methods=["GET"])
def index():
    token = request.args.get("token")
    if token != VALID_TOKEN:
        return "❌ Ungültiger oder fehlender QR-Code", 403

    return render_template("index.html", token=token)


@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Keine Daten empfangen"}), 400

    name = data.get("name")
    device_id = data.get("device_id")
    token = data.get("token")
    city = data.get("city", "Unbekannt")

    if not name or not device_id or not token:
        return jsonify({"error": "Unvollständige Daten"}), 400

    if token != VALID_TOKEN:
        return jsonify({"error": "Ungültiger QR-Code"}), 403

    device_hash = hash_device(device_id)

    if already_checked_in_today(device_hash):
        return jsonify({
            "status": "blocked",
            "message": "⚠️ Heute bereits eingecheckt"
        }), 409

    now = datetime.now()

    sheet.append_row([
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        name,
        device_hash,
        city
    ])

    return jsonify({
        "status": "ok",
        "message": f"✅ Check-in erfolgreich ({city})"
    })


# -----------------------
# Render Port Binding
# -----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
