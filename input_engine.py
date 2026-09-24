"""Facade over mouse and keyboard engines."""

from __future__ import annotations

from typing import Optional, Tuple

from keyboard_engine import KeyboardEngine
from mouse_engine import MouseEngine
from safety import SafetyManager
from window_manager import TargetWindow


class InputEngine:
    def __init__(self, safety: Optional[SafetyManager] = None, stop_check=None) -> None:
        self.safety = safety or SafetyManager()
        self.stop_check = stop_check or (lambda: False)
        self.mouse = MouseEngine(stop_check=self.stop_check)
        self.keyboard = KeyboardEngine(self.safety, stop_check=self.stop_check)

    def set_stop_check(self, stop_check) -> None:
        self.stop_check = stop_check
        self.mouse.stop_check = stop_check
        self.keyboard.stop_check = stop_check

    def move_to_region(
        self,
        window: TargetWindow,
        region: str,
        duration: float = 0.25,
        rng=None,
    ) -> Tuple[int, int]:
        return self.mouse.move_to_region(
            window, region, duration=duration, rng=rng
        )

    def click(self, **kwargs) -> None:
        self.mouse.click(**kwargs)

    def double_click(self, **kwargs) -> None:
        self.mouse.double_click(**kwargs)

    def drag(self, start: Tuple[int, int], end: Tuple[int, int], duration: float = 0.35) -> None:
        self.mouse.drag(start, end, duration=duration)

    def scroll(self, amount: int) -> None:
        self.mouse.scroll(amount)

    def press(self, key: str) -> None:
        self.keyboard.press(key)

    def hotkey(self, *keys: str) -> None:
        self.keyboard.hotkey(*keys)

    def type_text(self, text: str, interval: float = 0.03) -> None:
        self.keyboard.type_text(text, interval=interval)
