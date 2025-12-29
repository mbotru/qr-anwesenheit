import io
import csv
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- KONFIGURATION FÜR STABILE SESSIONS (BEHEBT FALL A) ---
# WICHTIG: Setze 'SECRET_KEY' in den Render Environment Variables!
app.secret_key = os.environ.get('SECRET_KEY', 'ein-sehr-langer-geheimer-fallback-schlüssel')

# Cookie-Einstellungen für HTTPS (Render Standard)
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2)
)

# Datenbank-URL (Postgres für Render, SQLite für Lokal)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///checkins.db')
if database_url and database_url.startswith("postgres://"):
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
# Generiere deinen Hash lokal mit: generate_password_hash('deinpasswort')
# Dies ist der Hash für 'deinpasswort' (bitte später anpassen)
ADMIN_PASSWORT_HASH = generate_password_hash('deinpasswort')

with app.app_context():
    db.create_all()

# --- HILFSFUNKTION: CACHE-SCHUTZ ---
def prevent_cache(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# --- ROUTEN ---

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
    # Wenn bereits eingeloggt, direkt zum Dashboard
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
        
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == ADMIN_BENUTZER and check_password_hash(ADMIN_PASSWORT_HASH, password):
            session.clear()
            session.permanent = True  # Macht die Sitzung stabil
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = 'Ungültige Zugangsdaten.'
    
    return render_template('admin.html', error=error)

@app.route('/dashboard')
def dashboard():
    # Strengere Prüfung der Session
    if 'logged_in' not in session or session['logged_in'] is not True:
        return redirect(url_for('admin'))
    
    alle_checkins = CheckIn.query.order_by(CheckIn.datum.desc()).all()
    
    # Seite mit Cache-Schutz ausliefern
    response = make_response(render_template('dashboard.html', checkins=alle_checkins))
    return prevent_cache(response)

@app.route('/admin/export/csv')
def export_csv():
    if not session.get('logged_in'):
        return redirect(url_for('admin'))

    filter_date = request.args.get('date')
    query = CheckIn.query
    if filter_date:
        query = query.filter(func.date(CheckIn.datum) == filter_date)

    eintraege = query.all()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Vorname', 'Nachname', 'Bürotag nachholen', 'Datum'])
    for row in eintraege:
        cw.writerow([row.vorname, row.nachname, row.buerotag_nachholen, row.datum.strftime('%Y-%m-%d %H:%M:%S')])

    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)
    
    filename = f"checkins_{filter_date if filter_date else 'alle'}.csv"
    return send_file(output, mimetype='text/csv', download_name=filename, as_attachment=True)

@app.route('/admin/delete/<int:id>')
def delete_entry(id):
    if not session.get('logged_in'):
        return redirect(url_for('admin'))
    entry = CheckIn.query.get_or_404(id)
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
