"""Rian｜人鱼王子的假新娘 · 第三视角开放式实时版的本机中转。画面里同时看到 Rian 和她（女主）。Vivix 和 OpenRouter 的 key 只在本机，网页只拿到口令和视频地址。
和 output/vivix-tests-20261022/live_server.py 同一套流程，区别：
- 开场之后没有预设分支：每次点选项或自由输入，都实时生成一条三段视频，播完给出下一轮的两个选项和输入框，一直往下演；
- 导演层由模型自动写（director.py）；选项是导演层上一轮给的，选择点一出现就在后台把 A/B 两个选项的 spec 先写好，点选项不用等导演层；
- 第 1 段首帧 = 上一轮第 2 段的最后一帧（第 1 轮是开场最后一帧），上一轮一播完就在后台抽帧、上传，下一轮直接用。

POST /api/session {k, mode}                       → {sid, next}       重新开始（回到开场后的第一个选择点）
POST /api/round   {k, sid, kind, choice, input}    → {id}              kind=option（choice=A/B）或 free（input=她的话）
GET  /api/round/<id>?k=…                           → 状态、两段视频地址、台词字幕、下一轮选项、各阶段时刻（毫秒）
POST /api/round/<id>/view {k, play_at, seg1_end, stall, end_at, buffer}  网页回报实际开播时刻和接缝
用法：rian_third_relay.py <口令> [端口，默认 8908]"""
import json, os, re, shutil, subprocess, sys, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib import request as U
import live_common as L
import director, qa_guard
from live_common import W1Client, VivixError, JobFailed, MODEL
import vivix_fastpath as FP  # V1.5 提速：任务阶段、第 2 段预计出片时间

D = L.D; RD = D / 'rounds'; RD.mkdir(exist_ok=True); FR = D / 'frames'; FR.mkdir(exist_ok=True)
SITE = D / 'site'
TOKEN = sys.argv[1]; PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8908
TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mp4': 'video/mp4', '.mp3': 'audio/mpeg', '.jpg': 'image/jpeg', '.png': 'image/png', '.json': 'application/json'}
ORIGINS = {'http://127.0.0.1:%d' % PORT, 'http://localhost:%d' % PORT}
ORIGINS |= {'https://lyx1265897416-lab.github.io', 'http://127.0.0.1:8850', 'http://localhost:8850'}  # 即兴剧场 APP（realtime-drama-app）直接调接口
FIX_WAIT = 20
TU = L.TU
HER_URL = qa_guard.HER_URL  # 她（女主）的身份母版：第三视角每段参考图都带上
STAGING_URL = TU['staging']  # 两人站位母版（男左女右，灰底），换场那一段没有上一刻画面，靠它定左右
OPEN_FRAME = D / 'masters' / 'open-key.jpg'  # 开场确认版（外国人版 v9，71.9 秒，停在斯凯抬头看他的近景）之后切到这一张第三视角关键帧接着演：东廊里的双人中近景，男左女右并肩站着，两张脸都看得到
MAX_ROUNDS = 200
c = W1Client(); POOL = ThreadPoolExecutor(6)
C2 = W1Client(api_key=os.environ['VIVIX_API_KEY_2']) if os.environ.get('VIVIX_API_KEY_2') else None  # V3.1：第二个 Vivix 工作区（~/.config/vicky-realtime/env 里写 VIVIX_API_KEY_2）。有它时第 2 段交到这个工作区，两段真正同时生成；没有时照旧串行
now = lambda: int(time.time() * 1000)
LOCK = threading.Lock()
VIVIX = {'balance': 'unknown', 'at': None, 'err': None}  # Vivix 没有查余额接口：按每次提交的结果判断，10005 = 工作区余额不足
R = {}       # 每一轮
S = {}       # 每个会话
URLS_F = D / 'urls.json'; URLS = json.loads(URLS_F.read_text()) if URLS_F.exists() else {}
CDN_F = D / 'cdn.json'; CDN = json.loads(CDN_F.read_text()) if CDN_F.exists() else {}  # 公网链接：视频走 waku 的 GCS 地址，不走隧道（隧道下载约 100 KB/s，2.8 MB 的开场要 29 秒）
PUBLIC = os.environ.get('MAG_PUBLIC') == '1'  # 开着公网隧道时：第 2 段不校色，视频都直接从 Vivix CDN 播


def persist(path):
    r = subprocess.run(['waku', 'persist', str(path)], capture_output=True, text=True, timeout=40)
    m = re.search(r'"url":\s*"([^"]+)"', r.stdout)
    if not m: raise RuntimeError((r.stdout + r.stderr)[-200:])
    return m.group(1)

OPEN_STATE = '开场那天清晨，海下王宫的东廊。Rian 站在画面左侧，她站在画面右侧，两人并肩站着、身体侧向对方，相距半臂；她刚从海里出来，橙红色长发和衣服湿透；摄政官 Vessa 拿着深蓝册子站在画面外左侧（这一刻画面里只有他们两人，Vessa 只有声音，要正面出镜只能放在 seg2 并写进 cast）。她跳海去救被潮水卷走的好友米拉，被他救进王宫；维萨说未登记的访客会被扣留、关于这里的记忆会被封存；他刚当着维萨说她是他未来的新娘；维萨（画面外）冷冷地问她“Is that true?”，等她亲口回答，他也低头看着她。她还没回答。隐藏真相她还不知道：“未婚妻”是他临时编的，普通担保和通行证其实存在。'
OPEN_NEXT = {'cue': {'zh': '维萨问她是不是真的，他低头看着她，两人都在等她的回答。', 'en': 'Vessa asks if it is true. He looks down at her. Both wait for her answer.'},
             'A': {'zh': '先配合他，找朋友要紧。', 'en': 'Play along—for now.', 'leads_to': 'K02：他低声让她先配合、保证带她去找米拉，维萨暂时放行'},
             'B': {'zh': '当场反问：谁是你的新娘？', 'en': 'Call his bluff: whose bride?', 'leads_to': 'K02：他面不改色接住，维萨冷冷合上册子放行'}}


def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)


def url_of(key, path):
    if key not in URLS: URLS[key] = c.upload(path)['url']; URLS_F.write_text(json.dumps(URLS, indent=1))
    return URLS[key]


SAVE_LOCK = threading.Lock()


def save(rid):
    """V1.9：先写临时文件再替换，写不进去（磁盘满，2026-10-30）只记日志，不让请求崩掉、不让这一轮卡住。"""
    try:
        with SAVE_LOCK:
            tmp = RD / f'.{rid}.json.tmp'; tmp.write_text(json.dumps(R[rid], ensure_ascii=False, indent=1)); tmp.replace(RD / f'{rid}.json')
    except OSError as e: log('SAVEFAIL', rid, str(e)[:120])


def url_ok(u):
    try:
        with U.urlopen(U.Request(u, method='HEAD'), timeout=10) as r: return r.status == 200
    except Exception: return False


def speculate(s):
    """选择点一出现：在后台把 A/B 两个选项的 spec 先写好（同一份剧情记录和状态）。"""
    gen = s['gen']; s['spec_cache'] = {}
    for k in ('A', 'B'):
        opt = (s.get('next') or {}).get(k)
        if not isinstance(opt, dict) or not (opt.get('zh') or opt.get('en')): continue  # 少了一个选项也不让整轮失败
        text = opt.get('zh') or opt.get('en')
        fut = POOL.submit(director.direct, list(s['history']), s['state'], text, 'option', s['mode'], place=s.get('place'), place_rounds=s.get('place_rounds', 0), done=tuple(s.get('cards', [])), stall=s.get('stall', 0), set_now=s.get('set'), persona=s.get('persona'), wardrobe=dict(s.get('wardrobe') or {}), cont=cont_of(s))
        s['spec_cache'][k] = {'fut': fut, 'text': text, 'at': now(), 'gen': gen}


def wide(qa):
    """脸宽不到画面宽度的 0.2 就算站远了（近景约 0.35–0.5，全身约 0.12）。"""
    fb = qa.get('face_box')
    try: return bool(fb) and (float(fb[2]) - float(fb[0])) < 0.28  # v0.16：两段都是参考图后，这张只当场景参考，裁近一点没有画质负担；腰部以上的参考图也会让下一段拍远、补出女主的肩膀
    except (TypeError, ValueError, IndexError): return False


def too_close(qa):
    """V0.17c：视觉质检量的脸框偏大（正常近景约 0.35–0.55），超过 0.7 就是贴脸特写。锁帧会把它放大成整整 10 秒（V0.17b 第 12 轮皮肤显老），要往前找一帧标准近景。"""
    fb = qa.get('face_box')
    try: return bool(fb) and (float(fb[2]) - float(fb[0])) > 0.7
    except (TypeError, ValueError, IndexError): return False


def kinds(qa, *ks): return [i for i in qa.get('issues', []) if isinstance(i, dict) and i.get('kind') in ks and i.get('level') == 'high']


