"""
LinkedIn Fleet Manager (Edge + Selenium).

IMPORTANT: LinkedIn's rules do not allow automated activity. Your account can be
limited or banned. Use only on an account you can afford to lose.
The browser profiles saved in %LOCALAPPDATA%\\LinkedInLikerBot contain your
LOGIN SESSION - never share or upload that folder.
"""
import json
import os
import random
import re
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

APPDATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "LinkedInLikerBot")
CONFIG_PATH = os.path.join(APPDATA_DIR, "bots_config.json")
REPORT_PATH = os.path.join(APPDATA_DIR, "daily_report.json")
os.makedirs(APPDATA_DIR, exist_ok=True)

MAX_TARGET = 25                      # hard daily-style cap per bot run
PROFILE_RE = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")
FILE_LOCK = threading.Lock()         # 3 bots write the report at once

DEFAULT_CONFIG = [
    {"id": 1, "name": "Primary Liker", "profile": "edge_bot_profile", "target": 8, "status": "Idle"},
    {"id": 2, "name": "Outreach Assistant", "profile": "edge_bot_profile_2", "target": 5, "status": "Idle"},
    {"id": 3, "name": "Engagement Scout", "profile": "edge_bot_profile_3", "target": 10, "status": "Idle"},
]


# ---------------- safe file + config helpers ----------------
def atomic_write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)            # never leaves a half-written file


def validate_config(cfg):
    """Keeps only well-formed entries; blocks path tricks like '..\\..\\x'."""
    clean, seen = [], set()
    if not isinstance(cfg, list):
        return [dict(b) for b in DEFAULT_CONFIG]
    for b in cfg:
        try:
            bid = int(b["id"])
            name = str(b["name"])[:40]
            profile = str(b["profile"])
            target = max(1, min(int(b["target"]), MAX_TARGET))
        except (KeyError, TypeError, ValueError):
            continue
        if bid in seen or not PROFILE_RE.match(profile):
            continue
        seen.add(bid)
        clean.append({"id": bid, "name": name, "profile": profile, "target": target, "status": "Idle"})
    return clean or [dict(b) for b in DEFAULT_CONFIG]


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return validate_config(json.load(f))
        except Exception:
            pass
    return [dict(b) for b in DEFAULT_CONFIG]


def append_report(bot_name, likes_done, status_note):
    today = datetime.now().strftime("%Y-%m-%d")
    with FILE_LOCK:
        report = {}
        if os.path.exists(REPORT_PATH):
            try:
                with open(REPORT_PATH, "r", encoding="utf-8") as f:
                    report = json.load(f)
            except Exception:
                report = {}
        report.setdefault(today, []).append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "bot": bot_name, "likes": likes_done, "status": status_note,
        })
        atomic_write_json(REPORT_PATH, report)


# ---------------- page scripts ----------------
JS_FORCE_SCROLL = """
window.scrollBy({ top: 650, behavior: 'smooth' });
if (document.documentElement) document.documentElement.scrollTop += 650;
if (document.body) document.body.scrollTop += 650;
var scrollables = document.querySelectorAll('main, div[tabindex="-1"], .scaffold-layout__main');
scrollables.forEach(function(el) { el.scrollTop += 650; });
"""

