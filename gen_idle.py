"""待机循环：开场末帧（WS25e 结尾）用 Seedance 2.5 只给首帧生成 5 秒几乎不动的画面（制作/新版互动剧集-v32/rtow.py 的 RT_idle），取前 3.6 秒正放 + 倒放拼成无缝循环。"""
import subprocess
from pathlib import Path
D = Path(__file__).resolve().parent
SRC = Path('/Users/vicky/Interactive storyline/projects/the-sea-princes-almost-bride/制作/新版互动剧集-v32/results/RT_idle-clip.mp4')
FF = '/Users/vicky/Interactive storyline/.media-runtime/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1'
subprocess.run([FF, '-y', '-v', 'error', '-i', str(SRC), '-filter_complex', '[0:v]trim=0:3.6,setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=24,split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,format=yuv420p[v]',
                '-map', '[v]', '-an', '-c:v', 'libx264', '-crf', '19', '-movflags', '+faststart', str(D / 'docs/media/IDLE0.mp4')], check=True)
print('idle ok')
