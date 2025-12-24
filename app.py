from flask import (
    Flask, request, jsonify, render_template,
    redirect, url_for, session, send_file
)
import gspread
from google.oauth2.service_account import Credentials
import os, json, csv
from datetime import datetime, date
from zoneinfo import ZoneInfo
from io import BytesIO, TextIOWrapper

# ---------------------------
# APP INIT
# ---------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True
)

# ---------------------------
# CONFIG
# ---------------------------
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
QR_TOKEN = os.environ.get("QR_TOKEN", "QR2025-ZUTRITT")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
tz = ZoneInfo("Europe/Berlin")

# ---------------------------
# GOOGLE SHEETS
# ---------------------------
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

HEADERS = ["Zeitstempel", "Datum", "Vorname", "Nachname", "Nachholen"]

# ---------------------------
# ROUTES
# ---------------------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------------------------
# CHECK-IN
# ---------------------------
@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.get_json()
    vorname = data.get("vorname")
    nachname = data.get("nachname")
    nachholen = data.get("nachholen")
    token = data.get("token")

    if not vorname or not nachname or not nachholen or token != QR_TOKEN:
        return jsonify(error="Ungültige Daten"), 400

    now = datetime.now(tz)
    today = now.date().isoformat()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    rows = sheet.get_all_records()
    for r in rows:
        if r.get("Vorname") == vorname and r.get("Nachname") == nachname and r.get("Datum") == today:
            return jsonify(message="⚠️ Heute bereits eingecheckt"), 200

    sheet.append_row([timestamp, today, vorname, nachname, nachholen])
    return jsonify(message="✅ Check-in erfolgreich"), 200

# ---------------------------
# ADMIN LOGIN
# ---------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        return render_template("admin_login.html", error="Falsches Passwort")
    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if no
