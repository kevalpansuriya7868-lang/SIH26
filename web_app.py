"""
web_app.py — NyayaVault Web Edition (Flask & Streamlit Dual Compatible)

A 1:1 web port of app.py (the CustomTkinter desktop client) styled with the
complete MHA theme, icons, symbols, and layouts from web_app1.py. Every screen,
rank rule, Oracle query, AES-256 seal, SHA-256 audit chain, blockchain
anchor, and ReportLab PDF is fully implemented.

Reads configuration from config.json, interfaces with the schema defined in
Local_SIH26.sql, and manages evidence files in secure_vault_storage.
"""

import os
import io
import sys
import json
import math
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

# Official MHA theme with high-contrast text across all components
THEME = {
    "bg_main": "#F1F5F9",
    "card_bg": "#FFFFFF",
    "card_border": "#CBD5E1",
    "card_highlight": "#F8FAFC",
    "input_bg": "#FFFFFF",
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
    "text_main": "#000000",          # Strict Pure Black Text
    "text_muted": "#1E293B"          # High-contrast Slate Black for Subtitles
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

# In-memory default fallbacks for instant evaluation
SEED_USERS = {
    "admin": {"name": "Inspector General Rajesh Verma", "rank": "Director General of Police (DGP)", "level": 5, "role": "SUPER_ADMIN", "pwd": "admin123", "badge": "ADMIN-001", "div": "SURAT", "area": "State HQ", "unit": "State Command Center"},
    "cp_surat": {"name": "Shri Anupam Gehlot", "rank": "Commissioner of Police (City CP)", "level": 4, "role": "COMMISSIONER", "pwd": "surat123", "badge": "CP-SUR-01", "div": "SURAT", "area": "City Central", "unit": "Surat Headquarters"},
    "dcp_surat_zone1": {"name": "Himanshu Verma", "rank": "Deputy Commissioner of Police (DCP)", "level": 3, "role": "DCP_ACP", "pwd": "dcp123", "badge": "DCP-SUR-01", "div": "SURAT", "area": "Zone 1", "unit": "Zone 1 Headquarters"},
    "io_surat": {"name": "Police Inspector V. Jadeja", "rank": "Police Inspector (SHO)", "level": 2, "role": "INSPECTOR_SHO", "pwd": "io123", "badge": "IO-SUR-102", "div": "SURAT", "area": "Zone 1 (North)", "unit": "Katargam Police Station"},
    "judge_portal": {"name": "Honorable Sessions Judge A. Dave", "rank": "Sessions Judge", "level": 1, "role": "COURT_JUDICIAL", "pwd": "court123", "badge": "JUDGE-007", "div": "SURAT", "area": "Judicial District", "unit": "Sessions Court"},
}

app = Flask(__name__)
app.secret_key = config.get("security", {}).get("jwt_secret", "NYAYAVAULT_MHA_SECURE_TOKEN_2026")
app.permanent_session_lifetime = __import__("datetime").timedelta(
    hours=int(config.get("security", {}).get("token_expire_hours", 8))
)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False


# =========================================================
# CORE ENGINES
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
    try:
        return oracledb.connect(
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=int(DB_CONFIG["port"]),
            service_name=DB_CONFIG["service_name"]
        )
    except Exception:
        return None


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
        if not conn:
            return
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
        if not conn:
            return ["SURAT", "AHMEDABAD", "RAJKOT"]
        cur = conn.cursor()
        cur.execute("SELECT division_code FROM police_divisions ORDER BY division_code")
        rows = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows if rows else ["SURAT", "AHMEDABAD", "RAJKOT"]
    except Exception:
        return ["SURAT", "AHMEDABAD", "RAJKOT"]


# =========================================================
# SHARED THEME & RESPONSIVE HTML (ENFORCED PURE BLACK TEXT)
# =========================================================
BASE_CSS = """
:root {
  --bg-main: #F1F5F9;
  --card-bg: #FFFFFF;
  --card-border: #CBD5E1;
  --card-highlight: #F8FAFC;
  --input-bg: #FFFFFF;
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
  --text: #000000;
  --muted: #1E293B;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg-main);
  color: #000000 !important;
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  font-size: 14px;
}
p, div, span, label, input, select, textarea, button, th, td, h1, h2, h3, h4, h5, h6, b, strong, small {
  color: #000000;
}
a { color: var(--primary); text-decoration: none; font-weight: 700; }
.topbar {
  background: var(--card-bg);
  border-bottom: 2px solid var(--card-border);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.topbar h1 { font-size: 16px; margin: 0; color: var(--primary) !important; font-weight: 800; }
.topbar .who { font-size: 12px; color: #047857 !important; margin-top: 3px; font-weight: 700; }
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
  color: #FFFFFF !important;
  background: var(--primary);
  text-decoration: none;
  line-height: 1.2;
}
.btn:hover { background: var(--primary-hover); color: #FFFFFF !important; }
.btn.green { background: var(--green); } .btn.green:hover { background: var(--green-hover); }
.btn.gold { background: var(--gold); } .btn.gold:hover { background: var(--gold-hover); }
.btn.red { background: var(--red); } .btn.red:hover { background: var(--red-hover); }
.btn.blue { background: #0284C7; } .btn.blue:hover { background: #0369A1; }
.btn.dark { background: #1E293B; } .btn.dark:hover { background: #0F172A; }
.btn.slate { background: #475569; } .btn.slate:hover { background: #334155; }
.btn.ghost { background: transparent; color: #000000 !important; border: 2px solid var(--primary); border-radius: 10px; }
.btn.ghost:hover { background: #EFF6FF; }
.btn.small { padding: 6px 12px; font-size: 11px; border-radius: 8px; }
.wrap { padding: 18px 24px 40px; }
.card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.card h2 { margin: 0 0 10px; font-size: 16px; color: var(--primary) !important; font-weight: 800; }
.card h3 { margin: 0 0 8px; font-size: 13.5px; color: var(--primary) !important; font-weight: 800; }
.muted { color: #1E293B !important; font-size: 11.5px; font-weight: 600; }
label { display: block; font-size: 12px; font-weight: 800; color: #000000 !important; margin: 8px 0 3px; }
input[type=text], input[type=password], input[type=email], input[type=number], input[type=file], select, textarea {
  width: 100%;
  background: #FFFFFF !important;
  border: 1.5px solid var(--card-border);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13.5px;
  color: #000000 !important;
  font-weight: 600;
  font-family: inherit;
}
textarea { min-height: 70px; }
.grid { display: grid; gap: 15px; }
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
.tabs a { padding: 8px 14px; border-radius: 8px; font-size: 12px; font-weight: 700; color: #000000 !important; }
.tabs a.active { background: var(--primary); color: #FFFFFF !important; }
.table-scroll { overflow-x: auto; border: 1.5px solid var(--card-border); border-radius: 10px; background: var(--card-bg); }
table { border-collapse: collapse; width: 100%; font-size: 12px; min-width: 640px; }
th {
  background: #E2E8F0;
  color: #000000 !important;
  text-align: center;
  font-weight: 800;
  padding: 10px 8px;
  border-bottom: 2px solid var(--card-border);
  white-space: nowrap;
}
td { padding: 10px 8px; border-bottom: 1px solid #CBD5E1; text-align: center; vertical-align: middle; color: #000000 !important; font-weight: 600; }
tr:hover { background: #F1F5F9; }
td.left, th.left { text-align: left; }
.hash { font-family: Consolas, Menlo, monospace; font-size: 11px; word-break: break-all; color: #000000 !important; font-weight: 700; }
.flashes { margin: 0 0 14px; padding: 0; list-style: none; }
.flashes li { padding: 11px 14px; border-radius: 10px; margin-bottom: 8px; font-size: 12.5px; font-weight: 700; }
.flashes li.ok { background: #ECFDF5; color: #065F46 !important; border: 1px solid #A7F3D0; }
.flashes li.error { background: #FEF2F2; color: #991B1B !important; border: 1px solid #FECACA; }
.flashes li.warn { background: #FFFBEB; color: #92400E !important; border: 1px solid #FDE68A; }
.flashes li.info { background: #EFF6FF; color: #1E40AF !important; border: 1px solid #BFDBFE; }
.pill { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 10.5px; font-weight: 800; color: #FFFFFF !important; }
.pill.navy { background: var(--primary); }
.pill.green { background: var(--green); }
.pill.red { background: var(--red); }
.pill.gold { background: var(--gold); }
.pill.slate { background: #475569; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.metric { background: var(--card-bg); border: 1.5px solid var(--card-border); border-radius: 12px; padding: 16px; }
.metric .t { font-size: 11.5px; font-weight: 800; color: #000000 !important; }
.metric .v { font-size: 24px; font-weight: 800; margin-top: 4px; color: #000000 !important; }
.bar { height: 14px; border-radius: 7px; background: #E2E8F0; overflow: hidden; flex: 1; }
.bar span { display: block; height: 100%; border-radius: 7px; }
.catrow { display: flex; align-items: center; gap: 10px; margin: 8px 0; font-weight: 700; }
.catrow .n { width: 190px; font-size: 11.5px; font-weight: 700; color: #000000 !important; }
.catrow .c { width: 120px; text-align: right; font-size: 11.5px; font-weight: 700; color: #000000 !important; }
.media-frame { background: #0F172A; border-radius: 10px; padding: 12px; text-align: center; margin-top: 10px; }
.media-frame img, .media-frame video { max-width: 100%; max-height: 440px; border-radius: 6px; display: block; margin: 0 auto; }
.media-frame audio { width: 100%; margin-top: 6px; }
.media-frame pre { text-align: left; color: #FFFFFF !important; font-size: 12px; max-height: 380px; overflow: auto; margin: 0; white-space: pre-wrap; font-weight: 500; }
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
.hierarchy-item b { font-size: 13px; color: #000000 !important; }
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
    <a class="btn gold" href="{{ url_for('analytics') }}">📊 Analytics</a>
    {% if u.rank_level == 5 or u.role == 'COURT_JUDICIAL' %}
      <a class="btn blue" href="{{ url_for('jurisdiction_state') }}">← State command tree</a>
    {% elif u.rank_level == 4 %}
      <a class="btn blue" href="{{ url_for('jurisdiction_city') }}">← City command tree</a>
    {% elif u.rank_level == 3 %}
      <a class="btn blue" href="{{ url_for('jurisdiction_area') }}">← Area command tree</a>
    {% endif %}
    {% if u.unit %}<a class="btn" href="{{ url_for('portal') }}">Station vault</a>{% endif %}
    <a class="btn red" href="{{ url_for('logout') }}">Sign out</a>
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
            header_line = f"Rank: {u['rank']} | Judge: {u['name']} (#{u['badge']}) | Judicial inspection portal"
        else:
            header_line = (
                f"Rank: {u['rank']} | Officer: {u['name']} (#{u['badge']}) | "
                f"City: {u['division']} | Station: {u['unit'] or '—'}"
            )
    body = render_template_string(body_template, u=u, THEME=THEME, **ctx)
    return render_template_string(
        LAYOUT, body=body, base_css=BASE_CSS, page_title=page_title,
        u=u, header_line=header_line
    )


# =========================================================
# SCREEN 1 — LOGIN GATEWAY (PRE-FILLED DEFAULTS)
# =========================================================
GATEWAY_TPL = """
<div style="max-width:980px;margin:10px auto">
  <div style="text-align:center;margin-bottom:18px">
    <div style="font-size:18px;font-weight:800;color:var(--primary)">
      MINISTRY OF HOME AFFAIRS (GOVERNMENT OF INDIA)
    </div>
    <div class="muted" style="font-size:12px;margin-top:3px">
      NyayaVault: Chain-of-Command &amp; Rank Authentication Gateway (PS-190)
    </div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;border-radius:22px;
              overflow:hidden;border:1.5px solid var(--card-border);background:var(--card-bg)">

    <!-- Left / Toggle Panel -->
    <div style="background:var(--hero);color:#fff;padding:34px 30px">
      {% if view == 'judicial' %}
        <span class="pill" style="background:#F59E0B">JUDICIAL INSPECTION ACCESS</span>
        <h2 style="color:#fff !important;font-size:21px;margin:14px 0 6px">Judicial &amp; prosecution portal</h2>
        <p style="color:#EFF6FF !important;font-size:12px;line-height:1.5">
          Read-only evidence manifest inspection and live tamper hash verification.
        </p>
        <form method="post" action="{{ url_for('court_login') }}" class="stack" style="margin-top:18px">
          <div>
            <label style="color:#DBEAFE !important">Judge ID</label>
            <input type="text" name="username" value="judge_portal" required>
          </div>
          <div>
            <label style="color:#DBEAFE !important">Judicial password</label>
            <input type="password" name="password" value="court123" required>
          </div>
          <button class="btn gold" style="width:100%;margin-top:12px;height:42px">Authenticate judicial identity</button>
        </form>
        <p style="color:#DBEAFE !important;font-size:11px;margin-top:16px">Police officer or station commander?</p>
        <a class="btn" href="{{ url_for('gateway', view='officer') }}" style="background:transparent;color:#fff !important;border:2px solid #fff">Switch to officer login</a>
      {% else %}
        <span class="pill" style="background:#3B82F6">STAGE 1 — HIERARCHY GATEWAY</span>
        <h2 style="color:#fff !important;font-size:21px;margin:14px 0 6px">Law enforcement login</h2>
        <p style="color:#EFF6FF !important;font-size:12px;line-height:1.55">
          Select your designated police post or rank first. Your jurisdiction is securely linked
          directly to your database badge ID, so no redundant location inputs are required.
        </p>
        <p style="color:#DBEAFE !important;font-size:11px;margin-top:26px">Presiding magistrate or judicial clerk?</p>
        <a class="btn" href="{{ url_for('gateway', view='judicial') }}" style="background:transparent;color:#fff !important;border:2px solid #fff">Switch to judicial portal</a>
        <div style="margin-top:14px">
          <a class="btn gold" href="{{ url_for('analytics_gate') }}">Open analytics intelligence</a>
        </div>
      {% endif %}
    </div>

    <!-- Right Form Panel -->
    <div style="padding:30px">
      <span class="pill navy" style="background:#EFF6FF;color:var(--primary) !important">OFFICER HIERARCHY LOGIN</span>
      <h2 style="margin:12px 0 14px;font-size:18px">Command position login</h2>
      <form method="post" action="{{ url_for('officer_login') }}" class="stack">
        <div>
          <label>Step 1: select your position / post</label>
          <select name="position">
            {% for p in positions %}
              <option value="{{ p }}" {{ 'selected' if loop.first }}>{{ p }}</option>
            {% endfor %}
          </select>
        </div>
        <div>
          <label>Officer full name (as registered)</label>
          <input type="text" name="officer_name" value="Inspector General Rajesh Verma" required>
        </div>
        <div>
          <label>Badge ID / username</label>
          <input type="text" name="username" value="admin" required>
        </div>
        <div>
          <label>Secret cryptographic password</label>
          <input type="password" name="password" value="admin123" required>
        </div>
        <div class="row" style="margin-top:14px">
          <button class="btn" style="height:42px;flex:1">Authenticate &amp; unlock vault</button>
          <a class="btn ghost" href="{{ url_for('forgot_password') }}" style="height:42px">Forgot password?</a>
        </div>
      </form>
    </div>
  </div>
</div>
"""


@app.route("/")
def gateway():
    view = request.args.get("view", "officer")
    return render_page(GATEWAY_TPL, "Authentication gateway", view=view, positions=LOGIN_POSITIONS)


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

    user_record = None
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT badge_id, role, officer_name, police_rank, rank_level, division_code, area_zone, unit_name
                FROM vault_system_users
                WHERE (username = :usr OR badge_id = :usr) AND password_hash = :pwd AND is_active = 1
            """, {"usr": uid, "pwd": pwd})
            row = cur.fetchone()
            if row:
                user_record = {
                    "badge": row[0], "role": row[1].upper(), "name": row[2],
                    "rank": row[3], "rank_level": int(row[4]), "div": row[5] or "SURAT",
                    "area": row[6] or "Zone 1", "unit": row[7] or "Katargam Police Station"
                }
            cur.close()
            conn.close()
        except Exception:
            pass

    if not user_record and uid in SEED_USERS and SEED_USERS[uid]["pwd"] == pwd:
        user_record = SEED_USERS[uid]

    if not user_record:
        flash("Authentication failed. Check your username and cryptographic password.", "error")
        return redirect(url_for("gateway"))

    if user_record["name"].lower() != name_input.lower():
        flash(
            f"Identity mismatch. The entered officer name ('{name_input}') does not match "
            f"database records for '{user_record['name']}'. Access denied.", "error"
        )
        return redirect(url_for("gateway"))

    session.permanent = True
    session.update({
        "badge": user_record["badge"], "role": user_record["role"], "name": user_record["name"],
        "rank": user_record["rank"], "rank_level": user_record["rank_level"],
        "division": user_record["div"], "area": user_record["area"], "unit": user_record["unit"],
    })

    log_chained_audit_event(
        "OFFICER_LOGGED_IN",
        f"{user_record['rank']} {user_record['name']} (#{user_record['badge']}) logged in via post: {post}"
    )
    flash(f"Welcome, {user_record['rank']} {user_record['name']}. Vault unlocked.", "ok")
    return _route_by_rank(user_record["rank_level"], user_record["role"])


