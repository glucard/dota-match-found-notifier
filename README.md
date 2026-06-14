# d2kit — Dota 2 toolbox

Two Dota 2 tools in one program, driven by a simple arrow-key menu:

- **🔔 Match notifier** — pings your phone the moment Dota finds a match, so you can
  walk away while queuing and come back to accept. (Notification only — it does *not*
  click Accept for you.)
- **📊 Stats** — compares one of your matches' timings (items, net worth, CS, levels)
  against **your own recent mean** and **pro players' ranked pubs**, via the STRATZ API.

```
d2kit            ->  interactive menu  ->  pick a tool
match notifier   ->  watches Dota      ->  ntfy push  ->  phone
stats            ->  STRATZ API        ->  this match | your mean | pro mean
```

## ⚠️ Use at your own risk

Personal hobby project, provided **as-is and with no warranty of any kind**. Use it
**entirely at your own risk**. The author is **not responsible** for anything that
results from using it — including bugs, crashes, unexpected behavior, missed matches,
abandons, account penalties, suspensions, or bans. Not affiliated with or endorsed by
Valve. By downloading or running it, **you accept full responsibility.**

---

# How to use

## Get it

- **Prebuilt binary:** download `d2kit` (Linux) / `d2kit.exe` (Windows) from
  [**Releases**](../../releases). Single file, no install.
  - **Windows:** double-click `d2kit.exe` (if SmartScreen warns: *More info → Run anyway*).
  - **Linux:** `chmod +x d2kit`, then `./d2kit`.
- **From source:** `uv sync --extra wayland` then `uv run d2kit`.

Running `d2kit` opens the menu — use **↑/↓** and **Enter**:

```
d2kit · Dota 2 toolbox
── Match notifier ──
  Start watching for a match · Set up detection · Detection method · Test phone · Tune (monitor)
── Stats ──
  Compare a match vs your mean + pros · Set up STRATZ token / Steam id
  Show my ntfy / phone setup · Quit
```

## Match notifier (one-time setup)

1. **Set up detection** — choose how it detects a found match:
   - **Console log (recommended, Linux + Windows):** add `-condebug -conclearlog` to Dota's
     Steam launch options, restart Dota. Reads the Game Coordinator log — no calibration,
     works even minimized. (See [details](#console-detection).)
   - **Screen (pixel):** a guided click-calibration of the green **Accept** button. Needs
     Dota visible.
2. **Connect your phone:** install the **ntfy** app
   ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) /
   [iOS](https://apps.apple.com/us/app/ntfy/id1625396347)) and **subscribe** to the topic
   d2kit shows you.
3. **Test phone notification** → your phone should buzz.
4. **Start watching for a match** before you queue, then walk away. Ctrl-C returns to the menu.

If detection misses or false-fires (pixel), use **Tune detection (live monitor)**.

## Stats (one-time setup)

1. Get a free STRATZ token: sign in at [stratz.com](https://stratz.com) →
   [stratz.com/api](https://stratz.com/api) (read-only, revocable).
2. **Set up STRATZ token / Steam id** in the menu (paste the token, enter your Steam32 id).
3. **Compare a match vs your mean + pros** — pick a recent match; it renders a
   `this match | you | pro` table with colored deltas for item timings, CS@10/20, net worth,
   and level timings.

> Why pro *ranked pubs*, not tournaments? Tournament samples are too thin per patch; top pros'
> everyday ranked games are high-volume, current-patch, and clearly above Divine/Immortal.

---

# Reference

## Is the notifier bannable?

It's notification-only — it reads your screen or a log file and sends an HTTP request; it
never touches the game or automates input. Still: see the at-your-own-risk note above.

## Where settings are stored

One file at `~/.config/d2kit/config.toml` (Linux) / `%APPDATA%\d2kit\config.toml` (Windows),
chmod `0600` (it can hold your STRATZ token). The menu writes it for you. On first run it
**migrates** any old `d2aa` / `dota-stats` configs automatically.

```toml
[detector]
backend = "pixel"            # "pixel" (screen) or "console" (Game Coordinator log)
[detector.console]
log_path = "auto"            # "auto" searches your Steam libraries, or an explicit path
triggers = ["k_EMsgGCReadyUpStatus"]

[ntfy]
server = "https://ntfy.sh"
topic  = "d2kit-XXXXXXXX"    # your private push channel (keep it to yourself)

[calibration]                # pixel backend only (x/y fractional, color, tolerance, …)

[runtime]
poll_interval = 0.25
cooldown = 30                # min seconds between notifications
confirm_frames = 3

[stats]
stratz_api_token = ""        # or set the STRATZ_API_TOKEN env var (overrides this)
account_id = 0               # your Steam32 / friend id
last_n = 20                  # recent matches forming your personal mean
filter_turbo = true
```

## How detection works

Pluggable behind a `Detector` interface (`start/poll/stop`):

- **`console`** (Linux + Windows) — tails Dota's `console.log` (written by `-condebug
  -conclearlog`) and fires the instant the Game Coordinator logs `k_EMsgGCReadyUpStatus`.
  Resolution-independent, no calibration, works minimized. The more reliable backend.
- **`pixel`** — watches a calibrated screen region for the green Accept button. Capture is
  `mss` on Windows/X11 and the **PipeWire ScreenCast portal** on Wayland (where `mss` is black).

### Console detection {#console-detection}

Add `-condebug -conclearlog` to Dota → **Launch Options**, restart Dota, then pick
**Detection method → Console log**. It auto-finds `console.log` across all Steam libraries
(reads `libraryfolders.vdf` — second drives, Flatpak/Snap on Linux, default Windows install).
Test it penalty-free with a **custom arcade lobby** (same ready-up messages as matchmaking)
via **Tune detection**.

---

# For developers

```bash
uv sync --extra wayland --group dev
uv run d2kit                 # interactive menu
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
uv run mypy
uv run pytest -q
```

Flags (skip the menu): `--config`, `--test`, `--watch`, `--monitor`, `--stats`, `-v`. When
stdout isn't a TTY (pipe / service), bare `d2kit` starts watching instead of opening the menu.

Layout: `src/d2kit/` is the notifier (capture / detect / notify / gui) plus shared `ui` /
`config` (pydantic) / `cli` / `menu`; `src/d2kit/stats/` is the STRATZ comparison subpackage.

## Build a binary

PyInstaller can't cross-compile — each OS builds its own (CI does both on a `v*` tag;
`ci.yml` runs ruff + mypy + pytest on every push/PR).

```bash
# Linux
uv run pyinstaller --onefile --name d2kit \
  --collect-submodules prompt_toolkit --collect-submodules questionary \
  --collect-all pydantic --collect-all pipewire_capture pyi_entry.py
# Windows
uv run pyinstaller --onefile --name d2kit \
  --collect-submodules prompt_toolkit --collect-submodules questionary \
  --collect-all pydantic pyi_entry.py
```
