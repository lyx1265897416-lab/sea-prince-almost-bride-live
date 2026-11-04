# 人鱼王子的假新娘 · 第三视角实时版（2026-11-04）

开场 = 外国人版 v9 确认版（制作/新版互动剧集-v32/rto_openw/opening.mp4，71.9 秒），播完停在斯凯抬头看雷恩的近景，待机循环 docs/media/IDLE0.mp4（gen_idle.py，Seedance 只给首帧 + 正放倒放）。之后全部实时：第三视角共用模板（auto 优先 15+15）。

- 规则：tools/realtime-third/templates；本剧内容 drama_slots.py（make_slots.py 从《今天，再喜欢我一次》改写，之后直接改 drama_slots.py）。
- 资料包 pack/build_pack.py → rian_pack.json：隐藏真相（“未婚妻”是临时编的，普通担保和通行证存在，他想借她推掉联姻），K01–K12（过关→会客厅找到米拉→相机和通行证→承认私心→套房鳞光→送米拉→礁海→夜市→吻→议会）。海下地点写明没有日光（11-04 冒烟东廊写“清晨”时第 1 段末尾漂成日光大厅）。
- 母版 masters_build.py：雷恩用角色库 sea-rian--front + lib-RIA-master；斯凯用 SKYW6；站位图、维萨、米拉（不带相机）单人定装和四张地点空景（东廊、潮门、会客厅、套房 → urls.json 的 plates）由 v32 的 rtowm.py RT_* 生成；第 1 轮关键帧 open-key = 开场双人首帧 WV23v。
- 中转 rian_third_relay.py 8908，launchd：com.vicky.realtime.rian-third、rian-third-tunnel、rian-third-sync（隧道地址变了自动写 docs/relay.json 并推送）。口令 token.txt 不进仓库。
- 公开仓库 lyx1265897416-lab/sea-prince-almost-bride-live，Pages 从 docs/：https://lyx1265897416-lab.github.io/sea-prince-almost-bride-live/ ，带 ?k=口令&lang=zh|en 才能实时生成。推送要去掉代理（env -u HTTPS_PROXY -u HTTP_PROXY git -c http.version=HTTP/1.1 push）。
- 飞书「角色样例」5️⃣ Rian 已更新（feishu/update_pack.py、media.py）：角色简介、开场白、视频效果（新开场视频、测试链接、实时版说明）、斯凯/米拉/维萨新形象图，“米粒”改“米拉”。

## 测试（2026-11-04，本机冒烟，Vicky 还没人工测）
- 导演层干跑 tests/dry_open.py：A 配合、B 当场反问、自由输入“你为什么说我是你的新娘”都接得住（过维萨这关 → 会客厅找到米拉）。
- 冒烟 3 轮：S0113583d9（A）第 1 段东廊背景漂成海水和日光大厅、米拉挂着相机 → 加 plates、米拉母版去相机；S0128184a4（B）第 1 段末尾仍漂日光 → 地点写明没有日光；S013103190（自由输入）背景稳定，第 1 段末尾两人左右站位对调一次。每轮 2–3 分钟出片。
- 待做：Vicky 人工测后复盘；站位对调（共用模板问题）；测试记录页、即兴剧场 APP 还没加。
