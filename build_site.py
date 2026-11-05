"""播放页素材：开场确认版（v11：人鱼传说序幕 + 外国人版开场 + 维萨问“Is that true?”，11-04 Vicky 确认）、待机循环、封面、等待配乐传 GCS，写 cdn.json，并把 CDN 地址和开场字幕（含地点字卡）写进 docs/index.html。换开场后重跑。"""
import json, re, subprocess, time
from pathlib import Path
D = Path(__file__).resolve().parent; S = D / 'docs'; C = D / 'cdn.json'
CUES = Path('/Users/vicky/Interactive storyline/projects/the-sea-princes-almost-bride/制作/新版互动剧集-v32/rto_openw11/cues.json')
cdn = json.loads(C.read_text()) if C.exists() else {}
sig = {}
for rel in ('media/OPEN.mp4', 'media/IDLE0.mp4', 'media/poster.jpg', 'audio/WAIT.mp3'):
    f = S / rel; key = f'{f.stat().st_size}-{int(f.stat().st_mtime)}'
    if cdn.get(rel) and cdn.get('_sig', {}).get(rel) == key: sig[rel] = key; continue
    for _ in range(4):
        r = subprocess.run(['waku', 'persist', str(f)], capture_output=True, text=True, timeout=600)
        m = re.search(r'"url":\s*"([^"]+)"', r.stdout)
        if m: cdn[rel] = m.group(1); sig[rel] = key; break
        time.sleep(5)
    else: raise SystemExit('persist failed ' + rel + r.stdout[-200:] + r.stderr[-200:])
    print(rel, cdn[rel], flush=True)
cdn['_sig'] = {**cdn.get('_sig', {}), **sig}; C.write_text(json.dumps(cdn, indent=1))
src = json.loads(CUES.read_text(encoding='utf-8'))
WHO = {'SKY': 'Her', 'MIL': 'Mila', 'VES': 'Vessa', 'RIA': 'Rian', 'NAR': ''}
cues = [dict(s=c['s'], e=c['e'], zh=c['zh'], en=c['en'], who=WHO.get(c['sp'], c['sp'])) for c in src['cues']]
cues += [dict(s=k['t'], e=round(k['t'] + k['d'], 2), zh=k['zh'], en=k['en'], who='') for k in src['cards']]
cues.sort(key=lambda c: c['s'])
h = (S / 'index.html').read_text(encoding='utf-8')
h = re.sub(r'const CDN = \{.*?\};', 'const CDN = ' + json.dumps({k: v for k, v in cdn.items() if not k.startswith('_')}) + ';', h, count=1, flags=re.S)
h = re.sub(r'const OPEN_CUES = \[.*?\];', 'const OPEN_CUES = ' + json.dumps(cues, ensure_ascii=False) + ';', h, count=1, flags=re.S)
(S / 'index.html').write_text(h, encoding='utf-8'); (S / 'open_cues.json').write_text(json.dumps(cues, ensure_ascii=False)); print('index ok', len(cues), 'cues')
