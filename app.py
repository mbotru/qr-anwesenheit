from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_file
import gspread
from google.oauth2.service_account import Credentials
import os, json
from datetime import datetime, date
from zoneinfo import ZoneInfo
import pandas as pd
import io
import csv

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")

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
    vorname = data.get("vorname")
    nachname = data.get("nachname")
    nachholen = data.get("nachholen")
    token = data.get("token", QR_TOKEN)

    if not vorname or not nachname or not nachholen or token != QR_TOKEN:
        return jsonify(error="Unvollständige oder ungültige Daten"), 400

    now = datetime.now(tz)
    today = now.date().isoformat()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    # Prüfen, ob heute schon eingecheckt
    rows = sheet.get_all_records()
    for r in rows:
        if r.get("Vorname") == vorname and r.get("Nachname") == nachname and r.get("Datum") == today:
            return jsonify(message="⚠️ Heute bereits eingecheckt"), 200

    # Eintragen
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
            session['admin_logged_in'] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template("admin_login.html", error="Falsches Passwort")
    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for("admin"))

    records = sheet.get_all_records()
    df = pd.DataFrame(records)

    # Statistik: Check-Ins pro Tag
    stats = df.groupby("Datum").size().to_dict()

    return render_template("admin_dashboard.html", stats=stats, records=records)

# ---------------------------
# CSV EXPORT NACH DATUM
# ---------------------------
@app.route("/admin/export/csv")
def admin_export_csv_all():
    if not session.get('admin_logged_in'):
        return redirect(url_for("admin"))

    records = sheet.get_all_records()
    return _build_csv(records, f"checkin_{date.today().isoformat()}.csv")

def _build_csv(records, filename):
    output = io.StringIO()
    writer = csv.writer(output)
    # Header
    if records:
        HEADERS = records[0].keys()
        writer.writerow(HEADERS)
        for row in records:
            writer.writerow([row[h] for h in HEADERS])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        download_name=filename,
        as_attachment=True
    )

@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for("admin"))

# ---------------------------
# START
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