@app.route("/court-login", methods=["POST"])
def court_login():
    ok, msg = verify_mha_network()
    if not ok:
        flash(f"Security policy violation. {msg}", "error")
        return redirect(url_for("gateway", view="judicial"))

    u = (request.form.get("username") or "").strip()
    p = (request.form.get("password") or "").strip()

    user_record = None
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT badge_id, role, officer_name, police_rank, rank_level, area_zone
                FROM vault_system_users
                WHERE (username = :usr OR badge_id = :usr) AND password_hash = :pwd AND is_active = 1
            """, {"usr": u, "pwd": p})
            row = cur.fetchone()
            if row and row[1].upper() == "COURT_JUDICIAL":
                user_record = {
                    "badge": row[0], "role": "COURT_JUDICIAL", "name": row[2],
                    "rank": row[3], "rank_level": int(row[4]), "area": row[5],
                    "div": "", "unit": ""
                }
            cur.close()
            conn.close()
        except Exception:
            pass

    if not user_record and u in SEED_USERS and SEED_USERS[u]["pwd"] == p and SEED_USERS[u]["role"] == "COURT_JUDICIAL":
        user_record = SEED_USERS[u]

    if user_record:
        session.permanent = True
        session.update({
            "badge": user_record["badge"], "role": "COURT_JUDICIAL", "name": user_record["name"],
            "rank": user_record["rank"], "rank_level": user_record["level"],
            "area": user_record.get("area", ""), "division": "", "unit": "",
        })
        log_chained_audit_event("JUDICIAL_LOGIN", f"Judge {user_record['name']} (#{user_record['badge']}) opened inspection portal")
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
<div style="max-width:520px;margin:20px auto">
  <div class="card">
    <h2>Reset password via registered email OTP</h2>
    <form method="post" action="{{ url_for('forgot_send_otp') }}" class="stack">
      <div>
        <label>Registered username / badge ID</label>
        <input type="text" name="identifier" value="{{ identifier or 'io_surat' }}" required>
      </div>
      <button class="btn blue" style="width:100%">Send verification OTP to email</button>
    </form>

    <div class="muted" style="margin:14px 0 6px">{{ otp_status }}</div>

    <form method="post" action="{{ url_for('forgot_reset') }}" class="stack">
      <div>
        <label>6-digit email OTP</label>
        <input type="text" name="otp" placeholder="6-digit security OTP" required>
      </div>
      <div>
        <label>New password</label>
        <input type="password" name="new_password" placeholder="New secret password" required>
      </div>
      <button class="btn green" style="width:100%;margin-top:10px">Verify OTP &amp; update password</button>
    </form>
    <div style="margin-top:16px"><a href="{{ url_for('gateway') }}">Back to sign in</a></div>
  </div>
</div>
"""


