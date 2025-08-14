# -*- coding: utf-8 -*-
"""
Battery Notifier for Windows 11 — Headless with Tkinter Messagebox
- This version uses a simple Tkinter pop-up for notifications.
- It completely removes all system tray and toast libraries to avoid conflicts.
- To open settings, run with --settings from the command line.
"""

import os, sys, subprocess, json, time, threading, datetime
import tkinter as tk
from tkinter import messagebox, ttk

# --- Bootstrap Dependencies ---
APP_NAME = "Battery Notifier"
APP_VERSION = "1.0.0"
APP_DIR = os.path.join(os.getenv("APPDATA") or "", "BatteryNotifier")
VENDOR_DIR = os.path.join(APP_DIR, "_vendor")
os.makedirs(VENDOR_DIR, exist_ok=True)
if VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)

REQUIRED = {"psutil": "5.9.8"}

def _need_bootstrap():
    try:
        __import__("psutil")
        return False
    except ImportError:
        return True

def _ensure_pip():
    try:
        import pip
        return True
    except ImportError:
        try:
            import ensurepip
            ensurepip.bootstrap(upgrade=True)
            return True
        except Exception:
            return False

def _bootstrap_vendor():
    if not _ensure_pip():
        raise RuntimeError("Unable to bootstrap pip (ensurepip failed).")
    py = sys.executable or "python"
    for name, ver in REQUIRED.items():
        try:
            __import__(name)
        except ImportError:
            args = [
                py, "-m", "pip", "install",
                f"{name}=={ver}",
                "--no-warn-script-location",
                "--disable-pip-version-check",
                "--target", VENDOR_DIR,
            ]
            subprocess.check_call(args)

if _need_bootstrap():
    try:
        _bootstrap_vendor()
    except Exception as e:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Battery Notifier", f"First-run setup failed:\n{e}")
        sys.exit(1)

import psutil

# --- Static Settings (No UI) ---
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")
STARTUP_SHORTCUT_PATH = os.path.join(os.environ.get("APPDATA") or "", "Microsoft", "Windows", "Start Menu", "Programs", "Startup", f"{APP_NAME}.lnk")

DEFAULTS = {
    "low_threshold": 20,
    "high_threshold": 80,
    "poll_seconds": 60,
    "start_with_windows": True,
}

def ensure_app_dir():
    if APP_DIR and not os.path.isdir(APP_DIR):
        os.makedirs(APP_DIR, exist_ok=True)

def load_settings():
    ensure_app_dir()
    data = {}
    if os.path.isfile(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    cfg = DEFAULTS.copy()
    for k, v in data.items():
        if k in cfg:
            cfg[k] = v
    return cfg

def save_settings(s):
    ensure_app_dir()
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)

SETTINGS = load_settings()

def show_notification_messagebox(title: str, message: str):
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(title, message)
    root.destroy()

def open_settings_window():
    import win32com.client
    s = load_settings()
    root = tk.Tk()
    root.title(f"{APP_NAME} Settings")
    root.resizable(False, False)
    win_w, win_h = 420, 250
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    x = max(0, (sw - win_w)//2); y = max(0, (sh - win_h)//2)
    root.geometry(f"{win_w}x{win_h}+{x}+{y}")
    pad = {'padx': 10, 'pady': 6}

    ttk.Label(root, text="Low battery threshold (%)").grid(row=0, column=0, sticky="w", **pad)
    low_var = tk.IntVar(value=int(s["low_threshold"]))
    ttk.Spinbox(root, from_=1, to=100, textvariable=low_var, width=6, justify="center").grid(row=0, column=1, sticky="e", **pad)

    ttk.Label(root, text="High battery threshold (%)").grid(row=1, column=0, sticky="w", **pad)
    high_var = tk.IntVar(value=int(s["high_threshold"]))
    ttk.Spinbox(root, from_=1, to=100, textvariable=high_var, width=6, justify="center").grid(row=1, column=1, sticky="e", **pad)

    ttk.Label(root, text="Poll interval (seconds)").grid(row=2, column=0, sticky="w", **pad)
    poll_var = tk.IntVar(value=int(s["poll_seconds"]))
    ttk.Spinbox(root, from_=5, to=600, increment=5, textvariable=poll_var, width=6, justify="center").grid(row=2, column=1, sticky="e", **pad)

    start_with_windows_var = tk.BooleanVar(value=s["start_with_windows"])
    ttk.Checkbutton(root, text="Start with Windows", variable=start_with_windows_var).grid(row=3, column=0, columnspan=2, sticky="w", **pad)

    def save_and_close():
        try:
            s["low_threshold"] = max(1, min(100, int(low_var.get())))
            s["high_threshold"] = max(1, min(100, int(high_var.get())))
            s["poll_seconds"] = max(5, min(600, int(poll_var.get())))
            
            if start_with_windows_var.get() != s["start_with_windows"]:
                s["start_with_windows"] = start_with_windows_var.get()
                if s["start_with_windows"]:
                    enable_auto_startup()
                else:
                    disable_auto_startup()

            save_settings(s)
            SETTINGS.update(s)
            root.destroy()
        except tk.TclError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers.")
        except Exception as ex:
            messagebox.showerror("Error", f"An error occurred while saving settings: {ex}")

    btns = ttk.Frame(root); btns.grid(row=4, column=0, columnspan=2, pady=(8,10))
    ttk.Button(btns, text="Save", command=save_and_close).grid(row=0, column=0, padx=6)
    ttk.Button(btns, text="Cancel", command=root.destroy).grid(row=0, column=1, padx=6)
    root.mainloop()

def enable_auto_startup():
    import win32com.client
    if sys.platform != "win32": return
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(STARTUP_SHORTCUT_PATH)
        shortcut.Targetpath = sys.executable
        shortcut.Arguments = f'"{os.path.abspath(sys.argv[0])}"'
        shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(sys.argv[0]))
        shortcut.save()
    except Exception as e:
        print(f"Failed to enable auto-startup: {e}")

def disable_auto_startup():
    if sys.platform != "win32": return
    try:
        if os.path.exists(STARTUP_SHORTCUT_PATH):
            os.remove(STARTUP_SHORTCUT_PATH)
    except Exception as e:
        print(f"Failed to disable auto-startup: {e}")

def main_loop():
    last_alert = None
    
    while True:
        try:
            batt = psutil.sensors_battery()
            if batt is None:
                time.sleep(10)
                continue

            current_percent = int(round(batt.percent))
            current_charging = bool(batt.power_plugged)
            
            if not current_charging and current_percent <= SETTINGS["low_threshold"]:
                if last_alert != "low":
                    show_notification_messagebox(
                        f"Battery Low: {current_percent}%", 
                        "Please connect your charger."
                    )
                    last_alert = "low"
            elif current_charging and current_percent >= SETTINGS["high_threshold"]:
                if last_alert != "high":
                    show_notification_messagebox(
                        f"Battery High: {current_percent}%", 
                        "You can unplug the charger."
                    )
                    last_alert = "high"
            else:
                last_alert = None
        except Exception as e:
            print(f"An error occurred: {e}")
            
        time.sleep(max(5, int(SETTINGS.get("poll_seconds", 60))))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--settings":
        open_settings_window()
        sys.exit(0)

    if SETTINGS["start_with_windows"]:
        # Only bootstrap the auto-startup logic if running on Windows
        try:
            import win32com.client
            enable_auto_startup()
        except ImportError:
            print("Auto-startup not supported without pywin32. Please install it with 'pip install pywin32'")
    else:
        try:
            import win32com.client
            disable_auto_startup()
        except ImportError:
            pass

    main_loop()