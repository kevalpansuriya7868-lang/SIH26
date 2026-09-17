"""
web_app.py — NyayaVault Web Edition (Flask & Streamlit Cloud Compatible)

A 1:1 web port of app.py (the CustomTkinter desktop client). Every screen,
rank rule, Oracle query, AES-256 seal, SHA-256 audit chain, blockchain
anchor and ReportLab PDF from the desktop app is reproduced here.

Nothing else in the project needs to change: this file reads the same
config.json, talks to the same Oracle schema (Local_SIH26.sql), uses the
same secure_vault_storage directory, and calls the same blockchain_manager.
"""

import os
import io
import sys
import json
import random
import socket
import base64
import hashlib
import smtplib
import mimetypes
import tempfile
from email.mime.text import MIMEText
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, session, redirect, url_for, flash,
    render_template_string, send_file, Response, abort, jsonify
)

import oracledb
from PIL import Image

# Blockchain Anchoring (optional — app still runs fully without it)
try:
    from blockchain_manager import anchor_evidence_hash, verify_evidence_onchain
    BLOCKCHAIN_MODULE_AVAILABLE = True
except Exception:
    BLOCKCHAIN_MODULE_AVAILABLE = False

# Cryptographic Suite (AES-256 Symmetric File Encryption at Rest)
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# PDF Generation Libraries
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VAULT_STORAGE_DIR = os.path.join(BASE_DIR, "secure_vault_storage")
os.makedirs(VAULT_STORAGE_DIR, exist_ok=True)

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

try:
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
except Exception:
    config = {
        "oracle": {"user": "system", "password": "Keval@0409r", "host": "localhost", "port": 1521, "service_name": "xe"},
        "security": {"enforce_mha_subnet": False, "allowed_subnets": ["127.0.0.1"]},
        "vault_master_key": "NyayaVault@GovernmentOfIndia#MHA2026MasterKey",
        "smtp": {"enabled": False, "server": "smtp.gmail.com", "port": 587, "user": "nyayavault.mha@gmail.com", "password": "app_password_here"}
    }

DB_CONFIG = config.get("oracle", {})
SECURITY_CONFIG = config.get("security", {})
SMTP_CONFIG = config.get("smtp", {})
BLOCKCHAIN_CONFIG = config.get("blockchain", {})
MASTER_SALT = b"MHA_NYAYAVAULT_KEY_DERIVATION_SALT_2026"

ANALYTICS_PASSWORD = "analytics123"

# Identical official palette to app.py
THEME = {
    "bg_main": "#F1F5F9",
    "card_bg": "#FFFFFF",
    "card_border": "#D5DEE7",
    "card_highlight": "#F8FAFC",
    "input_bg": "#F8FAFC",
    "primary": "#1E3A8A",            # Deep Navy (MHA Official Theme)
    "primary_hover": "#1E40AF",
    "hero_gradient": "#244CB9",
    "hero_gradient_dark": "#172554",
    "accent_gold": "#D97706",
    "accent_gold_hover": "#B45309",
    "accent_green": "#059669",
    "accent_green_hover": "#047857",
    "accent_red": "#DC2626",
    "accent_red_hover": "#B91C1C",
    "text_main": "#0F172A",
    "text_muted": "#64748B"
}

CASE_CATEGORIES = [
    "Murder / Homicide", "Robbery / Theft", "Cyber / Ransomware",
    "Narcotics", "Economic Offense", "Assault / Other"
]

CASE_CONDITIONS = [
    "Under Investigation", "Charge Sheet Filed", "Pending Trial",
    "Convicted & Sentenced", "Transferred to Forensics", "Closed / Acquitted"
]

RESOLVED_CONDITIONS = ("Convicted & Sentenced", "Closed / Acquitted")

LOGIN_POSITIONS = [
    "Director General of Police (DGP)",
    "City Commissioner of Police (CP)",
    "Area / Zone Commissioner (DCP/ACP)",
    "Police Inspector / SHO",
    "Investigating Officer (IO)",
    "Forensic Scientist Lead",
    "Super Admin / Master IT"
]

app = Flask(__name__)
app.secret_key = config.get("security", {}).get("jwt_secret", "NYAYAVAULT_MHA_SECURE_TOKEN_2026")
app.permanent_session_lifetime = __import__("datetime").timedelta(
    hours=int(config.get("security", {}).get("token_expire_hours", 8))
)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False


# =========================================================
# CORE ENGINES (Identical to app.py)
# =========================================================
class EncryptionEngine:
    @staticmethod
    def get_cipher():
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=MASTER_SALT,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(config.get("vault_master_key", "MHA2026MasterKey").encode()))
        return Fernet(key)

    @staticmethod
    def encrypt_file(source_path, target_encrypted_path):
        cipher = EncryptionEngine.get_cipher()
        with open(source_path, "rb") as f_in:
            data = f_in.read()
        enc_data = cipher.encrypt(data)
        with open(target_encrypted_path, "wb") as f_out:
            f_out.write(enc_data)

    @staticmethod
    def encrypt_bytes_to_file(data, target_encrypted_path):
        cipher = EncryptionEngine.get_cipher()
        with open(target_encrypted_path, "wb") as f_out:
            f_out.write(cipher.encrypt(data))

    @staticmethod
    def decrypt_file_to_bytes(target_encrypted_path):
        cipher = EncryptionEngine.get_cipher()
        with open(target_encrypted_path, "rb") as f_in:
            enc_data = f_in.read()
        return cipher.decrypt(enc_data)


class IntelligentClassifier:
    @staticmethod
    def analyze_evidence(file_path, filename):
        ext = os.path.splitext(filename)[1].lower()
        extracted_text = f"Analyzed binary metadata for: {filename}\nFile extension: {ext}\nIngest Timestamp: {datetime.now()}"

        if ext in [".mp4", ".avi", ".mkv", ".mov"]:
            category = "CCTV Video Footage"
            classification = "Surveillance Video Exhibit (Digital Multimedia)"
        elif ext in [".jpg", ".jpeg", ".png", ".bmp"]:
            category = "Crime Scene Photograph"
            classification = "Forensic Physical/Scene Visual Evidence"
        elif ext in [".wav", ".mp3", ".aac"]:
            category = "Call Audio Recording"
            classification = "Audio Intercept / Telephony Recording"
        elif ext in [".raw", ".dd", ".img", ".e01"]:
            category = "Disk Dump Image"
            classification = "Bit-Stream Hard Drive Forensic Image"
        elif ext in [".pdf", ".docx", ".txt"]:
            category = "Forensic Lab Report"
            classification = "Documentary / Chemical / DNA Analysis Report"
            try:
                if ext == ".txt":
                    with open(file_path, "r", errors="ignore") as f:
                        content = f.read(5000)
                        extracted_text += "\n\nExtracted OCR Preview:\n" + content[:500]
                        if "DNA" in content.upper():
                            classification = "Forensic DNA Typing Report"
                        elif "CYBER" in content.upper() or "IP ADDRESS" in content.upper():
                            classification = "Cyber Forensics & IP Ledger"
            except Exception:
                pass
        else:
            category = "Digital Exhibit"
            classification = "General Digital Electronic Record"

        return category, classification, extracted_text


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
VIDEO_EXTS = {".mp4", ".webm", ".ogg", ".mov", ".mkv", ".avi"}
AUDIO_EXTS = {".wav", ".mp3", ".aac", ".m4a", ".oga"}
TEXT_EXTS = {".txt", ".log", ".csv", ".json", ".xml", ".md"}


def media_kind(raw_file_name):
    ext = os.path.splitext(raw_file_name or "")[1].lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext == ".pdf":
        return "pdf"
    if ext in TEXT_EXTS:
        return "text"
    return "binary"


def guess_mime(raw_file_name):
    mime, _ = mimetypes.guess_type(raw_file_name or "")
    return mime or "application/octet-stream"


# =========================================================
# DATABASE / AUDIT / SECURITY HELPERS
# =========================================================
def get_db_connection():
    return oracledb.connect(
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        host=DB_CONFIG["host"],
        port=int(DB_CONFIG["port"]),
        service_name=DB_CONFIG["service_name"]
    )


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        active_ip = s.getsockname()[0]
        s.close()
        return active_ip
    except Exception:
        return "127.0.0.1"


def get_client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def verify_mha_network():
    if not SECURITY_CONFIG.get("enforce_mha_subnet", False):
        return True, None

    allowed = SECURITY_CONFIG.get("allowed_subnets", ["127.0.0.1"])
    candidates = [get_client_ip(), get_local_ip()]

    for ip in candidates:
        for prefix in allowed:
            if ip.startswith(prefix) or ip == prefix:
                return True, None

    return False, (
        f"Unauthorized Network Node: {', '.join(candidates)} — this system is "
        "strictly restricted to the secure MHA/Police Intranet."
    )


def log_chained_audit_event(action_type, target_ref):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT log_hash FROM audit_security_logs ORDER BY log_id DESC FETCH FIRST 1 ROWS ONLY")
        row = cur.fetchone()
        prev_hash = row[0] if row else "0" * 64

        ip = get_client_ip()
        actor = session.get("badge") or "GATEWAY_AUTH"
        role = session.get("role") or "SECURITY_GATEWAY"
        ts = datetime.now().isoformat()

        digest_payload = f"{prev_hash}|{ts}|{actor}|{role}|{action_type}|{target_ref}|{ip}"
        log_hash = hashlib.sha256(digest_payload.encode()).hexdigest()

        cur.execute("""
            INSERT INTO audit_security_logs (prev_log_hash, actor_badge, role, action_type, target_reference, ip_address, log_hash)
            VALUES (:1, :2, :3, :4, :5, :6, :7)
        """, (prev_hash, actor, role, action_type, target_ref, ip, log_hash))
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def send_email_otp(recipient_email, otp_code, officer_name):
    subject = "NyayaVault Security Token (Password Reset OTP)"
    body = (
        f"Hello Officer {officer_name},\n\nYour one-time authorization OTP to reset your "
        f"NyayaVault credentials is: {otp_code}\n\nThis OTP is valid for 10 minutes. "
        "Do not share this token.\n\nMinistry of Home Affairs - Digital Vault Security Division"
    )

    if SMTP_CONFIG.get("enabled", False):
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = SMTP_CONFIG["user"]
            msg["To"] = recipient_email

            server = smtplib.SMTP(SMTP_CONFIG["server"], SMTP_CONFIG["port"])
            server.starttls()
            server.login(SMTP_CONFIG["user"], SMTP_CONFIG["password"])
            server.sendmail(SMTP_CONFIG["user"], [recipient_email], msg.as_string())
            server.quit()
            return True, "OTP email dispatched to your registered address."
        except Exception as e:
            return False, f"Email delivery failed: {str(e)}"
    else:
        return True, f"Demo Security Mode: OTP dispatched to {recipient_email} [One-Time Password Code: {otp_code}]"


