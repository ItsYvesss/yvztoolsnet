"""YVZTools updater with an explicit check/update UI and verified downloads."""
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import ssl
import certifi
import threading
import time
import urllib.error
import urllib.parse
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
RELEASE_CACHE_FILE = APP_DIR / "release_cache.json"
UPDATER_VERSION = "8.6.0"
USER_AGENT = f"YVZTOOLS-Updater/{UPDATER_VERSION}"
# Use certifi’s bundled Mozilla CA roots so HTTPS certificate validation works
# in the PyInstaller one-file build as well as a normal Python installation.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def version_tuple(value):
    """Parse v4.2, 4.2.0, or older version tags into comparable numeric tuples."""
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


def release_metadata_from_tag(tag, digest=""):
    tag = str(tag or '').strip()
    if not re.fullmatch(r'v?\d+(?:\.\d+){1,2}', tag):
        raise ValueError('GitHub returned an invalid stable release tag.')
    if not tag.startswith('v'):
        tag = 'v' + tag
    asset_url = ('https://github.com/' + GITHUB_REPO + '/releases/download/'
                 + urllib.parse.quote(tag, safe='') + '/'
                 + urllib.parse.quote(APP_NAME))
    return {
        'tag_name': tag,
        'asset': {
            'name': APP_NAME,
            'browser_download_url': asset_url,
            'digest': str(digest or '')
        }
    }


def save_release_cache(metadata):
    try:
        temp = RELEASE_CACHE_FILE.with_suffix('.tmp')
        temp.write_text(json.dumps({
            'tag_name': metadata['tag_name'],
            'digest': metadata['asset'].get('digest', ''),
            'saved_at': int(time.time())
        }), encoding='utf-8')
        os.replace(str(temp), str(RELEASE_CACHE_FILE))
    except (OSError, KeyError, TypeError):
        pass


