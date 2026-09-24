"""Safety helpers: release stuck input, deny dangerous operations."""

from __future__ import annotations

import logging
import sys
import time
from typing import Iterable

logger = logging.getLogger(__name__)

# Keys that must never be left held down.
MODIFIER_KEYS = ("ctrl", "shift", "alt", "win", "command")

# Hotkey combinations the workload must never emit.
DENIED_HOTKEYS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("ctrl", "s"),
        ("ctrl", "shift", "s"),
        ("ctrl", "n"),
        ("ctrl", "w"),
        ("ctrl", "k", "w"),
        ("ctrl", "shift", "n"),
        ("alt", "f4"),
        ("ctrl", "q"),
    }
)

# Substrings banned from typed terminal / search payloads.
DENIED_COMMAND_FRAGMENTS: frozenset[str] = frozenset(
    {
        "rm ",
        "del ",
        "format ",
        "git reset",
        "git clean",
        "npm publish",
        "deploy",
        "rmdir",
        "rd /s",
        "Remove-Item",
    }
)


def is_denied_hotkey(keys: Iterable[str]) -> bool:
    normalized = tuple(k.lower() for k in keys)
    return normalized in DENIED_HOTKEYS


def is_denied_command(text: str) -> bool:
    lower = text.lower()
    return any(frag.lower() in lower for frag in DENIED_COMMAND_FRAGMENTS)


class SafetyManager:
    """Release modifiers/buttons and validate actions."""

    def __init__(self) -> None:
        self._configure_pyautogui()

    def _configure_pyautogui(self) -> None:
        try:
            import pyautogui

            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.02
        except Exception as exc:  # pragma: no cover - import optional on CI
            logger.warning("pyautogui unavailable: %s", exc)

    def emergency_release(self) -> None:
        """Release all mouse buttons and common modifier keys."""
        try:
            import pyautogui
            from pyautogui import mouseUp

            for btn in ("left", "right", "middle"):
                try:
                    mouseUp(button=btn)
                except Exception:
                    pass

            for key in MODIFIER_KEYS:
                try:
                    pyautogui.keyUp(key)
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("emergency_release failed: %s", exc)

        if sys.platform == "win32":
            self._win32_release_modifiers()

    def _win32_release_modifiers(self) -> None:
        try:
            import ctypes

            # Virtual-key codes for Ctrl, Shift, Alt, Win
            vk_codes = (0x11, 0x10, 0x12, 0x5B, 0x5C)
            KEYEVENTF_KEYUP = 0x0002
            for vk in vk_codes:
                ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        except Exception as exc:
            logger.warning("win32 modifier release failed: %s", exc)

    def assert_safe_hotkey(self, *keys: str) -> None:
        if is_denied_hotkey(keys):
            raise PermissionError(f"Denied hotkey blocked: {'+'.join(keys)}")

    def assert_safe_text(self, text: str) -> None:
        if is_denied_command(text):
            raise PermissionError(f"Denied command fragment in text: {text!r}")

    def undo_pending_edits(self, count: int = 5, stop_check=None) -> int:
        """Best-effort Ctrl+Z flood to revert temporary markers."""
        done = 0
        try:
            import pyautogui

            for _ in range(max(0, count)):
                if stop_check and stop_check():
                    break
                self.assert_safe_hotkey("ctrl", "z")
                pyautogui.hotkey("ctrl", "z")
                done += 1
                time.sleep(0.05)
            # Dismiss find/terminal UI if open
            pyautogui.press("escape")
            time.sleep(0.05)
            pyautogui.press("escape")
        except Exception as exc:
            logger.warning("undo_pending_edits failed: %s", exc)
        return done
