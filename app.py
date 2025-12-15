from flask import Flask, request, jsonify
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime

# ==================================
# KONFIGURATION
# ==================================

SPREADSHEET_ID = "1d_ZgrOqK1NT0U7qRm5aKsw5hSjO1fQqHgbK-DK9Y_fo"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]

# ==================================
# GOOGLE AUTH (NUR SECRET FILE!)
# ==================================

credentials = Credentials.from_service_account_file(
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
    scopes=SCOPES
)

gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# ==================================
# FLASK APP
# ==================================

app = Flask(__name__)

@app.route("/")
def index():
    return "QR Anwesenheitssystem läuft ✅"

@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.get_json(force=True)

    name = data.get("name")
    ort = data.get("ort")

    if not name or not ort:
        return jsonify({"error": "Name und Ort erforderlich"}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sheet.append_row([timestamp, name, ort])

    return jsonify({"status": "ok"})

# ==================================
# START (lokal)
# ==================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
