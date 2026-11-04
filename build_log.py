"""《今天，再喜欢我一次》第三视角实时版 → 实时生成测试记录页（projects/realtime-drama-test-log）的“ROWAN · 第三视角”剧集，也是即兴剧场 APP 的案例回放。
复用 Magnus 第三视角 make_log_third.py / build_third_log.py 的拼接和卡片写法，只换开场、命名和参数；写 dramas/rafael-third.json，再按 id 合并进 data.js。
四个标记里“时延”自动算，另外三个来自审片记录 tests/review-<会话>.json。
用法：python3 build_log.py S2117451b6"""
import json, shutil, statistics as ST, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'magnus-third-live-v1'))
import make_log_third as ML

D = Path(__file__).resolve().parent
ML.D = D
SITE = ML.LOG
DID = 'meet-third'
OK_LAT = 90
SESSIONS = {'S2117451b6': ('案例 · 脚本模拟用户 · PE V2.9 · ultrafast · 15+15', 'case-v29-uf-15-15')}
BASE = dict(id=DID, title='ROWAN · 第三视角', sub='《今天，再喜欢我一次》开放式实时版 · 观众站在旁边看，画面里同时看到 Rowan 和她 · 开场是预制的院门初遇（38.6 秒），之后全部实时 · 界面、交互和通用 PE 与 Magnus、Rafael 第三视角一致', links=[], films=[], groups=[])


def M(ok, label, note): return [1 if ok else 0, label, note]


