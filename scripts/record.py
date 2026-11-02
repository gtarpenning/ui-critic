#!/usr/bin/env python3
"""Add one decision to taste/decisions.jsonl, copying the two images in at a size the skill can use.

  record.py --context "the Home tab of ..." --winner chosen.png --loser rejected.png --reason "their words" --topic home
"""
import argparse, datetime, json, os, re
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASTE = os.path.join(ROOT, 'taste')


def put(src, name):
    im = Image.open(src).convert('RGB')
    if im.width > 780:
        im = im.resize((780, round(im.height * 780 / im.width)), Image.LANCZOS)
    im.save(os.path.join(TASTE, 'img', name), optimize=True)
    return f'img/{name}'


def main():
    ap = argparse.ArgumentParser()
    for f in ('context', 'winner', 'loser', 'reason', 'topic'):
        ap.add_argument('--' + f, required=True)
    ap.add_argument('--date', default=datetime.date.today().isoformat())
    a = ap.parse_args()
    os.makedirs(os.path.join(TASTE, 'img'), exist_ok=True)
    path = os.path.join(TASTE, 'decisions.jsonl')
    n = sum(1 for _ in open(path)) if os.path.exists(path) else 0
    rid = f"{re.sub(r'[^a-z0-9]+', '-', a.topic.lower()).strip('-')}-{n}"
    row = {'id': rid, 'date': a.date, 'split': 'recorded', 'topic': a.topic, 'context': a.context,
           'winner': put(a.winner, rid + '__win.png'), 'loser': put(a.loser, rid + '__lose.png'), 'reason': a.reason, 'source': 'recorded'}
    with open(path, 'a') as f:
        f.write(json.dumps(row) + '\n')
    print(rid)


if __name__ == '__main__':
    main()
