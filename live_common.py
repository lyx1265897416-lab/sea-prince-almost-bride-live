"""Rian｜人鱼王子的假新娘 · 开放式实时版 · 第三视角（观众看着两个人，画面里同时有男女主）：公共设置与提示词组装。
从 output/meet-me-third-live-v1 的 drama_slots.py 改写（make_slots.py）：流程和 PE 规则是第三视角共用模板，角色、世界观、地点和时间换成《人鱼王子的假新娘》。
规则来源 docs/互动剧实时生成规则-v0.1.md：三段（回应她的话 + 演绎 + 引出钩子）、两段并发、两段都好再连续播；
硬规则（景别锁定、表演克制、第一视角、她的手、瞳色、台词、钩子收尾）原文沿用 output/vivix-tests-20261022/live.py。
和原项目的区别：没有预设分支和结局，开场之后每一轮的视频都由观众的选择或输入实时生成，一直往下演。
第 1 段的首帧 = 上一轮第 2 段的最后一帧（第 1 轮用开场最后一帧）；第 2 段用参考图（同一张画面 + 男主脸）。"""
import re, os, sys
from pathlib import Path
ROOT = Path('/Users/vicky/Interactive storyline')
for line in (ROOT / '.env.vivix').read_text(encoding='utf-8').splitlines():
    k, s, v = line.strip().partition('=')
    if s and k.strip() in ('VIVIX_API_KEY', 'VIVIX_CA_BUNDLE'): os.environ.setdefault(k.strip(), v.strip().strip('"\''))
os.environ['PATH'] = str(ROOT / '.media-runtime/vivix-bin') + os.pathsep + os.environ.get('PATH', '')
sys.path.insert(0, str(ROOT))
from vivix_w1 import W1Client, JobFailed, PollTimeout, VivixError, MODEL  # noqa: E402
import vivix_w1 as _vw  # noqa: E402
_vw.MODEL = MODEL = 'vivix-w1-ultrafast'  # 2026-10-29 Vicky：先切 Fast，V1.5 提速方案一再切 ultrafast（实测 5 秒段提交到出片 10–12 秒；只改这个进程，vivix_w1.py 默认仍是普通档）

D = Path(__file__).resolve().parent
FFMPEG = str(ROOT / '.media-runtime/vivix-bin/ffmpeg')
SEG2_FIRST = False  # 两段都用首帧的写法试过（2026-10-24 S0603061c1）：没有身份母版，4 轮就变老、瞳色发橙，还拍出了女主正脸；保留开关但不用
SEG1_REF = True  # v0.15：第 1 段也用参考图（上一刻画面 + 身份母版 + 服装母版）。首帧续接没有母版，脸一轮轮变老、西装换成米色外套（v0.15 自测第 4、6、7、8 轮）
MODES = {'5+10': (5, 10), '5+15': (5, 15), '15+15': (15, 15), '10+10': (10, 10)}  # V1.7：5+15 用于自动分流。V2.8（Vicky 11-03）：15+15 和 5+10、5+15 并列，优先 15+15
SEG1_LOCK = ('10+10',)  # V0.17：10+10 第 1 段改成首尾帧都锁成上一刻画面（咪的修复验证 4/4 无硬错误）。Vivix 首尾帧和参考图不能混用，所以这一段没有身份母版；它的末帧不传给下一轮，漂移不累积

# v0.7（2026-10-24）：按 Seedance/Vivix 的多镜头写法重写。提示词压短、只写要出现的东西，约束放在最后一句；
# 反向描述（“不出现她的头发、肩膀”“没有警徽”）会把这些东西招出来，全部删掉。旧版见 live_common.v5.py。
import json as _json
TU = _json.loads((Path(__file__).resolve().parent / 'masters' / 'urls.json').read_text())
CAST = {
    'Vessa': ('Vessa：三十八岁女人，潮城摄政官、雷恩的姑母，沉稳成熟的脸，淡蓝灰色眼睛，银紫色编发盘起点缀珍珠，一对蓝色耳鳍，珍珠吊坠耳环，梅紫色高领刺绣长袍（领口一枚月牙胸针），半透明淡紫色长袖外罩，手里常拿一本深蓝皮面册子。长相和衣着以她的身份母版为准。', TU['vessa']),
    'Mila': ('Mila：二十一岁女人，斯凯最好的朋友，西方人长相，暖白皮肤和很多小雀斑，明亮的蓝眼睛，圆润友善的脸，蜜金色卷发扎成凌乱的高马尾（一侧琥珀色发夹），芥末黄连帽外套里面石板蓝 T 恤，灰色工装裤，白色运动鞋，脖子上挂着黑色相机背带。长相和衣着以她的身份母版为准。', TU['mila']),
}
HE_LOOK = 'Rian：二十三岁的人鱼王子，一米八五左右，年轻修长的游泳者身材（不壮硕），皮肤非常白皙干净；狭长清秀的脸，高颧骨、尖而精致的下颌（不是方下巴），直而细的鼻梁，深邃的淡紫灰色眼睛，平直的深银色眉毛，小而精致的嘴唇；凌乱有层次的银紫色长发（几缕垂在额前）；一对很大的半透明蓝紫色蹼状耳鳍；每只耳朵两颗白珍珠和一条长长的冰蓝水滴耳坠；一条细银链挂着蓝色水滴吊坠；左手腕一只细银镯，上臂一只银臂环，不戴戒指、不戴手表。宫廷装：一件半透明珍珠白虹彩蕾丝长披袍，在他的左肩用一枚大银月牙胸针束起，胸前垂下一串串珍珠和冰蓝水滴珠链，另一侧肩膀和那边胸口露在外面；长袍分成许多层不规则的半透明长片一直垂到脚踝，里面只隐约透出宽松的象牙白灯笼裤（脚踝收口），银色绑带凉鞋；不系腰带。进到水里他就是人鱼：赤裸修长的上身、珍珠和银臂环，一条很长的浅长春花蓝鳞尾和半透明白蓝鳍边（上身和尾巴约 3:7），同一时刻不会既有腿又有尾巴。他的长相和服装全程不变，以参考的身份母版为准。'
HER_FP = '她的手外形全程固定：纤细白皙的女性双手，指甲短而圆、裸色素甲，手指和手腕上空无一物，袖口是浅长春花蓝泡泡袖的系扣袖口。'
HER = '她：二十二岁的成年女人，西方人的长相，白皙瓷肤，眼下和两颊淡淡的自然红晕，大而清澈的蓝灰色眼睛和长睫毛，柔和平直的眉毛，小巧的直鼻，饱满柔软的嘴唇，精致的鹅蛋脸，不显幼态；橙红色（铜橙色）的披散长发垂到背中间，柔软的波浪，几缕碎发贴着脸，左侧别着一枚小银月牙发夹，耳垂上一对小银圈耳环；浅长春花蓝的系扣衬衫（泡泡长袖、袖口有扣），细黑皮带，炭灰格纹高腰阔腿裤，奶油色粗跟短靴；指甲短而圆、裸色素甲，手指和手腕上空无一物。开场时她刚从海里出来，头发和衣服湿透贴身，之后会慢慢变干。她的长相、发型和服装全程不变，严格以她的身份母版（正面头像、全身正面、近景特写）为准。她的表情自然克制，情绪在眼神里。'
WOLF = ''
import json as _json2
_ab = Path(__file__).resolve().parent / 'masters' / 'audio_bank.json'
AUDIO_BANK = _json2.loads(_ab.read_text()) if _ab.exists() else {}  # V2.3：预先生成好的配乐和歌（每部剧自己一份），没有就不用
SEAM = '第一个镜头接着上一刻往下演：两个人的姿势、手的位置和道具的状态都和上一刻一样，不把上一刻已经做完的动作再做一遍；换景别时同时换机位，不在同一个机位上突然放大缩小。'  # V1.2：评分里接缝跳回首帧、同轴跳切扣分最多
KISS = '吻戏的拍法（V1.4）：靠近只用一个干脆的动作，不慢慢凑近；从嘴唇贴上开始，到动作里写明分开之前，是同一次连续的吻，正常速度，动作一直在细微地变化（头部角度微调、他的手在她背上收紧、她的手指攥紧他的肩），不慢动作、不定格、不僵住；切镜之后的镜头一开始两人就已经在接吻，接着上一镜继续，不重新靠近，不中途分开再吻；手的特写里手一定在动。两人的五官、发型、服装和男左女右在吻中保持不变：每个接吻镜头里 Rian 的脸都在画面左半边、脸朝画面右侧，她的脸都在画面右半边、脸朝画面左侧，近景和侧面近景也不对调（V1.4 便携包自测第 1 轮最后一个接吻近景两人左右对调）。'
ACT = '表演自然：Rian 年轻自信、笑意从容，逗人时眼里带笑，认真时笑意收住、目光聚焦，说话自然，不压嗓、不耳语；被她逗到时会短暂移开目光；她说话干脆、反应快，带一点不买账的冷幽默，着急时声音会发紧；情绪在眼神和嘴角。'
PACE = '节奏（V3.0，Vicky 11-04：说话、动作慢吞吞，有定格感）：人物说话是正常偏快的自然语速，一句接一句，句间不留长停顿；动作是真人速度的连续动作，一个动作做完马上接下一个，不慢动作、不定格、不在一个姿势上停住；镜头里始终有人在动或在说话。'
STYLE = ('画面和角色参考图是同一种渲染和画质：精致的三维恋爱游戏 CG 角色渲染，皮肤细节柔和自然，眼睛和睫毛清晰，发丝分明，织物和鳞片质感清楚；海下王宫低调电影感的光：按脸定曝光，一盏有来源的暖琥珀色烛光加蓝绿色水波光纹勾边，背景比脸暗一点但不发灰，浅景深；不雾、不灰、不柔焦、脸上不发光、不磨皮、不塑料感、不动漫，标准焦段，五官比例自然，画风全程统一；时间和光线按这个地点写的来，肤色保持参考图的颜色。'
         '镜头之间一律硬切，不用叠化、溶镜、淡入淡出、闪白或闪黑；同一地点所有镜头的光线、色温和色调完全一致，跟随这个地点的主光源，不突然变冷变暖、变亮变暗。')


