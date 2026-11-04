"""一键补跑：把某个人工测试会话里观众每一轮的原话，按顺序用另一种时长（默认 10+10）重放一遍，只算生成时间。
新开一个会话，从开场后的第一个选择点开始；每轮等上一轮两段都好、下一轮首帧准备好再发下一句，所以剧情也会一路接着演。
观众原来点的是选项的，导演层仍按“她点了选项”理解（director_kind=option），但选项文字原样作为她这一轮的话。
用法：python3 replay.py <原会话 sid> [10+10]      结果写 rounds/，汇总写 replays/<新会话>.json"""
import json, sys, time
from pathlib import Path
from urllib import request as U

D = Path(__file__).resolve().parent
K = (D / 'token.txt').read_text().strip(); API = 'http://127.0.0.1:8901'


def call(path, body=None):
    req = U.Request(API + path, data=json.dumps(dict(body, k=K)).encode() if body is not None else None,
                    headers={'Content-Type': 'application/json'}, method='POST' if body is not None else 'GET')
    with U.urlopen(req, timeout=30) as r: return json.loads(r.read())


def main():
    src, mode = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else '10+10')
    rounds = []
    for f in (D / 'rounds').glob('L*.json'):
        r = json.loads(f.read_text())
        if r.get('sid') == src and r.get('status') == 'done' and not r.get('replay_of'): rounds.append(r)
    rounds.sort(key=lambda r: r['at'])
    if not rounds: sys.exit(f'会话 {src} 没有已完成的轮次')
    print(f'原会话 {src}：{len(rounds)} 轮 → 用 {mode} 重放', flush=True)
    out = []; start = 1
    if '--session' in sys.argv:  # 接着一个已有会话往下跑：--session <sid> --from <轮次>（中转内存里这个会话还在）
        sid = sys.argv[sys.argv.index('--session') + 1]; start = int(sys.argv[sys.argv.index('--from') + 1])
        old = D / 'replays' / f'{sid}.json'
        if old.exists(): out = [x for x in json.loads(old.read_text())['rounds'] if x['n'] < start]
    else: sid = call('/api/session', {'mode': mode})['sid']
    for i, r0 in enumerate(rounds, 1):
        if i < start: continue
        for attempt in range(4):  # Vivix generation_failed（服务端失败、任务已结束）：等 90 秒重发同一句
          for _ in range(120):  # 等中转空闲
            try:
                rid = call('/api/round', {'sid': sid, 'kind': 'free', 'input': r0['input'], 'director_kind': r0['kind'], 'replay_of': r0['id']})['id']; break
            except Exception as e:
                if '429' not in str(e) and 'HTTP Error 429' not in str(e): raise
                time.sleep(3)
          while True:
            time.sleep(2); r = call(f'/api/round/{rid}?k={K}')
            if r['status'] in ('done', 'error'): break
          errs = ' '.join([str(r.get('err') or '')] + [str(x.get('err') or '') for x in (r.get('segs') or [])])
          if r['status'] == 'done' or 'generation_failed' not in errs or attempt == 3: break
          print(f'第 {i} 轮 {rid} 服务端失败（generation_failed），90 秒后重发同一句', flush=True); time.sleep(90)
        segs = r.get('segs') or []
        ready = [round((s['ready_at'] - r['director_at']) / 1000, 1) for s in segs if s.get('ready_at') and r.get('director_at')]
        row = {'n': i, 'input': r0['input'], 'kind': r0['kind'], 'orig': r0['id'], 'replay': rid, 'status': r['status'],
               'director': r.get('director_sec'), 'seg_ready': ready, 'all_ready': max(ready) if ready else None,
               'orig_all_ready': max(round((s['ready_at'] - r0['director_at']) / 1000, 1) for s in r0['segs'])}
        out.append(row); print(json.dumps(row, ensure_ascii=False), flush=True)
        (D / 'replays').mkdir(exist_ok=True)
        (D / 'replays' / f'{sid}.json').write_text(json.dumps({'source': src, 'mode': mode, 'session': sid, 'rounds': out}, ensure_ascii=False, indent=1))
        if r['status'] != 'done': print('这一轮失败，停止重放', flush=True); break
        time.sleep(15)  # 等下一轮首帧准备好（中转里也会再等）
    print('完成', sid, flush=True)


if __name__ == '__main__':
    main()
