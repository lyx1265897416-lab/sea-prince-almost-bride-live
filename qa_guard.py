"""末帧质检与修复（第三视角：画面里同时有 Rian 和她，两人都对照身份母版）：上一轮的末帧要当下一轮的首帧，一旦走样（多了人、换装、换脸）就会一路传下去。
check(jpg) 用视觉模型按锁定项检查，返回 {ok, issues:[...]}；fix(url, issues) 用 nano-banana-pro/edit 参考身份母版把这一帧修干净，返回新图地址。
都在观众看视频、做选择的时候后台完成，不增加等待。"""
import base64, json, re, subprocess, time
from pathlib import Path
from urllib import request as U
import director, live_common as _L

VLM = 'anthropic/claude-sonnet-5.5'
FACE_URL = _L.TU['face']  # 白底正面头像身份母版
OUTFIT_URL = _L.TU['outfit']  # 裁成上半身（全身站姿的母版会把画面往全身拉）

HE_HEAD = _L.TU.get('face_head') or _L.TU['face']  # V2.0：只有头和脖子，穿着不是默认时用，T 恤不会被带回来
HER_HEAD = _L.TU.get('her_head') or _L.TU['her']
HER_URL = _L.TU['her']  # 她：正面头像 + 全身正面 + 多角度合图

CHECK = """图片1是一部观众第三视角互动剧的一帧画面：画面里应该同时有男主 Rian 和女主（她），Rian 在画面左侧、她在画面右侧。图片2是男主的身份母版，图片3是女主的身份母版（判断是不是同一个人以它们为准）。下一段视频会从这一帧接着生成，所以这一帧必须干净。请按下面的锁定项检查，只报你在画面上确实看到的问题：
1. 画面里除了男主、女主{allowed}还有没有其他人（路人、背影、人影、半透明人头）？同一个人出现两次也算。
2. 女主在不在画面里、脸能不能看清？女主长相和图片3比是不是明显换了人（脸型、五官、眼睛、年龄、变得幼态）？她应为：西方人长相、白皙瓷肤、蓝灰色眼睛、橙红色披散长发和左侧银月牙发夹、银圈耳环；浅长春花蓝泡泡袖衬衫、细黑皮带、炭灰格纹阔腿裤。发色变成黑色、棕色或金黄色、头发变短或扎起、衬衫换了颜色款式、长裤换成裙子，都算问题（kind=her）。
3. 男主服装：在陆地上应为半透明珍珠白长披袍（左肩月牙胸针、胸前珍珠链）和象牙白灯笼裤；在水里是浅长春花蓝长尾。披袍变成不透明的白袍、短上衣、系腰带，裤子变成修身西裤或牛仔裤，或同时有腿又有尾巴，算问题。
4. 男主配饰：只有耳朵的珍珠和冰蓝水滴耳坠、蓝水滴吊坠、左手腕细银镯、上臂银臂环。多出纹身、戒指、手表算问题（kind=accessory）。
5. 男主瞳色：应为淡紫灰色。变成金色、红色、发光算问题。（看不到眼睛就不报）
6. 男主长相：和图片2比，是不是明显换了人（脸型、五官、年龄、肤色不同）、变老、变成方下巴、长出胡茬、头发变短变黑、耳鳍不见了？
7. 有没有可读的文字、乱码、手机界面、图标、招牌字样？门、墙面、纸张、衣服上有没有徽章、品牌标志、字母？
8. 有没有明显崩坏（手指粘连、多指、两人肢体粘连穿插、肢体变形、皮肤异常老化起皱、画面撕裂）？
9. 光线：人物肤色明显偏橙、偏黄或发灰，画面整体过暗看不清脸、或过曝发白、低饱和发灰，算问题（kind=light，level=low）。
10. 女主的手（能看到时）：纤细白皙、短而圆的裸色素甲、手上没有任何首饰。有没有涂指甲油、美甲、长尖指甲、戒指、手链、手表？
10b. 画面里有没有不合常理的道具：悬空的物件、拿反的杯子、东西放在不合理的位置（人身上、半空）、同一件东西重复出现？（kind=prop）
11. 配角（只在画面里有配角时检查）：维萨（银紫编发、蓝耳鳍、梅紫长袍）、米拉（金色卷发高马尾、雀斑、芥末黄外套）的长相和衣着是不是和她们平时的样子明显不同？
12. 背景：人物身后是不是变成了灰色或白色影棚幕布、平整的纯色背景，没有任何景物？是就算问题（kind=scene）。背景虚化、但还看得出灯光、窗户、家具的不算。
13. 站位：Rian 是不是跑到了画面右侧、她在左侧（左右对调）？是就算问题（kind=staging）。
14. 构图：两人里有没有谁的脸被画面边缘切掉一部分、或只露出后脑勺和背影？是就算问题（kind=framing）。
{side_rule}每个问题标类别 kind：people（多了人）、her（女主不在画面、换了人、发型服装不对）、outfit（男主服装）、accessory（男主多了纹身首饰）、face（男主换了人、明显变老、发型变了）、herhand（她的手：指甲油、美甲、首饰）、cast（配角不对）、eyes（瞳色、发光）、skin（皮肤粗糙、皱纹、油亮）、text（文字、手机界面）、broken（崩坏）、light（肤色和光线不对）、scene（背景变成影棚或纯色）、staging（左右对调、并排坐时正对镜头）、framing（有人的脸被画面边缘切掉、只露背影）、prop（道具不合常理）。
每个问题标级别：high = 第 1、2、3、7、8、10、11、12、13、14 项里的任何一条、明显换了人；low = 瞳色只是略偏、几缕头发略乱、她的表情略僵、光线略偏之类的小偏差。
另外报告：能不能看到男主的脸（face）、女主在不在画面里且能看到她的脸（her），以及男主脸部（额头到下巴、两耳之间）在画面里的位置 face_box = [左, 上, 右, 下]，用 0–1 的比例（看不到脸写 null）。
只输出一个 JSON：{"ok": true/false, "face": true/false, "her": true/false, "face_box": [0.1, 0.2, 0.35, 0.4], "issues": [{"text": "简短中文描述，可直接写进修图指令", "kind": "类别", "level": "high" 或 "low"}, ...]}；没有问题就 {"ok": true, "face": ..., "her": ..., "issues": []}。"""


