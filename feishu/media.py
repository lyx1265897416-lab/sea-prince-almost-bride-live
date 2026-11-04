"""把视频、样音、配乐、资料包压缩包插进 7️⃣ 的占位段落所在单元格：media-insert 会把文件块插到表格后面的根层级，再 block_move_after 移到占位段落后面，最后删占位段落。
只认本包自己的占位名，已插过的（占位已删）自动跳过。"""
import json, re, subprocess
from pathlib import Path
DOC = 'G4ojwsQrDiK3gikgYHUcv7y8nQc'; D = Path(__file__).resolve().parent
FILES = {'meet-opening': ('视频', 'MMA3P_OPENING_确认版_720p.mp4', 'preview'), 'voice-rowan-R1': ('音频', 'voice-rowan-R1.mp3', 'preview'),
         'voice-maisie-W2': ('音频', 'voice-maisie-W2.mp3', 'preview'), 'bgm-daylight': ('音频', 'bgm-daylight.mp3', 'preview'), 'meet-pack': ('附件', 'meet-pack.zip', 'card')}
def run(*a, t=280):
    return subprocess.run(['lark-cli', 'docs', *a, '--doc', DOC], capture_output=True, text=True, timeout=t, cwd=D)
c = json.loads(run('+fetch', '--scope', 'keyword', '--keyword', '|'.join(f'占位 {n}' for n in FILES), '--detail', 'with-ids').stdout)['data']['document']['content']
ph = {m.group(2): m.group(1) for m in re.finditer(r'<p id="([^"]+)">〔(?:视频|音频|附件)占位 ([^〕]+)〕</p>', c) if m.group(2) in FILES}; print(ph)
moved = []
for name, pid in ph.items():
    kind, f, view = FILES[name]
    r = run('+media-insert', '--type', 'file', '--file-view', view, '--file', f, '--selection-with-ellipsis', f'〔{kind}占位 {name}〕', t=400)
    i = r.stdout.find('{'); j = json.loads(r.stdout[i:]); assert j.get('ok'), r.stdout[-300:] + r.stderr[-300:]
    bid = j['data']['block_id']; print(name, 'inserted', bid, flush=True)
    r = run('+update', '--command', 'block_move_after', '--block-id', pid, '--src-block-ids', bid); assert json.loads(r.stdout).get('ok'), r.stdout[-300:]
    moved.append(pid)
if moved:
    r = run('+update', '--command', 'block_delete', '--block-id', ','.join(moved)); print('delete', json.loads(r.stdout).get('ok'), r.stdout[:120].replace('\n', ' '))
