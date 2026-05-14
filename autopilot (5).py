# ============================================================
# AutoPilot — Messenger Automation
# ============================================================
import customtkinter as ctk
import pyautogui as py
import pyperclip
import time
import random
import cv2
import numpy as np
import threading
import hashlib
import uuid
import platform
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone
import json
import os
import webbrowser

# ============================================================
# Firebase
# ============================================================
import sys

def resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

cred = credentials.Certificate(resource_path("serviceAccountKey.json"))
firebase_admin.initialize_app(cred)
db = firestore.client()

# ============================================================
# Local key save/load
# ============================================================
KEY_FILE = os.path.join(os.environ["APPDATA"], "autopilot_key.json")

def save_key(key):
    with open(KEY_FILE, "w") as f:
        json.dump({"key": key}, f)

def load_saved_key():
    try:
        with open(KEY_FILE, "r") as f:
            return json.load(f).get("key")
    except:
        return None

def delete_saved_key():
    try:
        os.remove(KEY_FILE)
    except:
        pass

# ============================================================
# Auto-save messages
# ============================================================
def _msg_file(key):
    key_hash = hashlib.md5(key.encode()).hexdigest()[:12]
    return os.path.join(os.environ["APPDATA"], f"autopilot_msg_{key_hash}.json")

def save_messages(key, msgs, break_t, wait_t):
    with open(_msg_file(key), "w") as f:
        json.dump({"msgs": msgs, "break": break_t, "wait": wait_t}, f)

def load_messages(key):
    try:
        with open(_msg_file(key), "r") as f:
            return json.load(f)
    except:
        return {}

# ============================================================
# Hardware ID
# ============================================================
def get_hardware_id():
    raw = platform.node() + str(uuid.getnode())
    return hashlib.sha256(raw.encode()).hexdigest()[:32]

# ============================================================
# License check
# ============================================================
def check_license(key):
    try:
        doc = db.collection("licenses").document(key).get()
        if not doc.exists:
            return False, "Key পাওয়া যায়নি!", {}
        data = doc.to_dict()
        if not data.get("active", False):
            return False, "Key বন্ধ করা হয়েছে!", {}

        license_info = {"type": "lifetime", "remaining_hours": None, "user": data.get("user", "User")}
        if data.get("trial", False):
            license_info["type"] = "trial"
            created = data.get("created_at")
            if created:
                now = datetime.now(timezone.utc)
                diff = (now - created).total_seconds() / 3600
                if diff > 48:
                    db.collection("licenses").document(key).update({"active": False})
                    return False, "Trial শেষ হয়েছে!", {}
                license_info["remaining_hours"] = round(48 - diff, 1)

        hw_id = get_hardware_id()
        saved_hw = data.get("hardware_id")
        if saved_hw is None:
            db.collection("licenses").document(key).update({"hardware_id": hw_id})
            return True, "Activated!", license_info
        elif saved_hw != hw_id:
            return False, "এই key অন্য PC তে activate করা!", {}
        return True, "OK", license_info
    except Exception as e:
        return False, f"Error: {e}", {}

# ============================================================
# Template load
# ============================================================
template = cv2.imread(resource_path("template.png"), cv2.IMREAD_GRAYSCALE)

# ============================================================
# Globals
# ============================================================
running = False
total_messages = 0
log_callback = None
current_key = [None]
current_license_info = [{}]
start_time_global = [None]

def ts():
    return datetime.now().strftime("%H:%M:%S")

def log(msg):
    if log_callback:
        log_callback(f"[{ts()}]  {msg}")

# ============================================================
# Automation
# ============================================================
def random_sleep(mn, mx):
    time.sleep(random.uniform(mn, mx))

def is_unread_empty():
    screenshot = py.screenshot(region=(0, 150, 140, 500))
    img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > 0.7

def wait_for_messenger(wait_sec):
    reloading = False
    while True:
        pixel = py.pixel(60, 244)
        if pixel == (36, 37, 38):
            if not reloading:
                log("⚠️  Messenger reload হচ্ছে — অপেক্ষায়...")
            reloading = True
            time.sleep(1)
        else:
            if reloading:
                log(f"✅  Reload শেষ — Unread click, {wait_sec}s অপেক্ষা...")
                py.click(45, 221)
                time.sleep(wait_sec)
            return True