STAGING = {
    'face': '站位：两人面对面站着，相距一臂到半臂，Rian 在画面左侧、她在画面右侧，两人都是三分之四侧脸朝着对方。',
    'side': '站位：两人并排坐着（蓝色沙发、套房床沿或夜市长凳），Rian 在画面左侧、她在画面右侧，上身侧过来朝向对方；不是面对面坐。',
}


STAGE_ALT = []


def stage_text(st, place):
    return STAGING[st]


FRAMING = {'特写': '特写（只拍眼睛、手或物件）', '近景': '近景（胸部以上）', '中近景': '中近景（腰部以上）', '插入特写': '插入特写（只拍手或物件）', '中景': '中景（膝盖以上）', '全景': '全景（人物全身和周围空间）',
           '空镜': '空镜（这个地点的环境，画面里完全没有人，也没有手臂、身体或行驶的车辆经过，没有东西进出画面，镜头全程静止）',
           '双人全景': '双人全景（两人全身和周围空间都在画面里，男左女右）', '双人中景': '双人中景（两人膝盖以上同框，男左女右）',
           '双人中近景': '双人中近景（两人腰部以上同框，男左女右）', '双人近景': '双人近景（两人胸部以上同框，男左女右，两张脸都清楚）',
           '单人中近景': '单人中近景（一个人腰部以上）', '单人近景': '单人近景（一个人胸部以上）'}
FRAMING_KEYS = ('双人全景', '双人中景', '双人中近景', '双人近景', '单人中近景', '单人近景', '插入特写', '空镜', '中近景', '中景', '全景', '近景', '特写')


def framing(shot):
    """景别后面补上构图范围。V1.1 起景别按剧情灵活用（全景交代空间、中景看动作、近景看判断、特写看细节）。"""
    for k in FRAMING_KEYS:
        if shot.startswith(k): return FRAMING[k] + shot[len(k):]
    return shot


def pov(cast):
    who = 'Rian（画面左侧）和她（画面右侧）两个人' if not cast else 'Rian（画面左侧）、她（画面右侧）和 ' + '、'.join(cast) + ' 三个人'
    return (f'第三人称电影镜头：观众站在旁边看着他们，不是任何人的主观视角。主要人物是{who}。'
            '景别和机位按每个镜头写的来（全景、中景、近景、特写、空镜交替，可以略俯、略仰），他比她高一个头；两人同在画面里时 Rian 永远在画面左侧、她永远在画面右侧，不越轴，两人都不背对镜头。')


EVENT_SOUND = ('车停', '停车', '车轮', '刹车', '敲门', '脚步', '狼嚎', '来电', '铃', '门开', '开门', '喊', '叫', '人声', '说话声')


def steady(amb):
    """环境声里去掉事件声（车停、敲门、脚步、狼嚎……）：事件只在写到它的那一拍发生。"""
    parts = [x for x in re.split('[，,、；;]', amb) if x and not any(w in x for w in EVENT_SOUND)]
    return '，'.join(parts) or '安静的室内环境声'


def tail(amb, cast):
    voice = 'Rian 是二十出头温暖、清澈、带一点笑意和调侃的美式英语男声，她是自然、清亮、干脆、带一点不买账的美式英语女声'
    return (f'只说上面写出的英文台词，每句只说一遍；{voice}；说话的人口型同步，不说话的人闭着嘴。保留{amb}，没有背景音乐。'
            '一切按现实的物理规律：没人骑、没人开的车不会动，停着的车熄火停稳在路面上，同一个地点只有一辆；东西不会自己移动或变形，人不会悬空。画面里的东西只因看得见的动作出现和改变，同一样东西同一时刻只有一个，不悬空、不穿进身体；画面里的手只长在 Rian 和她身上，每人最多两只，两人的手不粘连。门、墙面、纸张都是素面的，衣服上没有文字和标志。每一秒都是铺满整个竖屏的完整画面，从头到尾亮度和色调不变；不出现画中画、相框、边框、黑边、暗角、四周压暗或变模糊、中间一块亮框，也不突然变色、变暗、变亮。约束：无字幕，无文字，无标志，无旁白，除写到的人物外没有其他人。')


CAM_WORDS = [('看着她', '看着镜头'), ('看向她', '看向镜头'), ('盯着她', '盯着镜头'), ('朝她', '朝镜头'), ('向她', '向镜头'), ('对她', '对着镜头'),
             ('离她', '离镜头'), ('她面前', '镜头前'), ('她脸侧', '镜头前'), ('她脸边', '镜头前'), ('她身边', '镜头旁'), ('她身侧', '镜头旁'), ('她身旁', '镜头旁'),
             ('她左侧', '镜头左侧'), ('她右侧', '镜头右侧'), ('她左边', '镜头左侧'), ('她右边', '镜头右侧'), ('和她', '和镜头'), ('与她', '与镜头'), ('她的脸', '镜头'),
             ('等她', '等着'), ('给她', '给镜头'), ('她', '镜头')]


def cam(t):
    """第三视角：她在画面里，分镜里的“她”照写；只保留物件写法的修正。"""
    for w in ('工单', '账单', '文件', '协议'):  # V0.17c：纸写成没有可读文字的纸
        if w in t and '素面' not in t: t = t.replace(w, w + '（一张没有任何可读文字的纸）', 1); break
    if re.search('泡面|方便面|包装|袋子|盒子|罐|瓶', t) and '没有文字' not in t: t += '（包装是素面的，没有任何文字、品牌和图案）'  # V2.3：泡面袋上出现了编造的品牌字
    return t


