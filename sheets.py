"""审片联系表：一个会话的每一轮，两段视频各按每 0.5 秒抽一帧拼成一张图（review/<会话>/R<轮>.jpg），同时把两段下载到 review/<会话>/。
用法：python3 sheets.py <会话sid>"""
import json, subprocess, sys
from pathlib import Path
from urllib import request as U
import live_common as L

D = Path(__file__).resolve().parent


def rounds(sid):
    out = [json.loads(f.read_text()) for f in (D / 'rounds').glob('L*.json')]
    out = [r for r in out if r.get('sid') == sid and r.get('status') == 'done']
    return sorted(out, key=lambda r: r['at'])


def main(sid):
    od = D / 'review' / sid; od.mkdir(parents=True, exist_ok=True)
    for n, r in enumerate(rounds(sid), 1):
        sheet = od / f'R{n:02d}.jpg'
        if sheet.exists(): continue
        parts = []
        for i, s in enumerate(r['segs'], 1):
            mp4 = od / f'R{n:02d}_{i}.mp4'
            if not mp4.exists(): U.urlretrieve(s['url'], mp4)
            png = od / f'R{n:02d}_{i}.png'
            rows = max(1, round(s['dur'] / 5))  # 每行 10 帧 = 5 秒；写死 2 行会漏掉 15 秒段的最后 5 秒
            subprocess.run([L.FFMPEG, '-v', 'error', '-y', '-i', str(mp4), '-vf', f'fps=2,scale=144:-2,tile=10x{rows}', '-frames:v', '1', str(png)], check=True)
            parts.append(png)
        subprocess.run([L.FFMPEG, '-v', 'error', '-y', *sum([['-i', str(p)] for p in parts], []), '-filter_complex', f'vstack=inputs={len(parts)}', '-q:v', '3', str(sheet)], check=True)
        print(n, r['id'], r['input'][:30], sheet.name, flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