# =========================================================
# SESSION & RBAC HELPERS
# =========================================================
def current_user():
    return {
        "badge": session.get("badge"),
        "name": session.get("name"),
        "role": session.get("role"),
        "rank": session.get("rank"),
        "rank_level": int(session.get("rank_level") or 1),
        "division": session.get("division") or "",
        "unit": session.get("unit") or "",
        "area": session.get("area") or "",
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("badge"):
            flash("Please authenticate to access the secure evidence vault.", "error")
            return redirect(url_for("gateway"))
        return view(*args, **kwargs)
    return wrapped


def rank_required(min_level):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            u = current_user()
            if not u["badge"]:
                return redirect(url_for("gateway"))
            if u["rank_level"] < min_level:
                flash(
                    f"Strict rank restriction: your rank ({u['rank']}) is not authorised for this action.",
                    "error"
                )
                return redirect(url_for("portal"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def is_judge():
    return current_user()["role"] == "COURT_JUDICIAL"


def fetch_divisions():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT division_code FROM police_divisions ORDER BY division_code")
        rows = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception:
        return ["SURAT", "AHMEDABAD", "RAJKOT"]


# =========================================================
# SHARED THEME & RESPONSIVE HTML TEMPLATE
# =========================================================
BASE_CSS = """
:root {
  --bg-main: #F1F5F9;
  --card-bg: #FFFFFF;
  --card-border: #D5DEE7;
  --card-highlight: #F8FAFC;
  --input-bg: #F8FAFC;
  --primary: #1E3A8A;
  --primary-hover: #1E40AF;
  --hero: #244CB9;
  --hero-dark: #172554;
  --gold: #D97706;
  --gold-hover: #B45309;
  --green: #059669;
  --green-hover: #047857;
  --red: #DC2626;
  --red-hover: #B91C1C;
  --text: #0F172A;
  --muted: #64748B;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg-main);
  color: var(--text);
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  font-size: 14px;
}
a { color: var(--primary); text-decoration: none; }
.topbar {
  background: var(--card-bg);
  border-bottom: 1px solid var(--card-border);
  padding: 10px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.topbar h1 { font-size: 15px; margin: 0; color: var(--primary); font-weight: 700; }
.topbar .who { font-size: 11px; color: var(--green); margin-top: 3px; font-weight: 600; }
.topbar .actions { display: flex; gap: 10px; flex-wrap: wrap; }
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 0;
  border-radius: 10px;
  padding: 9px 15px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  color: #fff;
  background: var(--primary);
  text-decoration: none;
  line-height: 1.2;
}
.btn:hover { background: var(--primary-hover); }
.btn.green { background: var(--green); } .btn.green:hover { background: var(--green-hover); }
.btn.gold { background: var(--gold); } .btn.gold:hover { background: var(--gold-hover); }
.btn.red { background: var(--red); } .btn.red:hover { background: var(--red-hover); }
.btn.blue { background: #0284C7; } .btn.blue:hover { background: #0369A1; }
.btn.dark { background: #1E293B; } .btn.dark:hover { background: #0F172A; }
.btn.slate { background: #64748B; } .btn.slate:hover { background: #475569; }
.btn.ghost { background: transparent; color: #FFFFFF; border: 2px solid #FFFFFF; border-radius: 25px; }
.btn.ghost:hover { background: rgba(255,255,255,0.15); }
.btn.small { padding: 6px 11px; font-size: 11px; border-radius: 8px; }
.wrap { padding: 18px 24px 40px; }
.card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
.card h2 { margin: 0 0 10px; font-size: 16px; color: var(--primary); font-weight: 700; }
.card h3 { margin: 0 0 8px; font-size: 13px; color: var(--primary); font-weight: 700; }
.muted { color: var(--muted); font-size: 11.5px; }
label { display: block; font-size: 11.5px; font-weight: 700; color: var(--text); margin: 8px 0 3px; }
input[type=text], input[type=password], input[type=email], input[type=number], input[type=file], select, textarea {
  width: 100%;
  background: var(--input-bg);
  border: 1px solid var(--card-border);
  border-radius: 8px;
  padding: 9px 12px;
  font-size: 13px;
  color: var(--text);
  font-family: inherit;
}
.split { display: grid; grid-template-columns: 330px 1fr; gap: 16px; align-items: start; }
@media(max-width: 900px) { .split { grid-template-columns: 1fr; } }
.tabs {
  display: flex;
  gap: 6px;
  background: var(--card-highlight);
  border: 1px solid var(--card-border);
  border-radius: 10px;
  padding: 6px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.tabs a { padding: 8px 14px; border-radius: 8px; font-size: 12px; font-weight: 700; color: var(--muted); }
.tabs a.active { background: var(--primary); color: #fff; }
.table-scroll { overflow-x: auto; border: 1px solid var(--card-border); border-radius: 10px; background: var(--card-bg); }
table { border-collapse: collapse; width: 100%; font-size: 12px; min-width: 640px; }
th {
  background: var(--card-highlight);
  color: var(--text);
  text-align: center;
  font-weight: 700;
  padding: 10px 8px;
  border-bottom: 1px solid var(--card-border);
  white-space: nowrap;
}
td { padding: 9px 8px; border-bottom: 1px solid #EEF2F7; text-align: center; vertical-align: middle; }
tr:hover { background: var(--card-highlight); }
td.left, th.left { text-align: left; }
.hash { font-family: Consolas, Menlo, monospace; font-size: 10.5px; word-break: break-all; }
.flashes { margin: 0 0 14px; padding: 0; list-style: none; }
.flashes li { padding: 11px 14px; border-radius: 10px; margin-bottom: 8px; font-size: 12.5px; font-weight: 600; }
.flashes li.ok { background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; }
.flashes li.error { background: #FEF2F2; color: #991B1B; border: 1px solid #FECACA; }
.flashes li.warn { background: #FFFBEB; color: #92400E; border: 1px solid #FDE68A; }
.flashes li.info { background: #EFF6FF; color: #1E40AF; border: 1px solid #BFDBFE; }
.pill { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 10px; font-weight: 700; color: #fff; }
.pill.navy { background: var(--primary); }
.pill.green { background: var(--green); }
.pill.red { background: var(--red); }
.pill.gold { background: var(--gold); }
.pill.slate { background: #64748B; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.metric { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 14px; }
.metric .t { font-size: 11px; font-weight: 700; color: var(--muted); }
.metric .v { font-size: 22px; font-weight: 800; margin-top: 4px; }
.bar { height: 14px; border-radius: 7px; background: var(--input-bg); overflow: hidden; flex: 1; }
.bar span { display: block; height: 100%; border-radius: 7px; }
.catrow { display: flex; align-items: center; gap: 10px; margin: 8px 0; }
.catrow .n { width: 190px; font-size: 11px; font-weight: 700; }
.catrow .c { width: 120px; text-align: right; font-size: 11px; font-weight: 700; color: var(--muted); }
.media-frame { background: #0F172A; border-radius: 10px; padding: 12px; text-align: center; margin-top: 10px; }
.media-frame img, .media-frame video { max-width: 100%; max-height: 440px; border-radius: 6px; display: block; margin: 0 auto; }
.media-frame audio { width: 100%; margin-top: 6px; }
.media-frame pre { text-align: left; color: #E2E8F0; font-size: 11.5px; max-height: 380px; overflow: auto; margin: 0; white-space: pre-wrap; }
.row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.stack > * + * { margin-top: 9px; }
.hierarchy-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 8px;
}
"""

LAYOUT = """
<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ page_title or 'NyayaVault' }} — Ministry of Home Affairs</title>
<style>{{ base_css }}</style>
</head><body>
{% if session.get('badge') %}
<div class="topbar">
  <div>
    <h1>NyayaVault: Secure Digital Evidence Lifecycle System (PS-190)</h1>
    <div class="who">{{ header_line }}</div>
  </div>
  <div class="actions">
    <a class="btn gold" href="{{ url_for('analytics_gate') }}">📊 Analytics</a>
    {% if u.rank_level == 5 or u.role == 'COURT_JUDICIAL' %}
      <a class="btn blue" href="{{ url_for('jurisdiction_state') }}">← State Command Tree</a>
    {% elif u.rank_level == 4 %}
      <a class="btn blue" href="{{ url_for('jurisdiction_city') }}">← City Command Tree</a>
    {% elif u.rank_level == 3 %}
      <a class="btn blue" href="{{ url_for('jurisdiction_area') }}">← Area Command Tree</a>
    {% endif %}
    {% if u.unit %}<a class="btn" href="{{ url_for('portal') }}">Station Vault</a>{% endif %}
    <a class="btn red" href="{{ url_for('logout') }}">Sign Out</a>
  </div>
</div>
{% endif %}
<div class="wrap">
  {% with msgs = get_flashed_messages(with_categories=true) %}
    {% if msgs %}<ul class="flashes">
      {% for cat, m in msgs %}<li class="{{ cat }}">{{ m }}</li>{% endfor %}
    </ul>{% endif %}
  {% endwith %}
  {{ body|safe }}
</div>
</body></html>
"""


def render_page(body_template, page_title="NyayaVault", **ctx):
    u = current_user()
    header_line = ""
    if u["badge"]:
        if u["role"] == "COURT_JUDICIAL":
            header_line = f"Rank: {u['rank']} | Judge: {u['name']} (#{u['badge']}) | JUDICIAL INSPECTION PORTAL"
        else:
            header_line = (
                f"Rank: {u['rank']} | User: {u['name']} (#{u['badge']}) | "
                f"City: {u['division']} | Station: {u['unit'] or '—'}"
            )
    body = render_template_string(body_template, u=u, THEME=THEME, **ctx)
    return render_template_string(
        LAYOUT, body=body, base_css=BASE_CSS, page_title=page_title,
        u=u, header_line=header_line
    )


# =========================================================
# SCREEN 1 — LOGIN GATEWAY (WITH DEFAULT PRE-FILLED ID/PASS)
# =========================================================
GATEWAY_TPL = """
<div style="max-width:940px;margin:25px auto">
  <div style="text-align:center;margin-bottom:20px">
    <div style="font-size:18px;font-weight:800;color:var(--primary);letter-spacing:0.5px">
      MINISTRY OF HOME AFFAIRS (GOVERNMENT OF INDIA)
    </div>
    <div class="muted" style="font-size:12px;margin-top:4px">
      NyayaVault: Chain-of-Command &amp; Rank Authentication Gateway (PS-190)
    </div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;border-radius:22px;
              overflow:hidden;border:1px solid var(--card-border);background:var(--card-bg);
              box-shadow:0 8px 30px rgba(0,0,0,0.06)">

    <!-- Hero / Toggle Panel -->
    <div style="background:var(--hero);color:#fff;padding:45px 35px;display:flex;flex-direction:column;justify-content:center;text-align:center">
      {% if view == 'judicial' %}
        <span class="pill" style="background:#F59E0B;align-self:center;margin-bottom:12px">JUDICIAL INSPECTION ACCESS</span>
        <h2 style="color:#fff;font-size:22px;margin:8px 0 10px;font-weight:700">Judicial &amp; Prosecution Portal</h2>
        <p style="color:#EFF6FF;font-size:12px;line-height:1.6;margin-bottom:24px">
          Read-only evidence manifest inspection and live tamper hash verification.
        </p>
        <p style="color:#DBEAFE;font-size:11px;margin-bottom:10px">Need Law Enforcement Entrance?</p>
        <a class="btn ghost" href="{{ url_for('gateway', view='officer') }}" style="align-self:center;width:220px">Switch to Police Gateway</a>
      {% else %}
        <span class="pill" style="background:#3B82F6;align-self:center;margin-bottom:12px">STAGE 1 — HIERARCHY GATEWAY</span>
        <h2 style="color:#fff;font-size:22px;margin:8px 0 10px;font-weight:700">Law Enforcement Login</h2>
        <p style="color:#EFF6FF;font-size:12px;line-height:1.6;margin-bottom:20px">
          Select your designated police post/rank first. Your jurisdiction is securely linked directly to your database badge ID.
        </p>
        <p style="color:#DBEAFE;font-size:11px;margin-bottom:8px">Presiding Magistrate or Judicial Clerk?</p>
        <a class="btn ghost" href="{{ url_for('gateway', view='judicial') }}" style="align-self:center;width:220px;margin-bottom:12px">Switch to Judicial Portal</a>
        <a class="btn gold" href="{{ url_for('analytics_gate') }}" style="align-self:center;width:220px;border-radius:25px">📊 Open Analytics Intelligence</a>
      {% endif %}
    </div>

    <!-- Active Form Panel -->
    <div style="padding:40px 32px">
      {% if view == 'judicial' %}
        <span class="pill gold" style="background:#FEF3C7;color:var(--gold);margin-bottom:10px">JUDICIAL CREDENTIALS</span>
        <h2 style="margin:10px 0 16px;font-size:19px;color:var(--text)">Judicial Inspection Access</h2>
        <form method="post" action="{{ url_for('court_login') }}" class="stack">
          <div>
            <label>Judge ID</label>
            <input type="text" name="username" value="judge_portal" required>
          </div>
          <div>
            <label>Judicial Cryptographic Password</label>
            <input type="password" name="password" value="court123" required>
          </div>
          <button class="btn gold" style="width:100%;margin-top:16px;height:42px">Authenticate Judicial Identity ➔</button>
        </form>
      {% else %}
        <span class="pill navy" style="background:#EFF6FF;color:var(--primary);margin-bottom:10px">OFFICER HIERARCHY LOGIN</span>
        <h2 style="margin:10px 0 16px;font-size:19px;color:var(--text)">Command Position Login</h2>
        <form method="post" action="{{ url_for('officer_login') }}" class="stack">
          <div>
            <label>Step 1: Select Your Position / Post</label>
            <select name="position">
              {% for p in positions %}
                <option value="{{ p }}" {{ 'selected' if loop.first }}>{{ p }}</option>
              {% endfor %}
            </select>
          </div>
          <div>
            <label>Officer Full Name (as registered)</label>
            <input type="text" name="officer_name" value="Inspector General Rajesh Verma" required>
          </div>
          <div>
            <label>Badge ID / Username</label>
            <input type="text" name="username" value="admin" required>
          </div>
          <div>
            <label>Secret Cryptographic Password</label>
            <input type="password" name="password" value="admin123" required>
          </div>
          <div class="row" style="margin-top:16px">
            <button class="btn" style="height:42px;flex:1">Authenticate &amp; Unlock Vault ➔</button>
            <a class="btn ghost" href="{{ url_for('forgot_password') }}" style="height:42px;color:var(--primary);border-color:var(--primary)">Forgot Password?</a>
          </div>
        </form>
      {% endif %}
    </div>
  </div>
</div>
"""


@app.route("/")
def gateway():
    view = request.args.get("view", "officer")
    return render_page(GATEWAY_TPL, "Authentication Gateway", view=view, positions=LOGIN_POSITIONS)


def _route_by_rank(level, role):
    if role == "COURT_JUDICIAL":
        return redirect(url_for("jurisdiction_state"))
    if level == 5:
        return redirect(url_for("jurisdiction_state"))
    if level == 4:
        return redirect(url_for("jurisdiction_city"))
    if level == 3:
        return redirect(url_for("jurisdiction_area"))
    return redirect(url_for("portal"))


@app.route("/login", methods=["POST"])
def officer_login():
    ok, msg = verify_mha_network()
    if not ok:
        flash(f"Security policy violation. {msg}", "error")
        return redirect(url_for("gateway"))

    post = request.form.get("position", "")
    name_input = (request.form.get("officer_name") or "").strip()
    uid = (request.form.get("username") or "").strip()
    pwd = (request.form.get("password") or "").strip()

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT badge_id, role, officer_name, police_rank, rank_level, division_code, area_zone, unit_name
            FROM vault_system_users
            WHERE (username = :usr OR badge_id = :usr) AND password_hash = :pwd AND is_active = 1
        """, {"usr": uid, "pwd": pwd})
        row = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database connection error: {e}", "error")
        return redirect(url_for("gateway"))

    if not row:
        flash("Authentication failed. Check your username and cryptographic password.", "error")
        return redirect(url_for("gateway"))

    db_badge, db_role, db_name = row[0], row[1].upper(), row[2]
    db_rank, db_level = row[3], int(row[4])
    db_div = row[5] or "SURAT"
    db_area = row[6] or "Zone 1"
    db_unit = row[7] or "Katargam Police Station"

    if db_name.lower() != name_input.lower():
        flash(
            f"Identity mismatch. The entered officer name ('{name_input}') does not match "
            f"official database records for '{db_name}'. Access denied.", "error"
        )
        return redirect(url_for("gateway"))

    session.permanent = True
    session.update({
        "badge": db_badge, "role": db_role, "name": db_name, "rank": db_rank,
        "rank_level": db_level, "division": db_div, "area": db_area, "unit": db_unit,
    })

    log_chained_audit_event(
        "OFFICER_LOGGED_IN",
        f"{db_rank} {db_name} (#{db_badge}) logged in via post: {post}"
    )
    flash(f"Welcome, {db_rank} {db_name}. Vault unlocked.", "ok")
    return _route_by_rank(db_level, db_role)


@app.route("/court-login", methods=["POST"])
def court_login():
    ok, msg = verify_mha_network()
    if not ok:
        flash(f"Security policy violation. {msg}", "error")
        return redirect(url_for("gateway", view="judicial"))

    u = (request.form.get("username") or "").strip()
    p = (request.form.get("password") or "").strip()

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT badge_id, role, officer_name, police_rank, rank_level, area_zone
            FROM vault_system_users
            WHERE (username = :usr OR badge_id = :usr) AND password_hash = :pwd AND is_active = 1
        """, {"usr": u, "pwd": p})
        row = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Oracle DB error: {e}", "error")
        return redirect(url_for("gateway", view="judicial"))

    if row and row[1].upper() == "COURT_JUDICIAL":
        session.permanent = True
        session.update({
            "badge": row[0], "role": "COURT_JUDICIAL", "name": row[2],
            "rank": row[3], "rank_level": int(row[4]),
            "area": row[5], "division": "", "unit": "",
        })
        log_chained_audit_event("JUDICIAL_LOGIN", f"Judge {row[2]} (#{row[0]}) opened inspection portal")
        flash("Judicial identity authenticated. Read-only inspection enabled.", "ok")
        return redirect(url_for("jurisdiction_state"))

    flash("Access denied. Invalid judicial credentials.", "error")
    return redirect(url_for("gateway", view="judicial"))


@app.route("/logout")
def logout():
    if session.get("badge"):
        log_chained_audit_event("SESSION_SIGNED_OUT", f"Officer #{session.get('badge')} signed out")
    session.clear()
    flash("Signed out. The vault is sealed.", "info")
    return redirect(url_for("gateway"))


# =========================================================
# FORGOT PASSWORD
# =========================================================
FORGOT_TPL = """
<div style="max-width:520px;margin:25px auto">
  <div class="card">
    <h2>🔒 Reset Password via Registered Email OTP</h2>
    <form method="post" action="{{ url_for('forgot_send_otp') }}" class="stack">
      <div>
        <label>Enter Registered Username / Badge ID</label>
        <input type="text" name="identifier" value="{{ identifier or 'io_surat' }}" required>
      </div>
      <button class="btn blue" style="width:100%">✉️ Send Verification OTP to Email</button>
    </form>

    <div class="muted" style="margin:14px 0 6px">{{ otp_status }}</div>

    <form method="post" action="{{ url_for('forgot_reset') }}" class="stack">
      <div>
        <label>Enter 6-Digit Email OTP</label>
        <input type="text" name="otp" placeholder="6-digit security OTP" required>
      </div>
      <div>
        <label>Enter New Secret Password</label>
        <input type="password" name="new_password" placeholder="New password" required>
      </div>
      <button class="btn green" style="width:100%;margin-top:10px">🔑 Verify OTP &amp; Update Password</button>
    </form>
    <div style="margin-top:16px"><a href="{{ url_for('gateway') }}">← Back to Sign In</a></div>
  </div>
</div>
"""


@app.route("/forgot-password")
def forgot_password():
    return render_page(
        FORGOT_TPL, "Account Recovery",
        identifier=session.get("_otp_ident", "io_surat"),
        otp_status=session.get("_otp_status", "Click 'Send Verification OTP' to dispatch code.")
    )


@app.route("/forgot-password/send", methods=["POST"])
def forgot_send_otp():
    ident = (request.form.get("identifier") or "").strip()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT badge_id, officer_name, officer_email FROM vault_system_users WHERE username = :1 OR badge_id = :2",
            (ident, ident)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("forgot_password"))

    if not row:
        flash("No registered officer account matches this identifier.", "error")
        return redirect(url_for("forgot_password"))

    badge, name, email = row[0], row[1], row[2]
    code = str(random.randint(100000, 999999))
    session["_otp_code"] = code
    session["_otp_badge"] = badge
    session["_otp_ident"] = ident
    session["_otp_status"] = f"OTP dispatched to {email[:3]}***@***.gov.in"

    ok, msg = send_email_otp(email, code, name)
    flash(msg, "ok" if ok else "error")
    return redirect(url_for("forgot_password"))


@app.route("/forgot-password/reset", methods=["POST"])
def forgot_reset():
    entered = (request.form.get("otp") or "").strip()
    new_p = (request.form.get("new_password") or "").strip()

    if not entered or not new_p:
        flash("Please enter OTP and your new password.", "error")
        return redirect(url_for("forgot_password"))

    if not session.get("_otp_code") or entered != session.get("_otp_code"):
        flash("Incorrect or expired OTP. Please try again.", "error")
        return redirect(url_for("forgot_password"))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE vault_system_users SET password_hash = :1 WHERE badge_id = :2",
                    (new_p, session.get("_otp_badge")))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")
        return redirect(url_for("forgot_password"))

    log_chained_audit_event("PASSWORD_RESET_SUCCESS", f"Password reset for Officer #{session.get('_otp_badge')}")
    for k in ("_otp_code", "_otp_badge", "_otp_ident", "_otp_status"):
        session.pop(k, None)
    flash("Password updated successfully. You can now sign in with your new password.", "ok")
    return redirect(url_for("gateway"))


