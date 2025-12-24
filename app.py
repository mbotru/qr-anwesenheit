from flask import Flask, render_template, request, redirect, url_for, send_file
from datetime import datetime, date
import csv
import io

app = Flask(__name__)

# In-Memory Storage für Check-Ins
records = []

# Admin Credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password"

# CSV Header
HEADERS = ["Vorname", "Nachname", "Bürotag nachholen", "Datum", "Uhrzeit"]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/checkin", methods=["POST"])
def checkin():
    vorname = request.form.get("vorname")
    nachname = request.form.get("nachname")
    nachholen = request.form.get("nachholen")
    now = datetime.now()
    record = {
        "Vorname": vorname,
        "Nachname": nachname,
        "Bürotag nachholen": nachholen,
        "Datum": now.date().isoformat(),
        "Uhrzeit": now.time().strftime("%H:%M:%S")
    }
    records.append(record)
    return render_template("success.html", record=record)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            return redirect(url_for("dashboard"))
        else:
            return render_template("admin.html", error="Falscher Benutzername oder Passwort")
    return render_template("admin.html")

@app.route("/admin/dashboard")
def dashboard():
    return render_template("dashboard.html", records=records)

@app.route("/admin/export/csv")
def export_csv():
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(HEADERS)
    for r in records:
        writer.writerow([r[h] for h in HEADERS])
    si.seek(0)
    return send_file(
        io.BytesIO(si.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"checkin_{date.today().isoformat()}.csv"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
