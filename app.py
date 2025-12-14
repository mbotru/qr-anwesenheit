from flask import Flask, request, render_template_string, send_file
from datetime import datetime
from geopy.geocoders import Nominatim
import qrcode
import gspread
from google.oauth2.service_account import Credentials
import os

app = Flask(__name__)

# =======================
# Google Sheets Setup
# =======================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

CREDS = Credentials.from_service_account_file(
    "service_account.json",
    scopes=SCOPES
)

gc = gspread.authorize(CREDS)

SPREADSHEET_ID = "1AbCDefGhIJkLmNoPqRsTuvwXYZ"
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1



# =======================
# Standort (Ort)
# =======================
geolocator = Nominatim(user_agent="anwesenheit_qr_app")

def get_city(lat, lon):
    try:
        location = geolocator.reverse(
            f"{lat}, {lon}",
            language="de",
            exactly_one=True
        )
        if not location:
            return "Unbekannt"

        addr = location.raw.get("address", {})
        return (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("municipality")
            or "Unbekannt"
        )
    except Exception:
        return "Unbekannt"


# =======================
# QR-Code
# =======================
QR_FILE = "qr.png"

def create_qr(url):
    img = qrcode.make(url)
    img.save(QR_FILE)


# =======================
# Routes
# =======================
@app.route("/")
def index():
    url = request.host_url + "checkin"
    create_qr(url)

    return render_template_string("""
    <!doctype html>
    <html lang="de">
    <head>
        <meta charset="utf-8">
        <title>Anwesenheit QR</title>
    </head>
    <body>
        <h2>QR-Code scannen</h2>
        <img src="/qr" width="300">
        <p>{{ url }}</p>
    </body>
    </html>
    """, url=url)


@app.route("/qr")
def qr():
    return send_file(QR_FILE, mimetype="image/png")


@app.route("/checkin", methods=["GET", "POST"])
def checkin():
    if request.method == "POST":
        name = request.form.get("name")
        lat = request.form.get("lat")
        lon = request.form.get("lon")

        city = get_city(lat, lon)
        time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sheet.append_row([name, time, city])

        return f"""
        <h3>✅ Gespeichert</h3>
        <p><b>Name:</b> {name}</p>
        <p><b>Ort:</b> {city}</p>
        """

    return render_template_string("""
    <!doctype html>
    <html lang="de">
    <head>
        <meta charset="utf-8">
        <title>Check-in</title>
    </head>
    <body>
        <h2>Anwesenheit eintragen</h2>

        <form method="POST">
            <input name="name" placeholder="Name" required><br><br>
            <input type="hidden" name="lat" id="lat">
            <input type="hidden" name="lon" id="lon">
            <button type="submit">Einchecken</button>
        </form>

        <script>
        navigator.geolocation.getCurrentPosition(
            pos => {
                document.getElementById("lat").value = pos.coords.latitude;
                document.getElementById("lon").value = pos.coords.longitude;
            },
            err => alert("Standortfreigabe ist erforderlich!")
        );
        </script>
    </body>
    </html>
    """)


# =======================
# Local run (optional)
# =======================
if __name__ == "__main__":
    app.run(debug=True)
