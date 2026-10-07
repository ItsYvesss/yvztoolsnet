import os
import sys
import json
import time
import threading
import subprocess
import traceback
import importlib.util
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path

APP_NAME = 'YVZTOOLS — NetMath Space'
VERSION = '2.9.9 GUI'
BASE = Path(__file__).resolve().parent
CORE_PATH = BASE / 'yvznetmath_core.py'

spec = importlib.util.spec_from_file_location('yvznetmath_core', CORE_PATH)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

BG = '#070B1A'
PANEL = '#0D1330'
PANEL2 = '#121A3F'
TEXT = '#EAF0FF'
MUTED = '#8E9BCB'
BLUE = '#45A3FF'
PURPLE = '#A66BFF'
CYAN = '#55D7FF'
GREEN = '#45E0A8'
RED = '#FF6B8A'


class RoundedButton(tk.Canvas):
    """Small theme-aware rounded button with hover/pressed animation."""
    def __init__(self, master, text, command, fill, hover, fg='white', height=38, radius=16, **kwargs):
        super().__init__(master, height=height, highlightthickness=0, bd=0,
                         bg=master.cget('bg'), cursor='hand2', **kwargs)
        self.text = text
        self.command = command
        self.fill = fill
        self.hover = hover
        self.fg = fg
        self.height = height
        self.radius = radius
        self.enabled = True
        self._hover = False
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<ButtonPress-1>', self._press)
        self.bind('<ButtonRelease-1>', self._release)
        self.bind('<Configure>', lambda e: self._draw())
        self._draw()

    def _enter(self, _=None):
        if self.enabled:
            self._hover = True
            self._draw()

    def _leave(self, _=None):
        self._hover = False
        self._draw()

    def _press(self, _=None):
        if self.enabled:
            self._draw(pressed=True)

    def _release(self, _=None):
        if self.enabled:
            self._draw()
            if self.command:
                self.command()

    def _draw(self, pressed=False):
        self.delete('all')
        w = max(self.winfo_width(), 80)
        h = max(self.winfo_height(), self.height)
        fill = self.hover if self._hover else self.fill
        if not self.enabled:
            fill = PANEL2
        yoff = 1 if pressed and self.enabled else 0
        r = min(self.radius, h // 2 - 1, w // 2 - 1)
        # Rounded rectangle made from a central rectangle + four circles.
        self.create_rectangle(r, yoff, w-r, h-yoff, fill=fill, outline='')
        self.create_rectangle(0, r+yoff, w, h-r-yoff, fill=fill, outline='')
        for x, y in ((r, r+yoff), (w-r, r+yoff), (r, h-r-yoff), (w-r, h-r-yoff)):
            self.create_oval(x-r, y-r, x+r, y+r, fill=fill, outline='')
        self.create_text(w/2, h/2+yoff, text=self.text,
                         fill=self.fg if self.enabled else MUTED,
                         font=('Segoe UI Semibold', 9))

    def state(self, states=None):
        if states:
            if 'disabled' in states:
                self.enabled = False
            if '!disabled' in states:
                self.enabled = True
            self._draw()


class SpaceBackground(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, highlightthickness=0, bd=0, **kwargs)
        self.master = master
        self.stars = []
        self.t = 0
        self.running = True
        self._seed_stars()
        self._bw, self._bh = 900, 650
        self.bind('<Configure>', self._on_resize)
        self.after(30, self.animate)

    def _on_resize(self, e):
        # Only remember the size; the animation loop repaints. Redrawing here on every
        # drag event is what made resizing laggy/stuck.
        self._bw, self._bh = e.width, e.height

    def _seed_stars(self):
        import random
        self.stars = []
        for i in range(95):
            self.stars.append([
                random.uniform(0, 1200), random.uniform(0, 900),
                random.choice([1, 1, 1, 2]),
                random.uniform(0.15, 0.65),
                random.uniform(0, 6.28),
            ])

    def animate(self):
        if not self.running:
            return
        self.t += 1
        self.draw()
        self.after(30, self.animate)

    def stop_animation(self):
        self.running = False

    def draw(self):
        self.delete('all')
        w = max(self._bw, 300)
        h = max(self._bh, 300)

        theme = getattr(self.master, 'theme_name', 'dark')
        palettes = {
            'dark': ([('#040714',0.0),('#071129',.25),('#0B1433',.52),('#17103A',.78),('#06091C',1.0)], '#77A5FF','#254BA5','#6337A0'),
            'pink': ([('#FFF8FC',0.0),('#FFF1F7',.25),('#FFE8F1',.55),('#FFF7FB',1.0)], '#E88CAF','#F4B8D0','#E5A4C1'),
            'hacker': ([('#010302',0.0),('#031008',.3),('#04160A',.62),('#020905',1.0)], '#39FF88','#0B5E31','#168C48'),
            'red': ([('#070203',0.0),('#130407',.3),('#22070B',.62),('#090304',1.0)], '#FF526A','#741526','#9B263E')
        }
        bands, star, arc1, arc2 = palettes.get(theme, palettes['dark'])

        for i in range(len(bands) - 1):
            y0 = int(h * bands[i][1])
            y1 = int(h * bands[i + 1][1])
            self.create_rectangle(0, y0, w, y1, fill=bands[i][0], outline='')

        # Slow parallax stars. The phase creates a subtle twinkle.
        import math
        for s in self.stars:
            x, y, r, speed, phase = s
            xx = (x - self.t * speed * 1.2) % (w + 20) - 10
            yy = (y + math.sin(self.t * 0.012 + phase) * 7) % h
            twinkle = 0.65 + 0.35 * math.sin(self.t * 0.06 + phase)
            rr = max(1, r + (1 if twinkle > .92 else 0))
            self.create_oval(xx-rr, yy-rr, xx+rr, yy+rr, fill=star, outline='')

        # Moving nebula/orbit accents.
        drift = math.sin(self.t * 0.008) * 18
        self.create_oval(-180 + drift, h-300, 340 + drift, h+230,
                         outline=arc1, width=2)
        self.create_oval(w-360-drift, -160, w+190-drift, 380,
                         outline=arc2, width=2)
        self.create_oval(w*.50+drift, h*.16, w*.98+drift, h*.92,
                         outline=arc1, width=1)

        # Tiny shooting-star streak every so often.
        if (self.t // 8) % 75 == 0:
            sx = (self.t * 4) % max(w, 1)
            sy = 100 + (self.t * 2) % max(int(h*.55), 1)
            self.create_line(sx, sy, sx+34, sy+9,
                             fill={'dark':'#B9D7FF','pink':'#F1A8C5','hacker':'#6DFFAA','red':'#FF8797'}.get(theme, '#B9D7FF'), width=2)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry('1100x700')
        self.minsize(780, 600)
        self.resizable(True, True)
        self._fullscreen = False
        self.bind('<F11>', self._toggle_fullscreen)
        self.bind('<Escape>', lambda e: self._toggle_fullscreen(force=False) if self._fullscreen else None)
        self.configure(bg=BG)
        # YVZTOOLS square blue logo for the window/taskbar icon.
        try:
            self.iconbitmap(str(BASE / 'yvztools.ico'))
        except Exception:
            pass
        self.protocol('WM_DELETE_WINDOW', self.on_exit)
        self.last_extracted = None
        self.last_tab = None
        self.chrome_ok = False
        self.busy = False
        self._status_check_running = False
        self.theme_name = core.load_config().get('theme', 'dark')
        self.themes = {
            'dark': {
                'label':'🌌 SPACE BLUE', 'BG':'#050817','PANEL':'#0B1230','PANEL2':'#101A42',
                'TEXT':'#F2F6FF','MUTED':'#91A1CC','ACCENT':'#4A9BFF',
                'PURPLE':'#9A6BFF','CYAN':'#61D8FF','GREEN':'#4BE3B0','BORDER':'#263C82'
            },
            'pink': {
                'label':'🌸 COTTON CANDY', 'BG':'#FFF7FB','PANEL':'#FFF0F6','PANEL2':'#FFE4EF',
                'TEXT':'#3B2130','MUTED':'#9C6B80','ACCENT':'#E85D97',
                'PURPLE':'#A66AE8','CYAN':'#D94D8E','GREEN':'#3B9D78','BORDER':'#F0B2CA'
            },
            'hacker': {
                'label':'☠ HACKER GREEN', 'BG':'#020604','PANEL':'#06110A','PANEL2':'#0A1B10',
                'TEXT':'#D7FFE4','MUTED':'#6EA77D','ACCENT':'#19E66B',
                'PURPLE':'#00B84A','CYAN':'#59FF9A','GREEN':'#39FF88','BORDER':'#135E32'
            },
            'red': {
                'label':'🔥 CRIMSON', 'BG':'#090304','PANEL':'#190608','PANEL2':'#260A0E',
                'TEXT':'#FFF1F2','MUTED':'#B9868D','ACCENT':'#F0445E',
                'PURPLE':'#C83EAA','CYAN':'#FF7586','GREEN':'#58D89A','BORDER':'#6F1826'
            }
        }
        self._apply_theme_constants()
        self._build_styles()
        self._build_ui()
        self.refresh_status()
        # refresh_status schedules its own lightweight background polling.

    def _toggle_fullscreen(self, event=None, force=None):
        self._fullscreen = (not self._fullscreen) if force is None else force
        self.attributes('-fullscreen', self._fullscreen)

    def _apply_theme_constants(self):
        global BG, PANEL, PANEL2, TEXT, MUTED, BLUE, PURPLE, CYAN, GREEN, RED
        t = self.themes.get(self.theme_name, self.themes['dark'])
        BG, PANEL, PANEL2 = t['BG'], t['PANEL'], t['PANEL2']
        TEXT, MUTED = t['TEXT'], t['MUTED']
        BLUE, PURPLE, CYAN, GREEN = t['ACCENT'], t['PURPLE'], t['CYAN'], t['GREEN']
        RED = '#D94F72' if self.theme_name == 'pink' else '#FF6B8A'

    def toggle_theme(self):
        # Theme selector shown from the main control deck.
        win = tk.Toplevel(self)
        win.title('YVZTOOLS • Choose Theme')
        win.geometry('430x330')
        win.resizable(False, False)
        win.configure(bg=BG)
        try:
            win.transient(self)
            win.grab_set()
        except Exception:
            pass

        tk.Label(win, text='CHOOSE YOUR YVZTOOLS THEME',
                 bg=BG, fg=TEXT, font=('Segoe UI Black', 15)).pack(pady=(20, 4))
        tk.Label(win, text='Pick a style for the entire control deck',
                 bg=BG, fg=MUTED, font=('Segoe UI', 9)).pack(pady=(0, 14))

        def choose(name):
            self.theme_name = name
            cfg = core.load_config()
            cfg['theme'] = name
            core.save_config(cfg)
            win.destroy()
            for child in list(self.winfo_children()):
                child.destroy()
            self._apply_theme_constants()
            self.configure(bg=BG)
            self._build_styles()
            self._build_ui()
            self.refresh_status()

        for name in ('dark', 'pink', 'hacker', 'red'):
            t = self.themes[name]
            card = tk.Frame(win, bg=t['PANEL'], highlightthickness=1,
                            highlightbackground=t['BORDER'])
            card.pack(fill='x', padx=28, pady=5, ipady=4)
            btn = tk.Button(card, text=t['label'], command=lambda x=name: choose(x),
                            bg=t['PANEL2'], fg=t['TEXT'], activebackground=t['ACCENT'],
                            activeforeground='white', relief='flat', bd=0,
                            font=('Segoe UI Semibold', 9), cursor='hand2')
            btn.pack(fill='x', padx=7, pady=6)


    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TLabel', background=PANEL, foreground=TEXT, font=('Segoe UI', 9))
        style.configure('Muted.TLabel', background=PANEL, foreground=MUTED, font=('Segoe UI', 8))
        style.configure('Title.TLabel', background=BG, foreground=TEXT, font=('Segoe UI Semibold', 19))
        style.configure('Sub.TLabel', background=BG, foreground=MUTED, font=('Segoe UI', 8))
        style.configure('Card.TFrame', background=PANEL)
        style.configure('Card2.TFrame', background=PANEL2)
        style.configure('Accent.TButton', font=('Segoe UI Semibold', 8), foreground='white', background=BLUE, padding=(8, 6), borderwidth=0)
        style.map('Accent.TButton', background=[('active', CYAN), ('disabled', PANEL2)])
        style.configure('Purple.TButton', font=('Segoe UI Semibold', 8), foreground='white', background=PURPLE, padding=(8, 6), borderwidth=0)
        style.map('Purple.TButton', background=[('active', CYAN), ('disabled', PANEL2)])
        style.configure('Soft.TButton', font=('Segoe UI Semibold', 8), foreground=TEXT, background=PANEL2, padding=(8, 6), borderwidth=0)
        style.map('Soft.TButton', background=[('active', BLUE), ('disabled', PANEL)])

    def _build_ui(self):
        bg = SpaceBackground(self)
        bg.place(relx=0, rely=0, relwidth=1, relheight=1)

        border = self.themes[self.theme_name]['BORDER']

        # Header
        top = tk.Frame(self, bg=BG)
        self.grid_columnconfigure(0, weight=1, minsize=270, uniform='cols')
        self.grid_columnconfigure(1, weight=3, uniform='cols')
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        top.grid(row=0, column=0, columnspan=2, sticky='ew', padx=26, pady=(14, 6))
        title_row = tk.Frame(top, bg=BG)
        title_row.pack(fill='x')
        tk.Label(title_row, text='YVZTOOLS', bg=BG, fg=TEXT,
                 font=('Segoe UI Black', 22)).pack(side='left')
        tk.Label(title_row, text='  NETMATH SPACE', bg=BG, fg=BLUE,
                 font=('Segoe UI Semibold', 11)).pack(side='left', pady=(7, 0))
        tk.Label(title_row, text='V2.9.9', bg=PANEL2, fg=CYAN,
                 font=('Segoe UI Semibold', 8), padx=10, pady=4).pack(side='right', pady=5)
        tk.Label(top, text='Desktop control center  •  Chrome + Gemini  •  fast math workflow',
                 bg=BG, fg=MUTED, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 3))

        # Main two-column layout
        left = tk.Frame(self, bg=PANEL, highlightbackground=border, highlightthickness=1)
        left.grid(row=1, column=0, sticky='nsew', padx=(26, 8), pady=(0, 20))
        left.pack_propagate(False)
        right = tk.Frame(self, bg=PANEL, highlightbackground=border, highlightthickness=1)
        right.grid(row=1, column=1, sticky='nsew', padx=(8, 26), pady=(0, 20))

        # Left: control deck
        tk.Label(left, text='CONTROL DECK', bg=PANEL, fg=TEXT,
                 font=('Segoe UI Semibold', 10)).pack(anchor='w', padx=16, pady=(14, 2))
        tk.Label(left, text='Quick actions', bg=PANEL, fg=MUTED,
                 font=('Segoe UI', 8)).pack(anchor='w', padx=16, pady=(0, 10))

        self.btn_r = RoundedButton(left, 'R   START CHROME', self.start_chrome, BLUE, CYAN, height=42)
        self.btn_r.pack(fill='x', padx=14, pady=4)
        self.btn_y = RoundedButton(left, 'Y   SCAN QUESTION', self.scan, PANEL2, BLUE, TEXT, height=42)
        self.btn_y.pack(fill='x', padx=14, pady=4)
        self.btn_a = RoundedButton(left, 'A   SOLVE QUESTION', self.solve, PURPLE, CYAN, height=42)
        self.btn_a.pack(fill='x', padx=14, pady=4)

        # Compact status card
        status = tk.Frame(left, bg=PANEL2, highlightbackground=border, highlightthickness=1)
        status.pack(fill='x', padx=14, pady=(15, 8))
        tk.Label(status, text='SYSTEM STATUS', bg=PANEL2, fg=CYAN,
                 font=('Segoe UI Semibold', 8)).pack(anchor='w', padx=12, pady=(10, 5))
        self.status_debug = tk.Label(status, text='Chrome debug: checking…', bg=PANEL2, fg=MUTED,
                                      font=('Segoe UI', 8), anchor='w')
        self.status_debug.pack(fill='x', padx=12, pady=2)
        self.status_scan = tk.Label(status, text='Last scan: none', bg=PANEL2, fg=MUTED,
                                     font=('Segoe UI', 8), anchor='w')
        self.status_scan.pack(fill='x', padx=12, pady=(2, 10))

        self.btn_theme = RoundedButton(left, 'T   CHANGE THEME', self.toggle_theme, PANEL2, PURPLE, TEXT, height=38)
        self.btn_theme.pack(fill='x', padx=14, pady=4)
        self.btn_x = RoundedButton(left, 'X   EXIT', self.on_exit, PANEL2, BLUE, TEXT, height=38)
        self.btn_x.pack(fill='x', padx=14, pady=4)

        tk.Label(left, text='KEYBOARD', bg=PANEL, fg=MUTED,
                 font=('Segoe UI Semibold', 8)).pack(anchor='w', padx=16, pady=(15, 4))
        keys = tk.Frame(left, bg=PANEL)
        keys.pack(fill='x', padx=14)
        key_items = [('R','Chrome'), ('Y','Scan'), ('A','Solve'), ('1-4','Presets'), ('T','Theme'), ('X','Exit')]
        for i, (key, label) in enumerate(key_items):
            row = tk.Frame(keys, bg=PANEL)
            row.pack(fill='x', pady=1)
            tk.Label(row, text=key, bg=PANEL2, fg=CYAN, width=5,
                     font=('Consolas', 8, 'bold')).pack(side='left')
            tk.Label(row, text=label, bg=PANEL, fg=TEXT,
                     font=('Segoe UI', 8)).pack(side='left', padx=8)

        self.bind('<r>', lambda e: self.start_chrome())
        self.bind('<y>', lambda e: self.scan())
        self.bind('<a>', lambda e: self.solve())
        self.bind('<x>', lambda e: self.on_exit())
        self.bind('<KeyPress-1>', lambda e: self.quick_preset('1'))
        self.bind('<KeyPress-2>', lambda e: self.quick_preset('2'))
        self.bind('<KeyPress-3>', lambda e: self.quick_preset('3'))
        self.bind('<KeyPress-4>', lambda e: self.quick_preset('4'))
        self.bind('<KeyPress-t>', lambda e: self.toggle_theme())

        # Right: live workspace
        header = tk.Frame(right, bg=PANEL)
        header.pack(fill='x', padx=16, pady=(13, 0))
        tk.Label(header, text='LIVE QUESTION FEED', bg=PANEL, fg=TEXT,
                 font=('Segoe UI Semibold', 11)).pack(side='left')
        self.live_dot = tk.Label(header, text='● LIVE', bg=PANEL, fg=GREEN,
                                 font=('Segoe UI Semibold', 8))
        self.live_dot.pack(side='right')
        self.page_label = tk.Label(right, text='Waiting for a Netmath / NetFrancais question…',
                                   bg=PANEL, fg=MUTED, font=('Segoe UI', 8), anchor='w')
        self.page_label.pack(fill='x', padx=16, pady=(2, 9))

        # Question card
        qcard = tk.Frame(right, bg=PANEL2, highlightbackground=border, highlightthickness=1)
        qcard.pack(fill='x', padx=14, pady=(0, 9))
        qhead = tk.Frame(qcard, bg=PANEL2)
        qhead.pack(fill='x', padx=12, pady=(8, 0))
        tk.Label(qhead, text='QUESTION', bg=PANEL2, fg=CYAN,
                 font=('Segoe UI Semibold', 9)).pack(side='left')
        tk.Label(qhead, text='SCANNED', bg=PANEL2, fg=MUTED,
                 font=('Segoe UI', 7)).pack(side='right')
        self.question = tk.Text(qcard, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                                selectbackground='#34488B', relief='flat', wrap='word',
                                font=('Segoe UI', 10), height=5)
        self.question.pack(fill='x', padx=12, pady=(3, 10))
        self.question.configure(state='disabled')

        # Solution card
        solcard = tk.Frame(right, bg=PANEL2, highlightbackground=border, highlightthickness=1)
        solcard.pack(fill='both', expand=True, padx=14, pady=(0, 9))
        solhead = tk.Frame(solcard, bg=PANEL2)
        solhead.pack(fill='x', padx=12, pady=(8, 0))
        tk.Label(solhead, text='AI SOLUTION', bg=PANEL2, fg=GREEN,
                 font=('Segoe UI Semibold', 9)).pack(side='left')
        progress_row = tk.Frame(solcard, bg=PANEL2)
        progress_row.pack(fill='x', padx=12, pady=(5, 2))
        self.solution_status = tk.Label(progress_row, text='WAITING', bg=PANEL2, fg=MUTED,
                                        font=('Segoe UI Semibold', 8))
        self.solution_status.pack(side='left')
        self.ai_eta = tk.Label(progress_row, text='', bg=PANEL2, fg=MUTED,
                               font=('Segoe UI', 8))
        self.ai_eta.pack(side='right')

        self.ai_progress = tk.Canvas(solcard, height=7, bg=PANEL2, highlightthickness=0, bd=0)
        self.ai_progress.pack(fill='x', padx=12, pady=(0, 7))
        self.ai_progress_value = 0
        self.ai_progress_mode = 'idle'
        self.ai_progress_after = None
        self.ai_progress_phase = 0
        self.ai_progress.bind('<Configure>', lambda e: self.draw_ai_progress())

        self.solution = tk.Text(solcard, bg=PANEL2, fg=GREEN, insertbackground=GREEN,
                                selectbackground='#285D4A', relief='flat', wrap='word',
                                font=('Segoe UI', 10), padx=8, pady=5)
        self.solution.pack(fill='both', expand=True, padx=12, pady=(0, 10))
        self.solution.configure(state='disabled')

        # Activity footer
        logcard = tk.Frame(right, bg=PANEL2, highlightbackground=border, highlightthickness=1)
        logcard.pack(fill='x', padx=14, pady=(0, 14))
        tk.Label(logcard, text='ACTIVITY', bg=PANEL2, fg=GREEN,
                 font=('Segoe UI Semibold', 8)).pack(anchor='w', padx=12, pady=(7, 1))
        self.log = tk.Text(logcard, bg=PANEL2, fg=MUTED, relief='flat', wrap='word',
                           font=('Consolas', 8), height=3)
        self.log.pack(fill='both', expand=True, padx=12, pady=(0, 5))
        self.log.configure(state='disabled')

        self.write_log('V2.9.9 ready • R Chrome • Y Scan • A Solve • 1-4 Presets • T Theme')

    def write_log(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', f'• {text}\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def set_text(self, widget, text):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        if widget is self.solution:
            # Keep the AI output easy to scan: headings are bright green and
            # the actual solution text uses a clean Segoe UI font.
            widget.tag_configure('heading', foreground='#7CFFBE', font=('Segoe UI Semibold', 11, 'bold'))
            for heading in ('Solution', 'SOLUTION:', 'QUESTION:', 'ANSWER:'):
                start = '1.0'
                while True:
                    pos = widget.search(heading, start, stopindex='end')
                    if not pos:
                        break
                    end = f'{pos}+{len(heading)}c'
                    widget.tag_add('heading', pos, end)
                    start = end
        widget.configure(state='disabled')

    def set_solution_status(self, text):
        try:
            self.solution_status.config(text=text)
        except Exception:
            pass


    def draw_ai_progress(self):
        try:
            c = self.ai_progress
            c.delete('all')
            w = max(c.winfo_width(), 100)
            h = max(c.winfo_height(), 7)
            track = self.themes[self.theme_name]['BORDER']
            c.create_rectangle(0, 1, w, h-1, fill=track, outline='')
            if self.ai_progress_mode == 'idle':
                return
            if self.ai_progress_mode == 'waiting':
                # Dynamic indeterminate glow while Gemini is thinking.
                span = max(34, int(w * .18))
                x = int((self.ai_progress_phase % 100) / 100 * (w + span) - span)
                c.create_rectangle(max(0,x), 1, min(w,x+span), h-1, fill=CYAN, outline='')
            else:
                fill_w = int(w * max(0, min(100, self.ai_progress_value)) / 100)
                c.create_rectangle(0, 1, fill_w, h-1, fill=BLUE if self.theme_name == 'dark' else PURPLE, outline='')
                if fill_w > 5:
                    c.create_rectangle(max(0, fill_w-35), 1, fill_w, h-1, fill=CYAN, outline='')
        except Exception:
            pass

    def start_ai_progress(self):
        self.ai_progress_mode = 'waiting'
        self.ai_progress_value = 18
        self.ai_progress_phase = 0
        self.set_solution_status('CONNECTING TO GEMINI…')
        self.ai_eta.config(text='Response coming soon')
        self._tick_ai_progress()

    def _tick_ai_progress(self):
        if self.ai_progress_mode == 'idle':
            return
        self.ai_progress_phase = (self.ai_progress_phase + 3) % 100
        if self.ai_progress_mode == 'waiting':
            self.ai_progress_value = min(92, self.ai_progress_value + 0.35)
            self.draw_ai_progress()
            self.ai_progress_after = self.after(35, self._tick_ai_progress)

    def set_ai_stage(self, text, percent=None, eta=''):
        def update():
            self.ai_progress_mode = 'determinate'
            if percent is not None:
                self.ai_progress_value = percent
            self.set_solution_status(text)
            self.ai_eta.config(text=eta)
            self.draw_ai_progress()
        self.after(0, update)

    def finish_ai_progress(self):
        def update():
            self.ai_progress_mode = 'determinate'
            self.ai_progress_value = 100
            self.set_solution_status('GEMINI RESPONSE READY')
            self.ai_eta.config(text='Done ✓')
            self.draw_ai_progress()
            self.after(550, self.reset_ai_progress)
        self.after(0, update)

    def reset_ai_progress(self):
        self.ai_progress_mode = 'idle'
        self.ai_progress_value = 0
        self.ai_eta.config(text='')
        self.set_solution_status('WAITING')
        self.draw_ai_progress()

    def refresh_status(self):
        # Never perform the DevTools HTTP check on Tk's UI thread.
        # debug_port_alive() can wait up to ~1.5s when Chrome is closed, which
        # used to make the whole GUI visibly freeze every status interval.
        if not self._status_check_running:
            self._status_check_running = True
            threading.Thread(target=self._status_worker, daemon=True).start()
        self.after(1500, self.refresh_status)

    def _status_worker(self):
        try:
            ok = core.debug_port_alive()
        except Exception:
            ok = False
        def update():
            self.chrome_ok = ok
            self.status_debug.config(
                text=f"Chrome debug: {'CONNECTED :9222' if ok else 'not detected'}",
                fg=GREEN if ok else MUTED
            )
            self.status_scan.config(
                text=f"Last scan: {'ready' if self.last_extracted else 'none'}",
                fg=GREEN if self.last_extracted else MUTED
            )
            self._status_check_running = False
        self.after(0, update)

    def run_bg(self, fn):
        if self.busy:
            return
        self.busy = True
        for b in (self.btn_r, self.btn_y, self.btn_a): b.state(['disabled'])
        threading.Thread(target=self._bg_wrap, args=(fn,), daemon=True).start()

    def _bg_wrap(self, fn):
        try:
            fn()
        except Exception as e:
            self.after(0, lambda: self.ai_progress_mode if False else None)
            self.after(0, lambda: self.set_solution_status('REQUEST FAILED'))
            self.after(0, lambda: self.ai_eta.config(text='Check API / connection'))
            self.after(0, lambda: self.write_log(f'Error: {e}'))
            self.after(0, lambda: self.draw_ai_progress())
            self.after(0, lambda: messagebox.showerror('YVZTOOLS Error', str(e)))
        finally:
            self.busy = False
            self.after(0, lambda: [b.state(['!disabled']) for b in (self.btn_r, self.btn_y, self.btn_a)])

    def start_chrome(self):
        def work():
            if core.debug_port_alive():
                self.after(0, lambda: self.write_log('Chrome DevTools is already reachable on port 9222.'))
                return
            choice = self.ask_chrome_mode()
            if choice == 'separate':
                ok = self.launch_separate()
            else:
                ok = self.launch_main_setup()
            self.after(0, lambda: self.write_log('Chrome connected.' if ok else 'Chrome connection not established.'))
            if not ok:
                self.after(0, lambda: messagebox.showwarning('Chrome', 'Could not connect to Chrome on port 9222.'))
        self.run_bg(work)

    def ask_chrome_mode(self):
        result = {'v': 'separate'}
        ev = threading.Event()
        def show():
            win = tk.Toplevel(self); win.title('Start Chrome'); win.geometry('480x260'); win.configure(bg=PANEL); win.grab_set()
            tk.Label(win, text='How do you want to connect?', bg=PANEL, fg=TEXT, font=('Segoe UI Semibold', 14)).pack(pady=(22, 5))
            tk.Label(win, text='Choose the profile mode used by the original tool.', bg=PANEL, fg=MUTED, font=('Segoe UI', 8)).pack(pady=(0, 16))
            def pick(v): result['v'] = v; win.destroy(); ev.set()
            ttk.Button(win, text='Main Chrome profile', style='Accent.TButton', command=lambda: pick('main')).pack(fill='x', padx=36, pady=6)
            ttk.Button(win, text='Separate automation profile', style='Purple.TButton', command=lambda: pick('separate')).pack(fill='x', padx=36, pady=6)
            ttk.Button(win, text='Cancel', style='Soft.TButton', command=lambda: pick('cancel')).pack(fill='x', padx=36, pady=6)
        self.after(0, show); ev.wait()
        return result['v']

    def launch_separate(self):
        chrome = core.find_chrome_exe()
        if not chrome:
            self.after(0, lambda: messagebox.showerror('Chrome', 'chrome.exe could not be located.'))
            return False
        core.ensure_app_dir(); os.makedirs(core.CHROME_PROFILE_DIR, exist_ok=True)
        args = [chrome, f'--remote-debugging-port={core.DEBUG_PORT}', f'--user-data-dir={core.CHROME_PROFILE_DIR}', '--remote-allow-origins=*', '--no-first-run', '--no-default-browser-check', 'https://www.netmath.ca']
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            if core.debug_port_alive(): return True
            time.sleep(.5)
        return False

    def launch_main_setup(self):
        chrome = core.find_chrome_exe()
        if not chrome: return False
        subprocess.Popen([chrome, 'chrome://inspect/#remote-debugging'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.after(0, lambda: messagebox.showinfo('One-time Chrome setup', 'In Chrome, enable “Allow remote debugging for this browser instance”, then fully quit and reopen Chrome. The app will wait for port 9222.'))
        for _ in range(60):
            if core.debug_port_alive(): return True
            time.sleep(.5)
        return False

    def _choose_tab(self, tabs):
        candidates = [t for t in tabs if t.get('type') == 'page' and any(h in ((t.get('url') or '')+' '+(t.get('title') or '')).lower() for h in core.SITE_HINTS)]
        if not candidates: return None
        if len(candidates) == 1: return candidates[0]
        result = {'idx': None}; ev = threading.Event()
        def show():
            win = tk.Toplevel(self); win.title('Choose tab'); win.geometry('720x320'); win.configure(bg=PANEL); win.grab_set()
            tk.Label(win, text='Multiple Netmath / NetFrancais tabs found', bg=PANEL, fg=TEXT, font=('Segoe UI Semibold', 8)).pack(pady=12)
            lb = tk.Listbox(win, bg=PANEL2, fg=TEXT, selectbackground='#34488B', relief='flat', font=('Segoe UI', 8))
            lb.pack(fill='both', expand=True, padx=18, pady=8)
            for t in candidates: lb.insert('end', f"{t.get('title','Untitled')}  —  {t.get('url','')}")
            def ok():
                s = lb.curselection(); result['idx'] = s[0] if s else 0; win.destroy(); ev.set()
            ttk.Button(win, text='Use selected tab', style='Accent.TButton', command=ok).pack(pady=10)
        self.after(0, show); ev.wait()
        return candidates[result['idx'] or 0]

    def scan(self):
        def work():
            tabs = core.list_tabs()
            if tabs is None:
                raise RuntimeError('Chrome DevTools is not reachable. Press R first.')
            tab = self._choose_tab(tabs)
            if not tab: raise RuntimeError('No Netmath or NetFrancais tab found.')
            ws = tab.get('webSocketDebuggerUrl')
            if not ws: raise RuntimeError('Selected tab has no debugger websocket URL.')
            raw = core.evaluate_in_tab(ws, core.EXTRACTION_JS)
            data = json.loads(raw)
            self.last_extracted, self.last_tab = data, tab
            q = (data.get('questionText') or '(no readable text found)').strip()
            choices = data.get('choices') or []
            if choices:
                q += '\n\nAnswer choices:\n' + '\n'.join(f'{i+1}. {c}' for i, c in enumerate(choices))
            notes = []
            if data.get('hasImage'): notes.append('image')
            if data.get('hasCanvas'): notes.append('canvas')
            if data.get('hasSvgGraph'): notes.append('SVG graph')
            if data.get('geoWidget'): notes.append('interactive widget')
            if data.get('hasIframe'): notes.append('iframe')
            if notes: q += '\n\nVisual content detected: ' + ', '.join(notes) + '.'
            self.after(0, lambda: self.set_text(self.question, q))
            self.after(0, lambda: self.page_label.config(text=f"{data.get('pageTitle','Netmath')}  •  {data.get('pageUrl','')}"[:180], fg=CYAN))
            stamp = time.strftime('%H:%M:%S')
            self.after(0, lambda: self.set_solution_status('QUESTION UPDATED • ' + stamp))
            self.after(0, lambda: self.write_log(f'[{stamp}] LIVE FEED • Question updated.'))
        self.run_bg(work)

    def solve(self):
        if not self.last_extracted:
            messagebox.showinfo('Solve Question', 'Scan a question first with Y.')
            return
        self._preset_dialog()

    def _preset_dialog(self):
        # IMPORTANT: this dialog is created directly on the Tk/UI thread.
        # The old version scheduled it with after() and then blocked the UI
        # thread waiting on an Event, so the window could appear frozen or
        # never appear at all.
        win = tk.Toplevel(self)
        win.title('Solve Question — Gemini')
        win.geometry('560x400')
        win.configure(bg=PANEL)
        win.transient(self)
        win.grab_set()

        tk.Label(win, text='SOLVE QUESTION', bg=PANEL, fg=TEXT,
                 font=('Segoe UI Black', 14)).pack(pady=(22, 3))
        tk.Label(win, text='Choose your API-key and screenshot settings', bg=PANEL, fg=MUTED,
                 font=('Segoe UI', 8)).pack(pady=(0, 16))

        current = bool(os.environ.get('GEMINI_API_KEY') or core.load_config().get('gemini_api_key'))
        current_text = 'Saved API key detected' if current else 'No saved API key — you will be asked for one'
        tk.Label(win, text='API STATUS  •  ' + current_text, bg=PANEL2, fg=GREEN if current else RED,
                 font=('Segoe UI Semibold', 8), padx=12, pady=8).pack(fill='x', padx=30, pady=(0, 12))

        opts = [
            ('1', 'KEEP API KEY', 'TAKE SCREENSHOT', True, True),
            ('2', 'KEEP API KEY', 'NO SCREENSHOT', False, True),
            ('3', 'CHANGE API KEY', 'TAKE SCREENSHOT', True, False),
            ('4', 'CHANGE API KEY', 'NO SCREENSHOT', False, False),
        ]

        selected = {'choice': None}

        def choose(v):
            selected['choice'] = v
            win.destroy()

        for v, api_txt, shot_txt, _, _ in opts:
            frame = tk.Frame(win, bg=PANEL2, highlightbackground='#28366F', highlightthickness=1)
            frame.pack(fill='x', padx=30, pady=5)
            tk.Label(frame, text=f'[{v}]', bg=PANEL2, fg=CYAN,
                     font=('Consolas', 11, 'bold')).pack(side='left', padx=(12, 8), pady=11)
            tk.Label(frame, text=api_txt, bg=PANEL2, fg=TEXT,
                     font=('Segoe UI Semibold', 8)).pack(side='left', pady=11)
            tk.Label(frame, text='•', bg=PANEL2, fg=MUTED,
                     font=('Segoe UI', 8)).pack(side='left', padx=8)
            tk.Label(frame, text=shot_txt, bg=PANEL2, fg=PURPLE if 'SCREENSHOT' in shot_txt else MUTED,
                     font=('Segoe UI Semibold', 8)).pack(side='left', pady=11)
            ttk.Button(frame, text='SELECT', style='Purple.TButton' if v in ('1','3') else 'Accent.TButton',
                       command=lambda vv=v: choose(vv)).pack(side='right', padx=10, pady=6)

        ttk.Button(win, text='CANCEL', style='Soft.TButton', command=win.destroy).pack(fill='x', padx=30, pady=(12, 18))
        self.wait_window(win)

        if selected['choice']:
            self.run_bg(lambda: self.do_solve(selected['choice']))

    def quick_preset(self, preset):
        # 1/2/3/4 now work directly from the main app:
        # 1 = saved key + screenshot, 2 = saved key + no screenshot,
        # 3 = change key + screenshot, 4 = change key + no screenshot.
        if self.busy:
            return
        if not self.last_extracted:
            self.write_log('Scan a question first (Y).')
            self.set_solution_status('SCAN FIRST')
            return
        self.run_bg(lambda: self.do_solve(preset))

    def ask_key(self, old=None):
        # Called on the Tk thread through after(). Use wait_window so the
        # nested Tk event loop stays responsive while the worker waits.
        box = tk.Toplevel(self)
        box.title('Gemini API Key')
        box.geometry('600x250')
        box.configure(bg=PANEL)
        box.transient(self)
        box.grab_set()

        tk.Label(box, text='GEMINI API KEY', bg=PANEL, fg=TEXT,
                 font=('Segoe UI Black', 13)).pack(pady=(22, 5))
        tk.Label(box, text='Paste your Google Gemini API key. It will be saved locally.',
                 bg=PANEL, fg=MUTED, font=('Segoe UI', 8)).pack()

        entry = tk.Entry(box, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                         relief='flat', font=('Consolas', 9), show='•')
        entry.pack(fill='x', padx=30, pady=18, ipady=8)
        entry.focus_set()

        out = {'v': None}
        def ok(event=None):
            value = entry.get().strip()
            if value:
                out['v'] = value
                box.destroy()

        def cancel(event=None):
            box.destroy()

        ttk.Button(box, text='SAVE & CONTINUE', style='Accent.TButton', command=ok).pack(fill='x', padx=30, pady=4)
        ttk.Button(box, text='CANCEL', style='Soft.TButton', command=cancel).pack(fill='x', padx=30, pady=4)
        box.bind('<Return>', ok)
        box.bind('<Escape>', cancel)
        self.wait_window(box)
        return out['v']

    def do_solve(self, preset):
        cfg = core.load_config()
        key = os.environ.get('GEMINI_API_KEY') or (getattr(cfg, 'get', lambda *a: None)('gemini_api_key'))
        force_new = preset in ('3','4')
        want_ss = preset in ('1','3')
        if force_new or not key:
            ev = threading.Event(); holder={'v':None}
            def ask(): holder['v'] = self.ask_key(key); ev.set()
            self.after(0, ask); ev.wait(); key = holder['v']
            if key:
                cfg['gemini_api_key'] = key; core.save_config(cfg)
        if not key:
            raise RuntimeError('No Gemini API key was provided.')

        self.after(0, self.start_ai_progress)
        self.after(0, lambda: self.write_log('LIVE FEED • Preparing Gemini request.'))
        self.set_ai_stage('PREPARING GEMINI REQUEST…', 22, 'Building prompt…')
        self.after(0, lambda: self.write_log('LIVE FEED • Preparing the latest scanned question for Gemini.'))
        extracted = self.last_extracted
        question_text = (extracted.get('questionText') or '').strip()
        choices = extracted.get('choices') or []
        missing = []
        if extracted.get('hasImage'): missing.append('an image')
        if extracted.get('hasCanvas'): missing.append('a canvas element')
        if extracted.get('hasSvgGraph'): missing.append('an SVG graph/figure')
        if extracted.get('geoWidget'): missing.append('an interactive math widget')
        screenshot = None
        ws = (self.last_tab or {}).get('webSocketDebuggerUrl')
        if want_ss and ws:
            screenshot = core.capture_tab_screenshot_base64(ws)

        caveat = ''
        if missing and not screenshot:
            caveat = f"\\n\\nNOTE: The page also contains {', '.join(missing)} that was not extracted as text. Do not guess if it is required."
        choices_block = '\n\nAnswer choices shown on the page:\n' + '\n'.join(f'- {c}' for c in choices) if choices else ''
        prompt = (
            'You are a tutor helping a student understand a homework/quiz question extracted from a webpage (math or language-arts). '
            'Solve or answer it and explain your reasoning clearly, but be concise - short steps, no filler, no repeated ideas.\\n\\n'
            f'QUESTION TEXT (as extracted from the page):\\n{question_text}{choices_block}{caveat}\\n\\n'
            'Respond using exactly this format:\\nQUESTION:\\n<restate the question clearly, cleaned up>\\n\\n'
            'SOLUTION:\\n<brief step-by-step reasoning - as few steps as needed to justify the answer>\\n\\n'
            'ANSWER:\\n<final answer only>'
        )
        parts = []
        if screenshot:
            parts.append({'inlineData': {'mimeType': 'image/png', 'data': screenshot}})
        parts.append({'text': prompt})
        self.after(0, lambda: self.write_log('SENDING TO GEMINI' + (' • screenshot attached' if screenshot else ' • text only')))
        self.set_ai_stage('SENDING TO GEMINI…', 35, 'Waiting for response…')
        payload = {
            'contents': [{'role': 'user', 'parts': parts}],
            'generationConfig': {'maxOutputTokens': 700}
        }
        # Google documents x-goog-api-key for REST requests. Keep the key out
        # of the URL and provide a useful error if the model/key is rejected.
        resp = core.post_with_retry(
            url=core.GEMINI_API_URL,
            headers={'x-goog-api-key': key, 'Content-Type': 'application/json'},
            json=payload,
            timeout=60
        )
        if resp.status_code != 200:
            try:
                err = resp.json().get('error', {})
                detail = err.get('message') or resp.text[:500]
            except Exception:
                detail = resp.text[:500]
            if resp.status_code == 400:
                detail += '\n\nCheck that your Gemini API key is valid and that the Gemini API is enabled for it.'
            elif resp.status_code == 401 or resp.status_code == 403:
                detail += '\n\nThe API key was rejected. Use a valid Gemini API key.'
            elif resp.status_code == 404:
                detail += '\n\nThe selected Gemini model was not found. The app is configured for the current Flash model.'
            raise RuntimeError(f'Gemini API error ({resp.status_code})\n{detail}')
        try:
            body = resp.json()
        except Exception:
            raise RuntimeError('Gemini returned an invalid JSON response.')
        chunks=[]
        for cand in body.get('candidates', []):
            for part in cand.get('content',{}).get('parts',[]):
                if part.get('text'): chunks.append(part['text'])
        text='\n'.join(chunks).strip()
        if not text:
            block = body.get('promptFeedback', {})
            reason = block.get('blockReason')
            text = f'(Gemini returned no text{": " + reason if reason else ""}.)'
        self.after(0, lambda: self.set_text(self.solution, text))
        self.after(0, lambda: self.write_log('Gemini solution received.'))
        self.finish_ai_progress()

    def on_exit(self):
        if messagebox.askyesno('Exit YVZTOOLS', 'Close the app?'):
            self.destroy()


def _lerp_hex(a, b, t):
    t = max(0.0, min(1.0, t))
    a, b = a.lstrip('#'), b.lstrip('#')
    ca = [int(a[i:i+2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i+2], 16) for i in (0, 2, 4)]
    return '#%02x%02x%02x' % tuple(int(x + (y - x) * t) for x, y in zip(ca, cb))


class YVZSplash(tk.Tk):
    """Animated startup screen: centered, fade in/out, rotating rings, smooth progress."""
    W, H = 640, 380
    DURATION = 2.8
    PALETTES = {
        'dark':   dict(top='#030614', bot='#0B1233', star='#7FA9FF', ring1='#1B3A8C', ring2='#5B34A0', accent='#4A9BFF', accent2='#9A6BFF', text='#F4F7FF', sub='#61D8FF', muted='#91A1CC', track='#14204D'),
        'pink':   dict(top='#FFF8FC', bot='#FFE6F0', star='#E98BB0', ring1='#F2B5CC', ring2='#E5A4C1', accent='#E85D97', accent2='#A66AE8', text='#3B2130', sub='#D94D8E', muted='#9C6B80', track='#F6CFDF'),
        'hacker': dict(top='#010302', bot='#04180B', star='#39FF88', ring1='#0B5E31', ring2='#168C48', accent='#19E66B', accent2='#59FF9A', text='#D7FFE4', sub='#59FF9A', muted='#6EA77D', track='#0A2414'),
        'red':    dict(top='#070203', bot='#25080D', star='#FF526A', ring1='#741526', ring2='#9B263E', accent='#F0445E', accent2='#FF7586', text='#FFF1F2', sub='#FF7586', muted='#B9868D', track='#2A0C12'),
    }
    STAGES = [(0.00, 'Starting engine'), (0.28, 'Loading math core'), (0.58, 'Preparing interface'), (0.86, 'Almost ready')]

    def __init__(self):
        super().__init__()
        import random
        self.overrideredirect(True)
        theme = core.load_config().get('theme', 'dark')
        self.pal = self.PALETTES.get(theme, self.PALETTES['dark'])
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f'{self.W}x{self.H}+{(sw - self.W) // 2}+{(sh - self.H) // 2}')
        self.configure(bg=self.pal['top'])
        try:
            self.attributes('-topmost', True)
            self.attributes('-alpha', 0.0)
        except Exception:
            pass
        self.canvas = tk.Canvas(self, width=self.W, height=self.H, bg=self.pal['top'], highlightthickness=0, bd=0)
        self.canvas.pack(fill='both', expand=True)

        # Static vertical gradient (drawn once).
        for i in range(0, self.H, 4):
            self.canvas.create_rectangle(0, i, self.W, i + 4, outline='',
                                         fill=_lerp_hex(self.pal['top'], self.pal['bot'], i / self.H))
        rnd = random.Random(7)
        self.stars = [[rnd.uniform(0, self.W), rnd.uniform(0, self.H), rnd.choice([1, 1, 2]),
                       rnd.uniform(0.15, 0.6), rnd.uniform(0, 6.28)] for _ in range(60)]
        self.t0 = time.time()
        self.last = self.t0
        self.after(16, self.animate)

    def animate(self):
        import math
        el = time.time() - self.t0
        dt = el - (self.last - self.t0)
        self.last = time.time()
        P = self.pal
        c = self.canvas
        c.delete('dyn')

        # Fade in / out.
        fade_out_start = self.DURATION - 0.35
        alpha = min(1.0, el / 0.4)
        if el > fade_out_start:
            alpha = max(0.0, 1.0 - (el - fade_out_start) / 0.35)
        try:
            self.attributes('-alpha', alpha)
        except Exception:
            pass

        # Drifting stars with twinkle.
        for st in self.stars:
            st[0] -= st[3] * 60 * max(dt, 0.001)
            if st[0] < -4:
                st[0] = self.W + 4
            tw = 0.5 + 0.5 * math.sin(el * 3 + st[4])
            col = _lerp_hex(_lerp_hex(P['top'], P['bot'], st[1] / self.H), P['star'], 0.25 + 0.6 * tw)
            r = st[2]
            c.create_oval(st[0] - r, st[1] - r, st[0] + r, st[1] + r, fill=col, outline='', tags='dyn')

        # Rotating orbit rings with bright arc segments.
        cx, cy = self.W / 2, 150
        for rad, col, sp, w in ((150, P['ring1'], 40, 2), (105, P['ring2'], -70, 2), (62, P['accent'], 120, 2)):
            c.create_oval(cx - rad, cy - rad, cx + rad, cy + rad, outline=_lerp_hex(P['bot'], col, 0.45), width=1, tags='dyn')
            c.create_arc(cx - rad, cy - rad, cx + rad, cy + rad, start=(el * sp) % 360, extent=70,
                         style='arc', outline=col, width=w, tags='dyn')

        # Logo + subtitle fade in.
        a_logo = min(1.0, max(0.0, (el - 0.15) / 0.5))
        a_sub = min(1.0, max(0.0, (el - 0.55) / 0.5))
        bgc = _lerp_hex(P['top'], P['bot'], 150 / self.H)
        size = 30 + int(4 * min(1.0, el / 0.8))
        c.create_text(cx, cy - 8, text='YVZTOOLS', fill=_lerp_hex(bgc, P['text'], a_logo),
                      font=('Segoe UI Black', size), tags='dyn')
        c.create_text(cx, cy + 32, text='NETMATH SPACE', fill=_lerp_hex(bgc, P['sub'], a_sub),
                      font=('Segoe UI Semibold', 12), tags='dyn')

        # Smooth eased progress bar with glow.
        run = max(0.0, min(1.0, el / (self.DURATION - 0.35)))
        prog = 1 - (1 - run) ** 3
        x0, x1, y = 130, self.W - 130, 288
        c.create_line(x0, y, x1, y, width=8, capstyle='round', fill=P['track'], tags='dyn')
        if prog > 0.01:
            xe = x0 + (x1 - x0) * prog
            c.create_line(x0, y, xe, y, width=14, capstyle='round', fill=_lerp_hex(P['track'], P['accent'], 0.25), tags='dyn')
            c.create_line(x0, y, xe, y, width=8, capstyle='round', fill=P['accent'], tags='dyn')
            c.create_oval(xe - 4, y - 4, xe + 4, y + 4, fill=P['text'], outline='', tags='dyn')

        # Status text + percent.
        stage = [t for th, t in self.STAGES if prog >= th][-1]
        dots = '.' * (int(el * 3) % 4)
        c.create_text(x0, y + 24, anchor='w', text=stage + dots, fill=P['muted'], font=('Segoe UI', 9), tags='dyn')
        c.create_text(x1, y + 24, anchor='e', text=f'{int(prog * 100)}%', fill=P['sub'], font=('Segoe UI Semibold', 9), tags='dyn')
        c.create_text(cx, self.H - 18, text=f'v{VERSION.split()[0]}', fill=P['muted'], font=('Segoe UI', 8), tags='dyn')

        if el < self.DURATION:
            self.after(16, self.animate)
        else:
            self.destroy()


def launch_app():
    cfg = core.load_config()
    saved = cfg.get('theme', 'dark')
    themes = {
        'dark': ('🌌', 'SPACE BLUE', '#4A9BFF'),
        'pink': ('🌸', 'COTTON CANDY', '#E85D97'),
        'hacker': ('☠', 'HACKER GREEN', '#19E66B'),
        'red': ('🔥', 'CRIMSON', '#F0445E')
    }

    picker = tk.Tk()
    picker.title('YVZTOOLS • Select Theme')
    picker.geometry('650x470')
    picker.resizable(False, False)
    picker.configure(bg='#050817')
    selected = {'name': saved if saved in themes else 'dark'}

    tk.Label(picker, text='YVZTOOLS', bg='#050817', fg='#F4F7FF',
             font=('Segoe UI Black', 28)).pack(pady=(28, 0))
    tk.Label(picker, text='NETMATH SPACE  •  CHOOSE YOUR THEME',
             bg='#050817', fg='#61D8FF', font=('Segoe UI Semibold', 10)).pack(pady=(0, 22))

    grid = tk.Frame(picker, bg='#050817')
    grid.pack(fill='both', expand=True, padx=34)

    def choose(name):
        selected['name'] = name
        for child in grid.winfo_children():
            child.configure(relief='solid' if getattr(child, '_theme_name', None) == name else 'flat')

    for i, (name, (icon, label, accent)) in enumerate(themes.items()):
        card = tk.Frame(grid, bg='#0B1230', highlightthickness=1,
                        highlightbackground='#263C82', cursor='hand2')
        card._theme_name = name
        card.grid(row=i//2, column=i%2, padx=9, pady=9, sticky='nsew', ipadx=8, ipady=12)
        grid.grid_columnconfigure(i%2, weight=1)

        tk.Label(card, text=icon, bg='#0B1230', fg=accent,
                 font=('Segoe UI Emoji', 22)).pack(pady=(6,0))
        tk.Label(card, text=label, bg='#0B1230', fg='#F2F6FF',
                 font=('Segoe UI Semibold', 10)).pack(pady=5)

        for widget in (card, *card.winfo_children()):
            widget.bind('<Button-1>', lambda e, x=name: choose(x))

    tk.Label(picker, text='Your choice is saved for next launch.',
             bg='#050817', fg='#91A1CC', font=('Segoe UI', 8)).pack(pady=(3, 5))

    def launch():
        cfg['theme'] = selected['name']
        core.save_config(cfg)
        picker.destroy()

    tk.Button(picker, text='ENTER YVZTOOLS  →', command=launch,
              bg='#4A9BFF', fg='white', activebackground='#61D8FF',
              relief='flat', bd=0, font=('Segoe UI Semibold', 10),
              cursor='hand2', padx=25, pady=9).pack(pady=(4, 20))

    picker.mainloop()

    splash = YVZSplash()
    splash.mainloop()
    app = App()
    app.mainloop()


if __name__ == '__main__':
    try:
        launch_app()
    except Exception:
        traceback.print_exc()
        raise