JS_CLICK_FIRST_LIKE = """
function findAndClickLike() {
    var allButtons = Array.from(document.querySelectorAll('button'));
    for (var i = 0; i < allButtons.length; i++) {
        var btn = allButtons[i];
        if (btn.closest('header') || btn.closest('.msg-overlay-container') ||
            btn.closest('.global-nav') || btn.closest('.reactions-menu')) { continue; }
        var ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
        var innerText = (btn.innerText || '').trim().toLowerCase();
        if (ariaLabel.includes('open reactions menu') || ariaLabel.includes('reaction options')) { continue; }
        var isLikeBtn = ariaLabel.includes('reaction button state: no reaction') ||
                        ariaLabel.includes('react like') || innerText === 'like' ||
                        btn.classList.contains('react-button__trigger');
        var isAlreadyLiked = (btn.getAttribute('aria-pressed') === 'true') ||
                             ariaLabel.includes('unlike') || innerText.includes('unlike') ||
                             btn.dataset.botLiked === "true";
        if (isLikeBtn && !isAlreadyLiked) {
            btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
            btn.dataset.botLiked = "true";
            ['mouseenter', 'mouseover', 'mousedown', 'mouseup', 'click'].forEach(function(evtType) {
                btn.dispatchEvent(new MouseEvent(evtType, { view: window, bubbles: true, cancelable: true }));
            });
            return { status: true, text: innerText, aria: ariaLabel };
        }
    }
    return { status: false };
}
return findAndClickLike();
"""