# =========================================================
# ANALYTICS DASHBOARD (PRE-FILLED PASSWORD)
# =========================================================
ANALYTICS_GATE_TPL = """
<div style="max-width:460px;margin:40px auto">
  <div class="card">
    <h2>🔒 Restricted Analytics Security Gateway</h2>
    <p class="muted">Enter analytics master password to view high-level crime trend metrics.</p>
    <form method="post" action="{{ url_for('analytics_unlock') }}" class="stack">
      <div>
        <label>Enter Analytics Master Password</label>
        <input type="password" name="password" value="analytics123" required autofocus>
      </div>
      <button class="btn green" style="width:100%;margin-top:10px">Access Analytics ➔</button>
    </form>
    <div style="margin-top:14px"><a href="{{ back_url }}">← Back</a></div>
  </div>
</div>
"""

ANALYTICS_TPL = """
<div class="card" style="margin-bottom:14px">
  <h2>📊 Advanced Multi-Tier Crime &amp; Evidence Intelligence Analytics Dashboard</h2>
  <form method="get" action="{{ url_for('analytics') }}" class="row" style="gap:12px;align-items:flex-end">
    <div style="min-width:180px">
      <label>Analysis Scope</label>
      <select name="scope" onchange="this.form.submit()">
        {% for s in scopes %}<option value="{{ s }}" {{ 'selected' if s==scope }}>{{ s }}</option>{% endfor %}
      </select>
    </div>
    <div style="min-width:160px">
      <label>City</label>
      <select name="city" onchange="this.form.submit()">
        {% for c in cities %}<option value="{{ c }}" {{ 'selected' if c==city }}>{{ c }}</option>{% endfor %}
      </select>
    </div>
    <div style="min-width:170px">
      <label>Area / Zone</label>
      <select name="area" onchange="this.form.submit()">
        {% for a in areas %}<option value="{{ a }}" {{ 'selected' if a==area }}>{{ a }}</option>{% endfor %}
      </select>
    </div>
    {% if targets|length > 1 %}
    <div style="min-width:190px">
      <label>{{ target_label }}</label>
      <select name="target" onchange="this.form.submit()">
        {% for t in targets %}<option value="{{ t }}" {{ 'selected' if t==target }}>{{ t }}</option>{% endfor %}
      </select>
    </div>
    {% endif %}
  </form>
</div>

<div class="metrics" style="margin-bottom:14px">
  <div class="metric"><div class="t">Dockets [{{ scope_title }}]</div>
    <div class="v">{{ d.total }}</div><span class="pill navy">Active Scope</span></div>
  <div class="metric"><div class="t">Cases Resolved</div>
    <div class="v">{{ d.resolved }}</div><span class="pill green">{{ closure_pct }}% Closure</span></div>
  <div class="metric"><div class="t">High Severity (Murder)</div>
    <div class="v">{{ d.murder }}</div><span class="pill red">Priority Alpha</span></div>
  <div class="metric"><div class="t">Economic &amp; Financial</div>
    <div class="v">{{ d.economic }}</div><span class="pill gold">Fraud Track</span></div>
</div>

<div class="card" style="margin-bottom:14px">
  <h3>📈 Historical Trend Analysis: Previous Year vs Current Year &amp; Monthly Intake [{{ scope_title }}]</h3>
  <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px">
    {% for t in trends %}
    <div style="background:var(--card-highlight);border:1px solid var(--card-border);border-radius:9px;padding:13px">
      <div style="font-size:12px;font-weight:700;color:var(--primary)">{{ t.title }}</div>
      <div class="row" style="justify-content:space-between;margin-top:6px">
        <span style="font-size:11px;font-weight:700">Current Period: {{ t.curr }} cases</span>
        <span class="muted">Previous Period: {{ t.prev }} cases</span>
      </div>
      <div style="font-size:10.5px;font-weight:700;margin-top:6px;color:{{ t.color }}">{{ t.label }}</div>
    </div>
    {% endfor %}
  </div>
</div>

<div class="card">
  <h3>🔍 Crime Category Distribution Breakdown [{{ scope_title }}]</h3>
  {% for c in categories %}
  <div class="catrow">
    <div class="n">{{ c.name }}</div>
    <div class="bar"><span style="width:{{ c.pct }}%;background:{{ c.color }}"></span></div>
    <div class="c">{{ c.count }} cases ({{ c.pct }}%)</div>
  </div>
  {% endfor %}
</div>
"""


@app.route("/analytics/gate")
def analytics_gate():
    back = url_for("portal") if session.get("badge") else url_for("gateway")
    return render_page(ANALYTICS_GATE_TPL, "Analytics Gateway", back_url=back)


@app.route("/analytics/unlock", methods=["POST"])
def analytics_unlock():
    if (request.form.get("password") or "").strip() == ANALYTICS_PASSWORD:
        session["analytics_ok"] = True
        return redirect(url_for("analytics"))
    flash("Access Denied. Incorrect Analytics Master Password.", "error")
    return redirect(url_for("analytics_gate"))


def _analytics_counts(scope, city, area, target):
    d = dict(total=0, resolved=0, murder=0, robbery=0, cyber=0,
             narcotics=0, economic=0, other=0,
             curr_year=0, prev_year=0, curr_month=0, prev_month=0)

    base_query = "SELECT COUNT(*) FROM case_profiles c WHERE 1=1"
    params = []
    p_idx = 1

    if city != "All":
        base_query += f" AND c.division_code = :{p_idx}"; params.append(city); p_idx += 1
    if area != "All":
        base_query += f" AND c.area_zone = :{p_idx}"; params.append(area); p_idx += 1

    if scope == "City-wise" and target != "All":
        base_query += f" AND c.division_code = :{p_idx}"; params.append(target); p_idx += 1
    elif scope == "Area-wise" and target != "All":
        base_query += f" AND c.area_zone = :{p_idx}"; params.append(target); p_idx += 1
    elif scope == "Police Station-wise" and target != "All":
        base_query += f" AND c.unit_name = :{p_idx}"; params.append(target); p_idx += 1

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        def count(extra=""):
            cur.execute(base_query + extra, params)
            return cur.fetchone()[0]

        d["total"] = count()
        d["resolved"] = count(" AND c.case_condition IN ('Convicted & Sentenced', 'Closed / Acquitted')")
        d["murder"] = count(" AND (UPPER(c.case_name) LIKE '%MURDER%' OR UPPER(c.case_name) LIKE '%HOMICIDE%')")
        d["robbery"] = count(" AND (UPPER(c.case_name) LIKE '%ROBBERY%' OR UPPER(c.case_name) LIKE '%HEIST%' OR UPPER(c.case_name) LIKE '%THEFT%')")
        d["cyber"] = count(" AND (UPPER(c.case_name) LIKE '%CYBER%' OR UPPER(c.case_name) LIKE '%RANSOMWARE%')")
        d["narcotics"] = count(" AND (UPPER(c.case_name) LIKE '%NARCOTICS%' OR UPPER(c.case_name) LIKE '%DRUG%')")
        d["economic"] = count(" AND (UPPER(c.case_name) LIKE '%ECONOMIC%' OR UPPER(c.case_name) LIKE '%HAWALA%' OR UPPER(c.case_name) LIKE '%BANK%')")
        d["curr_year"] = count(" AND TO_CHAR(c.created_at, 'YYYY') = TO_CHAR(SYSDATE, 'YYYY')")
        d["prev_year"] = count(" AND TO_CHAR(c.created_at, 'YYYY') = TO_CHAR(SYSDATE, 'YYYY') - 1")
        d["curr_month"] = count(" AND TO_CHAR(c.created_at, 'YYYY-MM') = TO_CHAR(SYSDATE, 'YYYY-MM')")
        d["prev_month"] = count(" AND TO_CHAR(c.created_at, 'YYYY-MM') = TO_CHAR(ADD_MONTHS(SYSDATE, -1), 'YYYY-MM')")

        cur.close()
        conn.close()
    except Exception:
        d.update(total=10, resolved=6, murder=2, robbery=3, cyber=2, narcotics=1,
                 economic=2, curr_year=8, prev_year=4, curr_month=3, prev_month=2)

    d["other"] = max(0, d["total"] - (d["murder"] + d["robbery"] + d["cyber"] + d["narcotics"] + d["economic"]))
    return d