NO_FIX = {'eyes', 'skin', 'face'}  # 第三视角 v1：light（白天）改成必须修好才出发——5+10 第 1 段从末帧续接，白天会直接带进下一轮（第 11→12 轮）  # face（偏老、发型乱）也交给第 2 段身份母版：5+10 测试里这类修图 3 次都因为把背景换掉被退回，白等 1–2 分钟  # 这两类交给第 2 段的身份母版纠正，不为它们修图（修图慢，还可能把背景换掉）
SCENE_DIFF_MAX = 20  # 修图前后画面四周（背景）的平均灰度差，超过就认为修图把背景、构图换掉了


SIDE_RULE = '15. 站位（这一刻两人并排坐着）：两人应并排坐、身体侧过来朝向对方，Rian 在左、她在右。是不是变成面对面坐、或者两人都正对镜头像证件照？是就算问题（kind=staging）。\n'


def check(jpg, timeout=60, cast=(), side=False, worn=(), state=''):
    b64 = base64.b64encode(open(jpg, 'rb').read()).decode()
    body = {'model': VLM, 'max_tokens': 1200, 'reasoning': {'effort': 'low'},
            'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': (('这一刻的真实状态（穿着按它判，优先于下面写的默认服装）：' + state + '。只有画面和它明确矛盾才算问题（脱掉的衣服又穿在身上、该穿着的外套不见了或换了款、该躺着却站着、该在车上却不在），kind=state，level=high；画面里看不到的部位、手里的小东西、脚下的细节都不算。\n') if state else '') + (('剧情里披在她身上的：' + '、'.join(worn) + '（披在她的衬衫外面，这是允许的，不算换装）。\n') if worn else '') + CHECK.replace('{allowed}', ('和' + '、'.join(cast) + '（允许出镜的配角）') if cast else '').replace('{side_rule}', SIDE_RULE if side else '')},
                                                      {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
                                                      {'type': 'image_url', 'image_url': {'url': FACE_URL}},
                                                      {'type': 'image_url', 'image_url': {'url': HER_URL}}]}]}
    t0 = time.time()
    req = U.Request('https://openrouter.ai/api/v1/chat/completions', data=json.dumps(body).encode(),
                    headers={'Authorization': 'Bearer ' + director._key(), 'Content-Type': 'application/json'})
    with U.urlopen(req, timeout=timeout) as r: j = json.loads(r.read())
    txt = j['choices'][0]['message'].get('content') or ''
    m = re.search(r'\{.*\}', txt, re.S)
    res = json.loads(m.group(0)) if m else {'ok': True, 'issues': [], 'raw': txt[:200]}
    res['sec'] = round(time.time() - t0, 1)
    return res


