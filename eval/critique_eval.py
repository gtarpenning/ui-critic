#!/usr/bin/env python3
"""Does a critique of a design they rejected find what they objected to? Each critique sees only decisions from other
topics; a grader then checks the findings against their stated reason (hit), and whether a critique of the design they
CHOSE tells them to undo their choice (reversal).

  critique_eval.py --prompt eval/prompts/critique_taste.md --k 4
"""
import argparse, base64, glob, concurrent.futures as cf, hashlib, json, mimetypes, os, re, subprocess, sys
from PIL import Image
ap = argparse.ArgumentParser()
ap.add_argument('--prompt', required=True); ap.add_argument('--k', type=int, default=4)
ap.add_argument('--model', default='claude-sonnet-5-5'); ap.add_argument('--workers', type=int, default=4)
ap.add_argument('--rules-dir', default=''); ap.add_argument('--pairs', default='taste/decisions.jsonl'); ap.add_argument('--out', default='eval/runs/critique')
a = ap.parse_args()
base = os.path.dirname(os.path.abspath(a.pairs)); os.makedirs(a.out, exist_ok=True)
pairs = [json.loads(l) for l in open(a.pairs) if l.strip()]
prompt = open(a.prompt).read()
P = lambda p: p if os.path.isabs(p) else os.path.join(base, p)
def img(path): return {"type": "image", "source": {"type": "base64", "media_type": mimetypes.guess_type(P(path))[0], "data": base64.b64encode(open(P(path), 'rb').read()).decode()}}
def claude(content):
    msg = json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + '\n'
    env = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}
    for _ in range(3):
        try:
            r = subprocess.run(['claude', '-p', '--model', a.model, '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose', '--setting-sources', '', '--no-session-persistence', '--tools', ''], input=msg, capture_output=True, text=True, timeout=400, env=env, cwd='/tmp')
            res = [json.loads(l) for l in r.stdout.splitlines() if l.startswith('{') and '"type":"result"' in l.replace(' ', '')]
            if res and res[-1].get('result'): return res[-1]['result'], res[-1].get('total_cost_usd', 0)
        except subprocess.TimeoutExpired: pass
    return '', 0
def rules(p):
    # Rules distilled by loto.py from other topics only, so nothing about this decision leaks in.
    if not a.rules_dir: return []
    found = glob.glob(f"{a.rules_dir}/rules_{p['topic']}_*.md")
    return [{"type": "text", "text": "This product owner's taste, as rules:\n" + open(found[0]).read()}]
def cases(p):
    o = sorted([x for x in pairs if x['topic'] != p['topic']], key=lambda x: x['date'], reverse=True)
    ch, seen = [], set()
    for x in o:
        if x['topic'] not in seen: ch.append(x); seen.add(x['topic'])
    out = []
    for i, c in enumerate(ch[:a.k], 1):
        out += [{"type": "text", "text": f"Past decision {i}. {c['context']}\nChosen:"}, img(c['winner']), {"type": "text", "text": "Rejected:"}, img(c['loser']), {"type": "text", "text": f"His reason: {c['reason']}"}]
    return out
def parse(t):
    m = re.search(r'\{.*\}', t, re.S)
    try: return json.loads(m.group(0))
    except Exception: return {}
GRADE = """A product owner rejected a design and said why:
"{reason}"

A critic reviewing that design wrote:
{findings}

Did any finding identify substantially the problem they named, or propose substantially the change they made? Reply with only JSON: {{"hit": true|false, "rank": <1-based index of the first matching finding, or 0>}}"""
REV = """A product owner chose a design over an alternative, and said why:
"{reason}"

A critic reviewing the design they chose wrote:
{findings}

Does any finding tell them to undo that choice, i.e. bring back what they removed or remove what they asked for? Reply with only JSON: {{"reversal": true|false}}"""
key = hashlib.sha1((prompt + a.model + str(a.k)).encode()).hexdigest()[:10]
name = os.path.splitext(os.path.basename(a.prompt))[0] + ('+rules' if a.rules_dir else '')
cpath = f'{a.out}/{name}__{a.model}__{key}.jsonl'
done = {}
if os.path.exists(cpath):
    for l in open(cpath):
        r = json.loads(l); done[r['id']] = r
def run(p):
    if p['id'] in done: return done[p['id']]
    use = '{w}' in prompt and 'Above are' in prompt
    res = {'id': p['id'], 'cost': 0}
    for side in ('loser', 'winner'):
        w, h = Image.open(P(p[side])).size
        text = prompt.replace('{context}', p['context']).replace('{w}', str(w)).replace('{h}', str(h))
        c = rules(p) + (cases(p) if use else []) + [{"type": "text", "text": "The new screen:"}, img(p[side]), {"type": "text", "text": text}]
        out, cost = claude(c); res['cost'] += cost
        res[side] = parse(out)
        fs = '\n'.join(f"{i}. {f.get('title','')}: {f.get('why','')} Fix: {f.get('fix','')}" for i, f in enumerate(res[side].get('findings', []), 1)) or '(no findings)'
        q = (GRADE if side == 'loser' else REV).format(reason=p['reason'], findings=fs)
        g, cost = claude([{"type": "text", "text": q}]); res['cost'] += cost
        res[side + '_grade'] = parse(g)
    return res
with cf.ThreadPoolExecutor(a.workers) as ex, open(cpath, 'a') as f:
    rs = []
    for r in ex.map(run, pairs):
        rs.append(r)
        if r['id'] not in done: f.write(json.dumps(r) + '\n'); f.flush()
hit = [r for r in rs if r['loser_grade'].get('hit')]
top1 = [r for r in rs if r['loser_grade'].get('rank') == 1]
rev = [r for r in rs if r['winner_grade'].get('reversal')]
n = sum(len(r['loser'].get('findings', [])) for r in rs) / max(1, len(rs))
print(f"{name} {a.model} n={len(rs)} recall@findings={len(hit)/len(rs):.2f} top1={len(top1)/len(rs):.2f} reversal={len(rev)/len(rs):.2f} avg_findings={n:.1f} cost=${sum(r['cost'] for r in rs):.2f}")
print('  missed:', ' '.join(r['id'] for r in rs if r not in hit)[:400]); print('  reversed:', ' '.join(r['id'] for r in rev)[:400])
