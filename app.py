import csv
import io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'dein_ganz_geheimer_schluessel' # In Produktion als Umgebungsvariable nutzen

# Admin-Konfiguration
ADMIN_BENUTZER = 'admin'
# Das ist der Hash für 'deinpasswort'. Ersetze ihn später durch einen eigenen.
ADMIN_PASSWORT_HASH = generate_password_hash('deinpasswort')

# Temporäre Liste (Sollte später durch eine Datenbank ersetzt werden)
checkins = []

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        vorname = request.form.get('vorname')
        nachname = request.form.get('nachname')
        buerotag_nachholen = request.form.get('buerotag_nachholen', 'Nein')
        datum = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

        checkins.append({
            'Vorname': vorname,
            'Nachname': nachname,
            'Bürotag nachholen': buerotag_nachholen,
            'Datum': datum
        })
        return render_template('index.html', success=True)
    return render_template('index.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    fehler = None
    if request.method == 'POST':
        benutzername = request.form.get('username')
        passwort = request.form.get('password')

        # Sicherer Passwort-Abgleich
        if benutzername == ADMIN_BENUTZER and check_password_hash(ADMIN_PASSWORT_HASH, passwort):
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            fehler = 'Ungültige Anmeldedaten'
    return render_template('admin.html', error=fehler)

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('admin'))
    # Neueste Check-ins zuerst anzeigen
    sortierte_daten = sorted(checkins, key=lambda x: x['Datum'], reverse=True)
    return render_template('dashboard.html', checkins=sortierte_daten)

@app.route('/admin/export/csv')
def export_csv():
    if not session.get('logged_in'):
        return redirect(url_for('admin'))

    # CSV im Speicher erstellen
    output_stream = io.StringIO()
    writer = csv.DictWriter(output_stream, fieldnames=['Vorname', 'Nachname', 'Bürotag nachholen', 'Datum'])
    writer.writeheader()
    writer.writerows(checkins)

    # In Bytes umwandeln für den Download
    mem = io.BytesIO()
    mem.write(output_stream.getvalue().encode('utf-8'))
    mem.seek(0)
    output_stream.close()

    dateiname = f"checkins_{datetime.now().strftime('%Y-%m-%d')}.csv"
    
    return send_file(
        mem,
        mimetype='text/csv',
        download_name=dateiname,
        as_attachment=True
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