def side_of(shot, act, speaker=''):
    """第三视角：双人镜头写“Rian 在画面左侧、她在画面右侧”；单人近景写清是谁、在画面哪一侧、看向哪边，另一个人在画外。
    第三视角 v1 第 4 轮车里的双人近景拍成了反打（她到了左边），第 5、6 轮的过肩镜头也换了边。"""
    shot = str(shot)
    if shot.startswith('空镜'): return ''
    if shot.startswith('双人'): return 'Rian 在画面左侧、她在画面右侧（从这一镜的第一秒起就是这样），'  # V1.3：MD-B 越轴都发生在段落开头几秒
    if shot.startswith('单人'):
        her = speaker == '她' or (speaker != 'Rian' and re.match(r'(切到)?(她|她的)', act or '') is not None)
        return ('画面里只有她一个人，她在画面右半边、看向画面左侧的他（他在画外），' if her
                else '画面里只有 Rian 一个人，他在画面左半边、看向画面右侧的她（她在画外），')
    return ''


def shots(beats, dur, start=0, first=1, marks=None):
    """每一拍写成一个镜头：镜头N（起–止秒）【景别，运镜】动作 他说："台词"；镜头之间用“切到”。"""
    kiss = any('吻' in str(b[0]) for b in beats)
    w = [0.6 if str(b[2] if len(b) > 2 else '').startswith('空镜') else (0.7 if str(b[2] if len(b) > 2 else '').startswith(('插入特写', '特写')) else 1.6 if '仍在接吻' in str(b[0]) or ('吻' in str(b[0]) and '分开' not in str(b[0])) else 1.0) if kiss else 1.0 for b in beats]  # V2.4 空镜短一点（第 1、21 轮空镜拖到 5 秒）；V1.4：吻戏里接吻的拍子长、手的特写短（V1.3 等分，吻 2.5 秒、静止的手 3 秒）
    cut = [start + (dur - start) * sum(w[:i]) / sum(w) for i in range(len(beats) + 1)]
    out = []; here = ''
    for k, b in enumerate(beats):
        a, l = cam(b[0]), b[1]; shot = framing(b[2] if len(b) > 2 and b[2] else '近景，固定')
        m = re.match(r'切到([^：:，,。]{2,12})[：:，,]', a)
        if m and not re.search(r'景|特写|镜头|他|她|Rian|两人', m.group(1).replace('的空镜', '')): here = m.group(1).replace('的空镜', '')  # 第三视角常写“切到她的单人近景”：那是切镜不是换地点
        elif here: a = f'（仍在{here}）' + a  # 换场之后的每一拍都写明地点：参考图还是上一个地点，不写模型会切回去（v0.15 第 3 轮车里的戏最后回到了车库）
        who = b[3] if len(b) > 3 and b[3] else 'Rian'
        if not l: say = ''
        elif who.startswith('画外'): say = f'，画外传来{who.split(":", 1)[-1].split("：", 1)[-1] or "门外的人"}的声音："{l}"，画面里的 Rian 和她都闭着嘴在听，这句话不是他们说的，只用眼神回应'
        elif who == 'Rian':
            a = re.sub(r'[，,]?\s*(低声|轻声|沉声)?(开口|回应|回答)?(说|道)?(镜头|她)?$', '', a) if re.search(r'(说|开口|回应|回答)(镜头|她)?$', a) else a  # 避免“低声说，他说”
            say = f'，他说："{l}"' if a.strip('，, ') not in ('', '他') else f'他说："{l}"'
            if not say.startswith('，'): a = ''  # v0.8 写成“Rian 低声说”后出现了烧录字幕，改回
        elif who == '她': say = f'，她轻声说（女声，只有她的嘴在动，Rian 闭着嘴听）："{l}"'
        else: say = f'，{who} 说："{l}"'
        sh = b[2] if len(b) > 2 else ''
        a = re.sub(r'^切(到|回)(他|她|Rian|两人)?的?(单人|双人)?(中近景|近景|特写)[，,：:]\s*', '', a)  # 景别已经写在【】里
        if '门' in a and not any(c in a for c in CAST) and not who.startswith('画外'): a += '（门口和门外空无一人）'  # 第三视角 v1 第 8 轮：拍到门，门口背景里多出一个西装男人
        sd = side_of(sh, b[0], who if l else '')
        mm = re.match(r'(切到[^：:，,。]{2,12}[：:，,])', a)
        if k > 0 and '她在画面右侧' in sd and '空镜' not in str(sh): sd += '机位和上一个镜头在两人的同一侧，只是景别变了，不是反打，不绕到两人另一边；'  # kisstest
        a = (mm.group(1) + sd + a[mm.end():]) if mm else sd + a  # 换场那一拍：先写“切到新地点：”，再写站边  # 第三视角 v1 第 4–6 轮越轴：每个镜头都写明谁在画面哪一侧
        t = f'镜头{first + k}（{round(cut[k])}–{round(cut[k + 1])}秒）【{shot}】{a}' + say + (marks[k] if marks else '')
        out.append(t if k == 0 else '切到' + t)
    return '。'.join(out) + '。' + (KISS if kiss else '')


def take(beats, dur):
    """V0.17：首尾帧锁的一镜到底。几拍是同一个固定镜头里先后发生的动作，只写时间轴，不写景别、不写“切到”。"""
    step = dur / len(beats); out = []
    for k, b in enumerate(beats):
        a, l = cam(b[0]), b[1]; who = b[3] if len(b) > 3 and b[3] else 'Rian'
        a = re.sub(r'[，,]?\s*(低声|轻声|沉声)?(开口|回应|回答)?(说|道)?(镜头|她)?$', '', a) if re.search(r'(说|开口|回应|回答)(镜头|她)?$', a) else a
        if not l: say = ''
        elif who.startswith('画外'): say = f'，画外传来{who.split(":", 1)[-1].split("：", 1)[-1] or "门外的人"}的声音："{l}"，画面里的 Rian 和她都闭着嘴在听，这句话不是他们说的，只用眼神回应'
        elif who == '她': say = f'，她轻声说（女声，只有她的嘴在动，Rian 闭着嘴听）："{l}"'
        else: say = f'，他说："{l}"'
        out.append(f'（{round(k * step)}–{round((k + 1) * step)}秒）{a}' + say)
    return '。'.join(out) + '。'


timed = shots  # 旧名字，replay/make_log 里可能还在用


def moved(sp, set_start):
    """这一轮第 2 段换到了新地点（和 prompts 里的判断一致）。"""
    s0 = (set_start or sp.get('set') or '').rstrip('。'); s1 = (sp.get('set') or '').rstrip('。')
    return bool(sp.get('scene_changed') and s1 and s1 != s0)


TOUCH = re.compile(r'她的手|她的双手|她(?:的指尖|伸手|拉|握|牵|攥|抚|碰|摸|按|贴|拽|扯|捧)|拉着他|握着他|牵着他|攥着他')


def touches(beats):
    return any(TOUCH.search(b[0]) for b in beats)


def her_seg(hh):
    """her_hands 里写了“第1段/第2段”时，她的手只进那一段的提示词（v0.14 第 7 轮两段都写进去，第 2 段又冒出她的手）。"""
    a, b = any(w in hh for w in ('第1段', '第 1 段', '第一段')), any(w in hh for w in ('第2段', '第 2 段', '第二段'))
    return (True, True) if a == b else (a, b)


JACKET = '他的麂皮夹克'  # kisstest：他把外套给她之后，HE_LOOK 里“外套穿在身上”和服装母版会把外套画回他身上（S2343380d6 第 12、13 轮）
JACKET_ON = re.compile(r'(披|搭|裹)(到|在|上|住)[^。；]*(她|肩)|披着|裹着')
JACKET_OFF = re.compile(r'还给|还他|递还|递回|递出|递给他|穿回|重新穿|穿上|(取下|脱下)[^。；]*(还|递)')

def jacket_step(on, a):
    """kisstest：这一拍之后，他的外套是否在她身上。按整拍判断，不按小句。"""
    a = str(a)
    if '外套' not in a: return on
    if not on and re.search('脱|滑下|滑落|褪|推|拨开|扯下|扔|手搭', a) and '她肩' not in a: return on  # V1.8：脱他的外套不等于披到她身上（第 6 轮“她的双手搭上他外套的衣领往肩后推开”被当成披到她肩上）
    if on and JACKET_OFF.search(a): return False
    if JACKET_ON.search(a): return True
    return on


