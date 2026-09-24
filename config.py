"""Application paths and config loading/saving."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Literal, Optional


IntensityName = Literal["low", "medium", "high"]
TargetName = Literal["auto", "vscode", "cursor"]


def app_dir() -> Path:
    """Directory containing config.json and logs/ (next to exe when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def config_path() -> Path:
    return app_dir() / "config.json"


def logs_dir() -> Path:
    path = app_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class AppConfig:
    duration_minutes: int = 30
    intensity: IntensityName = "medium"
    target: TargetName = "auto"
    enable_mouse: bool = True
    enable_keyboard: bool = True
    enable_scrolling: bool = True
    enable_tab_switching: bool = True
    enable_terminal: bool = False
    preserve_workspace: bool = True
    random_seed: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        cfg = cls(**filtered)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.duration_minutes < 1:
            raise ValueError("duration_minutes must be >= 1")
        if self.intensity not in ("low", "medium", "high"):
            raise ValueError("intensity must be low, medium, or high")
        if self.target not in ("auto", "vscode", "cursor"):
            raise ValueError("target must be auto, vscode, or cursor")


# Intensity profile parameters (seconds / weights)
INTENSITY_PROFILES: dict[str, dict[str, Any]] = {
    "low": {
        "typing_burst_sec": (3.0, 10.0),
        "pause_sec": (2.0, 8.0),
        "action_pause_sec": (0.4, 1.2),
        "sequence_weights": {
            "A": 1.0,
            "B": 0.6,
            "C": 0.8,
            "D": 0.3,
        },
        "scroll_clicks": (-8, -2, 2, 6),
        "tab_switches_per_seq": (1, 2),
        "nav_steps": (2, 5),
    },
    "medium": {
        "typing_burst_sec": (2.0, 7.0),
        "pause_sec": (1.0, 5.0),
        "action_pause_sec": (0.2, 0.8),
        "sequence_weights": {
            "A": 1.0,
            "B": 1.0,
            "C": 1.0,
            "D": 0.5,
        },
        "scroll_clicks": (-12, -7, -3, 3, 5, 8),
        "tab_switches_per_seq": (1, 3),
        "nav_steps": (3, 8),
    },
    "high": {
        "typing_burst_sec": (1.0, 5.0),
        "pause_sec": (0.5, 3.0),
        "action_pause_sec": (0.1, 0.4),
        "sequence_weights": {
            "A": 1.0,
            "B": 1.2,
            "C": 1.2,
            "D": 0.8,
        },
        "scroll_clicks": (-15, -10, -6, -3, 3, 6, 10, 12),
        "tab_switches_per_seq": (2, 4),
        "nav_steps": (4, 12),
    },
}

SAFE_SEARCH_TERMS = [
    "def",
    "class",
    "import",
    "return",
    "function",
    "const",
    "TODO",
    "self",
    "True",
    "False",
]

TEMP_EDIT_MARKER = "QA_TEST_MARKER"
SAFE_TERMINAL_COMMAND = "echo QA_TEST"


def load_config(path: Optional[Path] = None) -> AppConfig:
    p = path or config_path()
    if not p.exists():
        cfg = AppConfig()
        save_config(cfg, p)
        return cfg
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return AppConfig.from_dict(data)


def save_config(cfg: AppConfig, path: Optional[Path] = None) -> None:
    cfg.validate()
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, indent=2)
        f.write("\n")
