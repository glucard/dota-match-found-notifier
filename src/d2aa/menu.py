"""Interactive arrow-key menu — the friendly entry point.

Shown when a human runs ``d2aa`` in a terminal (or double-clicks the binary). It
is pure orchestration: every action calls an existing function (a setup flow, the
watch loop, the notifier) and reuses the rich console/theme so the look matches
the rest of the app. No detection/notify/config logic lives here.
"""

from __future__ import annotations

import sys

import questionary
from questionary import Choice, Style

from . import app, ui
from .config import Config, ConfigError, load
from .detect.console import resolve_console_log
from .gui import wizard

# Mirror the rich THEME (ui.py) so the menu blends in.
MENU_STYLE = Style(
    [
        ("qmark", "fg:magenta bold"),
        ("question", "bold"),
        ("pointer", "fg:magenta bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("answer", "fg:cyan bold"),
        ("instruction", "fg:#808080"),
        ("disabled", "fg:#808080 italic"),
    ]
)

_GATED = "set up first"


def _load_cfg_safe() -> Config | None:
    try:
        return load()
    except ConfigError:
        return None


def _ready_reason(cfg: Config | None) -> str | None:
    """Short disabled-reason if the selected backend isn't ready, else None.

    I/O-light (no screen capturer is built — that could prompt on Wayland).
    """
    if cfg is None:
        return _GATED
    if cfg.detector.backend.lower() == "console":
        ok = sys.platform == "linux" and resolve_console_log(cfg.detector.console_log_path)
        return None if ok else _GATED
    return None if cfg.calibration.calibrated else _GATED


def _run_setup(cfg: Config | None) -> None:
    """Run the setup flow for the currently-selected backend."""
    backend = cfg.detector.backend.lower() if cfg else "pixel"
    if backend == "console":
        from . import setup_console

        setup_console.run()
    else:
        wizard.run()


def _choose_method() -> None:
    current = (_load_cfg_safe() or Config()).detector.backend.lower()
    choice = questionary.select(
        "Detection method",
        choices=[
            Choice("Screen (pixel) — works on Windows + Linux", value="pixel"),
            Choice("Console log (Game Coordinator) — Linux only", value="console"),
        ],
        default="console" if current == "console" else "pixel",
        style=MENU_STYLE,
        qmark="▶",
        pointer="❯",
    ).ask()
    if choice is None:
        return
    if choice == "console":
        from . import setup_console

        setup_console.run()
    else:
        wizard.run()


def _header(cfg: Config | None) -> None:
    ui.console.clear()
    ui.console.print(ui.APP_TITLE)
    if _ready_reason(cfg) is not None:
        ui.panel(
            "[warn]Not set up yet.[/] Pick [accent]Detection method[/] (screen or "
            "console),\nthen [accent]Set up detection[/] to get started.",
            title="welcome",
            style="warn",
        )
    else:
        method = "console log" if cfg.detector.backend.lower() == "console" else "screen"
        ui.console.print(
            f"[muted]method[/] [key]{method}[/]  [muted]·[/]  "
            f"[muted]topic[/] [topic]{cfg.ntfy.topic}[/]  [muted]·[/]  [ok]ready ✓[/]\n"
        )


def _build_choices(cfg: Config | None) -> list[Choice]:
    gate = _ready_reason(cfg)
    return [
        Choice("Start watching for a match", value="watch", disabled=gate),
        Choice("Set up detection", value="setup"),
        Choice("Detection method (screen / console)", value="method"),
        Choice("Test phone notification", value="test", disabled=gate),
        Choice("Tune detection (live monitor)", value="monitor", disabled=gate),
        Choice("Show my ntfy / phone setup", value="info"),
        Choice("Quit", value="quit"),
    ]


def show_phone_setup(cfg: Config) -> None:
    """Phone-setup panel, shared by the menu and the setup flows."""
    ui.panel(
        "[key]1.[/] Install the [topic]ntfy[/] app on your phone (Android / iOS).\n"
        f"[key]2.[/] Subscribe to this topic:  [topic]{cfg.ntfy.topic}[/]\n"
        f"   [muted]server: {cfg.ntfy.server}[/]\n\n"
        "[muted]Use[/] [accent]Test phone notification[/] [muted]to confirm it works.[/]",
        title="📱 Phone setup",
        style="info",
    )


def _dispatch(action: str) -> bool:
    """Run one menu action. Return False to exit the loop, True to keep looping."""
    if action == "setup":
        _run_setup(_load_cfg_safe())
    elif action == "method":
        _choose_method()
    elif action == "watch":
        app.run(load())  # blocks until Ctrl-C, then returns cleanly
    elif action == "monitor":
        app.run(load(), monitor=True)
    elif action == "test":
        from .cli import send_test

        send_test(load())
    elif action == "info":
        show_phone_setup(load())
    return action != "quit"


def run_menu() -> int:
    while True:
        cfg = _load_cfg_safe()
        _header(cfg)
        action = questionary.select(
            "What would you like to do?",
            choices=_build_choices(cfg),
            style=MENU_STYLE,
            qmark="▶",
            pointer="❯",
            instruction="(↑/↓, Enter)",
        ).ask()

        # None == Esc / Ctrl-C at the prompt -> treat as Quit.
        if action is None or action == "quit":
            ui.console.print("[muted]Bye![/]")
            return 0

        try:
            _dispatch(action)
        except ConfigError as exc:
            ui.error(str(exc))

        questionary.press_any_key_to_continue(
            "Press any key to return to the menu…", style=MENU_STYLE
        ).ask()
