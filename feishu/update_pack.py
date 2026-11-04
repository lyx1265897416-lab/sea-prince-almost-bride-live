"""更新飞书「角色样例」5️⃣ Rian Thalys 内容包（2026-11-04，开场外国人版 v9 确认 + 实时版上线）：
角色简介、开场白、视频效果（新开场、测试链接、实时版说明）、角色地图里斯凯、米拉、维萨的新形象图，“米粒”统一改“米拉”。
块 id 来自 11-04 fetch 的 rian_now.xml（这一节已被别的会话按 1️⃣ 版式重排过）。超时的请求往往已生效：任何错误都停下，先 fetch 核对再决定，不自动重试。
用法：python3 feishu/update_pack.py [--dry]"""
import json, subprocess, sys, time
from pathlib import Path
DOC = 'G4ojwsQrDiK3gikgYHUcv7y8nQc'; D = Path(__file__).resolve().parent; DRY = '--dry' in sys.argv
V = Path('/Users/vicky/Interactive storyline/projects/the-sea-princes-almost-bride/制作/新版互动剧集-v32/rto_openw/cues.json')
TOKEN = (D.parent / 'token.txt').read_text().strip()
PAGE = f'https://lyx1265897416-lab.github.io/sea-prince-almost-bride-live/?k={TOKEN}'
IMG = 'https://lyx1265897416-lab.github.io/sea-prince-almost-bride-live/feishu/'
OLD = 'https://lyx1265897416-lab.github.io/sea-prince-almost-bride/'
done = D / 'written.txt'; ok = set(done.read_text().split()) if done.exists() else set()


def e(t): return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
def p(i, inner): return f'<p id="{i}">{inner}</p>' if i else f'<p>{inner}</p>'
def a(u, t): return f'<a href="{e(u)}">{e(t)}</a>'
def img(f, cap, w, h): return f'<img width="{w}" height="{h}" caption="{e(cap)}" href="{IMG}{f}"/>'


WHO = {'SKY': '斯凯', 'MIL': '米拉', 'VES': '维萨', 'RIA': '雷恩'}
C = json.loads(V.read_text(encoding='utf-8'))
lines = '<br/>'.join(e(f"〔{c['s']:.1f}s〕{WHO[c['sp']]}：{c['en']}　{c['zh']}") for c in C['cues'])
OPEN = ('<pre id="doxcnx897qfpoh3s4wLC4u07HOc" caption="开场白｜外国人版 v9 确认版（71.9 秒）&#xA;" lang="Plain Text" wrap="true"><code>'
        + e('〔0.0s｜盐点港海岸 · 清晨 6:12〕礁石边的潮池泛着蓝绿色的光。米拉蹲在岩边举着相机，回头招呼斯凯过来看。') + '<br/>'
        + e('〔7.5s〕米拉低头拍照，脚下突然一滑掉进海里；斯凯同一瞬间扑过去，边抓边喊她的名字，没抓住，紧跟着一头扎进海里。') + '<br/>'
        + e('〔水下〕一条银蓝长尾掠过，戴银镯的手抓住她的手腕；银紫发丝在水里散开，他看清她还清醒，带她游向有光的水面。') + '<br/>'
        + e('〔潮门〕她破水而出、大口喘气，愣愣望着白色长阶和贝壳拱门，转身走上台阶。') + '<br/>'
        + e('〔东廊〕她边走边找米拉，摄政官维萨从柱后走出来拦住她；雷恩从蓝帘高门那边走来，停在她身旁，当着维萨说出那两句。') + '<br/><br/>'
        + lines + '<br/><br/>'
        + e('〔68–72s｜她的近景〕开场停在斯凯抬头看着他的近景：疑惑，但眼神柔和，把湿发别到耳后。') + '<br/><br/>'
        + e('〔交互开始〕先配合他，找朋友要紧／当场反问：谁是你的新娘？；也可以直接打字，替她说一句话或做一个动作。') + '</code></pre>')
