from flask import Flask, request, jsonify, render_template_string, abort
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime

# =====================================
# KONFIGURATION
# =====================================

SPREADSHEET_ID = "1d_ZgrOqK1NT0U7qRm5aKsw5hSjO1fQqHgbK-DK9Y_fo"
SECRET_TOKEN = "QR2025-ZUTRITT"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# =====================================
# GOOGLE AUTH
# =====================================

credentials = Credentials.from_service_account_file(
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
    scopes=SCOPES
)

gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# =====================================
# FLASK
# =====================================

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>QR Anwesenheit</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { font-family: Arial; max-width: 420px; margin: 40px auto; }
input, button { width: 100%; padding: 12px; margin-top: 12px; }
button { background: #2e7d32; color: white; border: none; }
</style>
</head>
<body>

<h2>Anwesenheit erfassen</h2>

<form id="form">
<input id="name" placeholder="Name" required>
<input id="ort" readonly placeholder="Ort wird ermittelt..." required>
<button>Einchecken</button>
</form>

<div id="status"></div>

<script>
const token = "{{ token }}";

navigator.geolocation.getCurrentPosition(async pos => {
    const lat = pos.coords.latitude;
    const lon = pos.coords.longitude;

    const r = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
    const d = await r.json();

    document.getElementById("ort").value =
        (d.address.city || d.address.town || d.address.village || "Unbekannt")
        + ", " + (d.address.country || "");
});

document.getElementById("form").addEventListener("submit", async e => {
    e.preventDefault();

    const res = await fetch("/checkin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            token: token,
            name: name.value,
            ort: ort.value
        })
    });

    status.innerText = res.ok ? "✔ Gespeichert" : "❌ Fehler";
});
</script>

</body>
</html>
"""

@app.route("/")
def index():
    token = request.args.get("token")
    if token != SECRET_TOKEN:
        abort(403)
    return render_template_string(HTML_PAGE, token=token)

@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.json

    if data.get("token") != SECRET_TOKEN:
        return jsonify({"error": "unauthorized"}), 403

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data["name"],
        data["ort"]
    ])

    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run()
