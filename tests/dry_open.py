"""开场之后第 1 轮干跑：只跑导演层，不花视频钱。用法：python3 tests/dry_open.py"""
import json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
D = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D))
import director, importlib.util
spec = importlib.util.spec_from_file_location('relay', D / 'rian_third_relay.py')
src = (D / 'rian_third_relay.py').read_text(encoding='utf-8'); OPEN_STATE = OPEN_NEXT = None
exec(src[src.index('OPEN_STATE ='):src.index('OPEN_NEXT =')]); exec('OPEN_NEXT =' + src.split('OPEN_NEXT =', 1)[1].split('\n\n', 1)[0])
cases = [('A', OPEN_NEXT['A']['zh'], 'option'), ('B', OPEN_NEXT['B']['zh'], 'option'), ('free', '你为什么要说我是你的新娘？我只是来找我朋友的。', 'free')]
def one(c):
    tag, text, kind = c
    sp, sec = director.direct([], OPEN_STATE, text, kind, 'auto', place='东廊', place_rounds=0, set_now=director.OPEN_SET)
    return tag, text, sec, sp
with ThreadPoolExecutor(3) as ex:
    for tag, t, sec, sp in ex.map(one, cases):
        print(f'\n=== {tag} {t} | {sec}s try={sp.get("director_attempts")} {sp.get("dur_mode")} staging={sp.get("staging")} cast={sp.get("cast")} loc={sp.get("location")} target={sp.get("target")}')
        print('  intent', str(sp.get('intent'))[:120])
        for k in ('seg1', 'seg2'):
            for b in sp.get(k) or []: print('    ', k[-1], str(b[2])[:10], '|', str(b[0])[:70], '|', str(b[1])[:40], '|', (b[3] if len(b) > 3 else ''))
        nx = sp.get('next') or {}
        print('  next', (nx.get('cue') or {}).get('zh'), '| A', (nx.get('A') or {}).get('zh'), '| B', (nx.get('B') or {}).get('zh'))
        print('  lint_left', [x[:80] for x in sp.get('lint_left') or []][:3], flush=True)
