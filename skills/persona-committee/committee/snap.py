"""Page 1's annotated asset.

For a URL: headless Chrome (driven over the DevTools protocol with the standard library only) takes a
full-page screenshot and finds where each message sits on the page, so the report can pin numbered
markers on the real layout. For text assets, or if Chrome is unavailable, the report shows the text in
a light frame with the same numbered markers.
"""
import base64
import json
import os
import random
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request

CHROME_PATHS = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium", "google-chrome", "chromium", "chromium-browser"]

FIND_JS = r"""
(function(needles){
  const norm = s => s.replace(/[\u2018\u2019]/g,"'").replace(/[\u201c\u201d]/g,'"').replace(/[\u2122\u00ae*]/g,'').replace(/\s+/g,' ').trim().toLowerCase();
  const out = {}; window.__pcEls = {};
  const els = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,p,li,a,span,div,td,th,button,strong,b,section'));
  const rects = els.map(el => { const r = el.getBoundingClientRect(); return {el, r, t: norm(el.innerText || '')}; })
                   .filter(o => o.r.width >= 8 && o.r.height >= 8 && o.t && o.t.length <= 900);
  for (const [id, text] of Object.entries(needles)) {
    const want = norm(text); const words = [...new Set(want.split(' ').filter(w => w.length > 1))];
    let best = null;
    for (const cut of [0.9, 0.75, 0.55]) {
      const cands = [];
      for (const o of rects) {
        const hit = words.filter(w => o.t.includes(w)).length;
        if (!words.length || hit / words.length < cut) continue;
        cands.push({area: o.r.width * o.r.height, el: o.el, r: o.r, y: o.r.top + scrollY, len: o.t.length, cov: hit / words.length});
      }
      if (!cands.length) continue;
      // near-exact text first, then the first occurrence on the page, then the smallest element
      const tight = cands.filter(c => c.len <= want.length * 1.6 + 12);
      const pool = tight.length ? tight : cands;
      const gap = c => Math.floor(Math.abs(c.len - want.length) / 12);
      pool.sort((a, b) => (gap(a) - gap(b)) || (a.y - b.y) || (a.area - b.area));
      best = pool[0];
      break;
    }
    if (best) {
      // stat tiles split the number from its caption: climb until the numbers are included
      const nums = (want.match(/\d[\d.,]*/g) || []);
      let el = best.el, steps = 0;
      while (nums.length && el.parentElement && steps < 3 && !nums.every(n => norm(el.innerText || '').includes(n))) {
        el = el.parentElement; steps++;
      }
      if (el !== best.el && nums.every(n => norm(el.innerText || '').includes(n))) best = Object.assign(best, {el, r: el.getBoundingClientRect()});
    }
    if (best) {
      window.__pcEls[id] = best.el;
      // use the rendered text, not the layout box: animated text can be drawn away from its box
      const rg = document.createRange(); rg.selectNodeContents(best.el);
      const rr = Array.from(rg.getClientRects()).filter(q => q.width > 1 && q.height > 1);
      let r = best.r;
      if (rr.length) {
        const L = Math.min(...rr.map(q => q.left)), T = Math.min(...rr.map(q => q.top));
        const R = Math.max(...rr.map(q => q.right)), B = Math.max(...rr.map(q => q.bottom));
        r = {left: L, top: T, width: R - L, height: B - T};
      }
      out[id] = {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height, score: Math.round(best.cov * 100)};
    }
  }
  return JSON.stringify({boxes: out, width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight, sy: scrollY});
})
"""


HIDE_JS = r"""
(function(){
  document.documentElement.style.scrollBehavior = 'auto';
  document.body && (document.body.style.scrollBehavior = 'auto');
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if ((cs.position === 'fixed' || cs.position === 'sticky') && /cookie|consent|privacy rights|personal information/i.test(el.innerText || '')) {
      el.style.setProperty('display', 'none', 'important');
    }
  }
  scrollTo(0, 0);
})()
"""


MARK_JS = r"""
(function(nums){
  for (const [id, n] of Object.entries(nums)) {
    const el = (window.__pcEls || {})[id]; if (!el) continue;
    el.style.setProperty('outline', '4px solid #052B42', 'important');
    el.style.setProperty('outline-offset', '6px', 'important');
    el.style.setProperty('border-radius', '6px');
    if (getComputedStyle(el).position === 'static') el.style.position = 'relative';
    const pin = document.createElement('span');
    pin.textContent = n;
    pin.style.cssText = 'position:absolute;left:-34px;top:-30px;width:46px;height:46px;border-radius:50%;background:#052B42;' +
      'color:#fff;font:700 24px/46px Inter,Arial,sans-serif;text-align:center;z-index:2147483647;letter-spacing:0;' +
      'box-shadow:0 0 0 4px #fff,0 2px 10px rgba(0,0,0,.3);pointer-events:none;text-transform:none';
    el.appendChild(pin);
  }
})
"""


