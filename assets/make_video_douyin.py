"""50s vertical (1080x1920) Douyin cut of the Skill Wheel intro.

Structure: 0-2s hook, 2-5s audience filter, 5-18s what it is,
18-34s how to use, 34-44s details, 44-50s GitHub.

    python assets/make_video_douyin.py --stills 2,10,25,40
    python assets/make_video_douyin.py --render
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QGuiApplication, QImage,
                           QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)

ASSETS = Path(__file__).resolve().parent
sys.path.insert(0, str(ASSETS))
import make_video as mw  # noqa: E402

W, H, FPS = 1080, 1920, 30
VID = ASSETS / "video"
VDIR = VID / "douyin_voice"
VOICE_RATE = mw.VOICE_RATE
ACCENT, ACCENT_SOFT, CYAN, TEXT, MUTED = mw.ACCENT, mw.ACCENT_SOFT, mw.CYAN, mw.TEXT, mw.MUTED
PANEL, RED = mw.PANEL, mw.RED

SCENES = [
    dict(key="hook", min=3.6,
         text="80 个 skill，一个都想不起来？"),
    dict(key="filter", min=5.2,
         text="Claude Code 用户，skills 超过十个的，继续看。"),
    dict(key="wheel", min=8.0,
         text="按住 Ctrl 加 Alt 加空格，所有技能在鼠标位置摊开。"),
    dict(key="interact", min=9.8,
         text="滑到哪个哪个放大，滚轮翻页，松开直接写进输入框；没动就松开是取消。"),
    dict(key="details", min=9.5,
         text="自动扫描本地 skills，按使用频率排序；圆盘打开时滚轮会被锁住。"),
    dict(key="end", min=8.5,
         text="Apache 二点零开源，已经上传 GitHub，链接放在评论区。"),
]

LABELS = ["archify", "design", "diagram", "slides", "brand", "banner", "ui ux", "community"]


# ---------------------------------------------------------------- drawing

def bg(p: QPainter, t: float):
    g = QRadialGradient(QPointF(W * 0.5, H * 0.42), 1100)
    g.setColorAt(0.0, QColor("#1C1715"))
    g.setColorAt(0.55, QColor("#171311"))
    g.setColorAt(1.0, QColor("#080706"))
    p.fillRect(QRectF(0, 0, W, H), g)
    p.setPen(QPen(QColor(255, 255, 255, 7), 1))
    for x in range(0, W, 54):
        p.drawLine(x, 0, x, H)
    for y in range(0, H, 54):
        p.drawLine(0, y, W, y)
    y = int((t * 30) % (H + 300)) - 150
    band = QLinearGradient(0, y, 0, y + 320)
    band.setColorAt(0.0, QColor(217, 119, 87, 0))
    band.setColorAt(0.5, QColor(217, 119, 87, 12))
    band.setColorAt(1.0, QColor(217, 119, 87, 0))
    p.fillRect(QRectF(0, y, W, 320), band)


def hud(p: QPainter, idx: int, t: float, total: float):
    mw.text(p, (60, 54, 520, 26), "SKILL WHEEL // DOUYIN", mw.font(15, "Consolas", spacing=3), ACCENT)
    mw.text(p, (W - 220, 54, 160, 26), f"{idx:02d} / 06", mw.font(15, "Consolas", spacing=3),
            MUTED, Qt.AlignmentFlag.AlignRight)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 20))
    p.drawRect(QRectF(60, 1818, W - 120, 3))
    p.setBrush(ACCENT)
    p.drawRect(QRectF(60, 1818, (W - 120) * mw.clamp(t / total), 3))


def caption(p: QPainter, s: str, color=TEXT, y=1540, size=44):
    mw.text(p, (40, y, W - 80, 70), s, mw.font(size, "Microsoft YaHei UI", QFont.Weight.DemiBold),
            color, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)


def keycap(p: QPainter, rect, label, pressed=1.0, size=30):
    x, y, w, h = rect
    off = 4 * pressed
    p.setPen(QPen(QColor(255, 255, 255, 30), 1))
    p.setBrush(QColor(120, 64, 46) if pressed > 0.5 else QColor(46, 40, 36))
    p.drawRoundedRect(QRectF(x, y + off, w, h), 10, 10)
    p.setPen(QPen(QColor(255, 255, 255, 18), 1))
    p.drawRoundedRect(QRectF(x, y, w, h), 10, 10)
    mw.text(p, (x, y, w, h), label, mw.font(size, "Bahnschrift"), TEXT, Qt.AlignmentFlag.AlignCenter)


def scene_hook(p: QPainter, lt: float, dur: float):
    z = 1.07 - 0.07 * mw.ease(lt / 0.45)
    p.save()
    p.translate(W / 2, H / 2)
    p.scale(z, z)
    p.translate(-W / 2, -H / 2)

    # ghost wheel
    p.setOpacity(0.22)
    mw.draw_wheel(p, QPointF(540, 1240), 430, 160, LABELS, highlight=2,
                  hover=0.6, rotation=lt * 6, label_size=17, cmd_size=9)
    p.setOpacity(1.0)

    mw.glow_text(p, QPointF(92, 470), "80 个 SKILL",
                 mw.font(118, "Bahnschrift SemiBold Condensed", QFont.Weight.Bold, 2),
                 ACCENT, QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 100), 20)
    mw.text(p, (60, 520, W - 120, 120), "一个都想不起来？",
            mw.font(88, "Microsoft YaHei UI", QFont.Weight.Bold), TEXT,
            Qt.AlignmentFlag.AlignHCenter)
    mw.text(p, (60, 690, W - 120, 46), "Claude Code 用户，别划走",
            mw.font(34, "Microsoft YaHei UI"), ACCENT_SOFT, Qt.AlignmentFlag.AlignHCenter)

    # red slash mark
    p.setPen(QPen(RED, 5))
    p.drawLine(QPointF(760, 380), QPointF(860, 480))
    p.drawLine(QPointF(860, 380), QPointF(760, 480))
    p.restore()


def scene_filter(p: QPainter, lt: float, dur: float):
    p.setOpacity(0.10)
    mw.draw_wheel(p, QPointF(540, 1430), 300, 112, LABELS, highlight=None, hover=0,
                  rotation=lt * 3, label_size=14, cmd_size=8)
    p.setOpacity(1.0)
    mw.text(p, (60, 360, W - 120, 44), "这条视频只讲给",
            mw.font(36, "Microsoft YaHei UI"), MUTED, Qt.AlignmentFlag.AlignHCenter)
    mw.text(p, (40, 430, W - 80, 120), "Claude Code 用户",
            mw.font(94, "Microsoft YaHei UI", QFont.Weight.Bold), TEXT,
            Qt.AlignmentFlag.AlignHCenter)

    card = (100, 640, 880, 230)
    mw.rounded(p, card, 16, QColor(20, 17, 16, 240), QColor(255, 255, 255, 24))
    mw.text(p, (130, 670, 500, 34), "符合任意一条", mw.font(18, "Consolas", spacing=3), MUTED)
    lines = ["skills 超过 10 个", "装了 Claude Code 扩展", "受够了记斜杠命令"]
    for i, s in enumerate(lines):
        y = 730 + i * 46
        p.setPen(QPen(ACCENT, 3))
        p.drawLine(QPointF(140, y + 12), QPointF(152, y + 24))
        p.drawLine(QPointF(152, y + 24), QPointF(172, y))
        mw.text(p, (190, y, 740, 40), s, mw.font(28, "Microsoft YaHei UI"), TEXT)

    mw.text(p, (60, 950, W - 120, 44), "其他人可以划走了",
            mw.font(30, "Microsoft YaHei UI"), MUTED, Qt.AlignmentFlag.AlignHCenter)
    mw.text(p, (60, 1060, W - 120, 50), "↓  继续看，40 秒讲完",
            mw.font(30, "Consolas"), ACCENT, Qt.AlignmentFlag.AlignHCenter)


def scene_wheel(p: QPainter, lt: float, dur: float):
    mw.text(p, (20, 230, W - 40, 80), "按住 Ctrl + Alt + Space",
            mw.font(56, "Microsoft YaHei UI", QFont.Weight.Bold), TEXT,
            Qt.AlignmentFlag.AlignHCenter)
    keycap(p, (250, 350, 170, 82), "Ctrl")
    keycap(p, (444, 350, 140, 82), "Alt")
    keycap(p, (608, 350, 230, 82), "Space")

    center = QPointF(540, 980)
    target = QPointF(center.x() - 225, center.y() - 185)
    move = mw.ease(mw.clamp((lt - 1.6) / 1.1))
    cur = QPointF(mw.lerp(center.x(), target.x(), move),
                  mw.lerp(center.y(), target.y(), move))
    mw.draw_wheel(p, center, 350, 132, LABELS,
                  highlight=2 if lt > 1.6 else None, hover=move,
                  rotation=math.sin(lt * 0.8) * 1.0, label_size=21, cmd_size=10)
    if lt > 1.6:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 40))
        p.drawEllipse(cur, 30, 30)
    mw.mouse_cursor(p, cur, 1.6)
    caption(p, "所有技能，在鼠标处摊开", TEXT, 1470, 42)


def scene_interact(p: QPainter, lt: float, dur: float):
    mw.text(p, (20, 220, W - 40, 70), "滚轮翻页 · 松开写入 · 不动取消",
            mw.font(42, "Microsoft YaHei UI", QFont.Weight.Bold), TEXT,
            Qt.AlignmentFlag.AlignHCenter)

    page2 = lt > 3.0
    labels = mw.WHEEL_PAGE2 if page2 else LABELS
    center = QPointF(540, 800)
    mw.draw_wheel(p, center, 260, 100, labels,
                  highlight=2 if lt > 4.0 else None,
                  hover=mw.ease(mw.clamp((lt - 4.0) / 0.7)),
                  label_size=17, cmd_size=9)
    mw.text(p, (440, 1070, 200, 30), "1 / 2" if not page2 else "2 / 2",
            mw.font(18, "Consolas", spacing=2), ACCENT, Qt.AlignmentFlag.AlignHCenter)

    # input bar
    bar = (80, 1220, 920, 96)
    mw.rounded(p, bar, 12, QColor(9, 8, 7, 245), QColor(255, 255, 255, 26))
    typed = "/archify " if lt > 6.4 else ""
    mw.text(p, (110, 1220, 840, 96), typed, mw.font(30, "Consolas"), TEXT)
    if typed:
        p.setPen(QPen(ACCENT, 2))
        p.drawLine(QPointF(110 + 190, 1240), QPointF(110 + 190, 1296))

    # command chip
    fly = mw.ease(mw.clamp((lt - 5.2) / 0.9))
    if fly > 0:
        fx = mw.lerp(center.x(), 500, fly)
        fy = mw.lerp(center.y() - 150, 1268, fly)
        mw.rounded(p, (fx - 120, fy - 30, 240, 60), 8, QColor(217, 119, 87, 235))
        mw.text(p, (fx - 120, fy - 30, 240, 60), "/archify ",
                mw.font(24, "Consolas"), QColor("#1A1210"), Qt.AlignmentFlag.AlignCenter)

    if lt < 3.0:
        caption(p, "滚轮  =  翻页", ACCENT_SOFT, 1450, 40)
    elif lt < 7.0:
        caption(p, "松开  =  写入 /skill", TEXT, 1450, 40)
    else:
        caption(p, "鼠标没动  =  取消", RED, 1450, 40)


def scene_details(p: QPainter, lt: float, dur: float):
    mw.text(p, (20, 200, W - 40, 44), "自动读取 · 按使用频率排序",
            mw.font(40, "Microsoft YaHei UI", QFont.Weight.Bold), TEXT,
            Qt.AlignmentFlag.AlignHCenter)
    mw.text(p, (60, 270, W - 120, 30), "~/.claude/skills/*/SKILL.md",
            mw.font(19, "Consolas"), CYAN, Qt.AlignmentFlag.AlignHCenter)

    rows = [("requirement-clarification", 0.92, True), ("archify", 0.78, True),
            ("android-emulator-deploy", 0.55, False)]
    for i, (name, val, pinned) in enumerate(rows):
        y = 350 + i * 96
        grow = mw.ease(mw.clamp((lt - 0.3 - i * 0.2) / 1.0))
        mw.text(p, (80, y, 740, 30), ("◆ " if pinned else "  ") + name,
                mw.font(22, "Consolas"), ACCENT_SOFT if pinned else TEXT)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawRoundedRect(QRectF(80, y + 40, 900, 10), 5, 5)
        p.setBrush(ACCENT if pinned else QColor(255, 255, 255, 80))
        p.drawRoundedRect(QRectF(80, y + 40, 900 * val * grow, 10), 5, 5)

    # mini VS Code + lock
    wx, wy, ww, wh = 60, 760, 960, 380
    mw.rounded(p, (wx, wy, ww, wh), 12, QColor(16, 16, 18, 245), QColor(255, 255, 255, 24))
    mw.rounded(p, (wx, wy, ww, 38), 12, QColor(28, 28, 31, 255))
    for i, c in enumerate(("#E05B4B", "#E0B84B", "#5BBE6B")):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(c))
        p.drawEllipse(QPointF(wx + 26 + i * 20, wy + 19), 5, 5)
    for i in range(11):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 22 if i % 4 else 40))
        p.drawRoundedRect(QRectF(wx + 34, wy + 70 + i * 26, 420 - (i * 41) % 170, 7), 4, 4)
    # wheel hint
    mw.draw_wheel(p, QPointF(wx + 720, wy + 200), 130, 54, LABELS,
                  highlight=2, hover=0, label_size=9, cmd_size=6)
    # lock
    p.setPen(QPen(CYAN, 3))
    p.setBrush(QColor(0, 0, 0, 0))
    p.drawRoundedRect(QRectF(wx + ww - 92, wy + 72, 52, 42), 6, 6)
    p.drawArc(QRectF(wx + ww - 82, wy + 46, 32, 44), 0, 180 * 16)
    mw.text(p, (wx + ww - 300, wy + wh - 44, 260, 26), "SCROLL LOCKED",
            mw.font(13, "Consolas", spacing=2), CYAN, Qt.AlignmentFlag.AlignRight)

    caption(p, "圆盘打开时，滚轮被锁住", CYAN, 1240, 38)
    caption(p, "松开后恢复正常滚动", MUTED, 1310, 30)


def scene_end(p: QPainter, lt: float, dur: float):
    mw.glow_text(p, QPointF(80, 430), "GitHub 已上传",
                 mw.font(96, "Microsoft YaHei UI", QFont.Weight.Bold),
                 TEXT, QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 90), 18)

    card = (70, 540, 940, 470)
    mw.rounded(p, card, 18, QColor(18, 16, 15, 245), QColor(255, 255, 255, 30))
    mw.text(p, (110, 570, 800, 26), "GITHUB / REPOSITORY", mw.font(14, "Consolas", spacing=3), MUTED)
    mw.text(p, (110, 610, 860, 64), "claude-skill-wheel",
            mw.font(52, "Bahnschrift SemiBold"), TEXT)
    mw.text(p, (110, 680, 860, 34), "A radial skill picker for Claude Code",
            mw.font(20, "Consolas"), MUTED)

    badges = [("Apache-2.0", ACCENT), ("Windows", CYAN), ("v0.1.1", MUTED)]
    bx = 110
    for name, color in badges:
        w = 40 + len(name) * 14
        mw.rounded(p, (bx, 740, w, 38), 19, QColor(255, 255, 255, 12), QColor(255, 255, 255, 26))
        mw.text(p, (bx, 740, w, 38), name, mw.font(15, "Consolas"), color, Qt.AlignmentFlag.AlignCenter)
        bx += w + 14

    clicked = lt > 2.0
    mw.rounded(p, (110, 820, 300, 66), 10,
               QColor(217, 119, 87, 235) if clicked else QColor(255, 255, 255, 16),
               QColor(217, 119, 87, 255), 1.5)
    mw.text(p, (110, 820, 300, 66), "★  Starred" if clicked else "★  Star",
            mw.font(22, "Microsoft YaHei UI"), QColor("#1A1210") if clicked else TEXT,
            Qt.AlignmentFlag.AlignCenter)

    mw.text(p, (60, 1120, W - 120, 60), "链接在评论区",
            mw.font(58, "Microsoft YaHei UI", QFont.Weight.Bold), ACCENT_SOFT,
            Qt.AlignmentFlag.AlignHCenter)
    mw.text(p, (60, 1190, W - 120, 30), "WELCOME TO STAR · ISSUE · PR",
            mw.font(16, "Consolas", spacing=3), MUTED, Qt.AlignmentFlag.AlignHCenter)

    # arrow to the comment area
    ax, ay = 860, 1280
    p.setPen(QPen(ACCENT, 4))
    p.drawLine(QPointF(ax, ay), QPointF(ax + 90, ay + 90))
    p.drawLine(QPointF(ax + 90, ay + 90), QPointF(ax + 40, ay + 86))
    p.drawLine(QPointF(ax + 90, ay + 90), QPointF(ax + 86, ay + 40))


SCENE_FN = {"hook": scene_hook, "filter": scene_filter, "wheel": scene_wheel,
            "interact": scene_interact, "details": scene_details, "end": scene_end}


# ---------------------------------------------------------------- audio

def synth_voice():
    VDIR.mkdir(parents=True, exist_ok=True)
    items = [{"file": str(VDIR / f"scene_{i+1:02d}.wav"), "text": sc["text"]}
             for i, sc in enumerate(SCENES)]
    manifest = VID / "douyin_voice_manifest.json"
    manifest.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    ps = (
        "Add-Type -AssemblyName System.Speech\n"
        f"$m = Get-Content -Raw -Encoding UTF8 '{manifest}' | ConvertFrom-Json\n"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "$s.SelectVoice('Microsoft Huihui Desktop')\n"
        "$s.Rate = 1\n$s.Volume = 100\n"
        "foreach ($i in $m) { $s.SetOutputToWaveFile($i.file); $s.Speak($i.text) }\n"
        "$s.Dispose()\n"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    return items


def build_timeline(items):
    out, t = [], 0.05
    for sc, item in zip(SCENES, items):
        vd = len(mw.decode_voice(Path(item["file"]))) / VOICE_RATE
        dur = max(sc["min"], vd + 0.55)
        out.append({"key": sc["key"], "start": t, "dur": dur, "voice": vd, "file": item["file"]})
        t += dur
    return out


def build_voice(timeline, total):
    n = int(total * VOICE_RATE)
    buf = np.zeros(n, dtype=np.int16)
    for sc in timeline:
        data = mw.decode_voice(Path(sc["file"]))
        s0 = int((sc["start"] + 0.22) * VOICE_RATE)
        s1 = min(n, s0 + len(data))
        buf[s0:s1] = data[:s1 - s0]
    path = VID / "douyin_voice_full.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(VOICE_RATE)
        w.writeframes(buf.tobytes())
    return path


# ---------------------------------------------------------------- video

def frame(t, timeline, total):
    img = QImage(W, H, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.black)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    idx = 0
    for i, sc in enumerate(timeline):
        if t >= sc["start"]:
            idx = i
    sc = timeline[idx]
    lt = t - sc["start"]

    bg(p, t)
    SCENE_FN[sc["key"]](p, lt, sc["dur"])
    hud(p, idx + 1, t, total)

    fin = 0.18
    a = 1.0
    if idx > 0 and lt < fin:
        a = lt / fin
    rem = sc["dur"] - lt
    if rem < fin:
        a = min(a, max(0.0, rem / fin))
    if a < 1:
        p.fillRect(QRectF(0, 0, W, H), QColor(0, 0, 0, int(255 * (1 - a))))
    p.end()
    return img


def encode(timeline, total, voice, music, out):
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(voice), "-i", str(music),
        "-filter_complex",
        "[1:a]aresample=44100,volume=1.0[a1];"
        "[2:a]aresample=44100,volume=0.15[a2];"
        "[a1][a2]amix=inputs=2:duration=longest:dropout_transition=0,"
        "loudnorm=I=-16:TP=-1.5:LRA=11[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-t", f"{total:.2f}", str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = int(math.ceil(total * FPS))
    for i in range(frames):
        img = frame(i / FPS, timeline, total)
        proc.stdin.write(img.constBits().tobytes())
        if i % 150 == 0:
            print(f"frame {i}/{frames}", flush=True)
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise SystemExit(f"ffmpeg failed {proc.returncode}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", default="")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--reuse-audio", action="store_true")
    args = ap.parse_args()

    app = QGuiApplication(sys.argv[:1])
    VID.mkdir(parents=True, exist_ok=True)

    if args.reuse_audio and (VID / "douyin_voice_manifest.json").exists():
        items = json.loads((VID / "douyin_voice_manifest.json").read_text(encoding="utf-8"))
    else:
        print("synthesizing voice...")
        items = synth_voice()

    timeline = build_timeline(items)
    total = timeline[-1]["start"] + timeline[-1]["dur"] + 1.0
    for sc in timeline:
        print(f"{sc['key']:<9} start={sc['start']:6.2f} dur={sc['dur']:5.2f} voice={sc['voice']:5.2f}")
    print(f"total {total:.2f}s")

    voice = build_voice(timeline, total)

    if args.stills:
        out = VID / "douyin_stills"
        out.mkdir(exist_ok=True)
        for tt in [float(x) for x in args.stills.split(",") if x]:
            frame(tt, timeline, total).save(str(out / f"still_{tt:04.1f}.png"), "PNG")
            print("still", tt)
        return 0

    music = mw.make_music(total + 0.4, "music_douyin.wav")
    if args.render:
        out = VID / "skill-wheel-douyin-50s.mp4"
        encode(timeline, total, voice, music, out)
        print("video ->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
