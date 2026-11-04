"""隧道重开后地址会变：盯 logs/tunnel-public.log，地址变了且能连通，就更新 docs/relay.json 和 public_url.txt 并推到 GitHub，Pages 长期链接因此不用换。由 launchd 托管（com.vicky.realtime.rian-third-sync）。"""
import json, re, subprocess, time
from pathlib import Path
from urllib import request as U
D = Path(__file__).resolve().parent; LOG = D / 'logs/tunnel-public.log'; F = D / 'docs/relay.json'
REPO = 'https://github.com/lyx1265897416-lab/sea-prince-almost-bride-live.git'
op = U.build_opener(U.ProxyHandler({}))
def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)
def git(*a): return subprocess.run(['git', *a], cwd=D, capture_output=True, text=True, timeout=300)
def up(u):
    try:
        with op.open(u + '/api/ping?k=x', timeout=15) as r: return r.status == 200
    except Exception: return False
while True:
    try:
        urls = re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com', LOG.read_text(errors='ignore'))
        u = urls[-1] if urls else None
        if u and u != json.loads(F.read_text()).get('url') and up(u):
            F.write_text(json.dumps({'url': u}) + '\n'); (D / 'public_url.txt').write_text(u + '\n')
            git('add', 'docs/relay.json')
            git('commit', '-m', '更新中转地址\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>', '--', 'docs/relay.json')
            log('relay.json', u)
        if git('rev-list', '--count', '@{u}..HEAD').stdout.strip() not in ('', '0'):  # 没推上去的下一轮再推
            r = git('-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential', 'push', REPO, 'main')
            log('push', r.returncode, r.stderr.strip()[-160:])
            if r.returncode == 0: git('fetch', REPO, 'main:refs/remotes/origin/main')
    except Exception as e: log('fail', repr(e)[:200])
    time.sleep(60)
