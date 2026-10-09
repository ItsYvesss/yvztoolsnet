"""YVZTools updater with an explicit check/update UI and verified downloads."""
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

GITHUB_REPO = "ItsYvesss/yvztoolsnet"
RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
APP_NAME = "YVZNETMATH.exe"
APP_DIR = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
APP_EXE = APP_DIR / APP_NAME
VERSION_FILE = APP_DIR / "version.txt"
UPDATER_VERSION = "4.0.0"
USER_AGENT = f"YVZTOOLS-Updater/{UPDATER_VERSION}"


def version_tuple(value):
    """Parse v4.0, 4.0.0, or older version tags into comparable numeric tuples."""
    found = re.findall(r"\d+", str(value or ""))
    return tuple(int(part) for part in found) if found else (0,)


def normalized_version(value):
    parts = list(version_tuple(value))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def display_version(value):
    parts = list(normalized_version(value))
    if parts[2] == 0:
        return f"v{parts[0]}.{parts[1]}"
    return f"v{parts[0]}.{parts[1]}.{parts[2]}"


def read_local_version():
    try:
        value = VERSION_FILE.read_text(encoding="utf-8").strip()
        return value or "0.0.0"
    except OSError:
        # No version marker is treated as an old installation, never as current.
        return "0.0.0"


