from flask import Flask, request, jsonify, render_template_string
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime

# =========================
# KONFIGURATION
# =========================

SPREADSHEET_ID = "1d_ZgrOqK1NT0U7qRm5aKsw5hSjO1fQqHgbK-DK9Y_fo"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# =========================
# GOOGLE AUTH
# =========================

credentials = Credentials.from_service_account_file(
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
    scopes=SCOPES
)

gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# =========================
# FLASK APP
# =========================

app = Flask(__name__)

HTML_FORM = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>QR Anwesenheit</title>
<style>
body { font-family: Arial; max-width: 400px; margin: 50px auto; }
input, button { width: 100%; padding: 10px; margin-top: 10px; }
button { background: #2e7d32; color: white; border: none; }
</style>
</head>
<body>

<h2>Anwesenheit erfassen</h2>

<form id="form">
    <input type="text" id="name" placeholder="Name" required>
    <input type="text" id="ort" placeholder="Ort wird ermittelt…" readonly>
    <button type="submit">Einchecken</button>
</form>

<p id="status"></p>

<script>
// GPS holen
navigator.geolocation.getCurrentPosition(async pos => {
    const lat = pos.coords.latitude;
    const lon = pos.coords.longitude;

    // Reverse Geocoding (OpenStreetMap)
    const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`
    );
    const data = await res.json();

    const city =
        data.address.city ||
        data.address.town ||
        data.address.village ||
        "";

    const country = data.address.country || "";

    document.getElementById("ort").value = city + ", " + country;
});

// Formular senden
document.getElementById("form").addEventListener("submit", async e => {
    e.preventDefault();

    const response = await fetch("/checkin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            name: document.getElementById("name").value,
            ort: document.getElementById("ort").value
        })
    });

    document.getElementById("status").innerText =
        response.ok ? "✔ Gespeichert" : "❌ Fehler";
});
</script>

</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_FORM)

@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.get_json()

    name = data.get("name")
    ort = data.get("ort")

    if not name or not ort:
        return jsonify({"error": "Name oder Ort fehlt"}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([timestamp, name, ort])

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
