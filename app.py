from flask import Flask, request, jsonify, render_template_string, abort
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime

# =================================================
# KONFIGURATION
# =================================================

SPREADSHEET_ID = "1d_ZgrOqK1NT0U7qRm5aKsw5hSjO1fQqHgbK-DK9Y_fo"
SECRET_TOKEN = "QR2025-ZUTRITT"

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

<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">

<style>
* { box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial;
    background: #f4f6f8;
    margin: 0;
    padding: 16px;
}

.container {
    max-width: 420px;
    margin: auto;
    background: #ffffff;
    padding: 24px;
    border-radius: 14px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.08);
}

h2 {
    text-align: center;
    margin-bottom: 24px;
}

input {
    width: 100%;
    padding: 14px;
    margin-top: 14px;
    font-size: 16px;
    border-radius: 10px;
    border: 1px solid #ccc;
}

input[readonly] {
    background-color: #f0f0f0;
}

button {
    width: 100%;
    margin-top: 20px;
    padding: 16px;
    font-size: 18px;
    border-radius: 12px;
    border: none;
    background-color: #2e7d32;
    color: white;
}

button:active {
    transform: scale(0.98);
}

#status {
    text-align: center;
    margin-top: 16px;
    font-weight: 600;
}
</style>
</head>

<body>

<div class="container">
    <h2>Anwesenheit erfassen</h2>

    <form id="checkinForm">
        <input type="text" id="name" placeholder="Name" required>
        <input type="text" id="ort" placeholder="Ort wird ermittelt..." readonly required>
        <button type="submit">Einchecken</button>
    </form>

    <div id="status"></div>
</div>

<script>
const TOKEN = "{{ token }}";

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
                    { headers: { "User-Agent": "QR-Anwesenheit/1.0" } }
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
            } catch {
                ortFeld.value = "Ort konnte nicht ermittelt werden";
            }
        },
        () => {
            ortFeld.value = "Standort blockiert";
        },
        { enableHighAccuracy: true, timeout: 10000 }
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
            token: TOKEN,
            name: document.getElementById("name").value,
            ort: document.getElementById("ort").value
        })
    });

    if (response.ok) {
        status.innerText = "✔ Anwesenheit gespeichert";
        status.style.color = "#2e7d32";
        document.getElementById("checkinForm").reset();
    } else {
        const err = await response.json();
        status.innerText = "❌ " + (err.error || "Fehler");
        status.style.color = "#c62828";
    }
});
</script>

</body>
</html>
"""

# =================================================
# ROUTES
# =================================================

@app.route("/")
def index():
    token = request.args.get("token")
    if token != SECRET_TOKEN:
        abort(403)
    return render_template_string(HTML_PAGE, token=token)

@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Keine Daten empfangen"}), 400

    if data.get("token") != SECRET_TOKEN:
        return jsonify({"error": "Ungültiger Token"}), 403

    name = data.get("name")
    ort = data.get("ort")

    if not name or not ort:
        return jsonify({"error": "Name oder Ort fehlt"}), 400

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        name,
        ort
    ])

    return jsonify({"status": "ok"})

# =================================================
# START
# =================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
