# 🖼 Wallpaper Manager

Automatic random wallpaper rotation for **GNOME on Wayland**.

Consists of two parts:

* **`wallpaper_daemon.py`** — runs in the background as a systemd user service, rotates wallpapers
* **`wallpaper_manager.py`** — TUI controller in the terminal, communicates with the daemon via Unix socket

---

## Requirements

* Python 3.10+
* GNOME + Wayland
* `textual` library

```
pip install textual --break-system-packages
```

---

## Installation

```
# 1. Copy the scripts
mkdir -p ~/.local/bin
cp wallpaper_daemon.py ~/.local/bin/
cp wallpaper_manager.py ~/.local/bin/

# 2. Install the systemd service
mkdir -p ~/.config/systemd/user
cp wallpaper-daemon.service ~/.config/systemd/user/

# 3. Start the daemon
systemctl --user daemon-reload
systemctl --user enable wallpaper-daemon
systemctl --user start wallpaper-daemon
```

The daemon will start automatically on every login.

---

## Usage

### TUI Controller

```
python3 ~/.local/bin/wallpaper_manager.py
```

| Key | Action |
| --- | --- |
| `N` | Immediately change wallpaper |
| `Space` | Pause / Resume rotation |
| `R` | Refresh status |
| `Q` | Close TUI |

### Daemon Management

```
# Status
systemctl --user status wallpaper-daemon

# Stop / Start / Restart
systemctl --user stop wallpaper-daemon
systemctl --user start wallpaper-daemon
systemctl --user restart wallpaper-daemon

# Logs
journalctl --user -u wallpaper-daemon -f
```

---

## Configuration

The config is automatically saved to `~/.config/wallpaper-manager/config.json`:

```
{
  "wallpaper_dir": "/home/user/wallpapers",
  "interval": 300
}
```

| Parameter | Description | Default value |
| --- | --- | --- |
| `wallpaper_dir` | Directory with wallpapers (including subdirectories) | `~/wallpapers` |
| `interval` | Rotation interval in seconds | `300` (5 minutes) |

Supported formats: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`

---

## File Structure

```
~/.local/bin/
├── wallpaper_daemon.py       # daemon
└── wallpaper_manager.py      # TUI

~/.config/systemd/user/
└── wallpaper-daemon.service  # systemd service

~/.config/wallpaper-manager/
├── config.json               # configuration
├── daemon.sock               # Unix socket (created at runtime)
└── daemon.log                # log file
```

---

## Troubleshooting

**Daemon not running after restart:**

```
loginctl enable-linger $USER
systemctl --user daemon-reload
systemctl --user enable wallpaper-daemon
```

**Wallpaper not changing (Wayland/GNOME):**

```
# Check if gsettings works
gsettings get org.gnome.desktop.background picture-uri
```

**TUI reports "Daemon unavailable":**

```
systemctl --user start wallpaper-daemon
journalctl --user -u wallpaper-daemon -n 20
```