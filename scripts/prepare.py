#!/usr/bin/env python3
"""Copy screenshots to a size Claude reads 1:1, so the pixel coordinates it reports land on the image we draw on.
Prints one JSON object per image: {"src", "path", "width", "height"}.

  prepare.py --out /tmp/review shot1.png shot2.png
"""
import argparse, json, math, os, sys
from PIL import Image

MAX_EDGE, MAX_TOKENS = 1568, 1568  # standard-tier limits; they also fit every higher tier


def fits(w, h):
    return math.ceil(w / 28) * 28 <= MAX_EDGE and math.ceil(h / 28) * 28 <= MAX_EDGE and \
        math.ceil(w / 28) * math.ceil(h / 28) <= MAX_TOKENS


def target(w, h):
    scale = 1.0
    while not fits(max(1, round(w * scale)), max(1, round(h * scale))):
        scale *= 0.98
    return max(1, round(w * scale)), max(1, round(h * scale))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('images', nargs='+')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for i, src in enumerate(a.images):
        im = Image.open(src).convert('RGB')
        w, h = target(*im.size)
        if (w, h) != im.size:
            im = im.resize((w, h), Image.LANCZOS)
        path = os.path.join(a.out, f'{i:02d}_{os.path.splitext(os.path.basename(src))[0]}.png')
        im.save(path, optimize=True)
        print(json.dumps({'src': src, 'path': os.path.abspath(path), 'width': w, 'height': h}))


if __name__ == '__main__':
    main()
