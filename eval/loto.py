#!/usr/bin/env python3
"""Leave-one-topic-out: each decision is judged using only decisions from OTHER topics, so nothing about the held-out
question leaks in. Modes: rules (distill rules from the other decisions, then judge), cases (show past decisions as
images with reasons), log (reasons as text only), rules+cases.

  loto.py --mode cases --k 4 --model claude-sonnet-5-5
"""
import argparse, base64, concurrent.futures as cf, hashlib, json, mimetypes, os, re, subprocess, sys
ap = argparse.ArgumentParser()
ap.add_argument('--mode', required=True); ap.add_argument('--k', type=int, default=4)
ap.add_argument('--model', default='claude-sonnet-5-5'); ap.add_argument('--workers', type=int, default=4)
ap.add_argument('--pairs', default='taste/decisions.jsonl'); ap.add_argument('--out', default='eval/runs/loto')
ap.add_argument('--select', default='overlap'); ap.add_argument('--json', default=''); ap.add_argument('--rep', type=int, default=0); ap.add_argument('--judge', default='eval/prompts/judge.md'); ap.add_argument('--distill', default='eval/prompts/distill.md')
a = ap.parse_args()
base = os.path.dirname(os.path.abspath(a.pairs)); os.makedirs(a.out, exist_ok=True)
pairs = [json.loads(l) for l in open(a.pairs) if l.strip()]
judge, distill = open(a.judge).read(), open(a.distill).read()

def img(path):
    path = path if os.path.isabs(path) else os.path.join(base, path)
    return {"type": "image", "source": {"type": "base64", "media_type": mimetypes.guess_type(path)[0],
                                        "data": base64.b64encode(open(path, 'rb').read()).decode()}}

def claude(content, model=None):
    msg = json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + '\n'
    env = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}
    for _ in range(3):
        try:
            r = subprocess.run(['claude', '-p', '--model', model or a.model, '--input-format', 'stream-json', '--output-format',
                                'stream-json', '--verbose', '--setting-sources', '', '--no-session-persistence', '--tools', ''],
                               input=msg, capture_output=True, text=True, timeout=400, env=env, cwd='/tmp')
            res = [json.loads(l) for l in r.stdout.splitlines() if l.startswith('{') and '"type":"result"' in l.replace(' ', '')]
            if res and res[-1].get('result'): return res[-1]['result'], res[-1].get('total_cost_usd', 0)
        except subprocess.TimeoutExpired: pass
    return '', 0

def case_blocks(cases):
    out = []
    for i, c in enumerate(cases, 1):
        out += [{"type": "text", "text": f"Past decision {i} ({c['date']}). {c['context']}\nChosen:"}, img(c['winner']),
                {"type": "text", "text": "Rejected:"}, img(c['loser']), {"type": "text", "text": f"Their reason: {c['reason']}"}]
    return out

rule_cache = {}
def rules_for(topic):
    others = [p for p in pairs if p['topic'] != topic]
    key = hashlib.sha1((distill + a.model + json.dumps([o['id'] for o in others])).encode()).hexdigest()[:10]
    path = f'{a.out}/rules_{topic}_{key}.md'
    if os.path.exists(path): return open(path).read(), 0
    text, cost = claude(case_blocks(others) + [{"type": "text", "text": distill}])
    open(path, 'w').write(text); return text, cost

STOP = set('a an the of to and or in on for with your you it is this that where app iphone screen page what they then'.split())
def words(t): return {w for w in re.findall(r'[a-z]+', t.lower()) if w not in STOP}

def pick_cases(p):
    # Same selection as scripts/cases.py: closest context, then newest, one per topic before doubling up.
    rows = sorted((o for o in pairs if o['topic'] != p['topic']), key=lambda o: o['date'], reverse=True)
    want = words(p['context'])
    # 'exact' was the first version: identical context first, then newest.
    rows.sort(key=(lambda o: o['context'] == p['context']) if a.select == 'exact' else (lambda o: len(want & words(o['context']))), reverse=True)
    chosen, seen = [], set()
    for o in rows:
        if o['topic'] not in seen: chosen.append(o); seen.add(o['topic'])
    chosen += [o for o in rows if o not in chosen]
    return chosen[:a.k]

