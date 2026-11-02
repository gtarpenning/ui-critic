#!/usr/bin/env python3
"""Render one state of the Beeri HTML prototype, as it was at a given commit, to a PNG plus the DOM boxes of its
tappable elements (the boxes are ground truth for the bounding-box eval). Input: a JSON list of shots."""
import json, os, subprocess, sys, time, http.server, socketserver, threading, functools
from playwright.sync_api import sync_playwright

PROTO, SHOTS, OUT = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
os.makedirs(OUT, exist_ok=True)

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def serve(root):
    h = functools.partial(Quiet, directory=root)
    s = socketserver.ThreadingTCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, s.server_address[1]

BOXES = """() => [...document.querySelectorAll('[data-act], h1, h2, h3, button, img, .pill, [class*=pill]')].map(e => {
  const r = e.getBoundingClientRect();
  return {tag: e.tagName, cls: String(e.className).slice(0,60), act: e.dataset.act||'', arg: e.dataset.arg||'',
          text: (e.innerText||e.getAttribute('aria-label')||'').trim().replace(/\\s+/g,' ').slice(0,60),
          box: [r.left,r.top,r.right,r.bottom].map(n => Math.round(n*2))};
}).filter(b => b.box[2]-b.box[0]>12 && b.box[3]-b.box[1]>12 && b.box[1]<1688 && b.box[3]>0 && b.box[2]<=780)"""

with sync_playwright() as p:
    b = p.chromium.launch(channel="chromium")
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    servers = {}
    for s in SHOTS:
        root = f"{PROTO}/{s['commit']}/prototype"
        if root not in servers: servers[root] = serve(root)
        port = servers[root][1]
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{port}/app/app.html?variant={s['variant']}&scenario={s.get('scenario','active')}&theme=light")
        page.wait_for_function("window.Beeri !== undefined")
        page.wait_for_timeout(500)
        for st in s.get('script', []):
            page.evaluate("""([a,g]) => window.postMessage({beeri:true,type:'dispatch',act:a,arg:g},'*')""", [st['act'], st.get('arg')])
            page.wait_for_timeout(250)
        page.wait_for_timeout(400)
        if s.get('scroll'):
            page.evaluate("""(sel) => { const e=document.querySelector(sel); if(e) e.scrollIntoView({block:'start'}); }""", s['scroll'])
            page.wait_for_timeout(200)
        page.screenshot(path=f"{OUT}/{s['id']}.png")
        json.dump(page.evaluate(BOXES), open(f"{OUT}/{s['id']}.boxes.json", "w"))
        page.close()
    b.close()
