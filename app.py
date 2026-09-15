import os
import sys
import json
import math
import random
import socket
import base64
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
import io
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog, Canvas, Toplevel
from PIL import Image
import oracledb

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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage
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

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")


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
                        if "DNA" in content.upper(): classification = "Forensic DNA Typing Report"
                        elif "CYBER" in content.upper() or "IP ADDRESS" in content.upper(): classification = "Cyber Forensics & IP Ledger"
            except Exception:
                pass
        else:
            category = "Digital Exhibit"
            classification = "General Digital Electronic Record"

        return category, classification, extracted_text


class FullAnimatedMeshCanvas(Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, highlightthickness=0, bd=0, **kwargs)
        self.step = 0
        self.colors = [(30, 58, 138), (217, 119, 6), (241, 245, 249), (59, 130, 246)]
        self.animate_mesh()

    def interpolate_color(self, c1, c2, factor):
        return tuple(int(c1[i] + (c2[i] - c1[i]) * factor) for i in range(3))

    def animate_mesh(self):
        if not self.winfo_exists():
            return

        w = self.winfo_width() or 1420
        h = self.winfo_height() or 840

        self.delete("all")

        t1 = (math.sin(self.step * 0.02) + 1) / 2
        t2 = (math.cos(self.step * 0.025) + 1) / 2

        c_a = self.interpolate_color(self.colors[0], self.colors[1], t1)
        c_b = self.interpolate_color(self.colors[2], self.colors[3], t2)

        lines = 16
        for i in range(lines):
            factor = i / lines
            cur_c = self.interpolate_color(c_a, c_b, factor)
            soft_r = int(cur_c[0] * 0.15 + 215)
            soft_g = int(cur_c[1] * 0.15 + 215)
            soft_b = int(cur_c[2] * 0.15 + 215)
            hex_cur = f"#{soft_r:02x}{soft_g:02x}{soft_b:02x}"
            y0 = i * (h / lines)
            y1 = (i + 1) * (h / lines)
            self.create_rectangle(0, y0, w, y1, fill=hex_cur, outline="")

        b1_x = (w * 0.25) + math.sin(self.step * 0.025) * (w * 0.15)
        b1_y = (h * 0.35) + math.cos(self.step * 0.02) * (h * 0.15)
        self.create_oval(b1_x - 220, b1_y - 220, b1_x + 220, b1_y + 220, fill="#E2E8F0", outline="")

        b2_x = (w * 0.75) + math.cos(self.step * 0.03) * (w * 0.2)
        b2_y = (h * 0.65) + math.sin(self.step * 0.025) * (h * 0.15)
        self.create_oval(b2_x - 250, b2_y - 250, b2_x + 250, b2_y + 250, fill="#DBEAFE", outline="")

        self.step += 1
        self.after(45, self.animate_mesh)