def _prompts(sp, mode, hands_in_frame=False, set_start=None, seg2_first=False, stage_start=None, worn=None, jacket_start=False):
    """第三视角：返回 [(时长, 提示词, 模式)]。模式 True=首帧续接、False=参考图、'lock'=首尾帧锁（10+10 第 1 段）。
    参考图顺序：不换场 [上一刻画面, Rian 脸, Rian 服装, 她, (Selene)]；换场的第 2 段 [两人站位母版, Rian 脸, Rian 服装, 她, (Selene)]。
    第 1 段永远在原地点、原站位；新地点和新站位只写进第 2 段。"""
    d1, d2 = MODES[mode]
    her_txt = HER + (f'这一刻她身上还加了剧情里披上的：{worn}，披在她的衬衫外面，全程保持，不要去掉。' if worn else '')  # V1.1 第 8–10 轮：他把外套披到她肩上，下一轮按固定外形写又把外套去掉了
    marks1 = marks2 = None; mag1 = mag2 = HE_LOOK; her1 = her2 = her_txt  # V2.0：外套走 wardrobe，这里不再单独判断（“披着”会被 jacket_marks 当成这一拍才脱下来）
    wolf = WOLF if sp.get('wolf') else ''
    st1 = sp.get('staging') or 'face'
    st0 = stage_start if stage_start in STAGING else st1
    cast_all = [c for c in (sp.get('cast') or []) if c in CAST]
    def seg_cast(beats): return [c for c in cast_all if any(c in b[0] or (len(b) > 3 and b[3] == c) for b in beats)]
    c1, c2 = seg_cast(sp['seg1']), seg_cast(sp['seg2'])
    amb = sp.get('amb') or '王宫回廊里远处的水流声和轻微的回声'
    amb1 = steady(amb)
    s0 = (set_start or sp.get('set') or '').rstrip('。'); s1 = (sp.get('set') or '').rstrip('。')
    moved = bool(sp.get('scene_changed') and s1 and s1 != s0)
    if not moved: st0 = st1
    else: amb1 = '安静的环境低鸣'  # 换场那一轮第 1 段还在原地点，不用新地点的环境声（第三视角 v1 干跑：车里配上了大宅的壁钟声）
    T0, T1 = stage_text(st0, s0), stage_text(st1, s1 + (sp.get('location') or ''))
    place1 = (f'地点：{s0}。' if s0 else '') + T0
    place2 = ((f'开头的地点：{s0}。' if s0 else '') + T0.replace('站位：', '开头的站位：') + f'切到新地点后：{s1}。' + T1.replace('站位：', '新地点的站位：')) if moved else place1
    people = 'Rian 和她的长相、服装以这些图为准，它们的影棚背景不进画面'
    plate = plate_for(sp)  # V3.0：这个地点的固定空景（有就用，没有照旧）
    if moved and plate:
        refs = '图片1是新地点的空景：每个镜头的背景、陈设、墙面、窗和光线都照它，人物站位是 Rian 在画面左侧、她在画面右侧，图片2是 Rian 的脸，图片3是他的服装，图片4是她（女主）的身份母版（正面头像、全身正面、近景特写）' + ''.join(f'，图片{5 + i}是 {c}' for i, c in enumerate(c2)) + f'，{people}；整段都在图片1这个地点，不回到上一个地点。'
    elif moved:
        refs = '图片1是两人的站位参考：Rian 在画面左侧、她在画面右侧（只参考左右站位和两人的样子），图片2是 Rian 的脸，图片3是他的服装，图片4是她（女主）的身份母版（正面头像、全身正面、近景特写）' + ''.join(f'，图片{5 + i}是 {c}' for i, c in enumerate(c2)) + f'，{people}；每个镜头的背景按下面写的地点。'
    else:
        refs = '图片2是 Rian 的脸，图片3是他的服装，图片4是她（女主）的身份母版（正面头像、全身正面、近景特写）' + ''.join(f'，图片{5 + i}是 {c}' for i, c in enumerate(c2)) + (('，图片5是这个地点的空景（陈设、墙面和光线照它）' if plate and not c2 else '')) + f'，{people}；图片1是上一刻的场景，每个镜头的背景、光线和色调都和图片1一致。'
    lead = '这一段紧接图片1那一刻：地点、背景、光线、两个人的位置、朝向和距离都和图片1一致，这一段不离开这个地点。'
    end = '最后停在两人同框的镜头上（男左女右，两张脸都看得到），留出悬念。'
    if mode in SEG1_LOCK and not seg2_first:  # 首尾帧锁，一镜到底，最后回到首帧
        lock = ('固定机位，一镜到底：镜头像架在三脚架上，全程不移动、不推近、不拉远、不切镜；两个人在画面里的大小和位置全程和首帧一样，'
                '画面上半部分的背景全程保持首帧的样子和位置。')
        lead = '首帧和尾帧是同一张画面（上一刻）：开头的场景、光线、两个人的长相、服装、位置、朝向和距离都与首帧一致，这一段不离开这个地点。两人的皮肤质感、他的瞳色和两人的发型全程和首帧完全一样。'
        p1 = (lock + pov(c1) + place1 + lead + mag1 + her1 + take(sp['seg1'], d1)
              + '最后 2 秒两人回到首帧的位置、姿势、表情和距离停住，画面和首帧一致。' + ACT + PACE + STYLE + tail(amb1, c1))
        hold2 = '图片1的画面（两人在原位的双人镜头）' if not moved else sp['hold'].rstrip('。')
        p2 = (refs + pov(c2) + place2 + mag2 + her2 + ''.join(CAST[c][0] for c in c2) + wolf
              + f'这一段从上一刻切过来，上一刻是：{hold2}。' + ('换场之前，' if moved else '') + '地点、背景、光线、两个人的位置和朝向与上一刻一致。' + SEAM
              + shots(sp['seg2'], d2, marks=marks2) + (f"最后停在{sp.get('location') or '新地点'}里，" if moved else '') + end + ACT + PACE + STYLE + tail(amb, c2))
        return [(d1, p1, 'lock'), (d2, p2, False)]
    lead = '这一段从首帧那一刻接着演：地点、背景、光线、两个人的长相、服装、位置、朝向和距离都和首帧一致，这一段不离开这个地点。'  # 第 1 段用首帧续接，和上一轮无缝接上；5 秒漂移小，末帧也不传给下一轮
    p1 = (pov(c1) + place1 + lead + mag1 + her1 + ''.join(CAST[c][0] for c in c1) + wolf
          + shots(sp['seg1'], d1, marks=marks1) + f'最后停在：{sp["hold"].rstrip("。")}。' + ACT + PACE + STYLE + tail(amb1, c1))
    p2 = (refs + pov(c2) + place2 + mag2 + her2 + ''.join(CAST[c][0] for c in c2) + wolf
          + f'这一段从上一刻切过来，上一刻是：{sp["hold"].rstrip("。")}。' + ('换场之前，' if moved else '') + '地点、背景、光线、两个人的位置和朝向与上一刻一致。' + SEAM
          + shots(sp['seg2'], d2, marks=marks2) + (f"最后停在{sp.get('location') or '新地点'}里，" if moved else '') + end + ACT + PACE + STYLE + tail(amb, c2))
    return [(d1, p1, True), (d2, p2, False)]


def seg2_cast_refs(sp):
    """第 2 段需要追加的配角身份母版（按出现顺序）。"""
    return [CAST[c][1] for c in (sp.get('cast') or []) if c in CAST and any(c in b[0] or (len(b) > 3 and b[3] == c) for b in sp['seg2'])]


def plate_for(sp):
    """V3.0（三真四假 S001455553：换到套房后第 2 段漂回泳池边，下一轮整轮都在泳池）：masters/urls.json 的 plates 是 {"地点关键词|关键词": 空景图}，这一轮的地点对上就用它当地点参考；没有 plates 的剧照旧。"""
    loc = str(sp.get('location') or '') + str(sp.get('set') or '')[:20]
    for k, u in (TU.get('plates') or {}).items():
        if any(x and x in loc for x in k.split('|')): return u
    return None


