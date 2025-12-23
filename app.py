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
QR_TOKEN = os.environ.get("QR_TOKEN", "QR2025-ZUTRITT")

# ---------------------------
# GOOGLE CREDENTIALS
# ---------------------------
if "GOOGLE_CREDENTIALS_JSON" not in os.environ:
    raise RuntimeError("GOOGLE_CREDENTIALS_JSON fehlt")

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
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

    vorname = data.get("vorname")
    nachname = data.get("nachname")
    nachholen = data.get("nachholen")
    token = data.get("token")

    if not vorname or not nachname or not nachholen or token != QR_TOKEN:
        return jsonify(error="Unvollständige oder ungültige Daten"), 400

    today = date.today().isoformat()
    rows = sheet.get_all_records()

    for r in rows:
        if (
            r.get("Vorname") == vorname
            and r.get("Nachname") == nachname
            and r.get("Datum") == today
        ):
            return jsonify(message="⚠️ Heute bereits eingecheckt"), 200

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        today,
        vorname,
        nachname,
        nachholen
    ])

    return jsonify(message="✅ Check-in erfolgreich"), 200

# ---------------------------
# START
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
