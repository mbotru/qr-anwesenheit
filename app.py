import io
import csv
import os
import hashlib
import uuid
import time
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
SOLL_DATEI_PFAD = os.path.join(os.path.dirname(__file__), 'soll_tage.csv')

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

# --- MODELL ---
class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vorname = db.Column(db.String(100), nullable=False)
    nachname = db.Column(db.String(100), nullable=False)
    buerotag_nachholen = db.Column(db.String(20), default="Nein")
    datum = db.Column(db.DateTime)

with app.app_context():
    db.create_all()

ADMIN_BENUTZER = 'admin'
ADMIN_PASSWORT_HASH = generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'deinpasswort'))

# --- HILFSFUNKTIONEN ---
def get_current_qr_token():
    time_step = int(datetime.now().timestamp() / 30)
    return hashlib.sha256(f"{QR_SECRET}{time_step}".encode()).hexdigest()[:10]

def is_mobile():
    ua = request.headers.get('User-Agent', '').lower()
    return any(k in ua for k in ['android', 'iphone', 'ipad', 'mobile'])

# --- ROUTEN ---

@app.route('/')
def root_redirect():
    return redirect(url_for('display_qr'))

@app.route('/display')
def display_qr():
    return render_template('qr_display.html')

@app.route('/get_qr_token')
def get_token_api():
    token = get_current_qr_token()
    qr_url = url_for('index', token=token, _external=True)
    return jsonify({"status": "success", "qr_string": qr_url})

@app.route('/checkin', methods=['GET', 'POST'])
def index():
    if not is_mobile():
        return render_template('mobile_only.html'), 403
    user_token = request.args.get('token')
    current_token = get_current_qr_token()
    prev_step = int(datetime.now().timestamp() / 30) - 1
    prev_token = hashlib.sha256(f"{QR_SECRET}{prev_step}".encode()).hexdigest()[:10]

    if user_token not in [current_token, prev_token]:
        return render_template('expired.html'), 403

    if request.method == 'POST':
        jetzt_berlin = datetime.now(BERLIN_TZ).replace(tzinfo=None)
        db.session.add(CheckIn(
            vorname=request.form.get('vorname'),
            nachname=request.form.get('nachname'),
            buerotag_nachholen=request.form.get('buerotag_nachholen', 'Nein'),
            datum=jetzt_berlin
        ))
        db.session.commit()
        return render_template('index.html', success=True, token=user_token)
    return render_template('index.html', token=user_token)

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
    
    jetzt = datetime.now(BERLIN_TZ)
    heute_datum = jetzt.date()
    
    anzahl_heute = CheckIn.query.filter(func.date(CheckIn.datum) == heute_datum).count()
    nachholen_anzahl = CheckIn.query.filter(func.date(CheckIn.datum) == heute_datum, CheckIn.buerotag_nachholen == 'Ja').count()
    letzter = CheckIn.query.order_by(CheckIn.datum.desc()).first()
    letzter_name = f"{letzter.vorname} {letzter.nachname}" if letzter else "-"

    search = request.args.get('search', '').strip()
    date_val = request.args.get('date', '')
    query = CheckIn.query
    if search:
        query = query.filter(or_(CheckIn.vorname.ilike(f'%{search}%'), CheckIn.nachname.ilike(f'%{search}%')))
    if date_val:
        query = query.filter(func.date(CheckIn.datum) == date_val)
    checkins = query.order_by(CheckIn.datum.desc()).all()
    
    return render_template('dashboard.html', checkins=checkins, search=search, date=date_val,
                           anzahl_heute=anzahl_heute, nachholen_anzahl=nachholen_anzahl, letzter_name=letzter_name)

@app.route('/admin/upload_soll', methods=['POST'])
def upload_soll():
    if not session.get('logged_in'): return redirect(url_for('admin'))
    file = request.files.get('file')
    if file and file.filename.endswith('.csv'):
        file.save(SOLL_DATEI_PFAD)
    return redirect(url_for('dashboard'))

@app.route('/export_csv')
def export_csv():
    if not session.get('logged_in'): return redirect(url_for('admin'))
    
    soll_stats = {}
    m_liste = []
    if os.path.exists(SOLL_DATEI_PFAD):
        with open(SOLL_DATEI_PFAD, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                k = (row['Nachname'].strip().lower(), row['Vorname'].strip().lower())
                soll_stats[k] = int(row.get('Soll', 0))
                m_liste.append(k)

    ist_stats = {}
    for c in CheckIn.query.all():
        j, kw, _ = c.datum.isocalendar()
        k = (c.nachname.strip().lower(), c.vorname.strip().lower(), kw, j)
        ist_stats[k] = ist_stats.get(k, 0) + 1

    heute = datetime.now(BERLIN_TZ)
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';')
    cw.writerow(['Jahr', 'KW', 'Nachname', 'Vorname', 'Ist', 'Soll', 'Diff', 'Status'])
    
    for i in range(8):
        d = heute - timedelta(weeks=i)
        j, kw, _ = d.isocalendar()
        for (nn, vn) in m_liste:
            ist = ist_stats.get((nn, vn, kw, j), 0)
            soll = soll_stats.get((nn, vn), 0)
