"""YVZTOOLS Updater - downloads the newest YVZNETMATH.exe from your GitHub Releases."""
import os, re, sys, json, time, math, subprocess, threading, urllib.request
import tkinter as tk

# ====== EDIT THESE TWO LINES ======
GITHUB_REPO = "ItsYvesss/yvztoolsnet"
ASSET_NAME = "YVZNETMATH.exe"             # file name attached to each Release
# ==================================

APP_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
APP_EXE = os.path.join(APP_DIR, ASSET_NAME)
VERSION_FILE = os.path.join(APP_DIR, "version.txt")
API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

BG, BG2 = "#050817", "#0B1233"
TEXT, MUTED, ACCENT, ACCENT2, TRACK, OK, BAD = "#F4F7FF", "#91A1CC", "#4A9BFF", "#9A6BFF", "#14204D", "#4BE3B0", "#FF6B8A"


def parse(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")) or (0,)


def local_version():
    try:
        return open(VERSION_FILE, encoding="utf-8").read().strip() or "0"
    except OSError:
        return "0"


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "yvz-updater", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


class Updater(tk.Tk):
    W, H = 560, 320

    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{self.W}x{self.H}+{(sw - self.W) // 2}+{(sh - self.H) // 2}")
        self.configure(bg=BG)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        self.c = tk.Canvas(self, width=self.W, height=self.H, bg=BG, highlightthickness=0, bd=0)
        self.c.pack()
        self.title_txt, self.sub_txt, self.right_txt = "Checking for updates", "Connecting to GitHub", ""
        self.pct = None          # None = indeterminate
        self.state_col = ACCENT
        self.t0 = time.time()
        self.closing = False
        self.after(16, self.draw)
        threading.Thread(target=self.run, daemon=True).start()

    # ---- UI ----
    def draw(self):
        c = self.c
        c.delete("all")
        el = time.time() - self.t0
        for i in range(0, self.H, 5):
            t = i / self.H
            c.create_rectangle(0, i, self.W, i + 5, outline="", fill=self._mix(BG, BG2, t))
        c.create_rectangle(0, 0, self.W, 3, outline="", fill=self.state_col)
        c.create_rectangle(0, 0, self.W, self.H, outline="#1B2A63", width=1)

        c.create_text(52, 35, anchor="w", text="YVZTOOLS", fill=TEXT, font=("Segoe UI Black", 20))
        c.create_text(52, 59, anchor="w", text="NETMATH  •  SMART UPDATER", fill=ACCENT, font=("Segoe UI Semibold", 9))

        # spinner
        cx, cy = self.W - 48, 44
        c.create_oval(cx - 14, cy - 14, cx + 14, cy + 14, outline=TRACK, width=3)
        if self.pct is None or self.pct < 1:
            c.create_arc(cx - 14, cy - 14, cx + 14, cy + 14, start=(el * 280) % 360, extent=90,
                         style="arc", outline=self.state_col, width=3)
        else:
            c.create_arc(cx - 14, cy - 14, cx + 14, cy + 14, start=0, extent=359, style="arc", outline=self.state_col, width=3)

        c.create_text(40, 104, anchor="w", text=self.title_txt, fill=TEXT, font=("Segoe UI Semibold", 15))
        c.create_text(40, 132, anchor="w", text=self.sub_txt, fill=MUTED, font=("Segoe UI", 9))

        x0, x1, y = 40, self.W - 40, 220
        c.create_line(x0, y, x1, y, width=8, capstyle="round", fill=TRACK)
        if self.pct is None:
            span = (x1 - x0) * 0.28
            pos = (math.sin(el * 2.2) * 0.5 + 0.5) * ((x1 - x0) - span)
            c.create_line(x0 + pos, y, x0 + pos + span, y, width=8, capstyle="round", fill=self.state_col)
        elif self.pct > 0.005:
            xe = x0 + (x1 - x0) * min(1.0, self.pct)
            c.create_line(x0, y, xe, y, width=14, capstyle="round", fill=self._mix(TRACK, self.state_col, 0.25))
            c.create_line(x0, y, xe, y, width=8, capstyle="round", fill=self.state_col)
            c.create_oval(xe - 4, y - 4, xe + 4, y + 4, fill=TEXT, outline="")
        c.create_text(x1, y + 26, anchor="e", text=self.right_txt, fill=MUTED, font=("Segoe UI", 9))
        if self.pct is not None:
            c.create_text(x0, y + 26, anchor="w", text=f"{int(min(1.0, self.pct) * 100)}%", fill=ACCENT, font=("Segoe UI Semibold", 9))
        if not self.closing or time.time() < self.closing:
            self.after(16, self.draw)

    @staticmethod
    def _mix(a, b, t):
        a, b = a.lstrip("#"), b.lstrip("#")
        ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
        cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
        return "#%02x%02x%02x" % tuple(int(x + (y - x) * t) for x, y in zip(ca, cb))

    def say(self, title, sub="", right="", pct="keep", color=None):
        self.title_txt, self.sub_txt, self.right_txt = title, sub, right
        if pct != "keep":
            self.pct = pct
        if color:
            self.state_col = color

    def finish(self, title, sub="", color=OK, launch=False, delay=1.8):
        self.say(title, sub, "", 1.0, color)
        if launch and os.path.exists(APP_EXE):
            try:
                subprocess.Popen([APP_EXE], cwd=APP_DIR)
            except Exception:
                pass
        self.closing = time.time() + delay
        self.after(int(delay * 1000), self.destroy)

    # ---- logic ----
    def run(self):
        try:
            rel = http_json(API)
            latest = rel["tag_name"]
            cur = local_version()
            if parse(latest) <= parse(cur) and os.path.exists(APP_EXE):
                return self.finish("You're up to date", f"Installed version: {cur}", launch=True, delay=1.4)
            asset = next((a for a in rel.get("assets", []) if a["name"] == ASSET_NAME), None)
            if not asset:
                return self.finish("Update failed", f"{ASSET_NAME} not found in release {latest}", BAD, launch=True, delay=4)

            installed = "not installed" if cur == "0" else cur
            self.say(f"Downloading {latest}", f"{installed}  ->  {latest}", "", 0.0, ACCENT)
            subprocess.run(["taskkill", "/IM", ASSET_NAME, "/F"], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            time.sleep(0.8)

            tmp = APP_EXE + ".new"
            req = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "yvz-updater"})
            with urllib.request.urlopen(req, timeout=30) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done, t_start = 0, time.time()
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    speed = done / max(time.time() - t_start, 0.1) / 1048576
                    self.say(f"Downloading {latest}", f"{installed}  ->  {latest}",
                             f"{done / 1048576:.1f} / {total / 1048576:.1f} MB  -  {speed:.1f} MB/s",
                             (done / total) if total else None)
            if total and os.path.getsize(tmp) != total:
                raise IOError("Download incomplete")

            self.say("Installing update", "Replacing old version...", "", 1.0, ACCENT2)
            bak = APP_EXE + ".bak"
            if os.path.exists(APP_EXE):
                if os.path.exists(bak):
                    os.remove(bak)
                os.replace(APP_EXE, bak)
            os.replace(tmp, APP_EXE)
            open(VERSION_FILE, "w", encoding="utf-8").write(latest)
            self.finish("Updated!", f"Now on {latest} - launching...", OK, launch=True)
        except Exception as e:
            self.finish("Update failed", str(e)[:70] + "  -  starting installed version", BAD, launch=True, delay=4)


if __name__ == "__main__":
    Updater().mainloop()
