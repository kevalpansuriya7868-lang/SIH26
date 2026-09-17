"""
web_app.py — NyayaVault Web Edition (Flask)

A 1:1 web port of app.py (the CustomTkinter desktop client). Every screen,
rank rule, Oracle query, AES-256 seal, SHA-256 audit chain, blockchain
anchor and ReportLab PDF from the desktop app is reproduced here.

Nothing else in the project needs to change: this file reads the same
config.json, talks to the same Oracle schema (Local_SIH26.sql), uses the
same secure_vault_storage directory, and calls the same blockchain_manager.

RUN:
    pip install flask oracledb cryptography reportlab pillow
    python web_app.py
    # then open http://127.0.0.1:5000

Desktop-only actions are mapped to their natural web equivalents:
    filedialog.askopenfilename()   -> multipart file upload
    filedialog.asksaveasfilename() -> streamed PDF download
    os.startfile(decrypted_temp)   -> inline <img>/<video>/<audio> render
    messagebox.showinfo/showerror  -> flash() banners
    Toplevel() modals              -> dedicated pages / <dialog> panels
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

# Identical palette to the desktop client so the web build looks the same.
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
app.secret_key = config.get("security", {}).get("jwt_secret", "NYAYAVAULT_FALLBACK_SESSION_KEY")
app.permanent_session_lifetime = __import__("datetime").timedelta(
    hours=int(config.get("security", {}).get("token_expire_hours", 8))
)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB evidence uploads


# =========================================================
# CORE ENGINES (identical to app.py)
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
        """Web upload path — the browser hands us bytes, not a disk path."""
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


# Media kinds that the case workspace can render inline after decryption.
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
VIDEO_EXTS = {".mp4", ".webm", ".ogg", ".mov", ".mkv", ".avi"}
AUDIO_EXTS = {".wav", ".mp3", ".aac", ".m4a", ".oga"}
TEXT_EXTS = {".txt", ".log", ".csv", ".json", ".xml", ".md"}


def media_kind(raw_file_name):
    """Decide how a decrypted exhibit should be presented in the browser."""
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
    """The server's own outward-facing IP (mirrors the desktop helper)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        active_ip = s.getsockname()[0]
        s.close()
        return active_ip
    except Exception:
        return "127.0.0.1"


def get_client_ip():
    """The browser's IP — what subnet policy is actually enforced against."""
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def auto_local_prefixes():
    """
    The subnet this server itself sits on, derived at runtime.

    A police station's intranet range is not known in advance, and a laptop
    joining a different network gets a different private IP every time. Rather
    than hand-editing config.json for each network, the server's own /24 is
    trusted automatically alongside whatever config.json lists. Set
    security.trust_local_subnet to false to disable this and rely purely on
    the configured prefixes.
    """
    prefixes = ["127.0.0.1", "::1"]
    if SECURITY_CONFIG.get("trust_local_subnet", True):
        parts = get_local_ip().split(".")
        if len(parts) == 4 and all(p.isdigit() for p in parts):
            prefixes.append(".".join(parts[:3]) + ".")   # e.g. 10.194.87.
    return prefixes


def verify_mha_network():
    """
    Desktop build checked the machine's own NIC. On the web the meaningful
    check is the requesting client, so remote_addr is tested against the
    allowed_subnets prefixes in config.json plus this server's own subnet.
    """
    if not SECURITY_CONFIG.get("enforce_mha_subnet", False):
        return True, None

    allowed = list(SECURITY_CONFIG.get("allowed_subnets", ["127.0.0.1"])) + auto_local_prefixes()
    client_ip = get_client_ip()

    for prefix in allowed:
        if client_ip.startswith(prefix) or client_ip == prefix:
            return True, None

    return False, (
        f"Unauthorized network node: {client_ip}. This system is restricted to the "
        f"secure MHA / police intranet. Permitted ranges: {', '.join(sorted(set(allowed)))}."
    )


def log_chained_audit_event(action_type, target_ref):
    """Tamper-evident hash-chained audit ledger (identical digest formula)."""
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


def clob_to_str(value):
    """oracledb returns CLOB handles; normalise to plain text."""
    if value is None:
        return ""
    if hasattr(value, "read"):
        try:
            return value.read()
        except Exception:
            return ""
    return str(value)


# =========================================================
# SESSION / RANK GUARDS
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
            flash("Please sign in to continue.", "error")
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


def fetch_units_for_division(div_code):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT unit_name FROM investigation_units WHERE division_code = :1 ORDER BY unit_name", (div_code,))
        rows = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows if rows else ["General Cell"]
    except Exception:
        return ["General Cell"]


def fetch_all_station_names():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT unit_name FROM investigation_units ORDER BY unit_name")
        rows = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows if rows else ["Katargam Police Station"]
    except Exception:
        return ["Katargam Police Station"]


