<h1 align="center">Rian｜人鱼王子的假新娘</h1>
<p align="center"><b>The Sea Prince's Almost Bride</b> · 女性向第三视角开放式实时互动剧</p>
<p align="center"><a href="https://lyx1265897416-lab.github.io/sea-prince-almost-bride-live/">▶ 打开体验页</a></p>

只有开场是预制的（71.9 秒）。之后每一段视频，都根据观众点的选项或自己打的一句话实时生成，故事一直往下演。

> 不带口令打开时只能看开场。实时生成要用带口令的测试链接，并且要这台 Mac 开着：中转和模型 key 都在本机，不在仓库里。

## 故事

为了找回被潮水卷走的好友米拉，斯凯跟着跳进海里，被人鱼王子雷恩救进海下王宫；守门的摄政官不放外人进来，雷恩当众说她是“我未来的新娘”。真相是普通担保和离城通行证都存在，他也想借她推掉自己的政治联姻。

## 组成

- 开场：外国人版 v9（`projects/the-sea-princes-almost-bride/制作/新版互动剧集-v32/rtow.py`、`build_rtow.py`），`docs/media/OPEN.mp4`。
- 资料包：`pack/build_pack.py` → `pack/rian_pack.json`（人物、隐藏真相、地点、K01–K12、规则）。
- 这部剧的内容：`drama_slots.py`（由 `make_slots.py` 从《今天，再喜欢我一次》那份改写）。`director.py`、`live_common.py`、`qa_guard.py`、`rian_third_relay.py` 由 `tools/realtime-third/render.py` 从第三视角共用模板合成，不要手改。
- 母版：`masters_build.py`，地址在 `masters/urls.json`。
- 播放页：`docs/index.html`（`build_site.py` 传 CDN、写开场字幕和地点字卡），待机循环 `gen_idle.py`。
