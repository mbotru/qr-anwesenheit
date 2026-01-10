import io
import csv
import os
import hashlib
from datetime import datetime, timedelta
import pytz
from flask import Flask, render_template, request, redirect, url_for, session, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- KONFIGURATION ---
BERLIN_TZ = pytz.timezone('Europe/Berlin')
QR_SECRET = os.environ.get('QR_SECRET', 'qr-sicherheit-2025-system')
app.secret_key = os.environ.get('SECRET_KEY', 'admin-session-schutz-123')

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12)
)

# Datenbank-Anbindung (Render Postgres oder lokal SQLite)
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
    buerotag_nachholen = db.Column(db.String(20), default="Nein")
    datum = db.Column(db.DateTime)

with app.app_context():
    db.create_all()

# --- ADMIN LOGIN DATEN ---
ADMIN_BENUTZER = 'admin'
ADMIN_PASSWORT_HASH = generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'deinpasswort'))

# --- HILFSFUNKTIONEN ---
def get_current_qr_token():
    # Erzeugt alle 30 Sekunden einen neuen Token basierend auf der Zeit
    time_step = int(datetime.now().timestamp() / 30)
    return hashlib.sha256(f"{QR_SECRET}{time_step}".encode()).hexdigest()[:10]

def is_mobile():
    ua = request.headers.get('User-Agent', '').lower()
    return any(k in ua for k in ['android', 'iphone', 'ipad', 'mobile'])

# --- ROUTEN: FRONTEND (Check-In via QR) ---

@app.route('/')
def root_redirect():
    """Leitet die Startseite auf /display weiter, um 403-Fehler zu vermeiden."""
    return redirect(url_for('display_qr'))

@app.route('/checkin', methods=['GET', 'POST'])
def index():
    if not is_mobile():
        return render_template('mobile_only.html'), 403
    
    user_token = request.args.get('token')
    current_token = get_current_qr_token()
    
    # Validierung des aktuellen und des vorherigen Tokens (Toleranzfenster)
    prev_step = int(datetime.now().timestamp() / 30) - 1
    prev_token = hashlib.sha256(f"{QR_SECRET}{prev_step}".encode()).hexdigest()[:10]

    if user_token not in [current_token, prev_token]:
        return render_template('expired.html'), 403

    if request.method == 'POST':
        jetzt_berlin = datetime.now(BERLIN_TZ).replace(tzinfo=None)
        neuer_eintrag = CheckIn(
            vorname=request.form.get('vorname'),
            nachname=request.form.get('nachname'),
            buerotag_nachholen=request.form.get('buerotag_nachholen', 'Nein'),
            datum=jetzt_berlin
        )
        db.session.add(neuer_eintrag)
        db.session.commit()
        return render_template('index.html', success=True, token=user_token)
    
    return render_template('index.html', token=user_token)

# --- ROUTEN: TERMINAL & SCANNER ---

@app.route('/display')
def display_qr():
    """Zeigt das kompakte QR-Code Terminal an."""
    return render_template('qr_display.html')

@app.route('/get_qr_token')
def get_token_api():
    """Schnittstelle für das Terminal-JavaScript (JSON-Antwort)."""
    token = get_current_qr_token()
    # Generiert die URL, die im QR-Code enthalten sein soll
    qr_url = url_for('index', token=token, _external=True)
    return jsonify({
        "status": "success",
        "qr_string": qr_url,
        "token": token
    })

# --- ADMIN BEREICH & EXPORT ---

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_BENUTZER and \
           check_password_hash(ADMIN_PASSWORT_HASH, request.form.get('password')):
            session.permanent = True
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        error = 'Login fehlgeschlagen.'
    return render_template('admin.html', error=error)

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('admin'))
    
    search = request.args.get('search', '').strip()
    date_val = request.args.get('date', '')
    
    query = CheckIn.query
    if search:
        query = query.filter(or_(CheckIn.vorname.ilike(f'%{search}%'), CheckIn.nachname.ilike(f'%{search}%')))
    if date_val:
        query = query.filter(func.date(CheckIn.datum) == date_val)
        
    checkins = query.order_by(CheckIn.datum.desc()).all()
    return render_template('dashboard.html', checkins=checkins, search=search, date=date_val)

@app.route('/export_csv')
def export_csv():
    if not session.get('logged_in'):
        return redirect(url_for('admin'))
    
    query = CheckIn.query.order_by(CheckIn.datum.desc()).all()
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    cw.writerow(['Vorname', 'Nachname', 'Datum', 'Uhrzeit', 'Nachholen'])
    
    for c in query:
        d_str = c.datum.strftime('%d.%m.%Y') if c.datum else ''
        t_str = c.datum.strftime('%H:%M') if c.datum else ''
        cw.writerow([c.vorname, c.nachname, d_str, t_str, c.buerotag_nachholen])
    
    csv_output = "\ufeff" + si.getvalue()
    output = make_response(csv_output)
    output.headers["Content-Disposition"] = "attachment; filename=export_anwesenheit.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    # Automatische Erkennung des Ports (wichtig für Render)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
