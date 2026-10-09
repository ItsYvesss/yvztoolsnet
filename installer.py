"""YVZTOOLS Installer v3.9 — installs the matching app and updater."""
import os
import sys
import json
import queue
import threading
import urllib.request
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import ssl

try:
    import certifi
except ImportError:
    certifi = None

GITHUB_REPO = "ItsYvesss/yvztoolsnet"
API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/v3.9"
APP_NAME = "YVZNETMATH.exe"
UPDATER_NAME = "YVZUPDATER.exe"

BG = "#070B18"
PANEL = "#0D1530"
TEXT = "#F4F7FF"
MUTED = "#91A1CC"
BLUE = "#4A9BFF"
GREEN = "#4BE3B0"
TRACK = "#1A2850"


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def make_ssl_context():
    if certifi:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


SSL_CONTEXT = make_ssl_context()


def get_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "YVZTOOLS-Installer/3.9",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as response:
        return json.load(response)


class Installer(tk.Tk):
    W, H = 680, 460

    def __init__(self):
        super().__init__()
        # Use a normal Windows window: native title bar, working X, taskbar entry,
        # Alt+Tab support, and standard Windows window management.
        self.title("YVZTOOLS Installer v3.9")
        self.resizable(False, False)
        self.configure(bg=BG)
        try:
            self.iconbitmap(resource_path("yvztools.ico"))
        except (tk.TclError, OSError):
            pass

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())

        self.closing = False
        self.stop_event = threading.Event()
        self.updates = queue.Queue(maxsize=1)
        self.worker = None
        self.folder = os.path.join(os.path.expanduser("~"), "YVZTOOLS")
        self.state = "choose"
        self.pct = 0.0
        self.msg = "Choose where YVZTOOLS will be installed."
        self.sub = "Select a folder, then install the latest build."
        self.c = tk.Canvas(self, width=self.W, height=self.H, bg=BG, highlightthickness=0)
        self.c.pack(fill="both", expand=True)
        self.draw()
        self.after(100, self.poll_updates)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.stop_event.set()
        try:
            self.destroy()
        except tk.TclError:
            pass

    def choose(self):
        if self.closing or self.state != "choose":
            return
        try:
            path = filedialog.askdirectory(
                parent=self,
                title="Choose YVZTOOLS installation folder",
                initialdir=os.path.dirname(self.folder),
                mustexist=True,
            )
        except tk.TclError:
            return
        if path and not self.closing:
            self.folder = (
                path if os.path.basename(path).upper() == "YVZTOOLS"
                else os.path.join(path, "YVZTOOLS")
            )
            self.draw()

    def install(self):
        if self.closing or self.state != "choose":
            return
        self.state = "download"
        self.msg = "Preparing YVZTOOLS..."
        self.sub = f"Installing to {self.folder}"
        self.pct = 0.0
        self.draw()
        self.worker = threading.Thread(target=self.run, name="YVZTOOLS-download", daemon=True)
        self.worker.start()

    def ui(self, msg=None, sub=None, pct=None, action=None):
        if self.stop_event.is_set():
            return
        update = (msg, sub, pct, action)
        # Keep only the newest UI update; never let a fast download flood the UI.
        try:
            self.updates.get_nowait()
        except queue.Empty:
            pass
        try:
            self.updates.put_nowait(update)
        except queue.Full:
            pass

    def poll_updates(self):
        if self.closing:
            return
        try:
            while True:
                msg, sub, pct, action = self.updates.get_nowait()
                if msg is not None:
                    self.msg = msg
                if sub is not None:
                    self.sub = sub
                if pct is not None:
                    self.pct = max(0.0, min(1.0, pct))
                self.draw()
                if action == "finish":
                    self.finish()
                    return
                if action == "fail":
                    messagebox.showerror("YVZTOOLS Installer", self.msg + "\n\n" + self.sub, parent=self)
        except queue.Empty:
            pass
        if not self.closing:
            self.after(100, self.poll_updates)

    def run(self):
        try:
            os.makedirs(self.folder, exist_ok=True)
            if self.stop_event.is_set():
                return
            release = get_json(API)
            tag = release["tag_name"]
            assets = {asset["name"]: asset for asset in release.get("assets", [])}
            missing = [name for name in (APP_NAME, UPDATER_NAME) if name not in assets]
            if missing:
                raise RuntimeError("The v3.9 release is missing required file(s): " + ", ".join(missing))
            # Always install the app AND the matching updater from the pinned v3.9 release.
            wanted = [APP_NAME, UPDATER_NAME]

            total_files = len(wanted)
            for index, name in enumerate(wanted):
                if self.stop_event.is_set():
                    return
                dest = os.path.join(self.folder, name)
                req = urllib.request.Request(
                    assets[name]["browser_download_url"],
                    headers={"User-Agent": "YVZTOOLS-Installer/3.9"},
                )
                self.ui(f"Downloading {name}", f"YVZTOOLS {tag} • {self.folder}", 0)
                with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as response, open(dest, "wb") as output:
                    total = int(response.headers.get("Content-Length") or 0)
                    done = 0
                    while True:
                        if self.stop_event.is_set():
                            return
                        chunk = response.read(128 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        done += len(chunk)
                        local = done / total if total > 0 else 0
                        progress = (index + local) / total_files
                        self.ui(
                            pct=progress,
                            sub=f"{name} • {done / 1048576:.1f} MB downloaded",
                        )

            if self.stop_event.is_set():
                return
            with open(os.path.join(self.folder, "version.txt"), "w", encoding="utf-8") as version_file:
                version_file.write(tag)
            self.ui("Installation complete", "Launching YVZTOOLS...", 1.0, "finish")
        except Exception as exc:
            if not self.stop_event.is_set():
                self.ui("Installation failed", str(exc)[:220], action="fail")

    def finish(self):
        if self.closing:
            return
        try:
            subprocess.Popen([os.path.join(self.folder, APP_NAME)], cwd=self.folder)
            self.close()
        except Exception as exc:
            messagebox.showerror(
                "YVZTOOLS Installer",
                f"Could not launch YVZNETMATH.exe:\n{exc}",
                parent=self,
            )

    def draw(self):
        if self.closing:
            return
        c = self.c
        c.delete("all")
        c.create_rectangle(0, 0, self.W, self.H, fill=BG, outline="")
        c.create_rectangle(0, 0, self.W, 5, fill=BLUE, outline="")
        c.create_rectangle(24, 22, self.W-24, self.H-22, fill=PANEL, outline="#20356F")
        c.create_text(48, 55, anchor="w", text="YVZTOOLS", fill=TEXT, font=("Segoe UI", 29, "bold"))
        c.create_text(50, 84, anchor="w", text="INSTALLER  •  V3.9", fill=BLUE, font=("Segoe UI Semibold", 10))
        c.create_text(48, 133, anchor="w", text=self.msg, fill=TEXT, font=("Segoe UI Semibold", 16))
        c.create_text(48, 162, anchor="w", text=self.sub[:85], fill=MUTED, font=("Segoe UI", 9))
        c.create_text(48, 205, anchor="w", text="INSTALL LOCATION", fill=MUTED, font=("Segoe UI Semibold", 8))
        c.create_rectangle(48, 220, 632, 264, fill="#080F28", outline=TRACK)
        c.create_text(62, 242, anchor="w", text=self.folder, fill=TEXT, font=("Segoe UI", 9))

        if self.state == "choose":
            c.create_rectangle(48, 292, 632, 345, fill=BLUE, outline="", tags="install")
            c.create_text(340, 318, text="INSTALL YVZTOOLS  →", fill="#FFFFFF", font=("Segoe UI Semibold", 11), tags="install")
            c.tag_bind("install", "<Button-1>", lambda _event: self.install())
            c.create_rectangle(48, 356, 270, 399, fill="#101A3A", outline=TRACK, tags="choose")
            c.create_text(159, 377, text="CHOOSE FOLDER", fill=TEXT, font=("Segoe UI Semibold", 9), tags="choose")
            c.tag_bind("choose", "<Button-1>", lambda _event: self.choose())
        else:
            c.create_line(48, 318, 632, 318, fill=TRACK, width=10, capstyle="round")
            c.create_line(48, 318, 48 + 584*self.pct, 318, fill=GREEN, width=10, capstyle="round")
            c.create_text(48, 344, anchor="w", text=f"{int(self.pct*100)}%", fill=GREEN, font=("Segoe UI Semibold", 9))
            c.create_text(632, 344, anchor="e", text="YVZTOOLS • SECURE INSTALL", fill=MUTED, font=("Segoe UI", 8))
        c.create_text(48, 424, anchor="w", text="YVZTOOLS NETMATH SPACE", fill=MUTED, font=("Segoe UI", 8))


if __name__ == "__main__":
    Installer().mainloop()