def request_json(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.load(response)
    if not isinstance(data, dict):
        raise ValueError("GitHub returned invalid release metadata.")
    return data


def app_is_running():
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {APP_NAME}", "/NH"],
            capture_output=True, text=True, timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return APP_NAME.lower() in (result.stdout or "").lower()
    except (OSError, subprocess.SubprocessError):
        # Atomic replacement remains the final safety check if process detection fails.
        return False


def verify_download(path, asset):
    size = path.stat().st_size
    if size < 1_000_000:
        raise ValueError("The downloaded application is unexpectedly small; the update was rejected.")
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("The downloaded file is not a valid Windows executable.")
    expected = str(asset.get("digest") or "").strip()
    algorithm, sep, expected_hash = expected.partition(":")
    if sep and algorithm.lower() == "sha256":
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != expected_hash.lower():
            raise ValueError("SHA-256 verification failed. The downloaded update was rejected.")
    return True


class Updater(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YVZTools Updater")
        self.geometry("650x440")
        self.minsize(600, 420)
        self.resizable(False, False)
        self.configure(bg="#080D20")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker = None
        self.busy = False
        self.latest_tag = None
        self.latest_asset = None
        self.current_version = read_local_version()
        self.status_var = tk.StringVar(value="Checking the official release channel…")
        self.detail_var = tk.StringVar(value="Connecting to GitHub Releases")
        self.current_var = tk.StringVar(value=f"Installed version: {display_version(self.current_version)}")
        self.latest_var = tk.StringVar(value="Latest version: checking…")

        outer = tk.Frame(self, bg="#080D20", padx=26, pady=22)
        outer.pack(fill="both", expand=True)
        tk.Label(outer, text="YVZTOOLS", bg="#080D20", fg="#F4F7FF",
                 font=("Segoe UI", 25, "bold")).pack(anchor="w")
        tk.Label(outer, text="UPDATER  •  OFFICIAL STABLE RELEASES",
                 bg="#080D20", fg="#59B8FF", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 20))

        panel = tk.Frame(outer, bg="#111A37", highlightbackground="#263C70", highlightthickness=1, padx=18, pady=17)
        panel.pack(fill="x")
        tk.Label(panel, textvariable=self.status_var, bg="#111A37", fg="#F4F7FF",
                 font=("Segoe UI", 15, "bold"), anchor="w", wraplength=540, justify="left").pack(fill="x")
        tk.Label(panel, textvariable=self.detail_var, bg="#111A37", fg="#AAB8DD",
                 font=("Segoe UI", 9), anchor="w", wraplength=540, justify="left").pack(fill="x", pady=(7, 13))
        tk.Label(panel, textvariable=self.current_var, bg="#111A37", fg="#E5EBFF",
                 font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=2)
        tk.Label(panel, textvariable=self.latest_var, bg="#111A37", fg="#E5EBFF",
                 font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=2)

        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100, value=0, length=590)
        self.progress.pack(fill="x", pady=(20, 4))
        self.progress_label = tk.Label(outer, text="", bg="#080D20", fg="#AAB8DD",
                                       font=("Segoe UI", 9), anchor="w")
        self.progress_label.pack(fill="x")

        row = tk.Frame(outer, bg="#080D20")
        row.pack(fill="x", side="bottom", pady=(20, 0))
        self.update_btn = tk.Button(row, text="Update Now", command=self.start_update,
                                    bg="#2589FF", fg="white", activebackground="#4AA0FF",
                                    activeforeground="white", relief="flat", bd=0,
                                    font=("Segoe UI", 10, "bold"), padx=20, pady=10, state="disabled")
        self.update_btn.pack(side="left")
        self.retry_btn = tk.Button(row, text="Retry Check", command=self.check_updates,
                                   bg="#1A2548", fg="#F4F7FF", activebackground="#283B70",
                                   activeforeground="white", relief="flat", bd=0,
                                   font=("Segoe UI", 10), padx=16, pady=10, state="disabled")
        self.retry_btn.pack(side="left", padx=(9, 0))
        self.cancel_btn = tk.Button(row, text="Cancel Download", command=self.cancel_download,
                                    bg="#442333", fg="#FFFFFF", activebackground="#67344A",
                                    activeforeground="white", relief="flat", bd=0,
                                    font=("Segoe UI", 10), padx=14, pady=10, state="disabled")
        self.cancel_btn.pack(side="left", padx=(9, 0))
        self.close_btn = tk.Button(row, text="Close", command=self.close,
                                   bg="#1A2548", fg="#F4F7FF", activebackground="#283B70",
                                   activeforeground="white", relief="flat", bd=0,
                                   font=("Segoe UI", 10), padx=18, pady=10)
        self.close_btn.pack(side="right")
        self.after(100, self.poll_events)
        self.check_updates()

    def close(self):
        if self.busy:
            if not messagebox.askyesno("YVZTools Updater", "An update operation is active. Close the updater anyway?", parent=self):
                return
            self.cancel_event.set()
        self.destroy()

    def set_busy(self, value):
        self.busy = value
        self.update_btn.configure(state="disabled" if value else "normal")
        self.retry_btn.configure(state="disabled" if value else "normal")
        self.cancel_btn.configure(state="normal" if value else "disabled")

    def check_updates(self):
        if self.busy:
            return
        self.cancel_event.clear()
        self.latest_tag = None
        self.latest_asset = None
        self.set_busy(True)
        self.cancel_btn.configure(state="disabled")
        self.update_btn.configure(state="disabled")
        self.retry_btn.configure(state="disabled")
        self.status_var.set("Checking for updates…")
        self.detail_var.set("Reading the latest stable release from GitHub.")
        self.progress.configure(value=0, mode="indeterminate")
        self.progress.start(10)
        self.progress_label.configure(text="")
        self.worker = threading.Thread(target=self.check_worker, daemon=True)
        self.worker.start()

    def check_worker(self):
        try:
            rel = request_json(RELEASE_API)
            tag = rel.get("tag_name")
            if not isinstance(tag, str) or not re.fullmatch(r"v?\d+(?:\.\d+){1,2}", tag.strip()):
                raise ValueError("The latest release has missing or invalid version metadata.")
            if rel.get("draft") or rel.get("prerelease"):
                raise ValueError("GitHub did not return a stable release. Please retry shortly.")
            asset = next((item for item in rel.get("assets", []) if item.get("name") == APP_NAME), None)
            if not asset or not asset.get("browser_download_url"):
                raise ValueError(f"The stable release {tag} is missing {APP_NAME}.")
            self.events.put(("check_ok", read_local_version(), tag.strip(), asset))
        except Exception as exc:
            self.events.put(("error", "Update check failed", self.describe_error(exc)))

    @staticmethod
    def describe_error(exc):
        if isinstance(exc, urllib.error.URLError):
            return f"Could not reach GitHub. Check your internet connection and try again. Details: {exc}"
        if isinstance(exc, TimeoutError):
            return "The connection timed out. Check your internet connection and retry."
        return str(exc) or exc.__class__.__name__

    def start_update(self):
        if self.busy or not self.latest_tag or not self.latest_asset:
            return
        self.cancel_event.clear()
        self.set_busy(True)
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self.progress_label.configure(text="Preparing verified download…")
        self.status_var.set(f"Update available: {display_version(self.latest_tag)}")
        self.detail_var.set("Downloading the official YVZNETMATH.exe release asset.")
        self.worker = threading.Thread(target=self.update_worker, daemon=True)
        self.worker.start()

    def cancel_download(self):
        if self.busy:
            self.cancel_event.set()
            self.status_var.set("Cancelling download…")
            self.detail_var.set("Stopping safely and removing the incomplete temporary file.")

    def update_worker(self):
        temp_path = APP_DIR / f".{APP_NAME}.download"
        try:
            if app_is_running():
                raise RuntimeError("YVZNETMATH.exe is currently running. Close YVZTOOLS completely, then click Update Now again.")
            req = urllib.request.Request(
                self.latest_asset["browser_download_url"],
                headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
            )
            with urllib.request.urlopen(req, timeout=25) as response:
                total = int(response.headers.get("Content-Length") or 0)
                done = 0
                with temp_path.open("wb") as output:
                    while True:
                        if self.cancel_event.is_set():
                            raise InterruptedError("Download cancelled.")
                        chunk = response.read(128 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        done += len(chunk)
                        percent = (done * 100 / total) if total > 0 else 0
                        self.events.put(("progress", percent, done, total))
            if self.cancel_event.is_set():
                raise InterruptedError("Download cancelled.")
            verify_download(temp_path, self.latest_asset)
            if app_is_running():
                raise RuntimeError("YVZTOOLS opened during the download. Close it and click Update Now again.")
            os.replace(str(temp_path), str(APP_EXE))
            version_tmp = VERSION_FILE.with_suffix(".txt.tmp")
            version_tmp.write_text(self.latest_tag, encoding="utf-8")
            os.replace(str(version_tmp), str(VERSION_FILE))
            try:
                subprocess.Popen([str(APP_EXE)], cwd=str(APP_DIR))
                self.events.put(("installed", self.latest_tag, True, "The update was verified, installed, and YVZTOOLS was relaunched."))
            except OSError as exc:
                self.events.put(("installed", self.latest_tag, False, f"Update installed, but YVZTOOLS could not be launched automatically: {exc}"))
        except InterruptedError:
            self.events.put(("cancelled",))
        except Exception as exc:
            self.events.put(("error", "Update failed", self.describe_error(exc)))
        finally:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass

    def poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "progress":
                    _, percent, done, total = event
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=max(0, min(100, percent)))
                    if total:
                        self.progress_label.configure(text=f"Downloaded {done / 1048576:.1f} MB of {total / 1048576:.1f} MB ({percent:.0f}%)")
                    else:
                        self.progress_label.configure(text=f"Downloaded {done / 1048576:.1f} MB")
                elif kind == "check_ok":
                    _, current, latest, asset = event
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
                    self.current_version = current
                    self.latest_tag = latest
                    self.latest_asset = asset
                    self.current_var.set(f"Installed version: {display_version(current)}")
                    self.latest_var.set(f"Latest version: {display_version(latest)}")
                    self.set_busy(False)
                    self.retry_btn.configure(state="normal")
                    if normalized_version(current) >= normalized_version(latest):
                        self.status_var.set("You're up to date!")
                        self.detail_var.set(f"YVZTOOLS {display_version(current)} is already the latest stable release. This window will stay open until you close it.")
                        self.update_btn.configure(state="disabled")
                    else:
                        self.status_var.set(f"Update available: {display_version(latest)}")
                        self.detail_var.set(f"Your installed version is {display_version(current)}. Select Update Now to download and install the official release.")
                        self.update_btn.configure(state="normal")
                    self.progress_label.configure(text="")
                elif kind == "installed":
                    _, tag, launched, detail = event
                    self.progress.stop()
                    self.progress.configure(value=100)
                    self.set_busy(False)
                    self.current_version = tag
                    self.current_var.set(f"Installed version: {display_version(tag)}")
                    self.latest_var.set(f"Latest version: {display_version(tag)}")
                    self.status_var.set("Update completed successfully" if launched else "Update installed")
                    self.detail_var.set(detail)
                    self.update_btn.configure(state="disabled")
                    self.retry_btn.configure(state="normal")
                    self.progress_label.configure(text="Verification passed • SHA-256 checked when provided by GitHub")
                elif kind == "cancelled":
                    self.progress.stop()
                    self.progress.configure(value=0)
                    self.set_busy(False)
                    self.status_var.set("Download cancelled")
                    self.detail_var.set("The incomplete download was removed. You can retry whenever you're ready.")
                    self.update_btn.configure(state="normal" if self.latest_asset else "disabled")
                    self.retry_btn.configure(state="normal")
                    self.progress_label.configure(text="")
                elif kind == "error":
                    _, title, detail = event
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
                    self.set_busy(False)
                    self.status_var.set(title)
                    self.detail_var.set(detail)
                    self.retry_btn.configure(state="normal")
                    self.update_btn.configure(state="normal" if self.latest_asset else "disabled")
                    self.progress_label.configure(text="")
        except queue.Empty:
            pass
        try:
            self.after(100, self.poll_events)
        except tk.TclError:
            pass


if __name__ == "__main__":
    Updater().mainloop()