def prompts(sp, mode, hands_in_frame=False, set_start=None, seg2_first=False, stage_start=None, worn=None, jacket_start=False):
    """第三视角不需要第一视角那套“并排坐时改写成三分之四侧脸”的补丁：站位句本身写清了男左女右。"""
    return _prompts(sp, mode, hands_in_frame, set_start, seg2_first, stage_start, worn, jacket_start)


# V1.5（Vicky：剧情需要时其他角色可以出现）：extras 写进提示词开头，末尾的“手只长在两人身上”放开；不多调用任何东西
_prompts_v14 = prompts


def prompts(sp, mode, *a, **kw):
    out = _prompts_v14(sp, mode, *a, **kw)
    xs = [x for x in (sp.get('extras') or []) if isinstance(x, dict) and x.get('name')]
    if not xs: return out
    res = []
    for k, (d, p, f) in enumerate(out):
        beats = sp['seg1' if k == 0 else 'seg2']
        here = [x for x in xs if any(x['name'] in str(b[0]) or (len(b) > 3 and b[3] == x['name']) for b in beats)]
        if here:
            names = '、'.join(x['name'] for x in here)
            p = '这一段还有：' + '；'.join(f"{x['name']}（{x.get('look') or ''}）" for x in here) + '。长相和衣服全程不变，只在写到的镜头里出现，说话时口型同步。' + p
            p = p.replace('画面里的手只长在 Rian 和她身上', f'画面里的手只长在 Rian、她和{names}身上')
        res.append((d, p, f))
    return res


# V1.8：穿着状态、末尾约束、字幕时间。都是拼字符串，不多调用
HE_DEFAULT = '半透明珍珠白虹彩蕾丝长披袍（左肩银月牙胸针），象牙白灯笼裤，银色绑带凉鞋'
SHE_DEFAULT = '浅长春花蓝泡泡袖系扣衬衫，细黑皮带，炭灰格纹高腰阔腿裤'
_HE_RE = re.compile(r'宫廷装：.*?以参考的身份母版为准。', re.S)
_SHE_RE = re.compile(r'浅长春花蓝的系扣衬衫.*?奶油色粗跟短靴[^；]*；', re.S)
_SHE_END = '她的长相、发型和服装全程不变，严格以她的身份母版（正面头像、全身正面、近景特写）为准。'
_NIGHT = '时间是深夜，室内暖灯，窗外是夜色；在室外时天空是黑色的夜空，只有灯光和月光，没有白天的天光、蓝天和白云。'
TAIL_V18 = '每个人只有两只手、两条胳膊，没有悬空、不连着身体的手臂和袖子；同一件衣服只有一件，衣服不穿进身体，脱下来的衣服落下后留在原处。每样东西的数量不变，不会自己变多、变少、变样或移动；画面里只出现写到的东西，不凭空多出任何物件，也不让已有的东西凭空消失。'
TU = globals().get('TU') or {}  # 有的剧没有 masters/urls.json
FEET = '脚入镜时：他穿银色绑带凉鞋（在水里是长尾），她穿奶油色粗跟短靴，不光脚，不换鞋；她不戴手表、不戴戒指，他只有左手腕的细银镯。'
FEET_HE = '脚入镜时他穿银色绑带凉鞋（在水里是长尾）；他左手腕一只细银镯、上臂一只银臂环，不戴手表、不戴戒指。'
LOOK_BASE = '泡泡袖|格纹|阔腿裤'
HER_LOCK = 'She is a young Western woman: porcelain skin with a soft rosy blush, large clear blue-grey eyes with long lashes, soft straight brows, a small straight nose, full soft lips, a delicate oval face. Her hair is long, loose, flowing orange-red (copper-orange) to mid-back, soft waves, with a small silver crescent-moon hair clip on the left side; small silver hoop earrings. She wears a pale periwinkle-blue button-up blouse with full puffed long sleeves and buttoned cuffs, a thin black belt, charcoal-grey plaid high-waisted wide-leg trousers, cream heeled ankle boots. Short nude nails, no rings, no necklace.'
HER_LOCK_CUSTOM = 'Short nude nails, no earrings, no necklace.'
CLOTHED = '她从第一帧到最后一帧都穿着写到的衣服。'


def is_base(she):
    """V2.6：她穿的还是定装那身（开衫可脱可穿）。其余都是她自己换的衣服，不能拿定装图和定装描述去套（第 6 轮她要米色长裙，关键帧按定装画成条纹上衣）。"""
    return not she or bool(re.search(LOOK_BASE, str(she))) if LOOK_BASE else not she


def her_lock(w):
    return HER_LOCK if is_base((w or {}).get('she')) else HER_LOCK_CUSTOM
  # V2.4：第 11 轮起他光脚、第 21 轮白运动鞋、第 19 轮又是皮靴
LOOK_OUTER = '泡泡袖'
VEH = re.compile('摩托|机车|汽车|轿车|单车|自行车|(?<![库床])车(?!库|间|道|灯光)')
SEG1_ACT = re.compile('翻身|压|扑|跨|抱起|起身|站起|坐下|坐到|躺|倒|跌|走|跑|拉|推|脱|穿|拿|递|放|吻|拥|抱|搂|掀|踢|跳')
HER_STRIP = re.compile('她[^，。]{0,10}(抓|拉|掀|扯|脱|解|褪)[^，。]{0,12}(他|T ?恤|衬衫|衣)')
TAIL_INTIMATE = '两人都是成年人，这是含蓄的爱情戏：镜头停在脸、肩和手上，床上的镜头两人盖着被子。'  # 写身体部位的否定句本身会触发 Vivix 内容审核（S040307dee 第 1 轮连牵手的第 1 段都被拦）


def _dress(p, w):
    he, she = w.get('he'), w.get('she')
    if he: p = _HE_RE.sub(lambda m: f'此刻他的穿着：{he}，就按这个样子，不自己穿回去；不加纹身和别的首饰，手指上空无一物。他的长相全程不变。', p)
    if she:
        p = _SHE_RE.sub(lambda m: f'此刻她的穿着：{she}，就按这个样子，不自己穿回去；', p)
        p = p.replace(_SHE_END, '她的长相和发型全程不变，以她的身份母版为准；身份母版里的衣服不用看，穿着按这里写的。')
    return p


_WEAR_RE = re.compile('脱|解开|解下|褪|滑下|滑落|拨开|敞开|掀开|扯开|推|穿上|穿回|披上|系上|扣上|扣好|换上')


def _wear_note(w):
    t = []
    if w.get('he'): t.append(f"Rian：{w['he']}")
    if w.get('she'): t.append(f"她：{w['she']}")
    return '（这个镜头的穿着，' + '；'.join(t) + '）' if t else ''


RIDE_ON = re.compile('行驶|骑行|疾驰|飞驰|驶过|驶向|驶在')
RIDE_MOVE = '（，头发和衣角被风吹向后方，两人的脚都踩在脚踏上；她坐在后座环着他的腰）'
CAR_MOVE = '（车正在路上行驶：车窗外的景物向后掠过，两人随车身轻微晃动）'


def _move(a):
    return CAR_MOVE if re.search('车窗|后排|车里', a) else RIDE_MOVE + '（镜头在车的正侧面，不从车头正前方拍；车上只有他们两个人，她在他身后，画面里只有一张她的脸）'  # Magnus 实测：从车头正面拍，他两侧各冒出一个女人


