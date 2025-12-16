from flask import Flask, request, jsonify, render_template
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import datetime

# ===============================
# FLASK APP
# ===============================
app = Flask(__name__)

# ===============================
# KONFIGURATION
# ===============================
VALID_TOKEN = "QR2025-ZUTRITT"
SPREADSHEET_ID = "1d_ZgrOqK1NT0U7qRm5aKsw5hSjO1fQqHgbK-DK9Y_fo"   # <- WICHTIG

# ===============================
# GOOGLE CREDENTIALS LADEN
# ===============================
if "GOOGLE_CREDENTIALS_JSON" not in os.environ:
    raise RuntimeError(
        "GOOGLE_CREDENTIALS_JSON fehlt. "
        "Bitte in Render → Environment → Secrets setzen."
    )

try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
except Exception as e:
    raise RuntimeError("GOOGLE_CREDENTIALS_JSON
