"""Skill Wheel — hold a hotkey, pick a Claude Code skill from a radial menu."""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QTimer

import wininput
from config import APP_DIR, bump_usage, ensure_app_dir, load_config
from hotkey import Hotkey
from skills import Skill, discover
from ui import RadialWheel

logger = logging.getLogger("skill-wheel")


def setup_logging() -> None:
    ensure_app_dir()
    handler = logging.FileHandler(APP_DIR / "overlay.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream)


class Bridge(QtCore.QObject):
    """Thread-safe hand-off from pynput's hook threads into Qt."""
    activated = QtCore.Signal()
    scrolled = QtCore.Signal(int)


class Controller(QtCore.QObject):
    def __init__(self, cfg: dict, workspace: str | None, port: int, app: QtWidgets.QApplication):
        super().__init__()
        self.cfg = cfg
        self.workspace = workspace
        self.port = port
        self.app = app
        self.bridge = Bridge()
        self.wheel = RadialWheel(cfg)
        self.skills: list[Skill] = []
        self.hotkey: Hotkey | None = None
        self._was_open = False
        self._busy = False
        self.demo_mode = False
        self._old_clip = None

        self.poll = QTimer(self)
        self.poll.setInterval(28)
        self.poll.timeout.connect(self._poll)

        self.bridge.activated.connect(self.on_hotkey)
        self.bridge.scrolled.connect(self.on_scroll)

        self._make_tray()

    # ---------- tray ----------
    def _make_tray(self) -> None:
        pix = QtGui.QPixmap(64, 64)
        pix.fill(Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        accent = QtGui.QColor(self.cfg.get("theme", {}).get("accent", "#D97757"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(accent)
        p.drawEllipse(6, 6, 52, 52)
        p.setBrush(QtGui.QColor("#1D1B19"))
        p.drawEllipse(20, 20, 24, 24)
        p.setBrush(accent)
        p.drawEllipse(28, 4, 8, 8)
        p.end()
        self.tray = QtWidgets.QSystemTrayIcon(QtGui.QIcon(pix), self)
        self.tray.setToolTip(f"Skill Wheel · {self.cfg.get('trigger', 'alt+`')}")
        menu = QtWidgets.QMenu()
        act_reload = menu.addAction("重新扫描 skills")
        act_reload.triggered.connect(self._reload)
        act_cfg = menu.addAction("打开配置")
        act_cfg.triggered.connect(self._open_config)
        menu.addSeparator()
        act_quit = menu.addAction("退出")
        act_quit.triggered.connect(self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self._open_config()
            if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self.tray.show()

    def _open_config(self) -> None:
        path = APP_DIR / "config.json"
        try:
            os.startfile(str(path))
        except Exception:
            logger.exception("cannot open config")

    def _reload(self) -> None:
        self.skills = discover(self.cfg, self.workspace)
        logger.info("reloaded %d skills", len(self.skills))
        self.tray.showMessage("Skill Wheel", f"已加载 {len(self.skills)} 个 skill",
                              QtWidgets.QSystemTrayIcon.MessageIcon.Information, 1800)

    # ---------- hotkey ----------
    def start_hotkey(self) -> None:
        try:
            self.hotkey = Hotkey(self.cfg.get("trigger", "alt+`"),
                                 on_activate=self.bridge.activated.emit,
                                 on_scroll=self.bridge.scrolled.emit,
                                 suppress_scroll=lambda: self.wheel.is_open())
            self.hotkey.start()
            logger.info("hotkey armed: %s (vk=%s mods=%s)",
                        self.cfg.get("trigger"), self.hotkey.key_vk, self.hotkey.mods)
        except Exception as exc:
            logger.exception("hotkey failed: %s", exc)
            self.tray.showMessage("Skill Wheel", f"快捷键注册失败：{exc}",
                                  QtWidgets.QSystemTrayIcon.MessageIcon.Warning, 4000)

    def on_hotkey(self) -> None:
        if self._busy:
            return
        if self.wheel.is_open():
            return
        self.skills = discover(self.cfg, self.workspace)
        if not self.skills:
            self.tray.showMessage("Skill Wheel", "没有找到任何 skill",
                                  QtWidgets.QSystemTrayIcon.MessageIcon.Warning, 2500)
            return
        self.wheel.open(self.skills, origin_phys=getattr(self.hotkey, 'activation_pos', None))
        self._was_open = True
        self.poll.setInterval(16)
        self.poll.start()

    def on_scroll(self, direction: int) -> None:
        if self.wheel.is_open():
            self.wheel.wheel(direction)

    def _poll(self) -> None:
        if not self.wheel.is_open():
            self.poll.stop()
            return
        self.wheel.tick()
        if self.demo_mode:
            return
        if wininput.is_down(wininput.VK_ESCAPE):
            logger.info("cancelled by esc")
            self._finish(commit=False)
            return
        if self.hotkey and not self.hotkey.held():
            commit = self.wheel.moved and self.wheel.hover is not None
            logger.info("released: moved=%s hover=%s", self.wheel.moved, self.wheel.hover)
            self._finish(commit=commit)

    def _finish(self, commit: bool) -> None:
        skill = None
        if commit and self.wheel.hover is not None:
            items = self.wheel._page_skills()
            if 0 <= self.wheel.hover < len(items):
                skill = items[self.wheel.hover]
        self.wheel.close_wheel()
        self.poll.stop()
        self._was_open = False
        if skill:
            self._commit(skill)
        else:
            self._closed()

    def _closed(self) -> None:
        self._busy = False

    # ---------- insertion ----------
    def _commit(self, skill: Skill) -> None:
        self._busy = True
        logger.info("commit: %s", skill.command)
        if self.cfg.get("trackUsage", True):
            try:
                bump_usage(skill.command)
            except Exception:
                logger.exception("usage bump failed")
        mode = self.cfg.get("insertMode", "insert")
        text = f"/{skill.command} "
        if mode == "clipboard":
            wininput.set_clipboard_text(text)
            self.tray.showMessage("Skill Wheel", f"已复制 /{skill.command}",
                                  QtWidgets.QSystemTrayIcon.MessageIcon.Information, 1500)
            self._busy = False
            return

        # Paste is far more reliable than typing: the first synthetic character
        # after hiding the overlay can be swallowed by the focus change.
        self._old_clip = wininput.get_clipboard_text()
        wininput.set_clipboard_text(text)

        def work() -> None:
            try:
                if self.cfg.get("focusClaude", True):
                    self._focus_claude()
                time.sleep(0.35)
                wininput.release_modifiers()
                time.sleep(0.06)
                wininput.send_paste()
                if mode == "insert_and_enter":
                    time.sleep(0.12)
                    wininput.tap(wininput.VK_RETURN)
                logger.info("pasted %s", text.strip())
            except Exception:
                logger.exception("paste failed")
            finally:
                QtCore.QMetaObject.invokeMethod(self, "_idle",
                                                 QtCore.Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=work, daemon=True).start()

    @QtCore.Slot()
    def _idle(self) -> None:
        self._busy = False
        old = self._old_clip
        self._old_clip = None
        if old is not None:
            QTimer.singleShot(1200, lambda: wininput.set_clipboard_text(old))

    def _focus_claude(self) -> None:
        if not self.port:
            return
        url = f"http://127.0.0.1:{self.port}/focus-claude"
        try:
            req = urllib.request.Request(url, data=b"{}", method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=0.4) as resp:
                resp.read()
        except Exception as exc:
            logger.info("focus bridge unavailable: %s", exc)

    def quit(self) -> None:
        try:
            self.wheel.close_wheel()
            if self.hotkey:
                self.hotkey.stop()
            self.tray.hide()
        finally:
            self.app.quit()


def run_demo(ctrl: Controller, shot: str | None, hover: int | None) -> None:
    ctrl.on_hotkey()

    def place_cursor() -> None:
        if hover is None or not ctrl.wheel.is_open():
            return
        items = ctrl.wheel._page_skills()
        if not items:
            return
        n = len(items)
        idx = max(0, min(hover, n - 1))
        step = 360.0 / n
        mid = -90.0 - step * n / 2.0 + (idx + 0.5) * step
        rad = (ctrl.wheel.inner + ctrl.wheel.radius) / 2
        import math
        x = ctrl.wheel._center.x() + rad * math.cos(math.radians(mid))
        y = ctrl.wheel._center.y() + rad * math.sin(math.radians(mid))
        geo = ctrl.wheel.geometry()
        QtGui.QCursor.setPos(int(geo.x() + x), int(geo.y() + y))
        ctrl.wheel.moved = True

    def shoot() -> None:
        if shot:
            ok = ctrl.wheel.grab_screen(shot)
            logger.info("screenshot %s -> %s", shot, ok)
        ctrl.wheel.close_wheel()
        ctrl.app.quit()

    QTimer.singleShot(250, place_cursor)
    QTimer.singleShot(1300, shoot)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--parent-pid", type=int, default=0)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--shot", default="")
    parser.add_argument("--hover", type=int, default=None)
    parser.add_argument("--trigger", default="")
    parser.add_argument("--catalog", action="store_true", help="list the community catalog")
    parser.add_argument("--catalog-url", default="")
    parser.add_argument("--catalog-path", default="")
    parser.add_argument("--catalog-import", default="", metavar="NAME")
    parser.add_argument("--yes", action="store_true", help="confirm a catalog import")
    parser.add_argument("--allow-license", action="store_true",
                        help="import even when the license is not permissive")
    args = parser.parse_args()

    setup_logging()
    cfg = load_config()
    if args.trigger:
        cfg["trigger"] = args.trigger

    if args.list:
        for s in discover(cfg, args.workspace or None):
            print(f"/{s.command:<40} {s.source:<8} {s.usage:>3}  {s.description[:60]}")
        return 0

    if args.catalog or args.catalog_import:
        from catalog import import_entry, load_index
        entries, errors = load_index(args.catalog_url, args.catalog_path)
        if args.catalog_import:
            match = next((e for e in entries if e.name == args.catalog_import), None)
            if match is None:
                print(f"not found in catalog: {args.catalog_import}", file=sys.stderr)
                return 2
            print(f"{match.name}: {match.description}")
            print(f"  repo:    {match.repo}")
            print(f"  license: {match.license or 'unknown'}")
            print(f"  source:  {match.source_url or match.raw_url}")
            print(f"  target:  {Path.home() / '.claude' / 'skills' / match.name}")
            if not args.yes:
                print("re-run with --yes to import.", file=sys.stderr)
                return 1
            try:
                path = import_entry(match, allow_license=args.allow_license)
            except Exception as exc:
                print(f"import failed: {exc}", file=sys.stderr)
                return 3
            print(f"imported -> {path}")
            return 0
        for e in entries:
            lic = e.license or "?"
            print(f"{e.name:<32} {lic:<14} {e.repo:<30} {e.description[:50]}")
        for err in errors:
            print(f"skip: {err}", file=sys.stderr)
        print(f"{len(entries)} entries")
        return 0

    mutex = wininput.create_single_instance("SkillWheelOverlaySingleton")
    if mutex is None and not args.demo:
        logger.info("another instance is running, exiting")
        return 0

    QtWidgets.QApplication.setQuitOnLastWindowClosed(False)
    app = QtWidgets.QApplication(sys.argv[:1])
    app.setApplicationName("Skill Wheel")

    ctrl = Controller(cfg, args.workspace or None, args.port, app)
    ctrl.demo_mode = bool(args.demo)
    ctrl.start_hotkey()
    ctrl._reload()

    if args.demo:
        run_demo(ctrl, args.shot or None, args.hover)

    if args.parent_pid:
        def watch() -> None:
            if not wininput.process_alive(args.parent_pid):
                logger.info("parent process gone, quitting")
                ctrl.quit()
            else:
                QTimer.singleShot(2500, watch)
        QTimer.singleShot(2500, watch)

    app.aboutToQuit.connect(lambda: ctrl.hotkey and ctrl.hotkey.stop())
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
