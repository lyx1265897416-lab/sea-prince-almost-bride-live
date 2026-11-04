"""查叠化和色调突变：逐帧算相邻两帧的平均灰度差和平均色相/亮度。
硬切 = 单帧尖峰；叠化 = 连续 ≥4 帧的中等差值（每帧都在变、但都不是尖峰）；色调突变 = 镜头前后平均亮度或冷暖（R-B）跳变很大。
用法：python3 dissolve.py <mp4> [...]，输出每条的可疑段落。"""
import subprocess, sys
import numpy as np
import live_common as L


def frames(mp4, w=96, h=170):
    raw = subprocess.run([L.FFMPEG, '-v', 'error', '-i', mp4, '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.float32)


def scan(mp4, fps=24):
    f = frames(mp4); g = f.mean(axis=3)
    d = np.abs(g[1:] - g[:-1]).mean(axis=(1, 2))
    out = {'cuts': [], 'dissolves': [], 'tone_jumps': []}
    cut = d > 18
    out['cuts'] = [round((i + 1) / fps, 2) for i in np.where(cut)[0]]
    # 叠化：中间那帧≈前后两帧的平均（运动不满足这个关系）；前后两帧差别要大（换了画面）
    for k in (8, 12, 16):
        i = 0
        while i + k < len(f):
            a, b, m = g[i], g[i + k], g[i + k // 2]
            D = float(np.abs(a - b).mean())
            if D > 22:
                be = float(np.abs(m - (a + b) / 2).mean())
                if be < 0.3 * D and float(d[i:i + k].max()) < 18:
                    out['dissolves'].append((round(i / fps, 2), round((i + k) / fps, 2), round(D, 1), round(be, 1))); i += k; continue
            i += 2
    warm = (f[..., 0] - f[..., 2]).mean(axis=(1, 2)); lum = g.mean(axis=(1, 2))
    for t in out['cuts']:
        i = int(t * fps)
        a, b = slice(max(0, i - 6), i - 1), slice(i + 1, min(len(f), i + 7))
        if i > 6 and i + 7 < len(f):
            dw = abs(warm[b].mean() - warm[a].mean()); dl = abs(lum[b].mean() - lum[a].mean())
            if dw > 25 or dl > 45: out['tone_jumps'].append((t, round(float(dw), 1), round(float(dl), 1)))
    return out


if __name__ == '__main__':
    for m in sys.argv[1:]:
        r = scan(m)
        if r['dissolves'] or r['tone_jumps']: print(m.split('/')[-2:], r)
