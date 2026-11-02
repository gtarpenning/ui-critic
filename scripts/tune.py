#!/usr/bin/env python3
"""The tuning desk: a small local page for teaching ui-critic your taste.

  Pick    choose between two designs, with the keyboard. Each pick becomes a decision the skill learns from.
  Misses  see where the judge disagrees with you and why: keep your call, or say you changed your mind.
  Rules   read and edit taste/taste.md, the short notes every review loads.
  Score   accuracy per run, how consistent your own picks are, and a button to re-score.

  tune.py [--port 8765]    (binds to 127.0.0.1 only, standard library only)
"""
import argparse, base64, datetime, http.server, json, mimetypes, os, shutil, socketserver, subprocess, sys, threading, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASTE = os.path.join(ROOT, 'taste')
DECISIONS = os.path.join(TASTE, 'decisions.jsonl')
QUEUE = os.path.join(TASTE, 'queue.jsonl')
ANSWERS = os.path.join(TASTE, 'answers.jsonl')
RULES = os.path.join(TASTE, 'taste.md')
SCORES = os.path.join(ROOT, 'eval', 'scores.jsonl')
MISSES = os.path.join(ROOT, 'eval', 'misses.jsonl')
lock = threading.Lock()
rescoring = {'running': False, 'log': ''}


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def append_jsonl(path, row):
    with open(path, 'a') as f:
        f.write(json.dumps(row) + '\n')


def next_pair():
    seen = {r['id'] for r in read_jsonl(ANSWERS)}
    queue = read_jsonl(QUEUE)
    left = [q for q in queue if q['id'] not in seen]
    return {'pair': left[0] if left else None, 'done': len(queue) - len(left), 'total': len(queue)}


def consistency():
    ans = {r['id']: r for r in read_jsonl(ANSWERS)}
    same = total = 0
    for i, r in ans.items():
        base = ans.get(r.get('repeat_of') or '')
        if base and r['pick'] != 'tie' and base['pick'] != 'tie':
            total += 1
            # Repeats show the same two images with the sides swapped, so the same image means the opposite letter.
            same += r['pick'] != base['pick']
    return {'same': same, 'total': total}


def answer(body):
    q = next((x for x in read_jsonl(QUEUE) if x['id'] == body['id']), None)
    if not q:
        return {'error': 'unknown pair'}
    with lock:
        pick = body['pick']
        append_jsonl(ANSWERS, {'id': q['id'], 'pick': pick, 'repeat_of': q.get('repeat_of'), 'reason': body.get('reason', ''),
                               'at': datetime.datetime.now().isoformat(timespec='seconds')})
        if pick in ('a', 'b') and not q.get('repeat_of'):
            win, lose = (q['a'], q['b']) if pick == 'a' else (q['b'], q['a'])
            append_jsonl(DECISIONS, {'id': q['id'], 'date': datetime.date.today().isoformat(), 'split': 'tuned', 'topic': q['id'],
                                     'context': q['context'], 'winner': win, 'loser': lose,
                                     'reason': body.get('reason') or '(no reason given)', 'source': 'tune: ' + q.get('source', '')})
    return next_pair()


def undo():
    with lock:
        rows = read_jsonl(ANSWERS)
        if not rows:
            return next_pair()
        last = rows.pop()
        with open(ANSWERS, 'w') as f:
            f.writelines(json.dumps(r) + '\n' for r in rows)
        keep = [d for d in read_jsonl(DECISIONS) if d['id'] != last['id']]
        with open(DECISIONS, 'w') as f:
            f.writelines(json.dumps(d) + '\n' for d in keep)
    return next_pair()


def resolve_miss(body):
    with lock:
        rows = read_jsonl(MISSES)
        for m in rows:
            if m['id'] == body['id']:
                m['resolved'] = body['action']
                if body['action'] == 'changed-my-mind':
                    # Taste moved: flip the decision, dated today, so the newer call wins.
                    ds = read_jsonl(DECISIONS)
                    for d in ds:
                        if d['id'] == m['id']:
                            d['winner'], d['loser'] = d['loser'], d['winner']
                            d['date'] = datetime.date.today().isoformat()
                            d['reason'] = body.get('reason') or ('Changed my mind. Was: ' + d['reason'])
                    with open(DECISIONS, 'w') as f:
                        f.writelines(json.dumps(d) + '\n' for d in ds)
                elif body.get('reason'):
                    ds = read_jsonl(DECISIONS)
                    for d in ds:
                        if d['id'] == m['id']:
                            d['reason'] = body['reason']
                    with open(DECISIONS, 'w') as f:
                        f.writelines(json.dumps(d) + '\n' for d in ds)
        with open(MISSES, 'w') as f:
            f.writelines(json.dumps(m) + '\n' for m in rows)
    return {'misses': [m for m in rows if not m.get('resolved')]}


def rescore():
    if rescoring['running']:
        return {'running': True}

    def work():
        rescoring.update(running=True, log='')
        p = subprocess.run([sys.executable, 'eval/score.py'], cwd=ROOT, capture_output=True, text=True)
        rescoring.update(running=False, log=(p.stdout + p.stderr)[-2000:])
    threading.Thread(target=work, daemon=True).start()
    return {'running': True}