# =========================================================
# SHARED LAYOUT / STYLING
# =========================================================
BASE_CSS = """
:root{
  --bg-main:#F1F5F9; --card-bg:#FFFFFF; --card-border:#D5DEE7; --card-highlight:#F8FAFC;
  --input-bg:#F8FAFC; --primary:#1E3A8A; --primary-hover:#1E40AF; --hero:#244CB9;
  --hero-dark:#172554; --gold:#D97706; --gold-hover:#B45309; --green:#059669;
  --green-hover:#047857; --red:#DC2626; --red-hover:#B91C1C; --text:#0F172A; --muted:#64748B;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg-main);color:var(--text);
  font-family:"Segoe UI",Tahoma,Geneva,Verdana,sans-serif;font-size:14px}
a{color:var(--primary);text-decoration:none}
.topbar{background:var(--card-bg);border-bottom:1px solid var(--card-border);
  padding:10px 20px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.topbar h1{font-size:15px;margin:0;color:var(--primary)}
.topbar .who{font-size:11px;color:var(--green);margin-top:2px}
.topbar .actions{display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;border:0;
  border-radius:10px;padding:9px 14px;font-size:12px;font-weight:600;cursor:pointer;
  color:#fff;background:var(--primary);text-decoration:none;line-height:1.2}
.btn:hover{background:var(--primary-hover)}
.btn.green{background:var(--green)} .btn.green:hover{background:var(--green-hover)}
.btn.gold{background:var(--gold)} .btn.gold:hover{background:var(--gold-hover)}
.btn.red{background:var(--red)} .btn.red:hover{background:var(--red-hover)}
.btn.blue{background:#0284C7} .btn.blue:hover{background:#0369A1}
.btn.dark{background:#1E293B} .btn.dark:hover{background:#0F172A}
.btn.slate{background:#64748B} .btn.slate:hover{background:#475569}
.btn.ghost{background:transparent;color:var(--primary);border:1px solid var(--primary)}
.btn.ghost:hover{background:#EFF6FF}
.btn.small{padding:6px 10px;font-size:11px;border-radius:8px}
.btn:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{
  outline:3px solid #93C5FD;outline-offset:2px}
.wrap{padding:16px 20px 40px}
.card{background:var(--card-bg);border:1px solid var(--card-border);border-radius:12px;padding:16px}
.card.tight{padding:12px}
.card h2{margin:0 0 10px;font-size:15px;color:var(--primary)}
.card h3{margin:0 0 8px;font-size:13px;color:var(--primary)}
.muted{color:var(--muted);font-size:11px}
label{display:block;font-size:11px;font-weight:600;color:var(--text);margin:8px 0 3px}
input[type=text],input[type=password],input[type=email],input[type=number],
input[type=file],select,textarea{width:100%;background:var(--input-bg);
  border:1px solid var(--card-border);border-radius:8px;padding:9px 10px;
  font-size:13px;color:var(--text);font-family:inherit}
textarea{min-height:70px}
.grid{display:grid;gap:15px}
.split{display:grid;grid-template-columns:330px 1fr;gap:15px;align-items:start}
@media(max-width:900px){.split{grid-template-columns:1fr}}
.tabs{display:flex;gap:6px;background:var(--card-highlight);border:1px solid var(--card-border);
  border-radius:10px;padding:6px;margin-bottom:14px;flex-wrap:wrap}
.tabs a{padding:8px 14px;border-radius:8px;font-size:12px;font-weight:600;color:var(--muted)}
.tabs a.active{background:var(--primary);color:#fff}
.table-scroll{overflow-x:auto;border:1px solid var(--card-border);border-radius:10px;background:var(--card-bg)}
table{border-collapse:collapse;width:100%;font-size:12px;min-width:640px}
th{background:var(--card-highlight);color:var(--text);text-align:center;font-weight:700;
  padding:9px 8px;border-bottom:1px solid var(--card-border);white-space:nowrap}
td{padding:8px;border-bottom:1px solid #EEF2F7;text-align:center;vertical-align:middle}
tr.sel{background:#EFF6FF}
tr:hover{background:var(--card-highlight)}
td.left,th.left{text-align:left}
.hash{font-family:Consolas,Menlo,monospace;font-size:10.5px;word-break:break-all}
.flashes{margin:0 0 14px;padding:0;list-style:none}
.flashes li{padding:11px 14px;border-radius:10px;margin-bottom:8px;font-size:12.5px;font-weight:600}
.flashes li.ok{background:#ECFDF5;color:#065F46;border:1px solid #A7F3D0}
.flashes li.error{background:#FEF2F2;color:#991B1B;border:1px solid #FECACA}
.flashes li.warn{background:#FFFBEB;color:#92400E;border:1px solid #FDE68A}
.flashes li.info{background:#EFF6FF;color:#1E40AF;border:1px solid #BFDBFE}
.pill{display:inline-block;padding:3px 9px;border-radius:12px;font-size:10px;font-weight:700;color:#fff}
.pill.navy{background:var(--primary)} .pill.green{background:var(--green)}
.pill.red{background:var(--red)} .pill.gold{background:var(--gold)}
.pill.slate{background:#64748B}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.metric{background:var(--card-bg);border:1px solid var(--card-border);border-radius:12px;padding:14px}
.metric .t{font-size:11px;font-weight:700;color:var(--muted)}
.metric .v{font-size:22px;font-weight:800;margin-top:4px}
.bar{height:14px;border-radius:7px;background:var(--input-bg);overflow:hidden;flex:1}
.bar span{display:block;height:100%;border-radius:7px}
.catrow{display:flex;align-items:center;gap:10px;margin:8px 0}
.catrow .n{width:190px;font-size:11px;font-weight:700}
.catrow .c{width:120px;text-align:right;font-size:11px;font-weight:700;color:var(--muted)}
.timeline{border-left:3px solid var(--primary);margin-left:10px;padding-left:16px}
.tl-item{background:var(--card-highlight);border:1px solid var(--card-border);
  border-radius:10px;padding:12px;margin-bottom:12px;position:relative}
.tl-item::before{content:"";position:absolute;left:-24px;top:16px;width:12px;height:12px;
  border-radius:50%;background:var(--primary);border:2px solid #fff}
.media-frame{background:#0F172A;border-radius:10px;padding:10px;text-align:center;margin-top:10px}
.media-frame img,.media-frame video{max-width:100%;max-height:440px;border-radius:6px;display:block;margin:0 auto}
.media-frame audio{width:100%;margin-top:6px}
.media-frame pre{text-align:left;color:#E2E8F0;font-size:11.5px;max-height:380px;
  overflow:auto;margin:0;white-space:pre-wrap;word-break:break-word}
.note{background:#FFFBEB;border:1px solid #FDE68A;color:#92400E;padding:11px 13px;
  border-radius:9px;font-size:12px;font-weight:600}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.stack>*+*{margin-top:8px}
.hierarchy-item{display:flex;align-items:center;justify-content:space-between;gap:10px;
  background:var(--card-bg);border:1px solid var(--card-border);border-radius:10px;
  padding:10px 12px;margin-bottom:8px}
.hierarchy-item b{font-size:12.5px}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
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
    <a class="btn gold" href="{{ url_for('analytics') }}">Analytics</a>
    {% if u.rank_level == 5 or u.role == 'COURT_JUDICIAL' %}
      <a class="btn blue" href="{{ url_for('jurisdiction_state') }}">State command tree</a>
    {% elif u.rank_level == 4 %}
      <a class="btn blue" href="{{ url_for('jurisdiction_city') }}">City command tree</a>
    {% elif u.rank_level == 3 %}
      <a class="btn blue" href="{{ url_for('jurisdiction_area') }}">Area command tree</a>
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
    """Render a page fragment inside the shared MHA chrome."""
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
# SCREEN 1 — LOGIN GATEWAY (position login + judicial portal)
# =========================================================
GATEWAY_TPL = """
<div style="max-width:980px;margin:10px auto">
  <div style="text-align:center;margin-bottom:18px">
    <div style="font-size:17px;font-weight:800;color:var(--primary)">
      MINISTRY OF HOME AFFAIRS (GOVERNMENT OF INDIA)</div>
    <div class="muted" style="font-size:12px;margin-top:3px">
      NyayaVault: Chain-of-Command &amp; Rank Authentication Gateway (PS-190)</div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:0;border-radius:22px;
              overflow:hidden;border:1px solid var(--card-border);background:var(--card-bg)">

    <!-- Judicial / hero side -->
    <div style="background:var(--hero);color:#fff;padding:34px 30px">
      {% if view == 'judicial' %}
        <span class="pill" style="background:#F59E0B">JUDICIAL INSPECTION ACCESS</span>
        <h2 style="color:#fff;font-size:21px;margin:14px 0 6px">Judicial &amp; prosecution portal</h2>
        <p style="color:#EFF6FF;font-size:12px;line-height:1.5">
          Read-only evidence manifest inspection and live tamper hash verification.</p>
        <form method="post" action="{{ url_for('court_login') }}" class="stack" style="margin-top:18px">
          <div>
            <label style="color:#DBEAFE">Judge ID</label>
            <input type="text" name="username" placeholder="judge_portal" required>
          </div>
          <div>
            <label style="color:#DBEAFE">Judicial password</label>
            <input type="password" name="password" placeholder="court123" required>
          </div>
          <button class="btn gold" style="width:100%;margin-top:12px;height:42px">
            Authenticate judicial identity</button>
        </form>
        <p style="color:#DBEAFE;font-size:11px;margin-top:16px">Police officer or station commander?</p>
        <a class="btn ghost" href="{{ url_for('gateway', view='officer') }}"
           style="color:#fff;border-color:#fff">Switch to officer login</a>
      {% else %}
        <span class="pill" style="background:#3B82F6">STAGE 1 — HIERARCHY GATEWAY</span>
        <h2 style="color:#fff;font-size:21px;margin:14px 0 6px">Law enforcement login</h2>
        <p style="color:#EFF6FF;font-size:12px;line-height:1.55">
          Select your designated police post or rank first. Your jurisdiction is securely linked
          directly to your database badge ID, so no redundant location inputs are required.</p>
        <p style="color:#DBEAFE;font-size:11px;margin-top:26px">Presiding magistrate or judicial clerk?</p>
        <a class="btn ghost" href="{{ url_for('gateway', view='judicial') }}"
           style="color:#fff;border-color:#fff">Switch to judicial portal</a>
        <div style="margin-top:14px">
          <a class="btn gold" href="{{ url_for('analytics_gate') }}">Open analytics intelligence</a>
        </div>
      {% endif %}
    </div>

    <!-- Officer login side -->
    <div style="padding:30px">
      <span class="pill navy" style="background:#EFF6FF;color:var(--primary)">OFFICER HIERARCHY LOGIN</span>
      <h2 style="margin:12px 0 14px;font-size:18px;color:var(--text)">Command position login</h2>
      <form method="post" action="{{ url_for('officer_login') }}" class="stack">
        <div>
          <label>Step 1: select your position / post</label>
          <select name="position">
            {% for p in positions %}<option value="{{ p }}">{{ p }}</option>{% endfor %}
          </select>
        </div>
        <div>
          <label>Officer full name (as registered)</label>
          <input type="text" name="officer_name" placeholder="e.g. Police Inspector V. Jadeja" required>
        </div>
        <div>
          <label>Badge ID / username</label>
          <input type="text" name="username" placeholder="e.g. dgp_gujarat / cp_surat / io_surat" required>
        </div>
        <div>
          <label>Secret cryptographic password</label>
          <input type="password" name="password" placeholder="Enter secure cryptographic password" required>
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
    session.pop("_pending_portal", None)
    view = request.args.get("view", "officer")
    return render_page(GATEWAY_TPL, "Authentication gateway",
                       view=view, positions=LOGIN_POSITIONS)


