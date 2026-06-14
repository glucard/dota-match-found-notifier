"""Guided single-click calibration wizard.

Flow for a non-technical user:
  1. Queue a Dota bot match.
  2. When the green "Accept" popup shows, press Enter in the terminal.
  3. We grab one full-screen frame and show it in a window.
  4. User clicks once on the Accept button.
  5. We sample the button's color + position, save the config, and print the
     ntfy topic to subscribe to on the phone.

The click is read window-local from our own Canvas, so the Wayland "can't query
global cursor position" limitation never applies.
"""

from __future__ import annotations

import sys
import time

import numpy as np

from .. import ui
from ..capture import make_capturer
from ..capture.base import Frame
from ..config import Config, load, new_topic, save
from ..detect.pixel import match_fraction, patch_mean_rgb

_COUNTDOWN = 5  # seconds between starting calibration and the screen capture


def _fresh_config() -> Config:
    """A config with current tuning defaults, carrying over the user's ntfy
    topic and Wayland restore-token from any existing file.

    Recalibration should adopt the latest detection defaults (tolerance,
    min_fraction, confirm_frames, ...) rather than silently preserving stale
    values, while keeping the phone subscription the user already set up.
    """
    cfg = Config()
    try:
        old = load()
    except Exception:
        return cfg
    if old.ntfy.topic:
        cfg.ntfy = old.ntfy
    cfg.capture.restore_token = old.capture.restore_token
    return cfg


def _pick_point(frame_rgb: np.ndarray) -> tuple[float, float] | None:
    """Show the screenshot and return fractional (x, y) of a single click.

    ``frame_rgb`` is an HxWx3 uint8 RGB array. Returns None if the window is
    closed without a confirmed pick.
    """
    import tkinter as tk

    from PIL import Image, ImageTk

    h, w = frame_rgb.shape[:2]
    root = tk.Tk()
    root.title("d2kit calibration — click the Accept button")

    # Fit the screenshot within ~90% of the screen, keep the scale factor.
    sw = int(root.winfo_screenwidth() * 0.9)
    sh = int(root.winfo_screenheight() * 0.9)
    scale = min(sw / w, sh / h, 1.0)
    disp_w, disp_h = max(int(w * scale), 1), max(int(h * scale), 1)

    img = Image.fromarray(frame_rgb).resize((disp_w, disp_h), Image.Resampling.BILINEAR)
    photo = ImageTk.PhotoImage(img)

    result: dict[str, tuple[float, float]] = {}

    canvas = tk.Canvas(root, width=disp_w, height=disp_h, highlightthickness=0)
    canvas.pack()
    canvas.create_image(0, 0, anchor="nw", image=photo)
    # A subtle backdrop strip so the banner text stays readable over any frame.
    canvas.create_rectangle(0, 0, disp_w, 48, fill="#101014", outline="", stipple="gray50")
    banner = canvas.create_text(
        disp_w // 2,
        24,
        text="①  Click the green ACCEPT button          (Esc to cancel)",
        fill="#7CFC58",
        font=("TkDefaultFont", 16, "bold"),
    )

    def on_click(event: tk.Event) -> None:
        fx = (event.x / scale) / w
        fy = (event.y / scale) / h
        fx = min(max(fx, 0.0), 1.0)
        fy = min(max(fy, 0.0), 1.0)
        # Draw a marker and ask for confirmation.
        canvas.delete("marker")
        r = 14
        canvas.create_oval(
            event.x - r,
            event.y - r,
            event.x + r,
            event.y + r,
            outline="#00ff00",
            width=3,
            tags="marker",
        )
        canvas.itemconfig(
            banner,
            text="②  Click the same spot to CONFIRM, or click elsewhere to move",
            fill="#FFD040",
        )
        if result.get("_pending") == (round(fx, 4), round(fy, 4)):
            result["point"] = (fx, fy)
            root.destroy()
        else:
            result["_pending"] = (round(fx, 4), round(fy, 4))

    canvas.bind("<Button-1>", on_click)
    root.bind("<Escape>", lambda _e: root.destroy())
    root.mainloop()
    return result.get("point")


