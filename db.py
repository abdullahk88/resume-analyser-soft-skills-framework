import mysql.connector
from mysql.connector import Error
from config import Config


def get_db_connection():
    try:
        connection = mysql.connector.connect(**Config.MYSQL_CONFIG)
        return connection
    except Error as e:
        print(f"[DB] Connection error: {e}")
        return None


def init_db():
    """Create all required tables if they don't exist."""
    connection = get_db_connection()
    if not connection:
        print("[DB] Could not initialize: no connection.")
        return
    try:
        cursor = connection.cursor()

        # Users table (supports both local + Google login)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                username    VARCHAR(100) NOT NULL UNIQUE,
                email       VARCHAR(255) UNIQUE,
                password    VARCHAR(255),
                google_id   VARCHAR(255) UNIQUE,
                avatar_url  VARCHAR(500),
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # OTP / password-reset codes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS otp_codes (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                email      VARCHAR(255) NOT NULL,
                code       VARCHAR(10) NOT NULL,
                expires_at DATETIME NOT NULL,
                used       TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Chat / analysis history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id               INT AUTO_INCREMENT PRIMARY KEY,
                user_id          INT NOT NULL,
                jd_filename      VARCHAR(255),
                resume_filename  VARCHAR(255),
                relevance_score  TEXT,
                skill_gaps       TEXT,
                questions        TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Add skill_gaps column if it doesn't exist (migration helper)
        try:
            cursor.execute("ALTER TABLE chats ADD COLUMN skill_gaps TEXT AFTER relevance_score")
        except Error:
            pass  # column already exists

        connection.commit()
        print("[DB] Tables ready.")
    except Error as e:
        print(f"[DB] Init error: {e}")
    finally:
        cursor.close()
        connection.close()


# ── User helpers ────────────────────────────────────────────────────────────

def get_user_by_username(username):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cur.fetchone()
    finally:
        cur.close(); conn.close()


def get_user_by_email(email):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        return cur.fetchone()
    finally:
        cur.close(); conn.close()


def get_user_by_google_id(google_id):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
        return cur.fetchone()
    finally:
        cur.close(); conn.close()


def create_user(username, email, hashed_password):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
            (username, email, hashed_password)
        )
        conn.commit()
        return True
    except Error as e:
        print(f"[DB] create_user error: {e}")
        return False
    finally:
        cur.close(); conn.close()


def create_or_update_google_user(google_id, email, username, avatar_url):
    """Upsert a Google-authenticated user."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        # Check existing by google_id or email
        cur.execute("SELECT * FROM users WHERE google_id = %s OR email = %s", (google_id, email))
        user = cur.fetchone()
        if user:
            cur.execute("""
                UPDATE users SET google_id=%s, avatar_url=%s WHERE id=%s
            """, (google_id, avatar_url, user['id']))
            conn.commit()
            cur.execute("SELECT * FROM users WHERE id=%s", (user['id'],))
            return cur.fetchone()
        else:
            # Ensure unique username
            base = username
            suffix = 0
            while True:
                cur.execute("SELECT id FROM users WHERE username=%s", (username,))
                if not cur.fetchone():
                    break
                suffix += 1
                username = f"{base}{suffix}"
            cur.execute("""
                INSERT INTO users (username, email, google_id, avatar_url)
                VALUES (%s, %s, %s, %s)
            """, (username, email, google_id, avatar_url))
            conn.commit()
            cur.execute("SELECT * FROM users WHERE google_id=%s", (google_id,))
            return cur.fetchone()
    except Error as e:
        print(f"[DB] google_user error: {e}")
        return None
    finally:
        cur.close(); conn.close()


def update_password(email, hashed_password):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET password=%s WHERE email=%s", (hashed_password, email))
        conn.commit()
        return True
    finally:
        cur.close(); conn.close()


# ── OTP helpers ─────────────────────────────────────────────────────────────

def save_otp(email, code, expires_at):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        # Invalidate previous codes
        cur.execute("UPDATE otp_codes SET used=1 WHERE email=%s", (email,))
        cur.execute(
            "INSERT INTO otp_codes (email, code, expires_at) VALUES (%s, %s, %s)",
            (email, code, expires_at)
        )
        conn.commit()
        return True
    finally:
        cur.close(); conn.close()


def verify_otp(email, code):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT * FROM otp_codes
            WHERE email=%s AND code=%s AND used=0 AND expires_at > NOW()
            ORDER BY created_at DESC LIMIT 1
        """, (email, code))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE otp_codes SET used=1 WHERE id=%s", (row['id'],))
            conn.commit()
            return True
        return False
    finally:
        cur.close(); conn.close()


# ── Chat history helpers ─────────────────────────────────────────────────────

def store_chat(user_id, jd_filename, resume_filename, relevance_score, skill_gaps, questions):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO chats (user_id, jd_filename, resume_filename, relevance_score, skill_gaps, questions)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, jd_filename, resume_filename, relevance_score, skill_gaps, questions))
        conn.commit()
        return cur.lastrowid
    except Error as e:
        print(f"[DB] store_chat error: {e}")
        return None
    finally:
        cur.close(); conn.close()


def update_chat_questions(chat_id, questions_text):
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("UPDATE chats SET questions=%s WHERE id=%s", (questions_text, chat_id))
        conn.commit()
    finally:
        cur.close(); conn.close()


def get_chat_history(user_id):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT * FROM chats WHERE user_id=%s ORDER BY created_at DESC
        """, (user_id,))
        return cur.fetchall()
    finally:
        cur.close(); conn.close()


def get_dashboard_stats(user_id):
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT COUNT(*) as total FROM chats WHERE user_id=%s", (user_id,))
        total = cur.fetchone()['total']

        # Average score
        cur.execute("""
            SELECT relevance_score FROM chats WHERE user_id=%s
        """, (user_id,))
        rows = cur.fetchall()
        scores = []
        for r in rows:
            import re
            m = re.search(r'(\d+)', r['relevance_score'] or '')
            if m:
                scores.append(int(m.group(1)))
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        best = max(scores) if scores else 0

        return {'total_analyses': total, 'avg_score': avg, 'best_score': best}
    finally:
        cur.close(); conn.close()