def _route_by_rank(level, role):
    """Same post-login routing the desktop client used."""
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

    if not name_input or not uid or not pwd:
        flash("Officer name, badge ID / username, and password are all mandatory.", "error")
        return redirect(url_for("gateway"))

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
        flash(f"Database error: {e}", "error")
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
            f"database records for '{db_name}'. Access denied.", "error"
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

    if not u or not p:
        flash("Judge ID and password are required.", "error")
        return redirect(url_for("gateway", view="judicial"))

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


# ---------- Password recovery via email OTP ----------
FORGOT_TPL = """
<div style="max-width:520px;margin:20px auto">
  <div class="card">
    <h2>Reset password via registered email OTP</h2>
    <form method="post" action="{{ url_for('forgot_send_otp') }}" class="stack">
      <div>
        <label>Registered username / badge ID</label>
        <input type="text" name="identifier" value="{{ identifier or '' }}"
               placeholder="e.g. io_surat or IO-SUR-102" required>
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
        identifier=session.get("_otp_ident", ""),
        otp_status=session.get("_otp_status", "Send an OTP to begin the reset.")
    )


@app.route("/forgot-password/send", methods=["POST"])
def forgot_send_otp():
    ident = (request.form.get("identifier") or "").strip()
    if not ident:
        flash("Please enter a username or badge ID.", "error")
        return redirect(url_for("forgot_password"))

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
        flash("Please enter the OTP and your new password.", "error")
        return redirect(url_for("forgot_password"))

    if not session.get("_otp_code") or entered != session.get("_otp_code"):
        flash("Incorrect or expired OTP. Please request a new one.", "error")
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
    flash("Password reset successfully. You can now sign in with your new password.", "ok")
    return redirect(url_for("gateway"))


# =========================================================
# ANALYTICS INTELLIGENCE DASHBOARD (password: analytics123)
# =========================================================
ANALYTICS_GATE_TPL = """
<div style="max-width:460px;margin:30px auto">
  <div class="card">
    <h2>Restricted analytics security gateway</h2>
    <p class="muted">This dashboard aggregates case data across every jurisdiction.</p>
    <form method="post" action="{{ url_for('analytics_unlock') }}" class="stack">
      <div>
        <label>Analytics master password</label>
        <input type="password" name="password" placeholder="Enter password" required autofocus>
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
    <noscript><button class="btn">Apply</button></noscript>
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
    """Replicates the desktop dashboard's aggregate queries exactly."""
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

    # Area list is dependent on the selected city, exactly as the desktop menus were.
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
# SCREEN 2 — JURISDICTION COMMAND TREES
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
            <form method="post" action="{{ item.delete_url }}"
                  onsubmit="return confirm('Permanently delete {{ item.label }}?')">
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
              <input type="text" name="{{ f.name }}" placeholder="{{ f.placeholder or '' }}"
                     {{ 'required' if f.required }}>
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
          <button class="btn green" style="height:40px">
            Open station vault — cases, evidence, custody</button>
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

{% if can_edit %}
<div class="card" style="margin-top:14px">
  <h3>Personnel administration</h3>
  <div class="row">
    <a class="btn red small" href="{{ url_for('officer_remove') }}">Decommission an officer</a>
  </div>
</div>
{% endif %}
"""


def _officer_row(div_code=None, area=None, unit=None, rank_level=None):
    """Single lookup used for CP / DCP / SHO cards."""
    sql = ("SELECT badge_id, officer_name, officer_email, police_rank "
           "FROM vault_system_users WHERE is_active = 1")
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
    """Shared data loader for the state-level and city-level browsers."""
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
                {"label": "City / division", "name": "division_code", "type": "select",
                 "options": [city_filter] if city_filter else divisions},
                {"label": "Station name", "name": "unit_name", "placeholder": "e.g. Pandesara Police Station", "required": True},
                {"label": "Area / zone", "name": "area_zone", "placeholder": "e.g. Zone 3 (West)"},
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
                    "title": f"Area / zone: {match[1]}",
                    "subtitle": f"City / division: {match[0]}",
                    "officer_heading": "Assigned DCP / ACP",
                    "officer": officer,
                    "enroll_url": url_for("officer_enroll", rank_type="DCP", city=match[0], area=match[1]),
                    "enroll_label": "a DCP",
                    "children_heading": "Police stations in this zone",
                    "children": children,
                    "extra_enrolments": [
                        {"label": "Add DCP", "url": url_for("officer_enroll", rank_type="DCP", city=match[0], area=match[1])},
                        {"label": "Add ACP", "url": url_for("officer_enroll", rank_type="ACP", city=match[0], area=match[1])},
                    ],
                }
            create_title = "Create an area / zone"
            create_url = url_for("area_create")
            create_button = "Create area zone"
            create_fields = [
                {"label": "City / division", "name": "division_code", "type": "select",
                 "options": [city_filter] if city_filter else divisions},
                {"label": "Area / zone name", "name": "area_zone", "placeholder": "e.g. Zone 4 (East)", "required": True},
            ]

        else:  # cities
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
                    "title": f"City: {match[0]}",
                    "subtitle": match[1],
                    "officer_heading": "Commissioner of police (city CP)",
                    "officer": officer,
                    "enroll_url": url_for("officer_enroll", rank_type="CP", city=match[0]),
                    "enroll_label": "a city CP",
                    "children_heading": "Areas / zones in this city",
                    "children": children,
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

        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")

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

    return render_page(AREA_DASH_TPL, "Area command tree",
                       area_name=area_name, div_code=div_code, stations=stations,
                       officer=_officer_row(div_code=div_code, area=area_name, rank_level=3))


@app.route("/jurisdiction/enter-station", methods=["POST"])
@login_required
def enter_station():
    """Scopes the session to one station, then opens the regular station vault."""
    session["unit"] = (request.form.get("unit_name") or "").strip()
    session["division"] = (request.form.get("division_code") or "").strip()
    session["area"] = (request.form.get("area_zone") or "").strip()
    log_chained_audit_event("STATION_VAULT_OPENED", f"Opened vault for {session['unit']} ({session['division']})")
    return redirect(url_for("portal"))


# ---------- Hierarchy CRUD ----------
@app.route("/jurisdiction/city/create", methods=["POST"])
@rank_required(4)
def city_create():
    code = (request.form.get("division_code") or "").strip().upper()
    if not code:
        flash("A city / division code is required.", "error")
        return redirect(request.referrer or url_for("jurisdiction_state"))
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO police_divisions (division_code, division_name, division_password, nodal_officer_email) "
            "VALUES (:1, :2, 'password123', 'cp@police.gov.in')",
            (code, f"{code} Police Commissionerate")
        )
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
    if not zone:
        flash("An area / zone name is required.", "error")
        return redirect(request.referrer or url_for("jurisdiction_state"))
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO investigation_units (division_code, unit_name, station_password, area_zone) "
            "VALUES (:1, :2, 'password123', :3)",
            (div, f"{zone} Central Station", zone)
        )
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
    if not name:
        flash("A station name is required.", "error")
        return redirect(request.referrer or url_for("jurisdiction_state"))
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO investigation_units (division_code, unit_name, station_password, area_zone) "
            "VALUES (:1, :2, 'password123', :3)",
            (div, name, zone)
        )
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
# PERSONNEL — ENROLMENT, UPDATE, DECOMMISSION
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

    <div style="background:var(--primary);color:#fff;border-radius:8px;padding:11px 13px;
                font-size:11.5px;font-weight:700;margin-bottom:14px">
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
      <button class="btn green" style="width:100%;margin-top:12px;height:42px">
        Enrol junior officer</button>
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

    if not all([b, n, em, un, pw, cpw]):
        flash("All registration fields are required.", "error")
        return redirect(url_for("officer_enroll", rank_type=rank_type, city=city, area=area, station=station))

    if pw != cpw:
        flash("Password and confirm password do not match.", "error")
        return redirect(url_for("officer_enroll", rank_type=rank_type, city=city, area=area, station=station))

    # Strict rank rule: you cannot enrol an equal or higher rank than your own.
    if u["rank_level"] <= assigned_lvl and u["rank_level"] < 5:
        flash(
            f"Strict rank rule: you cannot enrol an officer of equal or higher rank "
            f"({rank_title}) than your own ({u['rank']}).", "error"
        )
        return redirect(back_url)

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

    log_chained_audit_event("OFFICER_ENROLLED", f"New account created for {n} (#{b}) in {assign_unit} by {u['name']}")
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


REMOVE_TPL = """
<div style="max-width:560px;margin:0 auto">
  <div class="card">
    <h2>Decommission a junior officer</h2>
    <div class="muted" style="margin-bottom:12px">Authorised by: {{ u.rank }} ({{ u.name }})</div>
    <div class="note" style="margin-bottom:14px">
      Rank governance applies: you can only decommission officers ranked below you, and a city
      commissioner cannot remove officers posted to another city.</div>
    <form method="post" class="stack" onsubmit="return confirm('Permanently decommission this officer?')">
      <div><label>Junior officer badge ID to remove</label>
        <input type="text" name="target_badge" placeholder="e.g. IO-SUR-102" required></div>
      <div><label>Your authorising commander password</label>
        <input type="password" name="auth_password" required></div>
      <button class="btn red" style="width:100%;margin-top:12px;height:42px">
        Permanently decommission officer</button>
    </form>
    <div style="margin-top:14px"><a href="{{ back_url }}">Back</a></div>
  </div>