def _mark_shots(p, beats, start, end, posture='', holding=''):
    """每个镜头标当前穿着和姿态（只写在段首时，参考图会把衣服带回去）：变化那一拍（最后一个写了穿脱动作的拍子）之前按开头，之后按结束。V2.0：加上姿态、手里的东西和行进的运动。"""
    last = max([i for i, b in enumerate(beats) if _WEAR_RE.search(str(b[0]))], default=-1) if end != start else -1
    n = [-1]
    def sub(m):
        n[0] += 1
        i = n[0]; b = beats[i] if i < len(beats) else None
        if b is not None and '空镜' in str(b[2] if len(b) > 2 else ''): return m.group(0)
        w = end if (end != start and i > last) else start
        t = _wear_note(w)
        if posture: t += f'（这个镜头两人的姿态：{posture}）'
        if re.search('躺|俯在', posture or ''): t += '（从这个镜头第一秒到最后一秒两人都还躺在地上：镜头略俯，背景是身下的沙子或床，不是天空和海平线，没有人站着，也没有人站起来）'
        if re.search('坐', posture or '') and not re.search('躺|俯在|骑|摩托|车', posture or ''): t += '（从这个镜头第一秒到最后一秒两人都还坐着，没有人站着，也没有人站起来）'  # V2.4：回归 R4 收尾的中景把跨坐拍成站着
        if holding: t += f'（这一刻手里和身边的东西，数量和位置就是这样，不多不少：{holding}）'
        if b is not None and RIDE_ON.search(str(b[0])): t += _move(str(b[0]))
        return m.group(0) + t
    return re.sub(r'镜头\d+（[^）]*）【[^】]*】', sub, p)


_prompts_v17 = prompts


def prompts(sp, mode, *a, **kw):
    out = _prompts_v17(sp, mode, *a, **kw)
    start, end = sp.get('wardrobe_start') or {}, sp.get('wardrobe_end') or {}
    use = sp.get('use_key')  # V2.0：'bridge' 不换地点，第 1 段首尾帧演变化、第 2 段首帧=关键帧；'ref' 换地点（或有 Selene），第 2 段第一张参考图=关键帧
    custom = bool(sp.get('wardrobe_changed'))
    def looks_of(text):  # V2.3：只写这一段用到的东西（原来全写，第 7 轮小锅、泡面、碗跟到了修车店，第 12 轮跟到了沙滩）
        return '；'.join(f'{k}：{v}' for k, v in (sp.get('looks') or {}).items() if k in text or k[-2:] in text)  # V2.4：原来比前两个字，“黑色烤盘”把“黑色旧摩托车”也带进来
    res = []
    for k, (d, p, f) in enumerate(out):
        w_here = end if (k == 1 and use) else start
        m_x = re.match(r'这一段还有：.*?说话时口型同步。', p, re.S); x = m_x.group(0) if m_x else ''  # 换开头时保住 extras 的外形
        if custom:
            p = _dress(p, w_here)
            if w_here.get('tod'): p = p.replace(_NIGHT, '时间是清晨，窗外是柔和的晨光，室内是自然的晨光。').replace('深夜，', '').replace('深夜的', '').replace('深夜', '')
            stay = not sp.get('scene_changed')  # 不换地点：第 1 段首尾锁成上一刻的画面，第 2 段的第一张参考图也是它，接缝不跳，房间和穿着也接得上（第 4、5 轮换过房间）
            if k == 0 and stay and f is True and not use and not SEG1_ACT.search(' '.join(str(b[0]) for b in sp['seg1'])): f = 'lock'  # V2.4：只有纯说话才锁，第 16 轮穿着变过之后“翻身压住”被锁回首帧，动作没了
            if f == 'lock' and k == 0: p = p.replace('最后停在：', '最后回到和首帧一样的位置和姿势：', 1)
            if k == 1 and not use:
                i = p.find('第三人称电影镜头')
                if i > 0 and not f:
                    if stay: p = x + '图片1就是这一段的场景和上一刻的画面：房间、床、灯、光线、两人的穿着和位置都和图片1一样，这一段不离开这个地方；图片2只看 Rian 的脸和头发，图片3只看她的脸和头发' + '；两人的长相和画风以这些图为准，穿着按每个镜头写的。' + p[i:]  # 只用首帧时 4 轮就换脸（头发变棕、变真人画风），所以第 2 段仍带脸的参考图
                    else: p = x + '图片1是上一刻的画面：两人的长相和此刻的穿着都接着它（背景换成下面写的新地点）；图片2只看 Rian 的脸和头发；图片3只看她的脸和头发。' + p[i:]
                if end != start:
                    p = p.replace('他的长相和服装全程不变，以参考的身份母版为准。', '他的长相全程不变，穿着按写到的动作变化。').replace(_SHE_END, '她的长相和发型全程不变，穿着按写到的动作变化。').replace('全程穿在身上；', '开头穿在身上；')
                    p += f"这一段的穿着变化：开头是（Rian：{start.get('he', HE_DEFAULT)}；她：{start.get('she', SHE_DEFAULT)}），只在写到的那一拍变化，之后是（Rian：{end.get('he', start.get('he', HE_DEFAULT))}；她：{end.get('she', start.get('she', SHE_DEFAULT))}），不再变回去。"
        i = p.find('第三人称电影镜头')
        if k == 1 and use == 'bridge' and i >= 0:  # V2.0：第 2 段从关键帧开始，一开始就是变化之后的样子；不带参考图，服装母版不会把衣服穿回去
            f = True; p = x + '这一段从首帧那一刻接着演：地点、背景、光线、两个人的长相、穿着、姿态、手里的东西都和首帧一样，全程保持，不变回去。' + p[i:]
        if k == 1 and use == 'ref' and i >= 0:
            sel = [c for c in (sp.get('cast') or []) if c in CAST and any(c in b[0] or (len(b) > 3 and b[3] == c) for b in sp['seg2'])]
            f = False; p = x + '图片1是这一段的新地点和两人此刻的样子：地点、光线、两人的穿着、姿态和道具都照它，每个镜头保持，不变回去；图片2只看 Rian 的脸和头发，图片3只看她的脸和头发' + ''.join(f'，图片{4 + n}是 {c}' for n, c in enumerate(sel)) + '；他们的影棚背景不进画面。' + ('第一个镜头是空镜：画面里完全没有人，也没有车，两人从第二个镜头才出现。' if str(sp['seg2'][0][2]).startswith('空镜') else '') + p[i:]
        if k == 1 and use == 'ref':  # 图片1已经是新地点，再写旧地点和“上一刻”模型会先拍半秒旧地点再叠化（Magnus 实测第 2 段开头闪车库）
            p = re.sub(r'开头的地点：.*?切到新地点后：', '地点：', p, flags=re.S).replace('新地点的站位：', '站位：')
            p = re.sub(r'这一段从上一刻切过来，上一刻是：[^。]*。换场之前，地点、背景、光线、两个人的位置和朝向与上一刻一致。', '', p).replace(SEAM, '')
        if k == 1 and use: p = p.replace(_SHE_END, '她的长相和发型全程不变；穿着和姿态照图片和每个镜头写的。')
        if k == 0 and use == 'bridge':  # 第 1 段：首帧是上一刻，尾帧是变化之后的样子，一镜到底把动作演出来
            f = 'bridge'
            p = p.replace('这一段从首帧那一刻接着演：地点、背景、光线、两个人的长相、服装、位置、朝向和距离都和首帧一致，这一段不离开这个地点。', '这一段从首帧那一刻开始：地点、背景、光线和两个人的长相都和首帧一致，这一段不离开这个地点；穿着和姿势从首帧开始变，到最后一秒变成尾帧的样子。')
            p = p.replace('他的长相和服装全程不变，以参考的身份母版为准。', '他的长相全程不变，穿着按写到的动作变化。').replace(_SHE_END, '她的长相和发型全程不变，穿着按写到的动作变化。').replace('全程穿在身上；', '开头穿在身上；')
            a_ = p.find('镜头1（'); b_ = p.find('最后停在：')
            if a_ >= 0 and b_ > a_: p = p[:a_] + '固定机位，一镜到底，不切镜，把这个动作连续演完：' + take(sp['seg1'], d) + p[b_:]
            hold_now = str(sp.get('key') or sp.get('hold') or '').rstrip('。')
            p = re.sub(r'最后停在：[^。]*。', lambda m: f'最后变成尾帧的样子（动作已经做完）：{hold_now}。', p, count=1)
        beats = sp['seg1' if k == 0 else 'seg2']
        w1 = end if (k == 1 and not use) else w_here
        po = (sp.get('posture_end') if k == 1 else sp.get('posture_start')) or ''
        ho = (sp.get('holding_end') if k == 1 else sp.get('holding_start')) or ''
        if re.search('躺|俯在|跨坐', po):  # 站位句写着“面对面站着”，和躺着的姿态打架
            for st in list(STAGING.values()) + STAGE_ALT: p = p.replace(st[3:], f'{po}，Rian 在画面左侧、她在画面右侧。')
        if custom or po or ho:
            p = _mark_shots(p, beats, w_here if custom else {}, w1 if custom else {}, po, ho)
        elif any(RIDE_ON.search(str(b[0])) for b in beats): p = _mark_shots(p, beats, {}, {})
        looks = looks_of(' '.join(str(b[0]) for b in beats) + str(ho))
        if looks: p += f'固定外观（全程不变）：{looks}。'
        p = re.sub(r'(镜头\d+（[^）]*）【空镜[^】]*】)', r'\1（这个镜头从头到尾画面里完全没有人，也没有车，也没有路牌、广告牌和任何文字；镜头结束时硬切到下一个镜头，人物不从空镜里走进来）', p)  # V2.4：第 22 轮她从空镜里走进来，第 5 轮空镜里一排摩托
        seg_set = str(sp.get('set') or '') if k == 1 else str(kw.get('set_start') or sp.get('set') or '')
        if not VEH.search(' '.join(str(b[0]) for b in beats) + str(po) + str(ho) + seg_set): p += '这个地点的画面里没有摩托车和其他车。'  # V2.4：第 13、14 轮沙滩上冒出摩托
        if k == 0 and sp.get('redressed'): p = p.replace('不自己穿回去', '只在写到的那一拍把衣服穿回去')
        if k == 0 and HER_STRIP.search(' '.join(str(b[0]) for b in beats)): p += '脱衣服的动作是她的双手做的：她的手抓着衣服往上掀，他只是抬起手臂配合，不是他自己脱。'  # V2.4：第 14 轮他自己脱了
        if not re.search('光脚|赤脚|脱了?鞋|鞋[^，。]{0,4}脱', str(sp.get('intent') or '') + str(sp.get('wardrobe_end') or '') + str(ho)): p += FEET if is_base((w1 or {}).get('she')) else FEET_HE
        if k == 1 and re.search('比基尼|泳', str((w1 or {}).get('she') or '')) or k == 0 and re.search('比基尼|泳', str(start.get('she') or '')): p += '她的镜头是中景或全景，从正面或侧面拍，不从身后拍，动作自然日常。'
        if k == 0 and sp.get('offscreen_change') and end.get('she'): p += f"画面里她拿着或他递给她的那件衣服，就是她接下来要穿的：{end['she']}，颜色和款式一模一样。"  # V2.7：第 1 段递的是白裙子，穿好后是深蓝裙
        if k == 1 and (use == 'ref' or (custom and not use)) and swatch(w1): p = '参考图里有一张只有深色布料的图：那是他 T 恤的布料和颜色，不是一个人，也不进画面。' + p
        p += CLOTHED  # V2.6：第 4 轮换裙子时她上身裸露。写法只写“穿着”，不写身体部位（否定句写身体部位会触发内容审核）
        if any(RIDE_ON.search(str(b[0])) for b in beats) and TU.get('vehicle') and not f: p = '最后一张参考图是这辆车：款式和颜色照它，它的白底不进画面。' + p
        sg = sp.get('song')
        if sg and k == 1: p = _sing_marks(p, sg, beats)
        p += TAIL_V18
        if k == 1 and int(sp.get('intimacy') or 0) >= 3: p += TAIL_INTIMATE
        res.append((d, p, f))
    return res


