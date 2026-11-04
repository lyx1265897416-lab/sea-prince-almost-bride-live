"""11-04 复盘后干跑：用 Vicky 测的 S0412033e8 三轮的输入和当时的状态，只跑导演层，看 seg1 有没有配角正面出镜、换岸装有没有取衣过程。"""
import json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
D = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D))
import director
src = (D / 'rian_third_relay.py').read_text(encoding='utf-8'); OPEN_STATE = None
exec(src[src.index('OPEN_STATE ='):src.index('OPEN_NEXT =')])
R = {k: json.load(open(D / 'rounds' / f'{k}.json')) for k in ('L041320ed7', 'L041528f92', 'L041903b50')}
import importlib.util
_s = importlib.util.spec_from_file_location('relay_src', D / 'rian_third_relay.py')
exec(src[src.index('def hist_entry'):src.index('def new_session')])
def hist(*ks): return [hist_entry(R[k], R[k]['spec']) for k in ks]
cases = [
         ('R3', hist('L041320ed7', 'L041528f92'), R['L041528f92']['spec'].get('state_end') or OPEN_STATE, '我答应让他跟上岸，带他去盐点港，看看我的世界', 'option', '潮门', R['L041528f92']['spec'].get('set'))]
def one(c):
    tag, h, st, text, kind, place, setn = c
    try: sp, sec = director.direct(h, st, text, kind, 'auto', place=place, place_rounds=0, set_now=setn)
    except TypeError: sp, sec = director.direct([], st, text, kind, 'auto', place=place, place_rounds=0, set_now=setn)
    return tag, text, sec, sp
with ThreadPoolExecutor(2) as ex:
    for tag, t, sec, sp in ex.map(one, cases):
        print(f'\n=== {tag} {t} | {sec}s cast={sp.get("cast")} loc={sp.get("location")} wardrobe={sp.get("wardrobe")}')
        for k in ('seg1', 'seg2'):
            for b in sp.get(k) or []: print('    ', k[-1], '|', str(b[0])[:80], '|', str(b[1])[:40], '|', (b[3] if len(b) > 3 else ''))
        print('  lint_left', [x[:70] for x in sp.get('lint_left') or []][:3], flush=True)