def crop_close(jpg, fb, target=0.34):
    """按脸的位置裁出 9:16 的近景（V0.17c：脸宽约占画面三分之一，原来 40%，头顶留一点空），再放回 720×1280。"""
    W, H = 720, 1280
    x0, y0, x1, y1 = [float(v) for v in fb]
    cw = min(W, max(240, (x1 - x0) * W / target)); ch = cw * 16 / 9
    cx = (x0 + x1) / 2 * W; top = y0 * H - 0.18 * ch
    left = min(max(0, cx - cw / 2), W - cw); top = min(max(0, top), H - ch)
    tmp = jpg.with_name(jpg.stem + '_crop.jpg')
    subprocess.run([L.FFMPEG, '-v', 'error', '-y', '-i', str(jpg), '-vf', f'crop={int(cw)}:{int(ch)}:{int(left)}:{int(top)},scale={W}:{H}:flags=lanczos', '-q:v', '2', str(tmp)], check=True)
    tmp.replace(jpg)


DL = {}  # V3.3：url → 本机文件，同一段只下载一次（原来开播前检查、段内快检、末帧各下一次）


def fetch(url, dest, parts=6):
    """V3.3：成片分 6 段并行下载、不走代理。S015323dc3 生成只要 20–30 秒，单线程下载 8 MB 却花了 55–190 秒（开播 269 秒）；并行实测快约 3 倍。失败退回整段下载。"""
    dest = Path(dest); c = DL.get(url)
    if c and Path(c).exists(): shutil.copyfile(c, dest); return dest
    op = U.build_opener(U.ProxyHandler({}))
    try:
        r = op.open(U.Request(url, headers={'Range': 'bytes=0-0'}), timeout=20); size = int(r.headers['Content-Range'].split('/')[-1]); r.read()
        step = size // parts + 1
        def part(k): return op.open(U.Request(url, headers={'Range': f'bytes={k * step}-{min(size, (k + 1) * step) - 1}'}), timeout=90).read()
        with ThreadPoolExecutor(parts) as ex: data = b''.join(ex.map(part, range(parts)))
        if len(data) != size: raise IOError(f'size {len(data)} != {size}')
        dest.write_bytes(data)
    except Exception as e:
        log('FETCH fallback', str(e)[:80]); U.urlretrieve(url, dest)
    keep = FR / f'dl_{uuid.uuid5(uuid.NAMESPACE_URL, url).hex}.mp4'; shutil.copyfile(dest, keep); DL[url] = str(keep)
    for u, p in list(DL.items())[:-12]: Path(p).unlink(missing_ok=True); DL.pop(u, None)
    return dest