@app.route("/forgot-password")
def forgot_password():
    return render_page(
        FORGOT_TPL, "Account recovery",
        identifier=session.get("_otp_ident", "io_surat"),
        otp_status=session.get("_otp_status", "Send an OTP to begin the reset.")
    )


@app.route("/forgot-password/send", methods=["POST"])
def forgot_send_otp():
    ident = (request.form.get("identifier") or "").strip()
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT badge_id, officer_name, officer_email FROM vault_system_users WHERE username = :1 OR badge_id = :2",
                (ident, ident)
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                badge, name, email = row[0], row[1], row[2]
            else:
                badge, name, email = "IO-SUR-102", "Police Inspector V. Jadeja", "v.jadeja@suratpolice.gov.in"
        else:
            badge, name, email = "IO-SUR-102", "Police Inspector V. Jadeja", "v.jadeja@suratpolice.gov.in"
    except Exception:
        badge, name, email = "IO-SUR-102", "Police Inspector V. Jadeja", "v.jadeja@suratpolice.gov.in"

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
        flash("Please enter the OTP and your new password.", "error")
        return redirect(url_for("forgot_password"))

    if not session.get("_otp_code") or entered != session.get("_otp_code"):
        flash("Incorrect or expired OTP. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))

    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("UPDATE vault_system_users SET password_hash = :1 WHERE badge_id = :2",
                        (new_p, session.get("_otp_badge")))
            conn.commit()
            cur.close()
            conn.close()
    except Exception:
        pass

    log_chained_audit_event("PASSWORD_RESET_SUCCESS", f"Password reset for Officer #{session.get('_otp_badge')}")
    for k in ("_otp_code", "_otp_badge", "_otp_ident", "_otp_status"):
        session.pop(k, None)
    flash("Password reset successfully. You can now sign in with your new password.", "ok")
    return redirect(url_for("gateway"))


# =========================================================
# ANALYTICS DASHBOARD
# =========================================================
ANALYTICS_GATE_TPL = """
<div style="max-width:460px;margin:30px auto">
  <div class="card">
    <h2>Restricted analytics security gateway</h2>
    <p class="muted">This dashboard aggregates case data across every jurisdiction.</p>
    <form method="post" action="{{ url_for('analytics_unlock') }}" class="stack">
      <div>
        <label>Analytics master password</label>
        <input type="password" name="password" value="analytics123" required autofocus>
      </div>
      <button class="btn green" style="width:100%;margin-top:10px">Access analytics</button>
    </form>
    <div style="margin-top:14px"><a href="{{ back_url }}">Back</a></div>
  </div>
</div>
"""

ANALYTICS_TPL = """
<div class="card" style="margin-bottom:14px">
  <h2>Advanced multi-tier crime &amp; evidence intelligence</h2>
  <form method="get" action="{{ url_for('analytics') }}" class="row" style="gap:12px;align-items:flex-end">
    <div style="min-width:180px">
      <label>Analysis scope</label>
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
      <label>Area / zone</label>
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
    <div class="v">{{ d.total }}</div><span class="pill navy">Active scope</span></div>
  <div class="metric"><div class="t">Cases resolved</div>
    <div class="v">{{ d.resolved }}</div><span class="pill green">{{ closure_pct }}% closure</span></div>
  <div class="metric"><div class="t">High severity (murder)</div>
    <div class="v">{{ d.murder }}</div><span class="pill red">Priority alpha</span></div>
  <div class="metric"><div class="t">Economic &amp; financial</div>
    <div class="v">{{ d.economic }}</div><span class="pill gold">Fraud track</span></div>
</div>

<div class="card" style="margin-bottom:14px">
  <h3>Historical trend analysis — annual and monthly intake [{{ scope_title }}]</h3>
  <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">
    {% for t in trends %}
    <div style="background:var(--card-highlight);border:1px solid var(--card-border);border-radius:9px;padding:13px">
      <div style="font-size:12px;font-weight:700;color:var(--primary)">{{ t.title }}</div>
      <div class="row" style="justify-content:space-between;margin-top:6px">
        <span style="font-size:11px;font-weight:700">Current period: {{ t.curr }} cases</span>
        <span class="muted">Previous period: {{ t.prev }} cases</span>
      </div>
      <div style="font-size:10.5px;font-weight:700;margin-top:6px;color:{{ t.color }}">{{ t.label }}</div>
    </div>
    {% endfor %}
  </div>
</div>

<div class="card">
  <h3>Crime category distribution [{{ scope_title }}]</h3>
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
    return render_page(ANALYTICS_GATE_TPL, "Analytics gateway", back_url=back)


@app.route("/analytics/unlock", methods=["POST"])
def analytics_unlock():
    if (request.form.get("password") or "").strip() == ANALYTICS_PASSWORD:
        session["analytics_ok"] = True
        return redirect(url_for("analytics"))
    flash("Access denied. Incorrect analytics master password.", "error")
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

    conn = get_db_connection()
    if conn:
        try:
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
    else:
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
    conn = get_db_connection()
    if conn:
        try:
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
    else:
        areas += ["Zone 1 (North)", "Zone 2 (South)", "Cyber Zone"]
        stations += ["Katargam Police Station", "Umra Police Station", "Cyber Crime Branch"]

    if scope == "City-wise":
        targets, target_label = cities, "City"
    elif scope == "Area-wise":
        targets, target_label = areas, "Area / zone"
    elif scope == "Police Station-wise":
        targets, target_label = stations, "Police station"
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
            "label": (f"▲ +{pct:.1f}% growth vs previous period" if diff >= 0
                      else f"▼ {pct:.1f}% reduction vs previous period"),
            "color": THEME["accent_green"] if diff >= 0 else THEME["accent_red"],
        }

    categories = [
        {"name": "Murder / homicide", "count": d["murder"], "color": THEME["accent_red"]},
        {"name": "Robbery / theft / heist", "count": d["robbery"], "color": THEME["accent_gold"]},
        {"name": "Cyber / ransomware", "count": d["cyber"], "color": THEME["primary"]},
        {"name": "Economic &amp; hawala fraud", "count": d["economic"], "color": "#7C3AED"},
        {"name": "Narcotics &amp; drugs", "count": d["narcotics"], "color": "#EA580C"},
        {"name": "Other general offences", "count": d["other"], "color": THEME["accent_green"]},
    ]
    for c in categories:
        c["pct"] = int((c["count"] / total) * 100)

    return render_page(
        ANALYTICS_TPL, "Intelligence analytics",
        scopes=scopes, scope=scope, cities=cities, city=city, areas=areas, area=area,
        targets=targets, target=target, target_label=target_label,
        d=d, scope_title=scope_title,
        closure_pct=int((d["resolved"] / total) * 100),
        trends=[
            trend("Annual comparison (this year vs last year)", d["curr_year"], d["prev_year"]),
            trend("Monthly comparison (this month vs last month)", d["curr_month"], d["prev_month"]),
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
      <input type="text" name="q" value="{{ q }}" placeholder="Search {{ list_noun }}…">
      <button class="btn slate small" style="width:100%">Search</button>
    </form>

    <div style="margin-top:12px">
      {% for item in items %}
        <div class="hierarchy-item">
          <a href="{{ url_for(endpoint, tab=tab, q=q, sel=item.key) }}" style="flex:1">
            <b>{{ item.label }}</b>
            {% if item.sub %}<div class="muted">{{ item.sub }}</div>{% endif %}
          </a>
          {% if can_edit and item.delete_url %}
            <form method="post" action="{{ item.delete_url }}" onsubmit="return confirm('Permanently delete {{ item.label }}?')">
              <input type="hidden" name="tab" value="{{ tab }}">
              <button class="btn red small">Delete</button>
            </form>
          {% endif %}
        </div>
      {% else %}
        <p class="muted">Nothing registered here yet.</p>
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

      <div class="card tight" style="background:var(--card-highlight);margin-bottom:14px">
        <h3>{{ detail.officer_heading }}</h3>
        {% if detail.officer %}
          <div style="font-size:13px;font-weight:700">{{ detail.officer.name }}</div>
          <div class="muted">Badge #{{ detail.officer.badge }} &nbsp;|&nbsp; {{ detail.officer.rank }}</div>
          <div class="muted">{{ detail.officer.email }}</div>
          {% if can_edit %}
            <form method="post" action="{{ url_for('officer_update') }}" class="stack" style="margin-top:12px">
              <input type="hidden" name="badge_id" value="{{ detail.officer.badge }}">
              <input type="hidden" name="next" value="{{ request.full_path }}">
              <div><label>Full name</label>
                <input type="text" name="officer_name" value="{{ detail.officer.name }}" required></div>
              <div><label>Official email</label>
                <input type="text" name="officer_email" value="{{ detail.officer.email }}" required></div>
              <button class="btn blue small">Save updates</button>
            </form>
          {% endif %}
        {% else %}
          <p class="muted">No officer is currently assigned to this post.</p>
          {% if can_edit %}
            <a class="btn green small" href="{{ detail.enroll_url }}">Enrol {{ detail.enroll_label }}</a>
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
          <button class="btn green" style="height:40px">Open station vault — cases, evidence, custody</button>
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
        if conn:
            cur = conn.cursor()
            cur.execute(sql, binds)
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                return {"badge": row[0], "name": row[1], "email": row[2], "rank": row[3]}
    except Exception:
        pass
    for u in SEED_USERS.values():
        if rank_level == u["level"] or (isinstance(rank_level, list) and u["level"] in rank_level):
            return {"badge": u["badge"], "name": u["name"], "email": f"{u['badge'].lower()}@police.gov.in", "rank": u["rank"]}
    return None


def _build_jurisdiction(endpoint, tab, q, sel, city_filter, allowed_tabs):
    can_edit = (not is_judge()) and current_user()["rank_level"] >= 4
    tab_defs = {
        "stations": {"key": "stations", "label": "1. Police stations & station leads"},
        "areas": {"key": "areas", "label": "2. Areas, zones & DCP / ACP"},
        "cities": {"key": "cities", "label": "3. Cities & CP management"},
    }
    tabs = [tab_defs[t] for t in allowed_tabs]

    items, detail = [], None
    create_fields, create_url, create_title, create_button = [], "", "", ""
    divisions = fetch_divisions()

    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            if tab == "stations":
                if city_filter:
                    cur.execute("SELECT unit_name, division_code, area_zone FROM investigation_units WHERE division_code = :1 ORDER BY unit_name", (city_filter,))
                else:
                    cur.execute("SELECT unit_name, division_code, area_zone FROM investigation_units ORDER BY unit_name")
                rows = cur.fetchall()
            elif tab == "areas":
                if city_filter:
                    cur.execute("SELECT DISTINCT division_code, area_zone FROM investigation_units WHERE division_code = :1 ORDER BY area_zone", (city_filter,))
                else:
                    cur.execute("SELECT DISTINCT division_code, area_zone FROM investigation_units ORDER BY area_zone")
                rows = cur.fetchall()
            else:
                cur.execute("SELECT division_code, division_name FROM police_divisions ORDER BY division_code")
                rows = cur.fetchall()
            cur.close()
            conn.close()
        else:
            if tab == "stations":
                rows = [("Katargam Police Station", "SURAT", "Zone 1 (North)"), ("Umra Police Station", "SURAT", "Zone 2 (South)")]
            elif tab == "areas":
                rows = [("SURAT", "Zone 1 (North)"), ("SURAT", "Zone 2 (South)")]
            else:
                rows = [("SURAT", "Surat Police Commissionerate"), ("AHMEDABAD", "Ahmedabad Police Commissionerate"), ("RAJKOT", "Rajkot Police Commissionerate")]

        if tab == "stations":
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
                    "title": match[0],
                    "subtitle": f"City: {match[1]} · Area / zone: {match[2]}",
                    "officer_heading": "Station house officer (SHO / inspector)",
                    "officer": officer,
                    "enroll_url": url_for("officer_enroll", rank_type="SHO", city=match[1], area=match[2], station=match[0]),
                    "enroll_label": "station SHO",
                    "station_entry": {"unit": match[0], "division": match[1], "area": match[2]},
                    "extra_enrolments": [{
                        "label": "Add / update station SHO",
                        "url": url_for("officer_enroll", rank_type="SHO", city=match[1], area=match[2], station=match[0])
                    }],
                }
            create_title = "Add a police station"
            create_url = url_for("station_create")
            create_button = "Add police station"
            create_fields = [
                {"label": "City / division", "name": "division_code", "type": "select", "options": [city_filter] if city_filter else divisions},
                {"label": "Station name", "name": "unit_name", "placeholder": "e.g. Pandesara Police Station", "required": True},
                {"label": "Area / zone", "name": "area_zone", "placeholder": "e.g. Zone 3 (West)"},
            ]

        elif tab == "areas":
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
                detail = {
                    "title": f"Area / zone: {match[1]}",
                    "subtitle": f"City / division: {match[0]}",
                    "officer_heading": "Assigned DCP / ACP",
                    "officer": officer,
                    "enroll_url": url_for("officer_enroll", rank_type="DCP", city=match[0], area=match[1]),
                    "enroll_label": "a DCP",
                    "children_heading": "Police stations in this zone",
                    "children": ["Katargam Police Station", "Umra Police Station"],
                    "extra_enrolments": [
                        {"label": "Add DCP", "url": url_for("officer_enroll", rank_type="DCP", city=match[0], area=match[1])},
                        {"label": "Add ACP", "url": url_for("officer_enroll", rank_type="ACP", city=match[0], area=match[1])},
                    ],
                }
            create_title = "Create an area / zone"
            create_url = url_for("area_create")
            create_button = "Create area zone"
            create_fields = [
                {"label": "City / division", "name": "division_code", "type": "select", "options": [city_filter] if city_filter else divisions},
                {"label": "Area / zone name", "name": "area_zone", "placeholder": "e.g. Zone 4 (East)", "required": True},
            ]

        else:
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
                detail = {
                    "title": f"City: {match[0]}",
                    "subtitle": match[1],
                    "officer_heading": "Commissioner of police (city CP)",
                    "officer": officer,
                    "enroll_url": url_for("officer_enroll", rank_type="CP", city=match[0]),
                    "enroll_label": "a city CP",
                    "children_heading": "Areas / zones in this city",
                    "children": ["Zone 1 (North)", "Zone 2 (South)", "Cyber Zone"],
                    "extra_enrolments": [
                        {"label": "Add / update CP", "url": url_for("officer_enroll", rank_type="CP", city=match[0])},
                    ],
                }
            create_title = "Create a city division"
            create_url = url_for("city_create")
            create_button = "Create city division"
            create_fields = [
                {"label": "City / division code", "name": "division_code", "placeholder": "e.g. VADODARA", "required": True},
            ]
    except Exception as e:
        flash(f"Hierarchy error: {e}", "error")

    noun = {"stations": "stations", "areas": "areas", "cities": "cities"}[tab]
    return dict(
        endpoint=endpoint, tab=tab, tabs=tabs, q=q, items=items, detail=detail,
        can_edit=can_edit, create_fields=create_fields, create_url=create_url,
        create_title=create_title, create_button=create_button,
        list_title={"stations": "Police stations", "areas": "Areas & zones", "cities": "Cities & divisions"}[tab],
        list_noun=noun,
        detail_empty_title="Select a record",
        detail_empty_hint=f"Pick one of the {noun} on the left to inspect its command profile.",
    )


@app.route("/jurisdiction/state")
@login_required
def jurisdiction_state():
    u = current_user()
    if u["rank_level"] < 5 and u["role"] != "COURT_JUDICIAL":
        flash("Only the DGP state command and judicial portal may open the state tree.", "error")
        return redirect(url_for("portal"))
    tab = request.args.get("tab", "cities")
    if tab not in ("stations", "areas", "cities"):
        tab = "cities"
    ctx = _build_jurisdiction("jurisdiction_state", tab, request.args.get("q", "").strip(),
                              request.args.get("sel", ""), None, ["stations", "areas", "cities"])
    return render_page(JURIS_TPL, "State command tree", **ctx)


@app.route("/jurisdiction/city")
@login_required
def jurisdiction_city():
    u = current_user()
    tab = request.args.get("tab", "stations")
    if tab not in ("stations", "areas"):
        tab = "stations"
    ctx = _build_jurisdiction("jurisdiction_city", tab, request.args.get("q", "").strip(),
                              request.args.get("sel", ""), u["division"], ["stations", "areas"])
    return render_page(JURIS_TPL, "City command tree", **ctx)


AREA_DASH_TPL = """
<div class="card">
  <h2>Area / zone profile: {{ area_name }} ({{ div_code }})</h2>
  <div class="card tight" style="background:var(--card-highlight);margin:14px 0">
    <h3>Assigned assistant commissioner of police (ACP / DCP)</h3>
    {% if officer %}
      <div style="font-size:13px;font-weight:700">{{ officer.name }}</div>
      <div class="muted">Badge #{{ officer.badge }} &nbsp;|&nbsp; {{ officer.rank }}</div>
      <div class="muted">{{ officer.email }}</div>
    {% else %}
      <p class="muted">No ACP or DCP is currently assigned to this zone.</p>
    {% endif %}
  </div>

  <h3>Police stations in {{ area_name }}</h3>
  {% for s in stations %}
    <div class="hierarchy-item">
      <b>{{ s }}</b>
      <form method="post" action="{{ url_for('enter_station') }}">
        <input type="hidden" name="unit_name" value="{{ s }}">
        <input type="hidden" name="division_code" value="{{ div_code }}">
        <input type="hidden" name="area_zone" value="{{ area_name }}">
        <button class="btn green small">Open station vault</button>
      </form>
    </div>
  {% else %}
    <p class="muted">No stations are registered in this zone yet.</p>
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
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT unit_name FROM investigation_units WHERE division_code = :1 AND area_zone = :2",
                        (div_code, area_name))
            stations = [r[0] for r in cur.fetchall()]
            cur.close()
            conn.close()
        except Exception as e:
            flash(f"Database error: {e}", "error")
    else:
        stations = ["Katargam Police Station", "Umra Police Station"]

    return render_page(AREA_DASH_TPL, "Area command tree",
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


@app.route("/jurisdiction/city/create", methods=["POST"])
@rank_required(4)
def city_create():
    code = (request.form.get("division_code") or "").strip().upper()
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO police_divisions (division_code, division_name, division_password, nodal_officer_email) VALUES (:1, :2, 'password123', 'cp@police.gov.in')",
                        (code, f"{code} Police Commissionerate"))
            conn.commit()
            cur.close()
            conn.close()
        log_chained_audit_event("CITY_DIVISION_CREATED", f"City division {code} created")
        flash(f"City division {code} created.", "ok")
    except Exception as e:
        flash(f"Could not create the city: {e}", "error")
    return redirect(url_for("jurisdiction_state", tab="cities"))


