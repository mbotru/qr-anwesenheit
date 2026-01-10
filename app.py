from flask import Flask, render_template, jsonify
import uuid
import time

app = Flask(__name__)

# Hauptseite laden
@app.route('/')
def index():
    # Stellt sicher, dass die Datei templates/qr_display.html existiert
    return render_template('qr_display.html')

# Daten-Schnittstelle für den QR-Code
@app.route('/get_qr')
def get_qr():
    # Erzeugt einen neuen Token (Inhalt des QR-Codes)
    new_token = f"QR_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    
    # Gibt die Daten als JSON zurück, damit JS sie lesen kann
    return jsonify({
        "status": "success",
        "qr_string": new_token
    })

if __name__ == '__main__':
    # host='0.0.0.0' erlaubt Zugriff von anderen Geräten im WLAN
    app.run(host='0.0.0.0', port=5000, debug=True)
