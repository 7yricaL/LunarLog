import os
from flask import Flask, request, render_template, redirect, url_for, session
import sqlite3
from datetime import datetime, timedelta
import logging
import traceback

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')  # Use environment variable for secret key

if not app.debug:
    # In production mode, add log handler to sys.stderr.
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    app.logger.addHandler(stream_handler)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def format_name(name):
    return ' '.join(word.capitalize() for word in name.split())

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/select-date', methods=['POST'])
def select_date():
    name = request.form['name'].strip().lower()
    conn = get_db_connection()
    volunteer = conn.execute('SELECT * FROM volunteers WHERE LOWER(name) = ?', (name,)).fetchone()
    if volunteer is None:
        conn.close()
        return f"There is no record of volunteer '{request.form['name']}' in our database. Please double check your spelling or stop lying.", 404

    sessions = conn.execute('SELECT DISTINCT date FROM sessions WHERE volunteer_id = ?', (volunteer['id'],)).fetchall()
    conn.close()

    if not sessions:
        return f"There is no record of '{request.form['name']}' volunteering on any dates in our database. Please double check your spelling or stop lying.", 404
    
    return render_template('select_date.html', name=volunteer['name'], sessions=sessions)

@app.route('/get-certificate', methods=['POST'])
def get_certificate():
    name = request.form['name'].strip().lower()
    date = request.form['date'].strip()
    conn = get_db_connection()
    volunteer = conn.execute('SELECT * FROM volunteers WHERE LOWER(name) = ?', (name,)).fetchone()
    if volunteer is None:
        conn.close()
        return f"There is no record of volunteer '{request.form['name']}' in our database. Please double check your spelling or stop lying.", 404

    sessions = conn.execute('SELECT * FROM sessions WHERE volunteer_id = ? AND date = ?', (volunteer['id'], date)).fetchall()
    conn.close()
    
    if not sessions:
        return f"There is no record of '{request.form['name']}' volunteering during '{date}' in our database. Please double check the date or stop lying.", 404
    
    total_hours = 0
    for session in sessions:
        start_time = datetime.strptime(session['start_time'], '%I:%M %p')
        end_time = datetime.strptime(session['end_time'], '%I:%M %p')
        # Calculate difference in hours, considering crossing over midnight
        if end_time < start_time:
            end_time += timedelta(days=1)
        total_hours += (end_time - start_time).seconds / 3600
    
    total_hours = round(total_hours, 2)  # Round to 2 decimal places

    formatted_name = format_name(volunteer['name'])

    return render_template('certificate.html', name=formatted_name, date=date, hours=total_hours)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    try:
        if request.method == 'POST':
            passkey = request.form['passkey']
            if passkey == '12345':
                session['admin_logged_in'] = True
                return redirect(url_for('admin'))
            else:
                return render_template('admin_login.html', error='Invalid passkey')
        elif request.method == 'GET':
            if 'admin_logged_in' in session:
                conn = get_db_connection()
                volunteers = conn.execute('SELECT * FROM volunteers').fetchall()
                sessions = conn.execute('SELECT * FROM sessions').fetchall()
                current_sessions = conn.execute('''
                    SELECT current_sessions.id, volunteers.name, current_sessions.date, current_sessions.start_time
                    FROM current_sessions
                    JOIN volunteers ON current_sessions.volunteer_id = volunteers.id
                ''').fetchall()
                conn.close()
                return render_template('admin.html', volunteers=volunteers, sessions=sessions, current_sessions=current_sessions)
            else:
                return render_template('admin_login.html')
    except Exception as e:
        app.logger.error(f"Error on /admin route: {e}")
        app.logger.error(traceback.format_exc())
        return "Internal Server Error", 500

