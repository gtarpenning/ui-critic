#!/usr/bin/env python3
"""Run a judging prompt over decision pairs with headless Claude, both orders, and score it. Results are cached by
(prompt, model, pair, order, rep) under --out, so changing one prompt never re-pays for the others.

  run.py --prompt eval/prompts/v0.md --pairs taste/decisions.jsonl --split train --model claude-sonnet-5-5
"""
import argparse, base64, concurrent.futures as cf, hashlib, json, mimetypes, os, re, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument('--prompt', required=True); ap.add_argument('--pairs', required=True)
ap.add_argument('--split', default=''); ap.add_argument('--model', default='claude-sonnet-5-5')
ap.add_argument('--reps', type=int, default=1); ap.add_argument('--workers', type=int, default=4)
ap.add_argument('--out', default='eval/runs'); ap.add_argument('--taste', default='')
a = ap.parse_args()
base = os.path.dirname(os.path.abspath(a.pairs))
prompt = open(a.prompt).read()
if '{taste}' in prompt: prompt = prompt.replace('{taste}', open(a.taste).read() if a.taste else '')
pairs = [json.loads(l) for l in open(a.pairs) if l.strip()]
if a.split: pairs = [p for p in pairs if p.get('split') == a.split]
os.makedirs(a.out, exist_ok=True)
key = hashlib.sha1((prompt + a.model).encode()).hexdigest()[:10]
name = os.path.splitext(os.path.basename(a.prompt))[0] + (('+' + os.path.splitext(os.path.basename(a.taste))[0]) if a.taste else '')
cache_path = f'{a.out}/{name}__{a.model}__{key}.jsonl'
done = {}
if os.path.exists(cache_path):
    for l in open(cache_path):
        r = json.loads(l); done[(r['id'], r['order'], r['rep'])] = r

def img(path):
    path = path if os.path.isabs(path) else os.path.join(base, path)
    return {"type": "image", "source": {"type": "base64", "media_type": mimetypes.guess_type(path)[0],
                                        "data": base64.b64encode(open(path, 'rb').read()).decode()}}

def call(p, order, rep):
    k = (p['id'], order, rep)
    if k in done: return done[k]
    first, second = (p['winner'], p['loser']) if order == 'win_first' else (p['loser'], p['winner'])
    text = prompt.replace('{context}', p['context'])
    content = [{"type": "text", "text": "Design A:"}, img(first), {"type": "text", "text": "Design B:"}, img(second),
               {"type": "text", "text": text}]
    msg = json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + '\n'
    env = {k2: v for k2, v in os.environ.items() if k2 != 'ANTHROPIC_API_KEY'}
    for attempt in range(3):
        try:
            r = subprocess.run(['claude', '-p', '--model', a.model, '--input-format', 'stream-json', '--output-format',
                                'stream-json', '--verbose', '--setting-sources', '', '--no-session-persistence', '--tools', ''],
                               input=msg, capture_output=True, text=True, timeout=300, env=env, cwd='/tmp')
            res = [json.loads(l) for l in r.stdout.splitlines() if l.startswith('{') and '"type":"result"' in l.replace(' ', '')]
            if not res: continue
            out = res[-1].get('result') or ''
            m = re.findall(r'"winner"\s*:\s*"(A|B|TIE)"', out)
            if not m: continue
            pick = m[-1]
            correct = None if pick == 'TIE' else ((pick == 'A') == (order == 'win_first'))
            return {'id': p['id'], 'order': order, 'rep': rep, 'pick': pick, 'correct': correct, 'text': out,
                    'cost': res[-1].get('total_cost_usd', 0)}
        except subprocess.TimeoutExpired:
            pass
    return {'id': p['id'], 'order': order, 'rep': rep, 'pick': None, 'correct': None, 'text': 'FAILED', 'cost': 0}

jobs = [(p, o, r) for p in pairs for o in ('win_first', 'lose_first') for r in range(a.reps)]
with cf.ThreadPoolExecutor(a.workers) as ex, open(cache_path, 'a') as f:
    results = []
    for res in ex.map(lambda j: call(*j), jobs):
        results.append(res)
        if (res['id'], res['order'], res['rep']) not in done and res['pick']:
            f.write(json.dumps(res) + '\n'); f.flush()

decided = [r for r in results if r['correct'] is not None]
acc = sum(r['correct'] for r in decided) / max(1, len(decided))
by = {}
for r in results: by.setdefault((r['id'], r['rep']), {})[r['order']] = r
consistent = [v for v in by.values() if len(v) == 2 and None not in (v['win_first']['correct'], v['lose_first']['correct'])
              and v['win_first']['correct'] == v['lose_first']['correct']]
right = sum(v['win_first']['correct'] for v in consistent)
pos_a = sum(r['pick'] == 'A' for r in results) / max(1, len(results))
print(f"{name} {a.model} split={a.split or 'all'} n={len(results)} acc={acc:.3f} ties={sum(r['pick']=='TIE' for r in results)} "
      f"fail={sum(r['pick'] is None for r in results)} order_consistent={len(consistent)}/{len(by)} "
      f"acc_when_consistent={right/max(1,len(consistent)):.3f} picks_A={pos_a:.2f} cost=${sum(r['cost'] for r in results):.2f}")
wrong = sorted({r['id'] for r in results if r['correct'] is False})
print('  wrong at least once:', ' '.join(wrong)[:600])