def _sing_marks(p, sg, beats):
    """V2.3：唱的那几拍写明嘴跟着旋律动，没有说话声（歌声播放时叠上去）。"""
    who = '她' if sg.get('who') == '她' else '他'; n = [-1]
    def sub(m):
        n[0] += 1
        return m.group(0) + (f'（{who}在轻声唱歌：嘴跟着很慢的旋律一开一合，表情投入，看着对方；这一拍视频里没有说话声）' if n[0] in (sg.get('beats') or []) else '')
    return re.sub(r'镜头\d+（[^）]*）【[^】]*】', sub, p)


def mix_of(sp):
    """V2.3：这一轮要叠上去的配乐和歌声。都是预先生成好的，不增加等待。"""
    out = {}; bgm = (AUDIO_BANK.get('bgm') or {}).get(str(sp.get('bgm') or ''))
    if bgm: out['bgm'] = bgm['url']
    sg = sp.get('song')
    if sg:
        v = (AUDIO_BANK.get('songs') or {}).get(sg['id']) or {}
        n = len(sp.get('seg2') or [1]); out['song'] = {'url': v.get('url'), 'seg': 1, 'at': round(sg['beat'] * 15 / n + 0.2, 2), 'dur': v.get('dur')}
    return out


def swatch(w):
    """V2.7：他穿着 T 恤时，第 2 段带一张只有布料的裁图（不带全身图以后，近景里 T 恤变白）。"""
    return [TU['he_swatch']] if TU.get('he_swatch') and not re.search('赤裸|光着|裸', str((w or {}).get('he') or '')) else []


def key_people(w, her_url=None):
    """V2.4 关键帧的人物图：穿着图本身带脸，直接替换头像，始终 3 张（实测每多一张图关键帧慢 10 秒以上：3 张 11–25 秒，4 张 22–32 秒）。回归 R4 只给头像，关键帧把开衫画丢了。"""
    w = w or {}; he, she = str(w.get('he') or ''), str(w.get('she') or '')
    h = TU.get('look_he_off') if re.search('赤裸|光着|裸', he) else TU.get('outfit')
    s = (TU.get('look_she_on') if (not she or LOOK_OUTER in she) else TU.get('look_she_off')) if is_base(she) else her_url  # V2.6：她自己换的衣服，第一次只给脸，之后用第一次画出来的那张
    return h, s


def anchor_prompt(state, issues, w=None, objects='', vehicle=False):
    """V2.2：把上一轮末帧回正成定装图的样子，再交给下一轮。地点、姿态、穿着都不动，把累积的漂移擦掉；只拍到一个人时把另一个也带进来（只露一个人的末帧，下一轮第 1 段会把另一个人的衣服画错：V2.2 第 4 轮她变成黑背心牛仔裤）。"""
    w = w or {}
    return ('Image 1 is a frame from a film. Repaint this moment as one clean frame: the same location, background, lighting, poses, expressions and objects, the same camera distance and crop. Nobody changes pose: whoever sits stays sitting, whoever lies stays lying, a close-up stays a close-up; do not invent a wider view or the lower body. The man is on the left and the woman on the right; only if Image 1 shows just one of them, pull the camera back so the other is there too at the natural distance. '
            f'His clothes right now (Chinese): {w.get("he") or HE_DEFAULT}。 Her clothes right now (Chinese): {w.get("she") or SHE_DEFAULT}。 Exactly these clothes, nothing added back: if his torso is bare there is no shirt, no open shirt and no jacket on him. '
            'Image 2 is the man (Rian), Image 3 is the woman: ignore their studio backgrounds and only correct what has drifted away from them. '
            + (f'The state of this moment, keep it exactly (Chinese): {state}。 ' if state else '')
            + 'Keep every object exactly as it is in Image 1 and do not add any object that is not already visible in Image 1, including clothes on the ground. '
            + (f'Also fix (Chinese): {"；".join(issues)}。 ' if issues else '')
            + 'He: 23, very pale smooth skin, long messy layered silver-lilac hair, large translucent blue-violet fin ears, straight dark-silver brows, deep-set lavender-grey eyes, a long narrow slender face with a fine pointed jaw, a thin silver bangle on his left wrist, no tattoos, no rings, no watch. His face is long, narrow and slender with high cheekbones and a fine pointed jaw, deep-set lavender-grey eyes, straight dark-silver brows, very pale skin. His hair is long, messy, layered silver-lilac, never short, never black. Large translucent blue-violet webbed fin ears with white pearls and long ice-blue teardrop earrings; a blue teardrop pendant on a fine silver chain; a thin silver bangle on his left wrist and a silver upper-arm band. He wears a sheer ivory iridescent lace robe gathered on his left shoulder under a large silver crescent-moon brooch, strands of pearls and ice-blue beads down his chest, the other shoulder bare, the robe falling in sheer layered panels to his ankles over loose ivory harem trousers, silver strappy sandals. No belt, no tattoos, no rings, no watch. Young slim swimmer build, not bulky. In water he has a long pale periwinkle-blue scaled tail instead of legs. '
            'She: adult aged 22, a young Western woman with a delicate oval face, porcelain skin, a soft rosy blush, large clear blue-grey eyes, long loose flowing orange-red hair to mid-back with a small silver crescent-moon clip on the left side, small silver hoop earrings; short nude nails, no rings, no bracelet. ' + her_lock(w) + ' '
            + ('There is exactly one motorcycle. ' if vehicle else 'There is no motorcycle, car or any other vehicle in this frame. ')
            + 'Every object appears only once. Keep the same refined 3D romance-game CG character rendering. Correct anatomy, five fingers on each hand. Add nothing new. No text, no logo, no watermark.')


