"""
YVZNETMATH TOOL
================
A Windows terminal tool that connects to a running Google Chrome instance
(via the Chrome DevTools Protocol on localhost:9222), locates the open
Netmath tab, extracts the currently visible math question, and optionally
sends it to an AI math-solving system for a worked solution.

IMPORTANT: This tool NEVER submits anything to Netmath. It only reads
the page. You must always enter/submit your own answer in the browser.

Author: built for a specific user request. Windows-only (uses msvcrt).
"""

import os
import sys
import json
import time
import shutil
import subprocess
import traceback
import urllib.request
import urllib.error

try:
    import msvcrt  # Windows-only, stdlib
except ImportError:
    msvcrt = None

try:
    import websocket  # pip install websocket-client
except ImportError:
    websocket = None

try:
    import requests  # pip install requests
except ImportError:
    requests = None


def post_with_retry(**kwargs):
    """POST helper with retries for transient Gemini/API failures."""
    if requests is None:
        raise RuntimeError(
            "The requests Python package is not available in this build. "
            "Reinstall/rebuild YVZNETMATH.exe with requirements.txt."
        )

    max_attempts = 2
    retry_statuses = {429, 500, 502, 503, 504}
    last_err = None
    connection_errors = (
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
    )

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(**kwargs)
        except connection_errors as e:
            last_err = e
            if attempt < max_attempts:
                time.sleep(0.8 * (2 ** (attempt - 1)))
                continue
            raise

        if resp.status_code in retry_statuses and attempt < max_attempts:
            wait = 0.8 * (2 ** (attempt - 1))
            print(f"  (attempt {attempt} failed [{resp.status_code}] - retrying in {wait:.1f}s...)")
            time.sleep(wait)
            continue

        return resp

    raise last_err


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DEBUG_PORT = 9222
DEBUG_HOST = "127.0.0.1"
APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "YVZNetMathTool")
CHROME_PROFILE_DIR = os.path.join(APP_DATA_DIR, "ChromeDebugProfile")
CONFIG_PATH = os.path.join(APP_DATA_DIR, "config.json")

# Flash-Lite is Google's fastest/lowest-latency tier - built specifically
# for exactly this kind of quick, low-complexity Q&A workload.
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

SITE_HINTS = ["netmath", "netfrancais"]  # matched against tab URL / title, case-insensitive

# Bumped from 1.0 -> 2.0 for this release: the extraction scoring was
# reworked (instruction-style questions, word-tokenized passages, and
# sibling instruction headings are now handled), and solve_question
# was overhauled with the screenshot-capture feature and the 1-4
# preset menu (Gemini-only, Anthropic/Claude removed as an option).
TOOL_VERSION = "2.3"


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #

def ensure_app_dir():
    os.makedirs(APP_DATA_DIR, exist_ok=True)


def load_config():
    ensure_app_dir()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg):
    ensure_app_dir()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def pause_before_exit():
    print()
    input("Press Enter to close this window...")


def hr(char="-", width=60):
    print(char * width)


def print_header():
    os.system("")  # enables ANSI on some Windows terminals
    hr("=")
    print(f"  YVZTOOLS: NETMATH V{TOOL_VERSION}")
    hr("=")


def print_menu(status_lines=None):
    print()
    if status_lines:
        for line in status_lines:
            print(line)
        hr()
    print("[R] Start Chrome        [Y] Scan Question")
    print("[A] Solve Question      [X] Exit")
    hr()
    print("Press a key: ", end="", flush=True)


def get_keypress():
    """Read a single keypress without requiring Enter (Windows only)."""
    if msvcrt is None:
        # Fallback for non-Windows testing environments
        return input().strip()[:1].upper()
    ch = msvcrt.getch()
    try:
        return ch.decode("utf-8").upper()
    except UnicodeDecodeError:
        return ""


# --------------------------------------------------------------------------- #
# Chrome discovery / launch
# --------------------------------------------------------------------------- #