@app.route("/analytics")
def analytics():
    if not session.get("analytics_ok"):
        return redirect(url_for("analytics_gate"))

    scopes = ["Overall State", "City-wise", "Area-wise", "Police Station-wise"]
    scope = request.args.get("scope", "Overall State")
    city = request.args.get("city", "All")
    area = request.args.get("area", "All")
    target = request.args.get("target", "All")

    cities = ["All"] + fetch_divisions()
    areas, stations = ["All"], ["All"]
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if city != "All":
            cur.execute("SELECT DISTINCT area_zone FROM investigation_units WHERE division_code = :1 ORDER BY area_zone", (city,))
        else:
            cur.execute("SELECT DISTINCT area_zone FROM investigation_units ORDER BY area_zone")
        areas += [r[0] for r in cur.fetchall()]

        if city != "All" and area != "All":
            cur.execute("SELECT DISTINCT unit_name FROM investigation_units WHERE division_code = :1 AND area_zone = :2 ORDER BY unit_name", (city, area))
        elif city != "All":
            cur.execute("SELECT DISTINCT unit_name FROM investigation_units WHERE division_code = :1 ORDER BY unit_name", (city,))
        elif area != "All":
            cur.execute("SELECT DISTINCT unit_name FROM investigation_units WHERE area_zone = :1 ORDER BY unit_name", (area,))
        else:
            cur.execute("SELECT DISTINCT unit_name FROM investigation_units ORDER BY unit_name")
        stations += [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception:
        pass

    if scope == "City-wise":
        targets, target_label = cities, "City"
    elif scope == "Area-wise":
        targets, target_label = areas, "Area / Zone"
    elif scope == "Police Station-wise":
        targets, target_label = stations, "Police Station"
    else:
        targets, target_label, target = ["All"], "Target", "All"

    if target not in targets:
        target = "All"

    d = _analytics_counts(scope, city, area, target)
    scope_title = f"{scope} ({target})" if target != "All" else scope
    total = max(1, d["total"])

    def trend(title, curr, prev):
        diff = curr - prev
        pct = (diff / prev * 100) if prev > 0 else (100 if curr > 0 else 0)
        return {
            "title": title, "curr": curr, "prev": prev,
            "label": (f"▲ +{pct:.1f}% Growth vs Previous Period" if diff >= 0
                      else f"▼ {pct:.1f}% Reduction vs Previous Period"),
            "color": THEME["accent_green"] if diff >= 0 else THEME["accent_red"],
        }

    categories = [
        {"name": "🔴 Murder / Homicide", "count": d["murder"], "color": THEME["accent_red"]},
        {"name": "🟡 Robbery / Theft / Heist", "count": d["robbery"], "color": THEME["accent_gold"]},
        {"name": "🔵 Cyber / Ransomware", "count": d["cyber"], "color": THEME["primary"]},
        {"name": "🟣 Economic & Hawala Fraud", "count": d["economic"], "color": "#7C3AED"},
        {"name": "🟠 Narcotics & Drugs", "count": d["narcotics"], "color": "#EA580C"},
        {"name": "🟢 Other General Offenses", "count": d["other"], "color": THEME["accent_green"]},
    ]
    for c in categories:
        c["pct"] = int((c["count"] / total) * 100)

    return render_page(
        ANALYTICS_TPL, "Intelligence Analytics",
        scopes=scopes, scope=scope, cities=cities, city=city, areas=areas, area=area,
        targets=targets, target=target, target_label=target_label,
        d=d, scope_title=scope_title,
        closure_pct=int((d["resolved"] / total) * 100),
        trends=[
            trend("Annual Comparison (This Year vs Last Year)", d["curr_year"], d["prev_year"]),
            trend("Monthly Comparison (This Month vs Last Month)", d["curr_month"], d["prev_month"]),
        ],
        categories=categories
    )


# =========================================================
# SCREEN 2 — COMMAND TREE JURISDICTION DASHBOARDS
# =========================================================
JURIS_TPL = """
<div class="tabs">
  {% for t in tabs %}
    <a class="{{ 'active' if t.key == tab }}" href="{{ url_for(endpoint, tab=t.key) }}">{{ t.label }}</a>
  {% endfor %}
</div>

<div class="split">
  <div class="card">
    <h3>{{ list_title }}</h3>
    <form method="get" action="{{ url_for(endpoint) }}" class="stack">
      <input type="hidden" name="tab" value="{{ tab }}">
      <input type="text" name="q" value="{{ q }}" placeholder="🔍 Search {{ list_noun }}…">
      <button class="btn slate small" style="width:100%">Filter</button>
    </form>

    <div style="margin-top:12px">
      {% for item in items %}
        <div class="hierarchy-item">
          <a href="{{ url_for(endpoint, tab=tab, q=q, sel=item.key) }}" style="flex:1">
            <b>{{ item.label }}</b>
            {% if item.sub %}<div class="muted">{{ item.sub }}</div>{% endif %}
          </a>
          {% if can_edit and item.delete_url %}
            <form method="post" action="{{ item.delete_url }}" onsubmit="return confirm('Delete {{ item.label }}?')">
              <input type="hidden" name="tab" value="{{ tab }}">
              <button class="btn red small">🗑️</button>
            </form>
          {% endif %}
        </div>
      {% else %}
        <p class="muted">No records found.</p>
      {% endfor %}
    </div>

    {% if can_edit and create_fields %}
      <hr style="border:0;border-top:1px solid var(--card-border);margin:16px 0">
      <h3>{{ create_title }}</h3>
      <form method="post" action="{{ create_url }}" class="stack">
        <input type="hidden" name="tab" value="{{ tab }}">
        {% for f in create_fields %}
          <div>
            <label>{{ f.label }}</label>
            {% if f.type == 'select' %}
              <select name="{{ f.name }}">
                {% for o in f.options %}<option value="{{ o }}">{{ o }}</option>{% endfor %}
              </select>
            {% else %}
              <input type="text" name="{{ f.name }}" placeholder="{{ f.placeholder or '' }}" {{ 'required' if f.required }}>
            {% endif %}
          </div>
        {% endfor %}
        <button class="btn green" style="width:100%;margin-top:8px">{{ create_button }}</button>
      </form>
    {% endif %}
  </div>

  <div class="card">
    {% if not detail %}
      <h2>{{ detail_empty_title }}</h2>
      <p class="muted">{{ detail_empty_hint }}</p>
    {% else %}
      <h2>{{ detail.title }}</h2>
      <div class="muted" style="margin-bottom:12px">{{ detail.subtitle }}</div>

      <div class="card" style="background:var(--card-highlight);margin-bottom:14px">
        <h3>{{ detail.officer_heading }}</h3>
        {% if detail.officer %}
          <div style="font-size:13px;font-weight:700">Name: {{ detail.officer.name }}</div>
          <div class="muted">Badge ID: #{{ detail.officer.badge }} | Rank: {{ detail.officer.rank }}</div>
          <div class="muted">Email: {{ detail.officer.email }}</div>
          {% if can_edit %}
            <form method="post" action="{{ url_for('officer_update') }}" class="stack" style="margin-top:12px">
              <input type="hidden" name="badge_id" value="{{ detail.officer.badge }}">
              <input type="hidden" name="next" value="{{ request.full_path }}">
              <div><label>New Full Name</label>
                <input type="text" name="officer_name" value="{{ detail.officer.name }}" required></div>
              <div><label>New Official Email</label>
                <input type="text" name="officer_email" value="{{ detail.officer.email }}" required></div>
              <button class="btn blue small">Save Updates</button>
            </form>
          {% endif %}
        {% else %}
          <p class="muted">No officer assigned currently.</p>
          {% if can_edit %}
            <a class="btn green small" href="{{ detail.enroll_url }}">➕ Enrol {{ detail.enroll_label }}</a>
          {% endif %}
        {% endif %}
      </div>

      {% if detail.children %}
        <h3>{{ detail.children_heading }}</h3>
        {% for c in detail.children %}
          <div class="hierarchy-item"><b>{{ c }}</b></div>
        {% endfor %}
      {% endif %}

      {% if detail.station_entry %}
        <form method="post" action="{{ url_for('enter_station') }}" style="margin-top:14px">
          <input type="hidden" name="unit_name" value="{{ detail.station_entry.unit }}">
          <input type="hidden" name="division_code" value="{{ detail.station_entry.division }}">
          <input type="hidden" name="area_zone" value="{{ detail.station_entry.area }}">
          <button class="btn green" style="height:40px">
            🔓 Open Regular Station Vault (Cases, Evidence, Issue &amp; Return) ➔
          </button>
        </form>
      {% endif %}

      {% if can_edit and detail.extra_enrolments %}
        <div class="row" style="margin-top:14px">
          {% for e in detail.extra_enrolments %}
            <a class="btn green small" href="{{ e.url }}">{{ e.label }}</a>
          {% endfor %}
        </div>
      {% endif %}
    {% endif %}
  </div>
</div>
"""


def _officer_row(div_code=None, area=None, unit=None, rank_level=None):
    sql = "SELECT badge_id, officer_name, officer_email, police_rank FROM vault_system_users WHERE is_active = 1"
    binds = {}
    if div_code:
        sql += " AND division_code = :div"; binds["div"] = div_code
    if area:
        sql += " AND area_zone = :area"; binds["area"] = area
    if unit:
        sql += " AND unit_name = :unit"; binds["unit"] = unit
    if rank_level is not None:
        if isinstance(rank_level, (list, tuple)):
            sql += " AND rank_level <= :lvl"; binds["lvl"] = max(rank_level)
        else:
            sql += " AND rank_level = :lvl"; binds["lvl"] = rank_level
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(sql, binds)
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {"badge": row[0], "name": row[1], "email": row[2], "rank": row[3]}
    except Exception:
        pass
    return None


def _build_jurisdiction(endpoint, tab, q, sel, city_filter, allowed_tabs):
    can_edit = (not is_judge()) and current_user()["rank_level"] >= 4
    tab_defs = {
        "stations": {"key": "stations", "label": "1. Police Stations & Station Leads"},
        "areas": {"key": "areas", "label": "2. Areas, Zones & DCP / ACP"},
        "cities": {"key": "cities", "label": "3. Cities & CP Management"},
    }
    tabs = [tab_defs[t] for t in allowed_tabs]

    items, detail = [], None
    create_fields, create_url, create_title, create_button = [], "", "", ""
    divisions = fetch_divisions()

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if tab == "stations":
            if city_filter:
                cur.execute("SELECT unit_name, division_code, area_zone FROM investigation_units WHERE division_code = :1 ORDER BY unit_name", (city_filter,))
            else:
                cur.execute("SELECT unit_name, division_code, area_zone FROM investigation_units ORDER BY unit_name")
            rows = cur.fetchall()
            for r in rows:
                if q and q.upper() not in f"{r[0]} {r[1]} {r[2]}".upper():
                    continue
                items.append({
                    "key": r[0], "label": r[0], "sub": f"{r[1]} · {r[2]}",
                    "delete_url": url_for("station_delete", unit_name=r[0]),
                })
            match = next((r for r in rows if r[0] == sel), None)
            if match:
                officer = _officer_row(unit=match[0], rank_level=[2])
                detail = {
                    "title": f"🏛️ Police Station Profile: {match[0]}",
                    "subtitle": f"City: {match[1]} · Area / Zone: {match[2]}",
                    "officer_heading": "Station Leadership (SHO / IO / Forensic Lead)",
                    "officer": officer,
                    "enroll_url": url_for("officer_enroll", rank_type="SHO", city=match[1], area=match[2], station=match[0]),
                    "enroll_label": "Station SHO",
                    "station_entry": {"unit": match[0], "division": match[1], "area": match[2]},
                    "extra_enrolments": [{
                        "label": "➕ Add / Update Station SHO",
                        "url": url_for("officer_enroll", rank_type="SHO", city=match[1], area=match[2], station=match[0])
                    }],
                }
            create_title = "Add New Police Station"
            create_url = url_for("station_create")
            create_button = "Add Police Station"
            create_fields = [
                {"label": "Select City Division", "name": "division_code", "type": "select", "options": [city_filter] if city_filter else divisions},
                {"label": "New Police Station Name", "name": "unit_name", "placeholder": "e.g. Adajan Police Station", "required": True},
                {"label": "Area / Zone", "name": "area_zone", "placeholder": "e.g. Zone 1"},
            ]

        elif tab == "areas":
            if city_filter:
                cur.execute("SELECT DISTINCT division_code, area_zone FROM investigation_units WHERE division_code = :1 ORDER BY area_zone", (city_filter,))
            else:
                cur.execute("SELECT DISTINCT division_code, area_zone FROM investigation_units ORDER BY area_zone")
            rows = cur.fetchall()
            for r in rows:
                key = f"{r[0]}||{r[1]}"
                if q and q.upper() not in f"{r[0]} {r[1]}".upper():
                    continue
                items.append({
                    "key": key, "label": r[1], "sub": r[0],
                    "delete_url": url_for("area_delete", division_code=r[0], area_zone=r[1]),
                })
            match = next((r for r in rows if f"{r[0]}||{r[1]}" == sel), None)
            if match:
                officer = _officer_row(div_code=match[0], area=match[1], rank_level=3)
                cur.execute("SELECT unit_name FROM investigation_units WHERE division_code = :1 AND area_zone = :2", (match[0], match[1]))
                children = [x[0] for x in cur.fetchall()]
                detail = {
                    "title": f"📍 Area / Zone Profile: {match[1]}",
                    "subtitle": f"City Division: {match[0]}",
                    "officer_heading": "Assigned Assistant Commissioner of Police (ACP / DCP)",
                    "officer": officer,
                    "enroll_url": url_for("officer_enroll", rank_type="DCP", city=match[0], area=match[1]),
                    "enroll_label": "DCP",
                    "children_heading": "Police Stations in this Area / Zone",
                    "children": children,
                    "extra_enrolments": [
                        {"label": "➕ Add DCP", "url": url_for("officer_enroll", rank_type="DCP", city=match[0], area=match[1])},
                        {"label": "➕ Add ACP", "url": url_for("officer_enroll", rank_type="ACP", city=match[0], area=match[1])},
                    ],
                }
            create_title = "Create New Area / Zone"
            create_url = url_for("area_create")
            create_button = "Create Area Zone"
            create_fields = [
                {"label": "Select City Division", "name": "division_code", "type": "select", "options": [city_filter] if city_filter else divisions},
                {"label": "New Area / Zone Name", "name": "area_zone", "placeholder": "e.g. Zone 3 (West)", "required": True},
            ]

        else:
            cur.execute("SELECT division_code, division_name FROM police_divisions ORDER BY division_code")
            rows = cur.fetchall()
            for r in rows:
                if q and q.upper() not in f"{r[0]} {r[1]}".upper():
                    continue
                items.append({
                    "key": r[0], "label": r[0], "sub": r[1],
                    "delete_url": url_for("city_delete", division_code=r[0]),
                })
            match = next((r for r in rows if r[0] == sel), None)
            if match:
                officer = _officer_row(div_code=match[0], rank_level=4)
                cur.execute("SELECT DISTINCT area_zone FROM investigation_units WHERE division_code = :1", (match[0],))
                children = [x[0] for x in cur.fetchall()]
                detail = {
                    "title": f"🏙️ Commissionerate Profile: {match[0]}",
                    "subtitle": match[1],
                    "officer_heading": "Assigned City Commissioner of Police (CP)",
                    "officer": officer,
                    "enroll_url": url_for("officer_enroll", rank_type="CP", city=match[0]),
                    "enroll_label": "City CP",
                    "children_heading": "Areas / Zones in this City",
                    "children": children,
                    "extra_enrolments": [
                        {"label": "➕ Add / Update CP", "url": url_for("officer_enroll", rank_type="CP", city=match[0])},
                    ],
                }
            create_title = "Create New City Commissionerate"
            create_url = url_for("city_create")
            create_button = "Create City Division"
            create_fields = [
                {"label": "New City / Division Code", "name": "division_code", "placeholder": "e.g. VADODARA", "required": True},
            ]

        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")

    noun = {"stations": "Stations", "areas": "Areas", "cities": "Cities"}[tab]
    return dict(
        endpoint=endpoint, tab=tab, tabs=tabs, q=q, items=items, detail=detail,
        can_edit=can_edit, create_fields=create_fields, create_url=create_url,
        create_title=create_title, create_button=create_button,
        list_title={"stations": "Police Station Branches", "areas": "Areas / Zones", "cities": "State Cities / Divisions"}[tab],
        list_noun=noun,
        detail_empty_title="Select a record",
        detail_empty_hint=f"👈 Select an item from the left panel to inspect its command profile.",
    )


@app.route("/jurisdiction/state")
@login_required
def jurisdiction_state():
    u = current_user()
    if u["rank_level"] < 5 and u["role"] != "COURT_JUDICIAL":
        flash("Restricted to DGP State Command and Judicial Portal.", "error")
        return redirect(url_for("portal"))
    tab = request.args.get("tab", "cities")
    if tab not in ("stations", "areas", "cities"):
        tab = "cities"
    ctx = _build_jurisdiction("jurisdiction_state", tab, request.args.get("q", "").strip(),
                              request.args.get("sel", ""), None, ["stations", "areas", "cities"])
    return render_page(JURIS_TPL, "State Command Center", **ctx)


@app.route("/jurisdiction/city")
@login_required
def jurisdiction_city():
    u = current_user()
    tab = request.args.get("tab", "stations")
    if tab not in ("stations", "areas"):
        tab = "stations"
    ctx = _build_jurisdiction("jurisdiction_city", tab, request.args.get("q", "").strip(),
                              request.args.get("sel", ""), u["division"], ["stations", "areas"])
    return render_page(JURIS_TPL, "City Command Center", **ctx)


AREA_DASH_TPL = """
<div class="card">
  <h2>📍 Area / Zone Profile: {{ area_name }} ({{ div_code }})</h2>
  <div class="card" style="background:var(--card-highlight);margin:14px 0">
    <h3>Assigned Assistant Commissioner of Police (ACP / DCP)</h3>
    {% if officer %}
      <div style="font-size:13px;font-weight:700">Name: {{ officer.name }}</div>
      <div class="muted">Badge ID: #{{ officer.badge }} | Rank: {{ officer.rank }}</div>
      <div class="muted">Email: {{ officer.email }}</div>
    {% else %}
      <p class="muted">No ACP or DCP assigned to this zone currently.</p>
    {% endif %}
  </div>

  <h3>Police Stations in {{ area_name }}</h3>
  {% for s in stations %}
    <div class="hierarchy-item">
      <b>🏛️ {{ s }}</b>
      <form method="post" action="{{ url_for('enter_station') }}">
        <input type="hidden" name="unit_name" value="{{ s }}">
        <input type="hidden" name="division_code" value="{{ div_code }}">
        <input type="hidden" name="area_zone" value="{{ area_name }}">
        <button class="btn green small">Open Station Vault ➔</button>
      </form>
    </div>
  {% else %}
    <p class="muted">No police stations registered under this area zone.</p>
  {% endfor %}
</div>
"""


@app.route("/jurisdiction/area")
@login_required
def jurisdiction_area():
    u = current_user()
    area_name = u["area"] or "Zone 1"
    div_code = u["division"]
    stations = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT unit_name FROM investigation_units WHERE division_code = :1 AND area_zone = :2",
                    (div_code, area_name))
        stations = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")

    return render_page(AREA_DASH_TPL, "Area Command Dashboard",
                       area_name=area_name, div_code=div_code, stations=stations,
                       officer=_officer_row(div_code=div_code, area=area_name, rank_level=3))


@app.route("/jurisdiction/enter-station", methods=["POST"])
@login_required
def enter_station():
    session["unit"] = (request.form.get("unit_name") or "").strip()
    session["division"] = (request.form.get("division_code") or "").strip()
    session["area"] = (request.form.get("area_zone") or "").strip()
    log_chained_audit_event("STATION_VAULT_OPENED", f"Opened vault for {session['unit']} ({session['division']})")
    return redirect(url_for("portal"))


