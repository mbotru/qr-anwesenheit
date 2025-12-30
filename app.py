import io
import csv
import os
import hashlib
from datetime import datetime, timedelta
import pytz
from flask import Flask, render_template, request, redirect, url_for, session, send_file, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- KONFIGURATION ---
BERLIN_TZ = pytz.timezone('Europe/Berlin')
QR_SECRET = os.environ.get('QR_SECRET', 'qr-sicherheit-2025')
app.secret_key = os.environ.get('SECRET_KEY', 'session-geheim-123')

# IP-Whitelist aus Render-Umgebungsvariablen laden
# Beispiel für den Wert in Render: "84.150.1.2, 127.0.0.1"
ALLOWED_IPS = [ip.strip() for ip in os.environ.get('ALLOWED_IPS', '127.0.0.1').split(',')]

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12) 
)

database_url = os.environ.get('DATABASE_URL', 'sqlite:///checkins.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODEL ---
class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vorname = db.Column(db.String(100), nullable=False)
    nachname = db.Column(db.String(100), nullable=False)
    buerotag_nachholen = db.Column(db.String(20), nullable=False)
    datum = db.Column(db.DateTime)

ADMIN_PASSWORT_HASH = generate_password_hash('deinpasswort')

with app.app_context():
    db.create_all()

# --- HILFSFUNKTIONEN ---

def get_client_ip():
    """Ermittelt die IP hinter dem Render-Proxy"""
    # Render nutzt den X-Forwarded-For Header
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def get_current_qr_token():
    time_step = int(datetime.now().timestamp() / 30)
    return hashlib.sha256(f"{QR_SECRET}{time_step}".encode()).hexdigest()[:10]

def is_mobile():
    ua = request.headers.get('User-Agent', '').lower()
    return any(k in ua for k in ['android', 'iphone', 'ipad', 'mobile'])

# --- ROUTEN ---

@app.route('/display')
def display_qr():
    """Terminal-Seite: Zugriff nur über IP-Whitelist ODER Login"""
    client_ip = get_client_ip()
    
    # Prüfen, ob die IP in der Whitelist ist
    if client_ip in ALLOWED_IPS or session.get('logged_in'):
        return render_template('qr_display.html')
    
    # Wenn IP nicht autorisiert, zeige Fehlermeldung mit der IP an (hilft beim Einrichten)
    return f"""
    <body style="background:#000;color:#f44;font-family:sans-serif;text-align:center;padding-top:100px;">
        <h1>Zugriff verweigert</h1>
        <p>Dieses Terminal ist für Ihre IP ({client_ip}) nicht freigeschaltet.</p>
        <p><a href="/admin" style="color:#0ff;">Als Admin anmelden</a></p>
    </body>
    """, 403

@app.route('/get_qr_token')
def get_token_api():
    """API-Schutz: Nur Whitelist oder Login"""
    if get_client_ip() in ALLOWED_IPS or session.get('logged_in'):
        return jsonify({"token": get_current_qr_token()})
    return jsonify({"error": "Unauthorized"}), 403

@app.route('/', methods=['GET', 'POST'])
def index():
    if not is_mobile():
        return render_template('mobile_only.html'), 403
    
    user_token = request.args.get('token')
    # Validierung wie bisher...
    if user_token != get_current_qr_token():
        prev_step = int(datetime.now().timestamp() / 30) - 1
        prev_token = hashlib.sha256(f"{QR_SECRET}{prev_step}".encode()).hexdigest()[:10]
        if user_token != prev_token:
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

# Admin & Dashboard (identisch wie zuvor)
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('logged_in'): return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        if request.form.get('username') == 'admin' and \
           check_password_hash(ADMIN_PASSWORT_HASH, request.form.get('password')):
            session.permanent = True
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        error = 'Login fehlgeschlagen.'
    return render_template('admin.html', error=error)

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'): return redirect(url_for('admin'))
    search = request.args.get('search', '').strip()
    date_val = request.args.get('date', '')
    query = CheckIn.query
    if search:
        comb = func.concat(CheckIn.vorname, ' ', CheckIn.nachname)
        query = query.filter(or_(CheckIn.vorname.ilike(f'%{search}%'), CheckIn.nachname.ilike(f'%{search}%'), comb.ilike(f'%{search}%')))
    if date_val:
        query = query.filter(func.date(CheckIn.datum) == date_val)
    checkins = query.order_by(CheckIn.datum.desc()).all()
    return render_template('dashboard.html', checkins=checkins, search=search, date=date_val)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