def minimize_and_reload(wait_sec):
    log("📭  Unread খালি — Window minimize করছি...")
    py.click(768, 33)
    time.sleep(2)
    log("🔄  Reload button click করছি...")
    py.click(155, 104)
    time.sleep(5)
    while True:
        pixel = py.pixel(60, 244)
        if pixel != (36, 37, 38):
            break
        time.sleep(1)
    log(f"✅  Reload শেষ — Unread click, {wait_sec}s অপেক্ষায়...")
    py.click(45, 221)
    time.sleep(wait_sec)

def auto_msg(messages, wait_sec, counter_label):
    global total_messages, running

    if is_unread_empty():
        minimize_and_reload(wait_sec)
        return False

    py.click(45, 221)
    random_sleep(3, 5)

    MSG_BOX_X = 284
    MSG_BOX_Y = 1061

    for i in range(0, 10):
        if not running:
            return False
        try:
            if is_unread_empty():
                minimize_and_reload(wait_sec)
                return False

            wait_for_messenger(wait_sec)

            py.click(60, 243)
            random_sleep(0.8, 1.2)

            py.click(MSG_BOX_X, MSG_BOX_Y)
            time.sleep(1)
            py.click(MSG_BOX_X, MSG_BOX_Y)
            time.sleep(0.5)

            text = random.choice(messages)
            pyperclip.copy(text)
            py.hotkey('ctrl', 'v')
            random_sleep(0.1, 0.2)
            py.press('enter')

            total_messages += 1
            counter_label.configure(text=str(total_messages))
            log(f"✉️   Message পাঠানো হয়েছে  (মোট: {total_messages})")

        except Exception:
            continue

    random_sleep(3, 6)
    return True

def run_automation(messages, break_sec, wait_sec, counter_label, status_label, start_btn, saved_key):
    global running
    start_time = time.time()
    last_check = time.time()
    start_time_global[0] = start_time

    log("🚀  Automation শুরু হয়েছে!")

    while running:
        if time.time() - last_check > 1800:
            ok, msg, _ = check_license(saved_key)
            if not ok:
                log(f"🚫  License check failed: {msg}")
                running = False
                break
            last_check = time.time()

        result = auto_msg(messages, wait_sec, counter_label)
        if result:
            elapsed = (time.time() - start_time) / 60
            if elapsed >= 2:
                log(f"⏸️   Break নিচ্ছি — {break_sec} সেকেন্ড...")
                time.sleep(break_sec)
                log("▶️   Break শেষ — আবার শুরু...")
                start_time = time.time()
        else:
            time.sleep(3)

    log("🛑  Automation বন্ধ হয়েছে।")
    status_label.configure(text="● OFFLINE", text_color="#EF4444")
    start_btn.configure(state="normal")
    start_time_global[0] = None

# ============================================================
# GUI
# ============================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG      = "#080810"
CARD    = "#0F0F1A"
BORDER  = "#1E1E2E"
ACCENT  = "#7C3AED"
ACCENT2 = "#A78BFA"
GREEN   = "#10B981"
RED     = "#EF4444"
TEXT    = "#F1F0FF"
SUBTEXT = "#6B6B8A"
LOG_BG  = "#06060F"
YELLOW  = "#F59E0B"

app = ctk.CTk()
app.title("AutoPilot")
app.configure(fg_color=BG)
app.resizable(False, False)

# ============================================================
# SPLASH SCREEN
# ============================================================
def build_splash():
    for w in app.winfo_children():
        w.destroy()
    app.geometry("420x280")

    outer = ctk.CTkFrame(app, fg_color=BG)
    outer.pack(fill="both", expand=True)

    ctk.CTkLabel(outer, text="✈  AutoPilot",
                  font=("Courier New", 32, "bold"), text_color=ACCENT2).pack(expand=True, pady=(60, 4))
    ctk.CTkLabel(outer, text="Messenger Automation",
                  font=("Courier New", 12), text_color=SUBTEXT).pack(pady=(0, 30))

    progress = ctk.CTkProgressBar(outer, width=300, fg_color=CARD, progress_color=ACCENT)
    progress.pack(pady=(0, 20))
    progress.set(0)

    status_lbl = ctk.CTkLabel(outer, text="Initializing...", font=("Courier New", 10), text_color=SUBTEXT)
    status_lbl.pack()

    def animate():
        steps = [(0.3, "Connecting to server..."), (0.6, "Checking license..."), (1.0, "Ready!")]
        for val, msg in steps:
            time.sleep(0.6)
            progress.set(val)
            status_lbl.configure(text=msg)
            app.update()
        time.sleep(0.4)
        saved = load_saved_key()
        if saved:
            ok, _, lic_info = check_license(saved)
            if ok:
                current_key[0] = saved
                current_license_info[0] = lic_info
                build_main_screen()
                return
        build_license_screen()

    threading.Thread(target=animate, daemon=True).start()