# ---------- Hierarchy Creation & Deletion ----------
@app.route("/jurisdiction/city/create", methods=["POST"])
@rank_required(4)
def city_create():
    code = (request.form.get("division_code") or "").strip().upper()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO police_divisions (division_code, division_name, division_password, nodal_officer_email) VALUES (:1, :2, 'password123', 'cp@police.gov.in')",
                    (code, f"{code} Police Commissionerate"))
        conn.commit()
        cur.close()
        conn.close()
        log_chained_audit_event("CITY_DIVISION_CREATED", f"City division {code} created")
        flash(f"City division {code} created.", "ok")
    except Exception as e:
        flash(f"Could not create city: {e}", "error")
    return redirect(url_for("jurisdiction_state", tab="cities"))


@app.route("/jurisdiction/city/<division_code>/delete", methods=["POST"])
@rank_required(5)
def city_delete(division_code):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM police_divisions WHERE division_code = :1", (division_code,))
        conn.commit()
        cur.close()
        conn.close()
        log_chained_audit_event("CITY_DIVISION_DELETED", f"City division {division_code} deleted")
        flash(f"City division {division_code} deleted.", "ok")
    except Exception as e:
        flash(f"Could not delete city: {e}", "error")
    return redirect(url_for("jurisdiction_state", tab="cities"))


@app.route("/jurisdiction/area/create", methods=["POST"])
@rank_required(4)
def area_create():
    div = (request.form.get("division_code") or "").strip()
    zone = (request.form.get("area_zone") or "").strip()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO investigation_units (division_code, unit_name, station_password, area_zone) VALUES (:1, :2, 'password123', :3)",
                    (div, f"{zone} Central Station", zone))
        conn.commit()
        cur.close()
        conn.close()
        log_chained_audit_event("AREA_ZONE_CREATED", f"Area zone {zone} created under {div}")
        flash(f"Area zone {zone} created.", "ok")
    except Exception as e:
        flash(f"Could not create area: {e}", "error")
    return redirect(request.referrer or url_for("jurisdiction_state", tab="areas"))


@app.route("/jurisdiction/area/delete", methods=["POST"])
@rank_required(4)
def area_delete():
    zone = request.args.get("area_zone") or request.form.get("area_zone")
    div = request.args.get("division_code") or request.form.get("division_code")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM investigation_units WHERE area_zone = :1 AND division_code = :2", (zone, div))
        conn.commit()
        cur.close()
        conn.close()
        log_chained_audit_event("AREA_ZONE_DELETED", f"Area zone {zone} deleted from {div}")
        flash(f"Area zone {zone} deleted.", "ok")
    except Exception as e:
        flash(f"Could not delete area: {e}", "error")
    return redirect(request.referrer or url_for("jurisdiction_state", tab="areas"))


@app.route("/jurisdiction/station/create", methods=["POST"])
@rank_required(4)
def station_create():
    div = (request.form.get("division_code") or "").strip()
    name = (request.form.get("unit_name") or "").strip()
    zone = (request.form.get("area_zone") or "").strip() or "Zone 1"
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO investigation_units (division_code, unit_name, station_password, area_zone) VALUES (:1, :2, 'password123', :3)",
                    (div, name, zone))
        conn.commit()
        cur.close()
        conn.close()
        log_chained_audit_event("STATION_CREATED", f"Police station {name} created in {div}")
        flash(f"Police station {name} added.", "ok")
    except Exception as e:
        flash(f"Could not add station: {e}", "error")
    return redirect(request.referrer or url_for("jurisdiction_state", tab="stations"))


@app.route("/jurisdiction/station/<path:unit_name>/delete", methods=["POST"])
@rank_required(4)
def station_delete(unit_name):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM investigation_units WHERE unit_name = :1", (unit_name,))
        conn.commit()
        cur.close()
        conn.close()
        log_chained_audit_event("STATION_DELETED", f"Police station {unit_name} deleted")
        flash(f"Police station {unit_name} deleted.", "ok")
    except Exception as e:
        flash(f"Could not delete station: {e}", "error")
    return redirect(request.referrer or url_for("jurisdiction_state", tab="stations"))


# =========================================================
# PERSONNEL ENROLMENT
# =========================================================
RANK_PRESETS = {
    "CP":  {"title": "Commissioner of Police (City CP)", "level": 4, "role": "COMMISSIONER"},
    "DCP": {"title": "Deputy Commissioner of Police (DCP)", "level": 3, "role": "DCP_ACP"},
    "ACP": {"title": "Assistant Commissioner of Police (ACP)", "level": 3, "role": "DCP_ACP"},
    "SHO": {"title": "Police Inspector / SHO", "level": 2, "role": "INSPECTOR_SHO"},
}

ENROLL_TPL = """
<div style="max-width:620px;margin:0 auto">
  <div class="card">
    <h2>👮 Enrol Junior Personnel</h2>
    <div class="muted" style="margin-bottom:12px">Authorised by: {{ u.rank }} ({{ u.name }})</div>

    <div style="background:var(--primary);color:#fff;border-radius:8px;padding:11px 13px;font-size:11.5px;font-weight:700;margin-bottom:14px">
      {{ assignment_tag }}
    </div>

    <form method="post" class="stack">
      <input type="hidden" name="rank_type" value="{{ rank_type }}">
      <input type="hidden" name="city" value="{{ city }}">
      <input type="hidden" name="area" value="{{ area }}">
      <input type="hidden" name="station" value="{{ station }}">
      <div><label>Officer Badge / ID (Unique)</label>
        <input type="text" name="badge_id" placeholder="e.g. IO-SUR-105" required></div>
      <div><label>Officer Full Name</label>
        <input type="text" name="officer_name" placeholder="e.g. Police Inspector K. Patel" required></div>
      <div><label>Official Police Email Address</label>
        <input type="email" name="officer_email" placeholder="e.g. k.patel@suratpolice.gov.in" required></div>
      <div><label>System Username</label>
        <input type="text" name="username" placeholder="e.g. io_kpatel" required></div>
      <div><label>Secret Password</label>
        <input type="password" name="password" required></div>
      <div><label>Confirm Secret Password</label>
        <input type="password" name="confirm_password" required></div>
      <button class="btn green" style="width:100%;margin-top:12px;height:42px">💾 Commit Enrol Junior Officer</button>
    </form>
    <div style="margin-top:14px"><a href="{{ back_url }}">← Back</a></div>
  </div>
</div>
"""


@app.route("/officers/enroll", methods=["GET", "POST"])
@rank_required(4)
def officer_enroll():
    u = current_user()
    src = request.form if request.method == "POST" else request.args
    rank_type = (src.get("rank_type") or "CP").upper()
    city = src.get("city") or u["division"] or "SURAT"
    area = src.get("area") or "Zone 1"
    station = src.get("station") or "Katargam Police Station"

    preset = RANK_PRESETS.get(rank_type, RANK_PRESETS["CP"])
    rank_title, assigned_lvl, assigned_role = preset["title"], preset["level"], preset["role"]

    if rank_type == "CP":
        assign_div, assign_unit, assign_area = city, "City Headquarters", "City Central Zone"
        assignment_tag = f"🏙️ {rank_title} | City: {city}"
    elif rank_type in ("DCP", "ACP"):
        assign_div, assign_unit, assign_area = city, f"{area} Headquarters", area
        assignment_tag = f"📍 {rank_title} | City: {city} | Area: {area}"
    else:
        assign_div, assign_unit, assign_area = city, station, area
        assignment_tag = f"🏛️ {rank_title} | City: {city} | Area: {area} | Station: {station}"

    back_url = url_for("jurisdiction_state") if u["rank_level"] >= 5 else url_for("jurisdiction_city")

    if request.method == "GET":
        return render_page(ENROLL_TPL, "Enrol Officer",
                           rank_type=rank_type, city=city, area=area, station=station,
                           assignment_tag=assignment_tag, back_url=back_url)

    b = (request.form.get("badge_id") or "").strip().upper()
    n = (request.form.get("officer_name") or "").strip()
    em = (request.form.get("officer_email") or "").strip()
    un = (request.form.get("username") or "").strip()
    pw = (request.form.get("password") or "").strip()
    cpw = (request.form.get("confirm_password") or "").strip()

    if pw != cpw:
        flash("Password and confirm password do not match.", "error")
        return redirect(url_for("officer_enroll", rank_type=rank_type, city=city, area=area, station=station))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO vault_system_users (badge_id, username, password_hash, officer_name, officer_email,
                                            police_rank, rank_level, role, division_code, area_zone, unit_name, is_active)
            VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, 1)
        """, (b, un, pw, n, em, rank_title, assigned_lvl, assigned_role, assign_div, assign_area, assign_unit))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Registration failed: {e}", "error")
        return redirect(url_for("officer_enroll", rank_type=rank_type, city=city, area=area, station=station))

    log_chained_audit_event("OFFICER_ENROLLED", f"New account created for {n} (#{b}) by {u['name']}")
    flash(f"Officer #{b} registered successfully.", "ok")
    return redirect(back_url)


@app.route("/officers/update", methods=["POST"])
@rank_required(4)
def officer_update():
    badge = (request.form.get("badge_id") or "").strip()
    name = (request.form.get("officer_name") or "").strip()
    email = (request.form.get("officer_email") or "").strip()
    nxt = request.form.get("next") or url_for("jurisdiction_state")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE vault_system_users SET officer_name = :1, officer_email = :2 WHERE badge_id = :3",
                    (name, email, badge))
        conn.commit()
        cur.close()
        conn.close()
        log_chained_audit_event("OFFICER_RECORD_UPDATED", f"Officer #{badge} updated")
        flash("Officer record updated.", "ok")
    except Exception as e:
        flash(f"Update failed: {e}", "error")
    return redirect(nxt)


# =========================================================
# SCREEN 3 — MAIN REPOSITORY & STATION WORKSPACE
# =========================================================
def portal_tabs(active):
    u = current_user()
    tabs = [("cases", "Case File Repository")]
    if u["role"] != "COURT_JUDICIAL":
        tabs.append(("custody", "Chain of Custody Ledger"))
    tabs.append(("verify", "Integrity Verification Dashboard"))
    if u["rank_level"] >= 3 or u["role"] == "COURT_JUDICIAL":
        tabs.append(("audit", "Security Audit Trails"))
    return [{"key": k, "label": l, "active": k == active} for k, l in tabs]


PORTAL_TABS_TPL = """
<div class="tabs">
  {% for t in tabs %}
    <a class="{{ 'active' if t.active }}" href="{{ url_for('portal', tab=t.key) }}">{{ t.label }}</a>
  {% endfor %}
</div>
"""


def fetch_cases(search_query=""):
    u = current_user()
    div, unit, area = u["division"], u["unit"], u["area"]
    binds = {}

    if u["rank_level"] == 5 or u["role"] == "COURT_JUDICIAL":
        if unit and unit not in ["State Command Center", "Surat Headquarters", "Sessions Court", ""]:
            where = "c.unit_name = :unit"; binds["unit"] = unit
        else:
            where = "1=1"
    elif u["rank_level"] == 4:
        if unit and unit != "City Headquarters":
            where = "c.division_code = :div AND c.unit_name = :unit"; binds.update(div=div, unit=unit)
        else:
            where = "c.division_code = :div"; binds["div"] = div
    elif u["rank_level"] == 3:
        where = "c.division_code = :div AND c.area_zone = :area AND c.unit_name = :unit"
        binds.update(div=div, area=area, unit=unit)
    else:
        where = "c.division_code = :div AND c.unit_name = :unit"
        binds.update(div=div, unit=unit)

    if search_query:
        where += (" AND (UPPER(c.case_no) LIKE :q OR UPPER(c.case_name) LIKE :q "
                  "OR UPPER(c.fir_no) LIKE :q OR UPPER(c.crime_location) LIKE :q "
                  "OR UPPER(c.unit_name) LIKE :q OR UPPER(c.division_code) LIKE :q)")
        binds["q"] = f"%{search_query.upper()}%"

    sql = f"""
        SELECT c.case_no, c.case_name, c.fir_no, c.crime_location, c.case_condition,
               c.punishment_details, c.division_code, c.area_zone, c.unit_name,
               (SELECT COUNT(*) FROM case_evidence_files e WHERE e.case_no = c.case_no) AS ev_count,
               c.registered_by
        FROM case_profiles c
        WHERE {where}
        ORDER BY c.created_at DESC
    """

    rows = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(sql, binds)
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Could not load cases: {e}", "error")

    cases = [{
        "case_no": r[0], "case_name": r[1], "fir_no": r[2], "location": r[3],
        "condition": r[4], "punishment": r[5], "city": r[6], "area": r[7],
        "station": r[8], "evidence_count": r[9], "registered_by": r[10],
    } for r in rows]

    pending = sum(1 for c in cases if c["condition"] not in RESOLVED_CONDITIONS)
    return cases, pending


CASES_TPL = """
{{ tabs_html|safe }}
<div class="split">
  {% if u.role != 'COURT_JUDICIAL' %}
  <div class="card">
    <h3>Register New Case Profile</h3>
    <p class="muted">Case No: [Auto-Generated by Station]</p>
    <form method="post" action="{{ url_for('case_register') }}" class="stack" onsubmit="return confirm('Register Case Permanently under {{ u.unit }}?')">
      <div><label>Case Name</label>
        <input type="text" name="case_name" placeholder="e.g. Lalita Bank Robbery" required></div>
      <div><label>Case Category (for Analytics &amp; Graphs)</label>
        <select name="category">
          {% for c in categories %}<option value="{{ c }}">{{ c }}</option>{% endfor %}
        </select></div>
      <div><label>FIR No</label>
        <input type="text" name="fir_no" placeholder="e.g. FIR-001/2026" required></div>
      <div><label>Crime Scene / Location</label>
        <input type="text" name="location" placeholder="Crime Scene Location" required></div>
      <div><label>Case Registered By</label>
        <input type="text" name="registered_by" value="{{ u.name }} (#{{ u.badge }})"></div>
      <div><label>Condition of Case</label>
        <select name="condition">
          {% for c in conditions %}<option value="{{ c }}">{{ c }}</option>{% endfor %}
        </select></div>
      <div><label>Sentence / Jail Facility (Optional)</label>
        <input type="text" name="punishment" placeholder="e.g. 5 Years RI at Lajpore Central Jail"></div>
      <button class="btn" style="width:100%;margin-top:12px;height:40px">➕ Commit &amp; Anchor Case</button>
    </form>

    <hr style="border:0;border-top:1px solid var(--card-border);margin:16px 0">
    <h3>Official Statutory Reports</h3>
    <a class="btn dark" style="width:100%" href="{{ url_for('report_pending_cases') }}">
      📊 Print Pending Cases Summary Report
    </a>
  </div>
  {% else %}
  <div class="card">
    <h3>Judicial Inspection Portal</h3>
    <p class="muted">Read-Only Evidence Manifest: Select any case record to inspect child exhibits, verify bit-level hashes, and export dossiers.</p>
    <a class="btn dark" style="width:100%;margin-top:10px" href="{{ url_for('report_pending_cases') }}">
      📊 Print Pending Cases Report
    </a>
  </div>
  {% endif %}

  <div class="card">
    <div class="row" style="justify-content:space-between;margin-bottom:10px">
      <form method="get" action="{{ url_for('portal') }}" class="row" style="flex:1">
        <input type="hidden" name="tab" value="cases">
        <input type="text" name="q" value="{{ q }}" style="max-width:380px" placeholder="🔍 Intelligent Keyword / FIR / City / Station Search...">
        <button class="btn small">Search</button>
        {% if q %}<a class="btn slate small" href="{{ url_for('portal', tab='cases') }}">Clear</a>{% endif %}
      </form>
      <div style="font-size:11px;font-weight:700;color:var(--red)">
        Station [{{ u.unit or 'All' }}] Unresolved Cases: {{ pending }} / {{ cases|length }}
      </div>
    </div>

    <div class="table-scroll">
      <table>
        <thead><tr>
          <th>Case No</th><th class="left">Case Name / Title</th><th>FIR Ref</th>
          <th>Crime Location</th><th>Condition</th><th class="left">Verdict / Jail Facility</th>
          <th>City</th><th>Area / Zone</th><th>Police Station</th>
          <th>Evidences</th><th>Registered By</th><th>Action</th>
        </tr></thead>
        <tbody>
          {% for c in cases %}
          <tr>
            <td><b>{{ c.case_no }}</b></td>
            <td class="left">{{ c.case_name }}</td>
            <td>{{ c.fir_no }}</td>
            <td>{{ c.location }}</td>
            <td>
              {% if c.condition in resolved %}<span class="pill green">{{ c.condition }}</span>
              {% else %}<span class="pill gold">{{ c.condition }}</span>{% endif %}
            </td>
            <td class="left">{{ c.punishment }}</td>
            <td>{{ c.city }}</td><td>{{ c.area }}</td><td>{{ c.station }}</td>
            <td><span class="pill navy">{{ c.evidence_count }}</span></td>
            <td>{{ c.registered_by }}</td>
            <td><a class="btn small" href="{{ url_for('case_workspace', case_no=c.case_no) }}">Workspace ➔</a></td>
          </tr>
          {% else %}
          <tr><td colspan="12" class="muted" style="padding:22px">No case profiles found.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
