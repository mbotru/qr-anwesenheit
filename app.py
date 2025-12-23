from flask import Flask, request, jsonify, render_template
import gspread
from google.oauth2.service_account import Credentials
import os, json
from datetime import datetime, date
import pytz  # Zeitzonenunterstützung

app = Flask(__name__)

# ---------------------------
# CONFIG
# ---------------------------
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1d_ZgrOqK1NT0U7qRm5aKsw5hSjO1fQqHgbK-DK9Y_fo")
QR_TOKEN = os.environ.get("QR_TOKEN", "QR2025-ZUTRITT")

# Zeitzone MEZ / GMT+1
tz = pytz.timezone("Europe/Berlin")

# ---------------------------
# GOOGLE CREDENTIALS
# ---------------------------
if "GOOGLE_CREDENTIALS_JSON" not in os.environ:
    raise RuntimeError("GOOGLE_CREDENTIALS_JSON fehlt")

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
scopes = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
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

    vorname = data.get("v
