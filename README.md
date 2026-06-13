# d2aa — Dota 2 match-found phone notifier

Get a push notification on your phone the moment Dota 2 finds a match, so you can
walk away while queuing and come back to accept. **Notification only — it does not
click Accept for you.**

It works by watching a small spot on your screen for the green **Accept** popup and
sending a push via [ntfy](https://ntfy.sh) (free, no account).

```
Dota 2  -->  d2aa watches the screen  -->  ntfy push  -->  phone
```

## ⚠️ Use at your own risk

This is a personal hobby project, provided **as-is and with no warranty of any
kind**. Use it **entirely at your own risk**.

The author is **not responsible** for anything that results from using it —
including but not limited to bugs, crashes, unexpected behavior, missed matches,
abandons, account penalties, suspensions, or bans. It is not affiliated with or
endorsed by Valve. By downloading or running it, **you accept full responsibility
for any consequences.** If you're not comfortable with that, don't use it.

---

# How to use

You only need to do the one-time setup once. After that it's just "run it before
you queue."

> **Before you start:** run Dota in **Borderless** or **Windowed** mode (not
> exclusive fullscreen). Alt-tab is instant and the screen captures reliably;
> exclusive fullscreen can capture a black screen, especially on Windows.

## Step 1 — Download

Go to the [**Releases**](../../releases) page and download the file for your system:

- **Windows:** `d2aa.exe`
- **Linux:** `d2aa`

No installer — it's a single file.

## Step 2 — Open it

- **Windows:** **double-click `d2aa.exe`.** A terminal window opens with a menu.
  (If Windows warns about an unknown app, click *More info → Run anyway*.)
- **Linux:** make it runnable once with `chmod +x d2aa`, then run `./d2aa`.

You'll see a simple menu — use the **↑/↓ arrow keys** and **Enter** to pick things.
No commands to memorize:

```
▶ What would you like to do?  (↑/↓, Enter)
❯ Set up / calibrate
  Test phone notification
  Start watching for a match
  Tune detection (live monitor)
  Show my ntfy / phone setup
  Quit
```

## Step 3 — Pick "Set up / calibrate"

A short wizard walks you through teaching it where your Accept button is:

1. **Queue a Dota match** so the green **Accept** popup can appear.
2. On **Linux** a "share your screen" box pops up — pick **Entire Screen** and Share.
   (Windows has no such box.)
3. When the popup is showing, **press Enter** to start a 5-second countdown, then
   **click back into Dota** so the Accept popup is on screen when it snaps a picture.
4. A window opens with that screenshot — **click the green Accept button**, then click
   the same spot again to **confirm**.

It saves your settings and shows you a **topic name** (your private notification
channel).

## Step 4 — Connect your phone

1. Install the **ntfy** app ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   / [iOS](https://apps.apple.com/us/app/ntfy/id1625396347)).
2. In the app, **subscribe** to the exact **topic name** the wizard showed you.

## Step 5 — Pick "Test phone notification"

Your phone should buzz with a test notification. If it does, you're set.

## Step 6 — Pick "Start watching for a match"

Do this **before/while you queue**, then walk away. When a match is found, your phone
gets a push. Keep Dota visible while it runs (it can only see what's on screen). Press
**Ctrl-C** to stop watching and return to the menu.

### If detection misses or false-fires

Pick **Tune detection (live monitor)** from the menu. It shows a live match bar without
notifying — trigger the Accept popup and watch it: the bar should jump high and hold. If
it's off, just run **Set up / calibrate** again and click more squarely on the solid
green of the button.

> On Linux (GNOME Wayland) the screen-share box appears once each time you start
> watching. It only asks once per launch.

---

# Reference

## Where settings are stored

`~/.config/d2aa/config.toml` (Linux) or `%APPDATA%\d2aa\config.toml` (Windows). You
normally never edit this by hand — the wizard writes it for you.

```toml
[detector]
backend = "pixel"          # "pixel" (screen) or "console" (Game Coordinator log, Linux)

[detector.console]
log_path = "auto"          # "auto" finds Dota's console.log, or an explicit path
triggers = ["k_EMsgGCReadyUpStatus"]

[ntfy]
server = "https://ntfy.sh"
topic  = "d2aa-XXXXXXXX"   # your private push channel (keep it to yourself)
priority = 5

[calibration]                # only used by the pixel backend
x = 0.5                    # fractional screen coords (survive resolution changes)
y = 0.72
color = [108, 168, 50]     # sampled Accept-button color
tolerance = 40             # per-pixel color match sensitivity
region = 28                # size of the box checked around the spot
min_fraction = 0.40        # how much of that box must match to count

[runtime]
poll_interval = 0.25       # seconds between checks
cooldown = 30              # min seconds between notifications
confirm_frames = 3         # consecutive hits required before notifying
```

## How it works

Detection is **pluggable** — everything sits behind a `Detector` interface
(`start/poll/stop`) so new methods can drop in without touching the rest:

- **`pixel`** — watches a calibrated screen region. Works on Windows + Linux; needs
  Dota visible.
- **`console`** (Linux only) — reads Dota's **Game Coordinator log** (`console.log`,
  written by the launch options `-condebug -conclearlog`) and fires the instant the
  ready-check appears. Resolution-independent, no calibration, works even when Dota is
  minimized. Linux-only because `console.log` is buffered-until-exit on Windows.

Screen capture (pixel backend) is likewise abstracted: **mss** on Windows/X11, the
**PipeWire ScreenCast portal** on Wayland (where mss returns black for fullscreen games).

### Console detection setup (Linux)

1. Steam → Dota 2 → Properties → **Launch Options** → add `-condebug -conclearlog`, then
   restart Dota. (`-conclearlog` also keeps the log small — it's wiped each launch.)
2. In the d2aa menu: **Detection method → Console log**. It auto-finds `console.log`
   across all your Steam libraries (it reads `libraryfolders.vdf`, so Dota on a second
   drive / custom library is handled — native, Flatpak, and Snap Steam too). No
   calibration needed. If your setup is unusual, set an explicit path in the config:
   `[detector.console] log_path = "/full/path/to/console.log"`.
3. Test penalty-free: create a **custom arcade lobby** (it uses the same ready-up
   messages as matchmaking) and run **Tune detection** to watch it fire.

---

# For developers

Run from source with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --extra wayland     # drop --extra wayland on Windows / X11-only
uv run d2aa                 # interactive menu (in a TTY)
```

Running `d2aa` in a terminal opens the menu. Flags skip it for direct/scripted use:
`--config`, `--test`, `--watch` (start watching, no menu), `--monitor`, `-v`. When
stdout isn't a TTY (pipe / service), bare `d2aa` starts watching instead of the menu.

Development:

```bash
uv sync --extra wayland --group dev
uv run ruff check src/      # lint
uv run pytest -q            # tests (no display/network needed)
uv run python scripts/check_capture.py   # prove screen capture returns a real frame
```

Build a single-file binary (PyInstaller can't cross-compile — each OS builds its
own; the GitHub Actions workflow builds both on a `v*` tag):

```bash
# Linux
uv run pyinstaller --onefile --name d2aa \
  --collect-submodules prompt_toolkit --collect-submodules questionary \
  --collect-all pipewire_capture pyi_entry.py
# Windows
uv run pyinstaller --onefile --name d2aa \
  --collect-submodules prompt_toolkit --collect-submodules questionary pyi_entry.py
```