def key_prompt(sp, moved):
    """V2.0：第 2 段第一张画面（状态关键帧）的修图指令。两段同时生成，第 2 段看不到第 1 段；衣服、姿态、地点变化都先画成这一张，两段都对着它演。"""
    w = sp.get('wardrobe_end') or {}
    he, she = w.get('he') or HE_DEFAULT, w.get('she') or SHE_DEFAULT
    place = (sp.get('set') or '').rstrip('。')
    head = ('Image 1 is the previous moment of the same film: use it for the two people and the render style, but the location changes to the one written below. ' if moved
            else 'Image 1 is the previous moment of the same film: keep the same location, background, lighting, color, camera side and about the same camera distance, not closer; both people keep their upper bodies in frame. ')
    when = ''  # 时间写在 set 里
    h_img, s_img = key_people(w, sp.get('she_look_url')); veh = bool(VEH.search(' '.join(str(sp.get(k) or '') for k in ('key', 'posture_end', 'holding_end', 'set'))))
    return (head + ('Image 2 is the man (Rian): his face and hair' + (', and also his exact clothes and tattoos right now' if h_img else '') + '; ignore its studio background. Image 3 is the woman: her face and hair' + (', and also her exact clothes and shoes right now' if s_img else '') + '; ignore its studio background. ') +
            f'Paint the next moment as one still frame, vertical 9:16. What the frame shows (written in Chinese): {sp.get("key")}。 '
            f'Location (Chinese): {place}。 Posture (Chinese): {sp.get("posture_end") or "按画面描述"}。 '
            f'His clothes right now (Chinese): {he}。 Her clothes right now (Chinese): {she}。 Clothes must be exactly these, nothing added back; whatever he has not taken off (trousers, shoes, accessories) keeps the exact color and style it has in Image 1. ' + when
            + 'A garment that was taken off is completely off the body: not on the arms, not at the elbows, not around the waist. '
            + (f'她身上穿着{LOOK_OUTER}，袖子在手臂上，不能画丢。 ' if LOOK_OUTER in she else '')
            + 'She is fully dressed in exactly the clothes written above. '
            + ('Medium-wide shot so her whole outfit is clearly visible. ' if sp.get('offscreen_change') else '')
            + (f'Objects here, exact count, only if their position falls inside this frame (Chinese): {sp.get("holding_end")}。 Clothes on the ground lie crumpled where they fell, part of the scene, never flat-laid or like icons. ' if sp.get('holding_end') else 'Nobody holds anything and nothing lies on the ground unless written above. ')
            + (f'Fixed object looks (Chinese): ' + '；'.join(f'{k}：{v}' for k, v in (sp.get('looks') or {}).items() if k in str(sp.get('key')) or k in str(sp.get('holding_end'))) + '。 ' if any(k in str(sp.get('key')) or k in str(sp.get('holding_end')) for k in (sp.get('looks') or {})) else '')
            + 'If his torso is bare: a natural fit build, not a bodybuilder, no oil, the same skin color as his face, lit by the light of this location. '
            + ('Nothing from the previous location comes along: no plates, food, cartons or furniture from it, only what is written under Objects. ' if moved else '')
            + 'Exactly two people: the man on the left of the frame, the woman on the right, both faces visible. He: 23, very pale smooth skin, long messy layered silver-lilac hair, large translucent blue-violet fin ears, straight dark-silver brows, deep-set lavender-grey eyes, a long narrow slender face with a fine pointed jaw, a thin silver bangle on his left wrist, no tattoos, no rings, no watch. His face is long, narrow and slender with high cheekbones and a fine pointed jaw, deep-set lavender-grey eyes, straight dark-silver brows, very pale skin. His hair is long, messy, layered silver-lilac, never short, never black. Large translucent blue-violet webbed fin ears with white pearls and long ice-blue teardrop earrings; a blue teardrop pendant on a fine silver chain; a thin silver bangle on his left wrist and a silver upper-arm band. He wears a sheer ivory iridescent lace robe gathered on his left shoulder under a large silver crescent-moon brooch, strands of pearls and ice-blue beads down his chest, the other shoulder bare, the robe falling in sheer layered panels to his ankles over loose ivory harem trousers, silver strappy sandals. No belt, no tattoos, no rings, no watch. Young slim swimmer build, not bulky. In water he has a long pale periwinkle-blue scaled tail instead of legs. '
            'She: adult aged 22, a young Western woman with a delicate oval face, porcelain skin, a soft rosy blush, large clear blue-grey eyes, long loose flowing orange-red hair to mid-back with a small silver crescent-moon clip on the left side, small silver hoop earrings; short nude nails, no rings, no bracelet. ' + her_lock(w) + ' '
            + ('There is exactly one motorcycle. ' if veh else 'There is no motorcycle, car or any other vehicle in this frame. ')
            + 'Every object appears only once. Keep the same refined 3D romance-game CG character rendering as Image 1. Correct anatomy, five fingers on each hand. No text, no logo, no watermark.')


def _song_rows(sp, cut):
    sg = sp.get('song'); v = (AUDIO_BANK.get('songs') or {}).get((sg or {}).get('id')) or {}
    if not sg: return []
    at = cut[sg['beat']] + 0.2
    return [{'en': x['en'], 'zh': x.get('zh', ''), 'who': '她' if v.get('who') == '她' else 'Rian', 's': round(at + x['s'], 1), 'e': round(at + x['e'], 1), 'sung': True} for x in v.get('lines') or []]


def line_times(sp, mode):
    """V1.8：每句台词在这一段里说的时间窗（和 shots 的分拍一致），播放页只在这个时间里显示字幕。"""
    d1, d2 = MODES[mode]; out = {}
    for k, dur in (('seg1', d1), ('seg2', d2)):
        beats = sp.get(k) or []; kiss = any('吻' in str(b[0]) for b in beats)
        w = [0.6 if str(b[2] if len(b) > 2 else '').startswith('空镜') else (0.7 if str(b[2] if len(b) > 2 else '').startswith(('插入特写', '特写')) else 1.6 if '仍在接吻' in str(b[0]) or ('吻' in str(b[0]) and '分开' not in str(b[0])) else 1.0) if kiss else 1.0 for b in beats]
        cut = [dur * sum(w[:i]) / max(sum(w), 1) for i in range(len(beats) + 1)]
        z = (sp.get('zh') or {}).get(k) or []; rows = []
        for i, b in enumerate(beats):
            if not b[1]: continue
            who = str(b[3]) if len(b) > 3 and b[3] else 'Rian'; who = who.split(':', 1)[-1].split('：', 1)[-1]
            s = cut[i] + 0.2; e = min(cut[i + 1], s + max(1.4, len(str(b[1]).split()) * 0.45 + 0.6))
            rows.append({'en': b[1], 'zh': z[i] if i < len(z) else '', 'who': who, 's': round(s, 1), 'e': round(e, 1)})
        if k == 'seg2': rows = sorted(rows + _song_rows(sp, cut), key=lambda x: x['s'])
        out[k] = rows
    return out

