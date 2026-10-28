# 用你自己的声音配音

视频的旁白是 8 段独立 WAV。只要把这 8 个文件换成你的声音，再跑一次渲染即可。

## 1. 录一段参考音

- **20–60 秒**，安静房间，手机/耳麦都行，别开混响和降噪重度处理。
- 16-bit / 44.1kHz / 单声道 WAV 最稳；MP3 也能用（脚本会用 ffmpeg 统一转成 22.05k 单声道）。
- 离麦 15–20cm，音量稳定，语气接近视频旁白（平静、偏慢）。
- 最好直接读下面 8 句里的 3–5 句，克隆出来的韵律会更贴。

## 2. 克隆（本地，RTX 4060 8GB 够推理）

| 方案 | 参考音 | 特点 | 适合 |
| --- | --- | --- | --- |
| **GPT-SoVITS** | 5s 零样本；1 分钟微调更像 | 中文社区最成熟，整合包开箱即用；8GB 推理没问题，微调要把 batch 降到 1–2 | 追求相似度，愿意花 20 分钟微调 |
| **IndexTTS / IndexTTS2** | 10–20s 零样本 | 中文韵律自然，部署相对简单 | 想快速出结果 |
| **CosyVoice2-0.5B** | 10–20s 零样本 | 0.5B 小模型，中英日韩；8GB 轻松 | 低门槛、速度快 |
| **F5-TTS** | 10–20s 零样本 | 轻量、中英双语 | 显卡紧张时 |

> 只克隆**你自己**的声音，或已获得明确授权的声源。别拿它模仿他人。

### 云端（不想折腾本地）

- 阿里云百炼「CosyVoice 声音复刻」
- 火山引擎「声音复刻」（豆包）
- MiniMax 语音克隆
- ElevenLabs Instant Voice Cloning

云端效果通常更稳，但需要把参考音上传到第三方，先看隐私条款和价格。

## 3. 生成台词

### 抖音 48 秒版（6 段）

台词在 `assets/make_video_douyin.py` 的 `SCENES` 里：

| 文件 | 台词 |
| --- | --- |
| `assets/video/douyin_voice/scene_01.wav` | 80 个 skill，一个都想不起来？ |
| `scene_02.wav` | Claude Code 用户，skills 超过十个的，继续看。 |
| `scene_03.wav` | 按住 Ctrl 加 Alt 加空格，所有技能在鼠标位置摊开。 |
| `scene_04.wav` | 滑到哪个哪个放大，滚轮翻页，松开直接写进输入框；没动就松开是取消。 |
| `scene_05.wav` | 自动扫描本地 skills，按使用频率排序；圆盘打开时滚轮会被锁住。 |
| `scene_06.wav` | Apache 二点零开源，已经上传 GitHub，链接放在评论区。 |

### 横版 89 秒版（8 段）

台词在 `assets/make_video.py` 的 `SCENES` 里，文件放
`assets/video/voice/scene_01.wav` … `scene_08.wav`。

每段开头/结尾留 0.3–0.6 秒静音，工具里不要加背景音乐或混响。

建议每段开头/结尾留 0.3–0.6 秒静音，工具里不要加背景音乐或混响。

## 4. 重渲视频

```powershell
# 抖音竖屏 48 秒
python assets/make_video_douyin.py --reuse-audio --render

# 横版 89 秒
python assets/make_video.py --reuse-audio --render
```

脚本会：
- 用 ffmpeg 把任意格式转成 22.05k 单声道；
- 按新配音时长重新计算每段画面时长（总长会随你的语速变化；抖音版会在 48 秒左右）；
- 重新混入配乐、响度标准化到 −16 LUFS。

输出分别是 `assets/video/skill-wheel-douyin-50s.mp4` 和 `assets/video/skill-wheel-intro.mp4`。

## 5. 想改台词

只改 `SCENES[i]["text"]`，然后**重新合成配音**（不要加 `--reuse-audio`，否则会沿用旧录音）：

```powershell
python assets/make_video.py --render
```

画面里的字幕/标题在各自的 `scene_*` 函数里，和台词是分开的，需要一起改。
