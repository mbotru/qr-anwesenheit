from flask import Flask, request, jsonify, render_template
import os, json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests

# ================== CONFIG ==================
VALID_TOKEN = "QR2025-ZUTRITT"
SPREADSHEET_ID = "1d_ZgrOqK1NT0U7qRm5aKsw5hSjO1fQqHgbK-DK9Y_fo"
PORT = int(os.environ.get("PORT", 10000))

# ================== GOOGLE AUTH ==================
if "GOOGLE_CREDENTIALS_JSON" not in os.environ:
    raise RuntimeError("GOOGLE_CREDENTIALS_JSON fehlt. Bitte in Render setzen.")

try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
except json.JSONDecodeError:
    raise RuntimeError("GOOGLE_CREDENTIALS_JSON ist kein gültiges JSON")

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# ================== APP ==================
app = Flask(__name__)

# ================== HELPER: CITY ==================
def get_city(lat, lon):
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json"
        }
        headers = {"User-Agent": "qr-anwesenheit-app"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()

        address = data.get("address", {})
        return (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or "Unbekannt"
        )
    except Exception:
        return "Unbekannt"

# ================== ROUTES ==================
@app.route("/")
def index():
    token = request.args.get("token")
    if token != VALID_TOKEN:
        return "Zugriff verweigert", 403
    return render_template("index.html", token=token)

@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"message": "Ungültige Anfrage"}), 400

    name = data.get("name")
    token = data.get("token")
    device_id = data.get("device_id")
    lat = data.get("latitude")
    lon = data.get("longitude")

    if not all([name, token, device_id, lat, lon]):
        return jsonify({"message": "Unvollständige Daten"}), 400

    if token != VALID_TOKEN:
        return jsonify({"message": "Ungültiger QR-Code"}), 403

    city = get_city(lat, lon)

    now = datetime.now()
    sheet.append_row([
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        name,
        city,
        device_id
    ])

return jsonify({
    "status": "ok",
    "message": f"✅ Check-in erfolgreich – Ort: {city}"
})
return jsonify({
    "status": "error",
    "message": "❌ Unvollständige Daten"
}), 400
# ================== START ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