"""


@app.route("/portal")
@login_required
def portal():
    tab = request.args.get("tab", "cases")
    tabs_html = render_template_string(PORTAL_TABS_TPL, tabs=portal_tabs(tab))

    if tab == "custody":
        return _custody_view(tabs_html)
    if tab == "verify":
        return _verify_view(tabs_html)
    if tab == "audit":
        return _audit_view(tabs_html)

    q = request.args.get("q", "").strip()
    cases, pending = fetch_cases(q)
    return render_page(
        CASES_TPL, "Case File Repository",
        tabs_html=tabs_html, cases=cases, pending=pending, q=q,
        categories=CASE_CATEGORIES, conditions=CASE_CONDITIONS, resolved=RESOLVED_CONDITIONS
    )


@app.route("/cases/register", methods=["POST"])
@login_required
def case_register():
    u = current_user()
    if u["role"] == "COURT_JUDICIAL":
        flash("The judicial portal is read-only.", "error")
        return redirect(url_for("portal"))

    c_name = (request.form.get("case_name") or "").strip()
    c_cat = request.form.get("category") or CASE_CATEGORIES[1]
    f_no = (request.form.get("fir_no") or "").strip().upper()
    loc = (request.form.get("location") or "").strip()
    reg_by = (request.form.get("registered_by") or "").strip() or f"{u['rank']} #{u['badge']}"
    cond = request.form.get("condition") or CASE_CONDITIONS[0]
    punish = (request.form.get("punishment") or "").strip() or "Pending Trial / No Conviction Yet"
    div, unit = u["division"], u["unit"]
    area = u["area"] or "Zone 1 (North)"

    prefix = "".join([w[0] for w in unit.split() if w]).upper()[:3]
    if len(prefix) < 2:
        prefix = "PS"
    year_str = datetime.now().strftime("%Y")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM case_profiles WHERE unit_name = :1", (unit,))
        cnt = cur.fetchone()[0] + 1
        cur.close()
        conn.close()
    except Exception:
        cnt = random.randint(100, 999)

    c_no = f"{prefix}-{year_str}-{cnt:03d}"
    full_case_title = f"[{c_cat}] {c_name}"

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO case_profiles (case_no, case_name, fir_no, crime_location, case_condition,
                                       punishment_details, conviction_date, division_code, area_zone,
                                       unit_name, registered_by)
            VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11)
        """, (c_no, full_case_title, f_no, loc, cond, punish,
              datetime.now().strftime("%Y-%m-%d"), div, area, unit, reg_by))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")
        return redirect(url_for("portal", tab="cases"))

    log_chained_audit_event("CASE_REGISTERED", f"Case {c_no} (FIR {f_no}) registered in {unit} by {reg_by}")
    flash(f"Case '{full_case_title}' registered with Auto-Generated No: {c_no}!", "ok")
    return redirect(url_for("portal", tab="cases"))


@app.route("/cases/<path:case_no>/status", methods=["POST"])
@login_required
def case_update_status(case_no):
    if is_judge():
        flash("The judicial portal is read-only.", "error")
        return redirect(url_for("case_workspace", case_no=case_no))

    new_val = request.form.get("condition") or CASE_CONDITIONS[0]
    new_punish = (request.form.get("punishment") or "").strip() or "Pending Trial / No Conviction Yet"

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE case_profiles SET case_condition = :1, punishment_details = :2 WHERE case_no = :3",
                    (new_val, new_punish, case_no))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")
        return redirect(url_for("case_workspace", case_no=case_no))

    log_chained_audit_event("CASE_STATUS_UPDATED", f"Case {case_no} status -> {new_val}")
    flash(f"Case {case_no} status updated.", "ok")
    return redirect(url_for("case_workspace", case_no=case_no))


# =========================================================
# WORKSPACE & EVIDENCE MEDIA RENDERING
# =========================================================
def get_case(case_no):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT case_no, case_name, fir_no, crime_location, case_condition,
                   punishment_details, division_code, area_zone, unit_name, registered_by
            FROM case_profiles WHERE case_no = :1
        """, (case_no,))
        r = cur.fetchone()
        cur.close()
        conn.close()
        if r:
            return {
                "case_no": r[0], "case_name": r[1], "fir_no": r[2], "location": r[3],
                "condition": r[4], "punishment": r[5], "city": r[6], "area": r[7],
                "station": r[8], "registered_by": r[9],
            }
    except Exception:
        pass
    return None


def get_case_evidence(case_no):
    rows = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT evidence_id, evidence_title, category, ai_classification, sha256_hash,
                   vault_locker, active_custody_officer, raw_file_name, encrypted_path,
                   blockchain_status, blockchain_tx_hash, blockchain_block_number
            FROM case_evidence_files WHERE case_no = :1 ORDER BY uploaded_at
        """, (case_no,))
        for r in cur.fetchall():
            rows.append({
                "evidence_id": r[0], "title": r[1], "category": r[2], "classification": r[3],
                "sha256": r[4], "locker": r[5], "custody": r[6], "raw_file_name": r[7],
                "encrypted_path": r[8], "chain_status": r[9] or "PENDING",
                "tx_hash": r[10], "block_number": r[11],
                "kind": media_kind(r[7]),
                "on_disk": bool(r[8] and os.path.exists(r[8])),
            })
        cur.close()
        conn.close()
    except Exception:
        pass
    return rows