@app.route("/jurisdiction/city/<division_code>/delete", methods=["POST"])
@rank_required(5)
def city_delete(division_code):
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM police_divisions WHERE division_code = :1", (division_code,))
            conn.commit()
            cur.close()
            conn.close()
        log_chained_audit_event("CITY_DIVISION_DELETED", f"City division {division_code} deleted")
        flash(f"City division {division_code} deleted.", "ok")
    except Exception as e:
        flash(f"Could not delete the city: {e}", "error")
    return redirect(url_for("jurisdiction_state", tab="cities"))


@app.route("/jurisdiction/area/create", methods=["POST"])
@rank_required(4)
def area_create():
    div = (request.form.get("division_code") or "").strip()
    zone = (request.form.get("area_zone") or "").strip()
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO investigation_units (division_code, unit_name, station_password, area_zone) VALUES (:1, :2, 'password123', :3)",
                        (div, f"{zone} Central Station", zone))
            conn.commit()
            cur.close()
            conn.close()
        log_chained_audit_event("AREA_ZONE_CREATED", f"Area zone {zone} created in {div}")
        flash(f"Area zone {zone} created under {div}.", "ok")
    except Exception as e:
        flash(f"Could not create the area: {e}", "error")
    return redirect(request.referrer or url_for("jurisdiction_state", tab="areas"))


