from flask import Flask, request, jsonify, render_template_string, abort
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime, date

# =================================================
# KONFIGURATION
# =================================================

SPREADSHEET_ID = "1d_ZgrOqK1NT0U7qRm5aKsw5hSjO1fQqHgbK-DK9Y_fo"
SECRET_TOKEN = "QR2025-ZUTRITT"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# =================================================
# GOOGLE AUTH
# =================================================

credentials = Credentials.from_service_account_file(
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
    scopes=SCOPES
)

gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# =================================================
# FLASK
# =================================================

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>QR Anwesenheit</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { font-family: Arial; background:#f4f6f8; padding:16px; }
.container { max-width:420px; margin:auto; background:#fff; padding:24px;
             border-radius:14px; box-shadow:0 10px 25px rgba(0,0,0,0.08); }
input, button { width:100%; padding:14px; margin-top:14px; font-size:16px; }
button { background:#2e7d32; color:#fff; border:none; border-radius:12px; }
#status { margin-top:16px; text-align:center; font-weight:bold; }
</style>
</head>
<body>

<div class="container">
<h2>Anwesenheit erfassen</h2>

<form id="form">
<input id="name" placeholder="Name" required>
<input id="ort" readonly placeholder="Ort wird ermittelt..." required>
<button>Einchecken</button>
</form>

<div id="status"></div>
</div>

<script>
const TOKEN = "{{ token }}";

// ---------- Device ID ----------
let deviceId = localStorage.getItem("device_id");
if (!deviceId) {
    deviceId = crypto.randomUUID();
    localStorage.setItem("device_id", deviceId);
}

// ---------- Standort ----------
navigator.geolocation.getCurrentPosition(async pos => {
    const r = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`
    );
    const d = await r.json();
    document.getElementById("ort").value =
        (d.address.city || d.address.town || d.address.village || "Unbekannt")
        + ", " + (d.address.country || "");
}, () => {
    document.getElementById("ort").value = "Standort blockiert";
});

// ---------- Submit ----------
document.getElementById("form").addEventListener("submit", async e => {
    e.preventDefault();
    const status = document.getElementById("status");

    const res = await fetch("/checkin", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
            token: TOKEN,
            name: name.value,
            ort: ort.value,
            device_id: deviceId
        })
    });

    const data = await res.json();
    status.innerText = res.ok ? "✔ Erfolgreich eingecheckt" : "❌ " + data.error;
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
    if request.args.get("token") != SECRET_TOKEN:
        abort(403)
    return render_template_string(HTML_PAGE, token=SECRET_TOKEN)

@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.get_json()
    today = date.today().isoformat()

    name = data.get("name")
    ort = data.get("ort")
    device_id = data.get("device_id")

    if not name or not ort or not device_id:
        return jsonify({"error": "Unvollständige Daten"}), 400

    rows = sheet.get_all_values()[1:]  # ohne Header

    for row in rows:
        row_date, row_name, _, row_device = row
        if row_date == today and row_name == name and row_device == device_id:
            return jsonify({"error": "Heute bereits eingecheckt"}), 400

    sheet.append_row([today, name, ort, device_id])
    return jsonify({"status": "ok"})

# =================================================
# START
# =================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
