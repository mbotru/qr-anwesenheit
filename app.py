from flask import Flask, request, jsonify, render_template
import gspread
from google.oauth2.service_account import Credentials
import os, json, datetime

app = Flask(__name__)

# ===============================
# KONFIG
# ===============================
VALID_TOKEN = "QR2025-ZUTRITT"
SPREADSHEET_ID = "1d_ZgrOqK1NT0U7qRm5aKsw5hSjO1fQqHgbK-DK9Y_fo"

# ===============================
# GOOGLE SHEETS
# ===============================
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# Header sicherstellen
if sheet.row_count < 1 or sheet.row_values(1) != ["Datum", "Name", "Ort", "Device ID"]:
    sheet.clear()
    sheet.append_row(["Datum", "Name", "Ort", "Device ID"])

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

