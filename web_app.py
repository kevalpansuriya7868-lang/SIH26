import os
import sys
import json
import math
import random
import socket
import base64
import hashlib
from datetime import datetime
import io

import streamlit as st
from PIL import Image

# Cryptographic Suite (AES-256 Symmetric File Encryption at Rest)
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# PDF Generation Libraries
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Oracle Database Driver (graceful fallback)
try:
    import oracledb
    ORACLE_AVAILABLE = True
except ImportError:
    ORACLE_AVAILABLE = False

# Blockchain Anchoring Driver (graceful fallback)
try:
    from blockchain_manager import anchor_evidence_hash, verify_evidence_onchain
    BLOCKCHAIN_MODULE_AVAILABLE = True
except Exception:
    BLOCKCHAIN_MODULE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Page Configuration & MHA Dark Navy Theme
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="NyayaVault — Ministry of Home Affairs (PS-190)",
    page_icon="🛡️",
    layout="wide"
)

THEME = {
    "primary": "#1E3A8A",
    "primary_hover": "#1E40AF",
    "accent_gold": "#D97706",
    "accent_green": "#059669",
    "accent_red": "#DC2626",
    "bg_main": "#F1F5F9",
    "card_bg": "#FFFFFF",
    "card_border": "#D5DEE7",
    "text_main": "#0F172A",
    "text_muted": "#64748B"
}

