"""把 chunks/*.xml 插到 6️⃣ Lena 包最后一个空行之后。倒序插（07 先、01 最后），每块都插在同一个锚点后面，结果就是 01→07 的顺序，不依赖新块的 id，也不怕别的会话在文末追加。
超时的请求往往已生效，所以任何错误都停下来，先 fetch 核对再决定，不自动重试。"""
import json, subprocess, sys, time
from pathlib import Path
DOC = 'G4ojwsQrDiK3gikgYHUcv7y8nQc'; D = Path(__file__).resolve().parent
ANCHOR = 'doxcnwVKVLw0BWnbS2LL1vHlggf'  # 6️⃣ Lena 包末尾第二个空段落（2026-11-03 fetch 确认）
done = D / 'written.txt'; ok = set(done.read_text().split()) if done.exists() else set()
for f in sorted((D / 'chunks').glob('*.xml'), reverse=True):
    if f.stem in ok: continue
    c = f.read_text(encoding='utf-8'); t0 = time.time()
    r = subprocess.run(['lark-cli', 'docs', '+update', '--doc', DOC, '--command', 'block_insert_after', '--block-id', ANCHOR, '--content', '-'], input=c, capture_output=True, text=True, timeout=280)
    print(f.stem, r.returncode, round(time.time() - t0, 1), (r.stdout[:220] + r.stderr[:300]).replace('\n', ' '), flush=True)
    try: good = r.returncode == 0 and json.loads(r.stdout).get('ok')
    except Exception: good = False
    if not good: print('STOP at', f.stem); sys.exit(1)
    ok.add(f.stem); done.write_text('\n'.join(sorted(ok)))
print('all written')
