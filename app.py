from flask import Flask, request, jsonify, render_template
import gspread
from google.oauth2.service_account import Credentials
import os, json
from datetime import datetime, date
import requests

app = Flask(__name__)

# ---------------------------
# CONFIG
# ---------------------------
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1d_ZgrOqK1NT0U7qRm5aKsw5hSjO1fQqHgbK-DK9Y_fo")
QR_TOKEN = os.environ.get("QR_TOKEN", "QR2025-ZUTRITT")

# SharePoint Config
SHAREPOINT_SITE = os.environ.get("SP_SITE", "fwpgovch.sharepoint.com/sites/BIT_AGR_SDE")
LIST_NAME = os.environ.get("SP_LIST", "CHECKIN Anwesenheit Brotag")
SP_CLIENT_ID = os.environ.get("SP_CLIENT_ID")
SP_CLIENT_SECRET = os.environ.get("SP_CLIENT_SECRET")
SP_TENANT_ID = os.environ.get("SP_TENANT_ID")

# ---------------------------
# GOOGLE CREDENTIALS
# ---------------------------
if "GOOGLE_CREDENTIALS_JSON" not in os.environ:
    raise RuntimeError("GOOGLE_CREDENTIALS_JSON fehlt")

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
scopes = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# ---------------------------
# SharePoint Helper
# ---------------------------
def get_access_token():
    url = f"https://login.microsoftonline.com/{SP_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": SP_CLIENT_ID,
        "scope": "https://graph.microsoft.com/.default",
        "client_secret": SP_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

def send_to_sharepoint(vorname, nachname, nachholen):
    token = get_access_token()
    
    # Graph API Site ID automatisch holen
    site_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_SITE.split('://')[1].replace('/','.')}"
    # Einfach direkt List Items erstellen
    url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_SITE}/lists/{LIST_NAME}/items"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "fields": {
            "Vorname": vorname,
            "Nachname": nachname,
            "Nachholen": nachholen,
            "Datum": datetime.now().strftime("%Y-%m-%d")
        }
    }
    
    r = requests.post(url, headers=headers, json=data)
    r.raise_for_status()
    return r.json()

# ---------------------------
# ROUTES
# ---------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.get_json()

    vorname = data.get("vorname")
    nachname = data.get("nachname")
    nachholen = data.get("nachholen")
    token = data.get("token")

    if not vorname or not nachname or not nachholen or token != QR_TOKEN:
        return jsonify(error="Unvollständige oder ungültige Daten"), 400

    today = date.today().isoformat()
    rows = sheet.get_all_records()

    for r in rows:
        if (
            r.get("Vorname") == vorname
            and r.get("Nachname") == nachname
            and r.get("Datum") == today
        ):
            return jsonify(message="⚠️ Heute bereits eingecheckt"),