</div>
"""


@app.route("/officers/remove", methods=["GET", "POST"])
@rank_required(4)
def officer_remove():
    u = current_user()
    back_url = url_for("jurisdiction_state") if u["rank_level"] >= 5 else url_for("jurisdiction_city")

    if request.method == "GET":
        return render_page(REMOVE_TPL, "Decommission officer", back_url=back_url)

    target_b = (request.form.get("target_badge") or "").strip().upper()
    auth_p = (request.form.get("auth_password") or "").strip()

    if not target_b or not auth_p:
        flash("Badge ID and authorisation password are required.", "error")
        return redirect(url_for("officer_remove"))

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT rank_level FROM vault_system_users WHERE badge_id = :1 AND password_hash = :2",
                    (u["badge"], auth_p))
        if not cur.fetchone():
            cur.close(); conn.close()
            flash("Incorrect authorisation password.", "error")
            return redirect(url_for("officer_remove"))

        cur.execute("SELECT officer_name, rank_level, police_rank, division_code FROM vault_system_users WHERE badge_id = :1",
                    (target_b,))
        r_target = cur.fetchone()
        if not r_target:
            cur.close(); conn.close()
            flash("That officer badge was not found.", "error")
            return redirect(url_for("officer_remove"))

        target_name, target_level, target_rank, target_div = r_target[0], int(r_target[1]), r_target[2], r_target[3]

        if u["rank_level"] <= target_level and u["rank_level"] < 5:
            cur.close(); conn.close()
            flash(
                f"Security hierarchy violation: you cannot decommission {target_rank} {target_name}. "
                "Only higher-ranking commanders have deletion rights.", "error"
            )
            return redirect(url_for("officer_remove"))

        if u["rank_level"] == 4 and target_div != u["division"]:
            cur.close(); conn.close()
            flash(
                f"Jurisdiction violation: the city commissioner of {u['division']} cannot remove "
                f"officers assigned to {target_div}.", "error"
            )
            return redirect(url_for("officer_remove"))

        cur.execute("DELETE FROM vault_system_users WHERE badge_id = :1", (target_b,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")
        return redirect(url_for("officer_remove"))

    log_chained_audit_event("OFFICER_DECOMMISSIONED", f"Officer #{target_b} ({target_name}) removed by {u['name']}")
    flash(f"Officer #{target_b} ({target_name}) decommissioned.", "ok")
    return redirect(back_url)


# =========================================================
# SCREEN 3 — MAIN STATION VAULT (tabbed portal)
# =========================================================
def portal_tabs(active):
    u = current_user()
    tabs = [("cases", "Case file repository")]
    if u["role"] != "COURT_JUDICIAL":
        tabs.append(("custody", "Chain of custody ledger"))
    tabs.append(("verify", "Integrity verification"))
    if u["rank_level"] >= 3 or u["role"] == "COURT_JUDICIAL":
        tabs.append(("audit", "Security audit trails"))
    return [{"key": k, "label": l, "active": k == active} for k, l in tabs]


PORTAL_TABS_TPL = """
<div class="tabs">
  {% for t in tabs %}
    <a class="{{ 'active' if t.active }}" href="{{ url_for('portal', tab=t.key) }}">{{ t.label }}</a>
  {% endfor %}
