"""内容包配图：转 jpg（长边 ≤1400）放 feishu/img/，再复制到公开仓库 realtime-drama-test-log 的 v/meet-pack/，飞书 <img href> 用 Pages 公网地址。尺寸写 sizes.json，地址写 urls.json。只加图片，不动仓库里别的文件。"""
import json, shutil
from pathlib import Path
from PIL import Image
D = Path(__file__).resolve().parent; R = D.parent
P = Path('/Users/vicky/Interactive storyline/projects/meet-me-again-deepspace-20261013'); REF = P / 'storyboard-v1/references'; O = R / 'opening-v1/frames'
REPO = Path('/Users/vicky/Interactive storyline/projects/realtime-drama-test-log'); SUB = 'v/meet-pack'
BASE = 'https://lyx1265897416-lab.github.io/realtime-drama-test-log/' + SUB + '/'
F = {'cover': D / 'frames/f_037.5.jpg',
     'rowan_front': REF / 'rowan.png', 'rowan_outfit': REF / 'CANON-rowan-ep1.png',
     'maisie_front': REF / 'maisie.png', 'maisie_open': O / 'REF_HER.png',
     'nora_front': P / 'storyboard-images-v1/characters/nora-style-v2.png',
     'L1': O / 'S01.png', 'L2': REF / 'S02-original.png', 'L3': REF / 'S03-original.png', 'L4': REF / 'S04-original.png', 'L5': REF / 'S05-original.png', 'L6': REF / 'S06-original.png',
     'P02': REF / 'P02.png', 'P03': REF / 'P03.png', 'P10': REF / 'P10.png', 'P01': REF / 'P01.png', 'P05': REF / 'P05.png', 'P06': REF / 'P06.png'}
(D / 'img').mkdir(exist_ok=True); (REPO / SUB).mkdir(parents=True, exist_ok=True)
sizes, urls = {}, {}
for k, src in F.items():
    im = Image.open(src).convert('RGB'); s = min(1, 1400 / max(im.size))
    if s < 1: im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    out = D / 'img' / f'{k}.jpg'; im.save(out, quality=88); shutil.copy(out, REPO / SUB / out.name)
    sizes[k] = im.size; urls[k] = BASE + out.name
(D / 'sizes.json').write_text(json.dumps(sizes)); (D / 'urls.json').write_text(json.dumps(urls, indent=1))
print(len(F), 'images'); print(sizes)