EDITS = [
 ('intro', 'block_replace', 'doxcnnqt6btSq4FyPkRf8a3WQjs', p('', e('你是斯凯 Skye，22 岁的海岸潜水向导学员，橙红色披散长发、蓝灰色眼睛（2026-11-04 外国人版形象）。好友米拉在礁石边失足落海，你跟着跳下去，被人鱼王子雷恩救进海下王宫；摄政官维萨不放外人进来，他当着她说你是“我未来的新娘”。你可以先配合，也可以当场拆穿。无论如何，先找朋友、拿到通行证，再决定这场戏演多久。'))),
 ('opening', 'block_replace', 'doxcnx897qfpoh3s4wLC4u07HOc', OPEN),
 ('links', 'block_replace', 'doxcnUJaq80MsFLJu4GQlYAvgR6', p('', '体验🔗：' + a(PAGE + '&lang=zh', '中文测试链接') + '｜' + a(PAGE + '&lang=en', '英文测试链接') + e('（第三视角实时版：开场之后全部实时生成；链接里的口令用来调用生成，只内部发。需要这台 Mac 开着）'))),
 ('note', 'block_replace', 'doxcnAtXqAqf1RNBNFEtTtzjOo6', p('', e('实时版 2026-11-04 上线：开场为外国人版 v9 确认版（71.9 秒），之后接第三视角共用 PE（Vivix，auto 优先 15+15，内容轻就 5+15/5+10），本剧只提供资料包（K01–K12）、人物、地点空景和时间线。冒烟 3 轮（先配合／当场反问／自由输入“你为什么说我是你的新娘”），每轮 2–3 分钟出片，过关、维萨放行、会客厅和米拉重逢都演到了。已知问题：偶尔一段末尾两人左右站位对调；还没进测试记录页和即兴剧场 APP。原版女主 POV 前五集互动版：') + a(OLD, '《人鱼王子的假新娘》前五集互动版'))),
 ('opencell', 'block_replace', 'doxcnHctfI8C1uP3KaG4BWuYKMh', p('', '<b>开场确认版｜外国人版 v9｜71.9 秒</b>') + p('', '〔视频占位 rian-opening〕') + p('', e('潮池发光 → 米拉失足落海，斯凯边喊边扑下去 → 水下被雷恩救起 → 潮门破水而出 → 东廊被维萨拦下 → “She is with me. My future bride.” → 停在斯凯的近景。'))),
 ('oldclips', 'block_delete', 'doxcn7rtpwh92m1Yh5LjSQw7vlh,doxcnZSNoNi5seGBS44JDFO8RuG,doxcnzshAJwXNWaTvA0yXsYOs0c', None),
 ('boundary', 'block_replace', 'doxcnfO76lfsUIUpABXJ1wqwiIe', p('', e('视频制作说明：开场用 Seedance 2.5（720p，9:16）原生演出，对白是模型原声；首帧用 gpt-image-2/edit 按定装图出，海下王宫统一低调电影感光影（按脸定曝光、烛光加水光勾边），相邻镜头按亮度对齐；连续动作用 video-extend 一镜到底，不从中间硬切。字幕和地点字卡不烧进画面，中英由页面显示。关键情节视频和状态参考视频两格仍是原版 POV 前五集的片段，作为人物和场景参考。'))),
 ('sky-img', 'block_replace', 'doxcnnGXKH1GnsVhfWHUXrM2zFd', img('sky-master.jpg', 'Skye｜斯凯 · 外国人版定装（SKYW6，五官按 Vicky 给的参考图）', 100, 178)),
 ('sky-txt', 'block_replace', 'doxcnpxR9WQ3wk43enkp6BQ5cHc', p('', e('22 岁女主；橙红色披散长发、左侧银月牙发夹、银圈耳环、蓝灰色眼睛；浅长春花蓝泡泡袖衬衫、细黑皮带、炭灰格纹阔腿裤、奶油色短靴。'))),
 ('sky-full', 'block_replace', 'doxcnDhPYV1CAQRFqdTIX8QYS5e', img('sky-full.jpg', 'Skye｜单人全身（实时版 look_she_on）', 110, 255)),
 ('mila-name', 'block_replace', 'doxcnhotZIsSOJjEdZnRc815jhb', p('', 'Mila｜米拉')),
 ('mila-img', 'block_replace', 'doxcnul3EDTB0oNK2q82udYzmqc', img('mila-face.jpg', 'Mila｜米拉 · 外国人版面部定装（MILWF）', 100, 178)),
 ('mila-txt', 'block_replace', 'doxcnKKzp9tuRLTk4QPpCt35ckl', p('', e('21 岁好友；蜜金色卷发高马尾、雀斑、蓝眼睛、芥末黄连帽外套、石板蓝 T 恤、灰色工装裤。实时版母版不带相机（相机被王宫收走，归还时再作为道具出现）。'))),
 ('mila-full', 'block_replace', 'doxcn2BYj6PEOfEnahhPrnZpDNd', img('mila-full.jpg', 'Mila｜单人全身（实时版配角母版）', 110, 196)),
 ('vessa-full', 'block_replace', 'doxcnhG84bnMg7phEvHkCJ2KCKb', img('vessa-full.jpg', 'Vessa｜单人全身（实时版配角母版）', 110, 196)),
]


def run(*a, inp=None):
    return subprocess.run(['lark-cli', 'docs', *a, '--doc', DOC], input=inp, capture_output=True, text=True, timeout=280)


for name, cmd, bid, content in EDITS:
    if name in ok: continue
    if DRY: print(name, cmd, bid, (content or '')[:160]); continue
    t0 = time.time()
    r = run('+update', '--command', cmd, '--block-id', bid, *(['--content', '-'] if content else []), inp=content)
    try: good = r.returncode == 0 and json.loads(r.stdout).get('ok')
    except Exception: good = False
    print(name, r.returncode, round(time.time() - t0, 1), (r.stdout[:160] + r.stderr[:200]).replace('\n', ' '), flush=True)
    if not good: print('STOP at', name); sys.exit(1)
    ok.add(name); done.write_text('\n'.join(sorted(ok)))
for pat, rep, name in (('米粒', '米拉', 'rename'), ('文档统一用“米拉”，早期稿“米拉”和会话“米莉”指同一人', '文档统一用“米拉”（2026-11-04 外国人版起；更早的稿子写“米粒”），会话里的“米莉”也指同一人', 'rename-note')):
    if name in ok or DRY: continue
    r = run('+update', '--command', 'str_replace', '--pattern', pat, '--content', rep)
    print(name, r.returncode, (r.stdout[:160] + r.stderr[:200]).replace('\n', ' '), flush=True)
    if r.returncode: print('STOP at', name); sys.exit(1)
    ok.add(name); done.write_text('\n'.join(sorted(ok)))
print('done')