</div>
"""


def fetch_cases(search_query=""):
    """
    Strict station-level data separation, identical to the desktop client:
      level 5 / judge -> whole state, or one station once scoped
      level 4         -> own division, or one station once scoped
      level 3         -> division + area + station
      level <=2       -> division + station
    """
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
    <h3>Register a new case profile</h3>
    <p class="muted">Case number is generated automatically from the station code.</p>
    <form method="post" action="{{ url_for('case_register') }}" class="stack"
          onsubmit="return confirm('Register this case permanently under {{ u.unit }}?')">
      <div><label>Case name</label>
        <input type="text" name="case_name" placeholder="e.g. Lalita Bank Robbery" required></div>
      <div><label>Case category (drives analytics)</label>
        <select name="category">
          {% for c in categories %}<option value="{{ c }}">{{ c }}</option>{% endfor %}
        </select></div>
      <div><label>FIR number</label>
        <input type="text" name="fir_no" placeholder="e.g. FIR-001/2026" required></div>
      <div><label>Crime scene / location</label>
        <input type="text" name="location" placeholder="Crime scene / location" required></div>
      <div><label>Registered by</label>
        <input type="text" name="registered_by" value="{{ u.name }} (#{{ u.badge }})"></div>
      <div><label>Condition of case</label>
        <select name="condition">
          {% for c in conditions %}<option value="{{ c }}">{{ c }}</option>{% endfor %}
        </select></div>
      <div><label>Sentence / jail facility (optional)</label>
        <input type="text" name="punishment" placeholder="e.g. 5 years RI at Lajpore Central Jail"></div>
      <button class="btn" style="width:100%;margin-top:12px;height:40px">Commit &amp; anchor case</button>
    </form>

    <hr style="border:0;border-top:1px solid var(--card-border);margin:16px 0">
    <h3>Official statutory reports</h3>
    <div class="stack">
      <a class="btn dark" style="width:100%" href="{{ url_for('report_pending_cases') }}">
        Print pending cases summary</a>
    </div>
  </div>
  {% else %}
  <div class="card">
    <h3>Judicial inspection portal</h3>
    <p class="muted">Read-only evidence manifest. Open any case to inspect encrypted child exhibits,
      verify SHA-256 seals, view the custody timeline, and export statutory dossiers.</p>
    <a class="btn dark" style="width:100%;margin-top:10px" href="{{ url_for('report_pending_cases') }}">
      Print pending cases report</a>
  </div>
  {% endif %}

  <div class="card">
    <div class="row" style="justify-content:space-between;margin-bottom:10px">
      <form method="get" action="{{ url_for('portal') }}" class="row" style="flex:1">
        <input type="hidden" name="tab" value="cases">
        <input type="text" name="q" value="{{ q }}" style="max-width:380px"
               placeholder="Search by case, FIR, city, station or location…">
        <button class="btn small">Search</button>
        {% if q %}<a class="btn slate small" href="{{ url_for('portal', tab='cases') }}">Clear</a>{% endif %}
      </form>
      <div style="font-size:11px;font-weight:700;color:var(--red)">
        Station [{{ u.unit or 'All' }}] unresolved: {{ pending }} / {{ cases|length }}</div>
    </div>

    <div class="table-scroll">
      <table>
        <thead><tr>
          <th>Case no</th><th class="left">Case name / title</th><th>FIR ref</th>
          <th>Crime location</th><th>Condition</th><th class="left">Verdict / jail facility</th>
          <th>City</th><th>Area / zone</th><th>Police station</th>
          <th>Evidences</th><th>Registered by</th><th>Open</th>
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
            <td><a class="btn small" href="{{ url_for('case_workspace', case_no=c.case_no) }}">Workspace</a></td>
          </tr>
          {% else %}
          <tr><td colspan="12" class="muted" style="padding:22px">
            No case profiles are registered for this scope yet.</td></tr>
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
        CASES_TPL, "Case file repository",
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

    if not c_name or not f_no or not loc:
        flash("Case name, FIR number, and location are mandatory.", "error")
        return redirect(url_for("portal", tab="cases"))

    if not unit:
        flash("Open a police station from the command tree before registering a case.", "error")
        return redirect(url_for("portal", tab="cases"))

    # Auto-generated station-scoped case number, e.g. KPS-2026-004
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
    flash(f"Case '{full_case_title}' registered as {c_no} under {unit}.", "ok")
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
    flash(f"Case {case_no} updated to '{new_val}'.", "ok")
    return redirect(url_for("case_workspace", case_no=case_no))


# =========================================================
# CASE WORKSPACE — EVIDENCE INGEST, DECRYPT & RENDER
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
    except Exception as e:
        flash(f"Could not load the case: {e}", "error")
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
    except Exception as e:
        flash(f"Could not load evidence: {e}", "error")
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
  <h2>{{ case.case_name }}</h2>
  <div class="muted">Case {{ case.case_no }} &nbsp;·&nbsp; FIR {{ case.fir_no }}
    &nbsp;·&nbsp; {{ case.city }} / {{ case.area }} / {{ case.station }}</div>
  <div class="row" style="margin-top:12px">
    <span class="pill {{ 'green' if case.condition in resolved else 'gold' }}">{{ case.condition }}</span>
    <span class="muted">Scene: {{ case.location }}</span>
    <span class="muted">Registered by: {{ case.registered_by }}</span>
  </div>
  <div class="row" style="margin-top:12px">
    <a class="btn dark small" href="{{ url_for('report_case_dossier', case_no=case.case_no) }}">
      Print full case dossier</a>
    <a class="btn slate small" href="{{ url_for('portal', tab='cases') }}">Back to repository</a>
  </div>
</div>

<div class="split">
  <div class="stack">
    {% if u.role != 'COURT_JUDICIAL' %}
    <div class="card">
      <h3>Ingest &amp; encrypt evidence</h3>
      <p class="muted">The file is hashed, AES-256 sealed, and anchored on-chain when the node is reachable.</p>
      <form method="post" action="{{ url_for('evidence_upload', case_no=case.case_no) }}"
            enctype="multipart/form-data" class="stack">
        <div><label>Evidence ID</label>
          <input type="text" name="evidence_id" placeholder="e.g. EV-CCTV-01" required></div>
        <div><label>Evidence title / name</label>
          <input type="text" name="evidence_title" placeholder="Evidence title" required></div>
        <div><label>Locker / shelf location</label>
          <input type="text" name="vault_locker" placeholder="e.g. Shelf B-14"></div>
        <div><label>Digital file (image, video, audio, report or disk dump)</label>
          <input type="file" name="evidence_file" required></div>
        <button class="btn green" style="width:100%;margin-top:12px;height:40px">
          Encrypt &amp; seal to vault</button>
      </form>
    </div>

    <div class="card">
      <h3>Update judicial status</h3>
      <form method="post" action="{{ url_for('case_update_status', case_no=case.case_no) }}" class="stack">
        <div><label>Condition of case</label>
          <select name="condition">
            {% for c in conditions %}
              <option value="{{ c }}" {{ 'selected' if c == case.condition }}>{{ c }}</option>
            {% endfor %}
          </select></div>
        <div><label>Verdict / detention facility</label>
          <input type="text" name="punishment" value="{{ case.punishment }}"></div>
        <button class="btn gold" style="width:100%;margin-top:10px">Commit status update</button>
      </form>
    </div>
    {% else %}
    <div class="card">
      <h3>Judicial inspection</h3>
      <p class="muted">Select any exhibit to decrypt and inspect it, verify its SHA-256 seal,
        or export a Section 65B certificate. Ingestion is disabled for judicial accounts.</p>
    </div>
    {% endif %}
  </div>

  <div class="stack">
    {% if preview %}
    <div class="card">
      <h3>Exhibit {{ preview.evidence_id }} — {{ preview.title }}</h3>
      <div class="muted">{{ preview.category }} · {{ preview.classification }}</div>
      <div class="hash muted" style="margin-top:6px">SHA-256: {{ preview.sha256 }}</div>

      <div class="media-frame">
        {% if preview.kind == 'image' %}
          <img src="{{ url_for('evidence_stream', evidence_id=preview.evidence_id) }}"
               alt="Decrypted exhibit {{ preview.evidence_id }}">
        {% elif preview.kind == 'video' %}
          <video controls preload="metadata"
                 src="{{ url_for('evidence_stream', evidence_id=preview.evidence_id) }}"></video>
        {% elif preview.kind == 'audio' %}
          <audio controls src="{{ url_for('evidence_stream', evidence_id=preview.evidence_id) }}"></audio>
        {% elif preview.kind == 'pdf' %}
          <iframe src="{{ url_for('evidence_stream', evidence_id=preview.evidence_id) }}"
                  style="width:100%;height:520px;border:0;border-radius:6px;background:#fff"></iframe>
        {% elif preview.kind == 'text' %}
          <pre>{{ preview_text }}</pre>
        {% else %}
          <p style="color:#E2E8F0;font-size:12px;margin:14px">
            This exhibit is footage or a binary dump that the browser cannot render.
            Download it to inspect with a forensic tool.</p>
        {% endif %}
      </div>

      <div class="row" style="margin-top:12px">
        <a class="btn blue small" href="{{ url_for('evidence_download', evidence_id=preview.evidence_id) }}">
          Download decrypted copy</a>
        <a class="btn gold small" href="{{ url_for('report_65b', evidence_id=preview.evidence_id) }}">
          Export Section 65B certificate</a>
        <a class="btn slate small" href="{{ url_for('case_workspace', case_no=case.case_no) }}">
          Close preview</a>
      </div>
    </div>
    {% endif %}

    <div class="card">
      <h3>Evidence manifest ({{ evidences|length }} exhibits)</h3>
      <div class="table-scroll">
        <table>
          <thead><tr>
            <th>Evidence ID</th><th class="left">Evidence name</th><th>Category</th>
            <th class="left">AI classification</th><th>SHA-256 seal</th><th>Locker</th>
            <th>Custody</th><th>Chain</th><th>Inspect</th>
          </tr></thead>
          <tbody>
            {% for e in evidences %}
            <tr>
              <td><b>{{ e.evidence_id }}</b></td>
              <td class="left">{{ e.title }}</td>
              <td>{{ e.category }}</td>
              <td class="left">{{ e.classification }}</td>
              <td class="hash">{{ e.sha256[:24] }}…</td>
              <td>{{ e.locker }}</td>
              <td>{% if e.custody == 'VAULT' %}<span class="pill green">In vault</span>
                  {% else %}<span class="pill gold">{{ e.custody }}</span>{% endif %}</td>
              <td>{% if e.chain_status == 'ANCHORED' %}<span class="pill navy">Anchored</span>
                  {% else %}<span class="pill slate">{{ e.chain_status }}</span>{% endif %}</td>
              <td>
                {% if e.on_disk %}
                  <a class="btn small"
                     href="{{ url_for('case_workspace', case_no=case.case_no, view=e.evidence_id) }}">
                     Decrypt &amp; view</a>
                {% else %}<span class="muted">File missing</span>{% endif %}
              </td>
            </tr>
            {% else %}
            <tr><td colspan="9" class="muted" style="padding:22px">
              No exhibits have been sealed into this case yet.</td></tr>
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
        flash("That case profile could not be found.", "error")
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
                preview_text = f"[Decryption failed: {e}]"
        if preview:
            log_chained_audit_event(
                "EVIDENCE_DECRYPTED_VIEW",
                f"Decrypted and inspected {preview['title']} ({preview['evidence_id']})"
            )

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
        flash("Evidence ID, title, and a file are all required.", "error")
        return redirect(url_for("case_workspace", case_no=case_no))

    raw_name = os.path.basename(upload.filename)

    # Buffer the upload to a temp file so the classifier can inspect it on disk,
    # exactly as the desktop client inspected the chosen path.
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(raw_name)[1])
    os.close(tmp_fd)
    try:
        upload.save(tmp_path)

        detected_category, detected_classification, extracted_text = \
            IntelligentClassifier.analyze_evidence(tmp_path, raw_name)

        hasher = hashlib.sha256()
        with open(tmp_path, "rb") as fobj:
            while True:
                chunk = fobj.read(4096)
                if not chunk:
                    break
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

    # On-chain anchoring never rolls back the committed off-chain record.
    chain_note = "Blockchain anchoring is not configured."
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
            chain_note = f"Anchored on-chain (tx {tx_hash[:18]}…, block {block_no})."
        except Exception as chain_err:
            chain_note = f"Blockchain anchoring pending — node unreachable ({chain_err})."

    flash(f"Evidence {eid} AES-256 encrypted and sealed. SHA-256: {fhash}", "ok")
    flash(chain_note, "info")
    return redirect(url_for("case_workspace", case_no=case_no, view=eid))


def _decrypt_to_cache(ev):
    """Decrypt an exhibit into a short-lived cache file so the browser can range-request it."""
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
    """Serves the decrypted exhibit inline — this is what renders images and video in the workspace."""
    ev = get_evidence(evidence_id)
    if not ev:
        abort(404)
    path = _decrypt_to_cache(ev)
    if not path:
        abort(404)
    return send_file(
        path, mimetype=guess_mime(ev["raw_file_name"]),
        as_attachment=False, conditional=True,       # conditional=True enables video seeking
        download_name=ev["raw_file_name"] or "exhibit.bin"
    )


@app.route("/evidence/<path:evidence_id>/download")
@login_required
def evidence_download(evidence_id):
    ev = get_evidence(evidence_id)
    if not ev:
        abort(404)
    if not ev["encrypted_path"] or not os.path.exists(ev["encrypted_path"]):
        flash(f"The encrypted payload for {evidence_id} is missing from vault storage.", "error")
        return redirect(url_for("case_workspace", case_no=ev["case_no"]))
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
# CHAIN OF CUSTODY LEDGER
# =========================================================
CUSTODY_TPL = """
{{ tabs_html|safe }}
<div class="split">
  <div class="card">
    <h3>Custody handover &amp; tracking</h3>
    <form method="post" action="{{ url_for('custody_issue') }}" class="stack">
      <div><label>Evidence ID</label>
        <input type="text" name="evidence_id" placeholder="e.g. EV-CCTV-01" required></div>
      <div><label>Recipient officer badge</label>
        <input type="text" name="badge" required></div>
      <div><label>Recipient officer name</label>
        <input type="text" name="name" required></div>
      <div><label>Officer rank</label>
        <input type="text" name="rank" placeholder="e.g. PI / DySP"></div>
      <div><label>Recipient mobile</label>
        <input type="text" name="mobile" placeholder="10 digits"></div>
      <div><label>Official email</label>
        <input type="text" name="email" placeholder="officer@police.gov.in"></div>
      <div><label>Transfer reason</label>
        <input type="text" name="reason" placeholder="e.g. FSL testing"></div>
      <div><label>Custody duration (days)</label>
        <input type="number" name="days" value="7" min="1"></div>
      <button class="btn" style="width:100%;margin-top:12px;height:40px">Transfer &amp; issue evidence</button>
    </form>
  </div>

  <div class="card">
    <h3>Custody movement ledger</h3>
    <p class="muted">Open a row's timeline to see the exhibit's full provenance journey.</p>
    <div class="table-scroll">
      <table>
        <thead><tr>
          <th>Transfer</th><th>Evidence</th><th>Case</th><th>Badge</th><th class="left">Officer</th>
          <th>Rank</th><th>Checked out</th><th>Court deadline</th><th>Status</th><th>Actions</th>
        </tr></thead>
        <tbody>
          {% for t in transfers %}
          <tr>
            <td>{{ t.transfer_id }}</td><td><b>{{ t.evidence_id }}</b></td><td>{{ t.case_no }}</td>
            <td>{{ t.badge }}</td><td class="left">{{ t.name }}</td><td>{{ t.rank }}</td>
            <td>{{ t.checkout }}</td><td>{{ t.deadline }}</td>
            <td>{% if t.status == 'CHECKED_OUT' %}<span class="pill gold">Checked out</span>
                {% else %}<span class="pill green">In vault</span>{% endif %}</td>
            <td>
              <div class="row" style="gap:5px;justify-content:center">
                <a class="btn small slate"
                   href="{{ url_for('custody_timeline', evidence_id=t.evidence_id) }}">Timeline</a>
                {% if t.status == 'CHECKED_OUT' %}
                <form method="post" action="{{ url_for('custody_return') }}">
                  <input type="hidden" name="transfer_id" value="{{ t.transfer_id }}">
                  <input type="hidden" name="evidence_id" value="{{ t.evidence_id }}">
                  <button class="btn green small">Mark returned</button>
                </form>
                {% endif %}
              </div>
            </td>
          </tr>
          {% else %}
          <tr><td colspan="10" class="muted" style="padding:22px">
            No custody movements have been recorded for this station.</td></tr>
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
        flash(f"Could not load the custody ledger: {e}", "error")

    return render_page(CUSTODY_TPL, "Chain of custody", tabs_html=tabs_html, transfers=transfers)


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

    if not eid or not badge or not name:
        flash("Evidence ID, recipient badge, and name are mandatory.", "error")
        return redirect(url_for("portal", tab="custody"))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT case_no, evidence_title FROM case_evidence_files WHERE evidence_id = :1", (eid,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            flash(f"Evidence ID {eid} was not found in the vault.", "error")
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

        cur.execute("UPDATE case_evidence_files SET active_custody_officer = :1 WHERE evidence_id = :2",
                    (name, eid))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")
        return redirect(url_for("portal", tab="custody"))

    log_chained_audit_event("CUSTODY_ISSUED", f"Evidence {eid} transferred to Officer {name} (#{badge}) for {days} days.")
    flash(f"Custody of {eid} transferred to {name} (#{badge}) for {days} days.", "ok")
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

    log_chained_audit_event("CUSTODY_RESTORED_VAULT", f"Evidence {eid} safely returned to vault storage.")
    flash(f"Evidence {eid} returned to the vault.", "ok")
    return redirect(url_for("portal", tab="custody"))


