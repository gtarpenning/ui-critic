#!/usr/bin/env python3
"""Choose which past decisions a review should look at: closest to this screen first, newest first, one per topic
before doubling up. Taste moves, so a newer decision outranks an older one. Prints JSON lines with absolute image paths.

With --sheet DIR, also writes one image per case with the chosen design on the left and the rejected one on the
right, so each case is a single Read.

  cases.py --context "the Home tab of a social app" --k 4 [--sheet /tmp/x] [--exclude-topic home]
"""
import argparse, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASTE = os.path.join(ROOT, 'taste')
STOP = set('a an the of to and or in on for with your you it is this that where app iphone screen page what they then'.split())
PANE_H = 1400  # Two panes side by side stay under the 1568px edge Claude reads at full detail.


def words(text):
    return {w for w in re.findall(r'[a-z]+', text.lower()) if w not in STOP}


def sheet(r, out):
    from PIL import Image, ImageDraw, ImageFont
    panes = []
    for label, rel, color in (('CHOSEN', r['winner'], (22, 140, 60)), ('REJECTED', r['loser'], (190, 40, 40))):
        im = Image.open(os.path.join(TASTE, rel)).convert('RGB')
        im = im.resize((round(im.width * PANE_H / im.height), PANE_H))
        panes.append((label, im, color))
    gap, bar = 24, 56
    w = sum(p[1].width for p in panes) + gap
    s = Image.new('RGB', (w, PANE_H + bar), 'white')
    d = ImageDraw.Draw(s)
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 34)
    except OSError:
        font = ImageFont.load_default()
    x = 0
    for label, im, color in panes:
        d.rectangle([x, 0, x + im.width, bar - 8], fill=color)
        d.text((x + 16, 8), label, fill='white', font=font)
        s.paste(im, (x, bar))
        x += im.width + gap
    path = os.path.join(out, f"case_{r['id']}.png")
    s.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--context', default='')
    ap.add_argument('--k', type=int, default=8)
    ap.add_argument('--exclude-topic', default='')
    ap.add_argument('--sheet', default='', help='write one chosen|rejected image per case into this folder')
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(os.path.join(TASTE, 'decisions.jsonl')) if l.strip()]
    rows = [r for r in rows if r['topic'] != a.exclude_topic]
    want = words(a.context)
    rows.sort(key=lambda r: r['date'], reverse=True)
    rows.sort(key=lambda r: len(want & words(r['context'])), reverse=True)
    chosen, seen = [], set()
    for r in rows:
        if r['topic'] not in seen:
            chosen.append(r)
            seen.add(r['topic'])
    chosen += [r for r in rows if r not in chosen]
    if a.sheet:
        os.makedirs(a.sheet, exist_ok=True)
    for r in chosen[:a.k]:
        row = {'id': r['id'], 'date': r['date'], 'context': r['context'], 'reason': r['reason'],
               'chosen': os.path.join(TASTE, r['winner']), 'rejected': os.path.join(TASTE, r['loser'])}
        if a.sheet:
            row['sheet'] = sheet(r, a.sheet)
        print(json.dumps(row))


if __name__ == '__main__':
    main()
