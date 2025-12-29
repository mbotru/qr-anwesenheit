import io
import csv
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# SICHERHEIT: Nutze Umgebungsvariablen für Geheimnisse
app.secret_key = os.environ.get('SECRET_KEY', 'ein-sehr-sicherer-fallback-key')

# DATENBANK: Render stellt 'DATABASE_URL' bereit. Lokal wird 'sqlite:///checkins.db' genutzt.
database_url = os.environ.get('DATABASE_URL', 'sqlite:///checkins.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Datenbank-Modell
class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vorname = db.Column(db.String(50), nullable=False)
    nachname = db.Column(db.String(50), nullable=False)
    buerotag_nachholen = db.Column(db.String(10), nullable=False)
    datum = db.Column(db.DateTime, default=datetime.utcnow)

# Admin-Konfiguration (Passwort hier ändern!)
ADMIN_BENUTZER = 'admin'
ADMIN_PASSWORT_HASH = generate_password_hash('DEIN_NEUES_PASSWORT') # Hier anpassen!

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        neuer_eintrag = CheckIn(
            vorname=request.form.get('vorname'),
            nachname=request.form.get('nachname'),
            buerotag_nachholen=request.form.get('buerotag_nachholen', 'Nein')
        )
        db.session.add(neuer_eintrag)
        db.session.commit()
        return render_template('index.html', success=True)
    return render_template('index.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    fehler = None
    if request.method == 'POST':
        benutzername = request.form.get('username')
        passwort = request.form.get('password')
        if benutzername == ADMIN_BENUTZER and check_password_hash(ADMIN_PASSWORT_HASH, passwort):
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            fehler = 'Zugriff verweigert'
    return render_template('admin.html', error=fehler)

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('admin'))
    alle_checkins = CheckIn.query.order_by(CheckIn.datum.desc()).all()
    return render_template('dashboard.html', checkins=alle_checkins)

@app.route('/admin/export/csv')
def export_csv():
    if not session.get('logged_in'):
        return redirect(url_for('admin'))
    
    alle_checkins = CheckIn.query.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Vorname', 'Nachname', 'Bürotag nachholen', 'Datum'])
    for c in alle_checkins:
        writer.writerow([c.vorname, c.nachname, c.buerotag_nachholen, c.datum.strftime('%d.%m.%Y %H:%M')])
    
    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    return send_file(mem, mimetype='text/csv', download_name='checkins.csv', as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    # Debug ist hier auf False gesetzt für Produktion
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
