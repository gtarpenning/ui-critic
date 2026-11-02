#!/usr/bin/env python3
"""Score the production judge against plain Claude on every recorded decision. Each decision is judged using only other
topics. Appends a row to eval/scores.jsonl and rewrites the open items in eval/misses.jsonl. Results are cached against
the exact set of decisions, so a re-score with nothing new costs nothing.

  score.py [--mode rules+cases] [--k 4] [--model claude-sonnet-5-5] [--baseline-model claude-sonnet-5-5]
"""
import argparse, datetime, hashlib, json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORES = os.path.join(ROOT, 'eval', 'scores.jsonl')
MISSES = os.path.join(ROOT, 'eval', 'misses.jsonl')
DECISIONS = os.path.join(ROOT, 'taste', 'decisions.jsonl')


def read_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []


def loto(out, **kw):
    fd, tmp = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    cmd = [sys.executable, 'eval/loto.py', '--out', out, '--json', tmp] + [x for k, v in kw.items() for x in (f'--{k}', str(v))]
    print('+', ' '.join(cmd[1:]), flush=True)
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    print(p.stdout[-1500:], end='', flush=True)
    if p.returncode:
        sys.exit(p.stderr[-1500:])
    res = json.load(open(tmp))
    os.unlink(tmp)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default='rules+cases')
    ap.add_argument('--k', type=int, default=4)
    ap.add_argument('--model', default='claude-sonnet-5-5')
    ap.add_argument('--baseline-model', default='claude-sonnet-5-5')
    a = ap.parse_args()
    data = open(DECISIONS, 'rb').read()
    out = os.path.join('eval', 'runs', 'score', hashlib.sha1(data).hexdigest()[:10])
    judge = loto(out, mode=a.mode, k=a.k, model=a.model)
    base = loto(out, mode='plain', k=0, model=a.baseline_model, judge='eval/prompts/v0_vanilla.md')
    row = {'date': datetime.date.today().isoformat(), 'decisions': judge['pairs'], 'config': f'{a.mode}{a.k} {a.model}',
           'judge': judge['acc'], 'baseline': base['acc'], 'consistent': judge['consistent'] / max(1, judge['pairs']),
           'cost': judge['cost'] + base['cost']}
    with open(SCORES, 'a') as f:
        f.write(json.dumps(row) + '\n')

    # A miss is a decision the judge got wrong in both orders. Anything already answered on the desk stays answered,
    # unless that decision has since changed.
    decisions = {d['id']: d for d in read_jsonl(DECISIONS)}
    old = {m['id']: m for m in read_jsonl(MISSES)}
    rows = []
    for i, r in judge['by_id'].items():
        if r['win_first']['correct'] is False and r['lose_first']['correct'] is False:
            d = decisions[i]
            prev = old.get(i)
            if prev and prev.get('resolved') and prev.get('winner') == d['winner']:
                rows.append(prev)
                continue
            rows.append({'id': i, 'context': d['context'], 'winner': d['winner'], 'loser': d['loser'], 'reason': d['reason'],
                         'argument': r['win_first']['text']})
    rows += [m for i, m in old.items() if m.get('resolved') and i not in {r['id'] for r in rows}]
    with open(MISSES, 'w') as f:
        f.writelines(json.dumps(m) + '\n' for m in rows)
    print(f"judge {row['judge']:.0%} plain {row['baseline']:.0%} agree {row['consistent']:.0%} "
          f"open misses {sum(not m.get('resolved') for m in rows)} ${row['cost']:.2f}")


if __name__ == '__main__':
    main()
