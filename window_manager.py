"""Detect and activate VS Code / Cursor windows (Windows)."""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

logger = logging.getLogger(__name__)

TargetFilter = Literal["auto", "vscode", "cursor"]

# Never treat QuirkCode itself as an IDE target.
RUNNER_TITLE_MARKERS = (
    "quirkcode",
    "qa workload runner",
)

VSCODE_MARKERS = ("visual studio code",)
# Require IDE-style Cursor titles; avoid accidental substring matches.
CURSOR_TITLE_SUFFIXES = (" - cursor",)


@dataclass
class TargetWindow:
    hwnd: int
    title: str
    kind: Literal["vscode", "cursor"]
    rect: Tuple[int, int, int, int]  # left, top, right, bottom

    @property
    def width(self) -> int:
        return max(0, self.rect[2] - self.rect[0])

    @property
    def height(self) -> int:
        return max(0, self.rect[3] - self.rect[1])

    @property
    def center(self) -> Tuple[int, int]:
        l, t, r, b = self.rect
        return ((l + r) // 2, (t + b) // 2)


def is_runner_title(title: str) -> bool:
    lower = (title or "").lower().strip()
    if not lower:
        return False
    return any(m in lower for m in RUNNER_TITLE_MARKERS)


def _classify_title(title: str) -> Optional[Literal["vscode", "cursor"]]:
    lower = (title or "").lower().strip()
    if not lower or is_runner_title(lower):
        return None

    if any(m in lower for m in VSCODE_MARKERS):
        return "vscode"

    # Cursor IDE titles typically look like: "file.ts - Project - Cursor"
    if lower.endswith("cursor") or any(suf in lower for suf in CURSOR_TITLE_SUFFIXES):
        # Exclude generic apps that only mention the word casually
        if "visual studio code" in lower:
            return "vscode"
        return "cursor"

    return None


def _windows_backend_available() -> bool:
    return sys.platform == "win32"


def find_target_windows(target: TargetFilter = "auto") -> List[TargetWindow]:
    """Return matching IDE windows. Never includes QuirkCode."""
    if not _windows_backend_available():
        return []

    import win32gui

    results: List[TargetWindow] = []

    def enum_handler(hwnd: int, _acc) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd) or ""
        if not title.strip() or is_runner_title(title):
            return
        kind = _classify_title(title)
        if kind is None:
            return
        if target == "vscode" and kind != "vscode":
            return
        if target == "cursor" and kind != "cursor":
            return
        try:
            rect = win32gui.GetWindowRect(hwnd)
        except Exception:
            return
        # Skip tiny / invalid windows
        if (rect[2] - rect[0]) < 200 or (rect[3] - rect[1]) < 200:
            return
        results.append(TargetWindow(hwnd=hwnd, title=title, kind=kind, rect=rect))

    win32gui.EnumWindows(enum_handler, None)
    return results


def get_foreground_target(target: TargetFilter = "auto") -> Optional[TargetWindow]:
    """If the foreground window is a matching IDE, return it."""
    if not _windows_backend_available():
        return None
    import win32gui

    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd) or ""
        if is_runner_title(title):
            return None
        kind = _classify_title(title)
        if kind is None:
            return None
        if target == "vscode" and kind != "vscode":
            return None
        if target == "cursor" and kind != "cursor":
            return None
        rect = win32gui.GetWindowRect(hwnd)
        return TargetWindow(hwnd=int(hwnd), title=title, kind=kind, rect=rect)
    except Exception:
        return None


def pick_initial_window(target: TargetFilter = "auto") -> Optional[TargetWindow]:
    """Prefer the already-focused IDE; otherwise first discovered target."""
    fg = get_foreground_target(target)
    if fg:
        return fg
    windows = find_target_windows(target)
    return windows[0] if windows else None