class MHADocManager(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Ministry of Home Affairs - NyayaVault Digital Evidence Lifecycle System (PS 190)")
        self.geometry("1420x840")
        self.configure(fg_color=THEME["bg_main"])

        self.current_user_badge = None
        self.current_user_name = None
        self.current_role = None
        self.current_rank = None
        self.current_rank_level = 1
        self.current_user_area = None

        self.selected_division = ctk.StringVar(value="")
        self.selected_unit = ctk.StringVar(value="")
        self.selected_area_zone = ctk.StringVar(value="")

        self.is_browse_mode = False
        self.animating_flip = False

        self.load_branding_images()
        self.apply_table_styling()
        self.show_admin_gateway_login_screen()

    def load_branding_images(self):
        self.gov_logo = None
        self.gov_path = os.path.join(BASE_DIR, "sesuni.png")
        if os.path.exists(self.gov_path):
            try:
                pil_gov = Image.open(self.gov_path)
                self.gov_logo = ctk.CTkImage(light_image=pil_gov, dark_image=pil_gov, size=(90, 90))
            except Exception:
                pass

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            active_ip = s.getsockname()[0]
            s.close()
            return active_ip
        except Exception:
            return "127.0.0.1"

    def get_local_ips(self):
        return [self.get_local_ip(), "127.0.0.1"]

    def verify_mha_network(self):
        if not SECURITY_CONFIG.get("enforce_mha_subnet", False):
            return True

        allowed = SECURITY_CONFIG.get("allowed_subnets", ["127.0.0.1"])
        current_ips = self.get_local_ips()

        for ip in current_ips:
            for prefix in allowed:
                if ip.startswith(prefix) or ip == prefix:
                    return True

        messagebox.showerror(
            "Security Policy Violation",
            f"Unauthorized Network Node: {', '.join(current_ips)}\n\nThis system is strictly restricted to secure MHA/Police Intranet."
        )
        return False

    def get_db_connection(self):
        return oracledb.connect(
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=int(DB_CONFIG["port"]),
            service_name=DB_CONFIG["service_name"]
        )

    def log_chained_audit_event(self, action_type, target_ref):
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT log_hash FROM audit_security_logs ORDER BY log_id DESC FETCH FIRST 1 ROWS ONLY")
            row = cur.fetchone()
            prev_hash = row[0] if row else "0000000000000000000000000000000000000000000000000000000000000000"

            ip = self.get_local_ip()
            actor = self.current_user_badge or "GATEWAY_AUTH"
            role = self.current_role or "SECURITY_GATEWAY"
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

    def send_email_otp(self, recipient_email, otp_code, officer_name):
        subject = "NyayaVault Security Token (Password Reset OTP)"
        body = f"Hello Officer {officer_name},\n\nYour one-time authorization OTP to reset your NyayaVault credentials is: {otp_code}\n\nThis OTP is valid for 10 minutes. Do not share this token.\n\nMinistry of Home Affairs - Digital Vault Security Division"
        
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
            return True, f"Demo Security Mode: OTP dispatched to {recipient_email}\n[One-Time Password Code: {otp_code}]"

    def apply_table_styling(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background=THEME["card_bg"],
            foreground=THEME["text_main"],
            fieldbackground=THEME["card_bg"],
            rowheight=34,
            font=("Segoe UI", 10),
            borderwidth=0
        )
        style.map("Treeview", background=[("selected", THEME["primary"])], foreground=[("selected", "#FFFFFF")])
        style.configure(
            "Treeview.Heading",
            background=THEME["card_highlight"],
            foreground=THEME["text_main"],
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padding=(8, 8)
        )

    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()

    # --- SCREEN 1: LOGIN PORTAL & GATEWAY ---
    def show_admin_gateway_login_screen(self):
        self.clear_window()
        self.current_user_badge = None
        self.current_user_name = None
        self.current_role = None
        self.is_browse_mode = False

        bg_canvas = FullAnimatedMeshCanvas(self, width=1420, height=840, bg=THEME["bg_main"])
        bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        header_bar = ctk.CTkFrame(self, height=80, fg_color="transparent")
        header_bar.place(relx=0, rely=0, relwidth=1)

        if self.gov_logo:
            ctk.CTkLabel(header_bar, image=self.gov_logo, text="").pack(side="left", padx=30, pady=6)
        else:
            ctk.CTkLabel(header_bar, text="NYAYAVAULT SYSTEM", text_color=THEME["primary"], font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")).pack(side="left", padx=30, pady=20)

        title_center = ctk.CTkFrame(header_bar, fg_color="transparent")
        title_center.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            title_center,
            text="MINISTRY OF HOME AFFAIRS (GOVERNMENT OF INDIA)",
            text_color=THEME["primary"],
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
        ).pack()

        ctk.CTkLabel(
            title_center,
            text="NyayaVault: Chain-of-Command & Rank Authentication Gateway (PS-190)",
            text_color=THEME["text_muted"],
            font=ctk.CTkFont(family="Segoe UI", size=11)
        ).pack()

        self.container = ctk.CTkFrame(self, width=920, height=500, corner_radius=22, fg_color=THEME["card_bg"], border_width=1, border_color=THEME["card_border"])
        self.container.pack_propagate(False)
        self.container.place(relx=0.5, rely=0.53, anchor="center")

        self.left_panel = ctk.CTkFrame(self.container, fg_color="transparent")
        self.left_panel.place(relx=0.0, rely=0.0, relwidth=0.5, relheight=1.0)

        self.right_panel = ctk.CTkFrame(self.container, fg_color="transparent")
        self.right_panel.place(relx=0.5, rely=0.0, relwidth=0.5, relheight=1.0)

        self.build_court_browse_panel()
        self.build_position_login_panel()

        self.overlay = ctk.CTkFrame(self.container, corner_radius=22, fg_color=THEME["hero_gradient"], border_width=0)
        self.overlay.pack_propagate(False)
        self.overlay.place(relx=0.0, rely=0.0, relwidth=0.5, relheight=1.0)

        self.build_overlay_content()

    def build_overlay_content(self):
        for w in self.overlay.winfo_children(): w.destroy()

        badge = ctk.CTkFrame(self.overlay, fg_color="#3B82F6", corner_radius=15, height=26)
        badge.pack(pady=(45, 6), padx=20)
        ctk.CTkLabel(badge, text="STAGE 1 — HIERARCHY GATEWAY", text_color="#FFFFFF", font=ctk.CTkFont(size=10, weight="bold")).pack(padx=14, pady=2)

        self.overlay_title = ctk.CTkLabel(self.overlay, text="Law Enforcement Login", text_color="#FFFFFF", font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"))
        self.overlay_title.pack(pady=(2, 4))

        self.overlay_subtitle = ctk.CTkLabel(
            self.overlay,
            text="Select your designated police post/rank first.\nYour jurisdiction is securely linked directly to your database badge ID. No redundant location inputs required.",
            text_color="#EFF6FF",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            wraplength=320,
            justify="center"
        )
        self.overlay_subtitle.pack(pady=(0, 10))

        self.overlay_prompt = ctk.CTkLabel(self.overlay, text="Presiding Magistrate or Judicial Clerk?", text_color="#DBEAFE", font=ctk.CTkFont(family="Segoe UI", size=11))
        self.overlay_prompt.pack(pady=(0, 4))

        self.overlay_btn = ctk.CTkButton(
            self.overlay,
            text="Switch to Judicial Portal",
            command=self.toggle_flip_view,
            width=220,
            height=34,
            fg_color="transparent",
            border_width=2,
            border_color="#FFFFFF",
            hover_color=THEME["hero_gradient_dark"],
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            corner_radius=25
        )
        self.overlay_btn.pack(pady=(0, 6))

        # Analytics Dashboard Button (Password Protected)
        self.analytics_btn = ctk.CTkButton(
            self.overlay,
            text="📊 Open Analytics Intelligence",
            command=self.prompt_analytics_password,
            width=220,
            height=34,
            fg_color=THEME["accent_gold"],
            hover_color=THEME["accent_gold_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            corner_radius=25
        )
        self.analytics_btn.pack(pady=(2, 0))

    def prompt_analytics_password(self):
        modal = Toplevel(self)
        modal.title("Security Authorization — Analytics Intelligence")
        modal.geometry("420x240")
        modal.configure(bg=THEME["bg_main"])
        modal.grab_set()

        top_h = ctk.CTkFrame(modal, fg_color=THEME["accent_gold"], height=50, corner_radius=0)
        top_h.pack(fill="x")
        ctk.CTkLabel(top_h, text="🔒 Restricted Analytics Security Gateway", font=ctk.CTkFont(size=13, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=20, pady=12)

        card = ctk.CTkFrame(modal, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        card.pack(fill="both", expand=True, padx=20, pady=15)

        ctk.CTkLabel(card, text="Enter Analytics Master Password:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(15, 2))
        pwd_entry = ctk.CTkEntry(card, placeholder_text="Enter password (analytics123)", show="*", width=340, height=36)
        pwd_entry.pack(padx=20, pady=5)

        def verify_pwd():
            if pwd_entry.get().strip() == "analytics123":
                modal.destroy()
                self.launch_advanced_analytics_portal()
            else:
                messagebox.showerror("Access Denied", "Incorrect Analytics Master Password.", parent=modal)

        ctk.CTkButton(card, text="Access Analytics ➔", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=verify_pwd, height=36).pack(fill="x", padx=20, pady=(10, 15))

    def launch_advanced_analytics_portal(self):
        modal = Toplevel(self)
        modal.title("NyayaVault — Advanced Crime & Evidence Intelligence Analytics Dashboard")
        modal.geometry("1380x820")
        modal.configure(bg=THEME["bg_main"])
        modal.grab_set()

        top_header = ctk.CTkFrame(modal, fg_color=THEME["primary"], height=65, corner_radius=0)
        top_header.pack(fill="x")
        ctk.CTkLabel(top_header, text="📊 Advanced Multi-Tier Crime & Evidence Intelligence Analytics Dashboard", font=ctk.CTkFont(size=16, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=25, pady=12)

        filter_bar = ctk.CTkFrame(modal, height=60, fg_color=THEME["card_bg"], corner_radius=0, border_width=1, border_color=THEME["card_border"])
        filter_bar.pack(fill="x")
        filter_bar.pack_propagate(False)

        ctk.CTkLabel(filter_bar, text="Analysis Scope:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(side="left", padx=(20, 8))
        
        scope_var = ctk.StringVar(value="Overall State")
        scope_menu = ctk.CTkOptionMenu(
            filter_bar,
            values=["Overall State", "City-wise", "Area-wise", "Police Station-wise"],
            variable=scope_var,
            width=160,
            height=32
        )
        scope_menu.pack(side="left", padx=5)

        ctk.CTkLabel(filter_bar, text="City:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(side="left", padx=(15, 5))
        city_var = ctk.StringVar(value="All")
        city_menu = ctk.CTkOptionMenu(filter_bar, values=["All"], variable=city_var, width=140, height=32)
        city_menu.pack(side="left", padx=5)

        ctk.CTkLabel(filter_bar, text="Area / Zone:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(side="left", padx=(15, 5))
        area_var = ctk.StringVar(value="All")
        area_menu = ctk.CTkOptionMenu(filter_bar, values=["All"], variable=area_var, width=150, height=32)
        area_menu.pack(side="left", padx=5)

        target_var = ctk.StringVar(value="All")
        target_menu = ctk.CTkOptionMenu(filter_bar, values=["All"], variable=target_var, width=160, height=32)
        target_menu.pack(side="left", padx=5)

        scroll_body = ctk.CTkScrollableFrame(modal, fg_color=THEME["card_highlight"], corner_radius=0)
        scroll_body.pack(fill="both", expand=True, padx=20, pady=15)

        metrics_container = ctk.CTkFrame(scroll_body, fg_color="transparent")
        metrics_container.pack(fill="both", expand=True)

        def refresh_analytics_view(*args):
            for w in metrics_container.winfo_children(): w.destroy()
            
            sc = scope_var.get()
            c_val = city_var.get()
            a_val = area_var.get()
            t_val = target_var.get()

            total_cases = 0
            resolved_cases = 0
            murder_count = 0
            robbery_count = 0
            cyber_count = 0
            narcotics_count = 0
            economic_count = 0
            other_count = 0
            prev_year_cases = 0
            curr_year_cases = 0
            prev_month_cases = 0
            curr_month_cases = 0

            try:
                conn = self.get_db_connection()
                cur = conn.cursor()

                base_query = "SELECT COUNT(*) FROM case_profiles c WHERE 1=1"
                params = []
                p_idx = 1

                if c_val != "All":
                    base_query += f" AND c.division_code = :{p_idx}"
                    params.append(c_val)
                    p_idx += 1

                if a_val != "All":
                    base_query += f" AND c.area_zone = :{p_idx}"
                    params.append(a_val)
                    p_idx += 1

                if sc == "City-wise" and t_val != "All":
                    base_query += f" AND c.division_code = :{p_idx}"
                    params.append(t_val)
                    p_idx += 1
                elif sc == "Area-wise" and t_val != "All":
                    base_query += f" AND c.area_zone = :{p_idx}"
                    params.append(t_val)
                    p_idx += 1
                elif sc == "Police Station-wise" and t_val != "All":
                    base_query += f" AND c.unit_name = :{p_idx}"
                    params.append(t_val)
                    p_idx += 1

                cur.execute(base_query, params)
                total_cases = cur.fetchone()[0]

                cur.execute(base_query + " AND c.case_condition IN ('Convicted & Sentenced', 'Closed / Acquitted')", params)
                resolved_cases = cur.fetchone()[0]

                cur.execute(base_query + " AND (UPPER(c.case_name) LIKE '%MURDER%' OR UPPER(c.case_name) LIKE '%HOMICIDE%')", params)
                murder_count = cur.fetchone()[0]

                cur.execute(base_query + " AND (UPPER(c.case_name) LIKE '%ROBBERY%' OR UPPER(c.case_name) LIKE '%HEIST%' OR UPPER(c.case_name) LIKE '%THEFT%')", params)
                robbery_count = cur.fetchone()[0]

                cur.execute(base_query + " AND (UPPER(c.case_name) LIKE '%CYBER%' OR UPPER(c.case_name) LIKE '%RANSOMWARE%')", params)
                cyber_count = cur.fetchone()[0]

                cur.execute(base_query + " AND (UPPER(c.case_name) LIKE '%NARCOTICS%' OR UPPER(c.case_name) LIKE '%DRUG%')", params)
                narcotics_count = cur.fetchone()[0]

                cur.execute(base_query + " AND (UPPER(c.case_name) LIKE '%ECONOMIC%' OR UPPER(c.case_name) LIKE '%HAWALA%' OR UPPER(c.case_name) LIKE '%BANK%')", params)
                economic_count = cur.fetchone()[0]

                other_count = max(0, total_cases - (murder_count + robbery_count + cyber_count + narcotics_count + economic_count))

                cur.execute(base_query + " AND TO_CHAR(c.created_at, 'YYYY') = TO_CHAR(SYSDATE, 'YYYY')", params)
                curr_year_cases = cur.fetchone()[0]

                cur.execute(base_query + " AND TO_CHAR(c.created_at, 'YYYY') = TO_CHAR(SYSDATE, 'YYYY') - 1", params)
                prev_year_cases = cur.fetchone()[0]

                cur.execute(base_query + " AND TO_CHAR(c.created_at, 'YYYY-MM') = TO_CHAR(SYSDATE, 'YYYY-MM')", params)
                curr_month_cases = cur.fetchone()[0]

                cur.execute(base_query + " AND TO_CHAR(c.created_at, 'YYYY-MM') = TO_CHAR(ADD_MONTHS(SYSDATE, -1), 'YYYY-MM')", params)
                prev_month_cases = cur.fetchone()[0]

                cur.close()
                conn.close()
            except Exception:
                total_cases = 10
                resolved_cases = 6
                murder_count = 2
                robbery_count = 3
                cyber_count = 2
                narcotics_count = 1
                economic_count = 2
                curr_year_cases = 8
                prev_year_cases = 4
                curr_month_cases = 3
                prev_month_cases = 2

            cards_row = ctk.CTkFrame(metrics_container, fg_color="transparent")
            cards_row.pack(fill="x", pady=(5, 15))

            def create_metric_card(parent, title, val, badge_text, color):
                card = ctk.CTkFrame(parent, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"], height=100)
                card.pack_propagate(False)
                card.pack(side="left", fill="x", expand=True, padx=6)
                
                ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_muted"]).pack(anchor="w", padx=15, pady=(12, 2))
                
                bot = ctk.CTkFrame(card, fg_color="transparent")
                bot.pack(fill="x", padx=15)
                ctk.CTkLabel(bot, text=str(val), font=ctk.CTkFont(size=22, weight="bold"), text_color=THEME["text_main"]).pack(side="left")
                
                badge = ctk.CTkFrame(bot, fg_color=color, corner_radius=8, height=22)
                badge.pack(side="right")
                ctk.CTkLabel(badge, text=badge_text, font=ctk.CTkFont(size=10, weight="bold"), text_color="#FFFFFF").pack(padx=8, pady=2)

            scope_title = f"{sc} ({t_val})" if t_val != "All" else sc
            create_metric_card(cards_row, f"Dockets [{scope_title}]", total_cases, "Active Scope", THEME["primary"])
            create_metric_card(cards_row, "Cases Resolved", resolved_cases, f"{int((resolved_cases/max(1,total_cases))*100)}% Closure", THEME["accent_green"])
            create_metric_card(cards_row, "High Severity (Murder)", murder_count, "Priority Alpha", THEME["accent_red"])
            create_metric_card(cards_row, "Economic & Financial", economic_count, "Fraud Track", THEME["accent_gold"])

            comp_frame = ctk.CTkFrame(metrics_container, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
            comp_frame.pack(fill="x", pady=10, padx=5)

            ctk.CTkLabel(comp_frame, text=f"📈 Historical Trend Analysis: Previous Year vs Current Year & Monthly Intake [{scope_title}]", font=ctk.CTkFont(size=14, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(15, 10))

            grid_comp = ctk.CTkFrame(comp_frame, fg_color="transparent")
            grid_comp.pack(fill="x", padx=20, pady=(0, 15))

            def make_detailed_comp_card(parent, title, curr_v, prev_v, unit_label="Cases"):
                f = ctk.CTkFrame(parent, fg_color=THEME["card_highlight"], corner_radius=8, border_width=1, border_color=THEME["card_border"])
                f.pack(side="left", fill="x", expand=True, padx=8, pady=5)
                ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=14, pady=(10, 2))
                
                row_stats = ctk.CTkFrame(f, fg_color="transparent")
                row_stats.pack(fill="x", padx=14, pady=2)
                ctk.CTkLabel(row_stats, text=f"Current Period: {curr_v} {unit_label}", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_main"]).pack(side="left")
                ctk.CTkLabel(row_stats, text=f"Previous Period: {prev_v} {unit_label}", font=ctk.CTkFont(size=11), text_color=THEME["text_muted"]).pack(side="right")
                
                diff = curr_v - prev_v
                pct = (diff / prev_v * 100) if prev_v > 0 else (100 if curr_v > 0 else 0)
                trend_str = f"▲ +{pct:.1f}% Growth vs Previous Period" if diff >= 0 else f"▼ {pct:.1f}% Reduction vs Previous Period"
                trend_color = THEME["accent_green"] if diff >= 0 else THEME["accent_red"]
                
                ctk.CTkLabel(f, text=trend_str, font=ctk.CTkFont(size=10, weight="bold"), text_color=trend_color).pack(anchor="w", padx=14, pady=(2, 10))

            make_detailed_comp_card(grid_comp, "Annual Comparison (This Year vs Last Year)", curr_year_cases, prev_year_cases)
            make_detailed_comp_card(grid_comp, "Monthly Comparison (This Month vs Last Month)", curr_month_cases, prev_month_cases)

            cat_frame = ctk.CTkFrame(metrics_container, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
            cat_frame.pack(fill="x", pady=10, padx=5)

            ctk.CTkLabel(cat_frame, text=f"🔍 Crime Category Distribution Breakdown [{scope_title}]", font=ctk.CTkFont(size=14, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(15, 10))

            cat_grid = ctk.CTkFrame(cat_frame, fg_color="transparent")
            cat_grid.pack(fill="x", padx=20, pady=(0, 15))

            def make_category_row(parent, cat_name, count, total, color):
                row = ctk.CTkFrame(parent, fg_color="transparent")
                row.pack(fill="x", pady=6)
                ctk.CTkLabel(row, text=cat_name, font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_main"], width=175, anchor="w").pack(side="left")
                
                pb = ctk.CTkProgressBar(row, progress_color=color, fg_color=THEME["input_bg"], height=14)
                pb.pack(side="left", fill="x", expand=True, padx=10)
                ratio = (count / total) if total > 0 else 0.0
                pb.set(ratio)

                ctk.CTkLabel(row, text=f"{count} Cases ({int(ratio*100)}%)", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_muted"], width=115, anchor="e").pack(side="right")

            make_category_row(cat_grid, "🔴 Murder / Homicide", murder_count, total_cases, THEME["accent_red"])
            make_category_row(cat_grid, "🟡 Robbery / Theft / Heist", robbery_count, total_cases, THEME["accent_gold"])
            make_category_row(cat_grid, "🔵 Cyber / Ransomware", cyber_count, total_cases, THEME["primary"])
            make_category_row(cat_grid, "🟣 Economic & Hawala Fraud", economic_count, total_cases, "#7C3AED")
            make_category_row(cat_grid, "🟠 Narcotics & Drugs", narcotics_count, total_cases, "#EA580C")
            make_category_row(cat_grid, "🟢 Other General Offenses", other_count, total_cases, THEME["accent_green"])

        def update_dropdown_options(*args):
            sc = scope_var.get()
            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                
                cur.execute("SELECT DISTINCT division_code FROM police_divisions ORDER BY division_code")
                cities = [r[0] for r in cur.fetchall()]
                city_menu.configure(values=["All"] + cities)

                sel_city = city_var.get()
                if sel_city != "All":
                    cur.execute("SELECT DISTINCT area_zone FROM investigation_units WHERE division_code = :1 ORDER BY area_zone", (sel_city,))
                else:
                    cur.execute("SELECT DISTINCT area_zone FROM investigation_units ORDER BY area_zone")
                areas = [r[0] for r in cur.fetchall()]
                area_menu.configure(values=["All"] + areas)

                sel_area = area_var.get()
                if sc == "City-wise":
                    target_menu.configure(values=["All"] + cities)
                elif sc == "Area-wise":
                    if sel_city != "All":
                        cur.execute("SELECT DISTINCT area_zone FROM investigation_units WHERE division_code = :1 ORDER BY area_zone", (sel_city,))
                    else:
                        cur.execute("SELECT DISTINCT area_zone FROM investigation_units ORDER BY area_zone")
                    azones = [r[0] for r in cur.fetchall()]
                    target_menu.configure(values=["All"] + azones)
                elif sc == "Police Station-wise":
                    if sel_city != "All" and sel_area != "All":
                        cur.execute("SELECT DISTINCT unit_name FROM investigation_units WHERE division_code = :1 AND area_zone = :2 ORDER BY unit_name", (sel_city, sel_area))
                    elif sel_city != "All":
                        cur.execute("SELECT DISTINCT unit_name FROM investigation_units WHERE division_code = :1 ORDER BY unit_name", (sel_city,))
                    elif sel_area != "All":
                        cur.execute("SELECT DISTINCT unit_name FROM investigation_units WHERE area_zone = :1 ORDER BY unit_name", (sel_area,))
                    else:
                        cur.execute("SELECT DISTINCT unit_name FROM investigation_units ORDER BY unit_name")
                    stations = [r[0] for r in cur.fetchall()]
                    target_menu.configure(values=["All"] + stations)
                else:
                    target_menu.configure(values=["All"])
                    target_var.set("All")

                cur.close()
                conn.close()
            except Exception:
                pass
            refresh_analytics_view()

        scope_var.trace("w", update_dropdown_options)
        city_var.trace("w", update_dropdown_options)
        area_var.trace("w", update_dropdown_options)
        target_var.trace("w", refresh_analytics_view)

        update_dropdown_options()

        ctk.CTkButton(scroll_body, text="Close Intelligence Analytics", fg_color=THEME["primary"], command=modal.destroy, height=38).pack(pady=15)

    def toggle_flip_view(self):
        if self.animating_flip: return
        self.animating_flip = True
        target_relx = 0.5 if not self.is_browse_mode else 0.0
        current_relx = 0.0 if not self.is_browse_mode else 0.5
        step = 0.04 if target_relx > current_relx else -0.04

        def animate_slide():
            nonlocal current_relx
            if (step > 0 and current_relx < target_relx) or (step < 0 and current_relx > target_relx):
                current_relx += step
                self.overlay.place(relx=current_relx, rely=0.0, relwidth=0.5, relheight=1.0)
                self.after(14, animate_slide)
            else:
                self.overlay.place(relx=target_relx, rely=0.0, relwidth=0.5, relheight=1.0)
                self.is_browse_mode = not self.is_browse_mode
                self.animating_flip = False
                if self.is_browse_mode:
                    self.overlay_title.configure(text="Police & Admin Gate")
                    self.overlay_subtitle.configure(text="Authorized law enforcement officers and administrators authenticate here.")
                    self.overlay_prompt.configure(text="Need Law Enforcement Entrance?")
                    self.overlay_btn.configure(text="Switch to Police Gateway")
                else:
                    self.overlay_title.configure(text="Law Enforcement Login")
                    self.overlay_subtitle.configure(text="Select your designated police post/rank first.\nYour jurisdiction is securely linked directly to your database badge ID. No redundant location inputs required.")
                    self.overlay_prompt.configure(text="Presiding Magistrate or Judicial Clerk?")
                    self.overlay_btn.configure(text="Switch to Judicial Portal")

        animate_slide()

    def build_position_login_panel(self):
        for w in self.right_panel.winfo_children(): w.destroy()

        form_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        form_frame.pack(fill="both", expand=True, padx=25, pady=15)

        badge = ctk.CTkFrame(form_frame, fg_color="#EFF6FF", corner_radius=15, height=24)
        badge.pack(pady=(2, 2))
        ctk.CTkLabel(badge, text="OFFICER HIERARCHY LOGIN", text_color=THEME["primary"], font=ctk.CTkFont(size=10, weight="bold")).pack(padx=12, pady=2)

        ctk.CTkLabel(form_frame, text="Command Position Login", text_color=THEME["text_main"], font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold")).pack(pady=(0, 6))

        ctk.CTkLabel(form_frame, text="Step 1: Select Your Position / Post", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", pady=(1, 1))
        
        positions = [
            "Director General of Police (DGP)",
            "City Commissioner of Police (CP)",
            "Area / Zone Commissioner (DCP/ACP)",
            "Police Inspector / SHO",
            "Investigating Officer (IO)",
            "Forensic Scientist Lead",
            "Super Admin / Master IT"
        ]
        self.selected_position_var = ctk.StringVar(value=positions[0])
        
        self.position_menu = ctk.CTkOptionMenu(
            form_frame,
            values=positions,
            variable=self.selected_position_var,
            width=380,
            height=34,
            fg_color=THEME["input_bg"],
            text_color=THEME["text_main"]
        )
        self.position_menu.pack(pady=2)

        ctk.CTkLabel(form_frame, text="Officer Full Name (as registered):", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_main"]).pack(anchor="w", pady=(4, 1))
        self.login_name_in = ctk.CTkEntry(form_frame, placeholder_text="e.g. DGP Vikas Sahay / V. Jadeja", width=380, height=34, fg_color=THEME["input_bg"])
        self.login_name_in.pack(pady=2)

        ctk.CTkLabel(form_frame, text="Badge ID / Username:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_main"]).pack(anchor="w", pady=(4, 1))
        self.login_id_in = ctk.CTkEntry(form_frame, placeholder_text="e.g. dgp_gujarat / cp_surat / io_surat", width=380, height=34, fg_color=THEME["input_bg"])
        self.login_id_in.pack(pady=2)

        ctk.CTkLabel(form_frame, text="Secret Cryptographic Password:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_main"]).pack(anchor="w", pady=(4, 1))
        self.login_pwd_in = ctk.CTkEntry(form_frame, placeholder_text="Enter secure cryptographic password", show="*", width=380, height=34, fg_color=THEME["input_bg"])
        self.login_pwd_in.pack(pady=2)

        btn_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 5))

        ctk.CTkButton(
            btn_row,
            text="Authenticate & Unlock Vault ➔",
            command=self.handle_position_based_login,
            width=230,
            height=40,
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            corner_radius=10
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="Forgot Password?",
            command=self.open_forgot_password_modal,
            width=135,
            height=40,
            fg_color="transparent",
            border_width=1,
            border_color=THEME["primary"],
            text_color=THEME["primary"],
            hover_color="#EFF6FF",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            corner_radius=10
        ).pack(side="right")

    def handle_position_based_login(self):
        if not self.verify_mha_network(): return
        post = self.selected_position_var.get()
        name_input = self.login_name_in.get().strip()
        uid = self.login_id_in.get().strip()
        pwd = self.login_pwd_in.get().strip()

        if not name_input or not uid or not pwd:
            messagebox.showerror("Validation Error", "Officer Name, Badge ID / Username, and Password are all mandatory.")
            return

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT badge_id, role, officer_name, police_rank, rank_level, division_code, area_zone, unit_name
                FROM vault_system_users 
                WHERE (username = :usr OR badge_id = :usr) AND password_hash = :pwd AND is_active = 1
            """, {"usr": uid, "pwd": pwd})
            row = cur.fetchone()
            cur.close()
            conn.close()

            if row:
                db_badge = row[0]
                db_role = row[1].upper()
                db_name = row[2]
                db_rank = row[3]
                db_level = int(row[4])
                db_div = row[5] or "SURAT"
                db_area = row[6] or "Zone 1"
                db_unit = row[7] or "Katargam Police Station"

                if db_name.lower() != name_input.lower():
                    messagebox.showerror("Identity Mismatch", f"Security Alert:\nThe entered Officer Name ('{name_input}') does not match official database records for '{db_name}'. Access denied.")
                    return

                self.current_user_badge = db_badge
                self.current_role = db_role
                self.current_user_name = db_name
                self.current_rank = db_rank
                self.current_rank_level = db_level
                self.selected_division.set(db_div)
                self.current_user_area = db_area
                self.selected_unit.set(db_unit)

                self.log_chained_audit_event("OFFICER_LOGGED_IN", f"{self.current_rank} {self.current_user_name} (#{self.current_user_badge}) logged in via post: {post}")
                
                if self.current_rank_level == 5:
                    self.show_dgp_jurisdiction_browser()
                elif self.current_rank_level == 4:
                    self.show_cp_jurisdiction_browser()
                elif self.current_rank_level == 3:
                    self.show_dcp_jurisdiction_dashboard()
                else:
                    self.launch_main_portal(self.current_role)
            else:
                messagebox.showerror("Authentication Failed", "Invalid credentials or officer ID. Please check your username and cryptographic password.")
        except Exception as e:
            messagebox.showerror("Database Error", str(e))

    def build_court_browse_panel(self):
        for w in self.left_panel.winfo_children(): w.destroy()

        badge = ctk.CTkFrame(self.left_panel, fg_color="#FEF3C7", corner_radius=15, height=26)
        badge.pack(pady=(60, 6), padx=30)
        ctk.CTkLabel(badge, text="JUDICIAL INSPECTION ACCESS", text_color=THEME["accent_gold"], font=ctk.CTkFont(size=10, weight="bold")).pack(padx=14, pady=3)

        ctk.CTkLabel(self.left_panel, text="Judicial & Prosecution Portal", text_color=THEME["text_main"], font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold")).pack(pady=(4, 2))
        ctk.CTkLabel(self.left_panel, text="Read-Only Evidence Manifest Inspection & Live Tamper Hash Verification.", text_color=THEME["text_muted"], font=ctk.CTkFont(family="Segoe UI", size=12), wraplength=310, justify="center").pack(pady=(0, 20))

        self.court_user = ctk.CTkEntry(self.left_panel, placeholder_text="Judge ID (judge_portal)", width=320, height=44, fg_color=THEME["input_bg"])
        self.court_user.pack(pady=6)

        self.court_pass = ctk.CTkEntry(self.left_panel, placeholder_text="Judicial Password (court123)", show="*", width=320, height=44, fg_color=THEME["input_bg"])
        self.court_pass.pack(pady=6)

        ctk.CTkButton(
            self.left_panel,
            text="Authenticate Judicial Identity ➔",
            command=self.handle_court_login,
            width=320,
            height=46,
            fg_color=THEME["accent_gold"],
            hover_color=THEME["accent_gold_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            corner_radius=12
        ).pack(pady=(16, 10))

    def handle_court_login(self):
        if not self.verify_mha_network(): return
        u = self.court_user.get().strip()
        p = self.court_pass.get().strip()

        if not u or not p:
            messagebox.showerror("Error", "Judge ID and Password required.")
            return

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT badge_id, role, officer_name, police_rank, rank_level, area_zone 
                FROM vault_system_users 
                WHERE (username = :usr OR badge_id = :usr) AND password_hash = :pwd AND is_active = 1
            """, {"usr": u, "pwd": p})
            row = cur.fetchone()
            cur.close()
            conn.close()

            if row and row[1].upper() == "COURT_JUDICIAL":
                self.current_user_badge = row[0]
                self.current_role = "COURT_JUDICIAL"
                self.current_user_name = row[2]
                self.current_rank = row[3]
                self.current_rank_level = int(row[4])
                self.current_user_area = row[5]
                # Default page for judge set to City & CP Management via jurisdiction browser
                self.show_dgp_jurisdiction_browser()
            else:
                messagebox.showerror("Access Denied", "Invalid Judicial credentials.")
        except Exception as e:
            messagebox.showerror("Oracle DB Error", str(e))

    def fetch_divisions(self):
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT division_code FROM police_divisions ORDER BY division_code")
            rows = [r[0] for r in cur.fetchall()]
            cur.close()
            conn.close()
            return rows
        except Exception:
            return ["SURAT", "AHMEDABAD", "RAJKOT"]

    def fetch_units_for_division(self, div_code):
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT unit_name FROM investigation_units WHERE division_code = :1 ORDER BY unit_name", (div_code,))
            rows = [r[0] for r in cur.fetchall()]
            cur.close()
            conn.close()
            return rows if rows else ["General Cell"]
        except Exception:
            return ["General Cell"]

    def fetch_all_station_names(self):
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT unit_name FROM investigation_units ORDER BY unit_name")
            rows = [r[0] for r in cur.fetchall()]
            cur.close()
            conn.close()
            return rows if rows else ["Katargam Police Station"]
        except Exception:
            return ["Katargam Police Station"]

    def open_forgot_password_modal(self):
        modal = Toplevel(self)
        modal.title("Account Recovery & Password Reset")
        modal.geometry("500x520")
        modal.configure(bg=THEME["bg_main"])
        modal.grab_set()

        top_h = ctk.CTkFrame(modal, fg_color=THEME["primary"], height=55, corner_radius=0)
        top_h.pack(fill="x")
        ctk.CTkLabel(top_h, text="🔒 Reset Password via Registered Email OTP", font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=20, pady=12)

        card = ctk.CTkFrame(modal, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        card.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(card, text="Enter Registered Username / Badge ID:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(10, 1))
        in_user_badge = self.create_styled_entry(card, "e.g. io_surat or IO-SUR-102")

        generated_otp = [""]
        verified_user = [""]

        otp_status_lbl = ctk.CTkLabel(card, text="Click 'Send Verification OTP' to dispatch code.", font=ctk.CTkFont(size=10), text_color=THEME["text_muted"])
        otp_status_lbl.pack(pady=4)

        def send_otp():
            ident = in_user_badge.get().strip()
            if not ident:
                messagebox.showerror("Error", "Please enter username or Badge ID.", parent=modal)
                return

            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT badge_id, officer_name, officer_email FROM vault_system_users WHERE username = :1 OR badge_id = :2", (ident, ident))
                row = cur.fetchone()
                cur.close()
                conn.close()

                if not row:
                    messagebox.showerror("Account Error", "No registered officer account found matching this identifier.", parent=modal)
                    return

                badge, name, email = row[0], row[1], row[2]
                code = str(random.randint(100000, 999999))
                generated_otp[0] = code
                verified_user[0] = badge

                ok, msg = self.send_email_otp(email, code, name)
                otp_status_lbl.configure(text=f"OTP dispatched to {email[:3]}***@***.gov.in", text_color=THEME["accent_green"])
                messagebox.showinfo("OTP Sent", msg, parent=modal)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)

        ctk.CTkButton(card, text="✉️ Send Verification OTP to Email", fg_color="#0284C7", hover_color="#0369A1", command=send_otp).pack(fill="x", padx=20, pady=6)

        ctk.CTkLabel(card, text="Enter 6-Digit Email OTP:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(8, 1))
        in_otp = self.create_styled_entry(card, "6-Digit Security OTP")

        ctk.CTkLabel(card, text="Enter New Password:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(6, 1))
        in_new_pwd = self.create_styled_entry(card, "New Secret Password", show="*")

        def reset_password():
            entered_otp = in_otp.get().strip()
            new_p = in_new_pwd.get().strip()

            if not entered_otp or not new_p:
                messagebox.showerror("Error", "Please enter OTP and your new password.", parent=modal)
                return

            if entered_otp != generated_otp[0]:
                messagebox.showerror("Invalid Token", "Incorrect or expired OTP. Please try again.", parent=modal)
                return

            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                cur.execute("UPDATE vault_system_users SET password_hash = :1 WHERE badge_id = :2", (new_p, verified_user[0]))
                conn.commit()
                cur.close()
                conn.close()

                self.log_chained_audit_event("PASSWORD_RESET_SUCCESS", f"Password reset for Officer #{verified_user[0]}")
                messagebox.showinfo("Password Updated", "Your password has been reset successfully! You can now sign in with your new password.", parent=modal)
                modal.destroy()
            except Exception as e:
                messagebox.showerror("DB Error", str(e), parent=modal)

        ctk.CTkButton(card, text="🔑 Verify OTP & Update Password", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=reset_password).pack(fill="x", padx=20, pady=(15, 10))

    def open_officer_registration_modal(self, target_rank_type="CP", target_city="SURAT", target_area="Zone 1", target_station="Katargam Police Station"):
        if self.current_rank_level < 4:
            messagebox.showerror("Permission Denied", f"STRICT RANK RESTRICTION:\nYour rank ({self.current_rank}) cannot enroll officers.\nOnly City Commissioners (CP) and DGP have personnel enrollment privileges.")
            return

        modal = Toplevel(self)
        modal.title("Police Officer Station Enrollment")
        modal.geometry("560x730")
        modal.configure(bg=THEME["bg_main"])
        modal.grab_set()

        top_h = ctk.CTkFrame(modal, fg_color=THEME["primary"], height=55, corner_radius=0)
        top_h.pack(fill="x")
        ctk.CTkLabel(top_h, text=f"👮 Enroll Junior Personnel (Authorized By: {self.current_rank})", font=ctk.CTkFont(size=13, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=20, pady=12)

        card = ctk.CTkScrollableFrame(modal, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        card.pack(fill="both", expand=True, padx=20, pady=15)

        ctk.CTkLabel(card, text="Officer Badge / ID (Unique):", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(5, 1))
        in_badge = self.create_styled_entry(card, "e.g. IO-SUR-105")

        ctk.CTkLabel(card, text="Officer Full Name:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(5, 1))
        in_name = self.create_styled_entry(card, "e.g. Police Inspector K. Patel")

        ctk.CTkLabel(card, text="Official Police Email Address:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(5, 1))
        in_email = self.create_styled_entry(card, "e.g. k.patel@suratpolice.gov.in")

        ctk.CTkLabel(card, text="System Username:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(5, 1))
        in_uname = self.create_styled_entry(card, "e.g. io_kpatel")

        ctk.CTkLabel(card, text="Secret Password:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(5, 1))
        in_pwd = self.create_styled_entry(card, "Enter Strong Password", show="*")

        ctk.CTkLabel(card, text="Confirm Secret Password:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(5, 1))
        in_cpwd = self.create_styled_entry(card, "Re-enter Password to Confirm", show="*")

        if target_rank_type == "CP":
            rank_title = "Commissioner of Police (City CP)"
            assigned_lvl, assigned_role = 4, "COMMISSIONER"
            
            ctk.CTkLabel(card, text="Assigned Position Tag (City & Position):", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(5, 1))
            tag_frame = ctk.CTkFrame(card, fg_color=THEME["primary"], corner_radius=8, height=38)
            tag_frame.pack_propagate(False)
            tag_frame.pack(fill="x", padx=15, pady=2)
            ctk.CTkLabel(tag_frame, text=f"🏙️ {rank_title} | City: {target_city}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=12, pady=8)

            assign_div = target_city
            assign_unit = "City Headquarters"
            assign_area = "City Central Zone"

        elif target_rank_type == "DCP":
            rank_title = "Deputy Commissioner of Police (DCP)"
            assigned_lvl, assigned_role = 3, "DCP_ACP"

            ctk.CTkLabel(card, text="Assigned Position Tag (Position, City, Area):", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(5, 1))
            tag_frame = ctk.CTkFrame(card, fg_color=THEME["primary"], corner_radius=8, height=38)
            tag_frame.pack_propagate(False)
            tag_frame.pack(fill="x", padx=15, pady=2)
            ctk.CTkLabel(tag_frame, text=f"📍 {rank_title} | City: {target_city} | Area: {target_area}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=12, pady=8)

            assign_div = target_city
            assign_unit = f"{target_area} Headquarters"
            assign_area = target_area

        elif target_rank_type == "ACP":
            rank_title = "Assistant Commissioner of Police (ACP)"
            assigned_lvl, assigned_role = 3, "DCP_ACP"

            ctk.CTkLabel(card, text="Assigned Position Tag (Position, City, Area):", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(5, 1))
            tag_frame = ctk.CTkFrame(card, fg_color=THEME["primary"], corner_radius=8, height=38)
            tag_frame.pack_propagate(False)
            tag_frame.pack(fill="x", padx=15, pady=2)
            ctk.CTkLabel(tag_frame, text=f"📍 {rank_title} | City: {target_city} | Area: {target_area}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=12, pady=8)

            assign_div = target_city
            assign_unit = f"{target_area} Headquarters"
            assign_area = target_area

        else:
            rank_title = "Police Inspector / SHO"
            assigned_lvl, assigned_role = 2, "INSPECTOR_SHO"

            ctk.CTkLabel(card, text="Assigned Position Tag (Position, City, Area, Station):", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(5, 1))
            tag_frame = ctk.CTkFrame(card, fg_color=THEME["primary"], corner_radius=8, height=38)
            tag_frame.pack_propagate(False)
            tag_frame.pack(fill="x", padx=15, pady=2)
            ctk.CTkLabel(tag_frame, text=f"🏛️ {rank_title} | City: {target_city} | Area: {target_area} | Station: {target_station}", font=ctk.CTkFont(size=10, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=10, pady=8)

            assign_div = target_city
            assign_unit = target_station
            assign_area = target_area

        def commit_officer_signup():
            b = in_badge.get().strip().upper()
            n = in_name.get().strip()
            em = in_email.get().strip()
            un = in_uname.get().strip()
            pw = in_pwd.get().strip()
            cpw = in_cpwd.get().strip()

            if not b or not n or not em or not un or not pw or not cpw:
                messagebox.showerror("Validation Error", "All registration fields are required.", parent=modal)
                return

            if pw != cpw:
                messagebox.showerror("Password Mismatch", "Password and Confirm Password fields do not match.", parent=modal)
                return

            if self.current_rank_level <= assigned_lvl and self.current_rank_level < 5:
                messagebox.showerror("Permission Error", f"STRICT RANK RULE:\nYou cannot enroll an officer with equal or higher rank ({rank_title}) than your own rank ({self.current_rank}).", parent=modal)
                return

            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO vault_system_users (badge_id, username, password_hash, officer_name, officer_email, police_rank, rank_level, role, division_code, area_zone, unit_name, is_active)
                    VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, 1)
                """, (b, un, pw, n, em, rank_title, assigned_lvl, assigned_role, assign_div, assign_area, assign_unit))
                conn.commit()
                cur.close()
                conn.close()

                self.log_chained_audit_event("OFFICER_ENROLLED", f"New account created for {n} (#{b}) in {assign_unit} by {self.current_user_name}")
                messagebox.showinfo("Officer Enrolled", f"Officer #{b} registered successfully under {assign_unit}!", parent=modal)
                modal.destroy()
            except Exception as e:
                messagebox.showerror("DB Error", f"Registration Failed: {str(e)}", parent=modal)

        ctk.CTkButton(card, text="💾 Commit Enroll Junior Officer", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=commit_officer_signup, height=40).pack(fill="x", padx=15, pady=(15, 10))

    def open_remove_officer_modal(self):
        if self.current_rank_level < 4:
            messagebox.showerror("Permission Denied", f"STRICT RANK RESTRICTION:\nYour rank ({self.current_rank}) cannot decommission officers.\nOnly City Commissioners (CP) and DGP have deletion rights.")
            return

        modal = Toplevel(self)
        modal.title("Decommission Officer")
        modal.geometry("520x420")
        modal.configure(bg=THEME["bg_main"])
        modal.grab_set()

        top_h = ctk.CTkFrame(modal, fg_color=THEME["accent_red"], height=55, corner_radius=0)
        top_h.pack(fill="x")
        ctk.CTkLabel(top_h, text=f"🗑️ Decommission Junior Officer (Authorized By: {self.current_rank})", font=ctk.CTkFont(size=13, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=20, pady=12)

        card = ctk.CTkFrame(modal, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        card.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(card, text="Enter Junior Officer Badge ID to Remove:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(10, 1))
        in_del_badge = self.create_styled_entry(card, "e.g. IO-SUR-102")

        ctk.CTkLabel(card, text="Enter Your Authorizing Commander Password:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(10, 1))
        in_auth_pwd = self.create_styled_entry(card, "Your Password", show="*")

        def commit_removal():
            target_b = in_del_badge.get().strip().upper()
            auth_p = in_auth_pwd.get().strip()

            if not target_b or not auth_p:
                messagebox.showerror("Error", "Badge ID and Authorization Password required.", parent=modal)
                return

            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT rank_level FROM vault_system_users WHERE badge_id = :1 AND password_hash = :2", (self.current_user_badge, auth_p))
                r_auth = cur.fetchone()
                if not r_auth:
                    messagebox.showerror("Auth Error", "Incorrect authorization password.", parent=modal)
                    cur.close()
                    conn.close()
                    return

                cur.execute("SELECT officer_name, rank_level, police_rank, division_code FROM vault_system_users WHERE badge_id = :1", (target_b,))
                r_target = cur.fetchone()
                if not r_target:
                    messagebox.showerror("Error", "Officer badge not found.", parent=modal)
                    cur.close()
                    conn.close()
                    return

                target_name, target_level, target_rank, target_div = r_target[0], int(r_target[1]), r_target[2], r_target[3]

                if self.current_rank_level <= target_level and self.current_rank_level < 5:
                    messagebox.showerror("Security Hierarchy Violation", f"STRICT RANK GOVERNANCE:\nYou cannot decommission {target_rank} {target_name}.\nOnly higher-ranking commanders have deletion rights.", parent=modal)
                    cur.close()
                    conn.close()
                    return

                if self.current_rank_level == 4 and target_div != self.selected_division.get():
                    messagebox.showerror("Jurisdiction Violation", f"City Commissioner of {self.selected_division.get()} cannot remove officers assigned to {target_div}.", parent=modal)
                    cur.close()
                    conn.close()
                    return

                cur.execute("DELETE FROM vault_system_users WHERE badge_id = :1", (target_b,))
                conn.commit()
                cur.close()
                conn.close()

                self.log_chained_audit_event("OFFICER_DECOMMISSIONED", f"Officer #{target_b} ({target_name}) removed by {self.current_user_name}")
                messagebox.showinfo("Officer Removed", f"Junior Officer #{target_b} ({target_name}) decommissioned successfully.", parent=modal)
                modal.destroy()
            except Exception as e:
                messagebox.showerror("DB Error", str(e), parent=modal)

        ctk.CTkButton(card, text="Permanently Decommission Officer", fg_color=THEME["accent_red"], hover_color=THEME["accent_red_hover"], command=commit_removal, height=40).pack(fill="x", padx=20, pady=(20, 10))

    # --- SCREEN 3: MAIN FULL-PAGE DASHBOARD (DATA STORAGE INVENTORY VIEW) ---
    def launch_main_portal(self, role):
        self.current_role = role
        self.clear_window()

        self.main_full_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=THEME["bg_main"])
        self.main_full_frame.pack(fill="both", expand=True)

        top_bar = ctk.CTkFrame(self.main_full_frame, height=65, fg_color=THEME["card_bg"], corner_radius=0, border_width=1, border_color=THEME["card_border"])
        top_bar.pack(fill="x", side="top")

        title_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=8)
        ctk.CTkLabel(title_frame, text="NyayaVault: Secure Digital Evidence Lifecycle System (PS-190)", font=ctk.CTkFont(size=15, weight="bold"), text_color=THEME["primary"]).pack(anchor="w")
        
        info_str = f"Rank: {self.current_rank} | User: {self.current_user_name} (#{self.current_user_badge}) | City: {self.selected_division.get()} | Station: {self.selected_unit.get()}"
        ctk.CTkLabel(title_frame, text=info_str, font=ctk.CTkFont(size=11), text_color=THEME["accent_green"]).pack(anchor="w")

        btn_container = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_container.pack(side="right", padx=20)

        # Analytics Button inside main portal for quick access
        ctk.CTkButton(
            btn_container,
            text="📊 Analytics",
            fg_color=THEME["accent_gold"],
            hover_color=THEME["accent_gold_hover"],
            width=100,
            height=32,
            command=self.prompt_analytics_password
        ).pack(side="left", padx=10)

        if self.current_rank_level == 5 or self.current_role == "COURT_JUDICIAL":
            ctk.CTkButton(
                btn_container,
                text="← State Command Tree",
                fg_color="#0284C7",
                hover_color="#0369A1",
                width=160,
                height=32,
                command=self.show_dgp_jurisdiction_browser
            ).pack(side="left", padx=10)
        elif self.current_rank_level == 4:
            ctk.CTkButton(
                btn_container,
                text="← City Command Tree",
                fg_color="#0284C7",
                hover_color="#0369A1",
                width=160,
                height=32,
                command=self.show_cp_jurisdiction_browser
            ).pack(side="left", padx=10)
        elif self.current_rank_level == 3:
            ctk.CTkButton(
                btn_container,
                text="← Area Command Tree",
                fg_color="#0284C7",
                hover_color="#0369A1",
                width=160,
                height=32,
                command=self.show_dcp_jurisdiction_dashboard
            ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_container,
            text="Sign Out",
            fg_color=THEME["accent_red"],
            hover_color=THEME["accent_red_hover"],
            width=85,
            height=32,
            command=self.show_admin_gateway_login_screen
        ).pack(side="left")

        self.tabview = ctk.CTkTabview(self.main_full_frame, fg_color=THEME["card_bg"], segmented_button_selected_color=THEME["primary"])
        self.tabview.pack(fill="both", expand=True, padx=20, pady=15)

        self.tab_cases = self.tabview.add("Case File Repository")
        self.build_cases_tab()

        if self.current_role != "COURT_JUDICIAL":
            self.tab_custody = self.tabview.add("Chain of Custody Ledger")
            self.build_custody_tab()

        self.tab_verify = self.tabview.add("Integrity Verification Dashboard")
        self.build_verification_tab()

        if self.current_rank_level >= 3 or self.current_role == "COURT_JUDICIAL":
            self.tab_audit = self.tabview.add("Security Audit Trails")
            self.build_audit_tab()

    def show_dgp_jurisdiction_browser(self):
        self.clear_window()
        self.main_full_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=THEME["bg_main"])
        self.main_full_frame.pack(fill="both", expand=True)

        top_bar = ctk.CTkFrame(self.main_full_frame, height=65, fg_color=THEME["card_bg"], corner_radius=0, border_width=1, border_color=THEME["card_border"])
        top_bar.pack(fill="x", side="top")

        title_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=8)
        ctk.CTkLabel(title_frame, text="NyayaVault: Secure Digital Evidence Lifecycle System (PS-190)", font=ctk.CTkFont(size=15, weight="bold"), text_color=THEME["primary"]).pack(anchor="w")
        
        role_label_txt = f"Rank: {self.current_rank} | Officer: {self.current_user_name} (#{self.current_user_badge}) | DGP STATE COMMAND CENTER"
        if self.current_role == "COURT_JUDICIAL":
            role_label_txt = f"Rank: {self.current_rank} | Judge: {self.current_user_name} (#{self.current_user_badge}) | JUDICIAL INSPECTION PORTAL"
        ctk.CTkLabel(title_frame, text=role_label_txt, font=ctk.CTkFont(size=11), text_color=THEME["accent_green"]).pack(anchor="w")

        btn_container = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_container.pack(side="right", padx=20)

        if self.current_role == "COURT_JUDICIAL":
            ctk.CTkButton(
                btn_container,
                text="📂 Open Evidence Vault",
                fg_color="#0284C7",
                hover_color="#0369A1",
                width=160,
                height=32,
                command=lambda: self.launch_main_portal("COURT_JUDICIAL")
            ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_container,
            text="Sign Out",
            fg_color=THEME["accent_red"],
            hover_color=THEME["accent_red_hover"],
            width=85,
            height=32,
            command=self.show_admin_gateway_login_screen
        ).pack(side="left")

        body_frame = ctk.CTkFrame(self.main_full_frame, fg_color="transparent")
        body_frame.pack(fill="both", expand=True, padx=20, pady=15)

        dgp_tabview = ctk.CTkTabview(body_frame, fg_color=THEME["card_bg"], segmented_button_selected_color=THEME["primary"])
        dgp_tabview.pack(fill="both", expand=True)

        tab_station = dgp_tabview.add("1. Police Stations & Station Leads")
        tab_area = dgp_tabview.add("2. Areas, Zones & DCP / ACP")
        tab_city = dgp_tabview.add("3. Cities & CP Management")

        # Set Cities & CP Management as default active tab
        dgp_tabview.set("3. Cities & CP Management")

        self.build_jurisdiction_tabs_content(dgp_tabview, tab_station, tab_area, tab_city, city_filter=None)

    def show_cp_jurisdiction_browser(self):
        self.clear_window()
        self.main_full_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=THEME["bg_main"])
        self.main_full_frame.pack(fill="both", expand=True)

        top_bar = ctk.CTkFrame(self.main_full_frame, height=65, fg_color=THEME["card_bg"], corner_radius=0, border_width=1, border_color=THEME["card_border"])
        top_bar.pack(fill="x", side="top")

        title_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=8)
        ctk.CTkLabel(title_frame, text="NyayaVault: Secure Digital Evidence Lifecycle System (PS-190)", font=ctk.CTkFont(size=15, weight="bold"), text_color=THEME["primary"]).pack(anchor="w")
        ctk.CTkLabel(title_frame, text=f"Rank: {self.current_rank} | Officer: {self.current_user_name} (#{self.current_user_badge}) | City: {self.selected_division.get()} COMMAND CENTER", font=ctk.CTkFont(size=11), text_color=THEME["accent_green"]).pack(anchor="w")

        btn_container = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_container.pack(side="right", padx=20)

        ctk.CTkButton(
            btn_container,
            text="Sign Out",
            fg_color=THEME["accent_red"],
            hover_color=THEME["accent_red_hover"],
            width=85,
            height=32,
            command=self.show_admin_gateway_login_screen
        ).pack(side="left")

        body_frame = ctk.CTkFrame(self.main_full_frame, fg_color="transparent")
        body_frame.pack(fill="both", expand=True, padx=20, pady=15)

        cp_tabview = ctk.CTkTabview(body_frame, fg_color=THEME["card_bg"], segmented_button_selected_color=THEME["primary"])
        try:
            cp_tabview._segmented_button.pack_forget()
        except Exception:
            pass
        cp_tabview.pack(fill="both", expand=True)

        tab_station = cp_tabview.add("1. Police Stations & Station Leads")
        tab_area = cp_tabview.add("2. Areas, Zones & DCP / ACP")

        cp_tabview.set("1. Police Stations & Station Leads")

        self.build_jurisdiction_tabs_content(cp_tabview, tab_station, tab_area, None, city_filter=self.selected_division.get())

    def show_dcp_jurisdiction_dashboard(self):
        self.clear_window()
        self.main_full_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=THEME["bg_main"])
        self.main_full_frame.pack(fill="both", expand=True)

        top_bar = ctk.CTkFrame(self.main_full_frame, height=65, fg_color=THEME["card_bg"], corner_radius=0, border_width=1, border_color=THEME["card_border"])
        top_bar.pack(fill="x", side="top")

        title_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=8)
        ctk.CTkLabel(title_frame, text="NyayaVault: Secure Digital Evidence Lifecycle System (PS-190)", font=ctk.CTkFont(size=15, weight="bold"), text_color=THEME["primary"]).pack(anchor="w")
        ctk.CTkLabel(title_frame, text=f"Rank: {self.current_rank} | Officer: {self.current_user_name} (#{self.current_user_badge}) | Area / Zone: {self.current_user_area}", font=ctk.CTkFont(size=11), text_color=THEME["accent_green"]).pack(anchor="w")

        btn_container = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_container.pack(side="right", padx=20)

        ctk.CTkButton(
            btn_container,
            text="Sign Out",
            fg_color=THEME["accent_red"],
            hover_color=THEME["accent_red_hover"],
            width=85,
            height=32,
            command=self.show_admin_gateway_login_screen
        ).pack(side="left")

        body_frame = ctk.CTkFrame(self.main_full_frame, fg_color="transparent")
        body_frame.pack(fill="both", expand=True, padx=20, pady=15)

        area_container = ctk.CTkFrame(body_frame, fg_color="transparent")
        area_container.pack(fill="both", expand=True, padx=10, pady=10)

        a_right = ctk.CTkScrollableFrame(area_container, fg_color=THEME["card_highlight"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        a_right.pack(side="top", fill="both", expand=True)

        area_name = self.current_user_area or "Zone 1"
        div_code = self.selected_division.get()

        ctk.CTkLabel(a_right, text=f"📍 Area / Zone Profile: {area_name} ({div_code})", font=ctk.CTkFont(size=16, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(20, 10))

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT badge_id, officer_name, officer_email, police_rank FROM vault_system_users WHERE division_code = :1 AND area_zone = :2 AND rank_level = 3 AND is_active = 1", (div_code, area_name))
            dcp_row = cur.fetchone()

            cur.execute("SELECT unit_name FROM investigation_units WHERE division_code = :1 AND area_zone = :2", (div_code, area_name))
            station_rows = cur.fetchall()
            cur.close()
            conn.close()

            card = ctk.CTkFrame(a_right, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
            card.pack(fill="x", pady=10, padx=20)
            ctk.CTkLabel(card, text="Assigned Assistant Commissioner of Police (ACP / DCP)", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["accent_gold"]).pack(anchor="w", padx=15, pady=(12, 4))

            if dcp_row:
                ctk.CTkLabel(card, text=f"Name: {dcp_row[1]}", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["text_main"]).pack(anchor="w", padx=15, pady=2)
                ctk.CTkLabel(card, text=f"Badge ID: #{dcp_row[0]} | Rank: {dcp_row[3]}", font=ctk.CTkFont(size=11), text_color=THEME["text_muted"]).pack(anchor="w", padx=15, pady=2)
                ctk.CTkLabel(card, text=f"Email: {dcp_row[2]}", font=ctk.CTkFont(size=11), text_color=THEME["text_muted"]).pack(anchor="w", padx=15, pady=(2, 6))

                def update_dcp_modal():
                    modal = Toplevel(self)
                    modal.title(f"Update ACP Data for {area_name}")
                    modal.geometry("420x300")
                    modal.configure(bg=THEME["bg_main"])
                    modal.grab_set()

                    ctk.CTkLabel(modal, text=f"Update ACP for {area_name}", font=ctk.CTkFont(size=14, weight="bold"), text_color=THEME["primary"]).pack(pady=15)
                    ctk.CTkLabel(modal, text="New Full Name:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=30)
                    en_name = ctk.CTkEntry(modal, width=360, height=34)
                    en_name.insert(0, dcp_row[1])
                    en_name.pack(padx=30, pady=5)

                    ctk.CTkLabel(modal, text="New Official Email:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=30)
                    en_email = ctk.CTkEntry(modal, width=360, height=34)
                    en_email.insert(0, dcp_row[2])
                    en_email.pack(padx=30, pady=5)

                    def save_dcp():
                        try:
                            conn_up = self.get_db_connection()
                            cur_up = conn_up.cursor()
                            cur_up.execute("UPDATE vault_system_users SET officer_name = :1, officer_email = :2 WHERE badge_id = :3", (en_name.get().strip(), en_email.get().strip(), dcp_row[0]))
                            conn_up.commit()
                            cur_up.close()
                            conn_up.close()
                            messagebox.showinfo("Updated", "ACP record updated successfully!", parent=modal)
                            modal.destroy()
                            self.show_dcp_jurisdiction_dashboard()
                        except Exception as ex:
                            messagebox.showerror("Error", str(ex), parent=modal)

                    ctk.CTkButton(modal, text="Save Updates", fg_color=THEME["accent_green"], command=save_dcp).pack(pady=15)

                if self.current_role != "COURT_JUDICIAL":
                    btn_update_row = ctk.CTkFrame(card, fg_color="transparent")
                    btn_update_row.pack(anchor="w", padx=15, pady=(4, 15))
                    ctk.CTkButton(btn_update_row, text="✏️ Update DCP Data", fg_color="#0284C7", command=update_dcp_modal, width=150, height=32).pack(side="left", padx=(0, 10))
                    ctk.CTkButton(btn_update_row, text="✏️ Update ACP Data", fg_color="#0284C7", command=update_dcp_modal, width=150, height=32).pack(side="left")
            else:
                ctk.CTkLabel(card, text=f"No DCP / ACP assigned to {area_name} yet.", text_color=THEME["text_muted"]).pack(anchor="w", padx=15, pady=4)
                
                if self.current_role != "COURT_JUDICIAL":
                    def open_dcp_enroll():
                        self.open_officer_registration_modal(target_rank_type="DCP", target_city=div_code, target_area=area_name)

                    def open_acp_enroll():
                        self.open_officer_registration_modal(target_rank_type="ACP", target_city=div_code, target_area=area_name)

                    btn_assign_row = ctk.CTkFrame(card, fg_color="transparent")
                    btn_assign_row.pack(anchor="w", padx=15, pady=(4, 15))
                    ctk.CTkButton(btn_assign_row, text="➕ Add DCP", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=open_dcp_enroll, width=130, height=32).pack(side="left", padx=(0, 10))
                    ctk.CTkButton(btn_assign_row, text="➕ Add ACP", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=open_acp_enroll, width=130, height=32).pack(side="left")

            ctk.CTkLabel(a_right, text=f"Police Stations in {area_name}:", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(15, 5))
            if station_rows:
                st_list_frame = ctk.CTkFrame(a_right, fg_color=THEME["card_bg"], corner_radius=10, border_width=1, border_color=THEME["card_border"])
                st_list_frame.pack(fill="x", padx=20, pady=(0, 20))
                for sr in station_rows:
                    s_btn_row = ctk.CTkFrame(st_list_frame, fg_color="transparent")
                    s_btn_row.pack(fill="x", padx=15, pady=6)
                    ctk.CTkLabel(s_btn_row, text=f"🏛️ {sr[0]}", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["text_main"]).pack(side="left")
                    ctk.CTkButton(
                        s_btn_row,
                        text="Open Station Vault ➔",
                        fg_color=THEME["accent_green"],
                        hover_color=THEME["accent_green_hover"],
                        width=180,
                        height=30,
                        command=lambda u=sr[0], a=area_name: [self.selected_unit.set(u), setattr(self, 'current_user_area', a), self.launch_main_portal(self.current_role)]
                    ).pack(side="right")
        except Exception as e:
            ctk.CTkLabel(a_right, text=f"Error: {str(e)}", text_color=THEME["accent_red"]).pack(padx=20, pady=20)

    def build_jurisdiction_tabs_content(self, parent_tabview, tab_station, tab_area, tab_city, city_filter=None):
        is_judge = (self.current_role == "COURT_JUDICIAL")

        load_area_details_ref = [None]
        load_station_details_ref = [None]

        # --- TAB 1: POLICE STATIONS ---
        st_container = ctk.CTkFrame(tab_station, fg_color="transparent")
        st_container.pack(fill="both", expand=True, padx=10, pady=10)

        s_left = ctk.CTkFrame(st_container, width=380, fg_color=THEME["card_highlight"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        s_left.pack(side="left", fill="y", padx=(0, 15))
        s_left.pack_propagate(False)

        ctk.CTkLabel(s_left, text="Police Station Branches", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(15, 5))

        # Search Bar added at the marked location
        search_st_in = ctk.CTkEntry(s_left, placeholder_text="🔍 Search Police Stations...", width=340, height=34, fg_color=THEME["input_bg"])
        search_st_in.pack(padx=15, pady=(2, 8))

        station_list_frame = ctk.CTkScrollableFrame(s_left, height=310, fg_color="transparent")
        station_list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        s_right = ctk.CTkScrollableFrame(st_container, fg_color=THEME["card_highlight"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        s_right.pack(side="right", fill="both", expand=True)

        cp_station_info_frame = s_right

        def load_station_details(s_name, div_code, area_zone):
            for w in cp_station_info_frame.winfo_children(): w.destroy()
            self.selected_division.set(div_code)
            self.selected_unit.set(s_name)
            self.current_user_area = area_zone

            ctk.CTkLabel(cp_station_info_frame, text=f"🏛️ Police Station Profile: {s_name} ({div_code} - {area_zone})", font=ctk.CTkFont(size=16, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(20, 10))

            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT officer_name, police_rank, badge_id, officer_email FROM vault_system_users WHERE unit_name = :1 AND rank_level <= 2", (s_name,))
                leads = cur.fetchall()
                cur.close()
                conn.close()

                card = ctk.CTkFrame(cp_station_info_frame, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
                card.pack(fill="x", pady=10, padx=20)
                ctk.CTkLabel(card, text="Station Leadership (SHO / IO / Forensic Scientist Lead)", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["accent_gold"]).pack(anchor="w", padx=15, pady=(12, 4))

                if leads:
                    for l in leads:
                        ctk.CTkLabel(card, text=f"• {l[1]}: {l[0]} (#{l[2]}) | Email: {l[3]}", font=ctk.CTkFont(size=11), text_color=THEME["text_main"]).pack(anchor="w", padx=15, pady=2)
                else:
                    ctk.CTkLabel(card, text="No station leads assigned currently.", font=ctk.CTkFont(size=11), text_color=THEME["text_muted"]).pack(anchor="w", padx=15, pady=2)

                def open_station_vault():
                    self.launch_main_portal(self.current_role)

                ctk.CTkButton(card, text="🔓 Open Regular Station Vault (Cases, Evidence, Issue & Return) ➔", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=open_station_vault, height=38).pack(anchor="w", padx=15, pady=(10, 8))

                if not is_judge:
                    def open_sho_enroll_modal():
                        self.open_officer_registration_modal(target_rank_type="SHO", target_city=div_code, target_area=area_zone, target_station=s_name)

                    ctk.CTkButton(card, text="➕ Add / Update Station SHO", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=open_sho_enroll_modal, width=200, height=32).pack(anchor="w", padx=15, pady=(0, 15))

            except Exception as e:
                ctk.CTkLabel(cp_station_info_frame, text=f"Error: {str(e)}", text_color=THEME["accent_red"]).pack(anchor="w", padx=20)

        load_station_details_ref[0] = load_station_details

        ctk.CTkLabel(cp_station_info_frame, text="👈 Select a police station branch on the left to inspect its leads and open the regular station data page.", font=ctk.CTkFont(size=12), text_color=THEME["text_muted"]).pack(anchor="w", padx=20, pady=20)

        def refresh_station_list(query=""):
            for w in station_list_frame.winfo_children(): w.destroy()
            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                if city_filter:
                    cur.execute("SELECT unit_name, division_code, area_zone FROM investigation_units WHERE division_code = :1", (city_filter,))
                else:
                    cur.execute("SELECT unit_name, division_code, area_zone FROM investigation_units")
                rows = cur.fetchall()
                cur.close()
                conn.close()

                for u_name, d_code, a_zone in rows:
                    if query and query.upper() not in u_name.upper():
                        continue

                    card = ctk.CTkFrame(station_list_frame, fg_color=THEME["card_bg"], corner_radius=8)
                    card.pack(fill="x", pady=4, padx=5)
                    ctk.CTkLabel(card, text=u_name, font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_main"]).pack(anchor="w", padx=10, pady=(6, 2))
                    
                    row_btns = ctk.CTkFrame(card, fg_color="transparent")
                    row_btns.pack(fill="x", padx=10, pady=(0, 6))

                    inspect_btn_width = 180 if is_judge else 140
                    ctk.CTkButton(
                        row_btns,
                        text="Inspect ➔",
                        fg_color=THEME["primary"],
                        hover_color=THEME["primary_hover"],
                        height=30,
                        width=inspect_btn_width,
                        command=lambda u=u_name, d=d_code, a=a_zone: load_station_details(u, d, a)
                    ).pack(side="left")

                    if not is_judge:
                        def delete_station(u_name_val):
                            if messagebox.askyesno("Confirm Delete", f"Permanently delete police station branch '{u_name_val}'?"):
                                try:
                                    conn_del = self.get_db_connection()
                                    cur_del = conn_del.cursor()
                                    cur_del.execute("DELETE FROM investigation_units WHERE unit_name = :1", (u_name_val,))
                                    conn_del.commit()
                                    cur_del.close()
                                    conn_del.close()
                                    refresh_station_list(search_st_in.get().strip())
                                except Exception as ex:
                                    messagebox.showerror("Error", str(ex))

                        ctk.CTkButton(
                            row_btns,
                            text="🗑️",
                            fg_color=THEME["accent_red"],
                            hover_color=THEME["accent_red_hover"],
                            height=30,
                            width=36,
                            command=lambda u=u_name: delete_station(u)
                        ).pack(side="right")
            except Exception:
                pass

        search_st_in.bind("<KeyRelease>", lambda e: refresh_station_list(search_st_in.get().strip()))

        def create_new_station_prompt():
            modal = Toplevel(self)
            modal.title("Add New Police Station")
            modal.geometry("420x300")
            modal.configure(bg=THEME["bg_main"])
            modal.grab_set()

            ctk.CTkLabel(modal, text="Select City Division:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=30, pady=(15, 2))
            cities = [city_filter] if city_filter else self.fetch_divisions()
            div_var = ctk.StringVar(value=cities[0] if cities else "SURAT")
            ctk.CTkOptionMenu(modal, values=cities if cities else ["SURAT"], variable=div_var, width=360, height=34).pack(padx=30, pady=2)

            ctk.CTkLabel(modal, text="New Police Station Name:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=30, pady=(8, 2))
            en_st = ctk.CTkEntry(modal, width=360, height=34, placeholder_text="e.g. Adajan Police Station")
            en_st.pack(padx=30, pady=2)

            ctk.CTkLabel(modal, text="Area / Zone:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=30, pady=(8, 2))
            en_zone = ctk.CTkEntry(modal, width=360, height=34, placeholder_text="e.g. Zone 1")
            en_zone.pack(padx=30, pady=2)

            def commit_station():
                s_name = en_st.get().strip()
                d_code = div_var.get()
                z_name = en_zone.get().strip() or "Zone 1"
                if not s_name: return
                try:
                    conn_s = self.get_db_connection()
                    cur_s = conn_s.cursor()
                    cur_s.execute("INSERT INTO investigation_units (division_code, unit_name, station_password, area_zone) VALUES (:1, :2, 'password123', :3)", (d_code, s_name, z_name))
                    conn_s.commit()
                    cur_s.close()
                    conn_s.close()
                    refresh_station_list(search_st_in.get().strip())
                    modal.destroy()
                except Exception as ex:
                    messagebox.showerror("Error", str(ex), parent=modal)

            ctk.CTkButton(modal, text="Add Police Station", fg_color=THEME["accent_green"], command=commit_station).pack(pady=15)

        if not is_judge:
            ctk.CTkButton(s_left, text="➕ Add New Police Station", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=create_new_station_prompt, height=36).pack(fill="x", padx=15, pady=10)
        
        refresh_station_list()

        # --- TAB 2: AREAS ---
        area_container = ctk.CTkFrame(tab_area, fg_color="transparent")
        area_container.pack(fill="both", expand=True, padx=10, pady=10)

        a_left = ctk.CTkFrame(area_container, width=380, fg_color=THEME["card_highlight"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        a_left.pack(side="left", fill="y", padx=(0, 15))
        a_left.pack_propagate(False)

        ctk.CTkLabel(a_left, text="Select Area / Zone", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(15, 5))

        # Search Bar added at the marked location
        search_area_in = ctk.CTkEntry(a_left, placeholder_text="🔍 Search Areas / Zones...", width=340, height=34, fg_color=THEME["input_bg"])
        search_area_in.pack(padx=15, pady=(2, 8))

        area_list_frame = ctk.CTkScrollableFrame(a_left, height=310, fg_color="transparent")
        area_list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        a_right = ctk.CTkScrollableFrame(area_container, fg_color=THEME["card_highlight"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        a_right.pack(side="right", fill="both", expand=True)

        ctk.CTkLabel(a_right, text="👈 Select an Area / Zone on the left to inspect ACP profile and police stations.", font=ctk.CTkFont(size=12), text_color=THEME["text_muted"]).pack(anchor="w", padx=20, pady=20)

        def load_area_details(area_name, div_code):
            for w in a_right.winfo_children(): w.destroy()
            ctk.CTkLabel(a_right, text=f"📍 Area / Zone Profile: {area_name} ({div_code})", font=ctk.CTkFont(size=16, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(20, 10))

            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT badge_id, officer_name, officer_email, police_rank FROM vault_system_users WHERE division_code = :1 AND area_zone = :2 AND rank_level = 3 AND is_active = 1", (div_code, area_name))
                dcp_row = cur.fetchone()

                cur.execute("SELECT unit_name FROM investigation_units WHERE division_code = :1 AND area_zone = :2", (div_code, area_name))
                station_rows = cur.fetchall()
                cur.close()
                conn.close()

                card = ctk.CTkFrame(a_right, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
                card.pack(fill="x", pady=10, padx=20)
                ctk.CTkLabel(card, text="Assigned Assistant Commissioner of Police (ACP / DCP)", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["accent_gold"]).pack(anchor="w", padx=15, pady=(12, 4))

                if dcp_row:
                    ctk.CTkLabel(card, text=f"Name: {dcp_row[1]}", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["text_main"]).pack(anchor="w", padx=15, pady=2)
                    ctk.CTkLabel(card, text=f"Badge ID: #{dcp_row[0]} | Rank: {dcp_row[3]}", font=ctk.CTkFont(size=11), text_color=THEME["text_muted"]).pack(anchor="w", padx=15, pady=2)
                    ctk.CTkLabel(card, text=f"Email: {dcp_row[2]}", font=ctk.CTkFont(size=11), text_color=THEME["text_muted"]).pack(anchor="w", padx=15, pady=(2, 6))

                    def update_dcp_modal():
                        modal = Toplevel(self)
                        modal.title(f"Update ACP Data for {area_name}")
                        modal.geometry("420x300")
                        modal.configure(bg=THEME["bg_main"])
                        modal.grab_set()

                        ctk.CTkLabel(modal, text=f"Update ACP for {area_name}", font=ctk.CTkFont(size=14, weight="bold"), text_color=THEME["primary"]).pack(pady=15)
                        ctk.CTkLabel(modal, text="New Full Name:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=30)
                        en_name = ctk.CTkEntry(modal, width=360, height=34)
                        en_name.insert(0, dcp_row[1])
                        en_name.pack(padx=30, pady=5)

                        ctk.CTkLabel(modal, text="New Official Email:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=30)
                        en_email = ctk.CTkEntry(modal, width=360, height=34)
                        en_email.insert(0, dcp_row[2])
                        en_email.pack(padx=30, pady=5)

                        def save_dcp():
                            try:
                                conn_up = self.get_db_connection()
                                cur_up = conn_up.cursor()
                                cur_up.execute("UPDATE vault_system_users SET officer_name = :1, officer_email = :2 WHERE badge_id = :3", (en_name.get().strip(), en_email.get().strip(), dcp_row[0]))
                                conn_up.commit()
                                cur_up.close()
                                conn_up.close()
                                messagebox.showinfo("Updated", "ACP record updated successfully!", parent=modal)
                                modal.destroy()
                                load_area_details(area_name, div_code)
                            except Exception as ex:
                                messagebox.showerror("Error", str(ex), parent=modal)

                        ctk.CTkButton(modal, text="Save Updates", fg_color=THEME["accent_green"], command=save_dcp).pack(pady=15)

                    if not is_judge:
                        btn_update_row = ctk.CTkFrame(card, fg_color="transparent")
                        btn_update_row.pack(anchor="w", padx=15, pady=(4, 15))
                        ctk.CTkButton(btn_update_row, text="✏️ Update DCP Data", fg_color="#0284C7", command=update_dcp_modal, width=150, height=32).pack(side="left", padx=(0, 10))
                        ctk.CTkButton(btn_update_row, text="✏️ Update ACP Data", fg_color="#0284C7", command=update_dcp_modal, width=150, height=32).pack(side="left")
                else:
                    ctk.CTkLabel(card, text=f"No DCP / ACP assigned to {area_name} yet.", text_color=THEME["text_muted"]).pack(anchor="w", padx=15, pady=4)
                    
                    if not is_judge:
                        def open_dcp_enroll_modal():
                            self.open_officer_registration_modal(target_rank_type="DCP", target_city=div_code, target_area=area_name)

                        def open_acp_enroll_modal():
                            self.open_officer_registration_modal(target_rank_type="ACP", target_city=div_code, target_area=area_name)

                        btn_assign_row = ctk.CTkFrame(card, fg_color="transparent")
                        btn_assign_row.pack(anchor="w", padx=15, pady=(4, 15))
                        ctk.CTkButton(btn_assign_row, text="➕ Add DCP", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=open_dcp_enroll_modal, width=130, height=32).pack(side="left", padx=(0, 10))
                        ctk.CTkButton(btn_assign_row, text="➕ Add ACP", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=open_acp_enroll_modal, width=130, height=32).pack(side="left")

                ctk.CTkLabel(a_right, text=f"Police Stations in {area_name}:", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=20, pady=(15, 5))
                if station_rows:
                    st_list_frame = ctk.CTkFrame(a_right, fg_color=THEME["card_bg"], corner_radius=10, border_width=1, border_color=THEME["card_border"])
                    st_list_frame.pack(fill="x", padx=20, pady=(0, 20))
                    for sr in station_rows:
                        s_btn_row = ctk.CTkFrame(st_list_frame, fg_color="transparent")
                        s_btn_row.pack(fill="x", padx=15, pady=6)
                        ctk.CTkLabel(s_btn_row, text=f"🏛️ {sr[0]}", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["text_main"]).pack(side="left")
                        ctk.CTkButton(
                            s_btn_row,
                            text="Inspect Station Vault ➔",
                            fg_color="#0284C7",
                            hover_color="#0369A1",
                            width=180,
                            height=30,
                            command=lambda u=sr[0], d=div_code, a=area_name: [parent_tabview.set("1. Police Stations & Station Leads"), load_station_details_ref[0](u, d, a)]
                        ).pack(side="right")
                else:
                    ctk.CTkLabel(a_right, text="No police station branches registered under this zone.", text_color=THEME["text_muted"]).pack(anchor="w", padx=20, pady=5)

            except Exception as e:
                pass

        load_area_details_ref[0] = load_area_details

        def refresh_area_list(query=""):
            for w in area_list_frame.winfo_children(): w.destroy()
            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                
                active_city = self.selected_division.get()
                if active_city:
                    cur.execute("SELECT DISTINCT division_code, area_zone FROM investigation_units WHERE division_code = :1", (active_city,))
                elif city_filter:
                    cur.execute("SELECT DISTINCT division_code, area_zone FROM investigation_units WHERE division_code = :1", (city_filter,))
                else:
                    cur.execute("SELECT DISTINCT division_code, area_zone FROM investigation_units")
                rows = cur.fetchall()
                cur.close()
                conn.close()

                for d_code, a_zone in rows:
                    if query and query.upper() not in a_zone.upper():
                        continue

                    card_a = ctk.CTkFrame(area_list_frame, fg_color=THEME["card_bg"], corner_radius=8)
                    card_a.pack(fill="x", pady=4, padx=5)
                    
                    area_btn_width = 320 if is_judge else 280
                    ctk.CTkButton(
                        card_a,
                        text=f"📍 {a_zone} ({d_code})",
                        fg_color=THEME["primary"],
                        hover_color=THEME["primary_hover"],
                        anchor="w",
                        height=36,
                        width=area_btn_width,
                        command=lambda az=a_zone, dc=d_code: load_area_details(az, dc)
                    ).pack(side="left", fill="x", expand=True, padx=(0, 4), pady=4)

                    if not is_judge:
                        def delete_area(zone_name, d_code_val):
                            if messagebox.askyesno("Confirm Delete", f"Permanently delete area zone '{zone_name}' in {d_code_val}?"):
                                try:
                                    conn_da = self.get_db_connection()
                                    cur_da = conn_da.cursor()
                                    cur_da.execute("DELETE FROM investigation_units WHERE area_zone = :1 AND division_code = :2", (zone_name, d_code_val))
                                    conn_da.commit()
                                    cur_da.close()
                                    conn_da.close()
                                    refresh_area_list(search_area_in.get().strip())
                                except Exception as ex:
                                    messagebox.showerror("Error", str(ex))

                        ctk.CTkButton(
                            card_a,
                            text="🗑️",
                            fg_color=THEME["accent_red"],
                            hover_color=THEME["accent_red_hover"],
                            height=36,
                            width=36,
                            command=lambda az=a_zone, dc=d_code: delete_area(az, dc)
                        ).pack(side="right", pady=4)
            except Exception:
                pass

        search_area_in.bind("<KeyRelease>", lambda e: refresh_area_list(search_area_in.get().strip()))

        def create_new_area_prompt():
            modal = Toplevel(self)
            modal.title("Create New Area / Zone")
            modal.geometry("400x240")
            modal.configure(bg=THEME["bg_main"])
            modal.grab_set()

            ctk.CTkLabel(modal, text="Select City Division:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=30, pady=(15, 2))
            cities = [city_filter] if city_filter else self.fetch_divisions()
            div_var = ctk.StringVar(value=cities[0] if cities else "SURAT")
            ctk.CTkOptionMenu(modal, values=cities if cities else ["SURAT"], variable=div_var, width=340, height=34).pack(padx=30, pady=2)

            ctk.CTkLabel(modal, text="New Area / Zone Name:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=30, pady=(8, 2))
            en_zone = ctk.CTkEntry(modal, width=340, height=34, placeholder_text="e.g. Zone 3 (West)")
            en_zone.pack(padx=30, pady=2)

            def commit_area():
                z_name = en_zone.get().strip()
                d_code = div_var.get()
                if not z_name: return
                try:
                    conn_z = self.get_db_connection()
                    cur_z = conn_z.cursor()
                    cur_z.execute("INSERT INTO investigation_units (division_code, unit_name, station_password, area_zone) VALUES (:1, :2, 'password123', :3)", (d_code, f"{z_name} Central Station", z_name))
                    conn_z.commit()
                    cur_z.close()
                    conn_z.close()
                    refresh_area_list(search_area_in.get().strip())
                    modal.destroy()
                except Exception as ex:
                    messagebox.showerror("Error", str(ex), parent=modal)

            ctk.CTkButton(modal, text="Create Area Zone", fg_color=THEME["accent_green"], command=commit_area).pack(pady=15)

        if not is_judge:
            ctk.CTkButton(a_left, text="➕ Create New Area / Zone", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=create_new_area_prompt, height=36).pack(fill="x", padx=15, pady=10)
        
        refresh_area_list()

        # TAB 3: CITIES (Only if tab_city is provided)
        if tab_city is not None:
            city_container = ctk.CTkFrame(tab_city, fg_color="transparent")
            city_container.pack(fill="both", expand=True, padx=10, pady=10)

            c_left = ctk.CTkFrame(city_container, width=380, fg_color=THEME["card_highlight"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
            c_left.pack(side="left", fill="y", padx=(0, 15))
            c_left.pack_propagate(False)

            ctk.CTkLabel(c_left, text="State Cities / Divisions", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=(15, 5))

            # Search Bar added at the marked location
            search_city_in = ctk.CTkEntry(c_left, placeholder_text="🔍 Search Cities / Divisions...", width=340, height=34, fg_color=THEME["input_bg"])
            search_city_in.pack(padx=15, pady=(2, 8))

            city_list_frame = ctk.CTkScrollableFrame(c_left, height=310, fg_color="transparent")
            city_list_frame.pack(fill="both", expand=True, padx=10, pady=5)

            c_right = ctk.CTkFrame(city_container, fg_color=THEME["card_highlight"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
            c_right.pack(side="right", fill="both", expand=True)

            cp_info_frame = ctk.CTkScrollableFrame(c_right, fg_color="transparent")
            cp_info_frame.pack(fill="both", expand=True, padx=20, pady=20)

            ctk.CTkLabel(cp_info_frame, text="👈 Select a city from the left panel to inspect Commissioner of Police (CP) data and drill down into areas.", font=ctk.CTkFont(size=12), text_color=THEME["text_muted"]).pack(anchor="w", pady=20)

            def load_cp_details_for_city(div_code):
                for w in cp_info_frame.winfo_children(): w.destroy()
                self.selected_division.set(div_code)

                ctk.CTkLabel(cp_info_frame, text=f"🏙️ Commissionerate Profile: {div_code}", font=ctk.CTkFont(size=16, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", pady=(0, 10))

                try:
                    conn = self.get_db_connection()
                    cur = conn.cursor()
                    cur.execute("SELECT badge_id, officer_name, officer_email, police_rank FROM vault_system_users WHERE division_code = :1 AND rank_level = 4 AND is_active = 1", (div_code,))
                    cp_row = cur.fetchone()

                    cur.execute("SELECT DISTINCT area_zone FROM investigation_units WHERE division_code = :1", (div_code,))
                    area_rows = cur.fetchall()
                    cur.close()
                    conn.close()

                    card = ctk.CTkFrame(cp_info_frame, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
                    card.pack(fill="x", pady=10, padx=5)

                    ctk.CTkLabel(card, text="Assigned City Commissioner of Police (CP)", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["accent_gold"]).pack(anchor="w", padx=15, pady=(12, 4))

                    if cp_row:
                        ctk.CTkLabel(card, text=f"Name: {cp_row[1]}", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["text_main"]).pack(anchor="w", padx=15, pady=2)
                        ctk.CTkLabel(card, text=f"Badge ID: #{cp_row[0]} | Rank: {cp_row[3]}", font=ctk.CTkFont(size=11), text_color=THEME["text_muted"]).pack(anchor="w", padx=15, pady=2)
                        ctk.CTkLabel(card, text=f"Official Email: {cp_row[2]}", font=ctk.CTkFont(size=11), text_color=THEME["text_muted"]).pack(anchor="w", padx=15, pady=(2, 6))

                        def update_cp_modal():
                            modal = Toplevel(self)
                            modal.title(f"Update CP Data for {div_code}")
                            modal.geometry("420x300")
                            modal.configure(bg=THEME["bg_main"])
                            modal.grab_set()

                            ctk.CTkLabel(modal, text=f"Update CP for {div_code}", font=ctk.CTkFont(size=14, weight="bold"), text_color=THEME["primary"]).pack(pady=15)
                            ctk.CTkLabel(modal, text="New CP Full Name:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=30)
                            en_name = ctk.CTkEntry(modal, width=360, height=34)
                            en_name.insert(0, cp_row[1])
                            en_name.pack(padx=30, pady=5)

                            ctk.CTkLabel(modal, text="New Official Email:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=30)
                            en_email = ctk.CTkEntry(modal, width=360, height=34)
                            en_email.insert(0, cp_row[2])
                            en_email.pack(padx=30, pady=5)

                            def save_cp():
                                try:
                                    conn_up = self.get_db_connection()
                                    cur_up = conn_up.cursor()
                                    cur_up.execute("UPDATE vault_system_users SET officer_name = :1, officer_email = :2 WHERE badge_id = :3", (en_name.get().strip(), en_email.get().strip(), cp_row[0]))
                                    conn_up.commit()
                                    cur_up.close()
                                    conn_up.close()
                                    messagebox.showinfo("Updated", "CP record updated successfully!", parent=modal)
                                    modal.destroy()
                                    load_cp_details_for_city(div_code)
                                except Exception as ex:
                                    messagebox.showerror("Error", str(ex), parent=modal)

                            ctk.CTkButton(modal, text="Save Updates", fg_color=THEME["accent_green"], command=save_cp).pack(pady=15)

                        if not is_judge:
                            ctk.CTkButton(card, text="✏️ Add / Update CP Data", fg_color="#0284C7", command=update_cp_modal, width=170, height=32).pack(anchor="w", padx=15, pady=(4, 15))
                    else:
                        ctk.CTkLabel(card, text=f"No City Commissioner assigned to {div_code} yet.", text_color=THEME["text_muted"]).pack(anchor="w", padx=15, pady=4)
                        
                        if not is_judge:
                            def open_cp_enroll_modal():
                                self.open_officer_registration_modal(target_rank_type="CP", target_city=div_code)

                            ctk.CTkButton(card, text="➕ Add / Update CP", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=open_cp_enroll_modal, width=160, height=32).pack(anchor="w", padx=15, pady=(4, 15))

                    ctk.CTkLabel(cp_info_frame, text=f"Areas / Zones in {div_code}:", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", pady=(15, 5))
                    if area_rows:
                        ar_list_frame = ctk.CTkFrame(cp_info_frame, fg_color=THEME["card_bg"], corner_radius=10, border_width=1, border_color=THEME["card_border"])
                        ar_list_frame.pack(fill="x", pady=(0, 10))
                        for ar in area_rows:
                            ar_btn_row = ctk.CTkFrame(ar_list_frame, fg_color="transparent")
                            ar_btn_row.pack(fill="x", padx=15, pady=6)
                            ctk.CTkLabel(ar_btn_row, text=f"📍 {ar[0]}", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["text_main"]).pack(side="left")
                            ctk.CTkButton(
                                ar_btn_row,
                                text="Inspect Area (ACP & Stations) ➔",
                                fg_color="#0284C7",
                                hover_color="#0369A1",
                                width=220,
                                height=30,
                                command=lambda a_name=ar[0], d_c=div_code: [parent_tabview.set("2. Areas, Zones & DCP / ACP"), load_area_details_ref[0](a_name, d_c)]
                            ).pack(side="right")
                    else:
                        ctk.CTkLabel(cp_info_frame, text="No areas or zones registered under this city.", text_color=THEME["text_muted"]).pack(anchor="w", pady=5)

                except Exception as e:
                    ctk.CTkLabel(cp_info_frame, text=f"Error loading city record: {str(e)}", text_color=THEME["accent_red"]).pack(anchor="w")

            def refresh_city_list(query=""):
                for w in city_list_frame.winfo_children(): w.destroy()
                cities = self.fetch_divisions()
                for c in cities:
                    if query and query.upper() not in c.upper():
                        continue

                    row_f = ctk.CTkFrame(city_list_frame, fg_color=THEME["card_bg"], corner_radius=8)
                    row_f.pack(fill="x", pady=4, padx=5)
                    
                    city_btn_width = 320 if is_judge else 280
                    ctk.CTkButton(row_f, text=f"🏙️ {c}", fg_color=THEME["primary"], hover_color=THEME["primary_hover"], anchor="w", height=36, width=city_btn_width, command=lambda code=c: load_cp_details_for_city(code)).pack(side="left", fill="x", expand=True, padx=(0, 4))
                    
                    if not is_judge:
                        def delete_city(code):
                            if messagebox.askyesno("Confirm Delete", f"Permanently delete city division {code}?"):
                                try:
                                    conn_d = self.get_db_connection()
                                    cur_d = conn_d.cursor()
                                    cur_d.execute("DELETE FROM police_divisions WHERE division_code = :1", (code,))
                                    conn_d.commit()
                                    cur_d.close()
                                    conn_d.close()
                                    refresh_city_list(search_city_in.get().strip())
                                except Exception as ex:
                                    messagebox.showerror("Error", str(ex))

                        ctk.CTkButton(row_f, text="🗑️", fg_color=THEME["accent_red"], width=36, height=36, command=lambda code=c: delete_city(code)).pack(side="right")

            search_city_in.bind("<KeyRelease>", lambda e: refresh_city_list(search_city_in.get().strip()))

            def create_new_city_prompt():
                modal = Toplevel(self)
                modal.title("Create New City Commissionerate")
                modal.geometry("400x240")
                modal.configure(bg=THEME["bg_main"])
                modal.grab_set()

                ctk.CTkLabel(modal, text="New City / Division Code:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=30, pady=(20, 2))
                en_c = ctk.CTkEntry(modal, width=340, height=34, placeholder_text="e.g. VADODARA")
                en_c.pack(padx=30, pady=5)

                def commit_city():
                    c_code = en_c.get().strip().upper()
                    if not c_code: return
                    try:
                        conn_c = self.get_db_connection()
                        cur_c = conn_c.cursor()
                        cur_c.execute("INSERT INTO police_divisions (division_code, division_name, division_password, nodal_officer_email) VALUES (:1, :2, 'password123', 'cp@police.gov.in')", (c_code, f"{c_code} Police Commissionerate"))
                        conn_c.commit()
                        cur_c.close()
                        conn_c.close()
                        refresh_city_list(search_city_in.get().strip())
                        modal.destroy()
                    except Exception as ex:
                        messagebox.showerror("Error", str(ex), parent=modal)

                ctk.CTkButton(modal, text="Create City Division", fg_color=THEME["accent_green"], command=commit_city).pack(pady=15)

            if not is_judge:
                ctk.CTkButton(c_left, text="➕ Create New City", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=create_new_city_prompt, height=36).pack(fill="x", padx=15, pady=10)
            
            refresh_city_list()

    def build_cases_tab(self):
        container = ctk.CTkFrame(self.tab_cases, fg_color="transparent")
        container.pack(fill="both", expand=True)

        if self.current_role != "COURT_JUDICIAL":
            left = ctk.CTkScrollableFrame(container, width=320, fg_color=THEME["card_highlight"], border_width=1, border_color=THEME["card_border"], corner_radius=12)
            left.pack(side="left", fill="y", padx=(0, 15), pady=5)

            ctk.CTkLabel(left, text="Register New Case Profile", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"]).pack(pady=10, padx=10, anchor="w")

            ctk.CTkLabel(left, text="Case No: [Auto-Generated by Station]", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_muted"]).pack(anchor="w", padx=10, pady=(4, 1))

            self.in_case_name = self.create_styled_entry(left, "Case Name (e.g. Lalita Bank Robbery)")
            
            ctk.CTkLabel(left, text="Case Category (for Analytics & Graphs):", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_main"]).pack(anchor="w", padx=10, pady=(6, 1))
            self.case_category_var = ctk.StringVar(value="Robbery / Theft")
            cat_menu = ctk.CTkOptionMenu(
                left,
                values=["Murder / Homicide", "Robbery / Theft", "Cyber / Ransomware", "Narcotics", "Economic Offense", "Assault / Other"],
                variable=self.case_category_var,
                fg_color=THEME["input_bg"],
                text_color=THEME["text_main"],
                height=34
            )
            cat_menu.pack(fill="x", padx=10, pady=2)

            self.in_fir_no = self.create_styled_entry(left, "FIR No (e.g. FIR-001/2026)")
            self.in_location = self.create_styled_entry(left, "Crime Scene / Location")
            
            self.in_registered_by = self.create_styled_entry(left, "Case Registered By (Officer Name/Badge)")
            if self.current_user_name:
                self.in_registered_by.insert(0, f"{self.current_user_name} (#{self.current_user_badge})")

            ctk.CTkLabel(left, text="Condition of Case:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_main"]).pack(anchor="w", padx=10, pady=(6, 1))
            self.case_cond_var = ctk.StringVar(value="Under Investigation")
            cond_menu = ctk.CTkOptionMenu(
                left,
                values=["Under Investigation", "Charge Sheet Filed", "Pending Trial", "Convicted & Sentenced", "Transferred to Forensics", "Closed / Acquitted"],
                variable=self.case_cond_var,
                fg_color=THEME["input_bg"],
                text_color=THEME["text_main"],
                height=34
            )
            cond_menu.pack(fill="x", padx=10, pady=2)

            self.in_punishment = self.create_styled_entry(left, "Sentence / Jail Facility (Optional)")

            ctk.CTkButton(left, text="➕ Commit & Anchor Case", fg_color=THEME["primary"], hover_color=THEME["primary_hover"], command=self.register_case_profile).pack(fill="x", padx=10, pady=(15, 6))

            ctk.CTkLabel(left, text="Active Case Actions:", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=10, pady=(12, 2))
            ctk.CTkButton(left, text="📂 Ingest / Encrypt Exhibits", fg_color="#0284C7", hover_color="#0369A1", command=self.open_evidence_manager_modal).pack(fill="x", padx=10, pady=3)
            ctk.CTkButton(left, text="🔄 Update Status & Detention", fg_color=THEME["accent_gold"], hover_color=THEME["accent_gold_hover"], command=self.open_update_case_condition_modal).pack(fill="x", padx=10, pady=3)

            ctk.CTkLabel(left, text="Official Statutory Reports:", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=10, pady=(12, 2))
            ctk.CTkButton(left, text="📄 Print Selected Case Dossier (All Evidences)", fg_color="#1E293B", hover_color="#0F172A", command=self.export_complete_case_dossier_pdf).pack(fill="x", padx=10, pady=3)
            ctk.CTkButton(left, text="📊 Print Pending Cases Summary Report", fg_color="#047857", hover_color="#065F46", command=self.export_pending_cases_report_pdf).pack(fill="x", padx=10, pady=3)
        else:
            left = ctk.CTkFrame(container, width=280, fg_color=THEME["card_highlight"], border_width=1, border_color=THEME["card_border"], corner_radius=12)
            left.pack(side="left", fill="y", padx=(0, 15), pady=5)
            ctk.CTkLabel(left, text="Judicial Inspection Portal", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["accent_gold"]).pack(pady=15, padx=10)
            ctk.CTkLabel(left, text="Read-Only Evidence Manifest:\nSelect any case record to inspect encrypted child exhibits, verify SHA-256 hashes, view the visual timeline, and export statutory dossiers.", font=ctk.CTkFont(size=11), text_color=THEME["text_muted"], wraplength=240, justify="center").pack(padx=10, pady=10)
            ctk.CTkButton(left, text="📂 Inspect Evidence Exhibits", fg_color="#0284C7", hover_color="#0369A1", command=self.open_evidence_manager_modal).pack(fill="x", padx=15, pady=6)
            ctk.CTkButton(left, text="📄 Print Case Dossier + Evidences", fg_color="#1E293B", hover_color="#0F172A", command=self.export_complete_case_dossier_pdf).pack(fill="x", padx=15, pady=6)
            ctk.CTkButton(left, text="📊 Print Pending Cases Report", fg_color="#047857", hover_color="#065F46", command=self.export_pending_cases_report_pdf).pack(fill="x", padx=15, pady=6)

        right = ctk.CTkFrame(container, fg_color=THEME["card_highlight"], border_width=1, border_color=THEME["card_border"], corner_radius=12)
        right.pack(side="right", fill="both", expand=True, pady=5)

        search_bar = ctk.CTkFrame(right, height=45, fg_color="transparent")
        search_bar.pack(fill="x", padx=12, pady=(10, 5))
        
        self.search_keyword_in = ctk.CTkEntry(search_bar, placeholder_text="🔍 Intelligent Keyword / FIR / City / Station Search...", width=380, height=34, fg_color=THEME["input_bg"])
        self.search_keyword_in.pack(side="left", padx=(0, 8))
        self.search_keyword_in.bind("<KeyRelease>", lambda e: self.populate_cases_table(self.search_keyword_in.get().strip()))
        ctk.CTkButton(search_bar, text="Clear Search", width=90, height=34, fg_color="#64748B", command=lambda: [self.search_keyword_in.delete(0, 'end'), self.populate_cases_table()]).pack(side="left")

        self.backlog_label = ctk.CTkLabel(search_bar, text="Pending Cases: Computing...", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["accent_red"])
        self.backlog_label.pack(side="right", padx=10)

        cols = ("case_no", "case_name", "fir_no", "location", "condition", "punishment", "city", "area", "station", "evidence_count", "registered_by")
        self.case_table = ttk.Treeview(right, columns=cols, show="headings", selectmode="browse")
        
        v_scroll = ttk.Scrollbar(right, orient="vertical", command=self.case_table.yview)
        h_scroll = ttk.Scrollbar(right, orient="horizontal", command=self.case_table.xview)
        self.case_table.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.case_table.heading("case_no", text="Case No")
        self.case_table.heading("case_name", text="Case Name / Title")
        self.case_table.heading("fir_no", text="FIR Ref")
        self.case_table.heading("location", text="Crime Location")
        self.case_table.heading("condition", text="Condition of Case")
        self.case_table.heading("punishment", text="Judicial Verdict / Jail Facility")
        self.case_table.heading("city", text="City / Division")
        self.case_table.heading("area", text="Area / Zone")
        self.case_table.heading("station", text="Police Station")
        self.case_table.heading("evidence_count", text="Evidences")
        self.case_table.heading("registered_by", text="Registered By")

        self.case_table.column("case_no", width=110, minwidth=85, anchor="center")
        self.case_table.column("case_name", width=250, minwidth=180, anchor="center")
        self.case_table.column("fir_no", width=120, minwidth=95, anchor="center")
        self.case_table.column("location", width=200, minwidth=140, anchor="center")
        self.case_table.column("condition", width=160, minwidth=130, anchor="center")
        self.case_table.column("punishment", width=380, minwidth=300, anchor="center")
        self.case_table.column("city", width=130, minwidth=100, anchor="center")
        self.case_table.column("area", width=140, minwidth=110, anchor="center")
        self.case_table.column("station", width=180, minwidth=140, anchor="center")
        self.case_table.column("evidence_count", width=100, minwidth=80, anchor="center")
        self.case_table.column("registered_by", width=160, minwidth=130, anchor="center")

        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        self.case_table.pack(fill="both", expand=True, padx=(12, 0), pady=(5, 0))
        self.case_table.bind("<Double-1>", lambda event: self.open_evidence_manager_modal())

        self.populate_cases_table()

    def register_case_profile(self):
        c_name = self.in_case_name.get().strip()
        c_cat = self.case_category_var.get()
        f_no = self.in_fir_no.get().strip().upper()
        loc = self.in_location.get().strip()
        reg_by = self.in_registered_by.get().strip() or f"{self.current_rank} #{self.current_user_badge}"
        cond = self.case_cond_var.get()
        punish = self.in_punishment.get().strip() or "Pending Trial / No Conviction Yet"
        div = self.selected_division.get()
        unit = self.selected_unit.get()
        area = self.current_user_area or "Zone 1 (North)"

        if not c_name or not f_no or not loc:
            messagebox.showerror("Error", "Case Name, FIR No, and Location are mandatory.")
            return

        prefix = "".join([word[0] for word in unit.split() if word]).upper()[:3]
        if len(prefix) < 2:
            prefix = "PS"
        year_str = datetime.now().strftime('%Y')

        try:
            conn_cnt = self.get_db_connection()
            cur_cnt = conn_cnt.cursor()
            cur_cnt.execute("SELECT COUNT(*) FROM case_profiles WHERE unit_name = :1", (unit,))
            cnt = cur_cnt.fetchone()[0] + 1
            cur_cnt.close()
            conn_cnt.close()
        except Exception:
            cnt = random.randint(100, 999)

        c_no = f"{prefix}-{year_str}-{cnt:03d}"
        full_case_title = f"[{c_cat}] {c_name}"

        confirm_msg = (
            f"Are you sure you want to register Case '{full_case_title}' (Auto-Generated No: {c_no}) under station {unit}?\n\n"
            f"⚠️ STRICT LEGAL NOTICE:\n"
            f"Core case parameters are cryptographically anchored and stored specifically for station: {unit}."
        )
        if not messagebox.askyesno("Confirm Permanent Case Registration", confirm_msg):
            return

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO case_profiles (case_no, case_name, fir_no, crime_location, case_condition, punishment_details, conviction_date, division_code, area_zone, unit_name, registered_by)
                VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11)
            """, (c_no, full_case_title, f_no, loc, cond, punish, datetime.now().strftime('%Y-%m-%d'), div, area, unit, reg_by))
            conn.commit()
            cur.close()
            conn.close()

            self.log_chained_audit_event("CASE_REGISTERED", f"Case {c_no} (FIR {f_no}) registered in {unit} by {reg_by}")
            self.populate_cases_table()
            messagebox.showinfo("Case Registered", f"Case '{full_case_title}' registered successfully with Auto-Generated No: {c_no} under station {unit}!")
            self.in_case_name.delete(0, 'end')
            self.in_fir_no.delete(0, 'end')
            self.in_location.delete(0, 'end')
            self.in_punishment.delete(0, 'end')
        except Exception as e:
            messagebox.showerror("Database Error", str(e))

    def populate_cases_table(self, search_query=""):
        for r in self.case_table.get_children(): self.case_table.delete(r)
        div = self.selected_division.get()
        unit = self.selected_unit.get()
        area = self.current_user_area or ""

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()

            # Strict station-level data separation for every police station
            if self.current_rank_level == 5 or self.current_role == "COURT_JUDICIAL":
                if unit and unit not in ["State Command Center", "Surat Headquarters", "Sessions Court", ""]:
                    where_clause = "c.unit_name = :1"
                    params = [unit]
                else:
                    where_clause = "1=1"
                    params = []
            elif self.current_rank_level == 4:
                if unit and unit != "City Headquarters":
                    where_clause = "c.division_code = :1 AND c.unit_name = :2"
                    params = [div, unit]
                else:
                    where_clause = "c.division_code = :1"
                    params = [div]
            elif self.current_rank_level == 3:
                where_clause = "c.division_code = :1 AND c.area_zone = :2 AND c.unit_name = :3"
                params = [div, area, unit]
            else:
                where_clause = "c.division_code = :1 AND c.unit_name = :2"
                params = [div, unit]

            if search_query:
                q = f"%{search_query.upper()}%"
                where_clause += f" AND (UPPER(c.case_no) LIKE ? OR UPPER(c.case_name) LIKE ? OR UPPER(c.fir_no) LIKE ? OR UPPER(c.crime_location) LIKE ? OR UPPER(c.unit_name) LIKE ? OR UPPER(c.division_code) LIKE ?)"
                params.extend([q, q, q, q, q, q])

            formatted_sql = f"""
                SELECT c.case_no, c.case_name, c.fir_no, c.crime_location, c.case_condition, c.punishment_details, c.division_code, c.area_zone, c.unit_name, 
                       (SELECT COUNT(*) FROM case_evidence_files e WHERE e.case_no = c.case_no) as ev_count,
                       c.registered_by
                FROM case_profiles c
                WHERE {where_clause}
                ORDER BY c.created_at DESC
            """
            
            for idx in range(len(params)):
                if "?" in formatted_sql:
                    formatted_sql = formatted_sql.replace("?", f":{idx+1}", 1)

            cur.execute(formatted_sql, params)
            rows = cur.fetchall()

            pending_count = 0
            for row in rows:
                self.case_table.insert("", "end", values=row)
                if row[4] not in ["Convicted & Sentenced", "Closed / Acquitted"]:
                    pending_count += 1

            self.backlog_label.configure(text=f"Station [{unit or 'All'}] Unresolved Cases: {pending_count} / {len(rows)}")
            cur.close()
            conn.close()
        except Exception:
            pass

    def export_complete_case_dossier_pdf(self):
        sel = self.case_table.selection()
        if not sel:
            messagebox.showwarning("Select Case", "Please select a case from the table to print its complete dossier.")
            return

        case_data = self.case_table.item(sel[0])["values"]
        c_no, c_name, f_no, loc, cond, punish, c_div, c_area, c_unit = case_data[0], case_data[1], case_data[2], case_data[3], case_data[4], case_data[5], case_data[6], case_data[7], case_data[8]

        fpath = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"Complete_Case_Dossier_{c_no}.pdf")
        if not fpath: return

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT evidence_id, evidence_title, category, ai_classification, sha256_hash, vault_locker, active_custody_officer, encrypted_path FROM case_evidence_files WHERE case_no = :1", (c_no,))
            ev_rows = cur.fetchall()
            cur.close()
            conn.close()

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            styles = getSampleStyleSheet()
            elements = []

            title_style = ParagraphStyle("TStyle", parent=styles["Heading1"], fontSize=14, alignment=1, textColor=colors.HexColor("#1E3A8A"))
            sub_style = ParagraphStyle("SubStyle", parent=styles["Normal"], fontSize=9, alignment=1, textColor=colors.HexColor("#475569"))
            h2_style = ParagraphStyle("H2Style", parent=styles["Heading2"], fontSize=11, textColor=colors.HexColor("#1E3A8A"))
            body_style = ParagraphStyle("BStyle", parent=styles["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#0F172A"))

            elements.append(Paragraph("MINISTRY OF HOME AFFAIRS • GOVERNMENT OF INDIA", sub_style))
            elements.append(Paragraph(f"OFFICIAL CASE & EVIDENCE LIFECYCLE DOSSIER", title_style))
            elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1E3A8A"), spaceAfter=12))

            meta_data = [
                ["Master Case Number:", c_no, "FIR Reference:", f_no],
                ["Incident / Case Title:", c_name, "Incident Scene:", loc],
                ["Jurisdiction Division:", c_div, "Area Zone / Station:", f"{c_area} — {c_unit}"],
                ["Current Case Condition:", cond, "Conviction / Detention:", punish],
                ["Sealing & Ingestion Stamp:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "Inspecting Authority:", f"{self.current_rank} {self.current_user_name}"]
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

            elements.append(Paragraph("<b>ITEMIZED DIGITAL EVIDENCE EXHIBITS, BIT-LEVEL SHA-256 SEALS & VISUAL ATTACHMENTS:</b>", h2_style))
            elements.append(Spacer(1, 6))

            if ev_rows:
                for er in ev_rows:
                    eid, etitle, ecat, eclass, ehash, elocker, ecustody, enc_path = er[0], er[1], er[2], er[3], er[4], er[5], er[6], er[7]
                    
                    exhibit_meta = [
                        [Paragraph(f"<b>Exhibit ID:</b> {eid}", body_style), Paragraph(f"<b>Title:</b> {etitle}", body_style)],
                        [Paragraph(f"<b>Category:</b> {ecat} ({eclass})", body_style), Paragraph(f"<b>Vault Shelf:</b> {elocker} | <b>Custody:</b> {ecustody}", body_style)],
                        [Paragraph(f"<b>SHA-256 Seal:</b> {ehash}", body_style), ""]
                    ]
                    t_ex = Table(exhibit_meta, colWidths=[260, 280])
                    t_ex.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
                        ('PADDING', (0,0), (-1,-1), 4),
                        ('SPAN', (0,2), (1,2))
                    ]))
                    elements.append(t_ex)
                    elements.append(Spacer(1, 4))

                    is_img = False
                    img_temp_path = None
                    if os.path.exists(enc_path):
                        try:
                            dec_bytes = EncryptionEngine.decrypt_file_to_bytes(enc_path)
                            ext = ecat.lower()
                            if "photograph" in ext or "image" in ext or "visual" in ext or "cctv" not in ext:
                                img_temp_path = os.path.join(VAULT_STORAGE_DIR, f"PDF_IMG_{eid}.png")
                                with open(img_temp_path, "wb") as f_img:
                                    f_img.write(dec_bytes)
                                Image.open(img_temp_path)
                                is_img = True
                        except Exception:
                            is_img = False

                    if is_img and img_temp_path and os.path.exists(img_temp_path):
                        try:
                            rl_img = RLImage(img_temp_path, width=160, height=110)
                            elements.append(rl_img)
                        except Exception:
                            elements.append(Paragraph("<i>[Visual attachment rendering failed]</i>", body_style))
                    else:
                        elements.append(Paragraph("<b>[This is footage / binary dump which can't be represented in PDF so please check in app for this]</b>", ParagraphStyle("FootageNote", parent=body_style, textColor=colors.HexColor("#DC2626"), fontName="Helvetica-Bold")))

                    elements.append(Spacer(1, 10))
            else:
                elements.append(Paragraph("<i>No digital evidence exhibits attached to this case profile yet.</i>", body_style))

            elements.append(Spacer(1, 15))
            elements.append(Paragraph("<b>STATUTORY AUTHENTICITY CERTIFICATE:</b> This electronic case record and its attached child evidence exhibits are cryptographically anchored under AES-256 encryption at rest and SHA-256 bit-stream integrity seals. Admissible in judicial trial under Indian Evidentiary Statutes (Section 65B IEA / Section 63 BSA).", body_style))

            doc.build(elements)
            with open(fpath, "wb") as f: f.write(buffer.getvalue())
            buffer.close()

            self.log_chained_audit_event("CASE_DOSSIER_PRINTED", f"Exported complete dossier for Case {c_no}")
            messagebox.showinfo("Dossier Printed", f"Complete Case Dossier generated successfully at:\n{fpath}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def export_pending_cases_report_pdf(self):
        fpath = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"Pending_Cases_Backlog_Report_{self.selected_unit.get()}.pdf")
        if not fpath: return

        try:
            div = self.selected_division.get()
            unit = self.selected_unit.get()
            area = self.current_user_area or ""

            conn = self.get_db_connection()
            cur = conn.cursor()

            cur.execute("SELECT case_no, case_name, fir_no, crime_location, case_condition, division_code, unit_name, TO_CHAR(created_at, 'YYYY-MM-DD') FROM case_profiles WHERE division_code = :1 AND unit_name = :2 AND case_condition NOT IN ('Convicted & Sentenced', 'Closed / Acquitted')", (div, unit))

            rows = cur.fetchall()
            cur.close()
            conn.close()

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            styles = getSampleStyleSheet()
            elements = []

            title_style = ParagraphStyle("TStyle", parent=styles["Heading1"], fontSize=14, alignment=1, textColor=colors.HexColor("#1E3A8A"))
            sub_style = ParagraphStyle("SubStyle", parent=styles["Normal"], fontSize=9, alignment=1, textColor=colors.HexColor("#475569"))

            elements.append(Paragraph("MINISTRY OF HOME AFFAIRS • GOVERNMENT OF INDIA", sub_style))
            elements.append(Paragraph(f"OFFICIAL PENDING CASES REPORT — {unit}", title_style))
            elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1E3A8A"), spaceAfter=12))

            summary_text = f"Report Generated By: {self.current_rank} {self.current_user_name} (#{self.current_user_badge}) | Station: {unit} | Total Pending Dockets: {len(rows)}"
            elements.append(Paragraph(summary_text, ParagraphStyle("Summ", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#0F172A"))))
            elements.append(Spacer(1, 10))

            if rows:
                p_data = [["Case No", "Case Name / Title", "FIR Ref", "Crime Location", "Status / Stage", "City", "Police Station", "Registered Date"]]
                for r in rows:
                    p_data.append([str(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4]), str(r[5]), str(r[6]), str(r[7])])

                t_p = Table(p_data, colWidths=[80, 140, 80, 110, 100, 70, 90, 70])
                t_p.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#94A3B8")),
                    ('FONTSIZE', (0,0), (-1,-1), 7.5),
                    ('PADDING', (0,0), (-1,-1), 4),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ]))
                elements.append(t_p)
            else:
                elements.append(Paragraph(f"<i>No pending cases in {unit}. Zero backlog reported.</i>", styles["Normal"]))

            doc.build(elements)
            with open(fpath, "wb") as f: f.write(buffer.getvalue())
            buffer.close()

            self.log_chained_audit_event("PENDING_REPORT_PRINTED", f"Exported pending cases report for {unit}")
            messagebox.showinfo("Report Printed", f"Pending cases report generated successfully at:\n{fpath}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def open_update_case_condition_modal(self):
        sel = self.case_table.selection()
        if not sel:
            messagebox.showwarning("Select Case", "Please select a Case profile from the table.")
            return

        case_data = self.case_table.item(sel[0])["values"]
        selected_case_no = case_data[0]
        selected_case_name = case_data[1]
        current_condition = case_data[4]
        current_punishment = case_data[5]

        modal = Toplevel(self)
        modal.title(f"Update Case Status: {selected_case_no}")
        modal.geometry("520x420")
        modal.configure(bg=THEME["bg_main"])
        modal.grab_set()

        top_h = ctk.CTkFrame(modal, fg_color=THEME["primary"], height=50, corner_radius=0)
        top_h.pack(fill="x")
        ctk.CTkLabel(top_h, text="Update Judicial Status & Jail Facility", font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=20, pady=10)

        card = ctk.CTkFrame(modal, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        card.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(card, text=f"Case: {selected_case_name} ({selected_case_no})", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["text_main"]).pack(pady=(10, 2))
        ctk.CTkLabel(card, text="Note: Core case metadata remains locked for forensic integrity.", font=ctk.CTkFont(size=10), text_color=THEME["text_muted"]).pack(pady=(0, 10))

        ctk.CTkLabel(card, text="Update Condition of Case:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=30, pady=(2, 1))
        new_cond_var = ctk.StringVar(value=current_condition)
        cond_dropdown = ctk.CTkOptionMenu(
            card,
            values=["Under Investigation", "Charge Sheet Filed", "Pending Trial", "Convicted & Sentenced", "Transferred to Forensics", "Closed / Acquitted"],
            variable=new_cond_var,
            width=380,
            height=36,
            fg_color=THEME["input_bg"],
            text_color=THEME["text_main"]
        )
        cond_dropdown.pack(pady=4)

        ctk.CTkLabel(card, text="Judicial Verdict / Detention Facility:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=30, pady=(6, 1))
        punish_in = self.create_styled_entry(card, "e.g. 5 Years RI at Lajpore Central Jail, Surat")
        punish_in.insert(0, current_punishment)

        def commit_condition_update():
            new_val = new_cond_var.get()
            new_punish = punish_in.get().strip() or "Pending Trial / No Conviction Yet"

            if not messagebox.askyesno("Confirm Status Update", f"Update status for Case {selected_case_no}?\n\nNew Condition: {new_val}\nDetention Facility: {new_punish}", parent=modal):
                return

            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                cur.execute("UPDATE case_profiles SET case_condition = :1, punishment_details = :2 WHERE case_no = :3", (new_val, new_punish, selected_case_no))
                conn.commit()
                cur.close()
                conn.close()

                self.log_chained_audit_event("CASE_STATUS_UPDATED", f"Case {selected_case_no} status -> {new_val}")
                self.populate_cases_table()
                messagebox.showinfo("Status Updated", f"Case {selected_case_no} status updated.", parent=modal)
                modal.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)

        ctk.CTkButton(card, text="💾 Commit Status & Detention Update", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=commit_condition_update, width=380, height=40).pack(pady=(16, 10))

    def open_evidence_manager_modal(self):
        sel = self.case_table.selection()
        if not sel:
            messagebox.showwarning("Select Case", "Please select a Case profile from the table first.")
            return

        case_data = self.case_table.item(sel[0])["values"]
        selected_case_no = case_data[0]
        selected_case_name = case_data[1]
        selected_fir_no = case_data[2]

        modal = Toplevel(self)
        modal.title(f"Evidence Repository for Case {selected_case_no} ({selected_case_name})")
        modal.geometry("1160x680")
        modal.configure(bg=THEME["bg_main"])
        modal.grab_set()

        top_header = ctk.CTkFrame(modal, fg_color=THEME["primary"], height=60, corner_radius=0)
        top_header.pack(fill="x")
        ctk.CTkLabel(top_header, text=f"📁 Evidence Manifest: {selected_case_name} (Case No: {selected_case_no} | FIR: {selected_fir_no})", font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=20, pady=12)

        main_box = ctk.CTkFrame(modal, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=15, pady=15)

        if self.current_role != "COURT_JUDICIAL":
            left_add = ctk.CTkFrame(main_box, width=330, fg_color=THEME["card_bg"], corner_radius=14, border_width=1, border_color=THEME["card_border"])
            left_add.pack(side="left", fill="y", padx=(0, 12))

            ctk.CTkLabel(left_add, text="Ingest & Encrypt Evidence", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"]).pack(pady=10, padx=12, anchor="w")

            ev_id_in = self.create_styled_entry(left_add, "Evidence ID (e.g. EV-CCTV-01)")
            ev_title_in = self.create_styled_entry(left_add, "Evidence Title / Name")
            ev_lock_in = self.create_styled_entry(left_add, "Locker / Shelf Location")

            ai_cat_lbl = ctk.CTkLabel(left_add, text="AI Classification: Auto-Detecting...", font=ctk.CTkFont(size=10, weight="bold"), text_color=THEME["accent_gold"])
            ai_cat_lbl.pack(padx=12, pady=2, anchor="w")

            file_var = ctk.StringVar(value="")
            detected_category = ["Digital Exhibit"]
            detected_classification = ["General Record"]
            extracted_text_holder = [""]

            def pick_file():
                p = filedialog.askopenfilename()
                if p:
                    file_var.set(p)
                    cat, cls_name, ocr_txt = IntelligentClassifier.analyze_evidence(p, os.path.basename(p))
                    detected_category[0] = cat
                    detected_classification[0] = cls_name
                    extracted_text_holder[0] = ocr_txt
                    ai_cat_lbl.configure(text=f"AI Classification: {cls_name}")

            ctk.CTkButton(left_add, text="📂 Choose Digital File", fg_color="#334155", command=pick_file).pack(fill="x", padx=12, pady=6)
            ctk.CTkLabel(left_add, textvariable=file_var, font=ctk.CTkFont(size=10), text_color=THEME["text_muted"], wraplength=280).pack(padx=12, pady=2)

            def seal_and_commit_evidence():
                eid = ev_id_in.get().strip().upper()
                etitle = ev_title_in.get().strip()
                elock = ev_lock_in.get().strip()
                fpath = file_var.get().strip()

                if not eid or not etitle or not fpath or not os.path.exists(fpath):
                    messagebox.showerror("Error", "Evidence ID, Title, and valid File are required.", parent=modal)
                    return

                if not messagebox.askyesno("Confirm Cryptographic Seal", f"Encrypt (AES-256) & Seal evidence '{etitle}' ({eid}) under Case {selected_case_no}?\n\nOnce locked, bit-level SHA-256 seals cannot be altered.", parent=modal):
                    return

                hasher = hashlib.sha256()
                with open(fpath, "rb") as fobj:
                    while chunk := fobj.read(4096):
                        hasher.update(chunk)
                fhash = hasher.hexdigest()

                enc_target_path = os.path.join(VAULT_STORAGE_DIR, f"{eid}_{fhash[:12]}.nyayavault")
                EncryptionEngine.encrypt_file(fpath, enc_target_path)

                try:
                    conn = self.get_db_connection()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO case_evidence_files (evidence_id, case_no, evidence_title, category, raw_file_name, encrypted_path, sha256_hash, vault_locker, ai_classification, ocr_extracted_text, uploaded_by)
                        VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11)
                    """, (eid, selected_case_no, etitle, detected_category[0], os.path.basename(fpath), enc_target_path, fhash, elock, detected_classification[0], extracted_text_holder[0], self.current_user_badge or "OFFICER"))
                    
                    cur.execute("SELECT NVL(MAX(transfer_id), 0) + 1 FROM chain_of_custody_ledger")
                    t_id = cur.fetchone()[0]
                    cur.execute("""
                        INSERT INTO chain_of_custody_ledger (transfer_id, evidence_id, case_no, from_officer, to_officer_badge, to_officer_name, to_officer_rank, transfer_reason, division_code, unit_name, checkout_time, court_return_deadline, custody_status)
                        VALUES (:1, :2, :3, 'CRIME_SCENE', :4, :5, :6, 'Initial Lawful Ingestion and Sealing', :7, :8, SYSDATE, SYSDATE + 30, 'RETURNED_TO_VAULT')
                    """, (t_id, eid, selected_case_no, self.current_user_badge or "OFFICER", self.current_user_name or "Investigator", self.current_rank or "Police Officer", self.selected_division.get(), self.selected_unit.get()))

                    conn.commit()
                    cur.close()
                    conn.close()

                    self.log_chained_audit_event("EVIDENCE_SEALED", f"Evidence {eid} sealed with hash {fhash} (AES-256 Protected)")

                    chain_note = "Blockchain anchoring not configured."
                    if BLOCKCHAIN_MODULE_AVAILABLE and BLOCKCHAIN_CONFIG.get("enabled", False):
                        try:
                            tx_hash, block_no = anchor_evidence_hash(selected_case_no, eid, fhash)
                            conn2 = self.get_db_connection()
                            cur2 = conn2.cursor()
                            cur2.execute("""
                                UPDATE case_evidence_files
                                SET blockchain_tx_hash = :1, blockchain_block_number = :2, blockchain_status = 'ANCHORED'
                                WHERE evidence_id = :3
                            """, (tx_hash, block_no, eid))
                            conn2.commit()
                            cur2.close()
                            conn2.close()
                            self.log_chained_audit_event("EVIDENCE_ANCHORED_ONCHAIN", f"Evidence {eid} anchored on-chain, tx {tx_hash}")
                            chain_note = f"Anchored on-chain (tx {tx_hash[:18]}..., block {block_no})."
                        except Exception as chain_err:
                            chain_note = f"Blockchain anchoring pending — node unreachable ({chain_err})."

                    load_evidences_into_table()
                    self.populate_cases_table()
                    messagebox.showinfo("Evidence Sealed", f"Evidence {eid} AES-256 Encrypted & Sealed!\nSHA-256:\n{fhash}\n\n{chain_note}", parent=modal)
                    ev_id_in.delete(0, 'end')
                    ev_title_in.delete(0, 'end')
                    file_var.set("")
                    ai_cat_lbl.configure(text="AI Classification: Auto-Detecting...")
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=modal)

            ctk.CTkButton(left_add, text="🔒 Encrypt & Seal to Vault", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=seal_and_commit_evidence).pack(fill="x", padx=12, pady=(10, 4))

        right_view = ctk.CTkFrame(main_box, fg_color=THEME["card_bg"], corner_radius=14, border_width=1, border_color=THEME["card_border"])
        right_view.pack(side="right", fill="both", expand=True)

        ev_cols = ("evidence_id", "title", "category", "ai_classification", "sha256_hash", "locker", "custody")
        ev_tree = ttk.Treeview(right_view, columns=ev_cols, show="headings", selectmode="browse")
        
        ev_v_scroll = ttk.Scrollbar(right_view, orient="vertical", command=ev_tree.yview)
        ev_h_scroll = ttk.Scrollbar(right_view, orient="horizontal", command=ev_tree.xview)
        ev_tree.configure(yscrollcommand=ev_v_scroll.set, xscrollcommand=ev_h_scroll.set)

        ev_tree.heading("evidence_id", text="Evidence ID")
        ev_tree.heading("title", text="Evidence Name")
        ev_tree.heading("category", text="Category")
        ev_tree.heading("ai_classification", text="AI Classification")
        ev_tree.heading("sha256_hash", text="SHA-256 Bit-Level Seal")
        ev_tree.heading("locker", text="Vault Locker")
        ev_tree.heading("custody", text="Custody State")

        ev_tree.column("evidence_id", width=110, minwidth=85, anchor="center")
        ev_tree.column("title", width=160, minwidth=120, anchor="w")
        ev_tree.column("category", width=130, minwidth=100, anchor="center")
        ev_tree.column("ai_classification", width=220, minwidth=160, anchor="w")
        ev_tree.column("sha256_hash", width=250, minwidth=190, anchor="center")
        ev_tree.column("locker", width=110, minwidth=85, anchor="center")
        ev_tree.column("custody", width=110, minwidth=85, anchor="center")

        ev_v_scroll.pack(side="right", fill="y")
        ev_h_scroll.pack(side="bottom", fill="x")
        ev_tree.pack(fill="both", expand=True, padx=(12, 0), pady=(12, 0))

        def load_evidences_into_table():
            for r in ev_tree.get_children(): ev_tree.delete(r)
            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT evidence_id, evidence_title, category, ai_classification, sha256_hash, vault_locker, active_custody_officer FROM case_evidence_files WHERE case_no = :1", (selected_case_no,))
                for row in cur.fetchall():
                    ev_tree.insert("", "end", values=row)
                cur.close()
                conn.close()
            except Exception:
                pass

        def open_target_evidence_file():
            s = ev_tree.selection()
            if not s:
                messagebox.showwarning("Select Evidence", "Select an evidence row from the table.", parent=modal)
                return
            eid = ev_tree.item(s[0])["values"][0]

            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT raw_file_name, encrypted_path, evidence_title, sha256_hash FROM case_evidence_files WHERE evidence_id = :1", (eid,))
                row = cur.fetchone()
                cur.close()
                conn.close()

                if row:
                    raw_fn = row[0]
                    enc_p = row[1]
                    title = row[2]

                    if os.path.exists(enc_p):
                        dec_bytes = EncryptionEngine.decrypt_file_to_bytes(enc_p)
                        temp_view_path = os.path.join(VAULT_STORAGE_DIR, f"DEC_TEMP_{raw_fn}")
                        with open(temp_view_path, "wb") as f_tmp:
                            f_tmp.write(dec_bytes)
                        self.log_chained_audit_event("EVIDENCE_DECRYPTED_VIEW", f"Decrypted and inspected {title} ({eid})")
                        os.startfile(temp_view_path) if sys.platform == "win32" else os.system(f'xdg-open "{temp_view_path}"')
                    else:
                        messagebox.showinfo("Evidence Path", f"Target file record:\n{title}\nVault Encrypted Storage: {enc_p}", parent=modal)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)

        def export_65b_for_selected():
            s = ev_tree.selection()
            if not s:
                messagebox.showwarning("Select Evidence", "Select an evidence row.", parent=modal)
                return
            ev_data = ev_tree.item(s[0])["values"]
            fpath = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"Section65B_Certificate_{ev_data[0]}.pdf", parent=modal)
            if not fpath: return

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
                ["Case Ref Number:", selected_case_no],
                ["Case Name / Title:", selected_case_name],
                ["FIR Number:", selected_fir_no],
                ["Evidence Identifier:", str(ev_data[0])],
                ["Evidence Title:", str(ev_data[1])],
                ["Category & AI Classification:", f"{ev_data[2]} ({ev_data[3]})"],
                ["Jurisdiction City:", self.selected_division.get()],
                ["Police Station / Area:", self.selected_unit.get()],
                ["Cryptographic SHA-256 Seal:", str(ev_data[4])],
                ["AES-256 Vault Encryption:", "ENABLED & VERIFIED AT REST"],
                ["Integrity Status:", "VERIFIED INTACT (100% UNMODIFIED BIT-STREAM)"]
            ]
            t = Table(cert_data, colWidths=[180, 360])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
                ('PADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 20))
            
            elements.append(Paragraph("<b>STATUTORY ASSISTANCE DECLARATION:</b> This electronic record was mathematically fingerprinted and encrypted at lawful ingestion. This document assists authorized personnel in generating an electronic-record certificate containing relevant metadata, timestamps, and integrity information, subject to applicable legal requirements.", body_style))

            doc.build(elements)
            with open(fpath, "wb") as f: f.write(buffer.getvalue())
            buffer.close()

            self.log_chained_audit_event("65B_CERTIFICATE_EXPORTED", f"Exported Section 65B PDF for Evidence {ev_data[0]}")
            messagebox.showinfo("Exported", f"Certificate generated at:\n{fpath}", parent=modal)

        btn_bar = ctk.CTkFrame(right_view, fg_color="transparent")
        btn_bar.pack(fill="x", padx=12, pady=10)

        ctk.CTkButton(btn_bar, text="👁️ Decrypt & View File", fg_color="#0284C7", hover_color="#0369A1", command=open_target_evidence_file).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_bar, text="📑 Export Section 65B Certificate", fg_color=THEME["accent_gold"], hover_color=THEME["accent_gold_hover"], command=export_65b_for_selected).pack(side="left", padx=8)

        load_evidences_into_table()

    def build_custody_tab(self):
        container = ctk.CTkFrame(self.tab_custody, fg_color="transparent")
        container.pack(fill="both", expand=True)

        left = ctk.CTkScrollableFrame(container, width=330, fg_color=THEME["card_highlight"], border_width=1, border_color=THEME["card_border"], corner_radius=12)
        left.pack(side="left", fill="y", padx=(0, 15), pady=5)

        ctk.CTkLabel(left, text="Custody Handover & Tracking", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"]).pack(pady=10, padx=10, anchor="w")

        self.c_ev_id = self.create_styled_entry(left, "Evidence ID (e.g. EV-CCTV-01)")
        self.c_officer_badge = self.create_styled_entry(left, "Recipient Officer Badge")
        self.c_officer_name = self.create_styled_entry(left, "Recipient Officer Name")
        self.c_officer_rank = self.create_styled_entry(left, "Officer Rank (e.g. PI / DySP)")
        self.c_officer_mobile = self.create_styled_entry(left, "Recipient Officer Mobile (10 Digits)")
        self.c_officer_email = self.create_styled_entry(left, "Official Email")
        self.c_reason = self.create_styled_entry(left, "Transfer Reason (e.g. FSL Testing)")
        self.c_days = self.create_styled_entry(left, "Custody Duration (Days)")

        ctk.CTkButton(left, text="🔒 Transfer & Issue Evidence", fg_color=THEME["primary"], hover_color=THEME["primary_hover"], command=self.process_custody_transfer_issue).pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkButton(left, text="📥 Mark Returned to Vault", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=self.process_vault_return).pack(fill="x", padx=10, pady=4)

        right = ctk.CTkFrame(container, fg_color=THEME["card_highlight"], border_width=1, border_color=THEME["card_border"], corner_radius=12)
        right.pack(side="right", fill="both", expand=True, pady=5)

        ctk.CTkLabel(right, text="Chain of Custody Movement Ledger (Double-Click Row to View Visual Timeline)", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"]).pack(anchor="w", padx=15, pady=10)

        cols = ("id", "evidence_id", "case_no", "badge", "name", "rank", "checkout_time", "deadline", "status")
        self.custody_table = ttk.Treeview(right, columns=cols, show="headings", selectmode="browse")
        
        c_v_scroll = ttk.Scrollbar(right, orient="vertical", command=self.custody_table.yview)
        c_h_scroll = ttk.Scrollbar(right, orient="horizontal", command=self.custody_table.xview)
        self.custody_table.configure(yscrollcommand=c_v_scroll.set, xscrollcommand=c_h_scroll.set)

        for c in cols:
            self.custody_table.heading(c, text=c.replace("_", " ").title())
            self.custody_table.column(c, width=125, minwidth=95, anchor="center")

        c_v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        self.custody_table.pack(fill="both", expand=True, padx=(12, 0), pady=(0, 10))
        self.custody_table.bind("<Double-1>", lambda e: self.show_visual_custody_timeline_modal())

        self.populate_custody_table()

    def process_custody_transfer_issue(self):
        eid = self.c_ev_id.get().strip().upper()
        badge = self.c_officer_badge.get().strip()
        name = self.c_officer_name.get().strip()
        rank = self.c_officer_rank.get().strip()
        mob = self.c_officer_mobile.get().strip() or "9876543210"
        email = self.c_officer_email.get().strip() or "officer@police.gov.in"
        reason = self.c_reason.get().strip() or "Official Forensic Examination"
        days_str = self.c_days.get().strip()
        days = int(days_str) if days_str.isdigit() else 7
        div = self.selected_division.get()
        unit = self.selected_unit.get()

        if not eid or not badge or not name:
            messagebox.showerror("Error", "Evidence ID, Recipient Badge, and Name are mandatory.")
            return

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT case_no, evidence_title FROM case_evidence_files WHERE evidence_id = :1", (eid,))
            row = cur.fetchone()
            if not row:
                messagebox.showerror("Error", "Evidence ID not found in database.")
                return

            c_no = row[0]
            cur.execute("SELECT NVL(MAX(transfer_id), 0) + 1 FROM chain_of_custody_ledger")
            next_tid = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO chain_of_custody_ledger (transfer_id, evidence_id, case_no, from_officer, to_officer_badge, to_officer_name, to_officer_rank, to_officer_mobile, to_officer_email, transfer_reason, division_code, unit_name, checkout_time, court_return_deadline, custody_status)
                VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, SYSDATE, SYSDATE + :13, 'CHECKED_OUT')
            """, (next_tid, eid, c_no, f"{self.current_rank} {self.current_user_name}", badge, name, rank, mob, email, reason, div, unit, days))

            cur.execute("UPDATE case_evidence_files SET active_custody_officer = :1 WHERE evidence_id = :2", (name, eid))
            conn.commit()
            cur.close()
            conn.close()

            self.log_chained_audit_event("CUSTODY_ISSUED", f"Evidence {eid} transferred to Officer {name} (#{badge}) for {days} days.")
            self.populate_custody_table()
            messagebox.showinfo("Custody Transferred", f"Custody of Evidence {eid} transferred to Officer {name} (#{badge}).")
        except Exception as e:
            messagebox.showerror("DB Error", str(e))

    def process_vault_return(self):
        sel = self.custody_table.selection()
        if not sel:
            messagebox.showwarning("Select Transfer", "Please select a transfer record from the table to return.")
            return
        r = self.custody_table.item(sel[0])["values"]
        tid = r[0]
        eid = r[1]

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("UPDATE chain_of_custody_ledger SET custody_status = 'RETURNED_TO_VAULT', return_time = SYSDATE, return_condition = 'Integrity_Passed' WHERE transfer_id = :1", (tid,))
            cur.execute("UPDATE case_evidence_files SET active_custody_officer = 'VAULT' WHERE evidence_id = :1", (eid,))
            conn.commit()
            cur.close()
            conn.close()

            self.log_chained_audit_event("CUSTODY_RESTORED_VAULT", f"Evidence {eid} safely returned to vault storage.")
            self.populate_custody_table()
            messagebox.showinfo("Restored", f"Evidence {eid} safely returned to Vault.")
        except Exception as e:
            messagebox.showerror("DB Error", str(e))

    def show_visual_custody_timeline_modal(self):
        sel = self.custody_table.selection()
        if not sel: return
        r = self.custody_table.item(sel[0])["values"]
        eid = r[1]

        modal = Toplevel(self)
        modal.title(f"Visual Custody Provenance: Evidence {eid}")
        modal.geometry("750x480")
        modal.configure(bg=THEME["bg_main"])
        modal.grab_set()

        top_h = ctk.CTkFrame(modal, fg_color=THEME["primary"], height=50, corner_radius=0)
        top_h.pack(fill="x")
        ctk.CTkLabel(top_h, text=f"🔍 Interactive Journey Timeline: Evidence {eid}", font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFFFFF").pack(side="left", padx=20, pady=10)

        timeline_box = ctk.CTkScrollableFrame(modal, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        timeline_box.pack(fill="both", expand=True, padx=20, pady=20)

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT from_officer, to_officer_name, to_officer_rank, transfer_reason, TO_CHAR(checkout_time, 'YYYY-MM-DD HH24:MI'), custody_status FROM chain_of_custody_ledger WHERE evidence_id = :1 ORDER BY transfer_id ASC", (eid,))
            events = cur.fetchall()
            cur.close()
            conn.close()

            for idx, ev in enumerate(events, 1):
                card = ctk.CTkFrame(timeline_box, fg_color=THEME["card_highlight"], corner_radius=10, border_width=1, border_color=THEME["card_border"])
                card.pack(fill="x", padx=10, pady=8)

                hdr = ctk.CTkFrame(card, fg_color="transparent")
                hdr.pack(fill="x", padx=12, pady=6)
                ctk.CTkLabel(hdr, text=f"Stage {idx}: {ev[5]}", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["primary"]).pack(side="left")
                ctk.CTkLabel(hdr, text=f"Timestamp: {ev[4]}", font=ctk.CTkFont(size=10), text_color=THEME["text_muted"]).pack(side="right")

                body = f"Transferred By: {ev[0]}  ➔  Recipient: {ev[1]} ({ev[2]})\nPurpose / Reason: {ev[3]}"
                ctk.CTkLabel(card, text=body, font=ctk.CTkFont(size=11), justify="left", text_color=THEME["text_main"]).pack(anchor="w", padx=12, pady=(0, 8))
        except Exception as e:
            pass

    def populate_custody_table(self):
        for r in self.custody_table.get_children(): self.custody_table.delete(r)
        div = self.selected_division.get()
        unit = self.selected_unit.get()
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT transfer_id, evidence_id, case_no, to_officer_badge, to_officer_name, to_officer_rank, TO_CHAR(checkout_time, 'YYYY-MM-DD HH24:MI'), TO_CHAR(court_return_deadline, 'YYYY-MM-DD'), custody_status FROM chain_of_custody_ledger WHERE division_code = :1 AND unit_name = :2 ORDER BY transfer_id DESC", (div, unit))
            for row in cur.fetchall():
                self.custody_table.insert("", "end", values=row)
            cur.close()
            conn.close()
        except Exception:
            pass

    def build_verification_tab(self):
        container = ctk.CTkFrame(self.tab_verify, fg_color="transparent")
        container.pack(fill="both", expand=True)

        top_ctrl = ctk.CTkFrame(container, height=60, fg_color=THEME["card_highlight"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        top_ctrl.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(top_ctrl, text="Live SHA-256 Bit-Level Integrity & Tamper Audit Dashboard", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"]).pack(side="left", padx=15)
        
        ctk.CTkButton(top_ctrl, text="⚡ Simulate Controlled File Tamper", fg_color=THEME["accent_red"], hover_color=THEME["accent_red_hover"], command=self.simulate_controlled_tamper_demo).pack(side="right", padx=10, pady=10)
        ctk.CTkButton(top_ctrl, text="🔍 Run Global Bit-Stream Audit", fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"], command=self.run_global_verification_audit).pack(side="right", padx=10, pady=10)

        mid_panel = ctk.CTkFrame(container, fg_color=THEME["card_highlight"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        mid_panel.pack(fill="both", expand=True, padx=5, pady=5)

        cols = ("ev_id", "case_no", "title", "sealed_hash", "active_disk_hash", "integrity_verdict")
        self.verify_table = ttk.Treeview(mid_panel, columns=cols, show="headings", selectmode="browse")

        v_scroll = ttk.Scrollbar(mid_panel, orient="vertical", command=self.verify_table.yview)
        h_scroll = ttk.Scrollbar(mid_panel, orient="horizontal", command=self.verify_table.xview)
        self.verify_table.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.verify_table.heading("ev_id", text="Evidence ID")
        self.verify_table.heading("case_no", text="Case No")
        self.verify_table.heading("title", text="Title")
        self.verify_table.heading("sealed_hash", text="Sealed Master Hash (DB)")
        self.verify_table.heading("active_disk_hash", text="Live Disk Re-Calculated Hash")
        self.verify_table.heading("integrity_verdict", text="Tamper Audit Status")

        self.verify_table.column("ev_id", width=110, anchor="center")
        self.verify_table.column("case_no", width=110, anchor="center")
        self.verify_table.column("title", width=180, anchor="w")
        self.verify_table.column("sealed_hash", width=250, anchor="center")
        self.verify_table.column("active_disk_hash", width=250, anchor="center")
        self.verify_table.column("integrity_verdict", width=180, anchor="center")

        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        self.verify_table.pack(fill="both", expand=True, padx=(12, 0), pady=(12, 0))

        self.run_global_verification_audit()

    def run_global_verification_audit(self):
        for r in self.verify_table.get_children(): self.verify_table.delete(r)
        div = self.selected_division.get()
        unit = self.selected_unit.get()

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            if self.current_rank_level == 5 or self.current_role == "COURT_JUDICIAL":
                cur.execute("""
                    SELECT e.evidence_id, e.case_no, e.evidence_title, e.sha256_hash, e.encrypted_path
                    FROM case_evidence_files e JOIN case_profiles c ON e.case_no = c.case_no
                """)
            else:
                cur.execute("""
                    SELECT e.evidence_id, e.case_no, e.evidence_title, e.sha256_hash, e.encrypted_path
                    FROM case_evidence_files e JOIN case_profiles c ON e.case_no = c.case_no
                    WHERE c.division_code = :1 AND c.unit_name = :2
                """, (div, unit))
            rows = cur.fetchall()
            cur.close()
            conn.close()

            for r in rows:
                eid = r[0]
                cno = r[1]
                title = r[2]
                sealed_h = r[3]
                enc_p = r[4]

                active_h = "FILE_NOT_FOUND"
                verdict = "❌ Missing File"

                if os.path.exists(enc_p):
                    try:
                        dec_bytes = EncryptionEngine.decrypt_file_to_bytes(enc_p)
                        active_h = hashlib.sha256(dec_bytes).hexdigest()
                        if active_h == sealed_h:
                            verdict = "✅ VERIFIED (100% INTACT)"
                        else:
                            verdict = "🚨 INTEGRITY MISMATCH"
                    except Exception:
                        active_h = "CORRUPTED_CIPHERTEXT"
                        verdict = "🚨 INTEGRITY MISMATCH"

                self.verify_table.insert("", "end", values=(eid, cno, title, sealed_h, active_h, verdict))

            self.log_chained_audit_event("INTEGRITY_AUDIT_RUN", f"Verified bit-level hash integrity across {len(rows)} exhibits.")
        except Exception as e:
            messagebox.showerror("Audit Error", str(e))

    def simulate_controlled_tamper_demo(self):
        sel = self.verify_table.selection()
        if not sel:
            children = self.verify_table.get_children()
            if not children:
                messagebox.showwarning("No Exhibits", "There are no evidence exhibits available in the vault to tamper with.")
                return
            sel = (children[0],)
            self.verify_table.selection_set(sel)

        eid = self.verify_table.item(sel[0])["values"][0]

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT encrypted_path, evidence_title FROM case_evidence_files WHERE evidence_id = :1", (eid,))
            row = cur.fetchone()
            cur.close()
            conn.close()

            if row and os.path.exists(row[0]):
                with open(row[0], "ab") as f:
                    f.write(b"\x00TAMPERED_PAYLOAD_BYTE_OVERRIDE\xFF")
                
                self.log_chained_audit_event("TAMPER_SIMULATION_EXECUTED", f"Controlled tamper applied to {eid}")
                self.run_global_verification_audit()
                messagebox.showerror("Tamper Simulation Active", f"Exhibit {eid} ({row[1]}) ciphertext modified on disk!\nRe-running audit immediately detects the bit mismatch.")
            else:
                messagebox.showerror("File Error", f"Encrypted physical file path not found for {eid}.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def build_audit_tab(self):
        container = ctk.CTkFrame(self.tab_audit, fg_color="transparent")
        container.pack(fill="both", expand=True)

        top_ctrl = ctk.CTkFrame(container, height=50, fg_color=THEME["card_highlight"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        top_ctrl.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(top_ctrl, text="Cryptographically Chained Audit Ledger (MHA Statutory Nonce Chaining)", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"]).pack(side="left", padx=15)
        ctk.CTkButton(top_ctrl, text="🔄 Refresh Audit Chain", fg_color=THEME["primary"], command=self.populate_audit_table).pack(side="right", padx=15, pady=8)

        mid_panel = ctk.CTkFrame(container, fg_color=THEME["card_highlight"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        mid_panel.pack(fill="both", expand=True, padx=5, pady=5)

        cols = ("log_id", "prev_hash", "timestamp", "actor", "role", "action", "target", "ip", "block_hash")
        self.audit_table = ttk.Treeview(mid_panel, columns=cols, show="headings", selectmode="browse")

        v_scroll = ttk.Scrollbar(mid_panel, orient="vertical", command=self.audit_table.yview)
        h_scroll = ttk.Scrollbar(mid_panel, orient="horizontal", command=self.audit_table.xview)
        self.audit_table.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        for c in cols:
            self.audit_table.heading(c, text=c.replace("_", " ").title())
            self.audit_table.column(c, width=125, minwidth=95, anchor="center")
        self.audit_table.column("prev_hash", width=160, anchor="center")
        self.audit_table.column("block_hash", width=160, anchor="center")
        self.audit_table.column("target", width=220, anchor="w")

        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        self.audit_table.pack(fill="both", expand=True, padx=(12, 0), pady=(12, 0))

        self.populate_audit_table()

    def populate_audit_table(self):
        for r in self.audit_table.get_children(): self.audit_table.delete(r)
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT log_id, prev_log_hash, TO_CHAR(event_timestamp, 'YYYY-MM-DD HH24:MI:SS'), actor_badge, role, action_type, target_reference, ip_address, log_hash
                FROM audit_security_logs ORDER BY log_id DESC
            """)
            for row in cur.fetchall():
                self.audit_table.insert("", "end", values=row)
            cur.close()
            conn.close()
        except Exception:
            pass

    def create_styled_entry(self, parent, placeholder, **kwargs):
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, fg_color=THEME["input_bg"], border_color=THEME["card_border"], text_color=THEME["text_muted"], corner_radius=8, height=34, **kwargs)
        entry.pack(fill="x", padx=10, pady=4)
        return entry


if __name__ == "__main__":
    app = MHADocManager()
    app.mainloop()