@app.route('/add-session')
def add_session_page():
    try:
        conn = get_db_connection()
        current_sessions = conn.execute('''
            SELECT current_sessions.id, volunteers.name, current_sessions.date, current_sessions.start_time
            FROM current_sessions
            JOIN volunteers ON current_sessions.volunteer_id = volunteers.id
        ''').fetchall()
        conn.close()
        return render_template('add_session.html', current_sessions=current_sessions)
    except Exception as e:
        app.logger.error(f"Error on /add-session page: {e}")
        app.logger.error(traceback.format_exc())
        return "Internal Server Error", 500

@app.route('/add-session', methods=['POST'])
def add_session():
    try:
        volunteer_name = request.form['volunteer_name'].strip().lower()
        date = request.form['date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        conn = get_db_connection()
        volunteer = conn.execute('SELECT id FROM volunteers WHERE LOWER(name) = ?', (volunteer_name,)).fetchone()
        if not volunteer:
            conn.execute('INSERT INTO volunteers (name) VALUES (?)', (volunteer_name,))
            conn.commit()
            volunteer = conn.execute('SELECT id FROM volunteers WHERE LOWER(name) = ?', (volunteer_name,)).fetchone()
        
        if end_time:
            conn.execute('INSERT INTO sessions (volunteer_id, date, start_time, end_time) VALUES (?, ?, ?, ?)', (volunteer['id'], date, start_time, end_time))
        else:
            conn.execute('INSERT INTO current_sessions (volunteer_id, date, start_time) VALUES (?, ?, ?)', (volunteer['id'], date, start_time))
        
        conn.commit()
        conn.close()
        return redirect(url_for('add_session_page'))
    except Exception as e:
        app.logger.error(f"Error in /add-session route: {e}")
        app.logger.error(traceback.format_exc())
        return "Internal Server Error", 500

@app.route('/complete-session', methods=['POST'])
def complete_session():
    try:
        session_id = request.form['session_id']
        end_time = request.form['end_time']
        conn = get_db_connection()
        current_session = conn.execute('SELECT * FROM current_sessions WHERE id = ?', (session_id,)).fetchone()
        if current_session:
            conn.execute('INSERT INTO sessions (volunteer_id, date, start_time, end_time) VALUES (?, ?, ?, ?)', 
                        (current_session['volunteer_id'], current_session['date'], current_session['start_time'], end_time))
            conn.execute('DELETE FROM current_sessions WHERE id = ?', (session_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('add_session_page'))
    except Exception as e:
        app.logger.error(f"Error in /complete-session route: {e}")
        app.logger.error(traceback.format_exc())
        return "Internal Server Error", 500

@app.route('/delete-session', methods=['POST'])
def delete_session():
    try:
        session_id = request.form['session_id']
        conn = get_db_connection()
        conn.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('admin'))
    except Exception as e:
        app.logger.error(f"Error in /delete-session route: {e}")
        app.logger.error(traceback.format_exc())
        return "Internal Server Error", 500

@app.route('/delete-current-session', methods=['POST'])
def delete_current_session():
    try:
        session_id = request.form['session_id']
        conn = get_db_connection()
        conn.execute('DELETE FROM current_sessions WHERE id = ?', (session_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('admin'))
    except Exception as e:
        app.logger.error(f"Error in /delete-current-session route: {e}")
        app.logger.error(traceback.format_exc())
        return "Internal Server Error", 500

@app.route('/delete-volunteer', methods=['POST'])
def delete_volunteer():
    try:
        volunteer_id = request.form['volunteer_id']
        conn = get_db_connection()
        conn.execute('DELETE FROM volunteers WHERE id = ?', (volunteer_id,))
        conn.execute('DELETE FROM sessions WHERE volunteer_id = ?', (volunteer_id,))
        conn.execute('DELETE FROM current_sessions WHERE volunteer_id = ?', (volunteer_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('admin'))
    except Exception as e:
        app.logger.error(f"Error in /delete-volunteer route: {e}")
        app.logger.error(traceback.format_exc())
        return "Internal Server Error", 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
