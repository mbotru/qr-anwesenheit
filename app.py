import os
import uuid
import time
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# --- KONFIGURATION ---
# Hier kannst du einstellen, wie lange ein Code gültig sein soll (in Sekunden)
QR_REFRESH_INTERVAL = 15 

# --- ROUTEN ---

@app.route('/')
def index():
    """
    Lädt das Dashboard / Terminal.
    Die Seite qr_display.html muss im Ordner 'templates' liegen.
    """
    return render_template('qr_display.html')

@app.route('/generate_qr')
def generate_qr():
    """
    Dieser Endpunkt wird vom JavaScript (Frontend) automatisch aufgerufen.
    Er liefert die Daten für den QR-Code als JSON.
    """
    try:
        # Erzeuge einen einzigartigen Token
        # Besteht aus einer UUID und dem aktuellen Zeitstempel
        unique_id = str(uuid.uuid4())[:8] # Kurzform der ID
        current_time = int(time.time())
        
        # Der Inhalt des QR-Codes (z.B. für die App zum Scannen)
        qr_content = f"PRESENCE_TOKEN:{unique_id}:{current_time}"
        
        # Rückgabe als JSON
        return jsonify({
            "status": "success",
            "code": qr_content,
            "expires_in": QR_REFRESH_INTERVAL,
            "server_time": current_time
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# --- START ---

if __name__ == '__main__':
    # '0.0.0.0' macht den Server im lokalen Netzwerk erreichbar
    # Port 5000 ist Standard für Flask
    app.run(host='0.0.0.0', port=5000, debug=True)