def with_bgm(r, files, pos):
    """V2.3 起配乐是播放时叠上去的（rt-player：循环，音量 0.3，同一首接着放）。成片和卡片要听到一样的，所以混进片段里。没有配乐的轮次原样返回。"""
    url = (r.get('mix') or {}).get('bgm')
    if not url: return files
    bank = D / 'review' / 'bgm'; bank.mkdir(parents=True, exist_ok=True)
    mp3 = bank / url.rsplit('/', 1)[1]
    if not mp3.exists(): ML.U.urlretrieve(url, mp3)
    length = ML.dur(mp3); out = []
    for i, f in enumerate(files):
        d = ML.dur(f); p = f.with_name(f.stem + '_mix.mp4'); start = pos.get(url, 0.0) % length
        if not p.exists():
            subprocess.run([ML.FF, '-v', 'error', '-y', '-i', str(f), '-stream_loop', '-1', '-ss', f'{start:.3f}', '-i', str(mp3), '-filter_complex',
                            '[1:a]volume=0.3[b];[0:a][b]amix=inputs=2:duration=first:normalize=0[a]', '-map', '0:v', '-map', '[a]', '-t', f'{d:.3f}',
                            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', str(p)], check=True)
        pos[url] = pos.get(url, 0.0) + d; out.append(p)
    return out


def seed_clips(sid, rs):
    """审片时 sheets.py 已下载过的片段直接拿来用，不再下载一次。"""
    (D / 'review' / 'clips').mkdir(parents=True, exist_ok=True)
    for n, r in enumerate(rs, 1):
        for i in (1, 2):
            a, b = D / 'review' / sid / f'R{n:02d}_{i}.mp4', D / 'review' / 'clips' / f"{r['id']}_{i}.mp4"
            if a.exists() and not b.exists(): shutil.copyfile(a, b)


def build_film(rs, tag):
    pos = {}
    open_mp4 = D / 'docs' / 'media' / 'OPEN.mp4'
    items, cues, chapters = [('v', open_mp4, ML.dur(open_mp4))], [], [['ep', '开场', 0.0]]
    for c in json.loads((D / 'docs' / 'open_cues.json').read_text(encoding='utf-8')):
        cues.append((c['s'], c['e'], f"{c['zh']}\n{c['en']}"))
    t = items[0][2]; prev_last = D / 'masters' / 'idle-key.jpg'
    for n, r in enumerate(rs, 1):
        raw = ML.seg_files(r); files = with_bgm(r, raw, pos); mode = r['mode']
        chapters.append(['rt', f'第 {n} 轮', round(t, 2)])
        items.append(('img', prev_last, ML.HOLD)); cues.append((t + 0.2, t + ML.HOLD, f"她：{r['input']}\n（实时生成 · {mode} · 第 {n} 轮）")); t += ML.HOLD
        for i, f in enumerate(files):
            d = ML.dur(f); items.append(('v', f, d)); cues += ML.seg_cues(r, i, t, d); t += d
        v, p = SITE / 'v' / f"{DID}-{r['id']}.mp4", SITE / 'v' / f"{DID}-{r['id']}.jpg"
        if not v.exists(): ML.encode([('v', f, ML.dur(f)) for f in files], v, crf='28')
        if not p.exists(): subprocess.run([ML.FF, '-v', 'error', '-y', '-ss', '1.5', '-i', str(files[0]), '-frames:v', '1', '-vf', 'scale=360:-2', '-q:v', '4', str(p)], check=True)
        prev_last = D / 'review' / 'clips' / f"{r['id']}_end.jpg"
        if not prev_last.exists(): subprocess.run([ML.FF, '-v', 'error', '-y', '-sseof', '-0.1', '-i', str(raw[1]), '-frames:v', '1', '-q:v', '2', str(prev_last)], check=True)
    out = SITE / 'film' / f'{DID}-{tag}.mp4'
    if not out.exists(): ML.encode(items, out)
    (SITE / 'film' / f'{DID}-{tag}.vtt').write_text('\n'.join(['WEBVTT', ''] + [f'{ML.ts(a)} --> {ML.ts(b)}\n{x}\n' for a, b, x in sorted(cues)]), encoding='utf-8')
    subprocess.run([ML.FF, '-v', 'error', '-y', '-i', str(D / 'docs' / 'media' / 'poster.jpg'), '-vf', 'scale=480:-2', '-q:v', '3', str(SITE / 'film' / f'{DID}-{tag}.jpg')], check=True)
    return dict(video=f'film/{DID}-{tag}.mp4', poster=f'film/{DID}-{tag}.jpg', vtt=f'film/{DID}-{tag}.vtt', duration=round(ML.dur(out), 1), chapters=chapters)


def card(n, r, rv):
    sp = r['spec']; mode = r['mode']; ready = [(s['ready_at'] - r['at']) / 1000 for s in r['segs']]; lat = max(ready)
    note = rv.get(str(n), {}); v = r.get('view') or {}
    play = (v['play_at'] - r['at']) / 1000 if v.get('play_at') else None
    if play is None:  # 脚本跑的案例没有播放页回报：按播放页的倒推规则估（第 1 段就绪后，等第 2 段离就绪不到 15 秒减 3 秒余量就开播）
        d1 = r['segs'][0].get('dur') or 15; play = max(ready[0], ready[1] - d1 + 3)
    marks = [M(note.get('err_ok', 1), '画面硬错误', note.get('err', '无')),
             M(note.get('free_ok', 1), '左右她', note.get('free', '跟着她的话走，没有替她做决定')),
             M(lat <= OK_LAT, '时延', f'发送到两段都就绪 {lat:.1f} 秒'),
             M(note.get('land_ok', 1), '那一下', note.get('land', sp.get('did') or ''))]
    stats = [['方案', mode], ['导演层', f"{r.get('director_sec') or 0:.1f}s" + ('（预先写好）' if r.get('director') == 'prefetched' else '')],
             ['第 1 段就绪', f'{ready[0]:.1f}s'], ['第 2 段就绪', f'{ready[1]:.1f}s']]
    if play is not None: stats += [['发送到开播' + ('' if v.get('play_at') else '（估算）'), f'{play:.1f}s'], ['接缝停顿', f"{v.get('stall') or 0:.1f}s"]]
    stats += [['判定', {'direction': '明确引导', 'question': '问答', 'vague': '模糊'}.get(sp.get('input_type'), '—')],
              ['关键剧情', '、'.join(sp.get('cards_done') or []) or '—'], ['地点', r.get('location') or '—']]
    lines = [b for k in ('seg1', 'seg2') for b in sp[k] if b[1]]
    zh = [z for k in ('seg1', 'seg2') for z in (sp.get('zh') or {}).get(k, []) if z]
    beats = [f"{b[2]}｜{b[0]}" for k in ('seg1', 'seg2') for b in sp[k]]
    nx = r.get('next') or sp.get('next') or {}
    c = dict(n=n, label=f"第 {n} 轮 · {'自由输入' if r['kind'] == 'free' else '点选项'} · {mode}", video=f"v/{DID}-{r['id']}.mp4", poster=f"v/{DID}-{r['id']}.jpg",
             her=r['input'], he=' '.join(b[1] for b in lines), he_zh=' '.join(zh), beat='；'.join(beats),
             rule=f"下一轮选项：A {nx.get('A', {}).get('zh', '')} ／ B {nx.get('B', {}).get('zh', '')}",
             stats=stats, marks=marks, job=' / '.join(s.get('job_id', '') for s in r['segs']))
    return c, lat, play, marks


def main(sid):
    rs = ML.rounds_of(sid); seed_clips(sid, rs)
    rv = json.loads((D / 'tests' / f'review-{sid}.json').read_text(encoding='utf-8'))
    rows = [card(n, r, rv) for n, r in enumerate(rs, 1)]
    lats = [x[1] for x in rows]; plays = [x[2] for x in rows]; n = len(rows); ok = [sum(x[3][k][0] for x in rows) for k in range(4)]
    opt = [x[2] for x, r in zip(rows, rs) if r['kind'] != 'free']; free = [x[2] for x, r in zip(rows, rs) if r['kind'] == 'free']
    places = []
    for r in rs:
        if r.get('location') and (not places or places[-1] != r['location']): places.append(r['location'])
    summary = [['轮数', str(n)], ['发送到两段都就绪 中位', f'{ST.median(lats):.1f} 秒'], ['范围', f'{min(lats):.1f}–{max(lats):.1f} 秒'], ['发送到开播 中位', f'{ST.median(plays):.1f} 秒'],
               ['无硬错误', f'{ok[0]}/{n}'], ['没有左右她', f'{ok[1]}/{n}'], ['那一下落到她', f'{ok[3]}/{n}'], ['演到的关键剧情', '—'], ['走过的地点', ' → '.join(places)]]
    meta = json.loads((D / 'tests' / f'log-meta-{sid}.json').read_text(encoding='utf-8'))
    note = meta['note'].format(play=ST.median(plays), opt=ST.median(opt), free=ST.median(free), hard=ok[0], freeok=ok[1], land=ok[3], n=n)
    title, tag = SESSIONS[sid]; info = build_film(rs, tag)
    g = dict(tab=title, title=f'{title}（{n} 轮）', when=time.strftime('%Y-%m-%d %H:%M', time.localtime(rs[0]['at'] / 1000)) + '–' + time.strftime('%H:%M', time.localtime(max(r['segs'][1]['ready_at'] for r in rs) / 1000)), note=note,
             params=meta['params'], summary=summary, cards=[x[0] for x in rows])
    film = dict(mode='15+15', title=f'完整成片 · {title}', desc=meta['desc'].format(n=n), stats=[summary[1], summary[2], summary[4], summary[7], summary[8]], **info)
    dp = SITE / 'dramas' / f'{DID}.json'; old = json.loads(dp.read_text(encoding='utf-8')) if dp.exists() else BASE
    drama = dict(old, films=[film] + [f for f in old['films'] if f['video'] != film['video']], groups=[g] + [x for x in old['groups'] if x['tab'] != title])  # 新的一次放最前面
    (SITE / 'dramas' / f'{DID}.json').write_text(json.dumps(drama, ensure_ascii=False, indent=1), encoding='utf-8')
    dj = SITE / 'data.js'; s = dj.read_text(encoding='utf-8'); log = json.loads(s[s.index('{'):s.rstrip().rstrip(';').rindex('}') + 1])
    ds = [d for d in log['dramas'] if d.get('id') != DID]
    i = next((k + 1 for k, d in enumerate(ds) if d.get('id') == 'rafael-third'), len(ds))
    log['dramas'] = ds[:i] + [drama] + ds[i:]; log['updated'] = time.strftime('%Y-%m-%d')
    dj.write_text('window.LOG = ' + json.dumps(log, ensure_ascii=False, indent=1) + ';\n', encoding='utf-8')
    print(note); print(summary); print(info['duration'], len(info['chapters']))


if __name__ == '__main__':
    main(sys.argv[1])