def _chrome():
    for p in CHROME_PATHS:
        if os.path.exists(p) or shutil.which(p):
            return p if os.path.exists(p) else shutil.which(p)
    return None


class _WS:
    """Just enough of a websocket client for the DevTools protocol."""

    def __init__(self, url):
        host_port, path = url[5:].split("/", 1)
        host, port = host_port.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET /{path} HTTP/1.1\r\nHost: {host_port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            resp += self.sock.recv(4096)
        self.buf = resp.split(b"\r\n\r\n", 1)[1]
        self.n = 0

    def _recv_exact(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(1 << 20)
            if not chunk:
                raise ConnectionError("closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _frame(self):
        b1, b2 = self._recv_exact(2)
        ln = b2 & 0x7F
        if ln == 126:
            ln = struct.unpack(">H", self._recv_exact(2))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", self._recv_exact(8))[0]
        return b1 & 0x80, b1 & 0x0F, self._recv_exact(ln)

    def send(self, method, params=None):
        self.n += 1
        payload = json.dumps({"id": self.n, "method": method, "params": params or {}}).encode()
        mask = os.urandom(4)
        head = bytes([0x81])
        ln = len(payload)
        head += bytes([0x80 | ln]) if ln < 126 else (bytes([0x80 | 126]) + struct.pack(">H", ln) if ln < 65536
                                                      else bytes([0x80 | 127]) + struct.pack(">Q", ln))
        self.sock.sendall(head + mask + bytes(c ^ mask[k % 4] for k, c in enumerate(payload)))
        want = self.n
        while True:
            data, fin = b"", 0
            while not fin:
                fin, op, part = self._frame()
                data += part
            msg = json.loads(data.decode("utf-8", "ignore"))
            if msg.get("id") == want:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})


def capture(url, needles, out_path, width=1280, max_height=6000, numbers=None):
    """Returns {"image": path, "width": w, "height": h, "boxes": {claim_id: {x,y,w,h}}} or None."""
    chrome = _chrome()
    if not chrome:
        return None
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]
    prof = tempfile.mkdtemp(prefix="pc-chrome-")
    proc = subprocess.Popen([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={port}",
                             f"--user-data-dir={prof}", f"--window-size={width},900", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(40):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2))
                ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t.get("type") == "page")
                break
            except Exception:
                time.sleep(0.5)
        if not ws_url:
            return None
        ws = _WS(ws_url)
        ws.send("Page.enable")
        ws.send("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        ws.send("Page.navigate", {"url": url})
        for _ in range(40):
            time.sleep(0.5)
            st = ws.send("Runtime.evaluate", {"expression": "document.readyState", "returnByValue": True})
            if st.get("result", {}).get("value") == "complete":
                break
        # scroll through once so lazy content renders, then return to top
        # no smooth scrolling; hide cookie and consent overlays
        ws.send("Runtime.evaluate", {"expression": HIDE_JS})
        # scroll through slowly so lazy content loads and count-up animations finish, then return to the top
        ws.send("Runtime.evaluate", {"expression": "(async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,450));}await new Promise(r=>setTimeout(r,2500));scrollTo(0,0);})()",
                                     "awaitPromise": True})
        ws.send("Runtime.evaluate", {"expression": HIDE_JS})
        # measure until the layout is stable, in the same state we capture
        info, prev = None, None
        for _ in range(8):
            time.sleep(0.8)
            res = ws.send("Runtime.evaluate", {"expression": FIND_JS + f"({json.dumps(needles)})", "returnByValue": True})
            info = json.loads(res["result"]["value"])
            sig = json.dumps(info["boxes"], sort_keys=True)
            if info.get("sy", 0) == 0 and sig == prev:
                break
            prev = sig
        h = min(int(info["height"]), max_height)
        # draw numbered markers into the page itself so they share the page's coordinates exactly
        marks = {k: (numbers or {}).get(k, k) for k, v in info["boxes"].items() if v["y"] < h}
        ws.send("Runtime.evaluate", {"expression": MARK_JS + f"({json.dumps(marks)})"})
        time.sleep(0.4)
        shot = ws.send("Page.captureScreenshot", {"format": "jpeg", "quality": 72, "captureBeyondViewport": True,
                                                  "clip": {"x": 0, "y": 0, "width": width, "height": h, "scale": 1}})
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        boxes = {k: v for k, v in info["boxes"].items() if v["y"] < h}
        return {"image": str(out_path), "width": width, "height": h, "boxes": boxes}
    except Exception:
        return None
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(prof, ignore_errors=True)