def state():
    d = read_jsonl(DECISIONS)
    return {'decisions': len(d), 'consistency': consistency(), 'scores': read_jsonl(SCORES),
            'misses': [m for m in read_jsonl(MISSES) if not m.get('resolved')], 'rescoring': rescoring,
            'rules': open(RULES).read() if os.path.exists(RULES) else ''}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype='application/json'):
        data = body if isinstance(body, bytes) else (body.encode() if isinstance(body, str) else json.dumps(body).encode())
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/':
            return self.send(200, PAGE, 'text/html; charset=utf-8')
        if u.path == '/next':
            return self.send(200, next_pair())
        if u.path == '/state':
            return self.send(200, state())
        if u.path.startswith('/img/'):
            rel = os.path.normpath(urllib.parse.unquote(u.path[5:]))
            full = os.path.join(TASTE, rel)
            if rel.startswith('..') or not os.path.isfile(full):
                return self.send(404, {'error': 'not found'})
            with open(full, 'rb') as f:
                return self.send(200, f.read(), mimetypes.guess_type(full)[0] or 'application/octet-stream')
        self.send(404, {'error': 'not found'})

    def do_POST(self):
        # Only this page may write: a page on any other site could otherwise post here.
        if self.headers.get('Origin') not in (None, f'http://127.0.0.1:{self.server.server_address[1]}'):
            return self.send(403, {'error': 'wrong origin'})
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n) or b'{}')
        p = self.path
        if p == '/answer':
            return self.send(200, answer(body))
        if p == '/undo':
            return self.send(200, undo())
        if p == '/miss':
            return self.send(200, resolve_miss(body))
        if p == '/rescore':
            return self.send(200, rescore())
        if p == '/rules':
            with open(RULES, 'w') as f:
                f.write(body.get('text', ''))
            return self.send(200, {'ok': True})
        self.send(404, {'error': 'not found'})


