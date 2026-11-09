"""
Pharmacy data-entry helper (Windows, uses pywinauto).

Safety features
  * A pharmacist must type 'y' to approve EVERY submission (default = No).
  * PDF data must match what is on screen, otherwise nothing is submitted.
  * Buttons are checked to be enabled before clicking.
  * Rx numbers are validated; CSV report is protected from formula injection.
  * Use --demo-auto ONLY with demo_app.py (fake data) to skip the approval prompt.
"""
import argparse
import os
import re
import sys
import time
from datetime import datetime

import pandas as pd

APP_TITLE = "Pharmacy Prescription System"
TARGET_KEYWORD = "compound"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_FILE = os.path.join(BASE_DIR, "prescription.pdf")
MAX_PDF_BYTES = 5 * 1024 * 1024
TOTAL_ITEMS = 4
RX_PATTERN = re.compile(r"^[A-Za-z0-9\-]{1,20}$")


# ---------------- pure helper functions (testable without Windows) ----------------
def is_valid_rx(rx_id: str) -> bool:
    return bool(RX_PATTERN.match(rx_id or ""))


def csv_safe(value) -> str:
    """Stops Excel from running text that starts with = + - @ as a formula."""
    s = str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def parse_pdf_fields(full_text: str):
    rx = re.search(r"Rx Number:\s*([^\n\r]+)", full_text, re.IGNORECASE)
    med = re.search(r"Medicine:\s*([^\n\r]+)", full_text, re.IGNORECASE)
    return (rx.group(1).strip() if rx else "Unknown",
            med.group(1).strip() if med else "Unknown")


def extract_pdf_data(pdf_path):
    from pypdf import PdfReader  # imported only when needed
    if not pdf_path.lower().endswith(".pdf"):
        raise ValueError("Not a .pdf file")
    if os.path.getsize(pdf_path) > MAX_PDF_BYTES:
        raise ValueError("PDF is larger than 5 MB - refusing to read it")
    reader = PdfReader(pdf_path)
    text = "".join((page.extract_text() or "") for page in reader.pages[:5])
    rx_id, med_name = parse_pdf_fields(text)
    return text, rx_id, med_name


def ask_pharmacist(rx_id, med_name, auto):
    if auto:
        return True
    try:
        ans = input(f"PHARMACIST CHECK - submit {rx_id} | {med_name}? [y/N]: ").strip().lower()
    except EOFError:      # no keyboard attached -> treat as NOT approved
        return False
    return ans == "y"


# ---------------- UI helpers ----------------
def click_button(win, title, wait_enabled=True, timeout=5):
    btn = win.child_window(title=title, control_type="Button")
    btn.wait("exists visible", timeout=timeout)
    if wait_enabled:
        btn.wait("enabled", timeout=timeout)
    btn.click_input()
    time.sleep(0.4)


def read_screen_rx(win):
    rx_id, med_name = "Unknown", "Unknown"
    for d in win.descendants(control_type="Text"):
        t = d.window_text()
        if t.startswith("Rx Number:"):
            rx_id = t.replace("Rx Number:", "").strip()
        elif t.startswith("Medicine:"):
            med_name = t.replace("Medicine:", "").strip()
    return rx_id, med_name


def run_steps_and_submit(app, win):
    from pywinauto import keyboard
    click_button(win, "Start Prescription")
    click_button(win, "Complete Preparation Step")
    click_button(win, "Submit")
    time.sleep(0.6)
    try:   # close the "Success" box by its OK button; fall back to ENTER
        app.window(title="Success").child_window(title="OK", control_type="Button").click_input()
    except Exception:
        keyboard.send_keys("{ENTER}")
    time.sleep(0.4)


def log_row(log, mode, rx_id, med_name, status):
    log.append({
        "Processed_Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Mode": mode, "Rx_Number": csv_safe(rx_id),
        "Medicine_Name": csv_safe(med_name), "Status": status,
    })


def process_current(app, win, mode, log, auto, pdf_rx=None):
    """Handles the prescription currently on screen. Returns nothing."""
    rx_id, med_name = read_screen_rx(win)
    print(f"Checking: {rx_id} | {med_name}")

    if not is_valid_rx(rx_id):
        print("--> Invalid or unreadable Rx number. Skipping.")
        log_row(log, mode, rx_id, med_name, "Skipped - unreadable Rx")
        click_button(win, "Go Back", wait_enabled=False)
        return
    if pdf_rx is not None and pdf_rx != rx_id:
        print(f"--> MISMATCH: PDF says {pdf_rx}, screen shows {rx_id}. Nothing submitted.")
        log_row(log, mode, rx_id, med_name, f"Skipped - PDF mismatch ({pdf_rx})")
        click_button(win, "Go Back", wait_enabled=False)
        return
    if TARGET_KEYWORD not in med_name.lower():
        print("--> Non-target medicine. Going back.")
        log_row(log, mode, rx_id, med_name, "Skipped - not target")
        click_button(win, "Go Back", wait_enabled=False)
        return
    if not ask_pharmacist(rx_id, med_name, auto):
        print("--> Not approved by pharmacist. Going back.")
        log_row(log, mode, rx_id, med_name, "Not approved")
        click_button(win, "Go Back", wait_enabled=False)
        return

    run_steps_and_submit(app, win)
    log_row(log, mode, rx_id, med_name, "Submitted (pharmacist approved)")
    print(f"--> Processed {rx_id}")


def save_report(log):
    if not log:
        return
    name = os.path.join(BASE_DIR, f"eod_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    df = pd.DataFrame(log)
    df.to_csv(name, index=False)
    print("\n" + "=" * 50 + f"\nREPORT GENERATED: {name}\n" + "=" * 50)
    print(df[["Mode", "Rx_Number", "Medicine_Name", "Status"]].to_string(index=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo-auto", action="store_true",
                        help="skip pharmacist prompt (ONLY for demo_app.py fake data)")
    args = parser.parse_args()

    try:
        from pywinauto import Application
    except ImportError:
        sys.exit("pywinauto is not installed (Windows only). Run: pip install pywinauto")

    try:
        app = Application(backend="uia").connect(title=APP_TITLE, timeout=10)
        win = app.window(title=APP_TITLE)
    except Exception as e:
        sys.exit(f"Could not find the window '{APP_TITLE}'. Start the app first. ({e})")

    log = []
    try:
        if os.path.exists(PDF_FILE):
            print(f"--> [PDF task] Found {PDF_FILE}")
            try:
                _, pdf_rx, pdf_med = extract_pdf_data(PDF_FILE)
            except Exception as e:
                sys.exit(f"Could not read PDF safely: {e}")
            print(f"    PDF says: {pdf_rx} | {pdf_med}")
            if not is_valid_rx(pdf_rx) or TARGET_KEYWORD not in pdf_med.lower():
                print(f"--> Skipped: PDF is not a valid '{TARGET_KEYWORD}' prescription.")
            else:
                click_button(win, "New Prescription")
                process_current(app, win, "PDF Data Entry", log, args.demo_auto, pdf_rx=pdf_rx)
        else:
            print("--> [Primary task] No PDF found. Running screen data entry...")
            for i in range(TOTAL_ITEMS):
                print(f"\n[Cycle {i + 1}/{TOTAL_ITEMS}]")
                click_button(win, "New Prescription")
                process_current(app, win, "Screen Data Entry", log, args.demo_auto)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"\nERROR - stopped safely: {e}")
    finally:
        save_report(log)   # report is always saved, even after an error


if __name__ == "__main__":
    main()
