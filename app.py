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

<form id="checkinForm">
    <input type="text" id="name" placeholder="Name" required>
    <input type="text" id="ort" placeholder="Ort" readonly>
    <button type="submit">Einchecken</button>
</form>

<p id="status"></p>

<script>
navigator.geolocation.getCurrentPosition(
    function(pos) {
        document.getElementById("ort").value =
            pos.coords.latitude.toFixed(5) + ", " +
            pos.coords.longitude.toFixed(5);
    },
    function() {
        document.getElementById("ort").value = "Standort nicht verfügbar";
    }
);

document.getElementById("checkinForm").addEventListener("submit", function(e) {
    e.preventDefault();

    fetch("/checkin", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            name: document.getElementById("name").value,
            ort: document.getElementById("ort").value
        })
    })
    .then(r => r.json())
    .then(d => {
        document.getElementById("status").innerText = "✔ Anwesenheit gespeichert";
    })
    .catch(() => {
        document.getElementById("status").innerText = "❌ Fehler";
    });
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

    if not name:
        return jsonify({"error": "Name fehlt"}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([timestamp, name, ort])

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
