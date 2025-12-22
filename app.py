from flask import Flask, request, jsonify, render_template
import gspread
from google.oauth2.service_account import Credentials
import os, json
from datetime import datetime, date

app = Flask(__name__)

# ---------------------------
# CONFIG
# ---------------------------
SPREADSHEET_ID = "1d_ZgrOqK1NT0U7qRm5aKsw5hSjO1fQqHgbK-DK9Y_fo"
QR_TOKEN = "QR2025-ZUTRITT"

# ---------------------------
# GOOGLE CREDENTIALS
# ---------------------------
if "GOOGLE_CREDENTIALS_JSON" not in os.environ:
    raise RuntimeError(
        "GOOGLE_CREDENTIALS_JSON fehlt. "
        "In Render → Environment → Secrets setzen."
    )

try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
except json.JSONDecodeError:
    raise RuntimeError("GOOGLE_CREDENTIALS_JSON ist kein gültiges JSON")

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)

# ❗ HIER passiert dein Fehler wenn ID / Freigabe falsch
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# ---------------------------
# ROUTES
# ---------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.get_json()

    if not data:
        return jsonify(error="Keine Daten"), 400

    name = data.get("name")
    device_id = data.get("device_id")
    token = data.get("token")
    city = data.get("city", "Unbekannt")

    if not name or not device_id or token != QR_TOKEN:
        return jsonify(error="Unvollständige Daten"), 400

    today = date.today().isoformat()

    rows = sheet.get_all_records()
    for r in rows:
        if (
            r.get("device_id") == device_id
            and r.get("Datum") == today
        ):
            return jsonify(
                message="⚠️ Heute bereits eingecheckt"
            ), 200

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        today,
        name,
        device_id,
        city
    ])

    return jsonify(
        message="✅ Check-in erfolgreich"
    ), 200

# ---------------------------
# START
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
