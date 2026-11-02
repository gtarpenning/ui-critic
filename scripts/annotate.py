#!/usr/bin/env python3
"""Draw a critique's findings on its screenshots. Writes <name>.annotated.png per screen and one report.html where
hovering a finding highlights its box. Storyboards work: pass several screens, findings say which one they are on.

findings.json:
{"verdict": "...", "screens": [{"path": "prepared.png", "label": "Home"}],
 "findings": [{"screen": 0, "box": [x1, y1, x2, y2], "severity": "high|medium|low", "title": "...", "why": "...", "fix": "..."}]}

  annotate.py findings.json --out /tmp/review
"""
import argparse, base64, html, json, os
from PIL import Image, ImageDraw, ImageFont

COLORS = {'high': (214, 48, 49), 'medium': (225, 112, 0), 'low': (9, 132, 227)}


def font(size):
    for f in ('/System/Library/Fonts/SFNS.ttf', '/System/Library/Fonts/Helvetica.ttc',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def clamp(box, w, h):
    x1, y1, x2, y2 = box
    x1, x2 = sorted((max(0, min(w, x1)), max(0, min(w, x2))))
    y1, y2 = sorted((max(0, min(h, y1)), max(0, min(h, y2))))
    return [x1, y1, x2, y2]


def draw(im, items):
    im = im.convert('RGB')
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w = max(3, im.width // 220)
    r = max(13, im.width // 34)
    f = font(int(r * 1.15))
    for n, finding in items:
        c = COLORS.get(finding.get('severity'), COLORS['medium'])
        x1, y1, x2, y2 = clamp(finding['box'], *im.size)
        d.rounded_rectangle([x1, y1, x2, y2], radius=8, outline=c + (255,), width=w, fill=c + (26,))
        # The number sits on the box's corner, moved inside if it would leave the image.
        cx, cy = min(max(x1, r + 1), im.width - r - 1), min(max(y1, r + 1), im.height - r - 1)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c + (255,), outline=(255, 255, 255, 255), width=2)
        d.text((cx, cy), str(n), fill='white', font=f, anchor='mm')
    return Image.alpha_composite(im.convert('RGBA'), layer).convert('RGB')


PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>UI critique</title><style>
:root{--bg:#f6f6f7;--fg:#17171a;--muted:#6b6b73;--card:#fff;--line:#e4e4e8}
@media(prefers-color-scheme:dark){:root{--bg:#141416;--fg:#f2f2f4;--muted:#a0a0a8;--card:#1f1f23;--line:#333338}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,system-ui,sans-serif;padding:16px}
main{max-width:1200px;margin:auto}h1{font-size:20px;margin:0 0 16px}.grid{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start}
.screens{display:flex;gap:16px;overflow-x:auto;flex:1 1 320px;max-width:100%}figure{margin:0;flex:none}figcaption{color:var(--muted);font-size:13px;margin-bottom:6px}
.s{position:relative;width:min(340px,80vw)}.s img{width:100%;display:block;border-radius:12px}.b{position:absolute;border:3px solid;border-radius:6px;transition:.12s}
.b span{position:absolute;left:-11px;top:-11px;width:22px;height:22px;border-radius:50%;color:#fff;font:600 12px/22px system-ui;text-align:center}
.dim .b:not(.on){opacity:.15}ol{list-style:none;margin:0;padding:0;flex:1 1 320px;display:grid;gap:10px}
li{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;cursor:default}li.on{border-color:var(--fg)}
li b{display:block}li p{margin:4px 0 0}.m{color:var(--muted)}</style><main><h1>%(verdict)s</h1><div class=grid id=g>
<div class=screens>%(screens)s</div><ol>%(items)s</ol></div></main><script>
const g=document.getElementById('g');const set=(n,on)=>{g.classList.toggle('dim',on);
document.querySelectorAll('[data-n="'+n+'"]').forEach(e=>e.classList.toggle('on',on))};
document.querySelectorAll('[data-n]').forEach(e=>{e.onmouseenter=()=>set(e.dataset.n,true);e.onmouseleave=()=>set(e.dataset.n,false);
e.onclick=()=>set(e.dataset.n,!e.classList.contains('on'))});</script>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('findings')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    data = json.load(open(a.findings))
    base = os.path.dirname(os.path.abspath(a.findings))
    os.makedirs(a.out, exist_ok=True)
    numbered = list(enumerate(data.get('findings', []), 1))
    screens_html, written = [], []
    for i, s in enumerate(data['screens']):
        src = s['path'] if os.path.isabs(s['path']) else os.path.join(base, s['path'])
        im = Image.open(src)
        mine = [(n, f) for n, f in numbered if f.get('screen', 0) == i and f.get('box')]
        out = os.path.join(a.out, os.path.splitext(os.path.basename(src))[0] + '.annotated.png')
        draw(im, mine).save(out)
        written.append(out)
        boxes = ''
        for n, f in mine:
            x1, y1, x2, y2 = clamp(f['box'], *im.size)
            c = 'rgb(%d,%d,%d)' % COLORS.get(f.get('severity'), COLORS['medium'])
            boxes += (f'<div class=b data-n={n} style="left:{x1 / im.width:.2%};top:{y1 / im.height:.2%};width:{(x2 - x1) / im.width:.2%};'
                      f'height:{(y2 - y1) / im.height:.2%};border-color:{c}"><span style="background:{c}">{n}</span></div>')
        with open(src, 'rb') as fh:
            b64 = base64.b64encode(fh.read()).decode()
        screens_html.append(f'<figure><figcaption>{html.escape(s.get("label", ""))}</figcaption><div class=s>'
                            f'<img alt="{html.escape(s.get("label", "screen"))}" src="data:image/png;base64,{b64}">{boxes}</div></figure>')
    items = ''.join(f'<li data-n={n}><b>{n}. {html.escape(f.get("title", ""))}</b><p>{html.escape(f.get("why", ""))}</p>'
                    f'<p class=m>Fix: {html.escape(f.get("fix", ""))}</p></li>' for n, f in numbered)
    report = os.path.join(a.out, 'report.html')
    with open(report, 'w') as fh:
        fh.write(PAGE.replace('%(verdict)s', html.escape(data.get('verdict', 'Critique'))).replace('%(screens)s', ''.join(screens_html)).replace('%(items)s', items))
    print(json.dumps({'report': os.path.abspath(report), 'annotated': [os.path.abspath(p) for p in written]}))


if __name__ == '__main__':
    main()
