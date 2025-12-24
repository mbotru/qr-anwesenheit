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
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin"))

    records = sheet.get_all_records()
    stats = {}
    for r in records:
        d = r.get("Datum")
        stats[d] = stats.get(d, 0) + 1

    return render_template("admin_dashboard.html", records=records, stats=stats)

# ---------------------------
# CSV EXPORT – ALLE
# ---------------------------
@app.route("/admin/export/csv")
def admin_export_csv_all():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin"))

    records = sheet.get_all_records()
    return _build_csv(records, f"checkin_{date.today().isoformat()}.csv")

# ---------------------------
# CSV EXPORT – NACH DATUM
# ---------------------------
@app.route("/admin/export/csv/<export_date>")
def admin_export_csv_by_date(export_date):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin"))

    try:
        datetime.strptime(export_date, "%Y-%m-%d")
    except ValueError:
        return "Ungültiges Datum (YYYY-MM-DD)", 400

    records = sheet.get_all_records()
    filtered = [r for r in records if r.get("Datum") == export_date]

    return _build_csv(filtered, f"checkin_{export_date}.csv")

# ---------------------------
# CSV BUILDER
# ---------------------------
def _build_csv(records, filename):
    buffer = BytesIO()
    wrapper = TextIOWrapper(buffer, encoding="utf-8-sig", newline="", write_through=True)
    
    writer = csv.writer(wrapper, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(HEADERS)
    
    for r in records:
        writer.writerow([
            r.get("Zeitstempel", ""),
            r.get("Datum", ""),
            r.get("Vorname", ""),
            r.get("Nachname", ""),
            r.get("Nachholen", "")
        ])
    
    wrapper.flush()
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name=filename
    )

# ---------------------------
# LOGOUT
# ---------------------------
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin"))

# ---------------------------
# START
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