# ============================================================
# LICENSE SCREEN
# ============================================================
def build_license_screen():
    for w in app.winfo_children():
        w.destroy()
    app.geometry("420x370")

    outer = ctk.CTkFrame(app, fg_color=BG)
    outer.pack(fill="both", expand=True, padx=40, pady=30)

    logo = ctk.CTkFrame(outer, fg_color=CARD, corner_radius=12,
                         border_width=1, border_color=BORDER)
    logo.pack(fill="x", pady=(0, 20))

    ctk.CTkLabel(logo, text="✈  AutoPilot", font=("Courier New", 22, "bold"),
                  text_color=ACCENT2).pack(pady=(16, 4))
    ctk.CTkLabel(logo, text="Messenger Automation System", font=("Courier New", 10),
                  text_color=SUBTEXT).pack(pady=(0, 16))

    key_entry = ctk.CTkEntry(
        outer, width=340, height=44,
        placeholder_text="Enter License Key",
        font=("Courier New", 13),
        fg_color=CARD, border_color=ACCENT, border_width=1,
        text_color=TEXT, corner_radius=10
    )
    key_entry.pack(pady=(0, 10))

    err_label = ctk.CTkLabel(outer, text="", font=("Courier New", 11), text_color=RED)
    err_label.pack(pady=(0, 8))

    def activate():
        key = key_entry.get().strip()
        if not key:
            err_label.configure(text="⚠  Key দাও!")
            return
        err_label.configure(text="Verifying...", text_color=ACCENT2)
        app.update()
        ok, msg, lic_info = check_license(key)
        if ok:
            save_key(key)
            current_key[0] = key
            current_license_info[0] = lic_info
            build_main_screen()
        else:
            err_label.configure(text=f"✗  {msg}", text_color=RED)

    ctk.CTkButton(
        outer, text="ACTIVATE  →",
        width=340, height=42,
        font=("Courier New", 13, "bold"),
        fg_color=ACCENT, hover_color=ACCENT2,
        corner_radius=10, command=activate
    ).pack()

    ctk.CTkLabel(outer, text="Developed by AutoPilot Team",
                  font=("Courier New", 10), text_color=SUBTEXT).pack(pady=(12, 0))