# ---------------- GUI ----------------
class BotDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LinkedIn Fleet Manager & Control Hub")
        self.geometry("960x650")
        self.configure(bg="#111827")
        self.bots_data = load_config()
        self.running_threads, self.stop_flags = {}, {}
        self.accepted_risk = False
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TProgressbar", thickness=8, troughcolor="#1f2937", background="#0a66c2")
        self.build_ui()

    # --- thread-safe UI: workers call these, they hop onto the main thread ---
    def ui(self, fn, *a, **kw):
        try:
            self.after(0, lambda: fn(*a, **kw))
        except Exception:
            pass

    def _btn(self, parent, text, bg, cmd):
        b = tk.Button(parent, text=text, font=("Segoe UI", 9, "bold"), bg=bg, fg="white",
                      relief="flat", padx=12, pady=4, command=cmd)
        b.pack(side=tk.RIGHT, padx=6, pady=12)
        return b

    def build_ui(self):
        top = tk.Frame(self, bg="#1e293b", height=60)
        top.pack(fill=tk.X, side=tk.TOP)
        tk.Label(top, text="LINKEDIN BOT COMMAND CENTER", font=("Segoe UI", 14, "bold"),
                 bg="#1e293b", fg="#38bdf8").pack(side=tk.LEFT, padx=20, pady=12)
        self._btn(top, "📊 Daily Report", "#374151", self.show_daily_report)
        self._btn(top, "🛑 Stop All", "#ef4444", self.stop_all_bots)
        self._btn(top, "▶ Start All", "#10b981", self.start_all_bots)

        content = tk.Frame(self, bg="#111827")
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        self.left_frame = tk.Frame(content, bg="#111827", width=520)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        right = tk.Frame(content, bg="#1f2937", width=400)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        tk.Label(right, text="LIVE ACTIVITY FEED", font=("Segoe UI", 10, "bold"),
                 bg="#1f2937", fg="#9ca3af").pack(anchor="w", padx=10, pady=8)
        self.log_box = tk.Text(right, bg="#0f172a", fg="#e2e8f0", font=("Consolas", 9), bd=0, padx=8, pady=8)
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.bot_widgets = {}
        for b in self.bots_data:
            self.create_bot_card(b)

    def create_bot_card(self, bot):
        card = tk.Frame(self.left_frame, bg="#1f2937", bd=1, relief="ridge")
        card.pack(fill=tk.X, pady=6, padx=2)
        head = tk.Frame(card, bg="#1f2937")
        head.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(head, text=f"Bot #{bot['id']}: {bot['name']}", font=("Segoe UI", 11, "bold"),
                 bg="#1f2937", fg="white").pack(side=tk.LEFT)
        badge = tk.Label(head, text="IDLE", font=("Segoe UI", 8, "bold"), bg="#374151", fg="#9ca3af", padx=8, pady=2)
        badge.pack(side=tk.RIGHT)

        row = tk.Frame(card, bg="#1f2937")
        row.pack(fill=tk.X, padx=12, pady=6)
        tk.Label(row, text=f"Target (1-{MAX_TARGET}):", font=("Segoe UI", 9), bg="#1f2937", fg="#cbd5e1").pack(side=tk.LEFT)
        entry = tk.Entry(row, width=4, font=("Segoe UI", 9), justify="center")
        entry.insert(0, str(bot["target"]))
        entry.pack(side=tk.LEFT, padx=(4, 15))
        prog = ttk.Progressbar(row, orient="horizontal", length=140, mode="determinate")
        prog.pack(side=tk.LEFT, padx=(0, 15))
        b_start = tk.Button(row, text="Start", font=("Segoe UI", 8, "bold"), bg="#0284c7", fg="white",
                            relief="flat", padx=10, command=lambda b=bot: self.start_single_bot(b["id"]))
        b_start.pack(side=tk.LEFT, padx=3)
        b_stop = tk.Button(row, text="Stop", font=("Segoe UI", 8, "bold"), bg="#4b5563", fg="white",
                           relief="flat", padx=10, state=tk.DISABLED, command=lambda b=bot: self.stop_single_bot(b["id"]))
        b_stop.pack(side=tk.LEFT, padx=3)
        self.bot_widgets[bot["id"]] = {"badge": badge, "target": entry, "progress": prog,
                                       "start_btn": b_start, "stop_btn": b_stop}

    # --- UI actions (main thread only) ---
    def _log(self, bot_id, message):
        prefix = f"[{datetime.now():%H:%M:%S}] " + (f"[Bot #{bot_id}]" if bot_id else "[SYSTEM]")
        self.log_box.insert(tk.END, f"{prefix} {message}\n")
        self.log_box.see(tk.END)

    def log(self, bot_id, message):
        self.ui(self._log, bot_id, message)

    def set_badge(self, b_id, text, color, bg):
        self.ui(lambda: self.bot_widgets[b_id]["badge"].config(text=text, fg=color, bg=bg))

    def set_progress(self, b_id, value):
        self.ui(lambda: self.bot_widgets[b_id]["progress"].configure(value=value))

    def set_buttons(self, b_id, running):
        def apply():
            w = self.bot_widgets[b_id]
            w["start_btn"].config(state=tk.DISABLED if running else tk.NORMAL)
            w["stop_btn"].config(state=tk.NORMAL if running else tk.DISABLED, bg="#ef4444" if running else "#4b5563")
        self.ui(apply)

    def confirm_risk(self):
        if self.accepted_risk:
            return True
        self.accepted_risk = messagebox.askokcancel(
            "Warning",
            "Automated liking is against LinkedIn's rules.\nYour account may be limited or banned.\n\nContinue?")
        return self.accepted_risk

    def start_single_bot(self, b_id):
        if b_id in self.running_threads and self.running_threads[b_id].is_alive():
            return
        bot = next((b for b in self.bots_data if b["id"] == b_id), None)
        if not bot or not self.confirm_risk():
            return
        try:
            target = int(self.bot_widgets[b_id]["target"].get().strip())
            if not 1 <= target <= MAX_TARGET:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", f"Bot #{b_id}: enter a whole number from 1 to {MAX_TARGET}.")
            return
        self.stop_flags[b_id] = False
        self.set_buttons(b_id, True)
        self.bot_widgets[b_id]["progress"].configure(value=0, maximum=target)
        th = threading.Thread(target=self.bot_worker, args=(bot, target), daemon=True)
        self.running_threads[b_id] = th
        th.start()

    def stop_single_bot(self, b_id):
        if b_id in self.stop_flags:
            self.stop_flags[b_id] = True
            self.log(b_id, "Halting execution requested...")
            self.bot_widgets[b_id]["stop_btn"].config(state=tk.DISABLED)

    def start_all_bots(self):
        for b in self.bots_data:
            self.start_single_bot(b["id"])

    def stop_all_bots(self):
        for b_id in list(self.bot_widgets):
            self.stop_single_bot(b_id)

    # ---------------- worker thread (never touches widgets directly) ----------------
    def bot_worker(self, bot, target):
        b_id = bot["id"]
        self.set_badge(b_id, "RUNNING", "white", "#0284c7")
        self.log(b_id, f"Initializing browser profile '{bot['profile']}'...")
        driver, liked = None, 0
        try:
            from selenium import webdriver
            from selenium.webdriver.edge.options import Options

            profile_dir = os.path.join(APPDATA_DIR, bot["profile"])
            os.makedirs(profile_dir, exist_ok=True)
            options = Options()
            options.add_argument(f"--user-data-dir={profile_dir}")
            for a in ("--no-first-run", "--no-default-browser-check", "--disable-fre", "--start-maximized"):
                options.add_argument(a)
            driver = webdriver.Edge(options=options)   # Selenium Manager finds the driver

            self.log(b_id, "Navigating to LinkedIn Feed...")
            driver.get("https://www.linkedin.com/feed/")
            time.sleep(5)

            scrolls = 0
            while liked < target and not self.stop_flags[b_id]:
                result = driver.execute_script(JS_CLICK_FIRST_LIKE)
                if result and result.get("status"):
                    liked += 1
                    scrolls = 0
                    self.set_progress(b_id, liked)
                    self.log(b_id, f"Liked post ({liked}/{target})")
                    if liked >= target:
                        break
                    delay = random.uniform(5.0, 8.5)
                    self.log(b_id, f"Resting {delay:.1f}s...")
                    for _ in range(int(delay * 2)):
                        if self.stop_flags[b_id]:
                            break
                        time.sleep(0.5)
                else:
                    scrolls += 1
                    self.log(b_id, f"No post visible. Scrolling ({scrolls})...")
                    driver.execute_script(JS_FORCE_SCROLL)
                    time.sleep(random.uniform(2.5, 3.5))
                    if scrolls > 25:
                        self.log(b_id, "Scroll limit reached.")
                        break

            if self.stop_flags[b_id]:
                self.set_badge(b_id, "STOPPED", "white", "#ef4444")
                self.log(b_id, f"Stopped by user. Completed {liked} likes.")
                append_report(bot["name"], liked, "Stopped Manually")
            else:
                self.set_badge(b_id, "COMPLETED", "white", "#10b981")
                self.log(b_id, f"Task complete. Total likes: {liked}")
                append_report(bot["name"], liked, "Completed")
        except Exception as e:
            self.set_badge(b_id, "ERROR", "white", "#dc2626")
            self.log(b_id, f"Error: {str(e)[:200]}")
            try:
                append_report(bot["name"], liked, f"Error: {str(e)[:30]}")
            except Exception:
                pass
        finally:
            if driver is not None:
                try:
                    driver.quit()          # original never closed the browser
                except Exception:
                    pass
            self.set_buttons(b_id, False)

    def show_daily_report(self):
        win = tk.Toplevel(self)
        win.title("Daily Automation Activity Report")
        win.geometry("640x450")
        win.configure(bg="#0f172a")
        tk.Label(win, text="DAILY AUTOMATION AUDIT LOG", font=("Segoe UI", 12, "bold"),
                 bg="#0f172a", fg="#38bdf8").pack(pady=12)
        tree = ttk.Treeview(win, columns=("date", "time", "bot", "likes", "status"), show="headings", height=14)
        for col, text, width, anchor in (("date", "Date", 90, "center"), ("time", "Time", 80, "center"),
                                         ("bot", "Bot Name", 150, "w"), ("likes", "Likes Count", 90, "center"),
                                         ("status", "Outcome", 180, "w")):
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor=anchor)
        tree.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        with FILE_LOCK:
            try:
                with open(REPORT_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for day, entries in sorted(data.items(), reverse=True):
                    for it in entries:
                        tree.insert("", tk.END, values=(day, it["timestamp"], it["bot"], it["likes"], it["status"]))
            except Exception:
                pass


if __name__ == "__main__":
    BotDashboard().mainloop()