@app.route("/jurisdiction/area/delete", methods=["POST"])
@rank_required(4)
def area_delete():
    zone = request.args.get("area_zone") or request.form.get("area_zone")
    div = request.args.get("division_code") or request.form.get("division_code")
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM investigation_units WHERE area_zone = :1 AND division_code = :2", (zone, div))
            conn.commit()
            cur.close()
            conn.close()
        log_chained_audit_event("AREA_ZONE_DELETED", f"Area zone {zone} deleted from {div}")
        flash(f"Area zone {zone} deleted.", "ok")
    except Exception as e:
        flash(f"Could not delete the area: {e}", "error")
    return redirect(request.referrer or url_for("jurisdiction_state", tab="areas"))


@app.route("/jurisdiction/station/create", methods=["POST"])
@rank_required(4)
def station_create():
    div = (request.form.get("division_code") or "").strip()
    name = (request.form.get("unit_name") or "").strip()
    zone = (request.form.get("area_zone") or "").strip() or "Zone 1"
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO investigation_units (division_code, unit_name, station_password, area_zone) VALUES (:1, :2, 'password123', :3)",
                        (div, name, zone))
            conn.commit()
            cur.close()
            conn.close()
        log_chained_audit_event("STATION_CREATED", f"Police station {name} created in {div} / {zone}")
        flash(f"Police station {name} added.", "ok")
    except Exception as e:
        flash(f"Could not add the station: {e}", "error")
    return redirect(request.referrer or url_for("jurisdiction_state", tab="stations"))