def _edit(prompt, images, timeout):
    params = {'prompt': prompt, 'images': images, 'aspect_ratio': '9:16', 'resolution': '1k', 'output_format': 'jpeg'}
    r = subprocess.run(['waku', 'gen', 'run', 'google/nano-banana-pro/edit', '--capability', 'multimodal.generate.image', '--params', json.dumps(params)],
                       capture_output=True, text=True, timeout=timeout)
    m = re.search(r'\{.*\}', r.stdout, re.S)
    j = json.loads(m.group(0)) if m else {}
    if not j.get('asset_url') and j.get('job_id'):  # 偶尔先返回 pending：按 job_id 等结果，不重复提交
        r = subprocess.run(['waku', 'gen', 'result', j['job_id'], '--wait', '--timeout', '180'], capture_output=True, text=True, timeout=timeout)
        m = re.search(r'\{.*\}', r.stdout, re.S); j = json.loads(m.group(0)) if m else {}
    if not j.get('asset_url'): raise RuntimeError('修图没有返回地址：' + (r.stdout[-200:] or r.stderr[-200:]))
    return j['asset_url']


KEY_ALT = 'google/gemini-2.5-flash-image'  # 2026-11-02 实测 20 秒、$0.039
KEY_MODEL = 'google/gemini-3.1-flash-lite-image'  # 2026-11-01 实测：同一条指令 22.8 秒、约 $0.035；Waku 通道排队时 65–120 秒，等不起


ANCHOR_DIFF_BOTH = 50  # V2.4：两人都在画面里时回正不该改构图；第 13–17 轮差 87–107 的回正把坐着改成站着、多画出摩托，全被放行
ANCHOR_DIFF_MAX = 120  # 回正可以改构图（末帧是吻戏近景时回正会拉远，第 11–14 轮差 86–98 被拒，长相衣服又漂了），差到这个程度才是换了地点


