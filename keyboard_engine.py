"""Keyboard presses, hotkeys, and typing."""

from __future__ import annotations

import logging
import time
from typing import Iterable, Sequence

from safety import SafetyManager

logger = logging.getLogger(__name__)


class KeyboardEngine:
    def __init__(self, safety: SafetyManager, stop_check=None) -> None:
        self.safety = safety
        self.stop_check = stop_check or (lambda: False)

    def _pyautogui(self):
        import pyautogui

        return pyautogui

    def press(self, key: str) -> None:
        if self.stop_check():
            return
        self._pyautogui().press(key)

    def hotkey(self, *keys: str) -> None:
        if self.stop_check():
            return
        self.safety.assert_safe_hotkey(*keys)
        self._pyautogui().hotkey(*keys)

    def type_text(self, text: str, interval: float = 0.03) -> None:
        if self.stop_check():
            return
        self.safety.assert_safe_text(text)
        # write() is faster for ASCII; typewrite for compatibility
        pag = self._pyautogui()
        for ch in text:
            if self.stop_check():
                return
            pag.write(ch, interval=interval)

    def key_down(self, key: str) -> None:
        if self.stop_check():
            return
        self._pyautogui().keyDown(key)

    def key_up(self, key: str) -> None:
        self._pyautogui().keyUp(key)

    def chord_sequence(self, steps: Sequence[Iterable[str] | str]) -> None:
        for step in steps:
            if self.stop_check():
                return
            if isinstance(step, str):
                self.press(step)
            else:
                keys = list(step)
                if len(keys) == 1:
                    self.press(keys[0])
                else:
                    self.hotkey(*keys)
            time.sleep(0.04)
