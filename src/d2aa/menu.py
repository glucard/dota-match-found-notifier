"""Interactive arrow-key menu — the friendly entry point.

Shown when a human runs ``d2aa`` in a terminal (or double-clicks the binary). It
is pure orchestration: every action calls an existing function (the calibration
wizard, the watch loop, the notifier) and reuses the rich console/theme so the
look matches the rest of the app. No detection/notify/config logic lives here.
"""

from __future__ import annotations

import questionary
from questionary import Choice, Style

from . import app, ui
from .config import Config, ConfigError, load
from .gui import wizard

# Mirror the rich THEME (ui.py) so the menu blends in: accent=magenta,
# topic/highlight=cyan, ok=green, muted=dim.
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

_GATED = "set up first"  # disabled reason for actions that need calibration


def _load_cfg_safe() -> Config | None:
    try:
        return load()
    except ConfigError:
        return None


def _header(cfg: Config | None) -> None:
    ui.console.clear()
    ui.console.print(ui.APP_TITLE)
    if cfg is None or not cfg.calibration.calibrated:
        ui.panel(
            "[warn]Not set up yet.[/] Choose [accent]Set up / calibrate[/] first to "
            "teach d2aa\nwhere your green ACCEPT button is.",
            title="welcome",
            style="warn",
        )
    else:
        ui.console.print(
            f"[muted]topic[/] [topic]{cfg.ntfy.topic}[/]  [muted]·[/]  [ok]calibrated ✓[/]\n"
        )


def _build_choices(cfg: Config | None) -> list[Choice]:
    ready = cfg is not None and cfg.calibration.calibrated
    gate = None if ready else _GATED
    return [
        Choice("Set up / calibrate", value="config"),
        Choice("Test phone notification", value="test", disabled=gate),
        Choice("Start watching for a match", value="watch", disabled=gate),
        Choice("Tune detection (live monitor)", value="monitor", disabled=gate),
        Choice("Show my ntfy / phone setup", value="info"),
        Choice("Quit", value="quit"),
    ]


def _show_info(cfg: Config) -> None:
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
    if action == "config":
        wizard.run()
    elif action == "watch":
        app.run(load())  # blocks until Ctrl-C, then returns cleanly
    elif action == "monitor":
        app.run(load(), monitor=True)
    elif action == "test":
        from .cli import send_test

        send_test(load())
    elif action == "info":
        _show_info(load())
    return action != "quit"


def run_menu(verbose: bool = False) -> int:
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
