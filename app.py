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
QR_SECRET = os.environ.get('QR_SECRET', 'ein-sehr-geheimer-schluessel-789') # Ändern für Produktion!
app.secret_key = os.environ.get('SECRET_KEY', 'admin-session-geheimnis-123')

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2)
)

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
    datum = db.Column(db.DateTime)

# --- ADMIN DATEN ---
ADMIN_BENUTZER = 'admin'
ADMIN_PASSWORT_HASH = generate_password_hash('deinpasswort')

with app.app_context():
    db.create_all()

# --- HILFSFUNKTIONEN ---

def get_current_qr_token():
    """Erzeugt einen Token, der alle 30 Sekunden wechselt"""
    time_step = int(datetime.now().timestamp() / 30)
    hash_input = f"{QR_SECRET}{time_step}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:10]

def is_mobile():
    user_agent = request.headers.get('User-Agent', '').lower()
    mobile_keywords = ['android', 'iphone', 'ipad', 'iemobile', 'kindle', 'mobile']
    return any(keyword in user_agent for keyword in mobile_keywords)

def prevent_cache(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# --- ROUTEN ---

@app.route('/', methods=['GET', 'POST'])
def index():
    # 1. Mobile Check
    if not is_mobile():
        return render_template('mobile_only.html'), 403

    # 2. QR-Sicherheits-Token Validierung
    user_token = request.args.get('token')
    current_token = get_current_qr_token()
    
    # Letzten Token auch erlauben (Toleranz für langsame Handys)
    time_step_prev = int(datetime.now().timestamp() / 30) - 1
    prev_token = hashlib.sha256(f"{QR_SECRET}{time_step_prev}".encode()).hexdigest()[:10]

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

@app.route('/display')
def display_qr():
    """Seite für das Tablet vor Ort"""
    if session.get('logged_in') is not True:
        return redirect(url_for('admin'))
    return render_template('qr_display.html')

@app.route('/get_qr_token')
def get_token_api():
    """API für das automatische Update des QR-Codes"""
    return jsonify({"token": get_current_qr_token()})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('logged_in') is True: return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_BENUTZER and \
           check_password_hash(ADMIN_PASSWORT_HASH, request.form.get('password')):
            session.clear()
            session.permanent = True
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        error = 'Falsche Zugangsdaten.'
    return render_template('admin.html', error=error)

@app.route('/dashboard')
def dashboard():
    if session.get('logged_in') is not True: return redirect(url_for('admin'))
    
    search = request.args.get('search', '').strip()
    date_f = request.args.get('date', '')
    
    query = CheckIn.query
    if search:
        comb = func.concat(CheckIn.vorname, ' ', CheckIn.nachname)
        query = query.filter(or_(CheckIn.vorname.ilike(f'%{search}%'), 
                                 CheckIn.nachname.ilike(f'%{search}%'),
                                 comb.ilike(f'%{search}%')))
    if date_f:
        query = query.filter(func.date(CheckIn.datum) == date_f)
        
    checkins = query.order_by(CheckIn.datum.desc()).all()
    res = make_response(render_template('dashboard.html', checkins=checkins, search=search, date=date_f))
    return prevent_cache(res)

@app.route('/admin/export/csv')
def export_csv():
    if session.get('logged_in') is not True: return redirect(url_for('admin'))
    # ... (CSV Logik wie zuvor)
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';')
    cw.writerow(['Vorname', 'Nachname', 'Bürotag nachholen', 'Datum'])
    # Filterung wie im Dashboard anwenden...
    eintraege = CheckIn.query.all() # Vereinfacht für das Beispiel
    for r in eintraege:
        cw.writerow([r.vorname, r.nachname, r.buerotag_nachholen, r.datum.strftime('%d.%m.%Y %H:%M')])
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)
    return send_file(output, mimetype='text/csv', download_name='export.csv', as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
