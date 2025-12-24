from flask import Flask, render_template, request, redirect, url_for, session, send_file
from datetime import datetime
import csv
import io

app = Flask(__name__)
app.secret_key = 'dein_sicheres_secret_key'  # unbedingt anpassen!

# Dummy-Daten für Check-Ins
checkins = []

# Startseite Check-In
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        vorname = request.form.get('vorname')
        nachname = request.form.get('nachname')
        buerotag_nachholen = request.form.get('buerotag_nachholen')
        datum = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        checkins.append({
            'Vorname': vorname,
            'Nachname': nachname,
            'Bürotag nachholen': buerotag_nachholen,
            'Datum': datum
        })
        return render_template('index.html', success=True)
    return render_template('index.html')

# Admin Login
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'deinpasswort':  # Passwort anpassen
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = 'Falscher Benutzername oder Passwort'
    return render_template('admin.html', error=error)

# Admin Dashboard
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('admin'))
    return render_template('dashboard.html', checkins=checkins)

# CSV Export nach Datum
@app.route('/admin/export/csv')
def export_csv():
    if not session.get('logged_in'):
        return redirect(url_for('admin'))

    si = io.StringIO()
    cw = csv.writer(si)
    # Header
    cw.writerow(['Vorname', 'Nachname', 'Bürotag nachholen', 'Datum'])
    # Daten
    for row in checkins:
        cw.writerow([row['Vorname'], row['Nachname'], row['Bürotag nachholen'], row['Datum']])

    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)
    si.close()

    return send_file(output, mimetype='text/csv', download_name='checkins.csv', as_attachment=True)

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
