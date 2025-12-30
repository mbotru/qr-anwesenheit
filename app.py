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
QR_SECRET = os.environ.get('QR_SECRET', 'qr-sicherheit-2025-system')
app.secret_key = os.environ.get('SECRET_KEY', 'admin-session-schutz-123')

# IP-Whitelist aus Render-Umgebungsvariablen (z.B. "1.2.3.4, 5.6.7.8")
ALLOWED_IPS = [ip.strip() for ip in os.environ.get('ALLOWED_IPS', '127.0.0.1').split(',')]

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12)
)

# Datenbank-Anbindung
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
ADMIN_PASSWORT_HASH = generate_password_hash('deinpasswort') # Ändern!

# --- HILFSFUNKTIONEN ---

def get_client_ip():
    """Ermittelt die IP hinter dem Proxy (Render)"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def get_current_qr_token():
    """Erzeugt einen Token, der alle 30 Sekunden wechselt"""
    time_step = int(datetime.now().timestamp() / 30)
    hash_input = f"{QR_SECRET}{time_step}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:10]

def is_mobile():
    """Prüft auf mobile Endgeräte"""
    ua = request.headers.get('User-Agent', '').lower()
    return any(k in ua for k in ['android', 'iphone', 'ipad', 'mobile'])

def prevent_cache(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# --- ROUTEN: FRONTEND (MITARBEITER SMARTPHONE) ---

@app.route('/', methods=['GET', 'POST'])
def index():
    # 1. Mobile Check
    if not is_mobile():
        return render_template('mobile_only.html'), 403

    # 2. QR-Token Validierung
    user_token = request.args.get('token')
    current_token = get_current_qr_token()
    
    # Toleranz: Letzten Token auch erlauben
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

# --- ROUTEN: TERMINAL & BACKUP (BÜRO-GERÄT) ---

@app.route('/display')
def display_qr():
    """QR-Terminal für Smartphone-Scans (IP-geschützt)"""
    client_ip = get_client_ip()
    if client_ip in ALLOWED_IPS or session.get('logged_in'):
        return render_template('qr_display.html')
    return render_template('ip_denied.html', ip=client_ip), 403

@app.route('/scanner')
def scanner():
    """Backup: Webcam-Scanner für physische Mitarbeiter-Karten (IP-geschützt)"""
    client_ip = get_client_ip()
    if client_ip in ALLOWED_IPS or session.get('logged_in'):
        return render_template('scanner.html')
    return render_template('ip_denied.html', ip=client_ip), 403

@app.route('/quick-checkin')
def quick_checkin():
    """Verarbeitet Scans von statischen Mitarbeiter-QR-Codes (IP-geschützt)"""
    if get_client_ip() not in ALLOWED_IPS:
        return "Zugriff verweigert: Nur vor Ort möglich.", 403

    m_id = request.args.get('id')
    if not m_id or "_" not in m_id:
        return "Ungültiger QR-Code-Inhalt.", 400

    parts = m_id.split('_')
    vname, nname = parts[0], parts[1]

    jetzt_berlin = datetime.now(BERLIN_TZ).replace(tzinfo=None)
    neuer_eintrag = CheckIn(vorname=vname, nachname=nname, datum=jetzt_berlin)
    db.session.add(neuer_eintrag)
    db.session.commit()

    return render_template('quick_success.html', name=f"{vname} {nname}")

@app.route('/get_qr_token')
def get_token_api():
    """API für Terminal-Updates"""
    if get_client_ip() in ALLOWED_IPS or session.get('logged_in'):
        return jsonify({"token": get_current_qr_token()})
    return jsonify({"error": "Unauthorized"}), 403

# --- ROUTEN: ADMIN & DASHBOARD ---

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
        combined = func.concat(CheckIn.vorname, ' ', CheckIn.nachname)
        query = query.filter(or_(CheckIn.vorname.ilike(f'%{search}%'), 
                                 CheckIn.nachname.ilike(f'%{search}%'),
                                 combined.ilike(f'%{search}%')))
    if date_val:
        query = query.filter(func.date(CheckIn.datum) == date_val)
        
    checkins = query.order_by(CheckIn.datum.desc()).all()
    res = make_response(render_template('dashboard.html', checkins=checkins, search=search, date=date_val))
    return prevent_cache(res)

@app.route('/admin/delete/<int:id>')
def delete_entry(id):
    if not session.get('logged_in'): return redirect(url_for('admin'))
    entry = CheckIn.query.get_or_404(id)
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('dashboard', search=request.args.get('search'), date=request.args.get('date')))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
