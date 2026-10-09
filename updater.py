"""YVZTOOLS Updater — polished updater with a cinematic vault handoff."""
import os, re, sys, json, time, math, subprocess, threading, urllib.request
import tkinter as tk
import ssl
try:
    import certifi
except ImportError:
    certifi = None

GITHUB_REPO = "ItsYvesss/yvztoolsnet"
ASSET_NAME = "YVZNETMATH.exe"
APP_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
APP_EXE = os.path.join(APP_DIR, ASSET_NAME)
VERSION_FILE = os.path.join(APP_DIR, "version.txt")
API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/v3.9"

BG, BG2 = "#030303", "#101010"
TEXT, MUTED = "#FFFFFF", "#A6A6A6"
ACCENT, ACCENT2 = "#FFFFFF", "#777777"
TRACK, OK, BAD = "#262626", "#FFFFFF", "#D0D0D0"
UPDATER_VERSION = "3.9"


def parse(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")) or (0,)


def local_version():
    try:
        return open(VERSION_FILE, encoding="utf-8").read().strip() or "0"
    except OSError:
        return "0"


def ssl_context():
    return ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()

SSL_CONTEXT = ssl_context()

def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": f"YVZTOOLS-Updater/{UPDATER_VERSION}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as r:
        return json.load(r)


class Updater(tk.Tk):
    W, H = 620, 390

    def __init__(self):
        super().__init__()
        self.title("YVZTOOLS Updater v3.9")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _event: self.destroy())
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}")
        self.configure(bg=BG)
        self.c = tk.Canvas(self, width=self.W, height=self.H, bg=BG, highlightthickness=0, bd=0)
        self.c.pack()
        self.title_txt = "YVZTOOLS"
        self.sub_txt = "SMART UPDATE ENGINE • VERIFYING RELEASE CHANNEL"
        self.right_txt = ""
        self.pct = None
        self.state_col = ACCENT
        self.phase = "work"
        self.t0 = time.time()
        self.finish_launch = False
        self.launch_scheduled = False
        import random
        rnd = random.Random(34)
        self.stars = [[rnd.uniform(0,self.W), rnd.uniform(0,self.H), rnd.choice([1,1,2]), rnd.uniform(.2,.7), rnd.uniform(0,6.28)] for _ in range(90)]
        try:
            self.attributes("-topmost", True)
            self.attributes("-alpha", 0.0)
        except Exception:
            pass
        self.after(16, self.draw)
        threading.Thread(target=self.run, daemon=True).start()

    @staticmethod
    def _mix(a,b,t):
        a,b=a.lstrip("#"),b.lstrip("#")
        t=max(0,min(1,t))
        ca=[int(a[i:i+2],16) for i in (0,2,4)]
        cb=[int(b[i:i+2],16) for i in (0,2,4)]
        return "#%02x%02x%02x"%tuple(int(x+(y-x)*t) for x,y in zip(ca,cb))

    def ui_state(self, title, sub="", right="", pct="keep", color=None):
        def apply():
            self.title_txt, self.sub_txt, self.right_txt = title, sub, right
            if pct != "keep": self.pct = pct
            if color: self.state_col = color
        self.after(0, apply)

    def start_finish(self, title, sub, color=OK, launch=True):
        def apply():
            self.title_txt, self.sub_txt = title, sub
            self.right_txt = "SECURE • READY"
            self.pct = 1.0
            self.state_col = color
            self.phase = "vault"
            self.finish_launch = launch
            self.vault_started = time.time()
        self.after(0, apply)

    def draw(self):
        c=self.c
        c.delete("all")
        now=time.time()
        el=now-self.t0
        for i in range(0,self.H,5):
            c.create_rectangle(0,i,self.W,i+5,outline="",fill=self._mix(BG,BG2,i/self.H))
        import math
        for s in self.stars:
            s[0]-=s[3]
            if s[0] < -5: s[0]=self.W+5
            tw=.5+.5*math.sin(el*2+s[4])
            col=self._mix(BG2,self.state_col,.15+.5*tw)
            c.create_oval(s[0]-s[2],s[1]-s[2],s[0]+s[2],s[1]+s[2],fill=col,outline="")
        c.create_rectangle(0,0,self.W,self.H,outline="#20356F",width=1)
        c.create_rectangle(0,0,self.W,3,outline="",fill=self.state_col)

        if self.phase != "vault":
            cx,cy=70,62
            c.create_oval(cx-25,cy-25,cx+25,cy+25,outline=TRACK,width=4)
            c.create_arc(cx-25,cy-25,cx+25,cy+25,start=(el*180)%360,extent=105,outline=self.state_col,width=4)
            c.create_oval(cx-15,cy-15,cx+15,cy+15,outline=ACCENT2,width=1)
            c.create_text(110,42,anchor="w",text="YVZTOOLS",fill=TEXT,font=("Segoe UI Black",22))
            c.create_text(110,67,anchor="w",text="SMART UPDATER",fill=ACCENT,font=("Segoe UI Semibold",9))
            c.create_text(110,86,anchor="w",text="NETMATH SPACE  •  V3.9",fill=MUTED,font=("Segoe UI",8))
            c.create_text(42,126,anchor="w",text=self.title_txt,fill=TEXT,font=("Segoe UI Semibold",16))
            c.create_text(42,152,anchor="w",text=self.sub_txt,fill=MUTED,font=("Segoe UI",9))

            x0,x1,y=42,self.W-42,278
            c.create_line(x0,y,x1,y,width=9,capstyle="round",fill=TRACK)
            if self.pct is None:
                span=(x1-x0)*.25
                pos=(math.sin(el*2.5)*.5+.5)*((x1-x0)-span)
                c.create_line(x0+pos,y,x0+pos+span,y,width=9,capstyle="round",fill=self.state_col)
            else:
                xe=x0+(x1-x0)*min(1,max(0,self.pct))
                c.create_line(x0,y,xe,y,width=16,capstyle="round",fill=self._mix(TRACK,self.state_col,.28))
                c.create_line(x0,y,xe,y,width=9,capstyle="round",fill=self.state_col)
                c.create_oval(xe-4,y-4,xe+4,y+4,fill=TEXT,outline="")
            if self.pct is not None:
                c.create_text(x0,y+28,anchor="w",text=f"{int(self.pct*100)}%",fill=self.state_col,font=("Segoe UI Semibold",9))
            c.create_text(x1,y+28,anchor="e",text=self.right_txt,fill=MUTED,font=("Segoe UI",9))
            c.create_text(42,350,anchor="w",text="YVZTOOLS  •  SECURE UPDATE CHANNEL",fill=MUTED,font=("Segoe UI",8))
        else:
            start=getattr(self,"vault_started",now)
            v=min(1,max(0,(now-start)/2.6))
            ease=1-(1-v)**3
            cx,cy=self.W/2,160
            pulse=1+0.04*math.sin(now*6)
            c.create_oval(cx-118*pulse,cy-118*pulse,cx+118*pulse,cy+118*pulse,outline=self._mix(BG2,self.state_col,.55),width=2)
            for rad,col,spd in ((120,self.state_col,70),(94,ACCENT2,-100),(66,OK,140)):
                c.create_arc(cx-rad,cy-rad,cx+rad,cy+rad,start=(now*spd)%360,extent=68,style="arc",outline=col,width=3)
            gap=115*ease
            left=(cx-8-gap,cy-84,cx-8,cy+84)
            right=(cx+8,cy-84,cx+8+gap,cy+84)
            c.create_rectangle(left,fill=self._mix(BG2,self.state_col,.18),outline=self.state_col,width=2)
            c.create_rectangle(right,fill=self._mix(BG2,self.state_col,.18),outline=self.state_col,width=2)
            c.create_text(cx,cy-8,text="YVZTOOLS",fill=TEXT,font=("Segoe UI Black",28))
            c.create_text(cx,cy+31,text="VAULT OPEN",fill=OK,font=("Segoe UI Semibold",10))
            c.create_text(cx,286,text="Update installed  •  launching control center",fill=MUTED,font=("Segoe UI",9))
            c.create_line(135,322,485,322,fill=TRACK,width=6,capstyle="round")
            c.create_line(135,322,135+350*ease,322,fill=OK,width=6,capstyle="round")
            if v >= 1 and not self.launch_scheduled:
                self.launch_scheduled=True
                if self.finish_launch and os.path.exists(APP_EXE):
                    try: subprocess.Popen([APP_EXE],cwd=APP_DIR)
                    except Exception: pass
                self.after(400,self.destroy)

        if not (self.phase=="vault" and self.launch_scheduled):
            self.after(16,self.draw)

    def run(self):
        try:
            rel=http_json(API)
            latest=rel["tag_name"]
            cur=local_version()
            # Always refresh from the pinned v3.9 release. version.txt can say v3.9
            # even when an older EXE was copied over it, so version-only checks can
            # accidentally skip the actual UI update.
            asset=next((a for a in rel.get("assets",[]) if a["name"]==ASSET_NAME),None)
            if not asset:
                self.ui_state("Update unavailable",f"{ASSET_NAME} is missing from {latest}","",None,BAD)
                self.start_finish("YVZTOOLS READY","Could not update  •  opening installed version",BAD,True)
                return

            installed="not installed" if cur=="0" else cur
            self.ui_state(f"DOWNLOADING {latest.upper()}",f"{installed}  →  {latest}","CONNECTING TO GITHUB",0.0,ACCENT)
            tmp=APP_EXE+".new"
            req=urllib.request.Request(asset["browser_download_url"],headers={"User-Agent":f"YVZTOOLS-Updater/{UPDATER_VERSION}"})
            with urllib.request.urlopen(req,timeout=60,context=SSL_CONTEXT) as r, open(tmp,"wb") as f:
                total=int(r.headers.get("Content-Length") or 0)
                done,t0=0,time.time()
                while True:
                    chunk=r.read(256*1024)
                    if not chunk: break
                    f.write(chunk); done+=len(chunk)
                    speed=done/max(time.time()-t0,.1)/1048576
                    self.ui_state(f"DOWNLOADING {latest.upper()}",f"{installed}  →  {latest}",f"{done/1048576:.1f} / {(total/1048576):.1f} MB  •  {speed:.1f} MB/s",(done/total) if total else None,ACCENT)

            if total and os.path.getsize(tmp)!=total:
                raise IOError("Download incomplete")

            self.ui_state("INSTALLING UPDATE","Closing YVZTOOLS and replacing the old app…","SWAP + VERIFY",1.0,ACCENT2)
            subprocess.run(["taskkill","/IM",ASSET_NAME,"/F"],capture_output=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            time.sleep(.8)
            bak=APP_EXE+".bak"
            if os.path.exists(APP_EXE):
                if os.path.exists(bak): os.remove(bak)
                os.replace(APP_EXE,bak)
            os.replace(tmp,APP_EXE)
            with open(VERSION_FILE,"w",encoding="utf-8") as f: f.write(latest)
            self.start_finish("UPDATE COMPLETE",f"YVZTOOLS {latest} installed  •  opening vault",OK,True)
        except Exception as e:
            msg=str(e).replace("\n"," ")[:80]
            self.ui_state("Update failed",msg,"FALLBACK",1.0,BAD)
            self.start_finish("YVZTOOLS READY","Update failed  •  launching installed version",BAD,True)


if __name__=="__main__":
    Updater().mainloop()