def read_release_cache():
    try:
        cached = json.loads(RELEASE_CACHE_FILE.read_text(encoding='utf-8'))
        if time.time() - int(cached.get('saved_at', 0)) > 2592000:
            return None
        return release_metadata_from_tag(
            cached.get('tag_name'), cached.get('digest', '')
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def request_latest_release():
    """Fetch official release metadata, including GitHub's SHA-256 asset digest."""
    last_error = None
    for attempt in range(3):
        req = urllib.request.Request(
            RELEASE_API,
            headers={
                'User-Agent': USER_AGENT,
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
                'Cache-Control': 'no-cache'
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as response:
                release = json.loads(response.read().decode('utf-8'))
            tag = release.get('tag_name', '')
            metadata = release_metadata_from_tag(tag)
            assets = release.get('assets') or []
            asset = next(
                (item for item in assets if item.get('name') == APP_NAME),
                None
            )
            if not asset or not asset.get('browser_download_url'):
                raise ValueError('The latest GitHub release does not contain YVZNETMATH.exe.')
            digest = str(asset.get('digest') or '')
            if not digest.startswith('sha256:'):
                raise ValueError('GitHub did not provide a SHA-256 checksum for this release. The update was stopped for safety.')
            metadata['asset'] = {
                'name': APP_NAME,
                'browser_download_url': asset['browser_download_url'],
                'digest': digest
            }
            save_release_cache(metadata)
            return metadata
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            retry_after = exc.headers.get('Retry-After') if exc.headers else None
            try:
                delay = min(12, max(1, int(retry_after))) if retry_after else (2 ** attempt)
            except (TypeError, ValueError):
                delay = 2 ** attempt
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise last_error or RuntimeError('GitHub release check failed.')

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
    if not sep or algorithm.lower() != "sha256" or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash):
        raise ValueError("The official release is missing a valid SHA-256 checksum. The update was rejected.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().lower() != expected_hash.lower():
        raise ValueError("The downloaded update failed its SHA-256 integrity check and was rejected.")
    return True


class Updater(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YVZTools Updater")
        self.geometry("680x500")
        self.minsize(640, 470)
        self.resizable(True, True)
        self.configure(bg="#F4F6FA")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker = None
        self.busy = False
        self.latest_tag = None
        self.latest_asset = None
        self.current_version = read_local_version()

        # Deep-blue YVZTools updater interface
        BG = "#071426"
        PANEL = "#0D2039"
        PANEL_ALT = "#102945"
        TEXT = "#F4F8FF"
        MUTED = "#91A9C7"
        BLUE = "#287BFF"
        BLUE_HOVER = "#4590FF"
        BORDER = "#1D3B5E"
        GREEN = "#39D6A0"

        self.geometry("720x540")
        self.minsize(680, 510)
        self.configure(bg=BG)

        outer = tk.Frame(self, bg=BG, padx=30, pady=25)
        outer.pack(fill="both", expand=True)

        # Branded header with a strong blue accent.
        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", pady=(0, 20))
        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left", fill="x", expand=True)
        tk.Label(brand, text="YVZTOOLS", bg=BG, fg=TEXT,
                 font=("Segoe UI", 23, "bold")).pack(anchor="w")
        tk.Label(brand, text="UPDATE CENTER  /  KEEP YOUR TOOLS CURRENT",
                 bg=BG, fg="#6FAAFF", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(3, 0))
        self.header_badge = tk.Label(
            header, text="●  OFFICIAL RELEASE", bg="#102E52", fg="#77B7FF",
            font=("Segoe UI", 8, "bold"), padx=13, pady=8)
        self.header_badge.pack(side="right", anchor="center")

        # Main status panel.
        panel = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER,
                         highlightthickness=1, padx=22, pady=20)
        panel.pack(fill="x")
        self.status_var = tk.StringVar(value="Checking for updates…")
        self.detail_var = tk.StringVar(value="Connecting to GitHub.")
        status_row = tk.Frame(panel, bg=PANEL)
        status_row.pack(fill="x")
        self.status_dot = tk.Label(status_row, text="●", bg=PANEL, fg=BLUE,
                                   font=("Segoe UI", 16, "bold"))
        self.status_dot.pack(side="left", padx=(0, 10))
        tk.Label(status_row, textvariable=self.status_var, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 16, "bold"), anchor="w").pack(side="left", fill="x", expand=True)
        tk.Label(panel, textvariable=self.detail_var, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9), anchor="w", justify="left",
                 wraplength=610).pack(fill="x", pady=(8, 19))

        versions = tk.Frame(panel, bg=PANEL)
        versions.pack(fill="x")
        current_card = tk.Frame(versions, bg=PANEL_ALT, highlightbackground=BORDER,
                                highlightthickness=1, padx=15, pady=13)
        current_card.pack(side="left", fill="x", expand=True, padx=(0, 7))
        latest_card = tk.Frame(versions, bg="#102F55", highlightbackground="#24558B",
                               highlightthickness=1, padx=15, pady=13)
        latest_card.pack(side="left", fill="x", expand=True, padx=(7, 0))
        self.current_var = tk.StringVar(value=f"Installed: {display_version(self.current_version)}")
        self.latest_var = tk.StringVar(value="Latest: Checking…")
        tk.Label(current_card, text="YOUR VERSION", bg=PANEL_ALT, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(current_card, textvariable=self.current_var, bg=PANEL_ALT, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(6, 0))
        tk.Label(latest_card, text="LATEST RELEASE", bg="#102F55", fg="#80B9FF",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(latest_card, textvariable=self.latest_var, bg="#102F55", fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(6, 0))

        # Progress area sits in its own blue-toned section.
        progress_area = tk.Frame(outer, bg=BG)
        progress_area.pack(fill="x", pady=(22, 0))
        progress_top = tk.Frame(progress_area, bg=BG)
        progress_top.pack(fill="x", pady=(0, 9))
        tk.Label(progress_top, text="UPDATE PROGRESS", bg=BG, fg="#80B9FF",
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self.progress_percent = tk.StringVar(value="")
        tk.Label(progress_top, textvariable=self.progress_percent, bg=BG, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(side="right")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Updater.Horizontal.TProgressbar",
                        troughcolor="#142B46", background=BLUE,
                        bordercolor="#142B46", lightcolor=BLUE,
                        darkcolor=BLUE, thickness=13)
        style.configure("Updater.Horizontal.TProgressbar", troughrelief="flat")
        self.progress = ttk.Progressbar(progress_area, style="Updater.Horizontal.TProgressbar",
                                         mode="determinate", maximum=100, value=0)
        self.progress.pack(fill="x")
        self.progress_label = tk.Label(progress_area, text="Waiting for release information…",
                                        bg=BG, fg=MUTED,
                                        font=("Segoe UI", 9), anchor="w")
        self.progress_label.pack(fill="x", pady=(8, 0))

        footer = tk.Frame(outer, bg=BG)
        footer.pack(fill="x", side="bottom", pady=(22, 0))
        self.update_btn = tk.Button(
            footer, text="  UPDATE NOW  ", command=self.start_update,
            bg=BLUE, fg="#FFFFFF", activebackground=BLUE_HOVER,
            activeforeground="#FFFFFF", relief="flat", bd=0,
            font=("Segoe UI", 10, "bold"), padx=19, pady=11,
            state="disabled", cursor="hand2")
        self.update_btn.pack(side="left")
        self.retry_btn = tk.Button(
            footer, text="Check again", command=self.check_updates,
            bg=PANEL_ALT, fg="#C7D9F0", activebackground="#193B60",
            activeforeground="#FFFFFF", relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"), padx=16, pady=11,
            state="disabled", cursor="hand2")
        self.retry_btn.pack(side="left", padx=(10, 0))
        self.cancel_btn = tk.Button(
            footer, text="Cancel", command=self.cancel_download,
            bg="#2A2033", fg="#FF9CA8", activebackground="#402638",
            activeforeground="#FFFFFF", relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"), padx=16, pady=11,
            state="disabled", cursor="hand2")
        self.cancel_btn.pack(side="left", padx=(10, 0))
        self.close_btn = tk.Button(
            footer, text="Close", command=self.close,
            bg=BG, fg=MUTED, activebackground="#142B46",
            activeforeground=TEXT, relief="flat", bd=0,
            font=("Segoe UI", 9), padx=16, pady=11, cursor="hand2")
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
        self.progress_label.configure(text="Searching the latest official stable release…")
        self.worker = threading.Thread(target=self.check_worker, daemon=True)
        self.worker.start()

    def check_worker(self):
        try:
            metadata = request_latest_release()
            self.events.put(('check_ok', read_local_version(), metadata['tag_name'], metadata['asset'], ''))
        except Exception as exc:
            cached = read_release_cache()
            if cached:
                note = 'GitHub could not be reached, so the updater is using its last saved release information. Retry later to check for a newer release.'
                self.events.put(('check_ok', read_local_version(), cached['tag_name'], cached['asset'], note))
            else:
                self.events.put(('error', 'Update check failed', self.describe_error(exc)))
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
        self.progress_label.configure(text="Preparing download…")
        self.status_var.set(f"Update available: {display_version(self.latest_tag)}")
        self.detail_var.set("Downloading the latest YVZTools update.")
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
            # The main app launches this updater and exits automatically. Allow
            # Windows a short hand-off window before attempting to replace the EXE.
            wait_deadline = time.monotonic() + 25
            while app_is_running():
                if self.cancel_event.is_set():
                    raise InterruptedError("Update cancelled while waiting for YVZNETMATH to close.")
                if time.monotonic() >= wait_deadline:
                    raise RuntimeError("YVZNETMATH.exe is still running. Close YVZTOOLS and retry.")
                time.sleep(0.4)
            req = urllib.request.Request(
                self.latest_asset["browser_download_url"],
                headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
            )
            with urllib.request.urlopen(req, timeout=25, context=SSL_CONTEXT) as response:
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
                self.events.put(("installed", self.latest_tag, True, "The update was checked, installed, and YVZTools was reopened."))
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
                        self.progress_label.configure(text=f"Downloaded {done / 1048576:.1f} MB of {total / 1048576:.1f} MB")
                        self.progress_percent.set(f"{percent:.0f}%")
                    else:
                        self.progress_label.configure(text=f"Downloaded {done / 1048576:.1f} MB")
                        self.progress_percent.set(f"{percent:.0f}%")
                elif kind == "check_ok":
                    _, current, latest, asset, cache_note = event
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
                    self.current_version = current
                    self.latest_tag = latest
                    self.latest_asset = asset
                    self.current_var.set(f"Installed version: {display_version(current)}")
                    self.latest_var.set(f"Latest version: {display_version(latest)}")
                    self.set_busy(False)
                    self.retry_btn.configure(state="normal")
                    if cache_note:
                        self.detail_var.set(cache_note)
                    if normalized_version(current) >= normalized_version(latest):
                        self.status_var.set("You're up to date!")
                        self.detail_var.set(cache_note or f"YVZTOOLS {display_version(current)} is already the latest stable release. This window will stay open until you close it.")
                        self.update_btn.configure(state="disabled")
                    else:
                        self.status_var.set(f"Update available: {display_version(latest)}")
                        self.detail_var.set(cache_note or f"Your installed version is {display_version(current)}. Select Update Now to download and install the official release.")
                        self.update_btn.configure(state="normal")
                    self.progress_label.configure(text="")
                    self.progress_percent.set("")
                elif kind == "installed":
                    _, tag, launched, detail = event
                    self.progress.stop()
                    self.progress.configure(value=100)
                    self.set_busy(False)
                    self.current_version = tag
                    self.current_var.set(f"Installed version: {display_version(tag)}")
                    self.latest_var.set(f"Latest version: {display_version(tag)}")
                    self.status_var.set("Update complete" if launched else "Update installed")
                    self.detail_var.set(detail)
                    self.update_btn.configure(state="disabled")
                    self.retry_btn.configure(state="normal")
                    self.progress_label.configure(text="Update installed successfully.")
                    self.progress_percent.set("100%")
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