def find_chrome_exe():
    """Try common locations and the registry to find chrome.exe."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path

    which = shutil.which("chrome")
    if which:
        return which

    # Try the Windows registry App Paths key
    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    value, _ = winreg.QueryValueEx(key, None)
                    if value and os.path.isfile(value):
                        return value
            except OSError:
                continue
    except ImportError:
        pass

    return None


def debug_port_alive():
    try:
        with urllib.request.urlopen(f"http://{DEBUG_HOST}:{DEBUG_PORT}/json/version", timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def chrome_is_running():
    for name in ("chrome.exe", "chrome"):
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {name}"],
                capture_output=True, text=True, timeout=5
            )
            if name.split(".")[0].lower() in result.stdout.lower():
                return True
        except Exception:
            pass
    return False


def start_chrome():
    """Launch Chrome with remote debugging enabled, or confirm it's already running."""
    if debug_port_alive():
        print(f"Chrome is already reachable on port {DEBUG_PORT}.")
        return True

    print("How do you want to connect?")
    print("  [1] My main Chrome profile   - keeps all your logins/history as-is")
    print("                                 (needs a one-time manual step, see below)")
    print("  [2] A separate automation profile - fully automatic, but you'll need to")
    print("                                       log into Netmath once in that window")
    choice = input("Choose 1 or 2: ").strip()

    if choice == "2":
        return start_chrome_separate_profile()
    return start_chrome_main_profile()