def key_frame(prompt, images, out, timeout=45, hedge=3):
    """V2.0：状态关键帧（第 2 段第一张画面），写到本地文件 out。V2.2：同时发两个请求，先回来的用（单次 13–56 秒，抖动大），不再退回 Waku（曾一次等 195 秒）；都失败就抛错，这一轮按没有关键帧走。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    def one(i):
        body = {'model': KEY_ALT if i == 1 else KEY_MODEL, 'modalities': ['image', 'text'], 'image_config': {'aspect_ratio': '9:16'}, 'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}] + [{'type': 'image_url', 'image_url': {'url': u}} for u in images]}]}  # V2.4：第 2 个请求换模型（回归 R2 同一模型 3 个请求一起排队，47 秒全超时，这一轮穿着和姿态全错）
        req = U.Request('https://openrouter.ai/api/v1/chat/completions', data=json.dumps(body).encode(), headers={'Authorization': 'Bearer ' + director._key(), 'Content-Type': 'application/json'})
        with U.urlopen(req, timeout=timeout) as r: j = json.loads(r.read())
        u = ((j['choices'][0]['message'].get('images') or [{}])[0].get('image_url') or {}).get('url') or ''
        if not u.startswith('data:'): raise RuntimeError('没有返回图片')
        return base64.b64decode(u.split(',', 1)[1])
    ex = ThreadPoolExecutor(hedge); err = None
    try:
        for f in as_completed([ex.submit(one, i) for i in range(hedge)], timeout=timeout + 2):
            try:
                import io
                from PIL import Image
                Image.open(io.BytesIO(f.result())).convert('RGB').save(out, 'JPEG', quality=93)  # V2.6：备用模型返回 PNG，存成 .jpg 上传 Vivix 报 20008，这一轮关键帧作废
                return 'openrouter'
            except Exception as e: err = e
    except Exception as e: err = e
    finally: ex.shutdown(wait=False)
    raise RuntimeError('关键帧失败：' + str(err)[:160])


def fix_state(frame_url, issues, state, timeout=120):
    """V2.0：穿着不是默认时，按这一刻真实的穿着和姿态修（默认的 fix 会把脱掉的衣服修回去）。"""
    prompt = ('Edit Image 1 minimally. Fix only these problems (Chinese): ' + '；'.join(issues) + '。 The state of this moment (Chinese): ' + state + '。 '
              'Keep everything else pixel-faithful: background, location, lighting, camera angle, crop, both people\'s positions and expressions. Image 2 is only the man\'s face and hair reference, Image 3 is only the woman\'s face and hair reference. Do not add clothes that are not in the state. No readable text. Same refined 3D romance-game CG character rendering.')
    return _edit(prompt, [frame_url, HE_HEAD, HER_HEAD], timeout)


def fix_scene(frame_url, set_text, timeout=240):
    """背景变成灰色影棚或纯色时，只把背景换回这个地点。第三视角：两个人都保持原样。"""
    prompt = ('Edit Image 1: replace only the background. Behind the two people, the grey studio or plain backdrop becomes this real location, at the time of day it describes: ' + set_text + '. '
              'Keep both people exactly as they are in Image 1: the man on the left and the woman on the right, the same faces, hair, clothes, poses, expressions, head sizes and positions, camera angle and crop. '
              'Use Image 2 only as the reference for the man\'s face and Image 3 only as the reference for the woman\'s face. Only these two people are in the picture. No readable text, no logos. Same refined 3D romance-game CG character render style as the people in Image 1.')
    return _edit(prompt, [frame_url, FACE_URL, HER_URL], timeout)


def fix(frame_url, issues, timeout=240, keep_hands=False, worn=()):
    """第三视角：用两人的身份母版和他的服装母版把这一帧修干净：构图、地点、光线、景别、两人的姿势都保持不变，只改掉问题。"""
    prompt = ('Edit Image 1 minimally. Fix only these problems: ' + '；'.join(issues) + '。 '
              'Keep everything else in Image 1 pixel-faithful: the same background, location, lighting, camera angle, shot size, crop, both people\'s head sizes and positions, poses and expressions. '
              'There are exactly two people: the man (Rian) on the left side of the picture and the woman on the right side. '
              'Use Image 2 only as the reference for the man\'s face, long messy silver-lilac hair, large blue-violet fin ears and lavender-grey eyes. His outfit: a sheer ivory iridescent lace robe gathered on his left shoulder under a silver crescent-moon brooch, strands of pearls and ice-blue beads, the other shoulder bare, loose ivory harem trousers; a thin silver bangle on his left wrist; no tattoos, no rings, no watch. '
              'Use Image 3 only as the reference for the woman\'s face, hair and outfit: porcelain skin, large blue-grey eyes, long loose orange-red hair with a small silver crescent-moon clip on the left, small silver hoops; she wears a pale periwinkle-blue puff-sleeve button-up blouse, a thin black belt and charcoal-grey plaid wide-leg trousers; slender pale hands, short rounded nude nails, no rings, no bracelets, no watch. '
              'Do not add anything new. Only these two people are in the picture. No readable text. Same refined 3D romance-game CG render style.')
    if any('长袍' in w or '披袍' in w for w in worn): prompt += ' His robe stays draped over her shoulders on top of her blouse.'
    return _edit(prompt, [frame_url, FACE_URL, HER_URL], timeout)


def scene_diff(a, b):
    """比较修图前后画面四周（上 25%、左右各 15%）的灰度差，0–255；主体在中间，所以四周代表背景和构图。"""
    from PIL import Image, ImageChops
    A = Image.open(a).convert('L').resize((72, 128)); B = Image.open(b).convert('L').resize((72, 128))
    d = ImageChops.difference(A, B).load(); tot = n = 0
    for y in range(128):
        for x in range(72):
            if y < 32 or x < 11 or x >= 61: tot += d[x, y]; n += 1
    return round(tot / n, 1)


SEG_CHECK = """图片1是一段 9:16 视频按时间顺序抽出的 4 帧（左上=第1帧，右上=第2帧，左下=第3帧，右下=第4帧），来自一部观众第三视角的互动剧。图片2是男主 Rian 的身份母版（凌乱的银紫色长发、蓝紫耳鳍、半透明珍珠白长披袍（左肩月牙胸针））。图片3是女主的身份母版（正面头像、全身正面、近景特写）：橙红色披散长发、左侧银月牙发夹，浅长春花蓝泡泡袖衬衫，炭灰格纹阔腿裤。{allowed}
正确的站位：两人同在一帧时，男主在画面左侧、女主在画面右侧。

