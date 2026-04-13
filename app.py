import os
import re
import json
import requests
from functools import wraps
from datetime import datetime

from flask import (Flask, request, render_template, jsonify,
                   redirect, url_for, session, flash)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from db import (
    init_db, get_user_by_username, get_user_by_email,
    create_user, create_or_update_google_user, update_password,
    save_otp, verify_otp,
    store_chat, update_chat_questions,
    get_chat_history, get_dashboard_stats
)
from pdf_utils import extract_text_from_pdf_file
from ai_service import calculate_relevance_score, generate_questions, identify_skill_gaps
from mail_service import generate_otp, otp_expiry, send_otp_email

# ── App setup ────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
CORS(app)

UPLOAD_FOLDER = Config.UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Auth decorator ────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ── Helper: parse relevance score ────────────────────────────────────────────

def parse_score(text: str) -> int:
    """Extract score only from Relevance Score line - never returns >100."""
    if not text:
        return 0
    first_line = text.strip().split("\n")[0]
    m = re.search(r"(?:relevance\s+score\s*[:\-]?\s*)(\d+)", first_line, re.IGNORECASE)
    if m:
        return min(int(m.group(1)), 100)
    nums = re.findall(r"\b(\d{1,3})\b", first_line)
    for n in nums:
        if 0 <= int(n) <= 100:
            return int(n)
    return 0


# ══════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def landing():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = get_user_by_username(username)
        if user and user.get('password') and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['avatar_url'] = user.get('avatar_url', '')
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid username or password',
                               google_client_id=Config.GOOGLE_CLIENT_ID)

    return render_template('login.html', google_client_id=Config.GOOGLE_CLIENT_ID)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if password != confirm:
            return render_template('register.html', error='Passwords do not match')
        if len(password) < 8:
            return render_template('register.html', error='Password must be at least 8 characters')
        if get_user_by_username(username):
            return render_template('register.html', error='Username already taken')
        if email and get_user_by_email(email):
            return render_template('register.html', error='Email already registered')

        if create_user(username, email, generate_password_hash(password)):
            flash('Account created! Please log in.')
            return redirect(url_for('login'))
        return render_template('register.html', error='Registration failed. Try again.')

    return render_template('register.html')


@app.route('/google_login', methods=['POST'])
def google_login():
    """Verify Google ID token and log the user in."""
    data = request.get_json()
    credential = data.get('credential', '')

    # Verify token with Google
    resp = requests.get(
        f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}"
    )
    if resp.status_code != 200:
        return jsonify({"error": "Invalid Google token"}), 401

    info = resp.json()
    google_id  = info.get('sub')
    email      = info.get('email', '')
    name       = info.get('name', email.split('@')[0])
    avatar_url = info.get('picture', '')

    user = create_or_update_google_user(google_id, email, name, avatar_url)
    if not user:
        return jsonify({"error": "Could not create user"}), 500

    session['user_id']   = user['id']
    session['username']  = user['username']
    session['avatar_url'] = user.get('avatar_url', '')
    return jsonify({"redirect": url_for('index')})


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user  = get_user_by_email(email)
        if not user:
            return render_template('forgot_password.html',
                                   error='No account found with that email.')

        code    = generate_otp()
        expires = otp_expiry(minutes=10)
        save_otp(email, code, expires)
        sent = send_otp_email(email, code)

        if sent:
            session['reset_email'] = email
            return redirect(url_for('verify_otp_page'))
        return render_template('forgot_password.html',
                               error='Failed to send email. Check your mail config.')

    return render_template('forgot_password.html')


@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp_page():
    email = session.get('reset_email')
    if not email:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'verify':
            code = request.form.get('code', '').strip()
            if verify_otp(email, code):
                session['otp_verified'] = True
                return render_template('verify_otp.html', email=email,
                                       step='reset', success='Code verified! Set your new password.')
            return render_template('verify_otp.html', email=email,
                                   step='otp', error='Invalid or expired code.')

        if action == 'reset':
            if not session.get('otp_verified'):
                return redirect(url_for('verify_otp_page'))
            new_pw  = request.form.get('new_password', '')
            confirm = request.form.get('confirm_password', '')
            if new_pw != confirm:
                return render_template('verify_otp.html', email=email,
                                       step='reset', error='Passwords do not match.')
            if len(new_pw) < 8:
                return render_template('verify_otp.html', email=email,
                                       step='reset', error='Password must be at least 8 characters.')
            update_password(email, generate_password_hash(new_pw))
            session.pop('reset_email', None)
            session.pop('otp_verified', None)
            flash('Password reset successful! Please log in.')
            return redirect(url_for('login'))

    return render_template('verify_otp.html', email=email, step='otp')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/app')