def prepare_frame(s, rid, seg2_url):
    """上一轮第 2 段的最后一帧 → 下一轮第 1 段的首帧和第 2 段的参考图。
    末帧里看不到他的脸（插入特写收尾）就往前 1.5、3、5 秒再找；质检没有严重问题时原图放进 frame_raw，下一轮最多等 FIX_WAIT 秒；有严重问题必须等修图完成。"""
    try:
        mp4 = FR / f'{rid}_2.mp4'; jpg = FR / f'{rid}_last.jpg'
        if seg2_url.startswith('/'): mp4.write_bytes((SITE / seg2_url.lstrip('/')).read_bytes())  # 校色后的第 2 段在本机
        else: fetch(seg2_url, mp4)
        s2 = R[rid]['segs'][1]
        for _ in range(90):  # V3.6：等第 2 段的左右检查（约 15–25 秒，这时观众还在看第 1 段），末帧落在镜像的镜头里就跟着镜像，下一轮仍是男左女右
            if s2.get('side') is not None: break
            time.sleep(0.5)
        dur2 = float(subprocess.run([L.FFMPEG.replace('ffmpeg', 'ffprobe'), '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(mp4)], capture_output=True, text=True).stdout or 0)
        in_flip = lambda back: any(a <= dur2 - back < b for a, b in s2.get('flip') or [])
        mirror = lambda p: (subprocess.run([L.FFMPEG, '-v', 'error', '-y', '-i', str(p), '-vf', 'hflip', '-q:v', '2', str(p.with_name(p.stem + '_flip.jpg'))], check=True), p.write_bytes(p.with_name(p.stem + '_flip.jpg').read_bytes()))
        try:  # V1.5 提速：先抽一张没查过的末帧传上去，下一轮发送时质检、修图还没好就用它（不等）
            q0 = FR / f'{rid}_last_quick.jpg'
            subprocess.run([L.FFMPEG, '-v', 'error', '-y', '-sseof', '-0.15', '-i', str(mp4), '-frames:v', '1', '-q:v', '2', str(q0)], check=True)
            if in_flip(0.15): mirror(q0)
            if s.get('frame_pending') == rid: s['frame_quick'] = c.upload(q0)['url']
        except Exception as e: log('QUICKFRAMEFAIL', rid, str(e)[:120])
        qa = {}; url = None
        st_now = state_text(s)  # V2.0
        def must_fix(q): return [i for i in q.get('issues', []) if isinstance(i, dict) and i.get('level') == 'high' and (i.get('kind') == 'state' if st_now else i.get('kind') not in qa_guard.NO_FIX)]
        # V0.17c：末帧要“回正”再交给下一轮（锁帧会把它放大成整整 10 秒）：没有脸、贴脸特写、背景成了影棚、并排坐却正对镜头，都往前找一帧标准的；
        # 普通的必修问题仍然只多查一帧（每查一帧 10–20 秒）
        side = s.get('staging') == 'side'
        cands = []
        for back in (0.15, 1.5, 3.0, 4.5):
            subprocess.run([L.FFMPEG, '-v', 'error', '-y', '-sseof', f'-{back}', '-i', str(mp4), '-frames:v', '1', '-q:v', '2', str(jpg)], check=True)
            try: qa = qa_guard.check(jpg, cast=s.get('cast_last') or [], side=side, state=st_now)
            except Exception as e: qa = {'err': str(e)[:200]}; log('FRAMEQAFAIL', rid, e); break
            if qa.get('face', True) is False: log('FRAMEQA', rid, 'no face at', -back, 'try earlier'); cands.append((back, qa, jpg.read_bytes(), True, bool(must_fix(qa)))); continue
            # 第三视角：不按他的脸裁近景（会把她裁出画面）；她不在画面里（her=False）也往前找一帧双人的
            if qa.get('her', True) is False: log('FRAMEQA', rid, 'she is not in frame at', -back, 'try earlier'); cands.append((back, qa, jpg.read_bytes(), True, bool(must_fix(qa)))); continue
            frame_bad = too_close(qa) or kinds(qa, 'scene', 'staging', 'framing')
            cands.append((back, qa, jpg.read_bytes(), bool(frame_bad), bool(must_fix(qa))))
            if not frame_bad and not must_fix(qa): break
            if not frame_bad and back >= 1.5: break
            log('FRAMEQA', rid, 'reframe' if frame_bad else 'issues', 'at', -back, 'try earlier', qa.get('face_box'), [i.get('kind') for i in qa.get('issues', []) if isinstance(i, dict)])
        pick = next((c for c in cands if not c[3] and not c[4]), None) or next((c for c in cands if not c[3]), None) or (cands[0] if cands else None)
        if pick:
            back, qa, raw = pick[0], pick[1], pick[2]; jpg.write_bytes(raw)
            if pick[3]: log('FRAMEQA', rid, 'no standard frame found, keep', -back, qa.get('face_box'))
        else: back = 0.15
        qa['back'] = back
        if in_flip(back):
            mirror(jpg); qa['flipped'] = 'side'; log('FRAMEQA', rid, 'last shot was mirrored on the page, mirror the frame too')
            qa['issues'] = [i for i in qa.get('issues', []) if not (isinstance(i, dict) and i.get('kind') == 'staging')]
        elif any(re.search(r'对调|换边|Rian[^，。]{0,6}右侧|她[^，。]{0,6}左侧', i.get('text', '')) for i in kinds(qa, 'staging')):  # 第三视角 v1 第 4 轮：找不到不越轴的帧，就把这一帧左右镜像，让下一轮仍是男左女右
            subprocess.run([L.FFMPEG, '-v', 'error', '-y', '-i', str(jpg), '-vf', 'hflip', '-q:v', '2', str(jpg.with_name(jpg.stem + '_flip.jpg'))], check=True)
            jpg.write_bytes(jpg.with_name(jpg.stem + '_flip.jpg').read_bytes()); qa['flipped'] = True; log('FRAMEQA', rid, 'staging swapped, mirrored')
            qa['issues'] = [i for i in qa.get('issues', []) if not (isinstance(i, dict) and i.get('kind') == 'staging')]
        url = c.upload(jpg)['url']
        scene_bad = bool(kinds(qa, 'scene'))
        high = [i['text'] if isinstance(i, dict) else str(i) for i in qa.get('issues', [])
                if not isinstance(i, dict) or (i.get('level') == 'high' and i.get('kind') not in qa_guard.NO_FIX | {'scene', 'staging', 'framing'})]  # 瞳色、肤质交给第 2 段的身份母版纠正，不为它们让观众等修图
        if st_now: high = [i['text'] for i in qa.get('issues', []) if isinstance(i, dict) and i.get('kind') == 'state' and i.get('level') == 'high']  # V2.0：穿着不是默认时只修和状态不符的；默认的 fix 会把脱掉的衣服修回去，走 fix_state
        if scene_bad:  # V0.17c：背景成了影棚或纯色，找不到干净的帧：把背景换回这个地点，必须等它修好
            log('FRAMEQA', rid, 'scene fix', s.get('set', '')[:40])
            try:
                fixed = qa_guard.fix_scene(url, s.get('set') or director.OPEN_SET, timeout=150)
                U.urlretrieve(fixed, FR / f'{rid}_last_scene.jpg'); url = fixed; qa['scene_fixed'] = fixed
                jpg.write_bytes((FR / f'{rid}_last_scene.jpg').read_bytes())
            except Exception as e: qa['scene_fix_err'] = str(e)[:200]; log('SCENEFIXFAIL', rid, e)
        s['frame_serious'] = bool(kinds(qa, 'people'))
        if s.get('frame_pending') == rid and not scene_bad: s['frame_raw'] = url  # V2.2：不再因为质检挡下一轮，赶不上修好的图就用原图
        issues = [i['text'] for i in qa.get('issues', []) if isinstance(i, dict) and i.get('level') == 'high']
        try:  # V2.2 每轮回正末帧：第 1 段只有首帧没有身份参考，脸、发型、肤色、肌肉、戒指一轮轮累积（第 12 轮起头发变卷，第 15–17 轮脸上一片黑点、晒黑、肌肉越来越夸张）。观众看视频时后台做，不增加等待
            aj = FR / f'{rid}_anchor.jpg'; st_a = '；'.join(x for x in (st_now, ('姿态：' + s['posture']) if s.get('posture') and '姿态：' not in (st_now or '') else '') if x); qa['anchor_via'] = qa_guard.key_frame(L.anchor_prompt(st_a, issues, s.get('wardrobe'), s.get('holding') or '', bool(L.VEH.search(str(s.get('posture') or '') + str(s.get('holding') or '')))), [url, *[u or h for u, h in zip(L.key_people(s.get('wardrobe'), (s.get('she_looks') or {}).get((s.get('wardrobe') or {}).get('she') or '')), (qa_guard.HE_HEAD, qa_guard.HER_HEAD))]], aj, hedge=1)  # V2.4：站着、坐着也写进去；close-up 看不到下半身时，第 13 轮把坐着回正成站着
            diff = qa_guard.scene_diff(jpg, aj); qa['anchor_diff'] = diff
            if diff <= (qa_guard.ANCHOR_DIFF_BOTH if qa.get('her', True) and qa.get('face', True) and not s.get('frame_serious') else qa_guard.ANCHOR_DIFF_MAX): url = c.upload(aj)['url']; qa['anchored'] = True; high = []
            else: log('ANCHOR', rid, 'rejected: scene changed', diff)
        except Exception as e: qa['anchor_err'] = str(e)[:200]; log('ANCHORFAIL', rid, str(e)[:160])
        soft = [] if high else [i['text'] for i in qa.get('issues', []) if isinstance(i, dict) and i.get('level') == 'high' and i.get('kind') in ('face', 'skin', 'light')]  # light（窗外像白天）也后台修：v0.16 一次阻塞修图被退回，下一轮白等 2.5 分钟
        if st_now or qa.get('anchored'): soft = []
        if soft:  # v0.15：脸偏老、皮肤粗糙会顺着首帧一轮轮累积（v0.14 第 11–13 轮），后台修，不挡下一轮：赶得上就用修好的
            high = soft; qa['soft_fix'] = True
        if high:  # 只修严重问题（多人、女主入镜、警徽戒指、换装换人、文字、崩坏）；小偏差只记录
            log('FRAMEQA', rid, 'fix', json.dumps(high, ensure_ascii=False)[:300])
            try:
                fixed = qa_guard.fix_state(url, high, st_now, timeout=120) if st_now else qa_guard.fix(url, high, timeout=120)
                U.urlretrieve(fixed, FR / f'{rid}_last_fixed.jpg')
                diff = qa_guard.scene_diff(jpg, FR / f'{rid}_last_fixed.jpg'); qa['fix_scene_diff'] = diff
                if diff > qa_guard.SCENE_DIFF_MAX: log('FRAMEFIX', rid, 'rejected: scene changed', diff)  # 修图把背景、构图换掉了：宁可用原图
                else: qa['fixed_url'] = fixed; url = fixed
            except Exception as e: qa['fix_err'] = str(e)[:200]; log('FRAMEFIXFAIL', rid, e)
        elif 'err' not in qa: log('FRAMEQA', rid, 'ok', qa.get('sec'))
        if rid in R: R[rid]['frame_qa'] = qa; save(rid)
        if s.get('frame_pending') != rid: log('FRAME', rid, 'stale, skip'); return  # 下一轮已经用原图出发，这张修好的图不再覆盖
        s['frame_url'] = url; s['frame_from'] = rid; s['frame_hands'] = bool(qa.get('hands')) and not qa.get('fixed_url')
        log('FRAME', rid, 'ready', 'fixed' if qa.get('fixed_url') else '', 'back', back)
    except Exception as e:
        log('FRAMEFAIL', rid, e); s['frame_err'] = str(e)
    if s.get('frame_pending') in (rid, None): s['frame_ready'].set()


def cont_of(s):
    """V2.0：这一刻的姿态、手里的东西、已出现东西的外观，每轮带给导演层。"""
    return {'posture': s.get('posture') or '', 'holding': s.get('holding') or '', 'looks': dict(s.get('looks') or {}), 'items': list(s.get('items') or []), 'left': dict(s.get('left') or {}), 'outfits': list(s.get('she_looks') or {})}


def state_text(s):
    """V2.0：质检按这一刻真实的状态判，默认服装不算数。"""
    w = s.get('wardrobe') or {}; t = []
    if w.get('he'): t.append('Rian 穿着：' + w['he'])
    if w.get('she'): t.append('她穿着：' + w['she'])
    if re.search('躺|俯在|骑|摩托', s.get('posture') or ''): t.append('姿态：' + s['posture'])  # V2.2：普通站着、坐着不算特殊状态（原来每轮都算，默认的修图从不触发）
    return '；'.join(t)


def seg_eta(r, i):
    """V3.1（Vicky 11-04：两段不是同时生成吗，怎么差这么久）：Vivix 同一工作区一次只跑一条 ultrafast（11-04 实测：两条同档同时交，第 2 条在第 1 条出片时才开工；不同档能同时跑，但 fast、标准档 15 秒要 33–37 秒，更慢）。
    原来第 2 段按“马上开工”估、生成按 13.5 秒、再加 13 秒检查余量，排队时一直 ≥29 秒，播放页要等它 ≤10.5 秒才开播，结果是第 2 段整段好了才开播（S231920f01 开播只比第 2 段出片早 0–1 秒）。
    改成串行估、用 11-04 实测：15 秒段生成中位 15.8（第 1 段）、16.5（第 2 段，p80 18.9），第 1 段生成完到第 2 段开工约 2 秒，检查加上传约 6–10 秒。"""
    segs = r.get('segs') or []; x = segs[i]
    if x.get('url') or x.get('status') == 'ready': return 0.0
    if x.get('status') == 'error': return None
    if (r.get('model') or MODEL) != 'vivix-w1-ultrafast' or int(x.get('dur') or 15) != 15 or str(r.get('mode')) != '15+15':
        e = FP.eta_left(x, r.get('model') or MODEL); return None if e is None else round(e + (x.get('qa_pad') or 0), 1)
    now = time.time() * 1000; P1, P2, GAP, PAD = 16.0, 18.0, 2.0, 11.0  # PAD：检查要先把 6–9 MB 的 mp4 从 Vivix 拉到本机（1.4–7.8 秒）再问模型（5–17 秒），11-04 实测中位约 9 秒
    def gen_left(s, p):  # 这一段离生成完还有多久
        if s.get('gen_ready_at'): return 0.0
        if s.get('proc_at'): return max(1.0, (s['proc_at'] - now) / 1000 + p)
        if s.get('accepted_at'): return max(0.0, (s['accepted_at'] - now) / 1000 + 4.0) + p
        return None
    if i == 0:
        g = gen_left(x, P1); return None if g is None else round(g + PAD, 1)
    if x.get('gen_ready_at'): return round(max(1.0, (x['gen_ready_at'] - now) / 1000 + PAD), 1)  # 生成完在检查（重生成会重新计时）
    if x.get('proc_at'): return round(gen_left(x, P2) + PAD, 1)
    if C2: g = gen_left(x, P2); return None if g is None else round(g + PAD, 1)  # 两个工作区：第 2 段不用排在第 1 段后面
    g0 = gen_left(segs[0], P1)
    if g0 is None or not x.get('accepted_at'): return None
    return round(g0 + GAP + P2 + PAD, 1)


def outfit_ref(rid):
    """V3.5（S034241cf8 第 5、6 轮他赤裸上身，第 2 段还带着穿夹克的服装母版，他的脸变年轻、变成另一种画风）：他没穿上衣时，服装母版换成他的头像，只锁脸。"""
    he = str((((R[rid].get('spec') or {}).get('wardrobe_end')) or {}).get('he', ''))
    return qa_guard.HE_HEAD if re.search('赤裸|光着|裸着|没穿上衣', he) else qa_guard.OUTFIT_URL


def run_seg(rid, i, dur, prompt, first, frame_url, face_url, extra=(), no_scene=False):
    s = R[rid]['segs'][i]
    kw = dict(prompt=prompt, duration=dur, aspect_ratio='9:16')
    if i == 1: s['qa_pad'] = 11  # V3.1：开播前检查提速后（每秒 1 帧，5–8 秒），15 秒段也只留 8 秒；原来 13 秒让第 2 段的预计一直偏大，第 1 段等到第 2 段整段出片才开播（三真四假 S231920f01：开播只比第 2 段出片早 0–1 秒）  # V2.8：15 秒段实测比预计晚 2–10 秒（中位约 4 秒，两段同时在生成），多留 5 秒，宁可晚开播几秒也不在接缝停。V2.7：第 2 段查过才给地址，开播不再按出片时间倒推（第 1 段播完要停 6 秒），也不会播到一半才发现要重新生成
    use = (R[rid].get('spec') or {}).get('use_key'); key = R[rid].get('key_url')
    if first == 'bridge': kw['first_frame_image'] = frame_url; kw['last_frame_image'] = key  # V2.0：首帧上一刻、尾帧关键帧，一镜到底把动作演出来
    elif i == 1 and use == 'bridge': frame_url = key; kw['first_frame_image'] = key  # V2.0：第 2 段从变化之后的样子开始
    elif i == 1 and use == 'ref': kw['ref_images'] = [key, qa_guard.HE_HEAD, qa_guard.HER_HEAD] + list(extra)[:2] + L.swatch(R[rid]['spec'].get('wardrobe_end')); frame_url = key  # V2.0：换地点，关键帧定地点、穿着和姿态；头像不带衣服
    elif first == 'lock': kw['first_frame_image'] = kw['last_frame_image'] = frame_url  # V0.17：10+10 第 1 段首尾帧都锁成上一刻画面
    elif first or (L.SEG2_FIRST and not extra): kw['first_frame_image'] = frame_url  # v0.11：第 2 段也从同一张首帧出发（参考图模式容易拍成第三人称、出现过肩）
    elif (R[rid].get('spec') or {}).get('wardrobe_changed'): kw['ref_images'] = [frame_url, qa_guard.HE_HEAD, qa_guard.HER_HEAD] + list(extra)[:2] + L.swatch(R[rid]['spec'].get('wardrobe_end'))  # V2.0 只带头像；V1.8：穿着变了不带服装母版和站位母版（它们会把衣服穿回去），穿着看上一刻的画面
    elif no_scene: kw['ref_images'] = [L.plate_for(R[rid]['spec']) or STAGING_URL, face_url, outfit_ref(rid), HER_URL] + list(extra)[:1]  # V3.0：有这个地点的固定空景就用它，不用灰底站位图（不然会漂回上一个地点）  # 换场的第 2 段不带旧地点的画面：带了模型会在最后一拍切回旧地点（v0.15 第 3 轮）
    else: kw['ref_images'] = [frame_url, face_url, outfit_ref(rid), HER_URL] + list(extra)[:1] + ([L.plate_for(R[rid]['spec']) if not (i == 0 and (R[rid].get('spec') or {}).get('scene_changed')) else L.plate_for({'location': R[rid].get('place_before') or ''})] if not extra and (L.plate_for(R[rid]['spec']) if not (i == 0 and (R[rid].get('spec') or {}).get('scene_changed')) else L.plate_for({'location': R[rid].get('place_before') or ''})) else [])  # V3.4：换场那一轮第 1 段还在旧地点，带旧地点（place_before）的空景，不带新地点的（人鱼王子 11-04：会客厅那段带了潮门空景漂成别的大厅；什么都不带又漂成水下）  # V3.0：没有配角时第 5 张带上这个地点的空景  # Vivix 最多 5 张  # 有配角出镜时仍用参考图带上她的身份母版
    if i == 1 and L.TU.get('vehicle') and 'ref_images' in kw and len(kw['ref_images']) < 5 and any(L.RIDE_ON.search(str(b[0])) for b in (R[rid].get('spec') or {}).get('seg2') or []): kw['ref_images'] = kw['ref_images'] + [L.TU['vehicle']]  # V2.3：摩托每轮款式都在变
    def gen(body):
        cli = C2 if (i == 1 and C2) else c; sub = W1Client(api_key=os.environ['VIVIX_API_KEY_2'], max_retries=0) if cli is C2 else W1Client(max_retries=0); job = None  # V3.1：第 2 段走第二个工作区
        tries = 4 if first in ('lock', 'bridge') else (5 if 'ref_images' in kw else 2)  # V1.1：参考图段失败多是几秒内被拒、不扣费，先在参考图模式重提 3 次（保住身份母版），第 5 次才退回首帧  # 第三视角 v1：首尾帧锁这几天大约一半任务在 6–15 秒内 generation_failed（同一请求重提就成功），锁帧段最多重提 3 次
        force_fb = False  # V1.5 提速：参考图段报 request_timeout 是这条提示词在参考图模式下固定失败（同一条换 fast 也失败），不再重提 3 次，下一次直接退回首帧
        for attempt in range(tries):  # 任务本身失败（JobFailed）时自动重提；其余失败直接报
            if first in ('lock', 'bridge') and attempt == tries - 1:  # 连续 3 次锁帧失败：退回首帧续接，不让这一轮失败
                kw.pop('last_frame_image', None); body = c.build(**kw); s['lock_fallback'] = True; log('LOCKFALLBACK', rid, i + 1)
            if 'ref_images' in kw and (attempt == tries - 1 or force_fb) and frame_url:  # V1.1 第 7 轮：某些参考图段同一提示词 12 次 generation_failed，同一提示词改成首帧模式就能生成
                kw.pop('ref_images', None); kw['first_frame_image'] = frame_url; body = c.build(**kw); s['ref_fallback'] = True; log('REFFALLBACK', rid, i + 1)
            net = 0
            while True:
                try: jid = sub.submit_body(body); break
                except VivixError as e:
                    if e.code == 30006:  # 并发满、未建任务，每 3 秒再试
                        s['rejected_30006'] = s.get('rejected_30006', 0) + 1; time.sleep(3); continue
                    if e.code == 10002 and 'auth backend unavailable' in str(e) and net < 3:  # 鉴权服务 503，请求在鉴权这一步就被拒，没有建任务，可以安全重提
                        net += 1; s['auth_retry'] = s.get('auth_retry', 0) + 1; log('AUTHRETRY', rid, i + 1, net); time.sleep(6); continue
                    if e.code == -1 and 'urlopen error' in str(e) and net < 3:  # 连接阶段就断了：请求没到 Vivix，不会建任务
                        net += 1; s['net_retry'] = s.get('net_retry', 0) + 1; log('NETRETRY', rid, i + 1, net, str(e)[:120]); time.sleep(2); continue
                    raise  # 其他情况（包括"已发出、等回复时断了"）不知道有没有建任务，不自动重提，防重复扣费
            s.update(job_id=jid, accepted_at=now()); save(rid)
            job = None
            for w in range(4):  # 轮询断网不算失败：任务已经建好，继续查同一个 job_id
                try: job = FP.wait_job(cli, jid, s); break  # V1.5：记下排队、开始生成的时刻
                except VivixError as e:
                    if e.code != -1 or w == 3: raise
                    log('WAITRETRY', rid, i + 1, jid, str(e)[:120]); time.sleep(3)
                except JobFailed as e:
                    if attempt < tries - 1: force_fb = re.search('request_timeout|content_rejected', str(e)) is not None and 'ref_images' in kw; log('JOBFAILED_RESUBMIT', rid, i + 1, jid, str(e)[:160]); s.pop('proc_at', None); s['resubmitted'] = jid; s['failed_jobs'] = s.get('failed_jobs', []) + [jid]; job = None; break
                    raise
            if job: break
        for _ in range(30):  # 任务成功后 mp4 偶尔晚几秒才能取到
            if url_ok(job['video_url']): break
            time.sleep(1)
        return job

    try:
        job = gen(c.build(**kw)); s['gen_ready_at'] = now()
        sp_hc = R[rid].get('spec') or {}; looks = lambda txt, n: re.sub(r'^[^：]{0,12}：', '', str(txt or ''))[:n]  # V3.0：每个人带一句外形，检查模型才分得清谁是女主、谁是配角（三真四假 S2351533a4 把 Sloane 的蓝裙子当成女主的裙子变色）
        names = [f'男主（{looks(L.HE_LOOK, 50)}）', f'女主（{looks(L.HER, 90)}）'] + [f'{c}（{looks(L.CAST[c][0], 110)}）' if c in L.CAST else c for c in (sp_hc.get('cast') or []) if not (c in L.CAST and hasattr(L, 'on_screen') and not any(L.on_screen(c, b) for b in (sp_hc.get(f'seg{i + 1}') or [])))] + [x['name'] for x in (sp_hc.get('extras') or []) if isinstance(x, dict) and x.get('name')]  # V3.3：只按这一段画面里的配角查（只出声的不算，出现就是多人）；V2.7：每一轮每一段都查，不合格重新生成，最多三次，都不合格就拦下
        people = f"{len(names)} 个人：{'；'.join(names)}" + ('；背景远处的路人不算' if re.search('酒吧|餐厅|夜宵|摊|街|人群|派对', str(sp_hc.get('set') or '')) else '') + ('；这一段他会变身成狼，不算错误' if sp_hc.get('wolf') else '')
        w_hc = sp_hc.get('wardrobe_end') or {}; w0_hc = sp_hc.get('wardrobe_start') or {}
        wear = f"男主：{w_hc.get('he') or L.HE_DEFAULT}；女主：{w_hc.get('she') or L.SHE_DEFAULT}" if i == 1 else '；'.join(x for x in ((f"男主：{w0_hc.get('he') or L.HE_DEFAULT}" if w0_hc.get('he') == w_hc.get('he') else ''), (f"女主：{w0_hc.get('she') or L.SHE_DEFAULT}" if w0_hc.get('she') == w_hc.get('she') else '')) if x)  # V3.4：第 1 段也查，只查这一轮没换装的人（Rafael 11-04 第 4 轮第 1 段他的牛仔裤变成黑裤）
        magic = re.search('飞|魔法|悬浮|漂浮|超能力|变身|穿越', str(R[rid].get('input') or ''))
        def bg_side(u):  # V3.6：两人左右对调的镜头标出来（s['flip']），播放页播到那几秒水平镜像；和开播检查同时开始、不挡开播，只认最后通过检查的那一条
            mp4 = FR / f'{rid}_{i + 1}_side_{uuid.uuid5(uuid.NAMESPACE_URL, u).hex[:8]}.mp4'
            try:
                fetch(u, mp4); sd = qa_guard.side_flips(mp4, looks(L.HE_LOOK, 50), looks(L.HER, 90))
                if s.get('side_of') == u: s['flip'] = sd['flip']; s['side'] = {k: sd[k] for k in ('both', 'cuts', 'sec')}
                log('SIDE', rid, i + 1, sd['sec'], sd['both'], ('flip ' + json.dumps(sd['flip'])) if sd['flip'] else 'ok', '' if s.get('side_of') == u else '(regenerated, ignored)')
            except Exception as e:
                if s.get('side_of') == u: s['side'] = {'err': str(e)[:160]}
                log('SIDEFAIL', rid, i + 1, str(e)[:160])
            finally: mp4.unlink(missing_ok=True); save(rid)
        for tn in range(3):
            hcf = FR / f'{rid}_{i + 1}_hc.mp4'
            s['side_of'] = job['video_url']; s.pop('side', None); s.pop('flip', None)
            try: fetch(job['video_url'], hcf); threading.Thread(target=bg_side, args=(job['video_url'],), daemon=True).start(); hc = qa_guard.hard_check(hcf, people, wear)
            except Exception as e: hc = {'bad': False, 'kinds': [], 'err': str(e)[:120]}
            hcf.unlink(missing_ok=True); s.setdefault('hard_check', []).append(hc); log('HARDCHECK', rid, i + 1, tn, json.dumps(hc, ensure_ascii=False)[:200])
            kinds = set(hc.get('kinds') or []) or ({'people'} if hc.get('bad') else set())
            if magic: kinds.discard('motion')  # 她自己要飞、要魔法时不算
            if kinds == {'clothes'} and sp_hc.get('cast'): s['clothes_cast_ignored'] = s.get('clothes_cast_ignored', 0) + 1; kinds = set()  # V3.1：有配角在画面里时，只报衣服颜色的不重生成、只记录（S231920f01、S00530299f 都是把 Sloane 的蓝裙当成女主裙子变色，每次多等约 25 秒）
            if i == 0 and kinds and hc.get('frames') and set(hc['frames']) <= {1}: s['first_frame_issue'] = hc.get('why'); kinds = set()  # V3.3：第 1 段第 1 帧就是上一轮末帧，重生成改不掉（S0209398d1 第 3 轮“第 1 帧边缘多一只手”连拦两次后报错），只记录
            if not kinds: break
            if tn == 2: raise RuntimeError('这段画面没有通过检查，已拦下，请再发送一次')
            s['gate_regen'] = tn + 1; job = gen(c.build(**kw)); s['gen_ready_at'] = now()
        cast = list((R[rid].get('spec') or {}).get('cast') or []) + [x['name'] for x in ((R[rid].get('spec') or {}).get('extras') or []) if isinstance(x, dict) and x.get('name')]  # V1.5：其他角色不算多余的人
        props = [x.get('name') for x in ((R[rid].get('spec') or {}).get('props') or []) if isinstance(x, dict) and x.get('name')] + [w + '（披在她身上）' for w in (R[rid].get('worn') or [])]
        sp_now = R[rid].get('spec') or {}; w_end = sp_now.get('wardrobe_end') or {}
        st_seg = '；'.join(x for x in (('Rian 穿着：' + w_end['he']) if w_end.get('he') else '', ('她穿着：' + w_end['she']) if w_end.get('she') else '', ('姿态：' + sp_now['posture_end']) if re.search('躺|俯在|骑|摩托', str(sp_now.get('posture_end') or '')) else '') if x) if i == 1 else ''
        def bg_qa(u=job['video_url'], jid=s.get('job_id')):  # V1.5 提速：段内快检移出等待路径，只记录，不再重生成。V2.2：状态复查也只记录（挡开播时加 12 秒，重生成再加 30–45 秒，3 次触发都是半躺算不算躺这种误报）
            mp4 = FR / f'{rid}_{i + 1}_q0.mp4'
            try:
                fetch(u, mp4); q = qa_guard.seg_check(mp4, cast=cast, props=props)
                if st_seg: s['state_check'] = qa_guard.seg_state(mp4, st_seg); log('SEGSTATE', rid, i + 1, 'logged', json.dumps(s['state_check'], ensure_ascii=False)[:200])
            except Exception as e: q = {'regen': False, 'err': str(e)[:160]}; log('SEGQAFAIL', rid, i + 1, e)
            s.setdefault('seg_qa', []).append(dict(q, job=jid)); save(rid)
            for x in (mp4, mp4.with_suffix('.grid.jpg')): x.unlink(missing_ok=True)  # V1.9：质检下载的视频用完就删（CDN 上有，这里攒了 1.7G）
            log('SEGQA', rid, i + 1, 'bad (logged only)' if q.get('regen') else 'ok', q.get('sec'), json.dumps([x.get('kind') + ':' + x.get('text', '')[:30] for x in q.get('issues', [])], ensure_ascii=False)[:300])
        threading.Thread(target=bg_qa, daemon=True).start()
        s['done_at'] = now()
        s.update(url=job['video_url'], ready_at=now(), seconds=job.get('duration') or dur, status='ready')
        VIVIX.update(balance='ok', at=now(), err=None)
        log('SEG', rid, i + 1, 'ready', round((s['ready_at'] - R[rid]['director_at']) / 1000, 1), 's', 'vivix', round((s['gen_ready_at'] - s['accepted_at']) / 1000, 1))
    except Exception as e:
        low = isinstance(e, VivixError) and getattr(e, 'code', None) == 10005
        s.update(status='error', err=('Vivix 工作区余额不足，请先给 Vivix 工作区充值，再回到这个选择点重新发送。' if low else str(e)[:300]), err_code=getattr(e, 'code', None), ready_at=now())
        if low: VIVIX.update(balance='insufficient', at=now(), err=str(e)[:200]); log('[credit] VIVIX BALANCE INSUFFICIENT', rid, i + 1, str(e)[:160])
        else: log('SEGFAIL', rid, i + 1, e)
    save(rid)


def update_worn(worn, sp):
    """V1.1：剧情里披到她身上的东西（外套、毯子、围巾）要一直写进提示词和质检，直到剧情里拿下来。按 props 的 how 判断。"""
    for x in sp.get('props') or []:
        if not isinstance(x, dict) or not x.get('name'): continue
        how = str(x.get('how', '')); name = str(x['name'])
        if '外套' in name: continue  # kisstest：外套不当道具，只从分镜动作里认（director 规定“他的外套不当道具”，第 10 轮 props 是空的，外套没记下）
        if re.search(r'脱下|拿下|取下|还给|摘下|放回', how): worn = [w for w in worn if w != name]
        elif re.search(r'腿|膝', how): continue  # kisstest：盖在腿上不算穿在身上（第 15 轮毛毯被记成“穿在大衣外面”，第 17、18 轮她整个人换了装）
        elif re.search(r'披|穿上|穿在|围上|留在她', how) and name not in worn: worn.append(name)
    acts = [str(b[0]) for k in ('seg1', 'seg2') for b in (sp.get(k) or [])]
    on = L.JACKET in worn  # 按分镜顺序逐拍走（和提示词逐拍状态句同一套判断）
    for a in acts: on = L.jacket_step(on, a)
    worn = [w for w in worn if w != L.JACKET] + ([L.JACKET] if on else [])
    if sp.get('scene_changed'): worn = [w for w in worn if '毯' not in w or any(w in a for a in acts)]  # kisstest：换了地点，毯子留在原地
    return worn


def tone_match(rid):
    """V1.1：同一地点（不换场）时，第 2 段整体按第 1 段校色：两段各取整段平均 RGB，算每个通道的增益（限制在 0.85–1.18），偏差超过 6% 才改。
    V1.0 两组里第 1 段到第 2 段有 5 处明显冷暖跳变（参考图模式的第 2 段会重新打光）。改好的文件放在 site/media/tm/，由中转直接提供。"""
    import numpy as np, dissolve
    r = R[rid]
    q1 = sorted(FR.glob(f'{rid}_1_q*.mp4')); q2 = sorted(FR.glob(f'{rid}_2_q*.mp4'))
    if not q1 or not q2: return
    a, b = dissolve.frames(str(q1[-1])), dissolve.frames(str(q2[-1]))
    m1, m2 = a.reshape(-1, 3).mean(0), b.reshape(-1, 3).mean(0)
    g = np.clip(m1 / np.maximum(m2, 1), 0.85, 1.18)
    r['segs'][1]['tone'] = {'seg1': [round(float(x), 1) for x in m1], 'seg2': [round(float(x), 1) for x in m2], 'gain': [round(float(x), 3) for x in g]}
    if float(np.abs(g - 1).max()) < 0.06: return
    if PUBLIC: log('TONE', rid, 'skip (public: seg2 stays on the Vivix CDN)', [round(float(x), 2) for x in g]); return  # 公网版：校色文件要经这台 Mac 传出去（5.9 MB 约 44 秒），宁可不校色
    out = SITE / 'media' / 'tm' / f'{rid}_2.mp4'; out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([L.FFMPEG, '-v', 'error', '-y', '-i', str(q2[-1]), '-vf', f'colorchannelmixer=rr={g[0]:.3f}:gg={g[1]:.3f}:bb={g[2]:.3f}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', str(out)], check=True)
    r['segs'][1]['url_orig'] = r['segs'][1]['url']; r['segs'][1]['url'] = f'/media/tm/{rid}_2.mp4'  # 相对地址：经公网链接打开时也能播（原来写死 127.0.0.1，别的电脑打不开）
    log('TONE', rid, 'seg2 gain', [round(float(x), 2) for x in g])


def worker(rid):
    try: _worker(rid)
    except Exception as e:  # 任何意外都把这一轮标成失败，不能让它一直卡在 submitted 挡住后面的请求
        R[rid].update(status='error', err='中转内部错误：' + str(e)[:200]); save(rid); log('WORKERFAIL', rid, repr(e)[:300])


def _worker(rid):
    r = R[rid]; s = S[r['sid']]
    try:
        # 1) 导演层：点选项用预先写好的 spec（还没写完就等它），自由输入现写
        cache = s.get('spec_cache', {}).get(r['choice']) if r['kind'] == 'option' else None
        sp = None
        if cache and cache['gen'] == s['gen']:
            try:
                sp, dsec = cache['fut'].result(timeout=120)
                r['director'] = 'prefetched'; r['director_wait'] = round((now() - r['at']) / 1000, 1)
            except Exception as e: log('PREFETCHFAIL', rid, e)
        if sp is None:
            r['director'] = 'live'; sp, dsec = director.direct(list(s['history']), s['state'], r['input'], r.get('director_kind') or r['kind'], r['mode'], place=s.get('place'), place_rounds=s.get('place_rounds', 0), done=tuple(s.get('cards', [])), stall=s.get('stall', 0), set_now=s.get('set'), persona=s.get('persona'), wardrobe=dict(s.get('wardrobe') or {}), cont=cont_of(s))
            r['director_wait'] = dsec
        r['director_sec'] = dsec; r['place_before'] = s.get('place'); r['place_rounds_before'] = s.get('place_rounds', 0)
    except Exception as e:
        r.update(status='error', err='导演层失败：' + str(e)[:200]); save(rid); log('DIRFAIL', rid, e); return
    # 2) 首帧：等上一轮的末帧准备好（第 1 轮是开场末帧）
    # V1.5 提速：不等末帧质检和修图。修好了用修好的；质检没严重问题用原图；其余用刚抽出来的末帧；连它都还没传上去（点得极快）才等几秒
    if not s['frame_ready'].is_set():  # V2.0：多等一下回正的末帧。V2.2：等 20 秒改 6 秒（原来姿态总有值，第 3 轮白等 20 秒）
        s['frame_ready'].wait(6)
        for _ in range(48):  # V2.4：至少等到质检做完（回归 R5：抽出来的末帧里多了一个她，质检已经会往前换一帧，但这轮直接用了没查过的）
            if s.get('frame_raw') or s['frame_ready'].is_set(): break
            time.sleep(0.25)
        if s.get('frame_serious'): s['frame_ready'].wait(25)  # 末帧多了人：等修好
    if s['frame_ready'].is_set(): frame_url = s.get('frame_url'); r['frame_pick'] = 'ready'
    elif s.get('frame_raw'): frame_url = s['frame_raw']; r['frame_pick'] = 'checked raw'
    else:
        for _ in range(40):
            if s.get('frame_quick') or s['frame_ready'].is_set(): break
            time.sleep(0.25)
        frame_url = s.get('frame_url') if s['frame_ready'].is_set() or not s.get('frame_quick') else s['frame_quick']
        r['frame_pick'] = 'ready' if s['frame_ready'].is_set() else ('quick' if s.get('frame_quick') else 'previous')
    if r['frame_pick'] != 'ready': r['frame_raw_used'] = True
    log('FRAMEPICK', rid, r['frame_pick'], 'pending', s.get('frame_pending'))
    face_url = qa_guard.FACE_URL  # 中性背景身份母版，不带场景
    if not frame_url: r.update(status='error', err='上一轮的末帧没准备好：' + s.get('frame_err', '')); save(rid); return
    extra = L.seg2_cast_refs(sp)
    ref_url = s.get('frame_ref') or frame_url  # 第 1 轮是去掉她的手的开场帧；这一轮成功后才丢掉（失败重发时还要用）
    if s['mode'] == 'auto': r['mode'] = sp.get('dur_mode') or '15+15'; r['auto_mode'] = True; r['dur_upgraded'] = sp.get('dur_upgraded')  # V1.7：一个链接自动分流
    lock = r['mode'] in L.SEG1_LOCK
    hands_now = bool(s.get('frame_hands')) and not (lock and ref_url != frame_url)  # 锁帧用的是无手开场帧时，首帧里没有她的手
    jacket_start = False; worn_now = []  # V2.0：衣服都走 wardrobe（Rafael 第 5–9 轮“他的外套”只有名字没有样子，牛仔、皮夹克、背包来回变）
    r['worn'] = worn_now
    # V2.0 状态关键帧：两段同时生成，第 2 段看不到第 1 段。穿着、姿态、地点变了，先画出变化之后的那一张，两段都对着它演。失败就退回原来的写法，不让这一轮失败
    w0, w1 = sp.get('wardrobe_start') or {}, sp.get('wardrobe_end') or {}
    moved_now = L.moved(sp, s.get('set') or director.OPEN_SET)
    sp['use_key'] = None
    sp['she_look_url'] = (s.get('she_looks') or {}).get(w1.get('she') or '')  # V2.6
    plain_move = moved_now and not w0 and not w1 and director._pose(sp.get('posture_end')) in ('站', '坐')  # V2.2：穿着默认、站着或坐着的普通换场不画关键帧（17 轮里 6 轮，每次多等 15–31 秒），用站位母版和服装母版
    if r['mode'] not in L.SEG1_LOCK and sp.get('key') and not plain_move and (moved_now or w0 != w1 or sp.get('posture_changed')):
        tk = now(); r['status'] = 'keyframe'; r['mode'] = r['mode']; save(rid)
        try:
            kj = FR / f'{rid}_key.jpg'; r['key_via'] = qa_guard.key_frame(L.key_prompt(sp, moved_now), [frame_url, L.key_people(w1, sp['she_look_url'])[0] or qa_guard.HE_HEAD, L.key_people(w1, sp['she_look_url'])[1] or qa_guard.HER_HEAD] + ([L.TU['vehicle']] if L.TU.get('vehicle') and re.search('骑|摩托', str(sp.get('posture_end'))) else []), kj)
            r['key_url'] = c.upload(kj)['url']  # 传到 Vivix 再用，比外部地址稳
            if w1.get('she') and not L.is_base(w1['she']) and w1['she'] not in (s.get('she_looks') or {}):  # V2.7：这条裙子第一次画出来的样子，只留她那半边（带两个人的图当参考会多画人），之后的关键帧和回正照它
                def keep_look(src=kj, name=w1['she']):
                    try:
                        from PIL import Image
                        im = Image.open(src); w_, h_ = im.size; cj = FR / f'{rid}_look.jpg'; im.crop((int(w_ * .45), 0, w_, h_)).convert('RGB').save(cj, 'JPEG', quality=92)
                        s.setdefault('she_looks', {}).setdefault(name, c.upload(cj)['url'])
                    except Exception as e: log('LOOKFAIL', rid, str(e)[:120])
                threading.Thread(target=keep_look, daemon=True).start()
            sp['use_key'] = 'ref' if (moved_now or extra or sp.get('offscreen_change')) else 'bridge'  # V2.6：换衣服不走首尾帧（首尾帧会把中间的换衣过程演出来，第 4 轮她上身裸露）  # 有身份母版的配角要带参考图，首尾帧模式带不了
        except Exception as e: log('KEYFAIL', rid, str(e)[:200])  # V2.2：不再重试和退回 Waku（曾一次等 195 秒），这一轮按没有关键帧走
        r['key_sec'] = round((now() - tk) / 1000, 1); log('KEY', rid, sp['use_key'], r['key_sec'], 's')
    segs = L.prompts(sp, r['mode'], hands_in_frame=hands_now, set_start=s.get('set') or director.OPEN_SET, stage_start=s.get('staging') or 'face', seg2_first=L.SEG2_FIRST and not extra, worn='、'.join(w for w in worn_now if w != L.JACKET), jacket_start=jacket_start)
    r['line_times'] = L.line_times(sp, r['mode'])  # V1.8：字幕只在说这句时显示
    r['mix'] = L.mix_of(sp)  # V2.3：配乐和歌声，播放时叠上去
    r.update(status='generating', director_at=now(), spec=sp, prompts=[p for _, p, _ in segs], model=MODEL, frame_from=s.get('frame_from'),
             lines={'seg1': [b[1] for b in sp['seg1']], 'seg2': [b[1] for b in sp['seg2']]}, zh=sp.get('zh', {}), next=sp.get('next'))
    r['segs'] = [{'dur': d, 'mode': '首尾帧到关键帧' if f == 'bridge' else '首尾帧锁' if f == 'lock' else ('首帧续接' if f else '参考图'), 'status': 'generating'} for d, _, f in segs]; save(rid)
    log('SUBMIT', rid, r['mode'], r['director'], 'director', r['director_wait'], 's')
    th = [threading.Thread(target=run_seg, args=(rid, i, d, p, f, ref_url if f == 'lock' else (frame_url if (f or (L.SEG2_FIRST and not extra)) else ref_url), face_url, extra if i == 1 else (), i == 1 and L.moved(sp, s.get('set') or director.OPEN_SET))) for i, (d, p, f) in enumerate(segs)]
    if str(r['mode']).startswith('15') and not C2:  # V3.1：有第二个工作区就两段同时交。V2.8：Vivix 同一工作区基本一次跑一条，等第 1 段开工再交第 2 段，开播才早（别信这段直播 15+15 实测）
        th[0].start(); t0 = time.time()
        while time.time() - t0 < 30 and not (r['segs'][0].get('proc_at') or r['segs'][0].get('status') in ('ready', 'error')): time.sleep(0.3)
        th[1].start()
    else:
        for t in th: t.start(); time.sleep(0.2)
    for t in th: t.join()
    ok = all(x['status'] == 'ready' for x in r['segs'])
    # V1.5 提速：不再校色（要等两段都好再重新编码第 2 段，播放页已经按原地址预载）
    r['status'] = 'done' if ok else 'error'; save(rid)
    if not ok: s['spec_cache'] = {}; log('SPECDROP', rid, 'round failed: next try rewrites the spec')  # V1.1 第 7 轮：同一份预写 spec 的第 2 段连续 12 次 generation_failed（文字触发），重发时必须重写
    log('DONE', rid, r['status'], [round((x.get('ready_at', 0) - r['director_at']) / 1000, 1) for x in r['segs']])
    if ok and s['gen'] == r['gen']:  # 推进剧情：记下这一轮，后台准备下一轮的首帧和两个选项的 spec
        s.pop('frame_ref', None)
        s['history'].append(hist_entry(r, sp))
        s['state'] = sp.get('state') or s['state']; s['next'] = sp['next']; s['round'] += 1
        changed = bool(sp.get('scene_changed'))
        s['place'] = sp.get('location') or s.get('place'); s['place_rounds'] = 0 if changed else s.get('place_rounds', 0) + 1
        if changed or not s.get('set'): s['set'] = sp.get('set') or s.get('set')
        s['cast_last'] = list(sp.get('cast') or []) + [x['name'] for x in (sp.get('extras') or []) if isinstance(x, dict) and x.get('name')]
        s['worn'] = r.get('worn') or []; s['worn_after'] = s['worn']
        s['wardrobe'] = sp.get('wardrobe_end') or {}  # V1.8
        s['posture'] = sp.get('posture_end') or ''; s['holding'] = sp.get('holding_end') or ''; s['looks'] = sp.get('looks') or {}; s['items'] = sp.get('items_end') or []; s['left'] = sp.get('left_end') or {}  # V2.0；V2.4 物品台账
        s['staging'] = sp.get('staging') or s.get('staging') or 'face'
        new = [str(k).strip().upper() for k in (sp.get('cards_done') or []) if str(k).strip().upper() not in s.setdefault('cards', [])]
        s['cards'] += new
        try: prog = int(sp.get('progress') or 0)
        except (TypeError, ValueError): prog = 0
        moved = bool(new or changed or (sp.get('input_type') == 'direction' and sp.get('delivered')))  # 只认换场、新演出的关键片段和她自己的情节被兑现（V1.4：她在推自己的情节也算推进，不再触发资料包兜底）；“她的问题被回答了”不算推进（v0.8 测试里它让兜底永远不触发）
        s['stall'] = 0 if moved else s.get('stall', 0) + 1
        r.update(location=s['place'], scene_changed=changed, route=sp.get('route'), target=sp.get('target'), cards_new=new, cards_after=list(s['cards']),
                 progress=prog, three_q=sp.get('three_q'), stall_after=s['stall'], input_type=sp.get('input_type'), ask=sp.get('ask'), delivered=sp.get('delivered'), hook_type=sp.get('hook_type')); save(rid)
        log('PLACE', rid, s['place'], 'changed' if changed else f"rounds_here={s['place_rounds']}", 'route', sp.get('route'), 'target', sp.get('target'),
            'cards', s['cards'], 'stall', s['stall'], 'type', sp.get('input_type'), 'try', sp.get('director_attempts'), 'ask', sp.get('ask'), 'delivered', sp.get('delivered'), 'hook', sp.get('hook_type'))
        s['frame_ready'] = threading.Event(); s['frame_serious'] = False
        s['frame_pending'] = rid; s.pop('frame_raw', None); s.pop('frame_quick', None)
        threading.Thread(target=prepare_frame, args=(s, rid, r['segs'][1]['url']), daemon=True).start()
        speculate(s)


def hist_entry(r, sp):
    return {'input': r['input'], 'kind': r['kind'], 'lines': r['lines']['seg1'] + r['lines']['seg2'],
            'did': sp.get('did'), 'ask': sp.get('ask'), 'delivered': bool(sp.get('delivered')), 'hook_type': sp.get('hook_type'),
            'reveal': sp.get('reveal') or [], 'intimacy': sp.get('intimacy') or 0, 'place': sp.get('location'), 'set': sp.get('set'), 'extras': sp.get('extras') or [], 'input_type': sp.get('input_type'), 'kiss': bool(sp.get('kiss')), 'surprise': bool(sp.get('surprise')), 'staging': sp.get('staging'),
            'pending': sp.get('pending_move') if isinstance(sp.get('pending_move'), dict) else {}, 'closed': str(sp.get('closed') or ''),  # V3.9：结尾悬着的招、这一轮关闭的疑问
            'opts': [((sp.get('next') or {}).get(k) or {}).get('zh', '') for k in ('A', 'B')]}


def new_session(mode):
    sid = 'S' + time.strftime('%H%M%S') + uuid.uuid4().hex[:3]
    s = {'sid': sid, 'mode': mode, 'history': [], 'state': OPEN_STATE, 'next': OPEN_NEXT, 'round': 0, 'gen': uuid.uuid4().hex, 'place': '东廊', 'place_rounds': 0, 'cards': [], 'stall': 0, 'set': director.OPEN_SET, 'staging': 'face', 'posture': 'Rian 站在画面左侧，她站在画面右侧，两人并肩站着、身体侧向对方',
         'frame_ready': threading.Event(), 'frame_from': 'OPEN'}
    s['frame_url'] = url_of('OPEN_V11', OPEN_FRAME); s['frame_hands'] = False; s['frame_ready'].set()  # 第三视角：开场末帧本身就是双人中近景，锁帧和参考图都用它
    S[sid] = s; speculate(s); log('SESSION', sid, mode)
    return s


def restore_session(sid):
    """中转重启后内存里的会话没了：按 rounds/ 里这个会话已完成的轮次恢复剧情记录、状态、下一轮选项和末帧。"""
    done = []
    for f in RD.glob('L*.json'):
        try: r = json.loads(f.read_text())
        except Exception: continue
        if r.get('sid') == sid and r.get('status') == 'done' and r.get('spec'): done.append(r)
    if not done: return None
    done.sort(key=lambda r: r['at']); last = done[-1]
    jpg = FR / f"{last['id']}_last.jpg"
    if not jpg.exists(): return None
    s = {'sid': sid, 'mode': 'auto' if last.get('auto_mode') else last['mode'], 'round': len(done), 'gen': uuid.uuid4().hex, 'frame_ready': threading.Event(), 'frame_from': last['id'],
         'history': [hist_entry(r, r['spec']) for r in done],
         'state': last['spec'].get('state') or OPEN_STATE, 'next': last['spec']['next']}
    s['place'] = '东廊'; s['place_rounds'] = 0; s['cards'] = []; s['stall'] = 0; s['set'] = director.OPEN_SET
    for r in done:
        s['place'] = r.get('location') or s['place']; s['place_rounds'] = 0 if r.get('scene_changed') else s['place_rounds'] + 1
        s['cards'] += [k for k in r.get('cards_new', []) if k not in s['cards']]; s['stall'] = r.get('stall_after', 0)
        if r.get('scene_changed') and (r.get('spec') or {}).get('set'): s['set'] = r['spec']['set']
        s['staging'] = (r.get('spec') or {}).get('staging') or s.get('staging') or 'face'
    s['worn'] = s['worn_after'] = []
    sp0 = last.get('spec') or {}; s['wardrobe'] = sp0.get('wardrobe_end') or {}; s['posture'] = sp0.get('posture_end') or ''; s['holding'] = sp0.get('holding_end') or ''; s['items'] = sp0.get('items_end') or []; s['left'] = sp0.get('left_end') or {}; s['looks'] = sp0.get('looks') or {}  # V2.0
    s['frame_url'] = c.upload(jpg)['url']; s['frame_ready'].set()
    S[sid] = s; speculate(s); log('RESTORE', sid, 'rounds', len(done), 'from', last['id'])
    return s


class H(BaseHTTPRequestHandler):
    def cors(self):
        o = self.headers.get('Origin', '')
        if o in ORIGINS: self.send_header('Access-Control-Allow-Origin', o); self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'); self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def out(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode(); self.send_response(code); self.cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_OPTIONS(self): self.send_response(204); self.cors(); self.end_headers()

    def static(self, path):
        host = self.headers.get('Host', '')
        u = CDN.get(path.lstrip('/'))
        if u and not host.startswith(('127.0.0.1', 'localhost')):  # 经公网链接打开：视频跳到 GCS
            self.send_response(302); self.send_header('Location', u); self.send_header('Content-Length', '0'); self.end_headers(); return
        f = (SITE / (path.lstrip('/') or 'index.html')).resolve()
        if SITE.resolve() not in f.parents and f != SITE.resolve() or not f.is_file(): return self.out(404, {'err': 'not found'})
        size = f.stat().st_size; rng = self.headers.get('Range', ''); a, b = 0, size - 1
        if rng.startswith('bytes='):
            x, _, y = rng[6:].partition('-'); a = int(x) if x else max(0, size - int(y)); b = int(y) if x and y else size - 1
        b = min(b, size - 1); n = b - a + 1
        self.send_response(206 if rng else 200); self.send_header('Content-Type', TYPES.get(f.suffix.lower(), 'application/octet-stream'))
        self.send_header('Accept-Ranges', 'bytes'); self.send_header('Content-Length', str(n)); self.send_header('Cache-Control', 'no-cache' if f.suffix == '.html' else 'max-age=3600')
        if rng: self.send_header('Content-Range', f'bytes {a}-{b}/{size}')
        self.end_headers()
        try:
            with open(f, 'rb') as fh:
                fh.seek(a); left = n
                while left > 0:
                    chunk = fh.read(min(262144, left))
                    if not chunk: break
                    self.wfile.write(chunk); left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError): pass

    def do_GET(self):
        path, _, qs = self.path.partition('?'); q = dict(x.split('=', 1) for x in qs.split('&') if '=' in x)
        if not path.startswith('/api/'): return self.static(path)
        if path == '/api/ping': return self.out(200, {'ok': q.get('k') == TOKEN, 'model': MODEL, 'director': director.MODEL, 'vivix_balance': VIVIX['balance']})
        if q.get('k') != TOKEN: return self.out(403, {'err': 'bad token'})
        rid = path.rsplit('/', 1)[-1]
        if path.startswith('/api/round/') and rid in R:
            out = {k: v for k, v in R[rid].items() if k not in ('prompts', 'spec')}; out['state'] = (R[rid].get('spec') or {}).get('state')  # V3.2：换搭档时播放页把这一刻的状态带给另一条线
            out['segs'] = [dict(x, eta_left=seg_eta(R[rid], i)) for i, x in enumerate(R[rid].get('segs') or [])]  # V3.1：第 2 段排在第 1 段后面时按串行估（seg_eta）  # V1.5：播放页按它倒推第 1 段开播
            return self.out(200, out)
        if path.startswith('/api/round/') and re.fullmatch(r'L[0-9a-f]{9,}', rid) and (RD / f'{rid}.json').exists():  # 中转重启后内存里没有这一轮：按文件回，没做完的告诉页面重发，别让页面一直等
            try: rr = json.loads((RD / f'{rid}.json').read_text())
            except Exception: rr = {'id': rid}
            out = {k: v for k, v in rr.items() if k not in ('prompts', 'spec')}
            if rr.get('status') not in ('done', 'error'): out.update(status='error', err='中转刚才重启，这一轮中断了，请再发一次')
            return self.out(200, out)
        self.out(404, {'err': 'not found'})

    def do_POST(self):
        try: self._post()
        except Exception as e:  # V1.9：任何意外都回 JSON（连接断开时 Cloudflare 会回一页 HTML，页面报 Unexpected token '<'）
            log('POSTFAIL', self.path, repr(e)[:200])
            try: self.out(503, {'err': '服务暂时不可用，请再发一次'})
            except Exception: pass

    def _post(self):
        try: body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0)) or 0) or b'{}')
        except ValueError: return self.out(400, {'err': 'bad json'})
        if body.get('k') != TOKEN: return self.out(403, {'err': 'bad token'})
        if self.path == '/api/session':
            mode = body.get('mode', '5+10')
            if mode not in L.MODES and mode != 'auto': return self.out(400, {'err': 'bad mode'})
            s = new_session(mode); s['persona'] = str(body.get('persona') or '')[:1500] or None
            rc = str(body.get('recap') or '').strip()[:2000]
            if rc:  # V3.2：换搭档——从另一条线带着前情过来（三真四假重新配对仪式）。前情写进当前状态和剧情记录，已演过的关键片段卡照算
                s['state'] = rc; s['history'] = [{'input': '（换搭档之前的剧情）', 'kind': 'option', 'lines': [], 'did': rc, 'opts': [], 'place': s.get('place'), 'input_type': 'direction', 'delivered': True, 'span': max(1, min(20, int(body.get('rounds') or 1)))}]
                s['cards'] = [str(k).strip().upper() for k in (body.get('cards') or []) if re.fullmatch(r'K\d{2}', str(k).strip().upper())][:20]; s['recap'] = True
            return self.out(200, {'sid': s['sid'], 'next': s['next'], 'mode': mode})
        if self.path.startswith('/api/round/') and self.path.endswith('/view'):
            rid = self.path.split('/')[3]
            if rid not in R: return self.out(404, {'err': 'not found'})
            R[rid]['view'] = {k: body[k] for k in ('play_at', 'seg1_end', 'stall', 'end_at', 'buffer') if k in body}; save(rid)
            v = R[rid]['view']; log('VIEW', rid, 'send→play', round((v['play_at'] - R[rid]['at']) / 1000, 1) if v.get('play_at') else '没开播', 's', 'stall', v.get('stall'))
            return self.out(200, {'ok': True})
        if self.path != '/api/round': return self.out(404, {'err': 'not found'})
        s = S.get(body.get('sid')) or (restore_session(body.get('sid')) if body.get('sid') else None); kind = body.get('kind')
        if not s: return self.out(410, {'err': '会话已过期，请回到开场'})
        if kind == 'option':
            choice = body.get('choice')
            if choice not in ('A', 'B'): return self.out(400, {'err': 'bad choice'})
            text = s['next'][choice]['zh'] or s['next'][choice]['en']
        elif kind == 'free':
            choice = None; text = str(body.get('input', '')).strip()[:120]
            if not text: return self.out(400, {'err': 'empty input'})
        else: return self.out(400, {'err': 'bad kind'})
        with LOCK:
            if any(r['sid'] == s['sid'] and r['status'] in ('submitted', 'generating') for r in R.values()): return self.out(429, {'err': '上一轮还在生成'})
            if len(R) >= MAX_ROUNDS: return self.out(429, {'err': '本次测试轮数已满'})
            rid = 'L' + time.strftime('%H%M%S') + uuid.uuid4().hex[:3]
            R[rid] = {'id': rid, 'sid': s['sid'], 'round': s['round'] + 1, 'kind': kind, 'choice': choice, 'input': text, 'mode': s['mode'],
                      'director_kind': body.get('director_kind') if body.get('director_kind') in ('option', 'free') else None, 'replay_of': body.get('replay_of'),
                      'gen': s['gen'], 'options_shown': s['next'], 'at': now(), 'status': 'submitted'}; save(rid)
        log('REQ', rid, s['sid'], f"#{s['round'] + 1}", kind, choice or '', json.dumps(text, ensure_ascii=False))
        threading.Thread(target=worker, args=(rid,), daemon=True).start()
        self.out(200, {'id': rid})

    def log_message(self, *a): pass


if __name__ == '__main__':
    log('listening', PORT, 'model', MODEL, 'director', director.MODEL)
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
