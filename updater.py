"""YVZTOOLS Updater - downloads the newest YVZNETMATH.exe from your GitHub Releases."""
import os, re, sys, json, time, subprocess, threading, urllib.request
import tkinter as tk
from tkinter import ttk

# ====== EDIT THESE TWO LINES ======
GITHUB_REPO = "YOUR_USERNAME/YOUR_REPO"   # e.g. "yvz/yvztools"
ASSET_NAME = "YVZNETMATH.exe"             # file name you upload to each Release
# ==================================

APP_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
APP_EXE = os.path.join(APP_DIR, ASSET_NAME)
VERSION_FILE = os.path.join(APP_DIR, "version.txt")
API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def parse(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")) or (0,)


def local_version():
    try:
        return open(VERSION_FILE, encoding="utf-8").read().strip()
    except OSError:
        return "0"


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "yvz-updater", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


class Updater(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YVZTOOLS Updater")
        self.geometry("420x170")
        self.resizable(False, False)
        self.configure(bg="#050817")
        self.msg = tk.Label(self, text="Checking for updates...", bg="#050817", fg="#F2F6FF", font=("Segoe UI Semibold", 11))
        self.msg.pack(pady=(28, 10))
        self.bar = ttk.Progressbar(self, length=340, mode="indeterminate")
        self.bar.pack()
        self.bar.start(12)
        self.sub = tk.Label(self, text="", bg="#050817", fg="#91A1CC", font=("Segoe UI", 8))
        self.sub.pack(pady=10)
        threading.Thread(target=self.run, daemon=True).start()

    def say(self, text, sub=""):
        self.after(0, lambda: (self.msg.config(text=text), self.sub.config(text=sub)))

    def finish(self, text, sub="", launch=False, delay=1800):
        self.say(text, sub)
        self.after(0, self.bar.stop)
        if launch and os.path.exists(APP_EXE):
            subprocess.Popen([APP_EXE], cwd=APP_DIR)
        self.after(delay, self.destroy)

    def run(self):
        try:
            rel = http_json(API)
            latest = rel["tag_name"]
            cur = local_version()
            if parse(latest) <= parse(cur) and os.path.exists(APP_EXE):
                return self.finish("You're up to date", f"Version {cur}", launch=True)
            asset = next((a for a in rel.get("assets", []) if a["name"] == ASSET_NAME), None)
            if not asset:
                return self.finish("Update failed", f"{ASSET_NAME} not found in release {latest}", delay=4000)

            self.say(f"Downloading {latest}...", f"{cur} -> {latest}")
            subprocess.run(["taskkill", "/IM", ASSET_NAME, "/F"], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            time.sleep(0.8)

            tmp = APP_EXE + ".new"
            req = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "yvz-updater"})
            with urllib.request.urlopen(req, timeout=30) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                self.after(0, lambda: self.bar.config(mode="determinate", maximum=max(total, 1), value=0))
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    self.after(0, lambda d=done: self.bar.config(value=d))
                    self.say(f"Downloading {latest}...", f"{done // 1048576} / {total // 1048576} MB")
            if total and os.path.getsize(tmp) != total:
                raise IOError("Download incomplete")

            bak = APP_EXE + ".bak"
            if os.path.exists(APP_EXE):
                if os.path.exists(bak):
                    os.remove(bak)
                os.replace(APP_EXE, bak)
            os.replace(tmp, APP_EXE)
            open(VERSION_FILE, "w", encoding="utf-8").write(latest)
            self.finish("Updated!", f"Now on {latest} - launching...", launch=True)
        except Exception as e:
            self.finish("Update failed", str(e)[:120], launch=True, delay=4000)


if __name__ == "__main__":
    Updater().mainloop()
