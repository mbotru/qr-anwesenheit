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
from werkzeug.utils import secure_filename

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

# Datenbank-Anbindung (Postgres für Render oder lokal SQLite)
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

# --- ADMIN LOGIN ---
ADMIN_BENUTZER = 'admin'
ADMIN_PASSWORT_HASH = generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'deinpasswort'))

# --- HILFSFUNKTIONEN ---
def get_current_qr_token():
    time_step = int(datetime.now().timestamp() / 30)
    return hashlib.sha256(f"{QR_SECRET}{time_step}".encode()).hexdigest()[:10]

def is_mobile():
    ua = request.headers.get('User-Agent', '').lower()
    return any(k in ua for k in ['android', 'iphone', 'ipad', 'mobile'])

# --- ROUTEN: FRONTEND & TERMINAL ---

@app.route('/')
def root_redirect():
    return redirect(url_for('display_qr'))

@app.route('/display')
def display_qr():
    return render_template('qr_display.html')

@app.route('/get_qr_token')
def get_token_api():
    token = get_current_qr_token()
    qr_url = url_for('checkin_page', token=token, _external=True)
    return jsonify({"status": "success", "qr_string": qr_url})

@app.route('/checkin', methods=['GET', 'POST'])
def checkin_page():
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

# --- ROUTEN: ADMIN & DATEN-MANAGEMENT ---

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

@app.route('/admin/upload_soll', methods=['POST'])
def upload_soll():
    if not session.get('logged_in'): return redirect(url_for('admin'))
    file = request.files.get('file')
    if file and file.filename.endswith('.csv'):
        file.save(SOLL_DATEI_PFAD)
        return redirect(url_for('dashboard'))
    return "Fehler: Nur CSV erlaubt", 400

@app.route('/export_csv')
def export_csv():
    if not session.get('logged_in'): return redirect(url_for('admin'))
    
    # 1. Soll-Statistik laden
    soll_statistik, mitarbeiter_liste = {}, []
    if os.path.exists(SOLL_DATEI_PFAD):
        with open(SOLL_DATEI_PFAD, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                n, v = row['Nachname'].strip().lower(), row['Vorname'].strip().lower()
                soll_statistik[(n, v)] = int(row.get('Soll', 0))
                mitarbeiter_liste.append({'n': n, 'v': v})

    # 2. Ist-Daten gruppieren
    ist_stats = {}
    for c in CheckIn.query.all():
        if c.datum:
            jahr, kw, _ = c.datum.isocalendar()
            key = (c.nachname.strip().lower(), c.vorname.strip().lower(), kw, jahr)
            ist_stats[key] = ist_stats.get(key, 0) + 1

    # 3. Zeitraum (letzte 8 Wochen)
    heute = datetime.now(BERLIN_TZ)
    zeitraum = []
    for i in range(8):
        d = heute - timedelta(weeks=i)
        j, k, _ = d.isocalendar()
        if (j, k) not in zeitraum: zeitraum.append((j, k))

    # 4. CSV generieren
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';')
    cw.writerow(['Jahr', 'KW', 'Nachname', 'Vorname', 'Ist', 'Soll', 'Differenz', 'Status'])
    
    for j, k in zeitraum:
        for m in mitarbeiter_liste:
            ist = ist_stats.get((m['n'], m['v'], k, j), 0)
            soll = soll_statistik.get((m['n'], m['v']), 0)
            diff = ist - soll
            status = "Erfüllt" if diff >= 0 else ("Kein Scan" if ist == 0 else f"Fehlt: {abs(diff)}")
            cw.writerow([j, f"KW {k}", m['n'].capitalize(), m['v'].capitalize(), ist, soll, diff, status])
    
    response = make_response("\ufeff" + si.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=präsenz_bericht_{heute.strftime('%Y%m%d')}.csv"
    response.headers["Content-type"] = "text/csv; charset=utf-8"
    return response

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
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
