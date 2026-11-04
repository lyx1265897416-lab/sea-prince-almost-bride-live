"""母版：把身份图、合成母版和开场末帧整理到 masters/，上传 Vivix，写 masters/urls.json。
图都来自 制作/新版互动剧集-v32：雷恩用角色库定装（sea-rian--front、lib-RIA-master），斯凯用外国人版母版 SKYW6，站位图和维萨、米拉单人定装由 rtowm.py 的 RT_* 生成，
第 1 轮关键帧用开场里雷恩说那两句时的双人首帧 WV23v（东廊，男左女右），待机用开场末帧。
用法：python3 masters_build.py"""
import json, os, shutil, subprocess, sys
from pathlib import Path
from PIL import Image
D = Path(__file__).resolve().parent; M = D / 'masters'; F = M / 'urls.json'
V = Path('/Users/vicky/Interactive storyline/projects/the-sea-princes-almost-bride/制作/新版互动剧集-v32'); R = V / 'results'; REF = V / 'refs'
OPEN = V / 'rto_openw/opening.mp4'
FF = '/Users/vicky/Interactive storyline/.media-runtime/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1'


def crop(src, out, top, bot, left=0.0, right=1.0):
    im = Image.open(src).convert('RGB'); W, H = im.size; im.crop((int(W * left), int(H * top), int(W * right), int(H * bot))).save(out, quality=93)


crop(REF / 'sea-rian--front.png', M / 'he-head.jpg', 0, .5, .1, .9)
crop(R / 'SKYW6-frame.png', M / 'her-head.jpg', .48, .76, .18, .82)
crop(R / 'SKYW6-frame.png', M / 'she-full.jpg', 0, .47, 0, .36)
for k, src in {'he-face': REF / 'sea-rian--front.png', 'he-outfit': REF / 'lib-RIA-master.png', 'her-sheet': R / 'SKYW6-frame.png', 'staging': R / 'RT_staging-frame.png',
               'open-key': R / 'WV23v-frame.png', 'vessa': R / 'RT_vessa-frame.png', 'mila': R / 'RT_mila-frame.png'}.items():
    Image.open(src).convert('RGB').save(M / f'{k}.jpg', quality=93)
subprocess.run([FF, '-y', '-v', 'error', '-sseof', '-0.15', '-i', str(OPEN), '-frames:v', '1', '-q:v', '2', str(M / 'idle-key.jpg')], check=True)
shutil.copy(M / 'idle-key.jpg', M / 'open-last.jpg')

sys.path.insert(0, '/Users/vicky/Interactive storyline')
os.environ.setdefault('MAG_PUBLIC', '1')
for _l in open('/Users/vicky/Interactive storyline/.env.vivix', encoding='utf-8'):
    if '=' in _l and _l.split('=', 1)[0].strip() == 'VIVIX_API_KEY': os.environ.setdefault('VIVIX_API_KEY', _l.split('=', 1)[1].strip().strip('"\''))
from vivix_w1 import W1Client
c = W1Client(); U = json.loads(F.read_text()) if F.exists() else {}
for key, f in {'face': 'he-face.jpg', 'face_head': 'he-head.jpg', 'outfit': 'he-outfit.jpg', 'her': 'her-sheet.jpg', 'her_head': 'her-head.jpg', 'staging': 'staging.jpg',
               'open_key': 'open-key.jpg', 'vessa': 'vessa.jpg', 'mila': 'mila.jpg', 'look_she_on': 'she-full.jpg', 'idle_key': 'idle-key.jpg'}.items():
    U[key] = c.upload(str(M / f))['url']; F.write_text(json.dumps(U, indent=1)); print(key, U[key], flush=True)
