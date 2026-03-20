# Changelog

All notable changes are recorded in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.0] - 2026-03-20

### Added

* `wallpaper_tray.py` — system tray app for GNOME using `AyatanaAppIndicator3` + `Gtk`
* Tray icon changes color based on daemon state (running / paused / offline)
* Tray menu shows: current wallpaper name, image count, countdown to next change
* Quick controls from tray: next wallpaper, pause/resume rotation
* Settings dialog in tray app for changing wallpaper directory and rotation interval
* `wallpaper-tray.desktop` — autostart entry for the tray app
* Installation instructions for `gir1.2-ayatanaappindicator3-0.1` and the AppIndicator GNOME extension

---

## [1.1.0] - 2026-03-20

### Changed

* Architecture split into daemon + TUI controller
* Daemon runs as a systemd user service independently of the TUI
* TUI communicates with the daemon via Unix socket (`daemon.sock`)
* Wallpaper rotation survives closing the terminal and system restarts

### Added

* `wallpaper_daemon.py` — standalone daemon process
* `wallpaper-daemon.service` — systemd user service unit
* Socket server in the daemon for commands: `status`, `next`, `toggle`, `pause`, `resume`, `set_dir`, `set_interval`, `stop`
* Automatic `DBUS_SESSION_BUS_ADDRESS` configuration for correct `gsettings` operation from the service
* Daemon logging to `~/.config/wallpaper-manager/daemon.log`
* Daemon status indicator in TUI (🟢 / 🔴)
* Warning in TUI if the daemon is not running

### Fixed

* Wallpaper no longer repeats twice in a row (if another one is available)

---

## [1.0.0] - 2026-03-20

### Added

* Initial release
* TUI interface using the `textual` library
* Random wallpaper rotation from a directory and all subdirectories
* Configurable rotation interval
* Graphical file picker for directory selection (DirectoryTree)
* Button for immediate wallpaper change
* Pause / resume rotation
* Log of recent changes with timestamps
* Supported formats: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`
* Configuration saved to `~/.config/wallpaper-manager/config.json`
* Keyboard shortcuts: `N` (next), `Space` (pause), `Q` (quit)
* Compatibility with GNOME + Wayland via `gsettings`