def pick_other_ide_window(
    current: TargetWindow,
    target: TargetFilter = "auto",
) -> Optional[TargetWindow]:
    """
    For Auto mode: pick a different IDE app (Cursor <-> VS Code) when available.
    Never returns QuirkCode. Prefer opposite kind; else another window of same kind.
    """
    windows = find_target_windows(target if target != "auto" else "auto")
    windows = [w for w in windows if w.hwnd != current.hwnd and not is_runner_title(w.title)]
    if not windows:
        return None

    opposite = [w for w in windows if w.kind != current.kind]
    if opposite and target == "auto":
        return opposite[0]
    return windows[0]


def activate_target_window(window: TargetWindow) -> bool:
    """Bring the target IDE window to the foreground. Never activates QuirkCode."""
    if not _windows_backend_available():
        raise RuntimeError(
            "QuirkCode requires Windows. "
            "Window activation is not available on this platform."
        )

    if is_runner_title(window.title):
        logger.warning("Refusing to activate QuirkCode window")
        return False

    import win32con
    import win32gui

    hwnd = window.hwnd
    try:
        title = win32gui.GetWindowText(hwnd) or ""
        if is_runner_title(title) or _classify_title(title) is None:
            logger.warning("Refusing to activate non-IDE window: %s", title)
            return False

        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        try:
            import ctypes

            user32 = ctypes.windll.user32
            foreground = user32.GetForegroundWindow()
            # If QuirkCode is foreground, still switch to IDE — do not stay on runner
            if foreground:
                current_thread = user32.GetWindowThreadProcessId(hwnd, None)
                foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
                if foreground_thread != current_thread:
                    user32.AttachThreadInput(foreground_thread, current_thread, True)
                    win32gui.SetForegroundWindow(hwnd)
                    user32.AttachThreadInput(foreground_thread, current_thread, False)
                else:
                    win32gui.SetForegroundWindow(hwnd)
            else:
                win32gui.SetForegroundWindow(hwnd)
        except Exception:
            win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.15)
        return is_target_window_active(window)
    except Exception as exc:
        logger.warning("activate_target_window failed: %s", exc)
        return False


def is_target_window_active(window: TargetWindow) -> bool:
    if not _windows_backend_available():
        return False
    import win32gui

    try:
        fg = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(fg) or ""
        if is_runner_title(title):
            return False
        return int(fg) == int(window.hwnd)
    except Exception:
        return False


def is_ide_foreground(target: TargetFilter = "auto") -> bool:
    return get_foreground_target(target) is not None


def refresh_window(window: TargetWindow) -> Optional[TargetWindow]:
    """Re-read rect/title for an existing hwnd."""
    if not _windows_backend_available():
        return None
    import win32gui

    try:
        if not win32gui.IsWindow(window.hwnd):
            return None
        title = win32gui.GetWindowText(window.hwnd) or window.title
        if is_runner_title(title):
            return None
        rect = win32gui.GetWindowRect(window.hwnd)
        kind = _classify_title(title) or window.kind
        return TargetWindow(hwnd=window.hwnd, title=title, kind=kind, rect=rect)
    except Exception:
        return None


def get_client_point(
    window: TargetWindow,
    fx: float,
    fy: float,
) -> Tuple[int, int]:
    """Map fractional client coordinates (0–1) to screen pixels."""
    l, t, r, b = window.rect
    inset_x = int((r - l) * 0.02)
    inset_y = int((b - t) * 0.05)
    left = l + inset_x
    top = t + inset_y
    width = max(1, (r - l) - 2 * inset_x)
    height = max(1, (b - t) - 2 * inset_y)
    fx = min(1.0, max(0.0, fx))
    fy = min(1.0, max(0.0, fy))
    return (int(left + fx * width), int(top + fy * height))


UI_REGIONS = {
    "editor": (0.55, 0.45),
    "tabs": (0.45, 0.08),
    "explorer": (0.12, 0.40),
    "terminal": (0.55, 0.88),
    "scrollbar": (0.98, 0.50),
    "search": (0.70, 0.12),
}


def assert_windows_platform() -> None:
    if not _windows_backend_available():
        raise RuntimeError(
            "QuirkCode only runs on Windows 10/11. "
            "Install dependencies on a Windows machine to generate workload activity."
        )