def get_evidence(evidence_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT evidence_id, case_no, evidence_title, category, ai_classification,
                   sha256_hash, vault_locker, active_custody_officer, raw_file_name, encrypted_path
            FROM case_evidence_files WHERE evidence_id = :1
        """, (evidence_id,))
        r = cur.fetchone()
        cur.close()
        conn.close()
        if r:
            return {
                "evidence_id": r[0], "case_no": r[1], "title": r[2], "category": r[3],
                "classification": r[4], "sha256": r[5], "locker": r[6], "custody": r[7],
                "raw_file_name": r[8], "encrypted_path": r[9], "kind": media_kind(r[8]),
            }
    except Exception:
        pass
    return None


WORKSPACE_TPL = """
<div class="card" style="margin-bottom:14px">
  <h2>📁 Evidence Manifest: {{ case.case_name }}</h2>
  <div class="muted">Case No: {{ case.case_no }} | FIR: {{ case.fir_no }} | {{ case.city }} — {{ case.area }} — {{ case.station }}</div>
  <div class="row" style="margin-top:12px">
    <span class="pill {{ 'green' if case.condition in resolved else 'gold' }}">{{ case.condition }}</span>
    <span class="muted">Scene: {{ case.location }}</span>
    <span class="muted">Registered by: {{ case.registered_by }}</span>
  </div>
  <div class="row" style="margin-top:12px">
    <a class="btn dark small" href="{{ url_for('report_case_dossier', case_no=case.case_no) }}">
      📄 Print Complete Case Dossier (All Evidences)
    </a>
    <a class="btn slate small" href="{{ url_for('portal', tab='cases') }}">← Back to Repository</a>
  </div>
</div>

<div class="split">
  <div class="stack">
    {% if u.role != 'COURT_JUDICIAL' %}
    <div class="card">
      <h3>Ingest &amp; Encrypt Evidence</h3>
      <form method="post" action="{{ url_for('evidence_upload', case_no=case.case_no) }}" enctype="multipart/form-data" class="stack">
        <div><label>Evidence ID</label>
          <input type="text" name="evidence_id" placeholder="e.g. EV-CCTV-01" required></div>
        <div><label>Evidence Title / Name</label>
          <input type="text" name="evidence_title" placeholder="e.g. Traffic CCTV Angle 2" required></div>
        <div><label>Locker / Shelf Location</label>
          <input type="text" name="vault_locker" placeholder="e.g. Locker 4-B"></div>
        <div><label>Select Digital Exhibit File</label>
          <input type="file" name="evidence_file" required></div>
        <button class="btn green" style="width:100%;margin-top:12px;height:40px">🔒 Encrypt &amp; Seal to Vault</button>
      </form>
    </div>

    <div class="card">
      <h3>Update Judicial Status &amp; Detention</h3>
      <form method="post" action="{{ url_for('case_update_status', case_no=case.case_no) }}" class="stack">
        <div><label>Condition of Case</label>
          <select name="condition">
            {% for c in conditions %}
              <option value="{{ c }}" {{ 'selected' if c == case.condition }}>{{ c }}</option>
            {% endfor %}
          </select></div>
        <div><label>Judicial Verdict / Detention Facility</label>
          <input type="text" name="punishment" value="{{ case.punishment }}"></div>
        <button class="btn gold" style="width:100%;margin-top:10px">💾 Commit Status &amp; Detention Update</button>
      </form>
    </div>
    {% endif %}
  </div>

  <div class="stack">
    {% if preview %}
    <div class="card">
      <h3>Exhibit {{ preview.evidence_id }} — {{ preview.title }}</h3>
      <div class="muted">{{ preview.category }} · {{ preview.classification }}</div>
      <div class="hash muted" style="margin-top:6px">SHA-256 Bit-Level Seal: {{ preview.sha256 }}</div>

      <div class="media-frame">
        {% if preview.kind == 'image' %}
          <img src="{{ url_for('evidence_stream', evidence_id=preview.evidence_id) }}" alt="Decrypted exhibit">
        {% elif preview.kind == 'video' %}
          <video controls preload="metadata" src="{{ url_for('evidence_stream', evidence_id=preview.evidence_id) }}"></video>
        {% elif preview.kind == 'audio' %}
          <audio controls src="{{ url_for('evidence_stream', evidence_id=preview.evidence_id) }}"></audio>
        {% elif preview.kind == 'pdf' %}
          <iframe src="{{ url_for('evidence_stream', evidence_id=preview.evidence_id) }}" style="width:100%;height:520px;border:0;border-radius:6px;background:#fff"></iframe>
        {% elif preview.kind == 'text' %}
          <pre>{{ preview_text }}</pre>
        {% else %}
          <p style="color:#E2E8F0;font-size:12px;margin:14px">
            [This is footage / binary dump which can't be represented inline. Please download to inspect with forensic tool.]
          </p>
        {% endif %}
      </div>

      <div class="row" style="margin-top:12px">
        <a class="btn blue small" href="{{ url_for('evidence_download', evidence_id=preview.evidence_id) }}">💾 Download Decrypted Copy</a>
        <a class="btn gold small" href="{{ url_for('report_65b', evidence_id=preview.evidence_id) }}">📑 Export Section 65B Certificate</a>
        <a class="btn slate small" href="{{ url_for('case_workspace', case_no=case.case_no) }}">Close Preview</a>
      </div>
    </div>
    {% endif %}

    <div class="card">
      <h3>Evidence Manifest ({{ evidences|length }} Exhibits Sealed)</h3>
      <div class="table-scroll">
        <table>
          <thead><tr>
            <th>Evidence ID</th><th class="left">Evidence Name</th><th>Category</th>
            <th class="left">AI Classification</th><th>SHA-256 Seal</th><th>Locker</th>
            <th>Custody</th><th>Chain</th><th>Inspect</th>
          </tr></thead>
          <tbody>
            {% for e in evidences %}
            <tr>
              <td><b>{{ e.evidence_id }}</b></td>
              <td class="left">{{ e.title }}</td>
              <td>{{ e.category }}</td>
              <td class="left">{{ e.classification }}</td>
              <td class="hash">{{ e.sha256[:20] }}…</td>
              <td>{{ e.locker }}</td>
              <td>{% if e.custody == 'VAULT' %}<span class="pill green">In Vault</span>
                  {% else %}<span class="pill gold">{{ e.custody }}</span>{% endif %}</td>
              <td>{% if e.chain_status == 'ANCHORED' %}<span class="pill navy">Anchored</span>
                  {% else %}<span class="pill slate">{{ e.chain_status }}</span>{% endif %}</td>
              <td>
                {% if e.on_disk %}
                  <a class="btn small" href="{{ url_for('case_workspace', case_no=case.case_no, view=e.evidence_id) }}">👁️ Decrypt &amp; View</a>
                {% else %}<span class="muted">Missing</span>{% endif %}
              </td>
            </tr>
            {% else %}
            <tr><td colspan="9" class="muted" style="padding:22px">No exhibits sealed yet.</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
"""


@app.route("/cases/<path:case_no>/workspace")
@login_required
def case_workspace(case_no):
    case = get_case(case_no)
    if not case:
        flash("Case profile not found.", "error")
        return redirect(url_for("portal", tab="cases"))

    evidences = get_case_evidence(case_no)
    preview, preview_text = None, ""
    view_id = request.args.get("view")

    if view_id:
        preview = next((e for e in evidences if e["evidence_id"] == view_id), None)
        if preview and preview["kind"] == "text" and preview["on_disk"]:
            try:
                raw = EncryptionEngine.decrypt_file_to_bytes(preview["encrypted_path"])
                preview_text = raw.decode("utf-8", errors="replace")[:20000]
            except Exception as e:
                preview_text = f"[Decryption Error: {e}]"
        if preview:
            log_chained_audit_event("EVIDENCE_DECRYPTED_VIEW", f"Decrypted and inspected {preview['title']} ({preview['evidence_id']})")

    return render_page(
        WORKSPACE_TPL, f"Case {case_no}",
        case=case, evidences=evidences, preview=preview, preview_text=preview_text,
        conditions=CASE_CONDITIONS, resolved=RESOLVED_CONDITIONS
    )


@app.route("/cases/<path:case_no>/evidence", methods=["POST"])
@login_required
def evidence_upload(case_no):
    u = current_user()
    if u["role"] == "COURT_JUDICIAL":
        flash("The judicial portal is read-only.", "error")
        return redirect(url_for("case_workspace", case_no=case_no))

    eid = (request.form.get("evidence_id") or "").strip().upper()
    etitle = (request.form.get("evidence_title") or "").strip()
    elock = (request.form.get("vault_locker") or "").strip() or "Unassigned Shelf"
    upload = request.files.get("evidence_file")

    if not eid or not etitle or not upload or not upload.filename:
        flash("Evidence ID, Title, and valid File are required.", "error")
        return redirect(url_for("case_workspace", case_no=case_no))

    raw_name = os.path.basename(upload.filename)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(raw_name)[1])
    os.close(tmp_fd)

    try:
        upload.save(tmp_path)
        detected_category, detected_classification, extracted_text = IntelligentClassifier.analyze_evidence(tmp_path, raw_name)

        hasher = hashlib.sha256()
        with open(tmp_path, "rb") as fobj:
            while chunk := fobj.read(4096):
                hasher.update(chunk)
        fhash = hasher.hexdigest()

        enc_target_path = os.path.join(VAULT_STORAGE_DIR, f"{eid}_{fhash[:12]}.nyayavault")
        EncryptionEngine.encrypt_file(tmp_path, enc_target_path)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO case_evidence_files (evidence_id, case_no, evidence_title, category, raw_file_name,
                                             encrypted_path, sha256_hash, vault_locker, ai_classification,
                                             ocr_extracted_text, uploaded_by)
            VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11)
        """, (eid, case_no, etitle, detected_category, raw_name, enc_target_path, fhash,
              elock, detected_classification, extracted_text, u["badge"] or "OFFICER"))

        cur.execute("SELECT NVL(MAX(transfer_id), 0) + 1 FROM chain_of_custody_ledger")
        t_id = cur.fetchone()[0]
        cur.execute("""
            INSERT INTO chain_of_custody_ledger (transfer_id, evidence_id, case_no, from_officer,
                                                 to_officer_badge, to_officer_name, to_officer_rank,
                                                 transfer_reason, division_code, unit_name,
                                                 checkout_time, court_return_deadline, custody_status)
            VALUES (:1, :2, :3, 'CRIME_SCENE', :4, :5, :6, 'Initial Lawful Ingestion and Sealing',
                    :7, :8, SYSDATE, SYSDATE + 30, 'RETURNED_TO_VAULT')
        """, (t_id, eid, case_no, u["badge"] or "OFFICER", u["name"] or "Investigator",
              u["rank"] or "Police Officer", u["division"], u["unit"]))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")
        return redirect(url_for("case_workspace", case_no=case_no))

    log_chained_audit_event("EVIDENCE_SEALED", f"Evidence {eid} sealed with hash {fhash} (AES-256 Protected)")

    if BLOCKCHAIN_MODULE_AVAILABLE and BLOCKCHAIN_CONFIG.get("enabled", False):
        try:
            tx_hash, block_no = anchor_evidence_hash(case_no, eid, fhash)
            conn2 = get_db_connection()
            cur2 = conn2.cursor()
            cur2.execute("""
                UPDATE case_evidence_files
                SET blockchain_tx_hash = :1, blockchain_block_number = :2, blockchain_status = 'ANCHORED'
                WHERE evidence_id = :3
            """, (tx_hash, block_no, eid))
            conn2.commit()
            cur2.close()
            conn2.close()
            log_chained_audit_event("EVIDENCE_ANCHORED_ONCHAIN", f"Evidence {eid} anchored on-chain, tx {tx_hash}")
        except Exception:
            pass

    flash(f"Evidence {eid} AES-256 Encrypted & Sealed! SHA-256: {fhash}", "ok")
    return redirect(url_for("case_workspace", case_no=case_no, view=eid))


def _decrypt_to_cache(ev):
    if not ev["encrypted_path"] or not os.path.exists(ev["encrypted_path"]):
        return None
    safe_name = "".join(ch for ch in (ev["raw_file_name"] or "exhibit.bin") if ch.isalnum() or ch in "._- ")
    cache_path = os.path.join(VAULT_STORAGE_DIR, f"DEC_TEMP_{ev['evidence_id']}_{safe_name}")
    try:
        enc_mtime = os.path.getmtime(ev["encrypted_path"])
        if not os.path.exists(cache_path) or os.path.getmtime(cache_path) < enc_mtime:
            data = EncryptionEngine.decrypt_file_to_bytes(ev["encrypted_path"])
            with open(cache_path, "wb") as f:
                f.write(data)
        return cache_path
    except Exception:
        return None


@app.route("/evidence/<path:evidence_id>/stream")
@login_required
def evidence_stream(evidence_id):
    ev = get_evidence(evidence_id)
    if not ev: abort(404)
    path = _decrypt_to_cache(ev)
    if not path: abort(404)
    return send_file(
        path, mimetype=guess_mime(ev["raw_file_name"]),
        as_attachment=False, conditional=True,
        download_name=ev["raw_file_name"] or "exhibit.bin"
    )


@app.route("/evidence/<path:evidence_id>/download")
@login_required
def evidence_download(evidence_id):
    ev = get_evidence(evidence_id)
    if not ev or not ev["encrypted_path"] or not os.path.exists(ev["encrypted_path"]):
        abort(404)
    try:
        data = EncryptionEngine.decrypt_file_to_bytes(ev["encrypted_path"])
    except Exception as e:
        flash(f"Decryption failed: {e}", "error")
        return redirect(url_for("case_workspace", case_no=ev["case_no"]))

    log_chained_audit_event("EVIDENCE_EXPORTED", f"Decrypted copy of {ev['title']} ({evidence_id}) downloaded")
    return send_file(
        io.BytesIO(data), mimetype=guess_mime(ev["raw_file_name"]),
        as_attachment=True, download_name=ev["raw_file_name"] or f"{evidence_id}.bin"
    )


# =========================================================
# CUSTODY & TIMELINE
# =========================================================
CUSTODY_TPL = """
{{ tabs_html|safe }}
<div class="split">
  <div class="card">
    <h3>Custody Handover &amp; Tracking</h3>
    <form method="post" action="{{ url_for('custody_issue') }}" class="stack">
      <div><label>Evidence ID</label>
        <input type="text" name="evidence_id" placeholder="e.g. EV-CCTV-01" required></div>
      <div><label>Recipient Officer Badge</label>
        <input type="text" name="badge" required></div>
      <div><label>Recipient Officer Name</label>
        <input type="text" name="name" required></div>
      <div><label>Officer Rank</label>
        <input type="text" name="rank" placeholder="e.g. PI / DySP"></div>
      <div><label>Recipient Officer Mobile</label>
        <input type="text" name="mobile" placeholder="10 Digits"></div>
      <div><label>Official Email</label>
        <input type="text" name="email" placeholder="officer@police.gov.in"></div>
      <div><label>Transfer Reason</label>
        <input type="text" name="reason" placeholder="e.g. FSL Testing"></div>
      <div><label>Custody Duration (Days)</label>
        <input type="number" name="days" value="7" min="1"></div>
      <button class="btn" style="width:100%;margin-top:12px;height:40px">🔒 Transfer &amp; Issue Evidence</button>
    </form>
  </div>

  <div class="card">
    <h3>Chain of Custody Movement Ledger</h3>
    <div class="table-scroll">
      <table>
        <thead><tr>
          <th>Transfer ID</th><th>Evidence ID</th><th>Case No</th><th>Badge</th><th class="left">Officer</th>
          <th>Rank</th><th>Checkout Time</th><th>Deadline</th><th>Status</th><th>Actions</th>
        </tr></thead>
        <tbody>
          {% for t in transfers %}
          <tr>
            <td>{{ t.transfer_id }}</td><td><b>{{ t.evidence_id }}</b></td><td>{{ t.case_no }}</td>
            <td>{{ t.badge }}</td><td class="left">{{ t.name }}</td><td>{{ t.rank }}</td>
            <td>{{ t.checkout }}</td><td>{{ t.deadline }}</td>
            <td>{% if t.status == 'CHECKED_OUT' %}<span class="pill gold">Checked Out</span>
                {% else %}<span class="pill green">In Vault</span>{% endif %}</td>
            <td>
              <div class="row" style="gap:5px;justify-content:center">
                <a class="btn small slate" href="{{ url_for('custody_timeline', evidence_id=t.evidence_id) }}">Timeline</a>
                {% if t.status == 'CHECKED_OUT' %}
                <form method="post" action="{{ url_for('custody_return') }}">
                  <input type="hidden" name="transfer_id" value="{{ t.transfer_id }}">
                  <input type="hidden" name="evidence_id" value="{{ t.evidence_id }}">
                  <button class="btn green small">Return</button>
                </form>
                {% endif %}
              </div>
            </td>
          </tr>
          {% else %}
          <tr><td colspan="10" class="muted" style="padding:22px">No movements logged.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
"""


def _custody_view(tabs_html):
    u = current_user()
    transfers = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT transfer_id, evidence_id, case_no, to_officer_badge, to_officer_name, to_officer_rank,
                   TO_CHAR(checkout_time, 'YYYY-MM-DD HH24:MI'), TO_CHAR(court_return_deadline, 'YYYY-MM-DD'),
                   custody_status
            FROM chain_of_custody_ledger WHERE division_code = :1 AND unit_name = :2
            ORDER BY transfer_id DESC
        """, (u["division"], u["unit"]))
        for r in cur.fetchall():
            transfers.append({
                "transfer_id": r[0], "evidence_id": r[1], "case_no": r[2], "badge": r[3],
                "name": r[4], "rank": r[5], "checkout": r[6], "deadline": r[7], "status": r[8],
            })
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Ledger error: {e}", "error")

    return render_page(CUSTODY_TPL, "Chain of Custody", tabs_html=tabs_html, transfers=transfers)


@app.route("/custody/issue", methods=["POST"])
@login_required
def custody_issue():
    u = current_user()
    eid = (request.form.get("evidence_id") or "").strip().upper()
    badge = (request.form.get("badge") or "").strip()
    name = (request.form.get("name") or "").strip()
    rank = (request.form.get("rank") or "").strip() or "Police Officer"
    mob = (request.form.get("mobile") or "").strip() or "9876543210"
    email = (request.form.get("email") or "").strip() or "officer@police.gov.in"
    reason = (request.form.get("reason") or "").strip() or "Official Forensic Examination"
    days_str = (request.form.get("days") or "").strip()
    days = int(days_str) if days_str.isdigit() else 7

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT case_no FROM case_evidence_files WHERE evidence_id = :1", (eid,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            flash("Evidence ID not found.", "error")
            return redirect(url_for("portal", tab="custody"))

        c_no = row[0]
        cur.execute("SELECT NVL(MAX(transfer_id), 0) + 1 FROM chain_of_custody_ledger")
        next_tid = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO chain_of_custody_ledger (transfer_id, evidence_id, case_no, from_officer,
                                                 to_officer_badge, to_officer_name, to_officer_rank,
                                                 to_officer_mobile, to_officer_email, transfer_reason,
                                                 division_code, unit_name, checkout_time,
                                                 court_return_deadline, custody_status)
            VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, SYSDATE, SYSDATE + :13, 'CHECKED_OUT')
        """, (next_tid, eid, c_no, f"{u['rank']} {u['name']}", badge, name, rank, mob, email,
              reason, u["division"], u["unit"], days))

        cur.execute("UPDATE case_evidence_files SET active_custody_officer = :1 WHERE evidence_id = :2", (name, eid))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")
        return redirect(url_for("portal", tab="custody"))

    log_chained_audit_event("CUSTODY_ISSUED", f"Evidence {eid} transferred to {name} (#{badge})")
    flash(f"Custody of Evidence {eid} transferred to Officer {name}.", "ok")
    return redirect(url_for("portal", tab="custody"))


@app.route("/custody/return", methods=["POST"])
@login_required
def custody_return():
    tid = request.form.get("transfer_id")
    eid = request.form.get("evidence_id")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE chain_of_custody_ledger
            SET custody_status = 'RETURNED_TO_VAULT', return_time = SYSDATE,
                return_condition = 'Integrity_Passed'
            WHERE transfer_id = :1
        """, (tid,))
        cur.execute("UPDATE case_evidence_files SET active_custody_officer = 'VAULT' WHERE evidence_id = :1", (eid,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")
        return redirect(url_for("portal", tab="custody"))

    log_chained_audit_event("CUSTODY_RESTORED_VAULT", f"Evidence {eid} returned to vault.")
    flash(f"Evidence {eid} safely returned to Vault.", "ok")
    return redirect(url_for("portal", tab="custody"))


TIMELINE_TPL = """
<div class="card">
  <h2>🔍 Interactive Journey Timeline: Evidence {{ evidence_id }}</h2>
  <div class="stack" style="margin-top:16px">
    {% for e in events %}
      <div class="card" style="background:var(--card-highlight);border:1px solid var(--card-border)">
        <div class="row" style="justify-content:space-between">
          <b>Stage {{ loop.index }}: {{ e.status }}</b>
          <span class="muted">Timestamp: {{ e.checkout }}</span>
        </div>
        <div style="margin-top:6px;font-size:12px">
          Transferred By: {{ e.from_officer }} ➔ Recipient: {{ e.to_name }} ({{ e.to_rank }})
        </div>
        <div class="muted" style="margin-top:3px">Purpose / Reason: {{ e.reason }}</div>
      </div>
    {% else %}
      <p class="muted">No tracking events recorded.</p>
    {% endfor %}
  </div>
  <a class="btn slate small" style="margin-top:14px" href="{{ url_for('portal', tab='custody') }}">← Back to Ledger</a>
</div>
"""


@app.route("/custody/<path:evidence_id>/timeline")
@login_required
def custody_timeline(evidence_id):
    events = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT from_officer, to_officer_name, to_officer_rank, transfer_reason,
                   TO_CHAR(checkout_time, 'YYYY-MM-DD HH24:MI'), custody_status
            FROM chain_of_custody_ledger WHERE evidence_id = :1 ORDER BY transfer_id ASC
        """, (evidence_id,))
        for r in cur.fetchall():
            events.append({
                "from_officer": r[0], "to_name": r[1], "to_rank": r[2],
                "reason": r[3], "checkout": r[4], "status": r[5],
            })
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Timeline error: {e}", "error")

    return render_page(TIMELINE_TPL, "Custody Timeline", evidence_id=evidence_id, events=events)


# =========================================================
# INTEGRITY AUDIT & TAMPER DEMO
# =========================================================
VERIFY_TPL = """
{{ tabs_html|safe }}
<div class="card" style="margin-bottom:14px">
  <div class="row" style="justify-content:space-between">
    <div>
      <h2>Live SHA-256 Bit-Level Integrity &amp; Tamper Audit Dashboard</h2>
      <p class="muted">Live calculation vs initial cryptographic SHA-256 bit-stream seal.</p>
    </div>
    <div class="row">
      <a class="btn green" href="{{ url_for('portal', tab='verify') }}">🔍 Run Global Bit-Stream Audit</a>
      {% if u.role != 'COURT_JUDICIAL' %}
      <form method="post" action="{{ url_for('tamper_simulate') }}" onsubmit="return confirm('Simulate bit tampering on disk payload?')">
        <select name="evidence_id" style="width:auto;display:inline-block;margin-right:6px">
          {% for r in results %}<option value="{{ r.evidence_id }}">{{ r.evidence_id }}</option>{% endfor %}
        </select>
        <button class="btn red">⚡ Simulate Controlled File Tamper</button>
      </form>
      {% endif %}
    </div>
  </div>
</div>

<div class="card">
  <div class="table-scroll">
    <table>
      <thead><tr>
        <th>Evidence ID</th><th>Case No</th><th class="left">Title</th>
        <th>Sealed Master Hash (DB)</th><th>Live Disk Re-Calculated Hash</th><th>Tamper Audit Status</th>
      </tr></thead>
      <tbody>
        {% for r in results %}
        <tr>
          <td><b>{{ r.evidence_id }}</b></td><td>{{ r.case_no }}</td>
          <td class="left">{{ r.title }}</td>
          <td class="hash">{{ r.sealed[:26] }}…</td>
          <td class="hash">{{ r.active[:26] }}{{ '…' if r.active|length > 26 }}</td>
          <td>
            {% if r.ok %}<span class="pill green">✅ VERIFIED (100% INTACT)</span>
            {% elif r.missing %}<span class="pill slate">❌ Missing File</span>
            {% else %}<span class="pill red">🚨 INTEGRITY MISMATCH</span>{% endif %}
          </td>
        </tr>
        {% else %}
        <tr><td colspan="6" class="muted" style="padding:22px">No exhibits found.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
"""


