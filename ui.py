"""Tkinter control UI for QuirkCode."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from config import AppConfig, load_config, save_config
from controller import TestController
from logger import EventLogger
from window_manager import find_target_windows


def _fmt_mmss(seconds: float) -> str:
    s = max(0, int(seconds))
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


class AppUI:
    WINDOW_TITLE = "QuirkCode"

    def __init__(self, root: tk.Tk, cfg: Optional[AppConfig] = None) -> None:
        self.root = root
        self.root.title(self.WINDOW_TITLE)
        self.root.minsize(420, 560)
        self._apply_window_icon()
        self.cfg = cfg or load_config()

        self.controller = TestController(self.cfg, EventLogger(), on_status=self._on_status)
        self._notified_run_end = False
        self._build()
        self._load_cfg_into_form()
        self._refresh_windows()
        self._poll()

    def _apply_window_icon(self) -> None:
        """Set taskbar/window icon from bundled assets."""
        from pathlib import Path
        import sys

        candidates = []
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).resolve().parent
            meipass = Path(getattr(sys, "_MEIPASS", base))
            candidates.extend(
                [
                    meipass / "assets" / "quirkcode_256.png",
                    meipass / "assets" / "quirkcode.png",
                    base / "assets" / "quirkcode_256.png",
                    base / "assets" / "quirkcode.png",
                    meipass / "assets" / "quirkcode.ico",
                    base / "assets" / "quirkcode.ico",
                ]
            )
        else:
            root = Path(__file__).resolve().parent
            candidates.extend(
                [
                    root / "assets" / "quirkcode_256.png",
                    root / "assets" / "quirkcode.png",
                    root / "assets" / "quirkcode.ico",
                ]
            )
        for path in candidates:
            if not path.exists():
                continue
            try:
                if path.suffix.lower() == ".ico":
                    self.root.iconbitmap(default=str(path))
                else:
                    icon = tk.PhotoImage(file=str(path))
                    self.root.iconphoto(True, icon)
                    self._icon_image = icon  # keep reference
                return
            except Exception:
                continue

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 4}
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="QuirkCode", font=("Segoe UI", 14, "bold")).pack(
            anchor=tk.W, **pad
        )
        ttk.Label(
            frm,
            text="Generates reversible IDE activity for tracker QA.\n"
            "Open VS Code/Cursor with multiple files before starting.\n"
            "Auto switches between Cursor and VS Code only — never QuirkCode.",
            wraplength=400,
        ).pack(anchor=tk.W, **pad)

        # Target
        tgt = ttk.LabelFrame(frm, text="Target", padding=8)
        tgt.pack(fill=tk.X, **pad)
        self.target_var = tk.StringVar(value=self.cfg.target)
        for label, val in (
            ("Auto", "auto"),
            ("VS Code", "vscode"),
            ("Cursor", "cursor"),
        ):
            ttk.Radiobutton(tgt, text=label, value=val, variable=self.target_var).pack(
                side=tk.LEFT, padx=6
            )
        ttk.Button(tgt, text="Refresh", command=self._refresh_windows).pack(side=tk.RIGHT)
        self.window_label = ttk.Label(frm, text="Windows: (scanning…)", wraplength=400)
        self.window_label.pack(anchor=tk.W, **pad)

        # Duration
        dur = ttk.LabelFrame(frm, text="Duration", padding=8)
        dur.pack(fill=tk.X, **pad)
        self.duration_preset = tk.StringVar(value="30")
        for mins in ("5", "15", "30", "60"):
            ttk.Radiobutton(
                dur, text=f"{mins} min", value=mins, variable=self.duration_preset,
                command=self._on_duration_preset,
            ).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(
            dur, text="Custom", value="custom", variable=self.duration_preset,
            command=self._on_duration_preset,
        ).pack(side=tk.LEFT, padx=4)
        self.custom_minutes = tk.StringVar(value=str(self.cfg.duration_minutes))
        self.custom_entry = ttk.Entry(dur, textvariable=self.custom_minutes, width=6)
        self.custom_entry.pack(side=tk.LEFT, padx=4)

        # Intensity
        inten = ttk.LabelFrame(frm, text="Intensity", padding=8)
        inten.pack(fill=tk.X, **pad)
        self.intensity_var = tk.StringVar(value=self.cfg.intensity)
        for label in ("low", "medium", "high"):
            ttk.Radiobutton(
                inten, text=label.capitalize(), value=label, variable=self.intensity_var
            ).pack(side=tk.LEFT, padx=8)

        # Features
        feat = ttk.LabelFrame(frm, text="Features", padding=8)
        feat.pack(fill=tk.X, **pad)
        self.enable_mouse = tk.BooleanVar(value=self.cfg.enable_mouse)
        self.enable_keyboard = tk.BooleanVar(value=self.cfg.enable_keyboard)
        self.enable_scrolling = tk.BooleanVar(value=self.cfg.enable_scrolling)
        self.enable_tab_switching = tk.BooleanVar(value=self.cfg.enable_tab_switching)
        self.enable_terminal = tk.BooleanVar(value=self.cfg.enable_terminal)
        self.preserve_workspace = tk.BooleanVar(value=self.cfg.preserve_workspace)
        for text, var in (
            ("Mouse", self.enable_mouse),
            ("Keyboard", self.enable_keyboard),
            ("Scrolling", self.enable_scrolling),
            ("Tab switching", self.enable_tab_switching),
            ("Terminal", self.enable_terminal),
            ("Preserve workspace", self.preserve_workspace),
        ):
            ttk.Checkbutton(feat, text=text, variable=var).pack(anchor=tk.W)

        # Seed
        seed_row = ttk.Frame(frm)
        seed_row.pack(fill=tk.X, **pad)
        ttk.Label(seed_row, text="Random seed (optional):").pack(side=tk.LEFT)
        self.seed_var = tk.StringVar(
            value="" if self.cfg.random_seed is None else str(self.cfg.random_seed)
        )
        ttk.Entry(seed_row, textvariable=self.seed_var, width=12).pack(side=tk.LEFT, padx=6)

        # Controls
        ctl = ttk.Frame(frm)
        ctl.pack(fill=tk.X, pady=10)
        self.btn_start = ttk.Button(ctl, text="Start", command=self._on_start)
        self.btn_pause = ttk.Button(ctl, text="Pause", command=self._on_pause, state=tk.DISABLED)
        self.btn_resume = ttk.Button(ctl, text="Resume", command=self._on_resume, state=tk.DISABLED)
        self.btn_stop = ttk.Button(ctl, text="STOP", command=self._on_stop, state=tk.DISABLED)
        self.btn_start.pack(side=tk.LEFT, padx=4)
        self.btn_pause.pack(side=tk.LEFT, padx=4)
        self.btn_resume.pack(side=tk.LEFT, padx=4)
        self.btn_stop.pack(side=tk.LEFT, padx=4)

        ttk.Label(
            frm,
            text="Emergency hotkey (Windows): Ctrl+Shift+F12",
            foreground="#666",
        ).pack(anchor=tk.W)

        # Status + stats
        stats = ttk.LabelFrame(frm, text="Live statistics", padding=8)
        stats.pack(fill=tk.BOTH, expand=True, **pad)
        self.status_var = tk.StringVar(value="Status: Idle")
        self.elapsed_var = tk.StringVar(value="Elapsed:       00:00")
        self.remaining_var = tk.StringVar(value="Remaining:     00:00")
        self.stats_text = tk.StringVar(value=self._stats_block({}))
        ttk.Label(stats, textvariable=self.status_var, font=("Segoe UI", 11, "bold")).pack(
            anchor=tk.W
        )
        ttk.Label(stats, textvariable=self.elapsed_var, font=("Consolas", 10)).pack(anchor=tk.W)
        ttk.Label(stats, textvariable=self.remaining_var, font=("Consolas", 10)).pack(anchor=tk.W)
        ttk.Label(stats, textvariable=self.stats_text, font=("Consolas", 10), justify=tk.LEFT).pack(
            anchor=tk.W, pady=6
        )

    def _stats_block(self, s: dict) -> str:
        return (
            f"Keyboard events:  {s.get('keyboard_events', 0)}\n"
            f"Mouse events:     {s.get('mouse_events', 0)}\n"
            f"Scroll events:    {s.get('scroll_events', 0)}\n"
            f"Tab switches:     {s.get('tab_switches', 0)}\n"
            f"Temporary edits:  {s.get('temporary_edits', 0)}\n"
            f"Sequences:        {s.get('sequences', 0)}"
        )

    def _on_duration_preset(self) -> None:
        preset = self.duration_preset.get()
        if preset != "custom":
            self.custom_minutes.set(preset)

    def _load_cfg_into_form(self) -> None:
        self.target_var.set(self.cfg.target)
        self.intensity_var.set(self.cfg.intensity)
        mins = str(self.cfg.duration_minutes)
        if mins in ("5", "15", "30", "60"):
            self.duration_preset.set(mins)
        else:
            self.duration_preset.set("custom")
        self.custom_minutes.set(mins)

    def _form_to_config(self) -> AppConfig:
        preset = self.duration_preset.get()
        if preset == "custom":
            duration = int(self.custom_minutes.get().strip() or "30")
        else:
            duration = int(preset)
        seed_raw = self.seed_var.get().strip()
        seed = int(seed_raw) if seed_raw else None
        return AppConfig(
            duration_minutes=duration,
            intensity=self.intensity_var.get(),  # type: ignore[arg-type]
            target=self.target_var.get(),  # type: ignore[arg-type]
            enable_mouse=self.enable_mouse.get(),
            enable_keyboard=self.enable_keyboard.get(),
            enable_scrolling=self.enable_scrolling.get(),
            enable_tab_switching=self.enable_tab_switching.get(),
            enable_terminal=self.enable_terminal.get(),
            preserve_workspace=self.preserve_workspace.get(),
            random_seed=seed,
        )

    def _refresh_windows(self) -> None:
        try:
            wins = find_target_windows(self.target_var.get())  # type: ignore[arg-type]
        except Exception as exc:
            self.window_label.config(text=f"Windows: error — {exc}")
            return
        if not wins:
            self.window_label.config(
                text="Windows: none detected (open VS Code/Cursor first)"
            )
            return
        lines = [f"Windows: {len(wins)} found"]
        for w in wins[:5]:
            lines.append(f"  • [{w.kind}] {w.title[:60]}")
        self.window_label.config(text="\n".join(lines))

    def _on_status(self, status: str) -> None:
        # Called from worker thread — schedule UI update
        self.root.after(0, lambda: self.status_var.set(f"Status: {status}"))

    def _on_start(self) -> None:
        try:
            cfg = self._form_to_config()
            cfg.validate()
        except Exception as exc:
            messagebox.showerror("Invalid configuration", str(exc))
            return
        save_config(cfg)
        self.cfg = cfg
        self.controller = TestController(cfg, EventLogger(), on_status=self._on_status)
        self._notified_run_end = False
        try:
            self.controller.start(cfg)
        except Exception as exc:
            messagebox.showerror("Cannot start", str(exc))
            return
        self.btn_start.config(state=tk.DISABLED)
        self.btn_pause.config(state=tk.NORMAL)
        self.btn_resume.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        # Keep QuirkCode visible but do not steal focus from the IDE
        try:
            self.root.lower()
            self.root.update_idletasks()
        except Exception:
            pass

    def _on_pause(self) -> None:
        self.controller.pause()
        self.btn_pause.config(state=tk.DISABLED)
        self.btn_resume.config(state=tk.NORMAL)

    def _on_resume(self) -> None:
        self.controller.resume()
        self.btn_pause.config(state=tk.NORMAL)
        self.btn_resume.config(state=tk.DISABLED)

    def _on_stop(self) -> None:
        self.controller.stop()
        self.btn_stop.config(state=tk.DISABLED)

    def _poll(self) -> None:
        ctrl = self.controller
        self.status_var.set(f"Status: {ctrl.get_status()}")
        self.elapsed_var.set(f"Elapsed:       {_fmt_mmss(ctrl.elapsed_time())}")
        self.remaining_var.set(f"Remaining:     {_fmt_mmss(ctrl.remaining_time())}")
        self.stats_text.set(self._stats_block(ctrl.logger.get_stats()))

        running = ctrl.is_running()
        if not running and self.btn_start["state"] == tk.DISABLED and not self._notified_run_end:
            self._notified_run_end = True
            self.btn_start.config(state=tk.NORMAL)
            self.btn_pause.config(state=tk.DISABLED)
            self.btn_resume.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.DISABLED)
            err = ctrl.get_error()
            if err:
                messagebox.showerror("Run failed", err)
            elif ctrl.get_status() == "Completed":
                report = getattr(ctrl.logger, "report_path", None)
                if report:
                    messagebox.showinfo(
                        "Run complete",
                        f"Workload finished.\nReport:\n{report}",
                    )

        self.root.after(250, self._poll)

    def on_close(self) -> None:
        if self.controller.is_running():
            if not messagebox.askyesno("Stop and exit?", "A test is running. Stop and exit?"):
                return
            self.controller.stop()
            self.controller.wait_until_done(timeout=5.0)
        self.root.destroy()


def launch(cfg: Optional[AppConfig] = None) -> None:
    root = tk.Tk()
    try:
        root.call("tk", "scaling", 1.25)
    except Exception:
        pass
    app = AppUI(root, cfg)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
