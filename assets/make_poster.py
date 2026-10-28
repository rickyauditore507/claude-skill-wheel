"""Render the Skill Wheel poster + README banner with QPainter.

No external services: run with the project venv.

    python assets/make_poster.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QGuiApplication,
                           QImage, QLinearGradient, QPainter, QPainterPath,
                           QPen, QRadialGradient)

OUT = Path(__file__).resolve().parent

ACCENT = QColor("#D97757")
ACCENT_SOFT = QColor("#F2B59E")
CYAN = QColor("#6FE3E1")
TEXT = QColor("#F5F0EA")
MUTED = QColor("#8F867E")
BG0 = QColor("#0A0908")
BG1 = QColor("#181412")
PANEL = QColor("#141110")

SKILLS = ["archify", "design", "diagram", "slides",
          "brand", "banner", "ui ux", "community"]


def font(size: int, family: str = "Microsoft YaHei UI", weight=QFont.Weight.Normal,
         spacing: float = 0) -> QFont:
    f = QFont(family)
    f.setPixelSize(size)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def draw_text(p: QPainter, rect: QRectF, text: str, f: QFont, color: QColor,
              align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter):
    p.setFont(f)
    p.setPen(color)
    p.drawText(rect, align, text)


def glow_text(p: QPainter, pos: QPointF, text: str, f: QFont, color: QColor,
              glow: QColor, radius: int = 18) -> None:
    p.setFont(f)
    path = QPainterPath()
    path.addText(pos, f, text)
    for width, alpha in ((radius, 18), (radius * 0.6, 30), (radius * 0.3, 46)):
        pen = QPen(QColor(glow.red(), glow.green(), glow.blue(), alpha))
        pen.setWidthF(width)
        p.strokePath(path, pen)
    p.fillPath(path, QBrush(color))


def wedge(center: QPointF, r_in: float, r_out: float, a0: float, a1: float) -> QPainterPath:
    steps = max(10, int(abs(a1 - a0) / 2))
    path = QPainterPath()

    def pt(r: float, ang: float) -> QPointF:
        rad = math.radians(ang)
        return QPointF(center.x() + r * math.cos(rad), center.y() + r * math.sin(rad))

    path.moveTo(pt(r_out, a0))
    for i in range(1, steps + 1):
        path.lineTo(pt(r_out, a0 + (a1 - a0) * i / steps))
    for i in range(steps, -1, -1):
        path.lineTo(pt(r_in, a0 + (a1 - a0) * i / steps))
    path.closeSubpath()
    return path


def background(p: QPainter, w: int, h: int, wheel_center: QPointF) -> None:
    grad = QRadialGradient(QPointF(w * 0.5, h * 0.43), max(w, h) * 0.75)
    grad.setColorAt(0.0, QColor("#1B1614"))
    grad.setColorAt(0.55, BG1)
    grad.setColorAt(1.0, BG0)
    p.fillRect(QRectF(0, 0, w, h), grad)

    # grid
    p.setPen(QPen(QColor(255, 255, 255, 7), 1))
    step = 48 if w > 1000 else 32
    for x in range(0, w, step):
        p.drawLine(x, 0, x, h)
    for y in range(0, h, step):
        p.drawLine(0, y, w, y)

    # concentric HUD rings behind the wheel
    for r, alpha in ((360, 10), (440, 8), (520, 7), (600, 5)):
        p.setPen(QPen(QColor(255, 255, 255, alpha), 1))
        p.drawEllipse(wheel_center, r, r)

    # corner brackets
    m, ln = 46, 44
    p.setPen(QPen(QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 150), 2))
    corners = [(m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)]
    for x, y, dx, dy in corners:
        p.drawLine(QPointF(x, y), QPointF(x + dx * ln, y))
        p.drawLine(QPointF(x, y), QPointF(x, y + dy * ln))


def draw_wheel(p: QPainter, center: QPointF, outer: float, inner: float,
               highlight: int, name_size: int, cmd_size: int) -> None:
    n = len(SKILLS)
    step = 360.0 / n
    start = -90.0 - step * n / 2.0
    gap = 2.4

    # outer tick ring
    p.setPen(QPen(QColor(255, 255, 255, 28), 1))
    p.drawEllipse(center, outer + 26, outer + 26)
    p.setPen(QPen(QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 90), 1))
    for i in range(72):
        ang = math.radians(i * 5)
        r0 = outer + 34
        r1 = outer + (46 if i % 6 == 0 else 40)
        p.drawLine(QPointF(center.x() + r0 * math.cos(ang), center.y() + r0 * math.sin(ang)),
                   QPointF(center.x() + r1 * math.cos(ang), center.y() + r1 * math.sin(ang)))

    for i, name in enumerate(SKILLS):
        a0 = start + i * step + gap / 2
        a1 = start + (i + 1) * step - gap / 2
        hot = i == highlight
        path = wedge(center, inner, outer, a0, a1)

        if hot:
            for spread, alpha in ((18, 26), (9, 40), (3, 70)):
                p.setPen(QPen(QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), alpha), spread))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(wedge(center, inner - 4, outer + 6, a0 - 0.6, a1 + 0.6))

        g = QLinearGradient()
        g.setStart(center)
        g.setFinalStop(QPointF(center.x() + math.cos(math.radians((a0 + a1) / 2)) * outer,
                               center.y() + math.sin(math.radians((a0 + a1) / 2)) * outer))
        if hot:
            g.setColorAt(0.0, QColor("#3A2A22"))
            g.setColorAt(0.55, QColor("#8A4F3A"))
            g.setColorAt(1.0, ACCENT)
            pen = QPen(QColor(255, 255, 255, 90), 1.4)
        else:
            g.setColorAt(0.0, QColor("#1D1A18"))
            g.setColorAt(1.0, QColor("#2B2724"))
            pen = QPen(QColor(255, 255, 255, 20), 1)
        p.setPen(pen)
        p.setBrush(g)
        p.drawPath(path)

        mid = (a0 + a1) / 2
        rad = math.radians(mid)
        lr = (inner + outer) / 2
        x = center.x() + lr * math.cos(rad)
        y = center.y() + lr * math.sin(rad)
        width = outer * math.radians(step) * 0.82
        f = font(name_size, "Bahnschrift SemiBold", QFont.Weight.DemiBold)
        fm = QFontMetrics(f)
        label = fm.elidedText(name.upper(), Qt.TextElideMode.ElideRight, int(width))
        draw_text(p, QRectF(x - width / 2, y - name_size, width, name_size * 1.5),
                  label, f, QColor("#FFFFFF") if hot else TEXT,
                  Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        draw_text(p, QRectF(x - width / 2, y + name_size * 0.45, width, cmd_size * 1.6),
                  "/" + name.replace(" ", "-"), font(cmd_size, "Consolas"),
                  ACCENT_SOFT if hot else MUTED,
                  Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

    # hub
    p.setPen(QPen(QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 140), 1.2))
    p.setBrush(QColor("#0E0C0B"))
    p.drawEllipse(center, inner - 18, inner - 18)
    ring = QRectF(center.x() - (inner - 40), center.y() - (inner - 40),
                  (inner - 40) * 2, (inner - 40) * 2)
    p.setPen(QPen(QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 60), 1))
    p.drawArc(ring, 20 * 16, 140 * 16)
    p.drawArc(ring, 200 * 16, 140 * 16)

    big = font(int(inner * 0.34), "Bahnschrift SemiBold Condensed", QFont.Weight.Bold, 2)
    draw_text(p, QRectF(center.x() - inner, center.y() - inner * 0.45, inner * 2, inner * 0.4),
              "SKILL", big, TEXT, Qt.AlignmentFlag.AlignCenter)
    draw_text(p, QRectF(center.x() - inner, center.y() - inner * 0.05, inner * 2, inner * 0.4),
              "WHEEL", big, ACCENT, Qt.AlignmentFlag.AlignCenter)
    draw_text(p, QRectF(center.x() - inner, center.y() + inner * 0.34, inner * 2, 30),
              "CLAUDE CODE", font(int(inner * 0.09), "Consolas", spacing=3), MUTED,
              Qt.AlignmentFlag.AlignCenter)


def chip(p: QPainter, rect: QRectF, kicker: str, value: str, accent: QColor) -> None:
    p.setPen(QPen(QColor(255, 255, 255, 18), 1))
    p.setBrush(QColor(PANEL.red(), PANEL.green(), PANEL.blue(), 210))
    p.drawRoundedRect(rect, 10, 10)
    p.setPen(QPen(accent, 2))
    p.drawLine(QPointF(rect.left() + 18, rect.top() + 18),
               QPointF(rect.left() + 18, rect.top() + 42))
    draw_text(p, QRectF(rect.left() + 32, rect.top() + 12, rect.width() - 44, 24),
              kicker, font(13, "Consolas", spacing=3), accent)
    draw_text(p, QRectF(rect.left() + 32, rect.top() + 38, rect.width() - 44, 40),
              value, font(24, "Microsoft YaHei UI", QFont.Weight.DemiBold), TEXT)


def render_poster() -> QImage:
    w, h, scale = 1600, 2000, 2
    img = QImage(w * scale, h * scale, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.scale(scale, scale)

    center = QPointF(w / 2, 1180)
    background(p, w, h, center)

    # top labels
    draw_text(p, QRectF(90, 84, 800, 30), "CLAUDE CODE // INTERFACE 01",
              font(17, "Consolas", spacing=4), ACCENT)
    draw_text(p, QRectF(w - 300, 84, 210, 30), "RADIAL SKILL PICKER",
              font(15, "Consolas", spacing=3), MUTED, Qt.AlignmentFlag.AlignRight)

    # title
    title_font = font(206, "Bahnschrift SemiBold Condensed", QFont.Weight.Bold, 1)
    glow_text(p, QPointF(86, 330), "SKILL", title_font, TEXT,
              QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 70), 26)
    glow_text(p, QPointF(86, 520), "WHEEL", title_font, ACCENT,
              QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 120), 30)
    draw_text(p, QRectF(92, 585, 900, 46), "按住一个键，滑向你的技能",
              font(36, "Microsoft YaHei UI", QFont.Weight.DemiBold), TEXT)
    draw_text(p, QRectF(92, 637, 1100, 30),
              "Hold a shortcut · hover a wedge · scroll rings · release to insert",
              font(18, "Consolas"), MUTED)

    # right HUD stats
    draw_text(p, QRectF(w - 360, 300, 270, 24), "16 SKILLS",
              font(14, "Consolas", spacing=2), ACCENT, Qt.AlignmentFlag.AlignRight)
    draw_text(p, QRectF(w - 360, 330, 270, 24), "8 / RING",
              font(14, "Consolas", spacing=2), MUTED, Qt.AlignmentFlag.AlignRight)
    draw_text(p, QRectF(w - 360, 360, 270, 24), "WINDOWS · VS CODE",
              font(14, "Consolas", spacing=2), MUTED, Qt.AlignmentFlag.AlignRight)

    draw_wheel(p, center, 450, 176, 2, 25, 12)

    # side HUD labels
    draw_text(p, QRectF(90, 1000, 210, 24), "DISCOVER", font(13, "Consolas", spacing=3), MUTED)
    draw_text(p, QRectF(90, 1026, 210, 24), "RENDER", font(13, "Consolas", spacing=3), MUTED)
    draw_text(p, QRectF(90, 1052, 210, 24), "INSERT", font(13, "Consolas", spacing=3), ACCENT)
    draw_text(p, QRectF(w - 300, 1280, 210, 24), "01 / HOLD", font(13, "Consolas", spacing=3), ACCENT)
    draw_text(p, QRectF(w - 300, 1306, 210, 24), "02 / SCROLL", font(13, "Consolas", spacing=3), MUTED)
    draw_text(p, QRectF(w - 300, 1332, 210, 24), "03 / RELEASE", font(13, "Consolas", spacing=3), MUTED)

    # feature chips
    cw, gap, y = 462, 27, 1718
    chip(p, QRectF(90, y, cw, 104), "HOLD", "Ctrl + Alt + Space", ACCENT)
    chip(p, QRectF(90 + cw + gap, y, cw, 104), "SWITCH", "Scroll to flip rings", CYAN)
    chip(p, QRectF(90 + 2 * (cw + gap), y, cw, 104), "INSERT", "Release → /skill", ACCENT)

    # footer
    p.setPen(QPen(QColor(255, 255, 255, 18), 1))
    p.drawLine(QPointF(90, 1900), QPointF(w - 90, 1900))
    draw_text(p, QRectF(90, 1916, 700, 30), "OPEN SOURCE · APACHE-2.0",
              font(15, "Consolas", spacing=3), ACCENT)
    draw_text(p, QRectF(w - 700, 1916, 610, 30), "CLAUDE CODE + VS CODE",
              font(15, "Consolas", spacing=3), MUTED, Qt.AlignmentFlag.AlignRight)

    p.end()
    return img


def render_banner() -> QImage:
    w, h, scale = 1280, 640, 2
    img = QImage(w * scale, h * scale, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.scale(scale, scale)

    center = QPointF(970, 320)
    background(p, w, h, center)

    draw_text(p, QRectF(64, 60, 600, 24), "CLAUDE CODE // SKILL INTERFACE",
              font(13, "Consolas", spacing=3), ACCENT)
    title_font = font(104, "Bahnschrift SemiBold Condensed", QFont.Weight.Bold, 1)
    glow_text(p, QPointF(60, 200), "SKILL WHEEL", title_font, TEXT,
              QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 90), 18)
    draw_text(p, QRectF(64, 224, 660, 34), "按住一个键，滑向你的技能",
              font(26, "Microsoft YaHei UI", QFont.Weight.DemiBold), ACCENT_SOFT)
    draw_text(p, QRectF(64, 266, 700, 24),
              "Hold · hover · scroll · release to insert /skill",
              font(15, "Consolas"), MUTED)

    chip(p, QRectF(64, 340, 300, 88), "HOLD", "Ctrl+Alt+Space", ACCENT)
    chip(p, QRectF(382, 340, 300, 88), "SWITCH", "Scroll rings", CYAN)

    draw_text(p, QRectF(64, 560, 600, 24), "OPEN SOURCE · APACHE-2.0",
              font(12, "Consolas", spacing=3), MUTED)

    draw_wheel(p, center, 240, 92, 2, 13, 8)
    p.end()
    return img


def main() -> int:
    app = QGuiApplication(sys.argv[:1])
    poster = render_poster()
    banner = render_banner()
    poster_path = OUT / "poster.png"
    banner_path = OUT / "banner.png"
    poster.save(str(poster_path), "PNG")
    banner.save(str(banner_path), "PNG")
    print(f"poster -> {poster_path} ({poster.width()}x{poster.height()})")
    print(f"banner -> {banner_path} ({banner.width()}x{banner.height()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