def run() -> int:
    cfg = _fresh_config()
    cap = make_capturer(cfg.capture)
    console = ui.console

    ui.panel(
        "Let's teach d2kit where the [ok]green ACCEPT button[/] appears.\n"
        "[muted]Tip: run Dota in Borderless/Windowed (not exclusive fullscreen) so[/]\n"
        "[muted]alt-tab is smooth and the screen captures reliably.[/]",
        title="d2kit · calibration",
        style="accent",
    )
    console.print("[key]1.[/] Queue a match so the green [ok]ACCEPT[/] popup can appear.")
    console.print(
        "[key]2.[/] If a screen-share picker appears, choose [key]Entire Screen[/] and Share."
    )
    console.print(
        f"[key]3.[/] Press Enter to start a [key]{_COUNTDOWN}s[/] countdown, then "
        "[accent]alt-tab back to Dota[/]\n"
        "   so the ACCEPT popup is on screen when it captures."
    )

    cap.start()
    try:
        console.input("\n[accent]▶[/]  Ready? Press [key]Enter[/] to start the countdown… ")
        with console.status("", spinner="dots") as status:
            for i in range(_COUNTDOWN, 0, -1):
                status.update(
                    f"[accent]Capturing in {i}s…[/]  [muted]show Dota + the ACCEPT popup[/]"
                )
                time.sleep(1)
        frame: Frame = cap.grab()  # BGR — taken while Dota is in front
        console.print("[ok]✓[/] [muted]Screen captured.[/]")
    finally:
        cap.stop()

    console.print("[muted]Opening the screenshot — click the ACCEPT button…[/]")
    frame_rgb = frame[:, :, ::-1].copy()  # BGR -> RGB for display
    point = _pick_point(frame_rgb)
    if point is None:
        ui.error("Calibration cancelled — nothing was saved.")
        return 1

    fx, fy = point
    color = patch_mean_rgb(frame, fx, fy, cfg.calibration.patch)
    cfg.calibration.x = round(fx, 4)
    cfg.calibration.y = round(fy, 4)
    cfg.calibration.color = [round(float(c)) for c in color]
    cfg.calibration.calibrated = True

    # Validate against the very frame we sampled: how much of the region matches?
    frac = match_fraction(frame, cfg.calibration, np.array(cfg.calibration.color, float))

    if not cfg.ntfy.topic:
        cfg.ntfy.topic = new_topic()

    path = save(cfg)

    strong = frac >= max(cfg.calibration.min_fraction * 1.5, 0.4)
    console.print()
    ui.panel(
        _calibration_summary(cfg, frac, strong),
        title="✓ Calibration saved",
        style="ok",
    )
    console.print(f"[muted]config: {path}[/]")
    if not strong:
        console.print(
            "[warn]Heads up:[/] that match is a bit low. For best results, re-run "
            "[accent]d2kit --config[/]\nand click squarely on the solid green of the "
            "ACCEPT button."
        )

    console.print()
    ui.panel(
        "[key]1.[/] Install the [topic]ntfy[/] app on your phone (Android / iOS).\n"
        f"[key]2.[/] Subscribe to this topic:  [topic]{cfg.ntfy.topic}[/]\n"
        f"   [muted]server: {cfg.ntfy.server}[/]\n\n"
        "[muted]Then run[/] [accent]d2kit[/] [muted]while you queue — you'll get a push "
        "when a match is found.[/]\n"
        "[muted]First, test it with[/] [accent]d2kit --test[/][muted].[/]",
        title="📱 Phone setup (one time)",
        style="info",
    )
    return 0


def _calibration_summary(cfg: Config, frac: float, strong: bool):
    """Renderable summarizing the saved calibration (presentation only)."""
    from rich.console import Group
    from rich.text import Text

    quality = Text("strong", style="ok") if strong else Text("weak", style="warn")
    return Group(
        Text.assemble(
            Text("spot   ", style="muted"),
            Text(f"x={cfg.calibration.x}, y={cfg.calibration.y}", style="key"),
        ),
        Text.assemble(Text("color  ", style="muted"), ui.color_swatch(cfg.calibration.color)),
        Text.assemble(
            Text("match  ", style="muted"),
            ui.match_bar(frac),
            Text(f"  {frac * 100:.0f}% ", style="key"),
            Text("(", style="muted"),
            quality,
            Text(f", fires at {cfg.calibration.min_fraction * 100:.0f}%)", style="muted"),
        ),
    )


if __name__ == "__main__":
    sys.exit(run())