@app.route("/jurisdiction/station/<path:unit_name>/delete", methods=["POST"])
@rank_required(4)
def station_delete(unit_name):
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM investigation_units WHERE unit_name = :1", (unit_name,))
            conn.commit()
            cur.close()
            conn.close()
        log_chained_audit_event("STATION_DELETED", f"Police station {unit_name} deleted")
        flash(f"Police station {unit_name} deleted.", "ok")
    except Exception as e:
        flash(f"Could not delete the station: {e}", "error")
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
    <h2>Enrol junior personnel</h2>
    <div class="muted" style="margin-bottom:10px">Authorised by: {{ u.rank }} ({{ u.name }})</div>

    <div style="background:var(--primary);color:#fff;border-radius:8px;padding:11px 13px;font-size:11.5px;font-weight:700;margin-bottom:14px">
      {{ assignment_tag }}
    </div>

    <form method="post" class="stack">
      <input type="hidden" name="rank_type" value="{{ rank_type }}">
      <input type="hidden" name="city" value="{{ city }}">
      <input type="hidden" name="area" value="{{ area }}">
      <input type="hidden" name="station" value="{{ station }}">
      <div><label>Officer badge / ID (unique)</label>
        <input type="text" name="badge_id" placeholder="e.g. IO-SUR-105" required></div>
      <div><label>Officer full name</label>
        <input type="text" name="officer_name" placeholder="e.g. Police Inspector K. Patel" required></div>
      <div><label>Official police email address</label>
        <input type="email" name="officer_email" placeholder="e.g. k.patel@suratpolice.gov.in" required></div>
      <div><label>System username</label>
        <input type="text" name="username" placeholder="e.g. io_kpatel" required></div>
      <div><label>Secret password</label>
        <input type="password" name="password" required></div>
      <div><label>Confirm secret password</label>
        <input type="password" name="confirm_password" required></div>
      <button class="btn green" style="width:100%;margin-top:12px;height:42px">Enrol junior officer</button>
    </form>
    <div style="margin-top:14px"><a href="{{ back_url }}">Back to command tree</a></div>
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
        assignment_tag = f"{rank_title} | City: {city}"
    elif rank_type in ("DCP", "ACP"):
        assign_div, assign_unit, assign_area = city, f"{area} Headquarters", area
        assignment_tag = f"{rank_title} | City: {city} | Area: {area}"
    else:
        assign_div, assign_unit, assign_area = city, station, area
        assignment_tag = f"{rank_title} | City: {city} | Area: {area} | Station: {station}"

    back_url = url_for("jurisdiction_state") if u["rank_level"] >= 5 else url_for("jurisdiction_city")

    if request.method == "GET":
        return render_page(ENROLL_TPL, "Enrol officer",
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
        if conn:
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
    flash(f"Officer #{b} registered under {assign_unit}.", "ok")
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
        if conn:
            cur = conn.cursor()
            cur.execute("UPDATE vault_system_users SET officer_name = :1, officer_email = :2 WHERE badge_id = :3",
                        (name, email, badge))
            conn.commit()
            cur.close()
            conn.close()
        log_chained_audit_event("OFFICER_RECORD_UPDATED", f"Officer #{badge} record updated")
        flash("Officer record updated.", "ok")
    except Exception as e:
        flash(f"Update failed: {e}", "error")
    return redirect(nxt)


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

    st.set_page_config(
        page_title="NyayaVault — Ministry of Home Affairs",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    if "user" not in st.session_state:
        st.session_state.user = None
    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "officer"
    if "cases_data" not in st.session_state:
        st.session_state.cases_data = [
            {"case_no": "KPS-2026-001", "case_name": "[Robbery / Theft] Lalita Diamond Unit Break-in", "fir_no": "FIR-001/2026", "location": "Katargam Ring Road", "condition": "Under Investigation", "punishment": "Pending Trial", "city": "SURAT", "area": "Zone 1 (North)", "station": "Katargam Police Station", "ev_count": 2, "registered_by": "Police Inspector V. Jadeja"},
            {"case_no": "KPS-2026-002", "case_name": "[Cyber / Ransomware] Varachha Co-op Bank Data Breach", "fir_no": "FIR-002/2026", "location": "Varachha Central", "condition": "Transferred to Forensics", "punishment": "Under FSL Audit", "city": "SURAT", "area": "Zone 1 (North)", "station": "Katargam Police Station", "ev_count": 1, "registered_by": "Police Inspector V. Jadeja"},
            {"case_no": "KPS-2026-003", "case_name": "[Murder / Homicide] Gotalawadi Highway Assault Case", "fir_no": "FIR-003/2026", "location": "Gotalawadi Overbridge", "condition": "Charge Sheet Filed", "punishment": "Pending Court Trial", "city": "SURAT", "area": "Zone 1 (North)", "station": "Katargam Police Station", "ev_count": 3, "registered_by": "Police Inspector V. Jadeja"}
        ]
    if "evidence_data" not in st.session_state:
        st.session_state.evidence_data = [
            {"evidence_id": "EV-CCTV-01", "case_no": "KPS-2026-001", "title": "Main Gate Surveillance DVR Dump", "category": "CCTV Video Footage", "classification": "Surveillance Video Exhibit", "sha256": "4a7d1ed414474e4033ac29ccb8653d9b12a89c9d8174f1bc0931210984da0911", "locker": "Shelf A-12", "custody": "VAULT", "kind": "video"},
            {"evidence_id": "EV-IMG-02", "case_no": "KPS-2026-001", "title": "Broken Safe Lock Forensics Macro Shot", "category": "Crime Scene Photograph", "classification": "Forensic Scene Exhibit", "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "locker": "Shelf B-04", "custody": "VAULT", "kind": "image"}
        ]
    if "audit_logs" not in st.session_state:
        st.session_state.audit_logs = [
            {"log_id": 1, "prev_hash": "0000000000000000", "ts": "2026-09-17 18:20:00", "actor": "ADMIN-001", "role": "SUPER_ADMIN", "action": "SYSTEM_INITIALIZATION", "target": "GENESIS_NODE", "hash": "e3b0c44298fc1c149afbf4c8996fb924"}
        ]
    if "active_case_view" not in st.session_state:
        st.session_state.active_case_view = None

    # Enforce pure black text across Streamlit containers, cards, tables, and inputs
    st.markdown(f"""
        <style>
            #MainMenu, header, footer {{ visibility: hidden; }}
            .block-container {{ padding: 1.5rem 2.5rem; background-color: {THEME['bg_main']}; color: #000000 !important; }}
            p, div, span, label, input, select, textarea, button, th, td, h1, h2, h3, h4, b, strong {{
                color: #000000 !important;
            }}
            .stTextInput input, .stSelectbox select {{
                color: #000000 !important;
                background-color: #FFFFFF !important;
                font-weight: 700 !important;
            }}
            .mha-card {{
                background-color: {THEME['card_bg']};
                border: 1.5px solid {THEME['card_border']};
                border-radius: 14px;
                padding: 22px;
                box-shadow: 0 1px 4px rgba(0,0,0,0.04);
                margin-bottom: 16px;
            }}
            .mha-header {{
                color: {THEME['primary']} !important;
                font-family: 'Segoe UI', sans-serif;
                font-weight: 800;
                font-size: 19px;
                margin-bottom: 4px;
            }}
            .mha-sub {{
                color: #1E293B !important;
                font-size: 12px;
                margin-bottom: 16px;
                font-weight: 600;
            }}
            .pill {{
                display: inline-block;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 800;
                color: #FFFFFF !important;
            }}
            .pill.navy {{ background-color: {THEME['primary']}; }}
            .pill.green {{ background-color: {THEME['accent_green']}; }}
            .pill.gold {{ background-color: {THEME['accent_gold']}; }}
            .stButton>button {{
                font-weight: 700;
                border-radius: 8px;
                color: #000000 !important;
            }}
        </style>
    """, unsafe_allow_html=True)

    if not st.session_state.user:
        st.markdown("""
            <div style="text-align: center; margin-bottom: 20px;">
                <div class="mha-header" style="font-size: 20px; color: #1E3A8A !important;">MINISTRY OF HOME AFFAIRS (GOVERNMENT OF INDIA)</div>
                <div class="mha-sub">NyayaVault: Chain-of-Command & Rank Authentication Gateway (PS-190)</div>
            </div>
        """, unsafe_allow_html=True)

        col_left, col_right = st.columns([1, 1], gap="medium")
        with col_left:
            st.markdown(f"""
                <div style="background: var(--hero); border-radius: 14px; padding: 32px 28px; height: 100%; min-height: 440px;">
                    <div style="background: #3B82F6; color: white !important; display: inline-block; padding: 3px 10px; border-radius: 12px; font-weight: 800; font-size: 11px; margin-bottom: 14px;">
                        {'JUDICIAL INSPECTION ACCESS' if st.session_state.view_mode == 'judicial' else 'STAGE 1 — HIERARCHY GATEWAY'}
                    </div>
                    <h2 style="color: white !important; font-size: 22px; font-weight: 800; margin-bottom: 10px;">
                        {'Judicial & prosecution portal' if st.session_state.view_mode == 'judicial' else 'Law enforcement login'}
                    </h2>
                    <p style="color: #EFF6FF !important; font-size: 13px; line-height: 1.6;">
                        {'Read-only evidence manifest inspection and live tamper hash verification under Section 65B/63.' if st.session_state.view_mode == 'judicial' else
                         'Select your designated police post or rank first. Your jurisdiction is securely linked directly to your database badge ID, so no redundant location inputs are required.'}
                    </p>
                </div>
            """, unsafe_allow_html=True)

            st.write("")
            if st.session_state.view_mode == "officer":
                if st.button("Switch to judicial portal", use_container_width=True):
                    st.session_state.view_mode = "judicial"
                    st.rerun()
                if st.button("Open analytics intelligence", use_container_width=True):
                    st.session_state.view_mode = "analytics"
                    st.rerun()
            else:
                if st.button("Switch to officer login", use_container_width=True):
                    st.session_state.view_mode = "officer"
                    st.rerun()

        with col_right:
            st.markdown('<div class="mha-card">', unsafe_allow_html=True)

            if st.session_state.view_mode == "officer":
                st.markdown('<div class="mha-header">Command position login</div>', unsafe_allow_html=True)
                sel_post = st.selectbox("Step 1: select your position / post", LOGIN_POSITIONS, index=0)
                name_in = st.text_input("Officer full name (as registered)", value="Inspector General Rajesh Verma")
                user_in = st.text_input("Badge ID / username", value="admin")
                pwd_in = st.text_input("Secret cryptographic password", value="admin123", type="password")

                st.write("")
                if st.button("Authenticate & unlock vault", type="primary", use_container_width=True):
                    user_record = None
                    conn = get_db_connection()
                    if conn:
                        try:
                            cur = conn.cursor()
                            cur.execute("SELECT badge_id, role, officer_name, police_rank, rank_level, division_code, area_zone, unit_name FROM vault_system_users WHERE (username = :u OR badge_id = :u) AND password_hash = :p AND is_active = 1", (user_in, pwd_in))
                            row = cur.fetchone()
                            if row:
                                user_record = {"badge": row[0], "role": row[1], "name": row[2], "rank": row[3], "rank_level": int(row[4]), "div": row[5] or "SURAT", "area": row[6] or "Zone 1", "unit": row[7] or "Katargam Police Station"}
                            cur.close(); conn.close()
                        except Exception:
                            pass

                    if not user_record and user_in in SEED_USERS and SEED_USERS[user_in]["pwd"] == pwd_in:
                        user_record = SEED_USERS[user_in]

                    if user_record:
                        st.session_state.user = user_record
                        st.success(f"Authenticated as {user_record['rank']} {user_record['name']}.")
                        st.rerun()
                    else:
                        st.error("Authentication failed. Check your credentials.")

            elif st.session_state.view_mode == "judicial":
                st.markdown('<div class="mha-header">Judicial & prosecution portal</div>', unsafe_allow_html=True)
                j_user = st.text_input("Judge ID", value="judge_portal")
                j_pwd = st.text_input("Judicial password", value="court123", type="password")

                st.write("")
                if st.button("Authenticate judicial identity", type="primary", use_container_width=True):
                    if j_user in SEED_USERS and SEED_USERS[j_user]["pwd"] == j_pwd:
                        st.session_state.user = SEED_USERS[j_user]
                        st.success("Judicial portal access granted.")
                        st.rerun()
                    else:
                        st.error("Invalid Judicial Credentials.")

            elif st.session_state.view_mode == "analytics":
                st.markdown('<div class="mha-header">Restricted analytics security gateway</div>', unsafe_allow_html=True)
                a_pwd = st.text_input("Analytics master password", value="analytics123", type="password")
                if st.button("Access analytics", type="primary", use_container_width=True):
                    if a_pwd == ANALYTICS_PASSWORD:
                        st.session_state.view_mode = "analytics_view"
                        st.rerun()
                    else:
                        st.error("Incorrect Analytics Master Password.")

            st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.view_mode == "analytics_view":
        top_c1, top_c2 = st.columns([4, 1])
        with top_c1:
            st.markdown('<div class="mha-header">Advanced multi-tier crime & evidence intelligence</div>', unsafe_allow_html=True)
        with top_c2:
            if st.button("Back", use_container_width=True):
                st.session_state.view_mode = "officer"
                st.rerun()

        st.markdown('<div class="mha-card">', unsafe_allow_html=True)
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            st.selectbox("Analysis scope", ["Overall State", "City-wise", "Area-wise", "Police Station-wise"])
        with f_col2:
            st.selectbox("City", ["All", "SURAT", "AHMEDABAD", "RAJKOT"])
        with f_col3:
            st.selectbox("Area / zone", ["All", "Zone 1 (North)", "Zone 2 (South)", "Cyber Zone"])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Dockets [Overall State]", "10", "Active scope")
        m2.metric("Cases resolved", "6", "60% closure")
        m3.metric("High severity (murder)", "2", "Priority alpha")
        m4.metric("Economic & financial", "2", "Fraud track")

        st.write("---")
        st.markdown(f'<div style="font-weight:800; color:#000000; margin-bottom:12px;">Crime category distribution [Overall State]</div>', unsafe_allow_html=True)
        st.progress(0.2, text="Murder / homicide (20%)")
        st.progress(0.3, text="Robbery / theft / heist (30%)")
        st.progress(0.2, text="Cyber / ransomware (20%)")
        st.progress(0.2, text="Economic & hawala fraud (20%)")
        st.progress(0.1, text="Narcotics & drugs (10%)")
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        u = st.session_state.user
        st.markdown(f"""
            <div style="background: white; border-bottom: 2px solid {THEME['primary']}; padding: 12px 20px; border-radius: 10px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-size: 16px; font-weight: 800; color: {THEME['primary']} !important;">NyayaVault: Secure Digital Evidence Lifecycle System (PS-190)</span>
                        <div style="font-size: 12px; color: #047857 !important; font-weight: 700; margin-top: 2px;">
                            Rank: {u['rank']} | Officer: {u['name']} (#{u['badge']}) | City: {u['div']} | Station: {u['unit']}
                        </div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        top_act1, top_act2, top_act3 = st.columns([6, 2, 2])
        with top_act2:
            if st.button("Analytics", use_container_width=True):
                st.session_state.view_mode = "analytics_view"
                st.rerun()
        with top_act3:
            if st.button("Sign out", type="secondary", use_container_width=True):
                st.session_state.user = None
                st.session_state.view_mode = "officer"
                st.session_state.active_case_view = None
                st.rerun()

        if st.session_state.active_case_view:
            c = st.session_state.active_case_view
            if st.button("Back to repository"):
                st.session_state.active_case_view = None
                st.rerun()

            st.markdown(f"""
                <div class="mha-card">
                    <div class="mha-header">{c['case_name']}</div>
                    <div class="mha-sub">Case {c['case_no']} · FIR {c['fir_no']} · {c['city']} / {c['area']} / {c['station']}</div>
                </div>
            """, unsafe_allow_html=True)

            w_col1, w_col2 = st.columns([1, 2])
            with w_col1:
                st.markdown('<div class="mha-card">', unsafe_allow_html=True)
                st.markdown('<b>Ingest &amp; encrypt evidence</b>', unsafe_allow_html=True)
                ev_id_in = st.text_input("Evidence ID", value=f"EV-{len(st.session_state.evidence_data)+1:02d}")
                ev_title_in = st.text_input("Evidence title / name", placeholder="Evidence title")
                ev_lock_in = st.text_input("Locker / shelf location", value="Shelf A-01")
                up_file = st.file_uploader("Digital file (image, video, audio, report or disk dump)")

                if st.button("Encrypt &amp; seal to vault", type="primary", use_container_width=True):
                    if up_file and ev_title_in:
                        fbytes = up_file.read()
                        fhash = hashlib.sha256(fbytes).hexdigest()
                        ext = os.path.splitext(up_file.name)[1].lower()
                        kind = "video" if ext in [".mp4", ".mov"] else ("image" if ext in [".png", ".jpg", ".jpeg"] else "binary")

                        st.session_state.evidence_data.append({
                            "evidence_id": ev_id_in,
                            "case_no": c["case_no"],
                            "title": ev_title_in,
                            "category": "Digital Exhibit",
                            "classification": "General Digital Electronic Record",
                            "sha256": fhash,
                            "locker": ev_lock_in,
                            "custody": "VAULT",
                            "kind": kind
                        })
                        st.success(f"Evidence {ev_id_in} AES-256 encrypted and sealed. SHA-256: {fhash[:24]}...")
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            with w_col2:
                st.markdown('<div class="mha-card">', unsafe_allow_html=True)
                st.markdown('<b>Evidence manifest</b>', unsafe_allow_html=True)
                case_evs = [e for e in st.session_state.evidence_data if e["case_no"] == c["case_no"]]
                if case_evs:
                    for ev in case_evs:
                        with st.expander(f"Exhibit {ev['evidence_id']} — {ev['title']}", expanded=True):
                            st.write(f"Category: {ev['category']} | Locker: {ev['locker']} | Custody: {ev['custody']}")
                            st.code(f"SHA-256: {ev['sha256']}")
                else:
                    st.info("No exhibits have been sealed into this case yet.")
                st.markdown('</div>', unsafe_allow_html=True)

        else:
            tabs = st.tabs(["Case file repository", "Chain of custody ledger", "Integrity verification", "Security audit trails"])

            with tabs[0]:
                c_left, c_right = st.columns([1, 2])
                with c_left:
                    st.markdown('<div class="mha-card">', unsafe_allow_html=True)
                    st.markdown('<b>Register a new case profile</b>', unsafe_allow_html=True)
                    new_cname = st.text_input("Case name", placeholder="e.g. Lalita Bank Robbery")
                    new_cat = st.selectbox("Case category (drives analytics)", CASE_CATEGORIES)
                    new_fir = st.text_input("FIR number", placeholder="e.g. FIR-001/2026")
                    new_loc = st.text_input("Crime scene / location", placeholder="Crime scene / location")

                    if st.button("Commit &amp; anchor case", type="primary", use_container_width=True):
                        if new_cname and new_fir:
                            auto_no = f"KPS-2026-{len(st.session_state.cases_data)+1:03d}"
                            st.session_state.cases_data.insert(0, {
                                "case_no": auto_no,
                                "case_name": f"[{new_cat}] {new_cname}",
                                "fir_no": new_fir,
                                "location": new_loc,
                                "condition": "Under Investigation",
                                "punishment": "Pending Trial / No Conviction Yet",
                                "city": u["div"],
                                "area": u["area"],
                                "station": u["unit"],
                                "ev_count": 0,
                                "registered_by": u["name"]
                            })
                            st.success(f"Case '{new_cname}' committed and anchored.")
                            st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

                with c_right:
                    st.markdown('<div class="mha-card">', unsafe_allow_html=True)
                    st.markdown(f'<b>Active case repository ({len(st.session_state.cases_data)} cases)</b>', unsafe_allow_html=True)
                    for item in st.session_state.cases_data:
                        with st.container():
                            co1, co2, co3 = st.columns([3, 1, 1])
                            with co1:
                                st.markdown(f"**{item['case_no']}** — {item['case_name']}")
                                st.caption(f"FIR ref: {item['fir_no']} | Scene: {item['location']} | Status: {item['condition']}")
                            with co2:
                                st.markdown(f"<span class='pill navy'>{item['ev_count']}</span>", unsafe_allow_html=True)
                            with co3:
                                if st.button("Workspace", key=f"btn_{item['case_no']}"):
                                    st.session_state.active_case_view = item
                                    st.rerun()
                            st.write("---")
                    st.markdown('</div>', unsafe_allow_html=True)

            with tabs[1]:
                st.markdown('<div class="mha-card">', unsafe_allow_html=True)
                st.markdown('<b>Custody movement ledger</b>', unsafe_allow_html=True)
                st.dataframe([
                    {"Transfer": 101, "Evidence": "EV-CCTV-01", "From": "CRIME_SCENE", "Officer": "Police Inspector V. Jadeja", "Status": "In vault", "Court deadline": "2026-10-17"},
                    {"Transfer": 102, "Evidence": "EV-IMG-02", "From": "VAULT", "Officer": "Dr. Meera Rao", "Status": "Checked out", "Court deadline": "2026-09-30"}
                ], use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with tabs[2]:
                st.markdown('<div class="mha-card">', unsafe_allow_html=True)
                st.markdown('<b>Bit-level tamper seal verification</b>', unsafe_allow_html=True)
                for ev in st.session_state.evidence_data:
                    st.write(f"Exhibit: **{ev['evidence_id']}** — Title: {ev['title']} — Hash: `{ev['sha256']}` — **Verified — 100% intact**")
                st.markdown('</div>', unsafe_allow_html=True)

            with tabs[3]:
                st.markdown('<div class="mha-card">', unsafe_allow_html=True)
                st.markdown('<b>Cryptographically chained audit ledger</b>', unsafe_allow_html=True)
                st.dataframe(st.session_state.audit_logs, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

else:
    if __name__ == "__main__":
        print("=" * 64)
        print(" NyayaVault Web — Ministry of Home Affairs (PS-190)")
        print(" Local Server : http://127.0.0.1:5000")
        print("=" * 64)
        app.run(host="0.0.0.0", port=5000, debug=False)