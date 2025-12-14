from flask import Flask, request, render_template_string, send_file
from datetime import datetime
from geopy.geocoders import Nominatim
import qrcode
import gspread
from google.oauth2.service_account import Credentials
import os

app = Flask(__name__)

# ---------- Google Sheets ----------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDS = Credentials.from_service_account_file(
    "service_account.json", scopes=SCOPES
)
gc = gspread.authorize(CREDS)

SHEET_NAME = "Anwesenheit QR"
sheet = gc.open(SHEET_NAME).sheet1

# ---------- Standort ----------
geolocator = Nominatim(user_agent="anwesenheit_app")

def get_city(lat, lon):
    try:
        location = geolocator.reverse(
            f"{lat}, {lon}", language="de", exactly_one=True
        )
        if not location:
            return "Unbekannt"

        addr = location.raw.get("address", {})
        return (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or "Unbekannt"
        )
    except:
        return "Unbekannt"

# ---------- QR-Code ----------
QR_FILE = "qr.png"

def create_qr(url):
    img = qrcode.make(url)
    img.save(QR_FILE)

@app.route("/")
def index():
    url = request.host_url + "checkin"
    create_qr(url)

    return render_template_string("""
    <h2>QR-Code scannen</h2>
    <img src="/qr" width="300">
    <p>{{ url }}</p>
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

        return f"<h3>✅ Gespeichert – Ort: {city}</h3>"

    return render_template_string("""
    <h2>Anwesenheit</h2>
    <form method="POST">
        <input name="name" placeholder="Name" required><br><br>
        <input type="hidden" name="lat" id="lat">
        <input type="hidden" name="lon" id="lon">
        <button>Einchecken</button>
    </form>

    <script>
    navigator.geolocation.getCurrentPosition(
        pos => {
            lat.value = pos.coords.latitude;
            lon.value = pos.coords.longitude;
        },
        err => alert("Standortfreigabe erforderlich!")
    );
    </script>
    """)
