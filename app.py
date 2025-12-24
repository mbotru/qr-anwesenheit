from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from datetime import datetime, date
import csv
import io
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Für Flash Messages

# Speicher für Checkins (in-memory, kann auf DB umgestellt werden)
records = []

# ----- ROUTES -----

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        firstname = request.form.get("firstname", "").strip()
        lastname = request.form.get("lastname", "").strip()
        makeup = request.form.get("makeup", "nein")
        checkin_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not firstname or not lastname:
            flash("Bitte Vorname und Nachname ausfüllen!", "error")
            return redirect(url_for("index"))

        # Record speichern
        records.append({
            "Vorname": firstname,
            "Nachname": lastname,
            "Bürotag nachholen": makeup,
            "Check-in Zeit": checkin_time
        })
        flash(f"{firstname} {lastname} eingecheckt!", "success")
        return redirect(url_for("index"))

    return render_template("index.html")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    password = request.form.get("password", "")
    if request.method == "POST":
        if password == "admin123":  # Admin-Passwort (kann DB/ENV sein)
            return redirect(url_for("dashboard"))
        else:
            flash("Falsches Passwort!", "error")
            return redirect(url_for("admin"))
    return render_template("admin.html")

@app.route("/admin/dashboard")
def dashboard():
    return render_template("admin_dashboard.html", records=records)

@app.route("/admin/export/csv")
def export_csv():
    # CSV-Datei in-memory erstellen
    output = io.StringIO()
    fieldnames = ["Vorname", "Nachname", "Bürotag nachholen", "Check-in Zeit"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for rec in records:
        writer.writerow(rec)

    output.seek(0)
    filename = f"checkin_{date.today().isoformat()}.csv"

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