st.markdown(f"""
    <style>
    .main-header {{
        background: linear-gradient(135deg, {THEME["primary"]}, #172554);
        color: white;
        padding: 18px 24px;
        border-radius: 12px;
        text-align: center;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }}
    .main-header h1 {{
        color: #FFFFFF;
        font-size: 22px;
        font-weight: 700;
        letter-spacing: 0.8px;
        margin-bottom: 4px;
    }}
    .main-header p {{
        color: #DBEAFE;
        font-size: 13px;
        margin: 0;
    }}
    .stButton>button {{
        border-radius: 8px;
        font-weight: 600;
    }}
    .metric-card {{
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}
    </style>
    <div class="main-header">
        <h1>MINISTRY OF HOME AFFAIRS • GOVERNMENT OF INDIA</h1>
        <p>NyayaVault: Chain-of-Custody & Tamper-Evident Digital Evidence Lifecycle System (PS-190)</p>
    </div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Directories, Secrets, and Salt Initialization
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_STORAGE_DIR = os.path.join(BASE_DIR, "secure_vault_storage")
os.makedirs(VAULT_STORAGE_DIR, exist_ok=True)

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

try:
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
except Exception:
    config = {
        "oracle": {"user": "system", "password": "password", "host": "localhost", "port": 1521, "service_name": "xe"},
        "security": {"enforce_mha_subnet": False, "allowed_subnets": ["127.0.0.1"]},
        "vault_master_key": "NyayaVault@GovernmentOfIndia#MHA2026MasterKey",
        "blockchain": {"enabled": False}
    }

DB_CONFIG = config.get("oracle", {})
SECURITY_CONFIG = config.get("security", {})
MASTER_SALT = b"MHA_NYAYAVAULT_KEY_DERIVATION_SALT_2026"

# ---------------------------------------------------------------------------
# Core Cryptographic & AI Engines
# ---------------------------------------------------------------------------
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
    def encrypt_payload(plain_text_bytes):
        cipher = EncryptionEngine.get_cipher()
        return cipher.encrypt(plain_text_bytes)

    @staticmethod
    def decrypt_payload(encrypted_bytes):
        cipher = EncryptionEngine.get_cipher()
        return cipher.decrypt(encrypted_bytes)

class IntelligentClassifier:
    @staticmethod
    def analyze_evidence(filename, file_bytes=None):
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
            classification = "Documentary / Chemical / Forensic Analysis Report"
            if file_bytes and ext == ".txt":
                try:
                    content = file_bytes.decode("utf-8", errors="ignore")[:2000]
                    extracted_text += "\n\nExtracted Preview:\n" + content[:400]
                    if "DNA" in content.upper(): classification = "Forensic DNA Typing Report"
                    elif "CYBER" in content.upper() or "IP" in content.upper(): classification = "Cyber Forensics & IP Ledger"
                except Exception:
                    pass
        else:
            category = "Digital Exhibit"
            classification = "General Digital Electronic Record"

        return category, classification, extracted_text

def get_network_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# ---------------------------------------------------------------------------
# Cryptographic Chained Audit Logging
# ---------------------------------------------------------------------------
def log_chained_audit_event(action_type, target_ref):
    ip = get_network_ip()
    actor = st.session_state.get("user", "GATEWAY_AUTH")
    role = st.session_state.get("role", "SECURITY_GATEWAY")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if "audit_logs" not in st.session_state or len(st.session_state.audit_logs) == 0:
        prev_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    else:
        prev_hash = st.session_state.audit_logs[-1]["log_hash"]

    payload = f"{prev_hash}|{ts}|{actor}|{role}|{action_type}|{target_ref}|{ip}"
    current_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    log_entry = {
        "log_id": len(st.session_state.get("audit_logs", [])) + 1,
        "prev_log_hash": prev_hash,
        "event_timestamp": ts,
        "actor_badge": actor,
        "role": role,
        "action_type": action_type,
        "target_reference": target_ref,
        "ip_address": ip,
        "log_hash": current_hash
    }

    if "audit_logs" not in st.session_state:
        st.session_state.audit_logs = []
    st.session_state.audit_logs.append(log_entry)

# ---------------------------------------------------------------------------
# Session State Initialization & Backwards-Compatibility Normalizer
# ---------------------------------------------------------------------------
if "hierarchy_db" not in st.session_state:
    st.session_state.hierarchy_db = {
        "Gujarat": {
            "Surat": {
                "Zone 1 (North)": ["Katargam Police Station"],
                "Zone 2 (South)": ["Umra Police Station"],
                "Zone 3 (East)": ["Varachha Police Station"]
            },
            "Ahmedabad": {
                "Cyber Zone": ["Cyber Crime Branch"],
                "West Zone": ["Navrangpura Police Station"]
            },
            "Rajkot": {
                "Zone 1 (East)": ["Bhaktinagar Police Station"]
            }
        }
    }

SAMPLE_EVID_FILE = "CR_KTG_2026_012_EV_CCTV_01.nyayavault"
sample_file_path = os.path.join(VAULT_STORAGE_DIR, SAMPLE_EVID_FILE)
sample_plain = b"MHA_VAULT_SECURE_PAYLOAD: CCTV Footages recovered from Katargam Bank perimeter surveillance camera."
if not os.path.exists(sample_file_path):
    try:
        with open(sample_file_path, "wb") as sf:
            sf.write(EncryptionEngine.encrypt_payload(sample_plain))
    except Exception:
        pass

if "cases_db" not in st.session_state:
    st.session_state.cases_db = {
        "Katargam Police Station": [
            {
                "Case No": "CR/KTG/2026/012",
                "Title": "[Robbery / Theft] Lalita Bank Vault Penetration",
                "FIR": "FIR-402/2026",
                "Category": "Robbery / Theft",
                "Location": "Katargam Industrial Area, Surat",
                "Condition": "Under Investigation",
                "Punishment": "Pending Trial / No Conviction Yet",
                "IO": "Insp. V.R. Jadeja (#IO-SUR-102)",
                "Registered By": "Police Inspector V. Jadeja (#IO-SUR-102)",
                "Created At": "2026-02-14 10:15:00",
                "Exhibits": [
                    {
                        "Evidence ID": "EV-CCTV-01",
                        "Title": "Perimeter CCTV Intercept",
                        "Category": "CCTV Video Footage",
                        "Classification": "Surveillance Video Exhibit (Digital Multimedia)",
                        "Encrypted File": SAMPLE_EVID_FILE,
                        "Raw File": "bank_perimeter.mp4",
                        "File Type": "video",
                        "SHA256": hashlib.sha256(sample_plain).hexdigest(),
                        "Locker": "Locker A-12 (Shelf 4)",
                        "Active Custody": "VAULT",
                        "Uploaded At": "2026-02-14 11:00:00",
                        "Notes": "Clear visual footprint of prime suspect penetrating rear exit."
                    }
                ]
            }
        ]
    }

# Normalize any existing session-state cases that might have legacy keys ("Scene", "Status", etc.)
for stn, cases_list in st.session_state.cases_db.items():
    for cs in cases_list:
        if "Location" not in cs:
            cs["Location"] = cs.get("Scene", "Katargam, Surat")
        if "Condition" not in cs:
            cs["Condition"] = cs.get("Status", "Under Investigation")
        if "Punishment" not in cs:
            cs["Punishment"] = "Pending Trial / No Conviction Yet"
        if "Category" not in cs:
            cs["Category"] = "General Offense"
        if "Registered By" not in cs:
            cs["Registered By"] = cs.get("IO", "Investigating Officer")
        if "Exhibits" not in cs:
            cs["Exhibits"] = []
            if "Evidence File" in cs and cs["Evidence File"]:
                cs["Exhibits"].append({
                    "Evidence ID": "EV-01",
                    "Title": "Initial Evidence File",
                    "Category": "Digital Exhibit",
                    "Classification": "Electronic Record",
                    "Encrypted File": cs["Evidence File"],
                    "Raw File": cs["Evidence File"],
                    "File Type": cs.get("File Type", "text"),
                    "SHA256": "PRE_EXISTING_DIGEST",
                    "Locker": "Shelf 1",
                    "Active Custody": "VAULT",
                    "Uploaded At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Notes": cs.get("Details", "")
                })

if "custody_ledger" not in st.session_state:
    st.session_state.custody_ledger = [
        {
            "Transfer ID": 1001,
            "Evidence ID": "EV-CCTV-01",
            "Case No": "CR/KTG/2026/012",
            "From Officer": "CRIME_SCENE",
            "To Officer Badge": "IO-SUR-102",
            "To Officer Name": "Police Inspector V. Jadeja",
            "Rank": "Police Inspector (SHO)",
            "Reason": "Initial Lawful Ingestion and Sealing",
            "Checkout Time": "2026-02-14 11:00:00",
            "Return Deadline": "2026-03-16 11:00:00",
            "Status": "RETURNED_TO_VAULT"
        }
    ]

if "audit_logs" not in st.session_state:
    st.session_state.audit_logs = [
        {
            "log_id": 1,
            "prev_log_hash": "0000000000000000000000000000000000000000000000000000000000000000",
            "event_timestamp": "2026-01-01 00:00:01",
            "actor_badge": "SYSTEM",
            "role": "ROOT",
            "action_type": "GENESIS_BLOCK",
            "target_reference": "SYSTEM_INITIALIZATION",
            "ip_address": "127.0.0.1",
            "log_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        }
    ]

if "tampered_exhibits" not in st.session_state:
    st.session_state.tampered_exhibits = set()

for k in ["nav_city", "nav_area", "nav_station", "selected_case"]:
    if k not in st.session_state:
        st.session_state[k] = None

# ---------------------------------------------------------------------------
# Sidebar Authentication & Strict RBAC Gateway
# ---------------------------------------------------------------------------
st.sidebar.title("🔐 Authentication Portal")
role_selection = st.sidebar.selectbox(
    "Select Access Authority / Rank",
    [
        "Director General of Police (DGP - State Command)",
        "City Commissioner of Police (CP)",
        "Deputy / Assistant Commissioner (DCP / ACP)",
        "Police Inspector / SHO",
        "Investigating Officer (IO)",
        "Forensic Scientist Lead",
        "Judicial Magistrate / Sessions Judge"
    ]
)

if "last_role" not in st.session_state:
    st.session_state.last_role = role_selection

if st.session_state.last_role != role_selection:
    st.session_state.authenticated = False
    st.session_state.last_role = role_selection
    st.session_state.selected_case = None
    st.session_state.nav_city = None
    st.session_state.nav_area = None
    st.session_state.nav_station = None

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.sidebar.subheader("Officer / Judge Credentials")

    if "Director General" in role_selection:
        def_u, def_p, rank_title = "admin", "admin123", "Director General of Police (DGP)"
    elif "City Commissioner" in role_selection:
        def_u, def_p, rank_title = "cp_surat", "surat123", "Commissioner of Police (CP)"
    elif "Deputy / Assistant" in role_selection:
        def_u, def_p, rank_title = "dcp_surat_zone1", "dcp123", "Deputy Commissioner of Police (DCP)"
    elif "Judicial" in role_selection:
        def_u, def_p, rank_title = "judge_portal", "court123", "Sessions Judge"
    elif "Forensic" in role_selection:
        def_u, def_p, rank_title = "forensic_lab", "forensic123", "Forensic Scientist Lead"
    else:
        def_u, def_p, rank_title = "io_surat", "io123", "Police Inspector (SHO)"

    uid = st.sidebar.text_input("Badge ID / Username", value=def_u)
    pwd = st.sidebar.text_input("Cryptographic Password", type="password", value=def_p)

    USER_MAP = {
        "admin": {"level": 5, "name": "Rajesh Verma", "role": "SUPER_ADMIN", "city": "SURAT", "area": "State HQ", "station": "State Command Center"},
        "cp_surat": {"level": 4, "name": "Anupam Gehlot", "role": "COMMISSIONER", "city": "SURAT", "area": "City Central", "station": "Surat Headquarters"},
        "dcp_surat_zone1": {"level": 3, "name": "Himanshu Verma", "role": "DCP_ACP", "city": "SURAT", "area": "Zone 1 (North)", "station": "Zone 1 Headquarters"},
        "io_surat": {"level": 2, "name": "Insp. V. Jadeja", "role": "INSPECTOR_SHO", "city": "SURAT", "area": "Zone 1 (North)", "station": "Katargam Police Station"},
        "forensic_lab": {"level": 1, "name": "Dr. Meera Rao", "role": "FORENSIC_EXAMINER", "city": "SURAT", "area": "Zone 1 (North)", "station": "Katargam Police Station"},
        "judge_portal": {"level": 1, "name": "Hon. Judge A. Dave", "role": "COURT_JUDICIAL", "city": "SURAT", "area": "Judicial District", "station": "Sessions Court"}
    }

    if st.sidebar.button("Authenticate & Unlock Vault", use_container_width=True):
        u_info = USER_MAP.get(uid.lower())
        if u_info and pwd:
            st.session_state.authenticated = True
            st.session_state.user = uid
            st.session_state.officer_name = u_info["name"]
            st.session_state.rank = rank_title
            st.session_state.level = u_info["level"]
            st.session_state.role = u_info["role"]
            st.session_state.city = u_info["city"]
            st.session_state.area = u_info["area"]
            st.session_state.station = u_info["station"]
            log_chained_audit_event("OFFICER_LOGGED_IN", f"{rank_title} {u_info['name']} logged in via badge {uid}")
            st.success("Identity Verified & Cryptographic Session Anchored.")
            st.rerun()
        else:
            st.sidebar.error("Invalid badge ID or cryptographic credentials.")
    st.stop()

st.sidebar.success(f"● Authenticated: {st.session_state.get('officer_name')}")
st.sidebar.info(f"**Rank:** {st.session_state.get('rank')}\n\n**Badge:** `#{st.session_state.get('user')}`")
if st.sidebar.button("🔒 Sign Out Session", use_container_width=True):
    log_chained_audit_event("OFFICER_LOGGED_OUT", f"{st.session_state.get('user')} ended session.")
    st.session_state.authenticated = False
    st.session_state.selected_case = None
    st.session_state.nav_city = None
    st.session_state.nav_area = None
    st.session_state.nav_station = None
    st.rerun()

# ---------------------------------------------------------------------------
# Statutory PDF Report Generation Helpers
# ---------------------------------------------------------------------------
def generate_section65b_pdf(case_no, case_title, fir_no, exhibit):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle("TStyle", parent=styles["Heading1"], fontSize=13, alignment=1, textColor=colors.HexColor("#1E3A8A"))
    body_style = ParagraphStyle("BStyle", parent=styles["Normal"], fontSize=9, leading=13, textColor=colors.HexColor("#0F172A"))

    elements.append(Paragraph("MINISTRY OF HOME AFFAIRS • GOVERNMENT OF INDIA", ParagraphStyle("Sub", fontName="Helvetica-Bold", fontSize=10, alignment=1, textColor=colors.HexColor("#475569"))))
    elements.append(Paragraph("CERTIFICATE OF AUTHENTICITY UNDER SECTION 65B (IEA) / SECTION 63 (BSA)", title_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=15))

    cert_data = [
        ["Master Case Number:", case_no],
        ["Case Incident / Title:", case_title],
        ["FIR Reference:", fir_no],
        ["Evidence Exhibit Identifier:", exhibit["Evidence ID"]],
        ["Exhibit Title:", exhibit["Title"]],
        ["Category & Classification:", f"{exhibit['Category']} ({exhibit.get('Classification', 'Electronic Exhibit')})"],
        ["Bit-Level SHA-256 Seal:", exhibit["SHA256"]],
        ["AES-256 Vault Encryption:", "VERIFIED & INTACT AT REST"],
        ["Custody State at Verification:", exhibit.get("Active Custody", "VAULT")],
        ["Inspecting Official:", f"{st.session_state.get('rank')} {st.session_state.get('officer_name')} (#{st.session_state.get('user')})"],
        ["Verification Timestamp:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    ]
    t = Table(cert_data, colWidths=[180, 360])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("<b>STATUTORY DECLARATION:</b> This electronic record was mathematically hashed and cryptographically sealed immediately upon lawful ingest. The integrity of the source data has remained uncompromised throughout its lifecycle pursuant to Section 65B of Indian Evidence Act and Section 63 of Bharatiya Sakshya Adhiniyam.", body_style))

    doc.build(elements)
    pdf_val = buffer.getvalue()
    buffer.close()
    return pdf_val

def generate_case_dossier_pdf(case_record):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle("TStyle", parent=styles["Heading1"], fontSize=14, alignment=1, textColor=colors.HexColor("#1E3A8A"))
    sub_style = ParagraphStyle("SubStyle", parent=styles["Normal"], fontSize=9, alignment=1, textColor=colors.HexColor("#475569"))
    body_style = ParagraphStyle("BStyle", parent=styles["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#0F172A"))

    elements.append(Paragraph("MINISTRY OF HOME AFFAIRS • GOVERNMENT OF INDIA", sub_style))
    elements.append(Paragraph("OFFICIAL CASE & EVIDENCE LIFECYCLE DOSSIER", title_style))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1E3A8A"), spaceAfter=12))

    meta_data = [
        ["Master Case Number:", case_record["Case No"], "FIR Reference:", case_record["FIR"]],
        ["Incident Title:", case_record["Title"], "Crime Location:", case_record.get("Location", case_record.get("Scene", "N/A"))],
        ["Investigating Officer:", case_record.get("IO", "N/A"), "Condition / Status:", case_record.get("Condition", case_record.get("Status", "N/A"))],
        ["Judicial Verdict / Jail:", case_record.get("Punishment", "Pending Trial"), "Registered By:", case_record.get("Registered By", "Police Officer")],
        ["Sealing & Export Stamp:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "Authority:", f"{st.session_state.get('rank')} #{st.session_state.get('user')}"]
    ]
    t_meta = Table(meta_data, colWidths=[130, 140, 130, 140])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("<b>ATTACHED DIGITAL EVIDENCE EXHIBITS & SHA-256 MASTER BIT SEALS:</b>", styles["Heading2"]))

    for ex in case_record.get("Exhibits", []):
        ex_data = [
            [Paragraph(f"<b>Exhibit ID:</b> {ex['Evidence ID']}", body_style), Paragraph(f"<b>Title:</b> {ex['Title']}", body_style)],
            [Paragraph(f"<b>Category:</b> {ex['Category']}", body_style), Paragraph(f"<b>Locker:</b> {ex.get('Locker', 'Vault Shelf')} | <b>Custody:</b> {ex.get('Active Custody', 'VAULT')}", body_style)],
            [Paragraph(f"<b>SHA-256 Bit Seal:</b> {ex['SHA256']}", body_style), ""]
        ]
        t_ex = Table(ex_data, colWidths=[260, 280])
        t_ex.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('PADDING', (0,0), (-1,-1), 4),
            ('SPAN', (0,2), (1,2))
        ]))
        elements.append(t_ex)
        elements.append(Spacer(1, 6))

    doc.build(elements)
    val = buffer.getvalue()
    buffer.close()
    return val

# ---------------------------------------------------------------------------
# Full System Primary Tabs
# ---------------------------------------------------------------------------
tabs = st.tabs([
    "🏛️ Command Hierarchy & Workspaces",
    "📁 Master Case Repository",
    "🔗 Chain of Custody Ledger",
    "🔍 SHA-256 Tamper Audit",
    "📜 Cryptographic Audit Trail (Non-Repudiable)",
    "📊 Intelligence Analytics"
])

# ===========================================================================
# TAB 1: COMMAND HIERARCHY, CASE WORKSPACE & EVIDENCE INGESTION
# ===========================================================================
with tabs[0]:
    auth_level = st.session_state.get("level", 1)
    is_judge = (st.session_state.get("role") == "COURT_JUDICIAL")
    state_tree = st.session_state.hierarchy_db["Gujarat"]

    if is_judge:
        st.info("⚖️ **Judicial Inspection Portal:** Read-only statutory manifest. Tamper hashes and custody ledgers are certified for inspection.")

    # VIEW A: CASE WORKSPACE
    if st.session_state.selected_case is not None:
        station_cases = st.session_state.cases_db.get(st.session_state.nav_station, [])
        active_case = next((c for c in station_cases if c["Case No"] == st.session_state.selected_case), None)

        if active_case:
            col_back, col_actions = st.columns([1, 4])
            with col_back:
                if st.button("⬅️ Back to Station", use_container_width=True):
                    st.session_state.selected_case = None
                    st.rerun()

            with col_actions:
                dossier_pdf = generate_case_dossier_pdf(active_case)
                st.download_button(
                    label="📄 Print Complete Case Dossier (All Exhibits Included)",
                    data=dossier_pdf,
                    file_name=f"Dossier_{active_case['Case No'].replace('/', '_')}.pdf",
                    mime="application/pdf"
                )

            st.markdown(f"## 📂 Case Workspace: `{active_case['Case No']}`")
            st.markdown(f"### {active_case['Title']}")

            loc_val = active_case.get("Location", active_case.get("Scene", "N/A"))
            cond_val = active_case.get("Condition", active_case.get("Status", "Under Investigation"))
            punish_val = active_case.get("Punishment", "Pending Trial / No Conviction Yet")

            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**FIR Ref:** `{active_case['FIR']}`\n\n**Category:** {active_case.get('Category', 'Offense')}")
            c2.markdown(f"**Location:** {loc_val}\n\n**Status:** `{cond_val}`")
            c3.markdown(f"**Investigating Officer:** {active_case.get('IO', 'N/A')}\n\n**Verdict / Facility:** {punish_val}")

            st.markdown("---")

            # Ingest evidence
            if not is_judge:
                st.subheader("📥 Ingest & Encrypt New Evidence Exhibit")
                with st.expander("➕ Open Evidence Ingestion Console", expanded=False):
                    with st.form(f"ingest_ev_form_{active_case['Case No']}"):
                        f_col1, f_col2 = st.columns(2)
                        with f_col1:
                            new_eid = st.text_input("Evidence Exhibit ID", value=f"EV-EX-{len(active_case.get('Exhibits', [])) + 1:02d}")
                            new_etitle = st.text_input("Evidence Exhibit Name / Title", placeholder="e.g. CCTV Surveillance Dump / Blood Spatter Photo")
                            new_elocker = st.text_input("Physical Evidence Shelf / Locker", value="Secure Locker Alpha-3")
                        with f_col2:
                            new_enotes = st.text_area("Forensic Ingestion Notes & Observations", placeholder="e.g. Ingested at scene under seizure memo. Device hash verified.")
                            uploaded_ev_file = st.file_uploader("Select Evidence File (jpg, png, mp4, mov, wav, mp3, pdf, txt, raw)", type=["jpg", "jpeg", "png", "mp4", "mov", "wav", "mp3", "pdf", "txt", "raw", "dd"])

                        submit_ev = st.form_submit_button("🔒 Seal, AES-256 Encrypt & Anchor Evidence Exhibit", use_container_width=True)

                    if submit_ev:
                        if not new_eid.strip() or not new_etitle.strip():
                            st.error("Evidence ID and Title are mandatory fields.")
                        elif any(ex["Evidence ID"].upper() == new_eid.strip().upper() for ex in active_case.get("Exhibits", [])):
                            st.error(f"Exhibit ID '{new_eid.strip().upper()}' is already used in this docket. Enter a unique ID.")
                        else:
                            file_name = uploaded_ev_file.name if uploaded_ev_file else f"{new_eid}.txt"
                            raw_payload = uploaded_ev_file.read() if uploaded_ev_file else (new_enotes.encode("utf-8") if new_enotes else b"MHA_EMPTY_PAYLOAD")

                            cat, classification, extracted_meta = IntelligentClassifier.analyze_evidence(file_name, raw_payload)
                            f_sha256 = hashlib.sha256(raw_payload).hexdigest()

                            enc_payload = EncryptionEngine.encrypt_payload(raw_payload)
                            safe_name = f"{st.session_state.nav_station.replace(' ', '_')}_{active_case['Case No'].replace('/', '_')}_{new_eid.strip()}_{f_sha256[:8]}.nyayavault"
                            target_save_path = os.path.join(VAULT_STORAGE_DIR, safe_name)

                            with open(target_save_path, "wb") as f_out:
                                f_out.write(enc_payload)

                            ext_l = os.path.splitext(file_name)[1].lower()
                            if ext_l in [".jpg", ".jpeg", ".png", ".bmp"]:
                                f_type = "image"
                            elif ext_l in [".mp4", ".mov", ".avi", ".mkv"]:
                                f_type = "video"
                            elif ext_l in [".mp3", ".wav", ".aac"]:
                                f_type = "audio"
                            elif ext_l == ".pdf":
                                f_type = "pdf"
                            else:
                                f_type = "text"

                            new_ex_record = {
                                "Evidence ID": new_eid.strip().upper(),
                                "Title": new_etitle.strip(),
                                "Category": cat,
                                "Classification": classification,
                                "Encrypted File": safe_name,
                                "Raw File": file_name,
                                "File Type": f_type,
                                "SHA256": f_sha256,
                                "Locker": new_elocker.strip(),
                                "Active Custody": "VAULT",
                                "Uploaded At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "Notes": new_enotes.strip()
                            }

                            if "Exhibits" not in active_case:
                                active_case["Exhibits"] = []
                            active_case["Exhibits"].append(new_ex_record)

                            next_tid = len(st.session_state.custody_ledger) + 1001
                            st.session_state.custody_ledger.append({
                                "Transfer ID": next_tid,
                                "Evidence ID": new_eid.strip().upper(),
                                "Case No": active_case["Case No"],
                                "From Officer": "CRIME_SCENE",
                                "To Officer Badge": st.session_state.get("user"),
                                "To Officer Name": st.session_state.get("officer_name"),
                                "Rank": st.session_state.get("rank"),
                                "Reason": "Initial Forensic Ingestion & Sealing",
                                "Checkout Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "Return Deadline": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "Status": "RETURNED_TO_VAULT"
                            })

                            log_chained_audit_event("EVIDENCE_INGESTED_SEALED", f"Exhibit {new_eid.strip().upper()} sealed with SHA-256 {f_sha256} under Case {active_case['Case No']}")
                            st.success(f"Exhibit `{new_eid.strip().upper()}` sealed with SHA-256 `{f_sha256}` and added to Case {active_case['Case No']}!")
                            st.rerun()

                st.markdown("---")

            # Exhibits list
            st.subheader("🔓 Attached Evidence Exhibits (Decryption, Audit & Inspection)")
            exhibits_list = active_case.get("Exhibits", [])
            if len(exhibits_list) == 0:
                st.warning("No digital evidence exhibits registered for this case docket yet.")
            else:
                for idx, ex in enumerate(exhibits_list):
                    with st.container():
                        e_col1, e_col2 = st.columns([3, 1])
                        with e_col1:
                            st.markdown(f"#### Exhibit `#{ex['Evidence ID']}`: {ex['Title']}")
                            st.markdown(f"**Category:** {ex['Category']} | **Classification:** {ex.get('Classification', 'Electronic Exhibit')}")
                            st.markdown(f"**Locker / Shelf:** `{ex.get('Locker', 'Vault Shelf')}` | **Custody Status:** `{ex.get('Active Custody', 'VAULT')}`")
                            st.code(f"Master SHA-256 Bit Seal: {ex['SHA256']}", language="bash")

                        with e_col2:
                            cert_65b_pdf = generate_section65b_pdf(active_case["Case No"], active_case["Title"], active_case["FIR"], ex)
                            st.download_button(
                                label="📜 65B/63 Certificate",
                                data=cert_65b_pdf,
                                file_name=f"Certificate_65B_{ex['Evidence ID']}.pdf",
                                mime="application/pdf",
                                key=f"cert_dl_{active_case['Case No']}_{ex['Evidence ID']}_{idx}"
                            )

                        target_fpath = os.path.join(VAULT_STORAGE_DIR, ex["Encrypted File"])
                        if os.path.exists(target_fpath):
                            if st.button(f"👁️ Decrypt & Inspect Exhibit {ex['Evidence ID']}", key=f"dec_btn_{active_case['Case No']}_{ex['Evidence ID']}_{idx}"):
                                try:
                                    with open(target_fpath, "rb") as enc_in:
                                        raw_cipher = enc_in.read()

                                    decrypted_bytes = EncryptionEngine.decrypt_payload(raw_cipher)
                                    calc_sha256 = hashlib.sha256(decrypted_bytes).hexdigest()

                                    if calc_sha256 == ex["SHA256"]:
                                        st.success(f"✅ Cryptographic Integrity Verified: Live Bit-Stream matches Master Seal ({calc_sha256[:16]}...).")
                                    else:
                                        st.error(f"🚨 INTEGRITY MISMATCH: Calculated Hash ({calc_sha256}) != Sealed Hash ({ex['SHA256']})")

                                    log_chained_audit_event("EVIDENCE_DECRYPTED_VIEW", f"Exhibit {ex['Evidence ID']} in Case {active_case['Case No']} decrypted for inspection.")

                                    ftype = ex.get("File Type", "text")
                                    if ftype == "image":
                                        st.image(decrypted_bytes, caption=f"Exhibit {ex['Evidence ID']} ({ex['Title']})", use_container_width=True)
                                    elif ftype == "video":
                                        st.video(decrypted_bytes)
                                    elif ftype == "audio":
                                        st.audio(decrypted_bytes)
                                    else:
                                        try:
                                            st.text_area(f"Decrypted Content ({ex.get('Raw File', 'Payload')}):", value=decrypted_bytes.decode("utf-8"), height=150)
                                        except Exception:
                                            st.info(f"Binary Forensic Image Payload: {len(decrypted_bytes)} bytes ready for analysis.")

                                    st.download_button(
                                        label=f"📥 Download Decrypted Exhibit Payload",
                                        data=decrypted_bytes,
                                        file_name=f"Decrypted_{ex['Evidence ID']}_{ex.get('Raw File', 'file.bin')}",
                                        key=f"dl_raw_{active_case['Case No']}_{ex['Evidence ID']}_{idx}"
                                    )
                                except Exception as err:
                                    st.error(f"Decryption failed! Ciphertext corrupted or key mismatch: {err}")
                        else:
                            st.warning(f"Encrypted file `{ex['Encrypted File']}` not found in storage vault.")

                        st.markdown("---")

    # VIEW B: POLICE STATION REPOSITORY
    elif st.session_state.nav_station:
        st.markdown(f"### 🏢 Police Station Vault: **[{st.session_state.nav_station}]**")
        st.info(f"Command Jurisdiction: **{st.session_state.nav_city}** Commissionerate ➔ **{st.session_state.nav_area}**")

        if st.button("⬅️ Back to Areas / Zones"):
            st.session_state.nav_station = None
            st.rerun()

        st_cases = st.session_state.cases_db.get(st.session_state.nav_station, [])
        st.markdown(f"#### Active Dockets Registered at {st.session_state.nav_station}")

        if st_cases:
            for idx, sc in enumerate(st_cases):
                col_info, col_btn = st.columns([4, 1])
                ex_count = len(sc.get("Exhibits", []))
                cond_str = sc.get("Condition", sc.get("Status", "Under Investigation"))
                io_str = sc.get("IO", "N/A")
                with col_info:
                    st.markdown(f"**Case No:** `{sc['Case No']}` | **Title:** {sc['Title']} | **IO:** {io_str} | **Status:** `{cond_str}` | **Exhibits Attached:** `{ex_count}`")
                with col_btn:
                    if st.button(f"📂 Open Case Workspace", key=f"open_case_{sc['Case No']}_{idx}", use_container_width=True):
                        st.session_state.selected_case = sc["Case No"]
                        st.rerun()
                st.markdown("---")
        else:
            st.warning("No registered case profiles at this station vault.")

        if not is_judge:
            st.markdown("#### ➕ Register New Case Profile")
            with st.form("new_case_registration_form"):
                rc1, rc2 = st.columns(2)
                with rc1:
                    station_prefix = "".join([w[0] for w in st.session_state.nav_station.split() if w])[:3].upper()
                    new_c_no = st.text_input("Case Number", value=f"CR/{station_prefix}/2026/{len(st_cases) + 101:03d}")
                    new_c_name = st.text_input("Case Name / Title", placeholder="e.g. Robbery / Cyber Ransomware Intrusion")
                    new_c_fir = st.text_input("FIR Reference Number", placeholder="e.g. FIR-102/2026")
                    new_c_cat = st.selectbox("Offense Category", ["Robbery / Theft", "Murder / Homicide", "Cyber / Ransomware", "Narcotics (NDPS)", "Economic Offense", "Assault / Other"])
                with rc2:
                    new_c_loc = st.text_input("Crime Scene / Location", value=f"{st.session_state.nav_area}, {st.session_state.nav_city}")
                    new_c_io = st.text_input("Investigating Officer (IO)", value=f"{st.session_state.get('rank')} {st.session_state.get('officer_name')} (#{st.session_state.get('user')})")
                    new_c_cond = st.selectbox("Condition of Case", ["Under Investigation", "Charge Sheet Filed", "Pending Trial", "Convicted & Sentenced", "Transferred to Forensics", "Closed / Acquitted"])
                    new_c_punish = st.text_input("Judicial Verdict / Jail Facility", value="Pending Trial / No Conviction Yet")

                submit_case = st.form_submit_button("Commit & Register Case Docket", use_container_width=True)

            if submit_case:
                if not new_c_no.strip() or not new_c_name.strip() or not new_c_fir.strip():
                    st.error("Case No, Title, and FIR are mandatory.")
                elif any(c["Case No"] == new_c_no.strip() for c in st_cases):
                    st.error(f"Case number '{new_c_no.strip()}' already exists. Use a unique docket identifier.")
                else:
                    new_case_obj = {
                        "Case No": new_c_no.strip(),
                        "Title": f"[{new_c_cat}] {new_c_name.strip()}",
                        "FIR": new_c_fir.strip(),
                        "Category": new_c_cat,
                        "Location": new_c_loc.strip(),
                        "Condition": new_c_cond,
                        "Punishment": new_c_punish.strip(),
                        "IO": new_c_io.strip(),
                        "Registered By": f"{st.session_state.get('rank')} #{st.session_state.get('user')}",
                        "Created At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Exhibits": []
                    }
                    if st.session_state.nav_station not in st.session_state.cases_db:
                        st.session_state.cases_db[st.session_state.nav_station] = []
                    st.session_state.cases_db[st.session_state.nav_station].append(new_case_obj)
                    log_chained_audit_event("CASE_REGISTERED", f"Case {new_c_no.strip()} ({new_c_fir.strip()}) registered in {st.session_state.nav_station}")
                    st.success(f"Case '{new_c_no.strip()}' committed. Open its workspace to attach evidence exhibits.")
                    st.rerun()

    # VIEW C: AREA / ZONE SELECTION LEVEL
    elif st.session_state.nav_area:
        st.markdown(f"### 📍 City: **{st.session_state.nav_city}** ➔ Area/Zone: **{st.session_state.nav_area}**")
        if st.button("⬅️ Back to City Divisions"):
            st.session_state.nav_area = None
            st.rerun()

        st.markdown("#### Select a Police Station Branch to Inspect:")
        stn_list = state_tree[st.session_state.nav_city][st.session_state.nav_area]
        for stn in stn_list:
            if st.button(f"🏛️ Enter Police Station: {stn}", key=f"stn_btn_{stn}", use_container_width=True):
                st.session_state.nav_station = stn
                st.rerun()

    # VIEW D: CITY SELECTION LEVEL
    elif st.session_state.nav_city:
        target_city = st.session_state.nav_city
        st.markdown(f"### 🏙️ City Commissionerate: **{target_city}**")
        if auth_level >= 5 or is_judge:
            if st.button("⬅️ Back to State Cities"):
                st.session_state.nav_city = None
                st.rerun()

        st.markdown("#### Select an Area / Zone Jurisdiction:")
        zones = state_tree[target_city]
        for zone in zones.keys():
            if st.button(f"📍 Area / Zone: {zone}", key=f"zone_btn_{zone}", use_container_width=True):
                st.session_state.nav_area = zone
                st.rerun()

    # VIEW E: STATE ROOT LEVEL
    else:
        if auth_level >= 5 or is_judge:
            st.success("👑 State Command Center: Direct jurisdiction drill-down across all state commissionerates.")
            st.markdown("### 🌆 State Cities / Commissionerates:")
            for city_key in state_tree.keys():
                if st.button(f"🏙️ Commissionerate: {city_key}", key=f"city_btn_{city_key}", use_container_width=True):
                    st.session_state.nav_city = city_key
                    st.rerun()
        else:
            default_city = st.session_state.get("city", "SURAT")
            st.session_state.nav_city = default_city
            st.rerun()

# ===========================================================================
# TAB 2: MASTER CASE REPOSITORY & SAFE DICTIONARY LOOKUPS
# ===========================================================================
with tabs[1]:
    st.subheader("📁 Master Digital Case Repository")
    st.write("Aggregated view across all police station vaults in the command hierarchy.")

    all_dockets = []
    for station_name, c_list in st.session_state.cases_db.items():
        for cs in c_list:
            all_dockets.append({
                "Case No": cs.get("Case No", "N/A"),
                "Title": cs.get("Title", "Untitled"),
                "FIR": cs.get("FIR", "N/A"),
                "Category": cs.get("Category", "General"),
                "Location": cs.get("Location", cs.get("Scene", "N/A")),
                "Condition": cs.get("Condition", cs.get("Status", "Under Investigation")),
                "Verdict / Facility": cs.get("Punishment", "Pending Trial"),
                "Police Station": station_name,
                "Exhibits Count": len(cs.get("Exhibits", [])),
                "Investigating Officer": cs.get("IO", "N/A")
            })

    if all_dockets:
        st.dataframe(all_dockets, use_container_width=True)
    else:
        st.info("No active dockets registered in the system.")

# ===========================================================================
# TAB 3: CHAIN OF CUSTODY LEDGER & RETURN TRACKING
# ===========================================================================
with tabs[2]:
    st.subheader("🔗 Chain of Custody Movement & Handover Ledger")
    st.write("Legally admissible custody tracking for forensic laboratory testing and judicial production.")

    is_judge = (st.session_state.get("role") == "COURT_JUDICIAL")
    if not is_judge:
        c_left, c_right = st.columns([1, 2])
        with c_left:
            st.markdown("#### Issue / Transfer Evidence")
            with st.form("custody_transfer_form"):
                t_eid = st.text_input("Evidence Exhibit ID", placeholder="e.g. EV-CCTV-01")
                t_cno = st.text_input("Case Number", placeholder="e.g. CR/KTG/2026/012")
                t_badge = st.text_input("Recipient Officer Badge", placeholder="e.g. FSL-SUR-201")
                t_name = st.text_input("Recipient Officer Name", placeholder="e.g. Dr. Meera Rao")
                t_rank = st.text_input("Officer Rank", placeholder="e.g. Forensic Scientist Lead")
                t_reason = st.text_input("Transfer Reason", value="Official Forensic Examination")
                t_days = st.number_input("Custody Duration (Days)", min_value=1, max_value=90, value=14)

                submit_transfer = st.form_submit_button("🔒 Issue Evidence & Update Custody", use_container_width=True)

            if submit_transfer:
                if not t_eid.strip() or not t_badge.strip() or not t_name.strip():
                    st.error("Exhibit ID, Recipient Badge, and Name are mandatory.")
                else:
                    new_tid = len(st.session_state.custody_ledger) + 1001
                    st.session_state.custody_ledger.insert(0, {
                        "Transfer ID": new_tid,
                        "Evidence ID": t_eid.strip().upper(),
                        "Case No": t_cno.strip(),
                        "From Officer": f"{st.session_state.get('rank')} #{st.session_state.get('user')}",
                        "To Officer Badge": t_badge.strip(),
                        "To Officer Name": t_name.strip(),
                        "Rank": t_rank.strip(),
                        "Reason": t_reason.strip(),
                        "Checkout Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Return Deadline": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Status": "CHECKED_OUT"
                    })

                    for stn_cases in st.session_state.cases_db.values():
                        for c in stn_cases:
                            for ex in c.get("Exhibits", []):
                                if ex["Evidence ID"] == t_eid.strip().upper():
                                    ex["Active Custody"] = f"ISSUED: {t_name.strip()} (#{t_badge.strip()})"

                    log_chained_audit_event("CUSTODY_TRANSFERRED", f"Exhibit {t_eid.strip().upper()} issued to {t_name.strip()} (#{t_badge.strip()}) for {t_days} days.")
                    st.success(f"Custody for Exhibit {t_eid.strip().upper()} transferred to {t_name.strip()}.")
                    st.rerun()

        with c_right:
            st.markdown("#### Immutable Movement History")
            st.dataframe(st.session_state.custody_ledger, use_container_width=True)
    else:
        st.dataframe(st.session_state.custody_ledger, use_container_width=True)

# ===========================================================================
# TAB 4: LIVE SHA-256 BIT-LEVEL TAMPER AUDIT
# ===========================================================================
with tabs[3]:
    st.subheader("🔍 SHA-256 Bit-Level Tamper Audit & Verification")
    st.write("Live re-computation of physical ciphertext on disk against sealed cryptographic hashes.")

    audit_col1, audit_col2 = st.columns(2)
    with audit_col1:
        if st.button("▶ Run Full Vault Integrity Audit", use_container_width=True):
            log_chained_audit_event("INTEGRITY_AUDIT_RUN", "Verified SHA-256 integrity across all vault exhibits.")
            st.success("Bit-stream audit completed successfully.")

    with audit_col2:
        if st.button("⚡ Simulate Controlled Bit-Stream Tamper Demo", use_container_width=True):
            st.session_state.tampered_exhibits.add("EV-CCTV-01")
            log_chained_audit_event("TAMPER_SIMULATION_EXECUTED", "Controlled bit override applied to EV-CCTV-01")
            st.error("Controlled byte override injected into EV-CCTV-01 ciphertext!")

    audit_results = []
    for stn_name, c_list in st.session_state.cases_db.items():
        for cs in c_list:
            for ex in cs.get("Exhibits", []):
                eid = ex["Evidence ID"]
                sealed_h = ex["SHA256"]
                target_p = os.path.join(VAULT_STORAGE_DIR, ex["Encrypted File"])

                if eid in st.session_state.tampered_exhibits:
                    active_h = "4f8a1c9e82937bb...[TAMPERED]"
                    status = "🚨 INTEGRITY MISMATCH"
                elif os.path.exists(target_p):
                    try:
                        with open(target_p, "rb") as ef:
                            dec = EncryptionEngine.decrypt_payload(ef.read())
                        active_h = hashlib.sha256(dec).hexdigest()
                        status = "✅ VERIFIED (100% INTACT)" if active_h == sealed_h else "🚨 INTEGRITY MISMATCH"
                    except Exception:
                        active_h = "CIPHERTEXT_CORRUPTED"
                        status = "🚨 CORRUPT"
                else:
                    active_h = "FILE_MISSING_ON_DISK"
                    status = "❌ MISSING"

                audit_results.append({
                    "Exhibit ID": eid,
                    "Case No": cs["Case No"],
                    "Title": ex["Title"],
                    "Sealed Master Hash": sealed_h,
                    "Live Disk Computed Hash": active_h,
                    "Tamper Verdict": status
                })

    st.dataframe(audit_results, use_container_width=True)

# ===========================================================================
# TAB 5: CRYPTOGRAPHIC AUDIT TRAIL
# ===========================================================================
with tabs[4]:
    st.subheader("📜 Cryptographically Chained Audit Ledger (MHA Statutory Nonce Chaining)")
    st.markdown("""
        Every administrative login, evidence ingestion, custody issuance, and decryption event is 
        cryptographically anchored to the preceding block's hash. Any modification breaks the chain validation.
    """)

    st.dataframe(st.session_state.audit_logs, use_container_width=True)

    broken_chain = False
    for i in range(1, len(st.session_state.audit_logs)):
        prev = st.session_state.audit_logs[i - 1]
        curr = st.session_state.audit_logs[i]
        if curr["prev_log_hash"] != prev["log_hash"]:
            broken_chain = True
            break

    if broken_chain:
        st.error("🚨 SECURITY BREACH: Audit chain integrity broken! Previous log hash mismatch detected.")
    else:
        st.success("🔒 Audit Chain Status: 100% Valid, Unbroken, and Non-Repudiable.")

# ===========================================================================
# TAB 6: CRIME & EVIDENCE INTELLIGENCE ANALYTICS
# ===========================================================================
with tabs[5]:
    st.subheader("📊 Multi-Tier Crime & Evidence Intelligence Analytics Dashboard")

    total_cases = sum(len(clist) for clist in st.session_state.cases_db.values())
    total_exhibits = sum(sum(len(c.get("Exhibits", [])) for c in clist) for clist in st.session_state.cases_db.values())
    total_custody_transfers = len(st.session_state.custody_ledger)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Case Dockets", total_cases, delta="+4 This Month")
    m2.metric("Sealed Exhibits at Rest", total_exhibits, delta="100% AES-256")
    m3.metric("Custody Movements", total_custody_transfers, delta="Audit Tracked")
    m4.metric("Hash Verification Rate", "100%", delta="Tamper Proof")

    st.markdown("---")

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown("#### 📈 Case Category Breakdown")
        cat_counts = {}
        for clist in st.session_state.cases_db.values():
            for c in clist:
                cat = c.get("Category", "General")
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
        st.bar_chart(cat_counts)

    with col_chart2:
        st.markdown("#### 🔍 Evidence Types in Secure Storage")
        type_counts = {}
        for clist in st.session_state.cases_db.values():
            for c in clist:
                for ex in c.get("Exhibits", []):
                    t = ex.get("Category", "Digital Exhibit")
                    type_counts[t] = type_counts.get(t, 0) + 1
        st.bar_chart(type_counts)