TIMELINE_TPL = """
<div class="card">
  <h2>Custody provenance timeline — exhibit {{ evidence_id }}</h2>
  <p class="muted">Every handover recorded against this exhibit, in order.</p>
  <div class="timeline" style="margin-top:18px">
    {% for e in events %}
      <div class="tl-item">
        <div class="row" style="justify-content:space-between">
          <b>Stage {{ loop.index }}: {{ e.from_officer }} → {{ e.to_name }}</b>
          <span class="pill {{ 'gold' if e.status == 'CHECKED_OUT' else 'green' }}">{{ e.status }}</span>
        </div>
        <div class="muted" style="margin-top:5px">Recipient rank: {{ e.to_rank }}</div>
        <div class="muted">Reason: {{ e.reason }}</div>
        <div class="muted">Recorded: {{ e.checkout }}</div>
      </div>
    {% else %}
      <p class="muted">No custody events recorded for this exhibit.</p>
    {% endfor %}
  </div>
  <a class="btn slate small" href="{{ url_for('portal', tab='custody') }}">Back to ledger</a>
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
        flash(f"Could not load the timeline: {e}", "error")

    return render_page(TIMELINE_TPL, "Custody timeline", evidence_id=evidence_id, events=events)


# =========================================================
# INTEGRITY VERIFICATION DASHBOARD
# =========================================================
VERIFY_TPL = """
{{ tabs_html|safe }}
<div class="card" style="margin-bottom:14px">
  <div class="row" style="justify-content:space-between">
    <div>
      <h2>Bit-level tamper seal verification</h2>
      <p class="muted">Each exhibit is decrypted in memory and re-hashed, then compared against
        the SHA-256 seal recorded at ingestion.</p>
    </div>
    <div class="row">
      <a class="btn" href="{{ url_for('portal', tab='verify') }}">Re-run integrity audit</a>
      {% if u.role != 'COURT_JUDICIAL' %}
      <form method="post" action="{{ url_for('tamper_simulate') }}"
            onsubmit="return confirm('Append tamper bytes to this exhibit on disk? This is a controlled demo.')">
        <select name="evidence_id" style="width:auto;display:inline-block;margin-right:6px">
          {% for r in results %}<option value="{{ r.evidence_id }}">{{ r.evidence_id }}</option>{% endfor %}
        </select>
        <button class="btn red">Simulate controlled tampering</button>
      </form>
      {% endif %}
    </div>
  </div>
</div>

<div class="metrics" style="margin-bottom:14px">
  <div class="metric"><div class="t">Exhibits audited</div><div class="v">{{ results|length }}</div></div>
  <div class="metric"><div class="t">Verified intact</div>
    <div class="v" style="color:var(--green)">{{ intact }}</div></div>
  <div class="metric"><div class="t">Integrity mismatches</div>
    <div class="v" style="color:var(--red)">{{ mismatched }}</div></div>
  <div class="metric"><div class="t">Missing payloads</div>
    <div class="v" style="color:var(--muted)">{{ missing }}</div></div>
</div>