先逐帧写清楚看到了什么，再判断：
frames: 每帧一项 {"frame": n, "people": ["画面里的人，从左到右，例如 男主/女主/配角/陌生人"], "her_outfit": "女主在这一帧的发色、衬衫和长裤（看不到女主写 null）", "notes": "其他异常"}

严重问题（只报你确实看到的）：
- her：女主和图片3明显不是同一个人；或她的衬衫、长裤换了（剧情写了换装的除外）；或发色变成黑色、棕色、金黄、变短。
- face/outfit：男主不是图片2的人，或不是珍珠白长披袍和灯笼裤、水里不是长尾（剧情写了脱下长袍的除外）。
- people：除了男主、女主和允许的配角之外，画面里出现了真人（背景、门口、倒影）；墙上画里的人像不算。
- axis：两人同在一帧时，男主在画面右侧、女主在画面左侧（也就是和正确站位相反）。只有一个人、或空镜、或特写时不算。
- dissolve：某一帧是两个画面叠在一起的半透明重影。
- text：可读文字、乱码、标志。
- broken：肢体变形、多指、脸部扭曲、两人身体穿插粘连。
- light：同一地点的光线前后明显跳变，或肤色明显偏橙偏黄，或画面整体灰暗、饱和度明显变低。
- prop：悬空的东西、拿反的杯子、凭空出现在手里的大件物品、同一件东西同时出现两个。
- hands（V1.2）：同一帧里某个人的手超过两只、多指少指、两人的手粘在一起分不清是谁的、手表在两只手之间跳；算 broken。
- set（V1.2）：背景变成纯灰影棚底、纯黑底，或和前后帧完全不是同一个地方（分镜里没写换场）。
只输出 JSON：{"frames": [...], "regen": true/false, "issues": [{"frame": 1-4, "text": "简短中文", "kind": "her/face/outfit/people/axis/dissolve/text/broken/light/prop/set"}]}；没有严重问题就 issues 为空、regen=false。"""


def grid(mp4, out):
    """按时长均匀抽帧拼图：10 秒段抽 6 帧（3×2），5 秒段抽 4 帧（2×2）。V1.1 首测：4 帧漏掉了 10+10 第 7 轮中段那个换了外套的单人镜头。"""
    import live_common as L
    dur = float(subprocess.run(['/Users/vicky/Interactive storyline/.media-runtime/vivix-bin/ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(mp4)], capture_output=True, text=True).stdout or 10)
    n, cols = (6, 3) if dur > 7 else (4, 2)
    fr = [(k + 0.5) / n for k in range(n)]
    ins = []
    for f in fr: ins += ['-ss', f'{dur * f:.2f}', '-i', str(mp4)]
    lay = '|'.join(f"{'+'.join(['w0'] * (k % cols)) or '0'}_{'+'.join(['h0'] * (k // cols)) or '0'}" for k in range(n))
    fc = ';'.join(f'[{i}:v]scale=300:-2,setsar=1[v{i}]' for i in range(n)) + ';' + ''.join(f'[v{i}]' for i in range(n)) + f'xstack=inputs={n}:layout={lay}'
    subprocess.run([L.FFMPEG, '-v', 'error', '-y', *ins, '-filter_complex', fc, '-frames:v', '1', '-q:v', '3', str(out)], check=True)
    return n


HARD_MODEL = 'google/gemini-3-flash-preview'  # 2026-11-02 用 25 段已审片段比过：它 6/6 全中、误报 1/19；flash-lite 6/6、误报 6/19；gemini-2.5-flash、haiku 都有漏报
HARD_LITE = 'google/gemini-3.1-flash-lite'
HARD_CHECK = ('下面是同一段短视频按时间顺序抽出的 {n} 张独立的画面，每张都是一整帧，互相没有拼接。这段视频里只应该有这些人：{people}。有些画面是空镜（没有人）或只拍到一个人，这都是正常的。逐张看，只报你确定的明显错误：\n'
              '- people：一张画面里，人数多于应有人数；同一个人出现两次（两个长得一样的人）；半透明的重影人；空镜里闪现人。\n'
              '- motion：人在空中飞、横着飞过画面、身体严重扭曲折叠。\n'
              '- nude：女性胸部裸露、上身没有穿衣服；任何人下身裸露。男性赤裸上身、泳装不算。\n'
              '{wear}手指细节、手臂姿势、画风都不报。只输出 JSON：{{"bad": true 或 false, "kinds": [], "frames": [第几张], "why": "简短说明"}}')


def hard_check(mp4, people, wear='', timeout=20):
    """V3.0：每秒 1 帧、320 宽（原 1.6 帧、384 宽，提速）；配角的衣服不按女主查（三真四假 S231920f01 第 5 轮 Sloane 的蓝裙子被当成女主的裙子变色，三次重生成后拦下）。V2.7 开播前的硬错误检查（Vicky：角色数量错误、动态错误、裸露要严格规避）。独立帧、每秒 1.6 帧：拼成一张图时模型把相邻格子当成多个人，误报超过一半。约 5–10 秒；都没答就放行并记录。"""
    import tempfile
    import live_common as L
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([L.FFMPEG, '-v', 'error', '-y', '-i', str(mp4), '-vf', 'fps=1.0,scale=320:-2', '-q:v', '5', d + '/%02d.jpg'], check=True)
        fr = [base64.b64encode(p.read_bytes()).decode() for p in sorted(Path(d).glob('*.jpg'))]
    t0 = time.time(); content = [{'type': 'text', 'text': HARD_CHECK.format(n=len(fr), people=people, wear=(f'- clothes：男主、女主这时应该穿着：{wear}。画面里的其他人（配角）穿的是他们自己的衣服，和女主不一样是正常的，不按男主女主的衣服查他们。一眼就能看出的颜色错误才报，比如灰色 T 恤变成白色、一条裙子变了颜色。深浅差一点、款式细节、光线造成的差异都不报；纹身、项链、皮肤和发型不是衣服，不报。\n' if wear else '衣服颜色和款式也不报。'))}] + [{'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b}} for b in fr]
    def ask(model):
        body = {'model': model, 'max_tokens': 600, 'messages': [{'role': 'user', 'content': content}]}
        req = U.Request('https://openrouter.ai/api/v1/chat/completions', data=json.dumps(body).encode(), headers={'Authorization': 'Bearer ' + director._key(), 'Content-Type': 'application/json'})
        with U.urlopen(req, timeout=timeout) as r: j = json.loads(r.read())
        txt = j['choices'][0]['message'].get('content') or ''
        return dict(json.JSONDecoder().raw_decode(txt[txt.find('{'):])[0], sec=round(time.time() - t0, 1), model=model)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    ex = ThreadPoolExecutor(3)  # 主模型同发两个，先回来的用（平时 5–10 秒，偶尔 15 秒以上）；20 秒还没有就用便宜模型的结论（它什么都拦得住，但误报约三成）
    main = [ex.submit(ask, HARD_MODEL) for _ in range(2)]; lite = ex.submit(ask, HARD_LITE)
    try:
        for f in as_completed(main, timeout=timeout):
            try: return f.result()
            except Exception: pass
    except Exception: pass
    finally: ex.shutdown(wait=False)
    try: return lite.result(timeout=3)
    except Exception: pass
    return {'bad': False, 'kinds': [], 'why': 'check failed', 'err': True, 'sec': round(time.time() - t0, 1)}


def seg_state(mp4, state, timeout=40):
    """V2.0：穿着或姿态不是默认的那一段，播放前看一遍全程有没有变回去（Rafael 第 6 轮第 2 段后半段 T 恤又穿回去了）。"""
    g = Path(str(mp4)).with_suffix('.st.jpg'); n = grid(mp4, g)
    b64 = base64.b64encode(open(g, 'rb').read()).decode()
    t = (f'这张图是一段视频按时间顺序等间隔抽的 {n} 帧。这一段全程的状态应该是：{state}。逐格看有没有和它明确矛盾：已经脱掉的衣服穿在身上、该穿着的衣服不见了、该躺着却站着、该在车上却不在。'
         '只看大状态：看不到、无法确认的都不算；手放在哪、搂得紧不紧、半躺还是全躺、手表和裤子看不看得到都不算；空镜、只拍到脸看不出来的格子不算。只输出 JSON：{"bad": true 或 false, "why": "哪一格、什么问题，没有写空"}')
    body = {'model': VLM, 'max_tokens': 400, 'reasoning': {'effort': 'low'}, 'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': t}, {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}}]}]}
    req = U.Request('https://openrouter.ai/api/v1/chat/completions', data=json.dumps(body).encode(), headers={'Authorization': 'Bearer ' + director._key(), 'Content-Type': 'application/json'})
    with U.urlopen(req, timeout=timeout) as r: j = json.loads(r.read())
    txt = j['choices'][0]['message'].get('content') or ''; g.unlink(missing_ok=True)
    i = txt.find('{')
    return json.JSONDecoder().raw_decode(txt[i:])[0] if i >= 0 else {'bad': False, 'why': 'no json'}


def seg_check(mp4, cast=(), timeout=60, props=()):
    """V1.1：段内快检。返回 {regen, issues, dissolves}；叠化用本地检测（dissolve.scan），其余用视觉模型看 4 帧。"""
    import dissolve
    from pathlib import Path
    res = {'regen': False, 'issues': []}
    try:
        dz = dissolve.scan(str(mp4))['dissolves']
        if dz: res['issues'].append({'frame': 0, 'text': f'叠化转场 {dz[0][0]}–{dz[0][1]} 秒', 'kind': 'dissolve'}); res['regen'] = True
    except Exception as e: res['dissolve_err'] = str(e)[:120]
    g = Path(str(mp4)).with_suffix('.grid.jpg'); n = grid(mp4, g)
    b64 = base64.b64encode(open(g, 'rb').read()).decode()
    body = {'model': VLM, 'max_tokens': 1500, 'reasoning': {'effort': 'low'},
            'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': (('剧情道具（允许出现，不算换装或凭空出现）：' + '、'.join(props) + '。披在她身上的毯子、外套之类按剧情允许。\n') if props else '') + SEG_CHECK.replace('4 帧（左上=第1帧，右上=第2帧，左下=第3帧，右下=第4帧）', f'{n} 帧（从左到右、从上到下依次是第 1–{n} 帧）').replace('1-4', f'1-{n}').replace('{allowed}', ('允许出镜的配角：' + '、'.join(cast) + '。') if cast else '')},
                                                      {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
                                                      {'type': 'image_url', 'image_url': {'url': FACE_URL}},
                                                      {'type': 'image_url', 'image_url': {'url': HER_URL}}]}]}
    t0 = time.time()
    req = U.Request('https://openrouter.ai/api/v1/chat/completions', data=json.dumps(body).encode(),
                    headers={'Authorization': 'Bearer ' + director._key(), 'Content-Type': 'application/json'})
    with U.urlopen(req, timeout=timeout) as r: j = json.loads(r.read())
    txt = j['choices'][0]['message'].get('content') or ''
    m = re.search(r'\{.*\}', txt, re.S)
    v = json.loads(m.group(0)) if m else {}
    res['issues'] += [i for i in (v.get('issues') or []) if isinstance(i, dict)]
    res['regen'] = res['regen'] or bool(v.get('regen'))
    res['sec'] = round(time.time() - t0, 1)
    return res