@login_required
def index():
    return render_template('index.html',
                           username=session.get('username'),
                           avatar=session.get('avatar_url', ''))


@app.route('/dashboard')
@login_required
def dashboard():
    stats = get_dashboard_stats(session['user_id'])
    chats = get_chat_history(session['user_id'])
    return render_template('dashboard.html',
                           stats=stats, chats=chats,
                           username=session.get('username'),
                           avatar=session.get('avatar_url', ''))


@app.route('/history')
@login_required
def history():
    chats = get_chat_history(session['user_id'])
    return render_template('chat_history.html', chats=chats,
                           username=session.get('username'),
                           avatar=session.get('avatar_url', ''))


# ══════════════════════════════════════════════════════════════════════════════
# AI API ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/analyze', methods=['POST'])
@login_required
def analyze():
    """
    Combined endpoint: returns relevance score + skill gaps + questions in one request.
    Expects multipart form with jd_pdf and resume_pdf.
    """
    if 'jd_pdf' not in request.files or 'resume_pdf' not in request.files:
        return jsonify({"error": "Both jd_pdf and resume_pdf are required."}), 400

    jd_file     = request.files['jd_pdf']
    resume_file = request.files['resume_pdf']

    jd_text     = extract_text_from_pdf_file(jd_file)
    resume_text = extract_text_from_pdf_file(resume_file)

    relevance  = calculate_relevance_score(jd_text, resume_text)
    skill_gaps = identify_skill_gaps(jd_text, resume_text)
    questions  = generate_questions(jd_text, resume_text)

    score_val = parse_score(relevance)

    # Store in DB
    chat_id = store_chat(
        user_id        = session['user_id'],
        jd_filename    = jd_file.filename,
        resume_filename= resume_file.filename,
        relevance_score= relevance,
        skill_gaps     = skill_gaps,
        questions      = '\n'.join(questions)
    )

    return jsonify({
        "chat_id":    chat_id,
        "relevance":  relevance,
        "score":      score_val,
        "skill_gaps": skill_gaps,
        "questions":  questions,
        "jd_filename": jd_file.filename,
        "resume_filename": resume_file.filename
    })


# ── Legacy individual endpoints (kept for compatibility) ─────────────────────

@app.route('/get_relevance', methods=['POST'])
@login_required
def get_relevance():
    jd_file     = request.files.get('jd_pdf')
    resume_file = request.files.get('resume_pdf')
    if not jd_file or not resume_file:
        return jsonify({"error": "Both PDFs required."}), 400
    jd_text     = extract_text_from_pdf_file(jd_file)
    resume_text = extract_text_from_pdf_file(resume_file)
    relevance   = calculate_relevance_score(jd_text, resume_text)
    return jsonify({"relevance": relevance, "score": parse_score(relevance)})


@app.route('/get_questions', methods=['POST'])
@login_required
def get_questions():
    jd_file     = request.files.get('jd_pdf')
    resume_file = request.files.get('resume_pdf')
    if not jd_file or not resume_file:
        return jsonify({"error": "Both PDFs required."}), 400
    jd_text     = extract_text_from_pdf_file(jd_file)
    resume_text = extract_text_from_pdf_file(resume_file)
    questions   = generate_questions(jd_text, resume_text)
    return jsonify({"questions": questions})


@app.route('/get_skill_gaps', methods=['POST'])
@login_required
def get_skill_gaps():
    jd_file     = request.files.get('jd_pdf')
    resume_file = request.files.get('resume_pdf')
    if not jd_file or not resume_file:
        return jsonify({"error": "Both PDFs required."}), 400
    jd_text     = extract_text_from_pdf_file(jd_file)
    resume_text = extract_text_from_pdf_file(resume_file)
    gaps        = identify_skill_gaps(jd_text, resume_text)
    return jsonify({"skill_gaps": gaps})


# ── Audio upload (fix: actually saves the recording) ─────────────────────────

@app.route('/upload_audio', methods=['POST'])
@login_required
def upload_audio():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided."}), 400

    audio_file   = request.files['audio']
    question_idx = request.form.get('question_index', 'unknown')
    chat_id      = request.form.get('chat_id', 'session')

    # Build a descriptive filename
    username = session.get('username', 'user')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    ext = '.webm'
    filename = f"{username}_chat{chat_id}_q{question_idx}_{timestamp}{ext}"

    save_path = os.path.join(UPLOAD_FOLDER, filename)
    audio_file.save(save_path)

    return jsonify({"message": "Audio saved.", "filename": filename})


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
