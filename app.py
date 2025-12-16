from flask import Flask, request, jsonify, render_template
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import datetime

# ===============================
# FLASK APP
# ===============================
app = Flask(__name__)

# ===============================
# KONFIGURATION
# ===============================
VALID_TOKEN = "QR2025-ZUTRITT"
SPREADSHEET_ID = "HIER_DEINE_SHEET_ID"  # <-- HIER ANPASSEN

# ===============================
# GOOGLE CREDENTIALS LADEN
# ===============================
if "GOOGLE_CREDENTIALS_JSON" not in os.environ:
    raise RuntimeError(
        "GOOGLE_CREDENTIALS_JSON fehlt. "
        "Bitte in Render → Environment → Secrets setzen."
    )

try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
except Exception as e:
    raise RuntimeError(
        "GOOGLE_CREDENTIALS_JSON ist kein gültiges JSON"
    ) from e

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)

# ===============================
# GOOGLE SHEET VERBINDEN
# ===============================
try:
    sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
except Exception as e:
    raise RuntimeError(
        "Google Sheet nicht erreichbar. "
        "ID korrekt? Sheet mit Service Account geteilt?"
    ) from e

# ===============================
# HEADER SICHERSTELLEN
# ===============================
EXPECTED_HEADER = ["Datum", "Name", "Ort", "Device ID"]

existing_header = sheet.row_values(1)
if existing_header != EXPECTED_HEADER:
    sheet.clear()
    sheet.append_row(EXPECTED_HEADER)

# ===============================
# ROUTES
# ===============================
@app.route("/")
def index():
    token = request.args.get("token")
    if token != VALID_TOKEN:
        return "❌ Ungültiger QR-Code", 403
    return render_template("index.html", token=token)

@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.json or {}

    token = data.get("token")
    name = data.get("name")
    ort = data.get("ort")
    device_id = data.get("device_id")

    if token != VALID_TOKEN or not name or not ort or not device_id:
        return jsonify({"error": "Unvollständige Daten"}), 400

    today = datetime.date.today().isoformat()

    rows = sheet.get_all_records()
    for r in rows:
        if r["Datum"] == today and r["Device ID"] == device_id:
            return jsonify({"error": "Heute bereits eingecheckt"}), 409

    sheet.append_row([today, name, ort, device_id])
    return jsonify({"success": True})

@app.route("/favicon.ico")
def favicon():
    return "", 204
