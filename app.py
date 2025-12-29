import io
import csv
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- KONFIGURATION ---
# Nutzt eine Umgebungsvariable auf Render oder einen Standardwert lokal
app.secret_key = os.environ.get('SECRET_KEY', 'dein-sehr-sicherer-schluessel-123')

# Datenbank-Pfad: Automatische Erkennung ob Render (Postgres) oder Lokal (SQLite)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///checkins.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- DATENBANK MODELL ---
class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vorname = db.Column(db.String(100), nullable=False)
    nachname = db.Column(db.String(100), nullable=False)
    buerotag_nachholen = db.Column(db.String(20), nullable=False)
    datum = db.Column(db.DateTime, default=datetime.utcnow)

# --- ADMIN LOGIN DATEN ---
ADMIN_BENUTZER = 'admin'
# WICHTIG: Ersetze 'deinpasswort' durch dein echtes Wunschpasswort
ADMIN_PASSWORT_HASH = generate_password_hash('deinpasswort')

# Datenbank initialisieren
with app.app_context():
    db.create_all()

# --- ROUTEN ---

# 1. Startseite: Check-In Formular
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        vorname = request.form.get('vorname')
        nachname = request.form.get('nachname')
        buerotag = request.form.get('buerotag_nachholen', 'Nein')

        neuer_eintrag = CheckIn(
            vorname=vorname,
            nachname=nachname,
            buerotag_nachholen=buerotag
        )
        db.session.add(neuer_eintrag)
        db.session.commit()
        return render_template('index.html', success=True)
    return render_template('index.html')

# 2. Admin Login
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == ADMIN_BENUTZER and check_password_hash(ADMIN_PASSWORT_HASH, password):
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = 'Ungültige Zugangsdaten!'
    return render_template('admin.html', error=error)

# 3. Admin Dashboard
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('admin'))
    
    # Alle Einträge laden, neueste zuerst
    alle_checkins = CheckIn.query.order_by(CheckIn.datum.desc()).all()
    return render_template('dashboard.html', checkins=alle_checkins)

# 4. CSV Export mit Datumsfilter
@app.route('/admin/export/csv')
def export_csv():
    if not session.get('logged_in'):
        return redirect(url_for('admin'))

    filter_date = request.args.get('date') # Datum aus dem Formular holen
    query = CheckIn.query

    if filter_date:
        # Filtert nur Einträge des spezifischen Tages
        query = query.filter(func.date(CheckIn.datum) == filter_date)

    eintraege = query.all()

    # CSV im Speicher erstellen
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Vorname', 'Nachname', 'Bürotag nachholen', 'Datum'])
    
    for row in eintraege:
        cw.writerow([
            row.vorname, 
            row.nachname, 
            row.buerotag_nachholen, 
            row.datum.strftime('%Y-%m-%d %H:%M:%S')
        ])

    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)
    
    filename = f"checkins_{filter_date if filter_date else 'alle'}.csv"
    return send_file(output, mimetype='text/csv', download_name=filename, as_attachment=True)

# 5. Eintrag löschen
@app.route('/admin/delete/<int:id>')
def delete_entry(id):
    if not session.get('logged_in'):
        return redirect(url_for('admin'))
    
    entry = CheckIn.query.get_or_404(id)
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('dashboard'))

# 6. Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    # debug=False ist sicherer für die Veröffentlichung
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