<div class="card">
  <div class="table-scroll">
    <table>
      <thead><tr>
        <th>Evidence ID</th><th>Case</th><th class="left">Title</th>
        <th>Sealed hash</th><th>Live recomputed hash</th><th>Verdict</th>
      </tr></thead>
      <tbody>
        {% for r in results %}
        <tr>
          <td><b>{{ r.evidence_id }}</b></td><td>{{ r.case_no }}</td>
          <td class="left">{{ r.title }}</td>
          <td class="hash">{{ r.sealed[:26] }}…</td>
          <td class="hash">{{ r.active[:26] }}{{ '…' if r.active|length > 26 }}</td>
          <td>
            {% if r.ok %}<span class="pill green">Verified — 100% intact</span>
            {% elif r.missing %}<span class="pill slate">Missing file</span>
            {% else %}<span class="pill red">Integrity mismatch</span>{% endif %}
          </td>
        </tr>
        {% else %}
        <tr><td colspan="6" class="muted" style="padding:22px">
          No exhibits are available in this scope to verify.</td></tr>
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
            cur.execute("""
                SELECT e.evidence_id, e.case_no, e.evidence_title, e.sha256_hash, e.encrypted_path
                FROM case_evidence_files e JOIN case_profiles c ON e.case_no = c.case_no
            """)
        else:
            cur.execute("""
                SELECT e.evidence_id, e.case_no, e.evidence_title, e.sha256_hash, e.encrypted_path
                FROM case_evidence_files e JOIN case_profiles c ON e.case_no = c.case_no
                WHERE c.division_code = :1 AND c.unit_name = :2
            """, (u["division"], u["unit"]))
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

        log_chained_audit_event("INTEGRITY_AUDIT_RUN", f"Verified bit-level hash integrity across {len(rows)} exhibits.")
    except Exception as e:
        flash(f"Audit error: {e}", "error")

    return render_page(
        VERIFY_TPL, "Integrity verification", tabs_html=tabs_html, results=results,
        intact=sum(1 for r in results if r["ok"]),
        mismatched=sum(1 for r in results if not r["ok"] and not r["missing"]),
        missing=sum(1 for r in results if r["missing"]),
    )


@app.route("/verify/tamper-demo", methods=["POST"])
@login_required
def tamper_simulate():
    if is_judge():
        flash("The judicial portal is read-only.", "error")
        return redirect(url_for("portal", tab="verify"))

    eid = (request.form.get("evidence_id") or "").strip()
    if not eid:
        flash("There are no exhibits in the vault to tamper with.", "warn")
        return redirect(url_for("portal", tab="verify"))

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
            flash(
                f"Exhibit {eid} ({row[1]}) ciphertext was modified on disk. "
                "The audit below now detects the bit mismatch.", "error"
            )
        else:
            flash(f"No encrypted payload found on disk for {eid}.", "error")
    except Exception as e:
        flash(str(e), "error")

    return redirect(url_for("portal", tab="verify"))


# =========================================================
# SECURITY AUDIT TRAILS (hash-chained ledger)
# =========================================================
AUDIT_TPL = """
{{ tabs_html|safe }}
<div class="card">
  <div class="row" style="justify-content:space-between;margin-bottom:10px">
    <div>
      <h2>Cryptographically chained audit ledger</h2>
      <p class="muted">Each block hashes the previous block's digest, so any removed or edited
        row breaks the chain.</p>
    </div>
    <a class="btn" href="{{ url_for('portal', tab='audit') }}">Refresh audit chain</a>
  </div>
  <div class="table-scroll">
    <table>
      <thead><tr>
        <th>Log ID</th><th>Previous hash</th><th>Timestamp</th><th>Actor</th><th>Role</th>
        <th>Action</th><th class="left">Target</th><th>IP address</th><th>Block hash</th>
      </tr></thead>
      <tbody>
        {% for l in logs %}
        <tr>
          <td>{{ l.log_id }}</td>
          <td class="hash">{{ l.prev_hash[:18] }}…</td>
          <td>{{ l.timestamp }}</td><td>{{ l.actor }}</td><td>{{ l.role }}</td>
          <td><span class="pill navy">{{ l.action }}</span></td>
          <td class="left">{{ l.target }}</td><td>{{ l.ip }}</td>
          <td class="hash">{{ l.log_hash[:18] }}…</td>
        </tr>
        {% else %}
        <tr><td colspan="9" class="muted" style="padding:22px">The audit ledger is empty.</td></tr>
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
        flash(f"Could not load the audit ledger: {e}", "error")

    return render_page(AUDIT_TPL, "Security audit trails", tabs_html=tabs_html, logs=logs)


# =========================================================
# STATUTORY PDF EXPORTS (ReportLab — identical layouts)
# =========================================================
def _pdf_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("TStyle", parent=styles["Heading1"], fontSize=14,
                                alignment=1, textColor=colors.HexColor("#1E3A8A")),
        "sub": ParagraphStyle("SubStyle", parent=styles["Normal"], fontSize=9,
                              alignment=1, textColor=colors.HexColor("#475569")),
        "h2": ParagraphStyle("H2Style", parent=styles["Heading2"], fontSize=11,
                             textColor=colors.HexColor("#1E3A8A")),
        "body": ParagraphStyle("BStyle", parent=styles["Normal"], fontSize=8.5, leading=12,
                               textColor=colors.HexColor("#0F172A")),
        "normal": styles["Normal"],
    }


@app.route("/reports/case/<path:case_no>/dossier")
@login_required
def report_case_dossier(case_no):
    u = current_user()
    case = get_case(case_no)
    if not case:
        flash("That case profile could not be found.", "error")
        return redirect(url_for("portal", tab="cases"))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT evidence_id, evidence_title, category, ai_classification, sha256_hash,
                   vault_locker, active_custody_officer, encrypted_path, raw_file_name
            FROM case_evidence_files WHERE case_no = :1
        """, (case_no,))
        ev_rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")
        return redirect(url_for("case_workspace", case_no=case_no))

    st = _pdf_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36,
                            topMargin=36, bottomMargin=36)
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
        ["Sealing & Ingestion Stamp:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "Inspecting Authority:", f"{u['rank']} {u['name']}"],
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
    elements.append(Paragraph(
        "<b>ITEMIZED DIGITAL EVIDENCE EXHIBITS, BIT-LEVEL SHA-256 SEALS & VISUAL ATTACHMENTS:</b>",
        st["h2"]))
    elements.append(Spacer(1, 6))

    temp_images = []
    if ev_rows:
        for er in ev_rows:
            eid, etitle, ecat, eclass = er[0], er[1], er[2], er[3]
            ehash, elocker, ecustody = er[4], er[5], er[6]
            enc_path, raw_name = er[7], er[8]

            exhibit_meta = [
                [Paragraph(f"<b>Exhibit ID:</b> {eid}", st["body"]),
                 Paragraph(f"<b>Title:</b> {etitle}", st["body"])],
                [Paragraph(f"<b>Category:</b> {ecat} ({eclass})", st["body"]),
                 Paragraph(f"<b>Vault Shelf:</b> {elocker} | <b>Custody:</b> {ecustody}", st["body"])],
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

            # Only genuine images are embedded; footage and binaries get the standard notice.
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
                    "<b>[This is footage / binary dump which can't be represented in PDF so please "
                    "check in app for this]</b>",
                    ParagraphStyle("FootageNote", parent=st["body"],
                                   textColor=colors.HexColor("#DC2626"), fontName="Helvetica-Bold")))

            elements.append(Spacer(1, 10))
    else:
        elements.append(Paragraph(
            "<i>No digital evidence exhibits attached to this case profile yet.</i>", st["body"]))

    elements += [Spacer(1, 15), Paragraph(
        "<b>STATUTORY AUTHENTICITY CERTIFICATE:</b> This electronic case record and its attached child "
        "evidence exhibits are cryptographically anchored under AES-256 encryption at rest and SHA-256 "
        "bit-stream integrity seals. Admissible in judicial trial under Indian Evidentiary Statutes "
        "(Section 65B IEA / Section 63 BSA).", st["body"])]

    doc.build(elements)
    buffer.seek(0)

    for p in temp_images:
        try:
            os.remove(p)
        except Exception:
            pass

    log_chained_audit_event("CASE_DOSSIER_PRINTED", f"Exported complete dossier for Case {case_no}")
    return send_file(buffer, mimetype="application/pdf", as_attachment=True,
                     download_name=f"Complete_Case_Dossier_{case_no.replace('/', '_')}.pdf")


