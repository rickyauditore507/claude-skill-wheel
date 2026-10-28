"""Build the ~90s Skill Wheel intro video.

Everything is generated locally:
  * voice  — Windows SAPI (Microsoft Huihui Desktop, zh-CN)
  * music  — numpy synth (no external assets)
  * frames — QPainter, piped into ffmpeg as rawvideo

Usage:
  python assets/make_video.py --stills 5,20,40,60,80
  python assets/make_video.py --render
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QGuiApplication, QImage,
                           QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)

ROOT = Path(__file__).resolve().parent.parent
VID = ROOT / "assets" / "video"
FRAMES_W, FRAMES_H, FPS = 1920, 1080, 30

ACCENT = QColor("#D97757")
ACCENT_SOFT = QColor("#F2B59E")
CYAN = QColor("#6FE3E1")
TEXT = QColor("#F5F0EA")
MUTED = QColor("#8F867E")
BG0 = QColor("#080706")
BG1 = QColor("#171311")
PANEL = QColor("#141110")
RED = QColor("#E05B4B")

SCENES = [
    dict(key="title", min=6.0,
         text="这是 Skill Wheel，一个为 Claude Code 打造的技能圆盘。"),
    dict(key="pain", min=7.5,
         text="skills 越装越多，靠记名字和斜杠命令，找起来越来越慢。"),
    dict(key="wheel", min=10.5,
         text="按住 Ctrl 加 Alt 加空格，圆盘在光标处展开。滑到哪个技能，哪个就放大。"),
    dict(key="interact", min=10.5,
         text="滚轮翻页；松开按键，命令直接写进输入框；鼠标没动就松开，就是取消。"),
    dict(key="discover", min=10.5,
         text="它自动读取你安装的 skills，按使用频率排序，还能置顶、隐藏、换主题。"),
    dict(key="vscode", min=10.5,
         text="配套的 VS Code 扩展负责启停和聚焦；圆盘打开时，滚轮不会滚动底下页面。"),
    dict(key="oss", min=7.0,
         text="项目使用 Apache 二点零开源，支持 Windows。"),
    dict(key="github", min=9.5,
         text="现在已经上传到 GitHub，链接放在评论区，欢迎试用和提 issue。"),
]

WHEEL_LABELS = ["archify", "design", "diagram", "slides", "brand", "banner", "ui ux", "community"]
WHEEL_PAGE2 = ["slides", "ui ux", "frontend", "diagram", "brand", "banner", "preview", "community"]


# ---------------------------------------------------------------- helpers

def ease(x: float) -> float:
    return 1 - (1 - max(0.0, min(1.0, x))) ** 3


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def lerp(a, b, t):
    return a + (b - a) * t


def font(size: int, family="Microsoft YaHei UI", weight=QFont.Weight.Normal, spacing=0.0):
    f = QFont(family)
    f.setPixelSize(int(size))
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def text(p: QPainter, rect, s, f, color, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter):
    p.setFont(f)
    p.setPen(color)
    p.drawText(QRectF(*rect), align, s)


def glow_text(p: QPainter, pos: QPointF, s, f, color, glow, radius=16):
    p.setFont(f)
    path = QPainterPath()
    path.addText(pos, f, s)
    for w, a in ((radius, 14), (radius * 0.55, 24), (radius * 0.25, 38)):
        pen = QPen(QColor(glow.red(), glow.green(), glow.blue(), a))
        pen.setWidthF(w)
        p.strokePath(path, pen)
    p.fillPath(path, QColor(color))


def rounded(p: QPainter, rect, radius, fill, border=None, border_w=1.0):
    p.setPen(QPen(border, border_w) if border else Qt.PenStyle.NoPen)
    p.setBrush(fill)
    p.drawRoundedRect(QRectF(*rect), radius, radius)


def wedge_path(center: QPointF, r_in, r_out, a0, a1):
    steps = max(10, int(abs(a1 - a0) / 2))
    path = QPainterPath()

    def pt(r, ang):
        rad = math.radians(ang)
        return QPointF(center.x() + r * math.cos(rad), center.y() + r * math.sin(rad))

    path.moveTo(pt(r_out, a0))
    for i in range(1, steps + 1):
        path.lineTo(pt(r_out, a0 + (a1 - a0) * i / steps))
    for i in range(steps, -1, -1):
        path.lineTo(pt(r_in, a0 + (a1 - a0) * i / steps))
    path.closeSubpath()
    return path


def background(p: QPainter, t: float):
    g = QRadialGradient(QPointF(FRAMES_W * 0.5, FRAMES_H * 0.42), 1100)
    g.setColorAt(0.0, QColor("#1C1715"))
    g.setColorAt(0.55, BG1)
    g.setColorAt(1.0, BG0)
    p.fillRect(QRectF(0, 0, FRAMES_W, FRAMES_H), g)

    p.setPen(QPen(QColor(255, 255, 255, 7), 1))
    for x in range(0, FRAMES_W, 64):
        p.drawLine(x, 0, x, FRAMES_H)
    for y in range(0, FRAMES_H, 64):
        p.drawLine(0, y, FRAMES_W, y)

    # slow scan glow
    y = int((t * 26) % (FRAMES_H + 300)) - 150
    band = QLinearGradient(0, y, 0, y + 300)
    band.setColorAt(0.0, QColor(217, 119, 87, 0))
    band.setColorAt(0.5, QColor(217, 119, 87, 10))
    band.setColorAt(1.0, QColor(217, 119, 87, 0))
    p.fillRect(QRectF(0, y, FRAMES_W, 300), band)


def hud(p: QPainter, scene_no: int, t: float, total: float):
    text(p, (72, 42, 500, 26), "SKILL WHEEL // INTRO", font(15, "Consolas", spacing=3), ACCENT)
    text(p, (FRAMES_W - 250, 42, 180, 26), f"{scene_no:02d} / 08",
         font(15, "Consolas", spacing=3), MUTED, Qt.AlignmentFlag.AlignRight)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 18))
    p.drawRect(QRectF(72, FRAMES_H - 40, FRAMES_W - 144, 2))
    p.setBrush(ACCENT)
    p.drawRect(QRectF(72, FRAMES_H - 40, (FRAMES_W - 144) * clamp(t / total), 2))


def mouse_cursor(p: QPainter, pos: QPointF, scale=1.0, color=TEXT):
    s = 12 * scale
    path = QPainterPath()
    path.moveTo(pos.x(), pos.y())
    path.lineTo(pos.x() + s * 0.65, pos.y() + s * 1.55)
    path.lineTo(pos.x() + s * 0.95, pos.y() + s * 0.95)
    path.lineTo(pos.x() + s * 1.6, pos.y() + s * 0.9)
    path.closeSubpath()
    p.setPen(QPen(QColor(0, 0, 0, 120), 2))
    p.setBrush(color)
    p.drawPath(path)


# ---------------------------------------------------------------- scenes

def scene_title(p: QPainter, lt: float, dur: float):
    a = ease(lt / 0.8)
    center = QPointF(FRAMES_W / 2, 520)

    p.save()
    p.translate(0, (1 - a) * 24)
    p.setOpacity(a)

    # HUD rings
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 20), 1))
    p.drawEllipse(center, 360, 360)
    p.setPen(QPen(QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 90), 2))
    for start in (0, 120, 240):
        p.drawArc(QRectF(center.x() - 360, center.y() - 360, 720, 720),
                  int((start + lt * 22) * 16), int(36 * 16))
    p.setPen(QPen(QColor(CYAN.red(), CYAN.green(), CYAN.blue(), 60), 1.4))
    p.drawArc(QRectF(center.x() - 392, center.y() - 392, 784, 784),
              int((180 - lt * 14) * 16), int(52 * 16))

    tf = font(150, "Bahnschrift SemiBold Condensed", QFont.Weight.Bold, 2)
    tw = QFontMetrics(tf).horizontalAdvance("SKILL WHEEL")
    glow_text(p, QPointF((FRAMES_W - tw) / 2, 470), "SKILL WHEEL", tf,
              TEXT, QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 80), 22)
    text(p, (0, 520, FRAMES_W, 60), "Claude Code 技能圆盘",
         font(42, "Microsoft YaHei UI", QFont.Weight.DemiBold), ACCENT_SOFT,
         Qt.AlignmentFlag.AlignHCenter)
    text(p, (0, 600, FRAMES_W, 30), "RADIAL SKILL PICKER  ·  CTRL + ALT + SPACE",
         font(17, "Consolas", spacing=3), MUTED, Qt.AlignmentFlag.AlignHCenter)
    p.restore()


def scene_pain(p: QPainter, lt: float, dur: float):
    text(p, (96, 130, 1100, 90), "越装越多，越难找", font(72, "Microsoft YaHei UI", QFont.Weight.Bold), TEXT)
    text(p, (100, 216, 900, 34), "SKILLS + COMMANDS + MEMORY", font(17, "Consolas", spacing=3), ACCENT)

    names = ["archify", "design", "diagram", "slides", "brand", "banner",
             "frontend-design", "ui-ux-pro-max", "competitor", "android",
             "requirement", "code-review", "simplify", "security"]
    x0, y0, w, h = 100, 290, 520, 40
    for i, name in enumerate(names):
        y = y0 + i * 50 - (lt * 40) % 50
        if y < y0 - 20 or y > 830:
            continue
        hot = i == 6
        rounded(p, (x0, y, w, h), 6,
                QColor(30, 26, 24, 230) if not hot else QColor(60, 32, 28, 240),
                QColor(255, 255, 255, 18), 1)
        text(p, (x0 + 16, y, w - 32, h), "/" + name,
             font(18, "Consolas"), ACCENT_SOFT if hot else TEXT)
        if hot:
            text(p, (x0 + w - 150, y, 134, h), "找不到 ✕", font(16, "Microsoft YaHei UI"),
                 RED, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    # counter
    n = int(lerp(16, 87, ease(min(1.0, lt / 5.0))))
    glow_text(p, QPointF(1120, 520), str(n),
              font(190, "Bahnschrift SemiBold Condensed", QFont.Weight.Bold, 2),
              ACCENT, QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 70), 20)
    text(p, (1120, 540, 600, 40), "个 skills 在本地", font(24, "Microsoft YaHei UI"), MUTED)
    text(p, (1120, 640, 620, 80), "记名字？翻面板？",
         font(38, "Microsoft YaHei UI", QFont.Weight.DemiBold), TEXT)


def draw_wheel(p: QPainter, center: QPointF, r_out: float, r_in: float,
               labels, highlight=None, hover=0.0, rotation=0.0, hub=True,
               label_size=20, cmd_size=11):
    n = len(labels)
    step = 360.0 / n
    start = -90.0 - step * n / 2.0 + rotation
    gap = 2.2
    for i, name in enumerate(labels):
        a0, a1 = start + i * step + gap / 2, start + (i + 1) * step - gap / 2
        hot = (highlight == i)
        h = hover if hot else 0.0
        path = wedge_path(center, r_in - 6 * h, r_out + 16 * h, a0, a1)
        if h > 0.02:
            p.setPen(QPen(QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), int(50 * h)), 14))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(wedge_path(center, r_in - 12 * h, r_out + 22 * h, a0 - 0.6, a1 + 0.6))
        grad = QLinearGradient(center.x(), center.y(),
                               center.x() + math.cos(math.radians((a0 + a1) / 2)) * r_out,
                               center.y() + math.sin(math.radians((a0 + a1) / 2)) * r_out)
        if hot:
            grad.setColorAt(0.0, QColor("#3A2A22"))
            grad.setColorAt(0.55, QColor("#8C5039"))
            grad.setColorAt(1.0, ACCENT)
            border = QColor(255, 255, 255, 90)
        else:
            grad.setColorAt(0.0, QColor("#1D1A18"))
            grad.setColorAt(1.0, QColor("#2C2825"))
            border = QColor(255, 255, 255, 20)
        p.setPen(QPen(border, 1))
        p.setBrush(grad)
        p.drawPath(path)

        mid = math.radians((a0 + a1) / 2)
        lr = (r_in + r_out) / 2
        x = center.x() + lr * math.cos(mid)
        y = center.y() + lr * math.sin(mid)
        width = max(70, r_out * math.radians(step) * 0.82)
        f = font(label_size + 3 * h, "Bahnschrift SemiBold", QFont.Weight.DemiBold)
        fm = QFontMetrics(f)
        label = fm.elidedText(name.upper(), Qt.TextElideMode.ElideRight, int(width))
        text(p, (x - width / 2, y - 14, width, 26), label, f,
             QColor("#FFFFFF") if hot else TEXT, Qt.AlignmentFlag.AlignHCenter)
        text(p, (x - width / 2, y + 13, width, 20), "/" + name.replace(" ", "-"),
             font(cmd_size, "Consolas"), ACCENT_SOFT if hot else MUTED,
             Qt.AlignmentFlag.AlignHCenter)

    if hub:
        p.setPen(QPen(QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 130), 1.2))
        p.setBrush(QColor("#0D0B0A"))
        p.drawEllipse(center, r_in - 14, r_in - 14)
        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
        p.drawEllipse(center, r_in - 2, r_in - 2)
        text(p, (center.x() - r_in, center.y() - r_in * 0.48, r_in * 2, r_in * 0.34),
             "SKILL", font(r_in * 0.30, "Bahnschrift SemiBold Condensed", QFont.Weight.Bold, 1),
             TEXT, Qt.AlignmentFlag.AlignHCenter)
        text(p, (center.x() - r_in, center.y() - r_in * 0.14, r_in * 2, r_in * 0.34),
             "WHEEL", font(r_in * 0.30, "Bahnschrift SemiBold Condensed", QFont.Weight.Bold, 1),
             ACCENT, Qt.AlignmentFlag.AlignHCenter)


def keycap(p: QPainter, rect, label, pressed=0.0, size=28):
    x, y, w, h = rect
    off = 4 * pressed
    p.setPen(QPen(QColor(255, 255, 255, 30), 1))
    p.setBrush(QColor(46, 40, 36) if pressed < 0.5 else QColor(120, 64, 46))
    p.drawRoundedRect(QRectF(x, y + off, w, h), 8, 8)
    p.setPen(QPen(QColor(255, 255, 255, 18), 1))
    p.drawRoundedRect(QRectF(x, y, w, h), 8, 8)
    text(p, (x, y, w, h), label, font(size, "Bahnschrift"), TEXT,
         Qt.AlignmentFlag.AlignCenter)


def scene_wheel(p: QPainter, lt: float, dur: float):
    text(p, (0, 70, FRAMES_W, 60), "按住  Ctrl + Alt + Space",
         font(52, "Microsoft YaHei UI", QFont.Weight.Bold), TEXT,
         Qt.AlignmentFlag.AlignHCenter)
    text(p, (0, 134, FRAMES_W, 30), "THE RING OPENS AT YOUR CURSOR",
         font(16, "Consolas", spacing=3), ACCENT, Qt.AlignmentFlag.AlignHCenter)

    center = QPointF(960, 600)
    press = [ease((lt - 0.5) / 0.25), ease((lt - 0.8) / 0.25), ease((lt - 1.1) / 0.25)]
    keycap(p, (700, 900, 150, 70), "Ctrl", press[0])
    keycap(p, (866, 900, 130, 70), "Alt", press[1])
    keycap(p, (1012, 900, 230, 70), "Space", press[2])

    # cursor path from hub to the diagram wedge
    target = QPointF(center.x() - 210, center.y() - 170)
    move = ease(min(1.0, max(0.0, (lt - 1.8) / 1.2)))
    cur = QPointF(lerp(center.x(), target.x(), move), lerp(center.y(), target.y(), move))
    hover = move

    draw_wheel(p, center, 300, 118, WHEEL_LABELS,
               highlight=2 if lt > 1.8 else None, hover=hover,
               rotation=math.sin(lt * 0.6) * 1.2)
    if lt > 1.8:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 40))
        p.drawEllipse(cur, 26, 26)
    mouse_cursor(p, cur, 1.3)
    text(p, (0, 985, FRAMES_W, 30), "滑到扇形 · 放大 · 中心显示描述",
         font(18, "Microsoft YaHei UI"), MUTED, Qt.AlignmentFlag.AlignHCenter)


def scene_interact(p: QPainter, lt: float, dur: float):
    text(p, (0, 60, FRAMES_W, 54), "滚轮翻页 · 松开写入 · 不动取消",
         font(44, "Microsoft YaHei UI", QFont.Weight.Bold), TEXT,
         Qt.AlignmentFlag.AlignHCenter)

    page2 = lt > 2.4
    labels = WHEEL_PAGE2 if page2 else WHEEL_LABELS
    center = QPointF(600, 560)
    draw_wheel(p, center, 250, 100, labels,
               highlight=2 if lt > 2.8 else None,
               hover=ease(min(1.0, max(0.0, (lt - 2.8) / 0.8))),
               rotation=0.0, label_size=17, cmd_size=10)

    # page badge
    text(p, (470, 828, 260, 30), "1 / 2" if not page2 else "2 / 2",
         font(18, "Consolas", spacing=2), ACCENT, Qt.AlignmentFlag.AlignHCenter)

    # mouse-wheel icon
    mx, my = 600, 900
    p.setPen(QPen(QColor(255, 255, 255, 60), 2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(mx - 22, my - 34, 44, 68), 20, 20)
    p.setPen(QPen(ACCENT, 3))
    dy = math.sin(lt * 5) * 8
    p.drawLine(QPointF(mx, my - 16 + dy), QPointF(mx, my - 4 + dy))
    text(p, (mx - 150, my + 40, 300, 26), "SCROLL", font(13, "Consolas", spacing=3),
         MUTED, Qt.AlignmentFlag.AlignHCenter)

    # right cards
    x = 1010
    rounded(p, (x, 300, 780, 150), 12, QColor(20, 17, 16, 235), QColor(255, 255, 255, 20))
    text(p, (x + 28, 318, 500, 26), "松开按键", font(16, "Consolas", spacing=3), ACCENT)
    text(p, (x + 28, 350, 720, 80), "→  /archify ", font(34, "Consolas"), TEXT)

    rounded(p, (x, 480, 780, 150), 12, QColor(20, 17, 16, 235), QColor(255, 255, 255, 20))
    text(p, (x + 28, 498, 500, 26), "鼠标没动就松开", font(16, "Consolas", spacing=3), MUTED)
    text(p, (x + 28, 530, 720, 80), "取消  ·  不会误选", font(34, "Microsoft YaHei UI"), RED)

    # command flies from the wheel
    fly = ease(min(1.0, max(0.0, (lt - 4.2) / 0.9)))
    if fly > 0:
        fx = lerp(center.x(), x + 360, fly)
        fy = lerp(center.y() - 140, 700, fly)
        rounded(p, (fx - 120, fy - 26, 240, 52), 8, QColor(217, 119, 87, 230))
        text(p, (fx - 120, fy - 26, 240, 52), "/archify ", font(22, "Consolas"),
             QColor("#1A1210"), Qt.AlignmentFlag.AlignCenter)

    # input bar
    rounded(p, (x, 700, 780, 78), 10, QColor(10, 9, 8, 240), QColor(255, 255, 255, 28))
    typed = "/archify " if lt > 5.0 else ""
    text(p, (x + 22, 700, 730, 78), typed, font(24, "Consolas"), TEXT)
    if lt > 5.0:
        p.setPen(QPen(ACCENT, 2))
        p.drawLine(QPointF(x + 22 + 150, 718), QPointF(x + 22 + 150, 760))


def scene_discover(p: QPainter, lt: float, dur: float):
    text(p, (96, 90, 1200, 70), "自动读取，按使用频率排序",
         font(54, "Microsoft YaHei UI", QFont.Weight.Bold), TEXT)
    text(p, (100, 160, 1100, 30), "~/.claude/skills/*/SKILL.md",
         font(18, "Consolas"), CYAN)

    # usage bars
    rows = [("requirement-clarification", 0.92, True), ("archify", 0.78, True),
            ("android-emulator-deploy", 0.55, False), ("ui-ux-pro-max", 0.38, False)]
    for i, (name, val, pinned) in enumerate(rows):
        y = 250 + i * 92
        grow = ease(min(1.0, max(0.0, (lt - 0.6 - i * 0.25) / 1.1)))
        text(p, (100, y, 520, 26), ("◆ " if pinned else "  ") + name,
             font(20, "Consolas"), ACCENT_SOFT if pinned else TEXT)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 14))
        p.drawRoundedRect(QRectF(100, y + 36, 620, 10), 5, 5)
        p.setBrush(ACCENT if pinned else QColor(255, 255, 255, 70))
        p.drawRoundedRect(QRectF(100, y + 36, 620 * val * grow, 10), 5, 5)

    text(p, (100, 660, 700, 30), "PINS · EXCLUDE · THEME · HOTKEY",
         font(15, "Consolas", spacing=3), MUTED)

    # mini wheel + scan
    center = QPointF(1440, 500)
    draw_wheel(p, center, 210, 84, WHEEL_LABELS, highlight=None, hover=0,
               rotation=math.sin(lt * 0.5) * 3, label_size=14, cmd_size=9)

    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 24), 1))
    p.drawEllipse(center, 244, 244)
    p.setPen(QPen(QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 110), 2, Qt.PenStyle.DashLine))
    for k in range(4):
        p.drawArc(QRectF(center.x() - 244, center.y() - 244, 488, 488),
                  int((k * 90 + lt * 18) * 16), int(46 * 16))

    scan_y = center.y() - 210 + (lt * 120) % 420
    p.setPen(QPen(QColor(CYAN.red(), CYAN.green(), CYAN.blue(), 150), 2))
    p.drawLine(QPointF(center.x() - 205, scan_y), QPointF(center.x() + 205, scan_y))
    p.setBrush(QColor(CYAN.red(), CYAN.green(), CYAN.blue(), 40))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRect(QRectF(center.x() - 205, scan_y - 10, 410, 20))

    text(p, (center.x() - 300, center.y() + 270, 600, 28), "SCANNING  ·  16 FOUND",
         font(15, "Consolas", spacing=3), CYAN, Qt.AlignmentFlag.AlignHCenter)


def scene_vscode(p: QPainter, lt: float, dur: float):
    text(p, (0, 56, FRAMES_W, 52), "VS Code 里，滚轮不会乱跑",
         font(46, "Microsoft YaHei UI", QFont.Weight.Bold), TEXT,
         Qt.AlignmentFlag.AlignHCenter)

    # window
    wx, wy, ww, wh = 140, 150, 1640, 780
    rounded(p, (wx, wy, ww, wh), 10, QColor(18, 18, 20, 245), QColor(255, 255, 255, 26))
    rounded(p, (wx, wy, ww, 44), 10, QColor(28, 28, 31, 255))
    for i, c in enumerate(("#E05B4B", "#E0B84B", "#5BBE6B")):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(c))
        p.drawEllipse(QPointF(wx + 24 + i * 22, wy + 22), 6, 6)
    text(p, (wx + 100, wy, 600, 44), "claude-skill-wheel — Visual Studio Code",
         font(14, "Consolas"), MUTED)

    # sidebar
    rounded(p, (wx, wy + 44, 220, wh - 44), 0, QColor(14, 14, 16, 255))
    for i in range(9):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 22 if i % 3 else 40))
        p.drawRoundedRect(QRectF(wx + 24, wy + 80 + i * 34, 150 - (i % 4) * 14, 8), 4, 4)

    # editor lines
    for i in range(16):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 20 if i % 5 else 34))
        p.drawRoundedRect(QRectF(wx + 270, wy + 96 + i * 32, 420 - (i * 37) % 190, 8), 4, 4)

    # chat panel
    rounded(p, (wx + 760, wy + 44, 660, wh - 44), 0, QColor(16, 16, 18, 255))
    text(p, (wx + 790, wy + 70, 400, 30), "Claude Code", font(18, "Microsoft YaHei UI"),
         TEXT)
    for i in range(5):
        rounded(p, (wx + 790, wy + 120 + i * 74, 480 - (i % 2) * 90, 44), 8,
                QColor(255, 255, 255, 16))
    rounded(p, (wx + 790, wy + wh - 120, 580, 56), 8, QColor(10, 9, 8, 255),
            QColor(255, 255, 255, 28))
    if lt > 2.0:
        text(p, (wx + 810, wy + wh - 120, 540, 56), "/diagram-design ",
             font(20, "Consolas"), TEXT)

    # wheel overlay
    draw_wheel(p, QPointF(wx + 1180, wy + 420), 200, 82, WHEEL_LABELS,
               highlight=2, hover=ease(min(1.0, max(0.0, (lt - 1.2) / 0.8))),
               rotation=0, label_size=13, cmd_size=8)

    # scroll lock
    sx, sy = wx + ww - 36, wy + 80
    p.setPen(QPen(QColor(255, 255, 255, 40), 1))
    p.setBrush(QColor(255, 255, 255, 16))
    p.drawRoundedRect(QRectF(sx, sy, 12, 220), 6, 6)
    p.setBrush(ACCENT)
    p.drawRoundedRect(QRectF(sx + 2, sy + 20, 8, 70), 4, 4)
    p.setPen(QPen(CYAN, 2))
    p.drawLine(QPointF(sx - 8, sy + 120), QPointF(sx + 20, sy + 120))
    text(p, (sx - 170, sy + 140, 160, 26), "SCROLL LOCKED", font(12, "Consolas", spacing=2),
         CYAN, Qt.AlignmentFlag.AlignRight)

    # status bar
    rounded(p, (wx, wy + wh - 30, ww, 30), 0, QColor(217, 119, 87, 220))
    text(p, (wx + 20, wy + wh - 30, 500, 30), "● Skill Wheel", font(13, "Consolas"),
         QColor("#1A1210"))

    text(p, (0, 985, FRAMES_W, 28), "VS CODE EXTENSION  ·  SYSTEM-WIDE SCROLL SUPPRESSION",
         font(15, "Consolas", spacing=2), MUTED, Qt.AlignmentFlag.AlignHCenter)


def scene_oss(p: QPainter, lt: float, dur: float):
    text(p, (0, 120, FRAMES_W, 80), "OPEN SOURCE", font(86, "Bahnschrift SemiBold Condensed",
                                                        QFont.Weight.Bold, 2),
         TEXT, Qt.AlignmentFlag.AlignHCenter)
    text(p, (0, 210, FRAMES_W, 40), "APACHE-2.0  ·  WINDOWS  ·  VS CODE + CLAUDE CODE",
         font(18, "Consolas", spacing=3), ACCENT, Qt.AlignmentFlag.AlignHCenter)

    items = [("Apache-2.0", "LICENSE"), ("PySide6 / Qt", "LGPL-3.0"),
             ("pynput", "LGPL-3.0"), ("CI", "GitHub Actions")]
    for i, (a, b) in enumerate(items):
        x = 260 + i * 360
        rounded(p, (x, 380, 320, 150), 12, PANEL, QColor(255, 255, 255, 22))
        text(p, (x + 24, 400, 270, 34), a, font(26, "Bahnschrift"), TEXT)
        text(p, (x + 24, 446, 270, 28), b, font(15, "Consolas", spacing=2), ACCENT_SOFT)
        p.setPen(QPen(ACCENT, 2))
        p.drawLine(QPointF(x + 24, 486), QPointF(x + 24 + 90 * ease(min(1, lt / 1.5)), 486))

    text(p, (0, 640, FRAMES_W, 40), "源码 · 扩展 · 海报 · 社区索引",
         font(28, "Microsoft YaHei UI"), MUTED, Qt.AlignmentFlag.AlignHCenter)


def scene_github(p: QPainter, lt: float, dur: float):
    text(p, (0, 90, FRAMES_W, 76), "已上传 GitHub",
         font(68, "Microsoft YaHei UI", QFont.Weight.Bold), TEXT,
         Qt.AlignmentFlag.AlignHCenter)
    text(p, (0, 186, FRAMES_W, 34), "LINK IN THE COMMENTS",
         font(18, "Consolas", spacing=4), ACCENT, Qt.AlignmentFlag.AlignHCenter)

    card = (330, 260, 1260, 520)
    rounded(p, card, 16, QColor(18, 16, 15, 245), QColor(255, 255, 255, 30))
    text(p, (card[0] + 42, 290, 900, 28), "GITHUB / REPOSITORY",
         font(14, "Consolas", spacing=3), MUTED)
    text(p, (card[0] + 42, 330, 1000, 60), "claude-skill-wheel",
         font(58, "Bahnschrift SemiBold"), TEXT)
    text(p, (card[0] + 42, 402, 1000, 36), "A radial skill picker for Claude Code",
         font(22, "Consolas"), MUTED)

    badges = [("Apache-2.0", ACCENT), ("Windows", CYAN), ("VS Code", MUTED), ("v0.1.1", MUTED)]
    bx = card[0] + 42
    for name, color in badges:
        w = 40 + len(name) * 14
        rounded(p, (bx, 470, w, 38), 19, QColor(255, 255, 255, 12), QColor(255, 255, 255, 26))
        text(p, (bx, 470, w, 38), name, font(15, "Consolas"), color, Qt.AlignmentFlag.AlignCenter)
        bx += w + 14

    text(p, (card[0] + 42, 680, 1000, 26),
         "README.md   ·   LICENSE   ·   extension/   ·   overlay/   ·   assets/",
         font(15, "Consolas"), MUTED)

    # star button
    clicked = lt > 2.6
    sx, sy, sw, sh = card[0] + 42, 560, 260, 64
    rounded(p, (sx, sy, sw, sh), 10,
            QColor(217, 119, 87, 235) if clicked else QColor(255, 255, 255, 16),
            QColor(217, 119, 87, 255), 1.5)
    text(p, (sx, sy, sw, sh), "★  Star" if not clicked else "★  Starred",
         font(22, "Microsoft YaHei UI"), QColor("#1A1210") if clicked else TEXT,
         Qt.AlignmentFlag.AlignCenter)

    # cursor clicks the star
    move = ease(min(1.0, max(0.0, (lt - 1.4) / 1.2)))
    cx = lerp(900, sx + sw / 2, move)
    cy = lerp(700, sy + sh / 2, move)
    if 1.4 < lt < 2.9:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 40))
        p.drawEllipse(QPointF(cx, cy), 26, 26)
    mouse_cursor(p, QPointF(cx, cy), 1.4)

    text(p, (0, 840, FRAMES_W, 50), "链接放在评论区",
         font(36, "Microsoft YaHei UI", QFont.Weight.DemiBold), ACCENT_SOFT,
         Qt.AlignmentFlag.AlignHCenter)
    text(p, (0, 900, FRAMES_W, 30), "WELCOME TO STAR · ISSUE · PR",
         font(16, "Consolas", spacing=3), MUTED, Qt.AlignmentFlag.AlignHCenter)


SCENE_FN = {
    "title": scene_title, "pain": scene_pain, "wheel": scene_wheel,
    "interact": scene_interact, "discover": scene_discover,
    "vscode": scene_vscode, "oss": scene_oss, "github": scene_github,
}


# ---------------------------------------------------------------- audio

def synth_voice() -> list[dict]:
    VID.mkdir(parents=True, exist_ok=True)
    voice_dir = VID / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for i, sc in enumerate(SCENES):
        items.append({"file": str(voice_dir / f"scene_{i+1:02d}.wav"), "text": sc["text"]})
    manifest = VID / "voice_manifest.json"
    manifest.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    ps = (
        "Add-Type -AssemblyName System.Speech\n"
        f"$m = Get-Content -Raw -Encoding UTF8 '{manifest}' | ConvertFrom-Json\n"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "$s.SelectVoice('Microsoft Huihui Desktop')\n"
        "$s.Rate = -2\n$s.Volume = 100\n"
        "foreach ($i in $m) { $s.SetOutputToWaveFile($i.file); $s.Speak($i.text) }\n"
        "$s.Dispose()\n"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    return items


def wav_info(path: Path):
    with wave.open(str(path), "rb") as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()


def build_timeline(items) -> list[dict]:
    timeline = []
    t = 1.0
    for sc, item in zip(SCENES, items):
        rate, ch, sw, n = wav_info(Path(item["file"]))
        vd = n / rate
        dur = max(sc["min"], vd + 1.4)
        timeline.append({"key": sc["key"], "start": t, "dur": dur, "voice": vd,
                         "file": item["file"], "rate": rate})
        t += dur
    return timeline


def build_voice_track(timeline, total: float) -> Path:
    rate = timeline[0]["rate"]
    total_n = int(total * rate)
    buf = np.zeros(total_n, dtype=np.int16)
    for sc in timeline:
        with wave.open(sc["file"], "rb") as w:
            frames = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        start = int((sc["start"] + 0.55) * rate)
        end = min(total_n, start + len(frames))
        buf[start:end] = frames[:end - start]
    out = VID / "voice_full.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(buf.tobytes())
    return out


def make_music(total: float) -> Path:
    sr = 44100
    n = int(total * sr)
    t = np.arange(n) / sr
    chords = [(220.00, 261.63, 329.63), (174.61, 220.00, 261.63),
              (261.63, 329.63, 392.00), (196.00, 246.94, 293.66)]
    roots = [110.0, 87.31, 130.81, 98.0]
    bar = 4.0
    bars = (t // bar).astype(np.int64) % 4
    out = np.zeros(n, dtype=np.float64)

    for ci, chord in enumerate(chords):
        mask = (bars == ci).astype(np.float64)
        for k, f in enumerate(chord):
            out += mask * np.sin(2 * np.pi * f * t + k) * 0.045
        out += mask * np.sin(2 * np.pi * roots[ci] * t) * 0.08

    step = 0.25
    count = int(total / step)
    for k in range(count):
        tt = k * step
        ci = int(tt // bar) % 4
        note = chords[ci][k % len(chords[ci])] * 2
        s0 = int(tt * sr)
        s1 = min(n, s0 + int(0.42 * sr))
        if s1 <= s0:
            continue
        local = np.arange(s1 - s0) / sr
        env = np.exp(-local * 9) * 0.045
        out[s0:s1] += np.sin(2 * np.pi * note * (t[s0:s1])) * env

    rng = np.random.default_rng(7)
    for k in range(int(total / 0.5)):
        tt = k * 0.5
        s0 = int(tt * sr)
        s1 = min(n, s0 + int(0.07 * sr))
        local = np.arange(s1 - s0) / sr
        env = np.exp(-local * 45) * 0.016
        out[s0:s1] += rng.standard_normal(s1 - s0) * env

    # gentle fade
    fade_in = int(2.0 * sr)
    fade_out = int(3.0 * sr)
    out[:fade_in] *= np.linspace(0, 1, fade_in)
    out[-fade_out:] *= np.linspace(1, 0, fade_out)
    out /= max(1e-9, np.max(np.abs(out))) * 1.0
    out *= 0.22

    stereo = np.stack([out, np.roll(out, int(0.008 * sr))], axis=1)
    data = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    path = VID / "music.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())
    return path


# ---------------------------------------------------------------- video

def render_frame(t: float, timeline, total: float) -> QImage:
    img = QImage(FRAMES_W, FRAMES_H, QImage.Format.Format_RGBA8888)
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

    background(p, t)
    SCENE_FN[sc["key"]](p, lt, sc["dur"])
    hud(p, idx + 1, t, total)

    # scene fade
    fin = 0.35
    a = 1.0
    if lt < fin:
        a = lt / fin
    remaining = sc["dur"] - lt
    if remaining < fin:
        a = min(a, remaining / fin)
    if a < 1:
        p.fillRect(QRectF(0, 0, FRAMES_W, FRAMES_H), QColor(0, 0, 0, int(255 * (1 - a))))

    p.end()
    return img


def save_stills(timeline, times, total):
    out = VID / "stills"
    out.mkdir(parents=True, exist_ok=True)
    for tt in times:
        img = render_frame(tt, timeline, total)
        path = out / f"still_{tt:05.1f}.png"
        img.save(str(path), "PNG")
        print("still", path)


def encode(timeline, total, voice_path, music_path, out_path):
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{FRAMES_W}x{FRAMES_H}",
        "-r", str(FPS), "-i", "-",
        "-i", str(voice_path), "-i", str(music_path),
        "-filter_complex",
        f"[1:a]volume=1.0[a1];"
        f"[2:a]volume=0.13,afade=t=in:st=0:d=1.5,"
        f"afade=t=out:st={max(0.0, total - 2.5):.2f}:d=2.5[a2];"
        f"[a1][a2]amix=inputs=2:duration=longest:dropout_transition=0[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-t", f"{total:.2f}", str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = int(math.ceil(total * FPS))
    for i in range(frames):
        img = render_frame(i / FPS, timeline, total)
        proc.stdin.write(img.constBits().tobytes())
        if i % 150 == 0:
            print(f"frame {i}/{frames}", flush=True)
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise SystemExit(f"ffmpeg failed: {proc.returncode}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", default="")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--reuse-audio", action="store_true")
    args = ap.parse_args()

    app = QGuiApplication(sys.argv[:1])
    VID.mkdir(parents=True, exist_ok=True)

    if args.reuse_audio and (VID / "voice_manifest.json").exists():
        items = json.loads((VID / "voice_manifest.json").read_text(encoding="utf-8"))
    else:
        print("synthesizing voice...")
        items = synth_voice()

    timeline = build_timeline(items)
    total = timeline[-1]["start"] + timeline[-1]["dur"] + 1.5
    for sc in timeline:
        print(f"{sc['key']:<10} start={sc['start']:6.2f} dur={sc['dur']:5.2f} voice={sc['voice']:5.2f}")
    print(f"total {total:.2f}s")

    voice_path = build_voice_track(timeline, total)

    if args.stills:
        save_stills(timeline, [float(x) for x in args.stills.split(",") if x], total)
        return 0

    music_path = make_music(total + 0.5)

    if args.render:
        out = VID / "skill-wheel-intro.mp4"
        encode(timeline, total, voice_path, music_path, out)
        print("video ->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
