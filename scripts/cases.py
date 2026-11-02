#!/usr/bin/env python3
"""Choose which past decisions a review should look at: closest to this screen first, newest first, one per topic
before doubling up. Taste moves, so a newer decision outranks an older one. Prints JSON lines with absolute image paths.

  cases.py --context "the Home tab of a social app" --k 8 [--exclude-topic home]
"""
import argparse, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASTE = os.path.join(ROOT, 'taste')
STOP = set('a an the of to and or in on for with your you it is this that where app iphone screen page what they then'.split())


def words(text):
    return {w for w in re.findall(r'[a-z]+', text.lower()) if w not in STOP}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--context', default='')
    ap.add_argument('--k', type=int, default=8)
    ap.add_argument('--exclude-topic', default='')
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
    for r in chosen[:a.k]:
        print(json.dumps({'id': r['id'], 'date': r['date'], 'context': r['context'], 'reason': r['reason'],
                          'chosen': os.path.join(TASTE, r['winner']), 'rejected': os.path.join(TASTE, r['loser'])}))


if __name__ == '__main__':
    main()
