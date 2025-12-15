from flask import Flask, request, jsonify, render_template_string
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime

# =================================================
# KONFIGURATION
# =================================================

SPREADSHEET_ID = "1d_ZgrOqK1NT0U7qRm5aKsw5hSjO1fQqHgbK-DK9Y_fo"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# =================================================
# GOOGLE AUTH (Render Secret File)
# =================================================

credentials = Credentials.from_service_account_file(
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
    scopes=SCOPES
)

gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# =================================================
# FLASK APP
# =================================================

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>QR Anwesenheit</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family: Arial, sans-serif; max-width: 420px; margin: 40px auto; }
input, button { width: 100%; padding: 12px; margin-top: 12px; font-size: 16px; }
button { background-color: #2e7d32; color: white; border: none; }
#status { margin-top: 15px; font-weight: bold; }
</style>
</head>
<body>

<h2>Anwesenheit erfassen</h2>

<form id="checkinForm">
    <input type="text" id="name" placeholder="Name" required>
    <input type="text" id="ort" placeholder="Ort wird ermittelt..." readonly required>
    <button type="submit">Einchecken</button>
</form>

<div id="status"></div>

<script>
async function ermittleOrt() {
    const ortFeld = document.getElementById("ort");

    if (!navigator.geolocation) {
        ortFeld.value = "Geolocation nicht unterstützt";
        return;
    }

    navigator.geolocation.getCurrentPosition(
        async pos => {
            try {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;

                const response = await fetch(
                    `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`,
                    {
                        headers: {
                            "User-Agent": "QR-Anwesenheit/1.0"
                        }
                    }
                );

                const data = await response.json();

                const city =
                    data.address.city ||
                    data.address.town ||
                    data.address.village ||
                    data.address.hamlet ||
                    "Unbekannter Ort";

                const country = data.address.country || "";

                ortFeld.value = city + ", " + country;
            } catch (e) {
                ortFeld.value = "Ort konnte nicht ermittelt werden";
            }
        },
        () => {
            ortFeld.value = "Standort blockiert";
        },
        {
            enableHighAccuracy: true,
            timeout: 10000
        }
    );
}

ermittleOrt();

document.getElementById("checkinForm").addEventListener("submit", async e => {
    e.preventDefault();

    const status = document.getElementById("status");

    const response = await fetch("/checkin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            name: document.getElementById("name").value,
            ort: document.getElementById("ort").value
        })
    });

    if (response.ok) {
        status.innerText = "✔ Anwesenheit gespeichert";
        status.style.color = "green";
    } else {
        status.innerText = "❌ Fehler beim Speichern";
        status.style.color = "red";
    }
});
</script>

</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.get_json()

    name = data.get("name")
    ort = data.get("ort")

    if not name or not ort or "blockiert" in ort.lower():
        return jsonify({"error": "Ungültige Daten"}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([timestamp, name, ort])

    return jsonify({"status": "ok"})

# =================================================
# START (lokal)
# =================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
