"""The radial skill wheel: a transparent, click-through, always-on-top overlay."""
from __future__ import annotations

import logging
import math
import time
from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QPointF, QRectF

from skills import Skill

logger = logging.getLogger("skill-wheel")


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _mix(c1: QtGui.QColor, c2: QtGui.QColor, t: float) -> QtGui.QColor:
    return QtGui.QColor(
        round(_lerp(c1.red(), c2.red(), t)),
        round(_lerp(c1.green(), c2.green(), t)),
        round(_lerp(c1.blue(), c2.blue(), t)),
        round(_lerp(c1.alpha(), c2.alpha(), t)),
    )


def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


class RadialWheel(QtWidgets.QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.cfg = config
        theme = config.get("theme", {})
        self.c_accent = QtGui.QColor(theme.get("accent", "#D97757"))
        self.c_accent_soft = QtGui.QColor(theme.get("accentSoft", "#E8A487"))
        self.c_text = QtGui.QColor(theme.get("text", "#F3EEE8"))
        self.c_muted = QtGui.QColor(theme.get("muted", "#9C948C"))
        self.c_panel = QtGui.QColor(theme.get("panel", "#1D1B19"))
        self.c_sector = QtGui.QColor(theme.get("sector", "#2A2724"))
        self.c_sector_hover = QtGui.QColor(theme.get("sectorHover", "#3A342E"))

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.skills: list[Skill] = []
        self.per_page = max(2, int(config.get("skillsPerPage", 8)))
        self.radius = float(config.get("radius", 250))
        self.inner = float(config.get("innerRadius", 108))
        self.page = 0
        self.hover: int | None = None
        self.moved = False
        self.open_at_cursor = True
        self._visible = False
        self._scales: dict[int, float] = {}
        self._hover_t = 0.0
        self._page_t = 0.0
        self._opened_at = 0.0
        self._origin = QtCore.QPoint()
        self._center = QPointF(0, 0)
        self._screen = None
        self._last_page = -1

    # ---------- lifecycle ----------
    def open(self, skills: list[Skill], cursor: QtCore.QPoint | None = None,
             origin_phys: tuple[int, int] | None = None) -> None:
        self.skills = skills
        self.page = 0
        self.hover = None
        self.moved = False
        self._scales = {}
        self._page_t = 0.0
        self._opened_at = time.monotonic()
        self._visible = True

        pos = cursor or QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(pos) or QtGui.QGuiApplication.primaryScreen()
        self._screen = screen

        cfg_radius = float(self.cfg.get("radius", 250))
        max_radius = min(screen.geometry().width(), screen.geometry().height()) / 2 - 28
        self.radius = max(140.0, min(cfg_radius, max_radius))
        self.inner = max(64.0, min(float(self.cfg.get("innerRadius", 108)), self.radius - 60))

        geo = screen.geometry()
        self.setGeometry(geo)
        margin = self.radius + 6
        cx = min(max(pos.x() - geo.x(), margin), geo.width() - margin)
        cy = min(max(pos.y() - geo.y(), margin), geo.height() - margin)
        self._center = QPointF(cx, cy)
        self._origin = pos
        try:
            from wininput import get_cursor_physical
            self._origin_phys = origin_phys or get_cursor_physical()
        except Exception:
            self._origin_phys = None

        self.show()
        try:
            from wininput import apply_overlay_window_style
            apply_overlay_window_style(int(self.winId()))
        except Exception:
            pass
        self.raise_()
        self.update()

    def close_wheel(self) -> None:
        self._visible = False
        self.hide()

    def is_open(self) -> bool:
        return self._visible

    # ---------- geometry ----------
    def _page_count(self) -> int:
        return max(1, math.ceil(len(self.skills) / self.per_page))

    def _page_skills(self) -> list[Skill]:
        start = self.page * self.per_page
        return self.skills[start:start + self.per_page]

    def _sector_angles(self, n: int) -> tuple[float, float]:
        step = 360.0 / max(1, n)
        return step, -90.0 - step * n / 2.0

    def _hover_index(self, cursor: QtCore.QPoint) -> int | None:
        items = self._page_skills()
        n = len(items)
        if not n or not self._visible:
            return None
        dx = cursor.x() - self._center.x()
        dy = cursor.y() - self._center.y()
        dist = math.hypot(dx, dy)
        if dist < self.inner - 14 or dist > self.radius + 22:
            return None
        step, start = self._sector_angles(n)
        ang = math.degrees(math.atan2(dy, dx))
        rel = (ang - start) % 360.0
        idx = int(rel // step)
        if idx >= n:
            idx = n - 1
        if rel - idx * step > step - min(2.2, 16.0 / n):
            # in the gap between wedges
            return None
        return idx

    # ---------- motion ----------
    def tick(self) -> None:
        """Called by the controller's polling timer; the wheel owns no timer."""
        try:
            self._tick_inner()
        except Exception:
            logger.exception('tick failed')

    def _tick_inner(self) -> None:
        if not self._visible:
            return
        cursor_global = QtGui.QCursor.pos()
        cursor = self.mapFromGlobal(cursor_global)
        if not self.moved and self._origin_phys is not None:
            try:
                from wininput import get_cursor_physical
                px, py = get_cursor_physical()
                dpr = self._screen.devicePixelRatio() if self._screen else 1.0
                limit = int(self.cfg.get("moveThreshold", 12) * dpr)
                if abs(px - self._origin_phys[0]) + abs(py - self._origin_phys[1]) > limit:
                    self.moved = True
            except Exception:
                pass
        idx = self._hover_index(cursor)  # window-local, same space as _center
        if idx != self.hover:
            self.hover = idx
        # per-sector animation
        items = self._page_skills()
        for i in range(len(items)):
            cur = self._scales.get(i, 0.0)
            goal = 1.0 if i == idx else 0.0
            self._scales[i] = cur + (goal - cur) * 0.28
        self._page_t = min(1.0, self._page_t + 0.12)
        self.update()

    def wheel(self, direction: int) -> None:
        if not self._visible or self._page_count() <= 1:
            return
        self.page = (self.page + direction) % self._page_count()
        self.hover = None
        self._page_t = 0.0
        self._scales = {}
        self.update()

    # ---------- painting ----------
    def paintEvent(self, _event) -> None:
        if not self._visible:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = self.rect()
        dim = float(self.cfg.get("dimBackground", 0.38))
        if dim > 0:
            p.fillRect(rect, QtGui.QColor(0, 0, 0, int(255 * dim * 0.62)))

        items = self._page_skills()
        n = len(items)
        if not n:
            self._paint_hub(p, None)
            p.end()
            return

        step, start = self._sector_angles(n)
        open_t = _ease_out((time.monotonic() - self._opened_at) / 0.16)
        gap = min(2.2, 16.0 / n)

        for i, skill in enumerate(items):
            t = self._scales.get(i, 0.0) * self._hover_t_scale()
            a0 = start + i * step + gap / 2
            a1 = start + (i + 1) * step - gap / 2
            # page-entry pop + opening pop
            pop = 0.94 + 0.06 * _ease_out(self._page_t) + 0.0 * open_t
            r_out = (self.radius + 16 * t) * pop
            r_in = (self.inner - 7 * t) * pop
            path = self._wedge(r_in, r_out, a0, a1, center=self._center)

            if t > 0.01:
                glow = self._wedge(r_in - 2, r_out + 10, a0 - 1.2, a1 + 1.2,
                                   center=self._center)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QtGui.QColor(self.c_accent.red(), self.c_accent.green(),
                                        self.c_accent.blue(), int(46 * t)))
                p.drawPath(glow)

            base = _mix(self.c_sector, self.c_sector_hover, t)
            base.setAlpha(int(228 + 20 * t))
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, int(16 + 22 * t)), 1.0))
            p.setBrush(base)
            p.drawPath(path)

            # hovered accent edge
            if t > 0.02:
                edge = self._wedge(r_out - 2.2, r_out, a0, a1, center=self._center)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QtGui.QColor(self.c_accent.red(), self.c_accent.green(),
                                        self.c_accent.blue(), int(235 * t)))
                p.drawPath(edge)

            self._paint_label(p, skill, a0, a1, r_in, r_out, t)

        self._paint_hub(p, items[self.hover] if self.hover is not None and
                        self.hover < len(items) else None)
        self._paint_page_dots(p, n)
        p.end()

    def _hover_t_scale(self) -> float:
        return 1.0

    def _wedge(self, r_in: float, r_out: float, a0: float, a1: float,
               center: QPointF) -> QtGui.QPainterPath:
        steps = max(8, int(abs(a1 - a0) / 3))
        path = QtGui.QPainterPath()

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

    def _paint_label(self, p: QtGui.QPainter, skill: Skill, a0: float, a1: float,
                     r_in: float, r_out: float, t: float) -> None:
        mid = (a0 + a1) / 2
        label_r = (r_in + r_out) / 2
        rad = math.radians(mid)
        x = self._center.x() + label_r * math.cos(rad)
        y = self._center.y() + label_r * math.sin(rad)

        step_rad = math.radians(a1 - a0 + 4)
        max_w = max(64.0, min(210.0, label_r * step_rad * 0.82))

        font = QtGui.QFont("Microsoft YaHei UI")
        font.setPixelSize(int(13 + 2 * t))
        font.setWeight(QtGui.QFont.Weight.DemiBold if t > 0.4 else QtGui.QFont.Weight.Normal)
        p.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        name = skill.name.replace("-", " ").replace("_", " ")
        shown = metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, int(max_w))
        color = _mix(self.c_text, QtGui.QColor("#FFFFFF"), t)
        p.setPen(color)
        r = QRectF(x - max_w / 2, y - 11, max_w, 22)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, shown)

        if t > 0.35:
            p.setPen(QtGui.QColor(self.c_accent_soft.red(), self.c_accent_soft.green(),
                                  self.c_accent_soft.blue(), int(200 * t)))
            f2 = QtGui.QFont("Microsoft YaHei UI")
            f2.setPixelSize(9)
            p.setFont(f2)
            p.drawText(QRectF(x - max_w / 2, y + 9, max_w, 14),
                       Qt.AlignmentFlag.AlignCenter, "/" + skill.command)

    def _paint_hub(self, p: QtGui.QPainter, hovered: Skill | None) -> None:
        hub_r = self.inner - 18
        if hub_r < 30:
            return
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 26), 1.2))
        p.setBrush(QtGui.QColor(self.c_panel.red(), self.c_panel.green(),
                                self.c_panel.blue(), 240))
        p.drawEllipse(self._center, hub_r, hub_r)

        width = hub_r * 1.66
        cx, cy = self._center.x(), self._center.y()
        pages = self._page_count()

        if hovered:
            display = hovered.name.replace("-", " ").replace("_", " ")
            name_font = QtGui.QFont("Microsoft YaHei UI")
            name_font.setPixelSize(11 if len(display) > 18 else 13)
            name_font.setWeight(QtGui.QFont.Weight.DemiBold)
            p.setFont(name_font)
            p.setPen(self.c_text)
            name_rect = QRectF(cx - width / 2, cy - hub_r * 0.70, width, hub_r * 0.50)
            p.drawText(name_rect,
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop |
                       Qt.TextFlag.TextWordWrap, display)

            desc_font = QtGui.QFont("Microsoft YaHei UI")
            desc_font.setPixelSize(8.5)
            p.setFont(desc_font)
            p.setPen(self.c_muted)
            desc = hovered.description or "（无描述）"
            if len(desc) > 72:
                desc = desc[:71] + "…"
            desc_rect = QRectF(cx - width / 2, cy - hub_r * 0.16,
                               width, hub_r * 0.68)
            p.drawText(desc_rect,
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop |
                       Qt.TextFlag.TextWordWrap, desc)

            badge_font = QtGui.QFont("Microsoft YaHei UI")
            badge_font.setPixelSize(9)
            p.setFont(badge_font)
            p.setPen(QtGui.QColor(self.c_accent_soft.red(), self.c_accent_soft.green(),
                                  self.c_accent_soft.blue(), 220))
            label = {"personal": "个人", "project": "项目", "plugin": "插件"}.get(
                hovered.source, hovered.source)
            if pages > 1:
                label += f" · {self.page + 1}/{pages}"
            p.drawText(QRectF(cx - width / 2, cy + hub_r * 0.58, width, 15),
                       Qt.AlignmentFlag.AlignHCenter, label)
        else:
            title_font = QtGui.QFont("Microsoft YaHei UI")
            title_font.setPixelSize(13)
            title_font.setWeight(QtGui.QFont.Weight.DemiBold)
            p.setFont(title_font)
            p.setPen(self.c_text)
            p.drawText(QRectF(cx - width / 2, cy - hub_r * 0.48, width, 28),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                       "松开取消" if self.moved else "移动鼠标选择")

            small = QtGui.QFont("Microsoft YaHei UI")
            small.setPixelSize(10)
            p.setFont(small)
            p.setPen(self.c_muted)
            hint = "滚轮翻页 · 松开确认" if pages > 1 else "松开确认"
            p.drawText(QRectF(cx - width / 2, cy - hub_r * 0.10, width, 20),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, hint)

    def _paint_page_dots(self, p: QtGui.QPainter, n: int) -> None:
        pages = self._page_count()
        if pages <= 1:
            return
        hub_r = self.inner - 18
        y = self._center.y() + hub_r * 0.86
        spacing = 11
        total = (pages - 1) * spacing
        x0 = self._center.x() - total / 2
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(pages):
            color = self.c_accent if i == self.page else QtGui.QColor(255, 255, 255, 60)
            p.setBrush(color)
            p.drawEllipse(QPointF(x0 + i * spacing, y), 2.3, 2.3)

    # ---------- test hook ----------
    def grab_screen(self, path: str) -> bool:
        screen = self._screen or QtGui.QGuiApplication.primaryScreen()
        pix = screen.grabWindow(0)
        return pix.save(path, "PNG")