def start_chrome_main_profile():
    print()
    print("IMPORTANT - Chrome security change:")
    print("Since Chrome 136, Google blocks the --remote-debugging-port command-line")
    print("flag on your normal/default profile, specifically to stop tools from")
    print("silently reading your saved passwords/cookies. This tool respects that -")
    print("it cannot and will not try to bypass it. Enabling debugging on your main")
    print("profile needs one manual, one-time step directly in Chrome:")
    print()
    print("  1. Make sure Chrome is open.")
    print("  2. Go to this address in a tab:  chrome://inspect/#remote-debugging")
    print("  3. Tick 'Allow remote debugging for this browser instance'.")
    print("  4. Fully quit Chrome (close every window; check Task Manager for any")
    print("     leftover chrome.exe process) and reopen it - the setting only takes")
    print("     effect after a full restart.")
    print()

    chrome_path = find_chrome_exe()
    if not chrome_path:
        print("ERROR: Could not locate chrome.exe on this system.")
        return False

    if chrome_is_running():
        answer = input("Open that settings page for you now, in your current Chrome? (Y/N): ").strip().lower()
        if answer == "y":
            try:
                subprocess.Popen([chrome_path, "chrome://inspect/#remote-debugging"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Could not open Chrome automatically: {e}")
    else:
        print("Opening Chrome to that settings page now...")
        try:
            subprocess.Popen([chrome_path, "chrome://inspect/#remote-debugging"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Could not open Chrome automatically: {e}")

    print()
    input("Once you've ticked the box and FULLY restarted Chrome, press Enter to check again...")

    print("Checking for the debugging port", end="", flush=True)
    for _ in range(20):
        if debug_port_alive():
            print(" connected!")
            return True
        print(".", end="", flush=True)
        time.sleep(0.5)

    print()
    print(f"ERROR: Still couldn't reach port {DEBUG_PORT} on your main profile.")
    print("Double-check you fully closed ALL Chrome windows/processes before")
    print("reopening it, then press [R] again. Or choose option [2] for a fully")
    print("automatic separate profile instead.")
    return False


def start_chrome_separate_profile():
    chrome_path = find_chrome_exe()
    if not chrome_path:
        print("ERROR: Could not locate chrome.exe on this system.")
        print("Please install Google Chrome, or launch it manually with:")
        print(f'  chrome.exe --remote-debugging-port={DEBUG_PORT} --user-data-dir="{CHROME_PROFILE_DIR}"')
        return False

    ensure_app_dir()
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)

    print("Launching Chrome with remote debugging enabled...")
    print("NOTE: This uses a separate Chrome profile dedicated to this tool")
    print("      (so it doesn't conflict with your normal, already-open Chrome).")
    print("      The first time, you may need to log into Netmath again in")
    print("      this new window.")

    args = [
        chrome_path,
        f"--remote-debugging-port={DEBUG_PORT}",
        f'--user-data-dir={CHROME_PROFILE_DIR}',
        "--no-first-run",
        "--no-default-browser-check",
        "https://www.netmath.ca",
    ]
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"ERROR: Failed to launch Chrome: {e}")
        return False

    print("Waiting for Chrome DevTools endpoint to come up", end="", flush=True)
    for _ in range(30):
        if debug_port_alive():
            print(" done.")
            return True
        print(".", end="", flush=True)
        time.sleep(0.5)

    print()
    print(f"ERROR: Chrome did not become reachable on port {DEBUG_PORT} in time.")
    print("Try closing all Chrome windows and running [R] again.")
    return False


def list_tabs():
    try:
        with urllib.request.urlopen(f"http://{DEBUG_HOST}:{DEBUG_PORT}/json", timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        return None
    except Exception:
        return None


def find_netmath_tab():
    tabs = list_tabs()
    if tabs is None:
        print(f"ERROR: Could not reach Chrome DevTools on port {DEBUG_PORT}.")
        print("Make sure Chrome was started with [R] Start Chrome first.")
        return None

    candidates = [
        t for t in tabs
        if t.get("type") == "page"
        and any(
            hint in (t.get("url") or "").lower() or hint in (t.get("title") or "").lower()
            for hint in SITE_HINTS
        )
    ]

    if not candidates:
        print("ERROR: No open Netmath or NetFrancais tab was found.")
        print("Please open netmath.ca or netfrancais.ca in the Chrome window launched by")
        print("this tool, navigate to your question, then press [Y] again.")
        return None

    if len(candidates) == 1:
        return candidates[0]

    print("Multiple Netmath/NetFrancais tabs found:")
    for i, t in enumerate(candidates, 1):
        print(f"  {i}. {t.get('title', '(untitled)')}  -  {t.get('url')}")
    while True:
        choice = input(f"Select a tab [1-{len(candidates)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1]
        print("Invalid selection, try again.")


# --------------------------------------------------------------------------- #
# DOM extraction via CDP (Runtime.evaluate over the tab's websocket)
# --------------------------------------------------------------------------- #

# This JS runs INSIDE the Netmath page. It avoids relying on fixed Netmath
# CSS class names (which can change) and instead uses generic heuristics:
#   - strip obvious chrome (nav/header/footer/ads/buttons/scripts)
#   - score remaining visible text blocks by density + math-keyword hints
#   - separately flag rendered math (KaTeX/MathJax/MathML), images, canvases,
#     SVG graphs, and iframes (e.g. GeoGebra/JSXGraph widgets) that can't be
#     reliably turned into text
#   - pull out anything that looks like multiple-choice answer options
EXTRACTION_JS = r"""
(function() {
  function isVisible(el) {
    if (!el || !(el instanceof Element)) return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 2 && rect.height > 2;
  }

  const EXCLUDE_SELECTOR = [
    'nav', 'header', 'footer', 'aside', 'script', 'style', 'noscript',
    '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]',
    '.navbar', '.nav', '.menu', '.sidebar', '.breadcrumb',
    '.cookie', '.ad', '.advertisement', '.footer', '.header',
    'button', '[role="button"]'
  ].join(',');

  function isExcluded(el) {
    let cur = el;
    while (cur && cur !== document.body) {
      if (cur.matches && cur.matches(EXCLUDE_SELECTOR)) return true;
      cur = cur.parentElement;
    }
    return false;
  }

  const MATH_KEYWORDS = [
    'question', 'exercice', 'exercise', 'probleme', 'problème',
    'enonce', 'énoncé', 'consigne', 'instructions', 'quiz', 'evaluation',
    'énoncé', 'activite', 'activité'
  ];

  // Many Netmath/NetFrancais exercises are phrased as an imperative
  // instruction rather than a "?" question - e.g. "Selectionne les deux
  // adjectifs et le verbe mal accordes." These never got the "?" score
  // bonus below, so they could easily lose to some unrelated block on
  // the page that happens to contain a "?" (nav, sidebar, unrelated
  // card). This checks for the leading verb of that kind of instruction
  // (French first, a few English equivalents too) instead of requiring
  // a question mark.
  const INSTRUCTION_RE = /\b(selectionne|choisis|choisissez|coche|cochez|clique|cliquez|encercle|encerclez|souligne|soulignez|complete|completez|associe|associez|classe|classez|classifie|classifiez|indique|indiquez|identifie|identifiez|trouve|trouvez|ecris|ecrivez|nomme|nommez|relie|reliez|corrige|corrigez|remplace|remplacez|ajoute|ajoutez|entoure|entourez|place|placez|glisse|glissez|reponds|repondez|deplace|deplacez|observe|observez|calcule|calculez|resous|resolvez|explique|expliquez|justifie|justifiez|select|choose|circle|underline|complete|match|classify|identify|find|write|name|connect|correct|replace|add|drag|answer|solve|explain|justify)\b/i;
  function normalizeForMatch(t) {
    // Strip accents so "Sélectionne" also matches "selectionne" etc.
    return t.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function textDensityScore(el) {
    const text = (el.innerText || '').trim();
    if (text.length < 10) return -1;
    const linkCount = el.querySelectorAll('a').length;
    const btnCount = el.querySelectorAll('button, [role="button"]').length;
    const descendantCount = el.querySelectorAll('*').length;
    let score = text.length - (linkCount * 15) - (btnCount * 10) - (descendantCount * 3);
    const classId = ((el.className || '') + ' ' + (el.id || '')).toLowerCase();
    for (const kw of MATH_KEYWORDS) {
      if (classId.includes(kw)) score += 200;
    }
    // Prefer blocks that actually ask something (a real "?"), OR that
    // open with a French/English imperative instruction verb - Netmath
    // frequently uses the latter phrasing instead of a question mark.
    // Only check the first ~120 chars so a stray match of a common word
    // deep inside a long passage doesn't trigger this on unrelated text.
    const leadText = normalizeForMatch(text.slice(0, 120));
    if (text.includes('?') || INSTRUCTION_RE.test(leadText)) score += 400;
    if (/^\s*(exemple|example)\b/i.test(text) || /\bexemple\s*:/i.test(text.slice(0, 80))) {
      score -= 350;
    }
    const hasNearbyInput = !!(
      el.querySelector('input, textarea, [contenteditable="true"]') ||
      (el.parentElement && el.parentElement.querySelector('input, textarea, [contenteditable="true"]'))
    );
    if (hasNearbyInput) score += 250;
    return score;
  }

  // Gather candidate content blocks
  const all = Array.from(document.querySelectorAll('body *'));
  let best = null;
  let bestScore = -1;

  for (const el of all) {
    if (!isVisible(el)) continue;
    if (isExcluded(el)) continue;
    // Some exercises wrap almost every word of the passage in its own
    // clickable <span> (e.g. "select the misused words" activities),
    // which can easily push direct child count past 40 for a single
    // normal-length paragraph. Filtering on DIRECT children like the
    // old check did throws those blocks out before they're even
    // scored. Instead, only bail out on elements that are huge by TOTAL
    // descendant count - that still catches genuine full-page wrapper
    // divs (which is what this guard is meant to protect against)
    // without discarding a word-tokenized paragraph.
    if (el.querySelectorAll('*').length > 150) continue;
    const s = textDensityScore(el);
    if (s > bestScore) {
      bestScore = s;
      best = el;
    }
  }

  let container = best || document.body;

  // The instruction line (e.g. "Selectionne les deux adjectifs et le
  // verbe mal accordes.") is often a sibling heading OUTSIDE the block
  // that scored best (that block is just the passage/answer card), not
  // an ancestor with a helpful class name. Walk up a few levels and, at
  // each level, check for a short heading-like element that sits next
  // to (not inside) the picked block; if found, widen container to
  // include it so it isn't lost from the extracted text.
  function findAdjacentInstruction(el) {
    let node = el;
    for (let depth = 0; depth < 3 && node && node.parentElement; depth++) {
      const parent = node.parentElement;
      for (const child of parent.children) {
        if (child === node || (node.contains && node.contains(child))) continue;
        if (!isVisible(child)) continue;
        const t = (child.innerText || '').trim();
        if (!t || t.length > 200) continue;
        const isHeadingTag = /^H[1-6]$/.test(child.tagName);
        const classId = ((child.className || '') + ' ' + (child.id || '')).toLowerCase();
        const looksLikeInstruction = isHeadingTag ||
          /titre|title|instruction|consigne|enonce/.test(classId) ||
          INSTRUCTION_RE.test(normalizeForMatch(t.slice(0, 120)));
        if (looksLikeInstruction) return { heading: child, ancestor: parent };
      }
      node = parent;
    }
    return null;
  }

  const adjacent = findAdjacentInstruction(container);
  if (adjacent && adjacent.ancestor.querySelectorAll('*').length <= 150) {
    container = adjacent.ancestor;
  }

  // Detect rendered math markup within the container (or nearby, in case
  // math lives in a sibling block that scored slightly lower)
  const searchRoot = container.closest('main, [class*="content"], [class*="main"]') || container;

  function has(selector, root) {
    return !!root.querySelector(selector);
  }

  const mathRendered = has('.katex, .MathJax, mjx-container, math, [class*="mathml"]', searchRoot);
  const hasImage = Array.from(searchRoot.querySelectorAll('img')).some(isVisible);
  const hasCanvas = Array.from(searchRoot.querySelectorAll('canvas')).some(isVisible);
  const hasSvgGraph = Array.from(searchRoot.querySelectorAll('svg')).some(
    svg => isVisible(svg) && !svg.closest('.katex, .MathJax, mjx-container')
  );
  const hasIframe = Array.from(searchRoot.querySelectorAll('iframe')).some(isVisible);
  const geoWidget = has('[class*="geogebra"], [class*="jsxgraph"], [class*="graphique"], [id*="geogebra"]', searchRoot);

  // Try to find answer choices: radios, checkboxes, or list items that look like options
  let choices = [];
  const radioLabels = Array.from(searchRoot.querySelectorAll('input[type="radio"], input[type="checkbox"]'))
    .map(inp => {
      let label = '';
      if (inp.id) {
        const lbl = document.querySelector(`label[for="${inp.id}"]`);
        if (lbl) label = lbl.innerText.trim();
      }
      if (!label && inp.closest('label')) {
        label = inp.closest('label').innerText.trim();
      }
      if (!label && inp.parentElement) {
        label = inp.parentElement.innerText.trim();
      }
      return label;
    })
    .filter(t => t && t.length > 0 && t.length < 300);
  choices = Array.from(new Set(radioLabels));

  // -------------------------------------------------------------------
  // KaTeX fixup: KaTeX renders fractions/exponents/roots as visually
  // stacked <span> layers (numerator span above a denominator span).
  // Plain .innerText reads DOM order top-to-bottom, so "1/(2+3)" comes
  // out as "1", newline, "2 + 3" - ambiguous once flattened to text.
  //
  // KaTeX also embeds the original LaTeX source in a hidden
  // <annotation encoding="application/x-tex"> tag. We read THAT
  // instead of the stacked visual layout and linearize it to plain
  // text (e.g. \frac{1}{2+3} -> (1)/(2+3)).
  // -------------------------------------------------------------------
  function texToPlain(tex) {
    if (!tex) return '';
    let s = tex;

    function resolveFrac(str) {
      const fracRe = /\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/;
      let m, guard = 0;
      while ((m = fracRe.exec(str)) && guard < 50) {
        str = str.slice(0, m.index) + '(' + m[1] + ')/(' + m[2] + ')' + str.slice(m.index + m[0].length);
        guard++;
      }
      return str;
    }
    let prev;
    do { prev = s; s = resolveFrac(s); } while (s !== prev);

    s = s.replace(/\\sqrt\s*\[(\d+)\]\s*\{([^{}]*)\}/g, 'root($1,$2)');
    s = s.replace(/\\sqrt\s*\{([^{}]*)\}/g, 'sqrt($1)');
    s = s.replace(/\^\s*\{([^{}]*)\}/g, '^($1)');
    s = s.replace(/_\s*\{([^{}]*)\}/g, '_($1)');
    s = s.replace(/\\left|\\right/g, '');
    s = s.replace(/\\times/g, ' * ');
    s = s.replace(/\\cdot/g, ' * ');
    s = s.replace(/\\div/g, ' / ');
    s = s.replace(/\\pm/g, ' +/- ');
    s = s.replace(/\\le(q)?/g, ' <= ');
    s = s.replace(/\\ge(q)?/g, ' >= ');
    s = s.replace(/\\neq/g, ' != ');
    s = s.replace(/\\%/g, '%');
    s = s.replace(/\\,|\\;|\\:|\\!|\\ /g, ' ');
    s = s.replace(/[{}]/g, '');
    s = s.replace(/\\([a-zA-Z]+)/g, ' $1 ');
    s = s.replace(/\s{2,}/g, ' ').trim();
    return s;
  }

  const workingRoot = searchRoot.cloneNode(true);
  const katexNodes = Array.from(workingRoot.querySelectorAll('.katex'));
  for (const kx of katexNodes) {
    if (kx.parentElement && kx.parentElement.closest('.katex')) continue;
    const annotation = kx.querySelector('annotation[encoding="application/x-tex"]');
    let replacementText = null;
    if (annotation && annotation.textContent && annotation.textContent.trim()) {
      replacementText = texToPlain(annotation.textContent.trim());
    }
    if (replacementText) {
      const marker = document.createTextNode(' ' + replacementText + ' ');
      kx.replaceWith(marker);
    }
  }

  let questionText = (workingRoot.innerText || container.innerText || '').trim();
  // Collapse excessive blank lines
  questionText = questionText.replace(/\n{3,}/g, '\n\n');
  questionText = questionText.replace(/[ \t]{2,}/g, ' ');

  return JSON.stringify({
    questionText: questionText.slice(0, 6000),
    choices: choices.slice(0, 12),
    mathRendered: mathRendered,
    hasImage: hasImage,
    hasCanvas: hasCanvas,
    hasSvgGraph: hasSvgGraph,
    hasIframe: hasIframe,
    geoWidget: geoWidget,
    pageTitle: document.title,
    pageUrl: location.href
  });
})();
"""


def evaluate_in_tab(ws_url, expression, timeout=10):
    """Send a Runtime.evaluate command over the tab's CDP websocket and return the value."""
    if websocket is None:
        raise RuntimeError(
            "The 'websocket-client' package is required. Install it with:\n"
            "  pip install websocket-client"
        )

    ws = websocket.create_connection(ws_url, timeout=timeout)
    try:
        msg_id = 1
        ws.send(json.dumps({
            "id": msg_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        }))

        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                result = data.get("result", {})
                if "exceptionDetails" in result:
                    raise RuntimeError(
                        "Page script error: " +
                        json.dumps(result["exceptionDetails"].get("text", "unknown error"))
                    )
                value = result.get("result", {}).get("value")
                return value
        raise RuntimeError("Timed out waiting for a response from Chrome.")
    finally:
        ws.close()


def capture_tab_screenshot_base64(ws_url, timeout=20):
    """Capture a PNG screenshot of just the tab's viewport via CDP
    Page.captureScreenshot - not the whole desktop, and not via the
    Windows Snipping Tool. This is deliberate: it's fully automatic (no
    manual drag-to-select, no window-focus dependency) and it can't
    accidentally grab something else on screen the way a full-screen
    snip could.

    PRIVACY: the returned base64 string is only ever held in memory for
    this run. It is never written to a file on disk - the caller sends
    it straight into the HTTPS request body for whichever AI provider
    was chosen, and it's discarded once solving finishes.
    """
    if websocket is None:
        raise RuntimeError(
            "The 'websocket-client' package is required. Install it with:\n"
            "  pip install websocket-client"
        )

    ws = websocket.create_connection(ws_url, timeout=timeout)
    try:
        msg_id = 1
        ws.send(json.dumps({
            "id": msg_id,
            "method": "Page.captureScreenshot",
            "params": {"format": "png"},
        }))

        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    raise RuntimeError(f"CDP error: {data['error'].get('message')}")
                b64 = data.get("result", {}).get("data")
                if not b64:
                    raise RuntimeError("Chrome did not return screenshot data.")
                return b64
        raise RuntimeError("Timed out waiting for a screenshot from Chrome.")
    finally:
        ws.close()


def scan_question():
    tab = find_netmath_tab()
    if tab is None:
        return None, None

    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        print("ERROR: This tab does not expose a debugger websocket URL.")
        print("Try reloading the Netmath page and pressing [Y] again.")
        return None, None

    print(f'Reading tab: "{tab.get("title", "")}"')
    try:
        raw_json = evaluate_in_tab(ws_url, EXTRACTION_JS)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return None, None

    if not raw_json:
        print("ERROR: No content could be extracted from the page.")
        return None, None

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        print("ERROR: Could not parse extracted page content.")
        return None, None

    return data, tab


def print_extracted(data):
    print()
    hr("=")
    print("EXTRACTED QUESTION")
    hr("=")
    text = data.get("questionText", "").strip()
    print(text if text else "(no readable text found)")
    print()

    choices = data.get("choices") or []
    if choices:
        print("Answer choices detected:")
        for i, c in enumerate(choices, 1):
            print(f"  {i}. {c}")
        print()

    warnings = []
    if data.get("hasImage"):
        warnings.append("This question includes an IMAGE. The tool cannot read image content, "
                         "so any diagram, photo, or picture-based detail is NOT included above.")
    if data.get("hasCanvas"):
        warnings.append("This question includes a CANVAS element (often an interactive drawing "
                         "or graph). Its contents cannot be extracted as text.")
    if data.get("hasSvgGraph"):
        warnings.append("This question includes an SVG graphic (possibly a graph or figure) "
                         "that cannot be reliably converted to text.")
    if data.get("geoWidget"):
        warnings.append("This question appears to use an interactive math widget "
                         "(e.g. GeoGebra/JSXGraph). Its content cannot be extracted.")
    if data.get("hasIframe"):
        warnings.append("This question embeds an iframe (external widget/content) that "
                         "cannot be inspected by this tool.")

    if warnings:
        hr("-")
        print("NOTE - Content this tool could NOT reliably extract:")
        for w in warnings:
            print(f"  - {w}")
        print("  You should visually check the Netmath page for these elements yourself.")

    hr("=")


# --------------------------------------------------------------------------- #
# AI solving
# --------------------------------------------------------------------------- #

def get_gemini_api_key(force_new=False):
    cfg = load_config()
    key = os.environ.get("GEMINI_API_KEY") or cfg.get("gemini_api_key")

    if key and not force_new:
        # Preset already told us to keep the current key - just use it,
        # no extra "use this key? Y/N" prompt.
        return key

    print()
    if key:
        print("Enter a new Gemini API key (this replaces the saved one).")
    else:
        print("Enter your Gemini API key.")
    print("You can get one (free tier available) at https://aistudio.google.com/apikey")
    new_key = input("Paste your Gemini API key (it will be saved locally for next time): ").strip()
    if new_key:
        cfg["gemini_api_key"] = new_key
        save_config(cfg)
        return new_key
    return key or None


def solve_question(extracted, tab=None):
    if requests is None:
        print("ERROR: The 'requests' package is required. Install it with:")
        print("  pip install requests")
        return

    if not extracted:
        print("No question has been scanned yet. Press [Y] first.")
        return

    question_text = (extracted.get("questionText") or "").strip()
    if not question_text:
        print("Nothing was extracted to solve. Press [Y] to scan again.")
        return

    print()
    print("How do you want to solve this (Gemini)?")
    print("  [1] Keep current API key, TAKE screenshot")
    print("  [2] Keep current API key, NO screenshot")
    print("  [3] Change API key,       TAKE screenshot")
    print("  [4] Change API key,       NO screenshot")
    preset = input("Choose 1-4: ").strip()

    presets = {
        "1": (False, True),
        "2": (False, False),
        "3": (True, True),
        "4": (True, False),
    }
    if preset not in presets:
        print("Invalid choice - defaulting to [2] keep current key, no screenshot.")
    force_new_key, want_screenshot = presets.get(preset, (False, False))

    api_key = get_gemini_api_key(force_new=force_new_key)
    if not api_key:
        print("Cannot solve without an API key.")
        return

    choices = extracted.get("choices") or []
    missing_bits = []
    if extracted.get("hasImage"):
        missing_bits.append("an image")
    if extracted.get("hasCanvas"):
        missing_bits.append("a canvas element")
    if extracted.get("hasSvgGraph"):
        missing_bits.append("an SVG graph/figure")
    if extracted.get("geoWidget"):
        missing_bits.append("an interactive math widget")

    screenshot_b64 = None
    ws_url = (tab or {}).get("webSocketDebuggerUrl")
    if want_screenshot:
        if ws_url:
            try:
                print("Capturing screenshot of the tab...")
                screenshot_b64 = capture_tab_screenshot_base64(ws_url)
                print("Screenshot captured (kept in memory only - not saved to disk).")
            except RuntimeError as e:
                print(f"Could not capture a screenshot: {e}")
                print("Continuing with text only.")
        else:
            print("No scanned tab on record to screenshot - press [Y] first. Continuing with text only.")

    caveat = ""
    if missing_bits and not screenshot_b64:
        caveat = (f"\n\nNOTE: The original page also contains {', '.join(missing_bits)} "
                  "that could not be extracted as text. If the question cannot be fully "
                  "understood without it, say so explicitly instead of guessing.")

    choices_block = ""
    if choices:
        choices_block = "\n\nAnswer choices shown on the page:\n" + "\n".join(
            f"- {c}" for c in choices
        )

    user_prompt = (
        "You are a tutor helping a student understand a homework/quiz question "
        "extracted from a webpage (math or language-arts). Solve or answer it and "
        "explain your reasoning clearly, but be concise - short steps, no filler, "
        "no restating the same idea twice.\n\n"
        f"QUESTION TEXT (as extracted from the page):\n{question_text}"
        f"{choices_block}{caveat}\n\n"
        "Respond using exactly this format:\n"
        "QUESTION:\n<restate the question clearly, cleaned up>\n\n"
        "SOLUTION:\n<brief step-by-step reasoning - as few steps as needed to justify the answer>\n\n"
        "ANSWER:\n<final answer only>"
    )

    print()
    print(f"Sending question to Gemini{' with screenshot' if screenshot_b64 else ''}...")

    solution_text = None
    try:
        parts = []
        if screenshot_b64:
            parts.append({"inlineData": {"mimeType": "image/png", "data": screenshot_b64}})
        parts.append({"text": user_prompt})
        resp = post_with_retry(
            url=GEMINI_API_URL,
            params={"key": api_key},
            json={
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": {"maxOutputTokens": 700},
            },
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"ERROR: Could not reach the AI solving service: {e}")
        return

    if resp.status_code != 200:
        print(f"ERROR: AI service returned status {resp.status_code}.")
        try:
            print(resp.json())
        except Exception:
            print(resp.text[:500])
        return

    try:
        body = resp.json()
        text_parts = []
        for cand in body.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                if part.get("text"):
                    text_parts.append(part["text"])
        solution_text = "\n".join(text_parts).strip()
    except Exception:
        print("ERROR: Could not parse the AI service's response.")
        return

    print()
    hr("=")
    print(solution_text if solution_text else "(empty response from AI)")
    hr("=")
    print()
    print("Reminder: enter and submit this answer YOURSELF in Netmath.")
    print("This tool will never submit anything on your behalf.")


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #

def main():
    last_extracted = None
    last_tab = None
    chrome_started = False

    while True:
        print_header()
        status = []
        status.append(f"Chrome debug port: {'reachable' if debug_port_alive() else 'not detected'}")
        status.append(f"Last scanned question: {'yes' if last_extracted else 'none yet'}")
        print_menu(status)

        key = get_keypress()
        print(key)

        if key == "R":
            hr()
            chrome_started = start_chrome()
        elif key == "Y":
            hr()
            try:
                data, tab = scan_question()
            except Exception:
                print("An unexpected error occurred while scanning:")
                traceback.print_exc()
                data, tab = None, None
            if data:
                last_extracted = data
                last_tab = tab
                print_extracted(data)
        elif key == "A":
            hr()
            try:
                solve_question(last_extracted, last_tab)
            except Exception:
                print("An unexpected error occurred while solving:")
                traceback.print_exc()
        elif key == "X":
            print("Exiting. Goodbye!")
            break
        else:
            print("Unrecognized key. Use R, Y, A, or X.")

        print()
        input("Press Enter to return to the menu...")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print()
        print("A fatal error occurred:")
        traceback.print_exc()
    finally:
        pause_before_exit()