PAGE = r"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>ui-critic tuning</title><style>
:root{--bg:#f5f5f6;--fg:#18181b;--muted:#6b6b73;--card:#fff;--line:#e2e2e6;--accent:#b4690e}
@media(prefers-color-scheme:dark){:root{--bg:#131315;--fg:#f3f3f5;--muted:#a2a2aa;--card:#1e1e22;--line:#333338;--accent:#e6a24a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,system-ui,sans-serif}
nav{display:flex;gap:4px;padding:10px 16px;border-bottom:1px solid var(--line);align-items:center;position:sticky;top:0;background:var(--bg);z-index:2}
nav button{background:none;border:0;color:var(--muted);font:inherit;padding:6px 10px;border-radius:8px;cursor:pointer}nav button.on{background:var(--card);color:var(--fg);font-weight:600}
nav .sp{flex:1}main{max-width:1100px;margin:auto;padding:16px}.ctx{color:var(--muted);text-align:center;margin:0 0 12px}
.pair{display:flex;gap:16px;justify-content:center}.opt{flex:0 1 340px;background:var(--card);border:2px solid var(--line);border-radius:14px;padding:8px;cursor:pointer;min-width:0}.opt:hover,.opt:focus-visible{border-color:var(--accent);outline:0}
.opt img{width:100%;max-height:68vh;object-fit:contain;display:block;border-radius:8px}.opt small{display:block;text-align:center;color:var(--muted);padding:6px 0 0}
.bar{display:flex;gap:8px;justify-content:center;align-items:center;margin-top:12px;flex-wrap:wrap}input[type=text],textarea{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px}input[type=text]{flex:1 1 280px;max-width:520px}
button.b{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;cursor:pointer}button.p{background:var(--accent);border-color:var(--accent);color:#fff}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:12px}.m{color:var(--muted)}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
.thumbs{display:flex;gap:10px}.thumbs figure{margin:0;flex:1;min-width:0}.thumbs img{width:100%;border-radius:8px;max-height:420px;object-fit:contain}.thumbs figcaption{font-size:13px;color:var(--muted);margin-bottom:4px}textarea{width:100%;height:50vh}kbd{border:1px solid var(--line);border-radius:4px;padding:0 4px;font-size:12px}
@media(max-width:560px){.pair{gap:8px}.opt{padding:4px}}</style>
<nav><button data-t=pick>Pick</button><button data-t=misses>Misses</button><button data-t=rules>Rules</button><button data-t=score>Score</button><span class=sp></span><span class=m id=count></span></nav><main id=m></main><script>
const $=s=>document.querySelector(s),m=$('#m');let tab='pick',cur=null;const J=(u,b)=>fetch(u,b===undefined?{}:{method:'POST',body:JSON.stringify(b)}).then(r=>r.json());
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function go(t){tab=t;document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('on',b.dataset.t==t));({pick:pick,misses:misses,rules:rules,score:score})[t]()}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>go(b.dataset.t));
function drawPick(n){$('#count').textContent=n.done+' of '+n.total+' picked';cur=n.pair;if(!cur){m.innerHTML='<div class=card><b>All picked.</b><p class=m>Open Score and re-score to see how close the judge is now.</p><button class=b onclick="J(\'/undo\',{}).then(drawPick)">Undo last</button></div>';return}
m.innerHTML=`<p class=ctx>${esc(cur.context)}</p><div class=pair><div class=opt tabindex=0 onclick="pickIt('a')"><img alt="Design A" src="/img/${esc(cur.a)}"><small>A <kbd>←</kbd></small></div><div class=opt tabindex=0 onclick="pickIt('b')"><img alt="Design B" src="/img/${esc(cur.b)}"><small>B <kbd>→</kbd></small></div></div>
<div class=bar><input id=why type=text placeholder="Why? Optional, but it teaches the most"><button class=b onclick="pickIt('tie')">Too close <kbd>↓</kbd></button><button class=b onclick="J('/undo',{}).then(drawPick)">Undo <kbd>U</kbd></button></div>`}
function pickIt(p){if(!cur)return;J('/answer',{id:cur.id,pick:p,reason:($('#why')||{}).value||''}).then(drawPick)}
function pick(){J('/next').then(drawPick)}
addEventListener('keydown',e=>{if(tab!='pick'||e.target.tagName=='INPUT'&&!['ArrowLeft','ArrowRight','ArrowDown'].includes(e.key)||e.target.tagName=='TEXTAREA')return;({ArrowLeft:()=>pickIt('a'),ArrowRight:()=>pickIt('b'),ArrowDown:()=>pickIt('tie'),u:()=>J('/undo',{}).then(drawPick)}[e.key]||(()=>{}))()});
function misses(){J('/state').then(s=>{$('#count').textContent=s.misses.length+' open';if(!s.misses.length){m.innerHTML='<div class=card>No open misses. Re-score from Score to look for new ones.</div>';return}
m.innerHTML=s.misses.map(x=>`<div class=card><p class=m>${esc(x.context)}</p><div class=thumbs><figure><figcaption>You chose</figcaption><img alt="" src="/img/${esc(x.winner)}"></figure><figure><figcaption>The judge chose</figcaption><img alt="" src="/img/${esc(x.loser)}"></figure></div><p><b>Your reason:</b> ${esc(x.reason)}</p><p><b>The judge argued:</b> ${esc(x.argument)}</p><div class=bar><input type=text id="r-${esc(x.id)}" placeholder="Say more about why (optional)"><button class="b p" onclick="res('${esc(x.id)}','keep')">I still choose mine</button><button class=b onclick="res('${esc(x.id)}','changed-my-mind')">The judge is right</button></div></div>`).join('')})}
function res(id,a){J('/miss',{id,action:a,reason:(document.getElementById('r-'+id)||{}).value||''}).then(misses)}
function rules(){J('/state').then(s=>{$('#count').textContent='';m.innerHTML=`<div class=card><p class=m>Short notes every review reads. Past choices still outrank these, so keep only what you'd say out loud.</p><textarea id=rt>${esc(s.rules)}</textarea><div class=bar><button class="b p" onclick="J('/rules',{text:$('#rt').value}).then(()=>this.textContent='Saved')">Save</button></div></div>`})}
function score(){J('/state').then(s=>{const c=s.consistency;$('#count').textContent=s.decisions+' decisions';const rows=s.scores.slice().reverse().map(r=>`<tr><td>${esc(r.date)}</td><td>${esc(r.decisions)}</td><td>${Math.round(r.judge*100)}%</td><td>${Math.round(r.baseline*100)}%</td><td>${Math.round(r.consistent*100)}%</td><td>$${(+r.cost).toFixed(2)}</td></tr>`).join('');
m.innerHTML=`<div class=card><b>Your own consistency:</b> ${c.total?Math.round(c.same/c.total*100)+'% ('+c.same+' of '+c.total+' repeats)':'not measured yet: some Pick pairs are hidden repeats'}<p class=m>The judge can't reliably beat this number.</p></div><div class=card><table><tr><th>When</th><th>Decisions</th><th>Judge</th><th>Plain Claude</th><th>Both orders agree</th><th>Cost</th></tr>${rows||'<tr><td colspan=6 class=m>No scores yet</td></tr>'}</table><div class=bar><button class="b p" ${s.rescoring.running?'disabled':''} onclick="J('/rescore',{}).then(()=>setTimeout(score,800))">${s.rescoring.running?'Scoring…':'Re-score'}</button></div><p class=m>Each decision is judged using only your other topics. Costs real tokens (about $0.25 per new decision).</p>${s.rescoring.log?`<pre style="white-space:pre-wrap">${esc(s.rescoring.log)}</pre>`:''}</div>`;if(s.rescoring.running)setTimeout(score,4000)})}
go('pick');</script>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(('127.0.0.1', a.port), Handler) as s:
        print(f'ui-critic tuning desk: http://127.0.0.1:{a.port}/', flush=True)
        s.serve_forever()


if __name__ == '__main__':
    main()