# ============================================================
# MAIN SCREEN
# ============================================================
def build_main_screen():
    global log_callback, running

    for w in app.winfo_children():
        w.destroy()
    app.geometry("500x750")

    saved_data = load_messages(current_key[0])
    saved_msgs = saved_data.get("msgs", ["", ""])
    if len(saved_msgs) < 2:
        saved_msgs = ["", ""]

    # Fixed bottom
    bottom = ctk.CTkFrame(app, fg_color=BG)
    bottom.pack(side="bottom", fill="x", padx=16, pady=(4, 10))

    # WhatsApp button — fixed above START/STOP
    def open_whatsapp():
        webbrowser.open("https://wa.me/8801950815114")

    ctk.CTkButton(
        bottom, text="💬  WhatsApp Support",
        height=32, font=("Courier New", 10),
        fg_color="#25D366", hover_color="#128C7E",
        text_color="white", corner_radius=8,
        command=open_whatsapp
    ).pack(fill="x", pady=(0, 6))

    btn_row = ctk.CTkFrame(bottom, fg_color="transparent")
    btn_row.pack(fill="x")

    # Main content
    root = ctk.CTkFrame(app, fg_color=BG)
    root.pack(fill="both", expand=True, padx=16, pady=(12, 0))

    # Header
    hdr = ctk.CTkFrame(root, fg_color=CARD, corner_radius=12,
                        border_width=1, border_color=BORDER)
    hdr.pack(fill="x", pady=(0, 8))

    ctk.CTkLabel(hdr, text="✈  AutoPilot", font=("Courier New", 15, "bold"),
                  text_color=ACCENT2).pack(side="left", padx=14, pady=10)

    status_dot = ctk.CTkLabel(hdr, text="● OFFLINE",
                               font=("Courier New", 10, "bold"), text_color=RED)
    status_dot.pack(side="right", padx=(0, 12), pady=10)

    def logout():
        global running
        running = False
        current_key[0] = None
        current_license_info[0] = {}
        build_license_screen()

    ctk.CTkButton(hdr, text="Logout", width=65, height=26,
                   font=("Courier New", 9), fg_color=BORDER,
                   hover_color=RED, text_color=SUBTEXT,
                   corner_radius=6, command=logout).pack(side="right", padx=(0, 6), pady=10)

    lic_info = current_license_info[0]
    if lic_info.get("type") == "trial":
        remaining = lic_info.get("remaining_hours", 0)
        badge_text = f"⏳ {remaining}h"
        badge_color = YELLOW
    else:
        badge_text = "💎 Lifetime"
        badge_color = ACCENT2

    ctk.CTkLabel(hdr, text=badge_text, font=("Courier New", 9, "bold"),
                  text_color=badge_color).pack(side="right", padx=(0, 6), pady=10)

    # Stats row
    stats = ctk.CTkFrame(root, fg_color="transparent")
    stats.pack(fill="x", pady=(0, 8))

    sent_card = ctk.CTkFrame(stats, fg_color=CARD, corner_radius=10,
                               border_width=1, border_color=BORDER)
    sent_card.pack(side="left", expand=True, fill="x", padx=(0, 4))
    ctk.CTkLabel(sent_card, text="MESSAGES SENT", font=("Courier New", 8),
                  text_color=SUBTEXT).pack(pady=(8, 0))
    counter_lbl = ctk.CTkLabel(sent_card, text="0",
                                font=("Courier New", 20, "bold"), text_color=ACCENT2)
    counter_lbl.pack(pady=(0, 8))

    run_card = ctk.CTkFrame(stats, fg_color=CARD, corner_radius=10,
                             border_width=1, border_color=BORDER)
    run_card.pack(side="left", expand=True, fill="x", padx=(4, 0))
    ctk.CTkLabel(run_card, text="RUN TIME", font=("Courier New", 8),
                  text_color=SUBTEXT).pack(pady=(8, 0))
    timer_lbl = ctk.CTkLabel(run_card, text="00:00:00",
                              font=("Courier New", 20, "bold"), text_color=GREEN)
    timer_lbl.pack(pady=(0, 8))

    def update_timer():
        if start_time_global[0] and running:
            elapsed = int(time.time() - start_time_global[0])
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            timer_lbl.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        else:
            timer_lbl.configure(text="00:00:00")
        app.after(1000, update_timer)

    update_timer()

    # Welcome
    user_name = current_license_info[0].get("user", "User")
    welcome = ctk.CTkFrame(root, fg_color=CARD, corner_radius=10,
                            border_width=1, border_color=BORDER)
    welcome.pack(fill="x", pady=(0, 8))
    ctk.CTkLabel(welcome, text=f"👋  Welcome, {user_name}!",
                  font=("Courier New", 12, "bold"),
                  text_color=GREEN).pack(anchor="w", padx=14, pady=10)

    # Messages card
    msg_outer = ctk.CTkFrame(root, fg_color=CARD, corner_radius=12,
                               border_width=1, border_color=BORDER)
    msg_outer.pack(fill="x", pady=(0, 8))

    msg_header = ctk.CTkFrame(msg_outer, fg_color="transparent")
    msg_header.pack(fill="x", padx=14, pady=(10, 4))
    ctk.CTkLabel(msg_header, text="✉  MESSAGES", font=("Courier New", 9, "bold"),
                  text_color=SUBTEXT).pack(side="left")

    msg_entries = []
    msg_container = ctk.CTkFrame(msg_outer, fg_color="transparent")
    msg_container.pack(fill="x", padx=14, pady=(0, 8))

    def add_msg_box(saved_val=""):
        row = ctk.CTkFrame(msg_container, fg_color="transparent")
        row.pack(fill="x", pady=2)

        e = ctk.CTkEntry(
            row, height=34,
            placeholder_text=f"Message {len(msg_entries)+1}",
            font=("Courier New", 11),
            fg_color=BG, border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=8
        )
        e.pack(side="left", fill="x", expand=True, padx=(0, 6))
        if saved_val:
            e.insert(0, saved_val)

        def remove():
            if len(msg_entries) <= 1:
                return
            msg_entries.remove(e)
            row.destroy()

        ctk.CTkButton(row, text="🗑", width=34, height=34,
                       font=("Courier New", 12),
                       fg_color=BORDER, hover_color=RED,
                       text_color=RED, corner_radius=8,
                       command=remove).pack(side="right")
        msg_entries.append(e)

    ctk.CTkButton(msg_header, text="＋ Add", width=60, height=26,
                   font=("Courier New", 9), fg_color=ACCENT,
                   hover_color=ACCENT2, corner_radius=6,
                   command=lambda: add_msg_box()).pack(side="right")

    for m in saved_msgs:
        add_msg_box(m)

    # Timing + Log side by side
    middle = ctk.CTkFrame(root, fg_color="transparent")
    middle.pack(fill="x", pady=(0, 8))

    # Timing card
    time_card2 = ctk.CTkFrame(middle, fg_color=CARD, corner_radius=12,
                                border_width=1, border_color=BORDER,
                                width=170)
    time_card2.pack(side="left", fill="y", padx=(0, 4))
    time_card2.pack_propagate(False)

    ctk.CTkLabel(time_card2, text="⏱  TIMING", font=("Courier New", 9, "bold"),
                  text_color=SUBTEXT).pack(anchor="w", padx=12, pady=(10, 4))

    ctk.CTkLabel(time_card2, text="Break (sec)", font=("Courier New", 8),
                  text_color=SUBTEXT).pack(anchor="w", padx=12)
    break_entry = ctk.CTkEntry(time_card2, height=32,
                                font=("Courier New", 11),
                                fg_color=BG, border_color=BORDER, border_width=1,
                                text_color=TEXT, corner_radius=8)
    break_entry.pack(fill="x", padx=12, pady=(2, 10))
    if saved_data.get("break"):
        break_entry.insert(0, saved_data.get("break"))

    ctk.CTkLabel(time_card2, text="Wait (sec)", font=("Courier New", 8),
                  text_color=SUBTEXT).pack(anchor="w", padx=12)
    wait_entry = ctk.CTkEntry(time_card2, height=32,
                               font=("Courier New", 11),
                               fg_color=BG, border_color=BORDER, border_width=1,
                               text_color=TEXT, corner_radius=8)
    wait_entry.pack(fill="x", padx=12, pady=(2, 10))
    if saved_data.get("wait"):
        wait_entry.insert(0, saved_data.get("wait"))

    # Log card
    log_card = ctk.CTkFrame(middle, fg_color=LOG_BG, corner_radius=12,
                              border_width=1, border_color=BORDER)
    log_card.pack(side="left", fill="both", expand=True, padx=(4, 0))
    ctk.CTkLabel(log_card, text="📋  ACTIVITY LOG", font=("Courier New", 9, "bold"),
                  text_color=SUBTEXT).pack(anchor="w", padx=12, pady=(10, 4))

    log_box = ctk.CTkTextbox(log_card, height=150,
                              font=("Courier New", 9),
                              fg_color=LOG_BG, text_color="#9090BB",
                              border_width=0, corner_radius=0, wrap="word")
    log_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    log_box.configure(state="disabled")

    def add_log(msg):
        log_box.configure(state="normal")
        log_box.insert("end", msg + "\n")
        log_box.see("end")
        log_box.configure(state="disabled")

    log_callback = add_log

    # START / STOP
    def start():
        global running, total_messages
        if running:
            return
        msgs = [e.get() for e in msg_entries if e.get().strip()]
        if not msgs:
            add_log("⚠️  কমপক্ষে একটা message লেখো!")
            return
        try:
            b = int(break_entry.get() or 30)
            w = int(wait_entry.get() or 50)
        except ValueError:
            add_log("⚠️  সঠিক সংখ্যা দাও!")
            return

        save_messages(current_key[0], [e.get() for e in msg_entries],
                      break_entry.get(), wait_entry.get())

        running = True
        total_messages = 0
        counter_lbl.configure(text="0")
        status_dot.configure(text="● LIVE", text_color=GREEN)
        start_btn.configure(state="disabled")
        threading.Thread(
            target=run_automation,
            args=(msgs, b, w, counter_lbl, status_dot, start_btn, current_key[0]),
            daemon=True
        ).start()

    def stop():
        global running
        running = False

    start_btn = ctk.CTkButton(
        btn_row, text="▶  START",
        height=44, font=("Courier New", 13, "bold"),
        fg_color=ACCENT, hover_color=ACCENT2,
        corner_radius=10, command=start
    )
    start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))

    ctk.CTkButton(
        btn_row, text="■  STOP",
        height=44, font=("Courier New", 13, "bold"),
        fg_color=BG, hover_color=RED,
        border_width=1, border_color=RED,
        text_color=RED, corner_radius=10,
        command=stop
    ).pack(side="left", expand=True, fill="x", padx=(6, 0))


# START
build_splash()
app.mainloop()
