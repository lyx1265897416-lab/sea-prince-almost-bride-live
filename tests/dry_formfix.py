"""V3.12 干跑：用 Vicky S024754f68 第 8、9、12 轮的真实输入和之前的剧情记录，只跑导演层，看水里他是不是人鱼形态（没有披袍和腿）、上岸写回定装。"""
import json, sys, glob
from pathlib import Path
D = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D))
import director, live_common as L
src = (D / 'rian_third_relay.py').read_text(encoding='utf-8')
exec(src[src.index('def hist_entry'):src.index('def new_session')])
R = sorted([json.load(open(f)) for f in glob.glob(str(D / 'rounds/L*.json'))], key=lambda d: d.get('round') or 0)
R = [d for d in R if d.get('sid') == 'S024754f68']
def case(n):
    prev = R[n - 2]; sp0 = prev['spec']
    hist = [hist_entry(d, d['spec']) for d in R[:n - 1]]
    w = sp0.get('wardrobe_end') or {}
    w = {k: (L.HE_DEFAULT if k == 'he' else L.SHE_DEFAULT) if (not v or '不变' in str(v)[:4]) else v for k, v in {'he': w.get('he'), 'she': w.get('she')}.items()}
    if n == 12: w['he'] = L.SEA_HE
    if n == 9: w['he'] = L.SEA_HE
    sp, sec = director.direct(hist, sp0.get('state_end') or '', R[n - 1]['input'], R[n - 1]['kind'], 'auto', place=sp0.get('location'), place_rounds=1, set_now=sp0.get('set'), wardrobe=w)
    print(f"\n=== 第{n}轮 {R[n-1]['input']} | {sec}s loc={sp.get('location')}\n  he_end={str((sp.get('wardrobe_end') or {}).get('he'))[:40]} | form_fix={sp.get('form_fix')}")
    for k in ('seg1', 'seg2'):
        for b in sp.get(k) or []: print('   ', k[-1], '|', str(b[0])[:80])
for n in (8, 9, 12): case(n)