jkey = hashlib.sha1((judge + distill + a.model + a.mode + str(a.k) + (str(a.rep) if a.rep else '') + ('' if a.select == 'overlap' else a.select)).encode()).hexdigest()[:10]
cache = f'{a.out}/{a.mode}{a.k}__{a.model}__{jkey}.jsonl'
done = {}
if os.path.exists(cache):
    for l in open(cache):
        r = json.loads(l); done[(r['id'], r['order'])] = r

def run(job):
    p, order = job
    if (p['id'], order) in done: return done[(p['id'], order)]
    content, cost = [], 0; taste = ''
    if 'rules' in a.mode:
        taste, cost = rules_for(p['topic'])
    if a.mode == 'log':
        taste = '\n'.join(f"- {o['date']}: {o['reason']}" for o in sorted(pairs, key=lambda o: o['date']) if o['topic'] != p['topic'])
    if 'cases' in a.mode:
        content += case_blocks(pick_cases(p))
    first, second = (p['winner'], p['loser']) if order == 'win_first' else (p['loser'], p['winner'])
    text = judge.replace('{context}', p['context']).replace('{taste}', taste or '(see the past decisions above)')
    content += [{"type": "text", "text": "Now the new choice. Design A:"}, img(first), {"type": "text", "text": "Design B:"}, img(second), {"type": "text", "text": text}]
    out, c2 = claude(content)
    m = re.findall(r'"winner"\s*:\s*"(A|B|TIE)"', out); pick = m[-1] if m else None
    correct = None if pick in (None, 'TIE') else ((pick == 'A') == (order == 'win_first'))
    return {'id': p['id'], 'topic': p['topic'], 'order': order, 'pick': pick, 'correct': correct, 'text': out, 'cost': cost + c2}

# Rules first, serially per topic, so parallel judges share them.
if 'rules' in a.mode:
    with cf.ThreadPoolExecutor(a.workers) as ex: list(ex.map(rules_for, sorted({p['topic'] for p in pairs})))
jobs = [(p, o) for p in pairs for o in ('win_first', 'lose_first')]
with cf.ThreadPoolExecutor(a.workers) as ex, open(cache, 'a') as f:
    res = []
    for r in ex.map(run, jobs):
        res.append(r)
        if (r['id'], r['order']) not in done and r['pick']: f.write(json.dumps(r) + '\n'); f.flush()
dec = [r for r in res if r['correct'] is not None]
by = {}
for r in res: by.setdefault(r['id'], {})[r['order']] = r['correct']
cons = [v for v in by.values() if None not in v.values() and len(set(v.values())) == 1]
print(f"{a.mode}{a.k} {a.model} n={len(res)} acc={sum(r['correct'] for r in dec)/max(1,len(dec)):.3f} fail={sum(r['pick'] is None for r in res)} ties={sum(r['pick']=='TIE' for r in res)} consistent={len(cons)}/{len(by)} acc_consistent={sum(list(v.values())[0] for v in cons)/max(1,len(cons)):.3f} cost=${sum(r['cost'] for r in res):.2f}")
print('  ' + ' '.join(i[:14] + ':' + ''.join('Y' if v.get(o) else 'n' for o in ('win_first', 'lose_first')) for i, v in by.items()))
if a.json:
    by_id = {}
    for r in res: by_id.setdefault(r['id'], {})[r['order']] = {'correct': r['correct'], 'text': r['text']}
    json.dump({'pairs': len(by), 'acc': sum(r['correct'] for r in dec) / max(1, len(dec)), 'consistent': len(cons),
               'cost': sum(r['cost'] for r in res), 'by_id': by_id}, open(a.json, 'w'))
