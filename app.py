import os
import uuid
import time
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# 1. Haupt-Route (Root)
@app.route('/')
def index():
    """Leitet die Startseite direkt auf das QR-Terminal."""
    return render_template('qr_display.html')

# 2. Deine spezifische Route aus den Logs
@app.route('/display')
def display_page():
    """Behebt den 404-Fehler für /display."""
    return render_template('qr_display.html')

# 3. Daten-Endpunkt für den QR-Code (wird vom JavaScript abgefragt)
@app.route('/get_qr')
def get_qr():
    """Generiert einen Token für den QR-Code."""
    try:
        # Einzigartiger Token aus Zeitstempel und Zufall-ID
        token = f"TOKEN-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        return jsonify({
            "status": "success",
            "qr_string": token
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# Start-Konfiguration für Render.com
if __name__ == '__main__':
    # Render nutzt dynamische Ports, daher lesen wir die Umgebungsvariable aus
    port = int(os.environ.get("PORT", 5000))
    # host='0.0.0.0' ist zwingend erforderlich für das Deployment
    app.run(host='0.0.0.0', port=port)