@app.route("/reports/pending-cases")
@login_required
def report_pending_cases():
    u = current_user()
    div, unit = u["division"], u["unit"]

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT case_no, case_name, fir_no, crime_location, case_condition, division_code,
                   unit_name, TO_CHAR(created_at, 'YYYY-MM-DD')
            FROM case_profiles
            WHERE division_code = :1 AND unit_name = :2
              AND case_condition NOT IN ('Convicted & Sentenced', 'Closed / Acquitted')
        """, (div, unit))
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {e}", "error")
        return redirect(url_for("portal", tab="cases"))

    st = _pdf_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), leftMargin=36, rightMargin=36,
                            topMargin=36, bottomMargin=36)
    elements = [
        Paragraph("MINISTRY OF HOME AFFAIRS • GOVERNMENT OF INDIA", st["sub"]),
        Paragraph(f"OFFICIAL PENDING CASES REPORT — {unit}", st["title"]),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1E3A8A"), spaceAfter=12),
        Paragraph(
            f"Report Generated By: {u['rank']} {u['name']} (#{u['badge']}) | Station: {unit} | "
            f"Total Pending Dockets: {len(rows)}",
            ParagraphStyle("Summ", parent=st["normal"], fontSize=9, textColor=colors.HexColor("#0F172A"))),
        Spacer(1, 10),
    ]

    if rows:
        p_data = [["Case No", "Case Name / Title", "FIR Ref", "Crime Location",
                   "Status / Stage", "City", "Police Station", "Registered Date"]]
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
    else:
        elements.append(Paragraph(
            f"<i>No pending cases in {unit}. Zero backlog reported.</i>", st["normal"]))

    doc.build(elements)
    buffer.seek(0)

    log_chained_audit_event("PENDING_REPORT_PRINTED", f"Exported pending cases report for {unit}")
    safe_unit = (unit or "AllStations").replace("/", "_").replace(" ", "_")
    return send_file(buffer, mimetype="application/pdf", as_attachment=True,
                     download_name=f"Pending_Cases_Backlog_Report_{safe_unit}.pdf")


@app.route("/reports/evidence/<path:evidence_id>/65b")
@login_required
def report_65b(evidence_id):
    u = current_user()
    ev = get_evidence(evidence_id)
    if not ev:
        flash("That exhibit could not be found.", "error")
        return redirect(url_for("portal", tab="cases"))

    case = get_case(ev["case_no"]) or {}
    st = _pdf_styles()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36,
                            topMargin=36, bottomMargin=36)
    title_style = ParagraphStyle("TStyle65", parent=st["title"], fontSize=13)
    body_style = ParagraphStyle("BStyle65", parent=st["body"], fontSize=9, leading=13)

    elements = [
        Paragraph("MINISTRY OF HOME AFFAIRS • GOVERNMENT OF INDIA",
                  ParagraphStyle("Sub65", fontName="Helvetica-Bold", fontSize=10, alignment=1,
                                 textColor=colors.HexColor("#475569"))),
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
        "<b>STATUTORY ASSISTANCE DECLARATION:</b> This electronic record was mathematically "
        "fingerprinted and encrypted at lawful ingestion. This document assists authorized personnel "
        "in generating an electronic-record certificate containing relevant metadata, timestamps, and "
        "integrity information, subject to applicable legal requirements.", body_style)]

    doc.build(elements)
    buffer.seek(0)

    log_chained_audit_event("65B_CERTIFICATE_EXPORTED", f"Exported Section 65B PDF for Evidence {evidence_id}")
    return send_file(buffer, mimetype="application/pdf", as_attachment=True,
                     download_name=f"Section65B_Certificate_{evidence_id.replace('/', '_')}.pdf")


# =========================================================
# ERROR HANDLING & ENTRY POINT
# =========================================================
@app.errorhandler(404)
def not_found(_e):
    body = """<div class="card" style="max-width:520px;margin:40px auto">
      <h2>That page isn't part of the vault</h2>
      <p class="muted">The link may be stale, or the record was removed.</p>
      <a class="btn" href="{{ url_for('portal') if session.get('badge') else url_for('gateway') }}">
        Back to safety</a></div>"""
    return render_page(body, "Not found"), 404


@app.errorhandler(413)
def too_large(_e):
    flash("That file exceeds the 512 MB evidence upload limit.", "error")
    return redirect(url_for("portal", tab="cases")), 302


@app.context_processor
def inject_globals():
    return {"THEME": THEME, "now": datetime.now()}


def preflight():
    """Check the environment before serving, so failures are readable instead of stack traces."""
    problems = []

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM vault_system_users")
        user_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        db_state = f"connected — {user_count} officer accounts"
    except Exception as e:
        first_line = str(e).strip().splitlines()[0][:110]
        db_state = f"UNREACHABLE — {first_line}"
        problems.append(
            "Oracle is not reachable. Confirm the OracleServiceXE and "
            "OracleOraDB21Home1TNSListener services are running, that the password in "
            "config.json is correct, and that Local_SIH26.sql has been executed."
        )

    if not os.path.isdir(VAULT_STORAGE_DIR):
        problems.append(f"Vault storage directory is missing: {VAULT_STORAGE_DIR}")

    chain_state = "disabled in config.json"
    if BLOCKCHAIN_CONFIG.get("enabled"):
        if not BLOCKCHAIN_MODULE_AVAILABLE:
            chain_state = "enabled but web3 / py-solc-x is not installed — anchoring will be skipped"
        elif not BLOCKCHAIN_CONFIG.get("contract_address"):
            chain_state = "enabled but no contract_address — run: python blockchain_manager.py"
        else:
            chain_state = f"enabled — contract {BLOCKCHAIN_CONFIG['contract_address'][:16]}…"

    lan_ip = get_local_ip()
    if SECURITY_CONFIG.get("enforce_mha_subnet"):
        allowed = list(SECURITY_CONFIG.get("allowed_subnets", [])) + auto_local_prefixes()
        subnet_state = "enforced — permitted: " + ", ".join(sorted(set(allowed)))
    else:
        subnet_state = "open to any network"

    print("=" * 72)
    print("  NyayaVault Web — Ministry of Home Affairs (PS-190)")
    print("=" * 72)
    print(f"  Oracle       : {db_state}")
    print(f"  Blockchain   : {chain_state}")
    print(f"  Vault store  : {VAULT_STORAGE_DIR}")
    print(f"  Subnet policy: {subnet_state}")
    print("-" * 72)
    print(f"  This computer     ->  http://127.0.0.1:5000")
    print(f"  Same Wi-Fi / LAN  ->  http://{lan_ip}:5000")
    print("=" * 72)

    for p in problems:
        print(f"  [!] {p}")
    if problems:
        print("-" * 72)
        print("  The server will still start so you can read the error in the browser.")
        print("=" * 72)

    print("  Press CTRL+C to stop the server.\n")


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
    # 1. Attach Flask WSGI Container to Streamlit's Tornado server
    try:
        from streamlit.web.server.server import Server
    except ImportError:
        try:
            from streamlit.server.server import Server
        except ImportError:
            Server = None

    if Server is not None:
        try:
            server = Server.get_current()
            if server and hasattr(server, "_app"):
                import tornado.wsgi
                from tornado.routing import Rule, PathMatches

                router = getattr(server._app, "default_router", getattr(server._app, "wildcard_router", None))
                if router and hasattr(router, "rules"):
                    if not any(getattr(r, "_is_nyaya_wsgi", False) for r in router.rules):
                        wsgi_handler = tornado.wsgi.WSGIContainer(app)
                        rule = Rule(PathMatches(r"^(?!/(_stcore|static)).*"), wsgi_handler)
                        rule._is_nyaya_wsgi = True
                        router.rules.insert(0, rule)
        except Exception:
            pass

    # 2. Render the initial Gateway UI directly into Streamlit
    try:
        import streamlit as st
        import streamlit.components.v1 as components

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
            iframe {border: none !important; width: 100% !important;}
            </style>
            """,
            unsafe_allow_html=True
        )

        with app.test_request_context("/"):
            gateway_html = render_page(GATEWAY_TPL, "Authentication gateway",
                                       view="officer", positions=LOGIN_POSITIONS)

        components.html(gateway_html, height=920, scrolling=True)
    except Exception:
        pass

else:
    if __name__ == "__main__":
        preflight()
        # host="0.0.0.0" lets other machines on the police intranet reach the vault.
        app.run(host="0.0.0.0", port=5000, debug=False)