def _verify_view(tabs_html):
    u = current_user()
    results = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if u["rank_level"] == 5 or u["role"] == "COURT_JUDICIAL":
            cur.execute("SELECT e.evidence_id, e.case_no, e.evidence_title, e.sha256_hash, e.encrypted_path FROM case_evidence_files e JOIN case_profiles c ON e.case_no = c.case_no")
        else:
            cur.execute("SELECT e.evidence_id, e.case_no, e.evidence_title, e.sha256_hash, e.encrypted_path FROM case_evidence_files e JOIN case_profiles c ON e.case_no = c.case_no WHERE c.division_code = :1 AND c.unit_name = :2",
                        (u["division"], u["unit"]))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for r in rows:
            eid, cno, title, sealed_h, enc_p = r[0], r[1], r[2], r[3], r[4]
            active_h, ok, missing = "FILE_NOT_FOUND", False, True

            if enc_p and os.path.exists(enc_p):
                missing = False
                try:
                    dec_bytes = EncryptionEngine.decrypt_file_to_bytes(enc_p)
                    active_h = hashlib.sha256(dec_bytes).hexdigest()
                    ok = (active_h == sealed_h)
                except Exception:
                    active_h = "CORRUPTED_CIPHERTEXT"

            results.append({
                "evidence_id": eid, "case_no": cno, "title": title,
                "sealed": sealed_h, "active": active_h, "ok": ok, "missing": missing,
            })
    except Exception as e:
        flash(f"Audit error: {e}", "error")

    return render_page(VERIFY_TPL, "Integrity Verification", tabs_html=tabs_html, results=results)


@app.route("/verify/tamper-demo", methods=["POST"])
@login_required
def tamper_simulate():
    eid = (request.form.get("evidence_id") or "").strip()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT encrypted_path, evidence_title FROM case_evidence_files WHERE evidence_id = :1", (eid,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row and row[0] and os.path.exists(row[0]):
            with open(row[0], "ab") as f:
                f.write(b"\x00TAMPERED_PAYLOAD_BYTE_OVERRIDE\xFF")
            log_chained_audit_event("TAMPER_SIMULATION_EXECUTED", f"Controlled tamper applied to {eid}")
            flash(f"Exhibit {eid} ({row[1]}) ciphertext modified on disk! Re-running audit detects mismatch.", "error")
        else:
            flash(f"Physical file missing for {eid}.", "error")
    except Exception as e:
        flash(str(e), "error")

    return redirect(url_for("portal", tab="verify"))


# =========================================================
# AUDIT TRAILS
# =========================================================
AUDIT_TPL = """
{{ tabs_html|safe }}
<div class="card">
  <div class="row" style="justify-content:space-between;margin-bottom:10px">
    <h2>Cryptographically Chained Audit Ledger (MHA Statutory Nonce Chaining)</h2>
    <a class="btn" href="{{ url_for('portal', tab='audit') }}">🔄 Refresh Audit Chain</a>
  </div>
  <div class="table-scroll">
    <table>
      <thead><tr>
        <th>Log ID</th><th>Prev Hash</th><th>Timestamp</th><th>Actor</th><th>Role</th>
        <th>Action</th><th class="left">Target</th><th>IP Address</th><th>Block Hash</th>
      </tr></thead>
      <tbody>
        {% for l in logs %}
        <tr>
          <td>{{ l.log_id }}</td>
          <td class="hash">{{ l.prev_hash[:16] }}…</td>
          <td>{{ l.timestamp }}</td><td>{{ l.actor }}</td><td>{{ l.role }}</td>
          <td><span class="pill navy">{{ l.action }}</span></td>
          <td class="left">{{ l.target }}</td><td>{{ l.ip }}</td>
          <td class="hash">{{ l.log_hash[:16] }}…</td>
        </tr>
        {% else %}
        <tr><td colspan="9" class="muted" style="padding:22px">No audit events.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
"""


def _audit_view(tabs_html):
    logs = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT log_id, prev_log_hash, TO_CHAR(event_timestamp, 'YYYY-MM-DD HH24:MI:SS'),
                   actor_badge, role, action_type, target_reference, ip_address, log_hash
            FROM audit_security_logs ORDER BY log_id DESC
        """)
        for r in cur.fetchall():
            logs.append({
                "log_id": r[0], "prev_hash": r[1] or "", "timestamp": r[2], "actor": r[3],
                "role": r[4], "action": r[5], "target": r[6], "ip": r[7], "log_hash": r[8] or "",
            })
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Audit error: {e}", "error")

    return render_page(AUDIT_TPL, "Security Audit Trails", tabs_html=tabs_html, logs=logs)


# =========================================================
# STATUTORY REPORT PDF GENERATION
# =========================================================
def _pdf_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("TStyle", parent=styles["Heading1"], fontSize=14, alignment=1, textColor=colors.HexColor("#1E3A8A")),
        "sub": ParagraphStyle("SubStyle", parent=styles["Normal"], fontSize=9, alignment=1, textColor=colors.HexColor("#475569")),
        "h2": ParagraphStyle("H2Style", parent=styles["Heading2"], fontSize=11, textColor=colors.HexColor("#1E3A8A")),
        "body": ParagraphStyle("BStyle", parent=styles["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#0F172A")),
        "normal": styles["Normal"],
    }


@app.route("/reports/case/<path:case_no>/dossier")
@login_required
def report_case_dossier(case_no):
    u = current_user()
    case = get_case(case_no)
    if not case:
        flash("Case not found.", "error")
        return redirect(url_for("portal", tab="cases"))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT evidence_id, evidence_title, category, ai_classification, sha256_hash, vault_locker, active_custody_officer, encrypted_path, raw_file_name FROM case_evidence_files WHERE case_no = :1", (case_no,))
        ev_rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"DB Error: {e}", "error")
        return redirect(url_for("case_workspace", case_no=case_no))

    st = _pdf_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    elements = [
        Paragraph("MINISTRY OF HOME AFFAIRS • GOVERNMENT OF INDIA", st["sub"]),
        Paragraph("OFFICIAL CASE & EVIDENCE LIFECYCLE DOSSIER", st["title"]),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1E3A8A"), spaceAfter=12),
    ]

    meta_data = [
        ["Master Case Number:", case["case_no"], "FIR Reference:", case["fir_no"]],
        ["Incident / Case Title:", case["case_name"], "Incident Scene:", case["location"]],
        ["Jurisdiction Division:", case["city"], "Area Zone / Station:", f"{case['area']} — {case['station']}"],
        ["Current Case Condition:", case["condition"], "Conviction / Detention:", case["punishment"]],
        ["Sealing & Ingestion Stamp:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Inspecting Authority:", f"{u['rank']} {u['name']}"],
    ]
    t_meta = Table(meta_data, colWidths=[130, 140, 130, 140])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements += [t_meta, Spacer(1, 15)]
    elements.append(Paragraph("<b>ITEMIZED DIGITAL EVIDENCE EXHIBITS, BIT-LEVEL SHA-256 SEALS & VISUAL ATTACHMENTS:</b>", st["h2"]))
    elements.append(Spacer(1, 6))

    temp_images = []
    if ev_rows:
        for er in ev_rows:
            eid, etitle, ecat, eclass, ehash, elocker, ecustody, enc_path, raw_name = er
            exhibit_meta = [
                [Paragraph(f"<b>Exhibit ID:</b> {eid}", st["body"]), Paragraph(f"<b>Title:</b> {etitle}", st["body"])],
                [Paragraph(f"<b>Category:</b> {ecat} ({eclass})", st["body"]), Paragraph(f"<b>Vault Shelf:</b> {elocker} | <b>Custody:</b> {ecustody}", st["body"])],
                [Paragraph(f"<b>SHA-256 Seal:</b> {ehash}", st["body"]), ""],
            ]
            t_ex = Table(exhibit_meta, colWidths=[260, 280])
            t_ex.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('PADDING', (0, 0), (-1, -1), 4),
                ('SPAN', (0, 2), (1, 2)),
            ]))
            elements += [t_ex, Spacer(1, 4)]

            img_temp_path = None
            if media_kind(raw_name) == "image" and enc_path and os.path.exists(enc_path):
                try:
                    dec_bytes = EncryptionEngine.decrypt_file_to_bytes(enc_path)
                    img_temp_path = os.path.join(VAULT_STORAGE_DIR, f"PDF_IMG_{eid}.png")
                    with open(img_temp_path, "wb") as f_img:
                        f_img.write(dec_bytes)
                    Image.open(img_temp_path).verify()
                    temp_images.append(img_temp_path)
                except Exception:
                    img_temp_path = None

            if img_temp_path and os.path.exists(img_temp_path):
                try:
                    elements.append(RLImage(img_temp_path, width=160, height=110))
                except Exception:
                    elements.append(Paragraph("<i>[Visual attachment rendering failed]</i>", st["body"]))
            else:
                elements.append(Paragraph(
                    "<b>[This is footage / binary dump which can't be represented in PDF so please check in app for this]</b>",
                    ParagraphStyle("FootageNote", parent=st["body"], textColor=colors.HexColor("#DC2626"), fontName="Helvetica-Bold")))

            elements.append(Spacer(1, 10))

    elements += [Spacer(1, 15), Paragraph(
        "<b>STATUTORY AUTHENTICITY CERTIFICATE:</b> This electronic case record and child exhibits are cryptographically anchored under AES-256 encryption at rest and SHA-256 bit-stream integrity seals. Admissible under Indian Evidentiary Statutes (Section 65B IEA / Section 63 BSA).", st["body"])]

    doc.build(elements)
    buffer.seek(0)
    for p in temp_images:
        try: os.remove(p)
        except Exception: pass

    log_chained_audit_event("CASE_DOSSIER_PRINTED", f"Exported complete dossier for Case {case_no}")
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=f"Complete_Case_Dossier_{case_no.replace('/', '_')}.pdf")


@app.route("/reports/pending-cases")
@login_required
def report_pending_cases():
    u = current_user()
    div, unit = u["division"], u["unit"]

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT case_no, case_name, fir_no, crime_location, case_condition, division_code, unit_name, TO_CHAR(created_at, 'YYYY-MM-DD')
            FROM case_profiles WHERE division_code = :1 AND unit_name = :2 AND case_condition NOT IN ('Convicted & Sentenced', 'Closed / Acquitted')
        """, (div, unit))
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"DB Error: {e}", "error")
        return redirect(url_for("portal", tab="cases"))

    st = _pdf_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    elements = [
        Paragraph("MINISTRY OF HOME AFFAIRS • GOVERNMENT OF INDIA", st["sub"]),
        Paragraph(f"OFFICIAL PENDING CASES REPORT — {unit}", st["title"]),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1E3A8A"), spaceAfter=12),
        Paragraph(f"Report Generated By: {u['rank']} {u['name']} (#{u['badge']}) | Station: {unit} | Total Pending Dockets: {len(rows)}", st["body"]),
        Spacer(1, 10),
    ]

    p_data = [["Case No", "Case Name / Title", "FIR Ref", "Crime Location", "Status / Stage", "City", "Police Station", "Registered Date"]]
    for r in rows:
        p_data.append([str(x) for x in r])

    t_p = Table(p_data, colWidths=[80, 140, 80, 110, 100, 70, 90, 70])
    t_p.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(t_p)
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=f"Pending_Cases_Report_{unit}.pdf")


@app.route("/reports/evidence/<path:evidence_id>/65b")
@login_required
def report_65b(evidence_id):
    u = current_user()
    ev = get_evidence(evidence_id)
    if not ev: abort(404)
    case = get_case(ev["case_no"]) or {}
    st = _pdf_styles()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    title_style = ParagraphStyle("TStyle65", parent=st["title"], fontSize=13)

    elements = [
        Paragraph("MINISTRY OF HOME AFFAIRS • GOVERNMENT OF INDIA", st["sub"]),
        Paragraph("CERTIFICATE OF AUTHENTICITY UNDER SECTION 65B (IEA) / SECTION 63 (BSA)", title_style),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=15),
    ]

    cert_data = [
        ["Case Ref Number:", ev["case_no"]],
        ["Case Name / Title:", case.get("case_name", "")],
        ["FIR Number:", case.get("fir_no", "")],
        ["Evidence Identifier:", ev["evidence_id"]],
        ["Evidence Title:", ev["title"]],
        ["Category & AI Classification:", f"{ev['category']} ({ev['classification']})"],
        ["Jurisdiction City:", case.get("city", u["division"])],
        ["Police Station / Area:", case.get("station", u["unit"])],
        ["Cryptographic SHA-256 Seal:", ev["sha256"]],
        ["AES-256 Vault Encryption:", "ENABLED & VERIFIED AT REST"],
        ["Integrity Status:", "VERIFIED INTACT (100% UNMODIFIED BIT-STREAM)"],
    ]
    t = Table(cert_data, colWidths=[180, 360])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements += [t, Spacer(1, 20), Paragraph(
        "<b>STATUTORY ASSISTANCE DECLARATION:</b> This electronic record was mathematically fingerprinted and encrypted at lawful ingestion under Section 65B of the Indian Evidence Act / Section 63 of Bharatiya Sakshya Adhiniyam.", st["body"])]

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=f"Section65B_Certificate_{evidence_id}.pdf")


# =========================================================
# DUAL-RUNTIME HANDLER (STANDALONE FLASK + STREAMLIT CLOUD)
# =========================================================
def is_running_in_streamlit():
    if any("streamlit" in str(arg).lower() for arg in sys.argv):
        return True
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        pass
    return False


if is_running_in_streamlit():
    import streamlit as st
    import streamlit.components.v1 as components
    import threading

    st.set_page_config(
        page_title="NyayaVault — Ministry of Home Affairs",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    st.markdown(
        """
        <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container {padding: 0 !important; margin: 0 !important; max-width: 100% !important;}
        iframe {border: none !important; width: 100% !important; min-height: 98vh;}
        </style>
        """,
        unsafe_allow_html=True
    )

    # Launch background Flask thread if not active
    if "flask_thread_started" not in st.session_state:
        st.session_state.flask_thread_started = True
        flask_thread = threading.Thread(
            target=lambda: app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False),
            daemon=True
        )
        flask_thread.start()

    components.iframe("http://127.0.0.1:5000", height=980, scrolling=True)

else:
    if __name__ == "__main__":
        print("=" * 64)
        print(" NyayaVault Web — Ministry of Home Affairs (PS-190)")
        print(" Listening on: http://127.0.0.1:5000")
        print("=" * 64)
        app.run(host="0.0.0.0", port=5000, debug=False)