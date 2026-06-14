"""Interactive arrow-key menu — the friendly entry point.

Shown when a human runs ``d2kit`` in a terminal (or double-clicks the binary). It
is pure orchestration: every action calls an existing function (a setup flow, the
watch loop, the notifier) and reuses the rich console/theme so the look matches
the rest of the app. No detection/notify/config logic lives here.
"""

from __future__ import annotations

import questionary
from questionary import Choice, Separator, Style

from . import app, ui
from .config import Config, ConfigError, load, resolve_token, save
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
        return None if resolve_console_log(cfg.detector.console.log_path) else _GATED
    return None if cfg.calibration.calibrated else _GATED


def _stats_ready_reason(cfg: Config | None) -> str | None:
    """Short disabled-reason if the stats tool isn't set up (token + account)."""
    if cfg is None or not resolve_token(cfg) or not cfg.stats.account_id:
        return _GATED
    return None


def _stats_setup() -> None:
    cfg = _load_cfg_safe() or Config()
    token = questionary.password(
        "STRATZ API token (free at stratz.com/api; blank = keep current):",
        style=MENU_STYLE,
    ).ask()
    account = questionary.text(
        "Your Steam32 / friend id:",
        default=str(cfg.stats.account_id or ""),
        style=MENU_STYLE,
    ).ask()
    if token:
        cfg.stats.stratz_api_token = token
    if account and account.strip().isdigit():
        cfg.stats.account_id = int(account)
    save(cfg)
    if _stats_ready_reason(cfg) is None:
        ui.console.print("[ok]✓ Stats ready.[/] Use [accent]Compare a match[/].")
    else:
        ui.console.print("[warn]Saved — but both a token and Steam id are needed to compare.[/]")


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
            Choice("Console log (Game Coordinator) — needs -condebug", value="console"),
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
    if cfg is None:
        ui.panel(
            "[warn]Welcome![/] Set up the [accent]match notifier[/] and/or the "
            "[accent]stats[/] tool from the menu below.",
            title="d2kit",
            style="warn",
        )
        return
    notifier = "[ok]ready ✓[/]" if _ready_reason(cfg) is None else "[muted]not set up[/]"
    stats = "[ok]ready ✓[/]" if _stats_ready_reason(cfg) is None else "[muted]not set up[/]"
    ui.console.print(f"[muted]notifier[/] {notifier}   [muted]·[/]   [muted]stats[/] {stats}\n")


def _build_choices(cfg: Config | None) -> list[Choice | Separator]:
    gate = _ready_reason(cfg)
    stats_gate = _stats_ready_reason(cfg)
    return [
        Separator("── Match notifier ──"),
        Choice("Start watching for a match", value="watch", disabled=gate),
        Choice("Set up detection", value="setup"),
        Choice("Detection method (screen / console)", value="method"),
        Choice("Test phone notification", value="test", disabled=gate),
        Choice("Tune detection (live monitor)", value="monitor", disabled=gate),
        Separator("── Stats ──"),
        Choice("Compare a match vs your mean + pros", value="stats", disabled=stats_gate),
        Choice("Set up STRATZ token / Steam id", value="stats_setup"),
        Separator(" "),
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
    elif action == "stats":
        from .stats.flow import compare

        compare(ui.console, load())
    elif action == "stats_setup":
        _stats_setup()
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
