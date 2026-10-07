"""YVZTOOLS Installer — polished installer for the latest YVZTOOLS build."""
import os, re, sys, json, time, threading, urllib.request, subprocess
import tkinter as tk
import ssl
try:
    import certifi
except ImportError:
    certifi = None
from tkinter import filedialog, messagebox

GITHUB_REPO = "ItsYvesss/yvztoolsnet"
API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
APP_NAME = "YVZNETMATH.exe"
UPDATER_NAME = "YVZUPDATER.exe"

BG="#040714"; BG2="#0B1233"; TEXT="#F4F7FF"; MUTED="#91A1CC"
BLUE="#4A9BFF"; GREEN="#4BE3B0"; TRACK="#14204D"

def make_ssl_context():
    # Use certifi's CA bundle so Windows/PyInstaller builds can verify
    # GitHub HTTPS certificates reliably.
    if certifi:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()

SSL_CONTEXT = make_ssl_context()

def get_json(url):
    req=urllib.request.Request(url, headers={"User-Agent":"YVZTOOLS-Installer/3.6","Accept":"application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as r:
        return json.load(r)

class Installer(tk.Tk):
    W,H=680,460
    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.closing = False
        self.configure(bg=BG)
        sw,sh=self.winfo_screenwidth(),self.winfo_screenheight()
        self.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}")
        self.c=tk.Canvas(self,width=self.W,height=self.H,bg=BG,highlightthickness=0)
        self.c.pack()
        self.folder=os.path.join(os.path.expanduser("~"),"YVZTOOLS")
        self.state="choose"; self.pct=0.0
        self.msg="Choose where YVZTOOLS will be installed."
        self.sub="The installer will create the YVZTOOLS folder and download the latest build."
        self.t0=time.time()
        self.after(16,self.draw)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.destroy()

    def choose(self):
        p=filedialog.askdirectory(title="Choose YVZTOOLS installation folder",
                                  initialdir=os.path.dirname(self.folder))
        if p:
            self.folder=p if os.path.basename(p).upper()=="YVZTOOLS" else os.path.join(p,"YVZTOOLS")

    def install(self):
        if self.closing:
            return
        self.state="download"; self.msg="Preparing YVZTOOLS"; self.sub=f"Installing to {self.folder}"; self.pct=0
        threading.Thread(target=self.run,daemon=True).start()

    def ui(self,msg=None,sub=None,pct=None):
        def apply():
            if msg is not None: self.msg=msg
            if sub is not None: self.sub=sub
            if pct is not None: self.pct=max(0,min(1,pct))
        self.after(0,apply)

    def run(self):
        try:
            os.makedirs(self.folder,exist_ok=True)
            rel=get_json(API); tag=rel["tag_name"]
            assets={a["name"]:a for a in rel.get("assets",[])}
            if APP_NAME not in assets:
                raise RuntimeError("The latest release does not contain YVZNETMATH.exe.")
            wanted=[APP_NAME]
            if UPDATER_NAME in assets: wanted.append(UPDATER_NAME)

            total_files=len(wanted)
            for index,name in enumerate(wanted):
                url=assets[name]["browser_download_url"]
                dest=os.path.join(self.folder,name)
                self.ui(f"Downloading {name}",f"YVZTOOLS {tag} • {self.folder}")
                req=urllib.request.Request(url,headers={"User-Agent":"YVZTOOLS-Installer/3.6"})
                with urllib.request.urlopen(req,timeout=60,context=SSL_CONTEXT) as r, open(dest,"wb") as f:
                    total=int(r.headers.get("Content-Length") or 0); done=0
                    while True:
                        chunk=r.read(256*1024)
                        if not chunk: break
                        f.write(chunk); done+=len(chunk)
                        local=(done/total) if total else 0
                        self.ui(pct=(index+local)/total_files,
                                sub=f"YVZTOOLS {tag} • {done/1048576:.1f} MB")
            with open(os.path.join(self.folder,"version.txt"),"w",encoding="utf-8") as f:
                f.write(tag)
            self.ui("Installation complete","YVZTOOLS is ready • launching NetMath Space",1)
            self.after(1000,self.finish)
        except Exception as e:
            self.ui("Installation failed",str(e)[:140])
            self.after(100,self.fail)

    def finish(self):
        try:
            subprocess.Popen([os.path.join(self.folder,APP_NAME)],cwd=self.folder)
            self.destroy()
        except Exception as e:
            messagebox.showerror("YVZTOOLS Installer",f"Could not launch YVZNETMATH.exe:\n{e}")

    def fail(self):
        messagebox.showerror("YVZTOOLS Installer",self.msg+"\n\n"+self.sub)

    def _set_close_hover(self, value):
        self._close_hover = value
        self.draw()

    def draw(self):
        c=self.c; now=time.time(); el=now-self.t0; c.delete("all")
        for y in range(0,self.H,5):
            t=y/self.H
            def mix(a,b,t):
                aa=[int(a[i:i+2],16) for i in (1,3,5)]
                bb=[int(b[i:i+2],16) for i in (1,3,5)]
                return "#%02x%02x%02x"%tuple(int(x+(z-x)*t) for x,z in zip(aa,bb))
            c.create_rectangle(0,y,self.W,y+5,fill=mix(BG,BG2,t),outline="")
        for i in range(42):
            x=(i*137+el*18)%self.W; y=(i*83)%self.H
            c.create_oval(x,y,x+2,y+2,fill="#1A3A72",outline="")
        c.create_rectangle(0,0,self.W,self.H,outline="#20356F")
        # Custom close button because the installer uses a borderless window.
        close_hover = getattr(self, "_close_hover", False)
        c.create_rectangle(self.W-62, 22, self.W-24, 60,
                           fill="#18264F" if close_hover else "#101A3A",
                           outline="#4A6DBA", tags="close")
        c.create_text(self.W-43, 41, text="×", fill=TEXT,
                      font=("Segoe UI", 18), tags="close")
        c.tag_bind("close", "<Enter>", lambda e: self._set_close_hover(True))
        c.tag_bind("close", "<Leave>", lambda e: self._set_close_hover(False))
        c.tag_bind("close", "<Button-1>", lambda e: self.close())
        c.create_rectangle(0,0,self.W,4,fill=BLUE,outline="")
        c.create_text(48,54,anchor="w",text="YVZTOOLS",fill=TEXT,font=("Segoe UI Black",30))
        c.create_text(50,84,anchor="w",text="INSTALLER  •  V3.6",fill=BLUE,font=("Segoe UI Semibold",10))
        c.create_text(48,136,anchor="w",text=self.msg,fill=TEXT,font=("Segoe UI Semibold",17))
        c.create_text(48,165,anchor="w",text=self.sub,fill=MUTED,font=("Segoe UI",9))
        c.create_text(48,211,anchor="w",text="INSTALL LOCATION",fill=MUTED,font=("Segoe UI Semibold",8))
        c.create_rectangle(48,225,632,267,fill="#080F28",outline=TRACK)
        c.create_text(62,246,anchor="w",text=self.folder,fill=TEXT,font=("Segoe UI",9))
        if self.state=="choose":
            c.create_rectangle(48,300,632,350,fill=BLUE,outline="",tags="install")
            c.create_text(340,325,text="INSTALL YVZTOOLS  →",fill="#FFFFFF",font=("Segoe UI Semibold",11))
            c.tag_bind("install","<Button-1>",lambda e:self.install())
            c.create_rectangle(48,362,270,405,fill="#101A3A",outline=TRACK,tags="choose")
            c.create_text(159,383,text="CHOOSE FOLDER",fill=TEXT,font=("Segoe UI Semibold",9))
            c.tag_bind("choose","<Button-1>",lambda e:self.choose())
        else:
            y=325
            c.create_line(48,y,632,y,fill=TRACK,width=10,capstyle="round")
            c.create_line(48,y,48+584*self.pct,y,fill=GREEN,width=10,capstyle="round")
            c.create_text(48,350,anchor="w",text=f"{int(self.pct*100)}%",fill=GREEN,font=("Segoe UI Semibold",9))
            c.create_text(632,350,anchor="e",text="YVZTOOLS • SECURE INSTALL",fill=MUTED,font=("Segoe UI",8))
        c.create_text(48,430,anchor="w",text="YVZTOOLS NETMATH SPACE",fill=MUTED,font=("Segoe UI",8))
        self.after(16,self.draw)

if __name__=="__main__":
    app=Installer()
    app.bind("<Escape>", lambda e: app.close())
    app.mainloop()
