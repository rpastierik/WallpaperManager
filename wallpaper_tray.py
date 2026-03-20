#!/usr/bin/env python3
"""
Wallpaper Manager — System Tray App
Requires:
    sudo apt install gir1.2-ayatanaappindicator3-0.1 gnome-shell-extension-appindicator
    gnome-extensions enable ubuntu-appindicators@ubuntu.com

Communicates with wallpaper-daemon via Unix socket.
"""

import json
import socket
import sys
import threading
import time
from pathlib import Path

import gi
gi.require_version("AyatanaAppIndicator3", "0.1")
gi.require_version("Gtk", "3.0")
from gi.repository import AyatanaAppIndicator3 as AppIndicator
from gi.repository import Gtk, GLib

SOCKET_PATH = Path.home() / ".config" / "wallpaper-manager" / "daemon.sock"

# ── Socket communication ──────────────────────────────────────────────────────

def send_command(cmd: dict) -> dict | None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(3.0)
            s.connect(str(SOCKET_PATH))
            s.sendall(json.dumps(cmd).encode() + b"\n")
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
                if data.endswith(b"\n"):
                    break
            return json.loads(data.decode())
    except Exception:
        return None


def format_interval(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m" if m else f"{h}h"


# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent, current_dir: str, current_interval: int):
        super().__init__(title="Settings", transient_for=parent, modal=True)
        self.set_default_size(420, 180)
        self.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL,
            "Apply",  Gtk.ResponseType.OK,
        )
        self.set_default_response(Gtk.ResponseType.OK)

        box = self.get_content_area()
        box.set_spacing(8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # Directory row
        box.add(Gtk.Label(label="Wallpaper directory:", xalign=0))
        dir_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.dir_entry = Gtk.Entry()
        self.dir_entry.set_text(current_dir)
        self.dir_entry.set_hexpand(True)
        browse_btn = Gtk.Button(label="Browse…")
        browse_btn.connect("clicked", self._on_browse)
        dir_row.pack_start(self.dir_entry, True, True, 0)
        dir_row.pack_start(browse_btn, False, False, 0)
        box.add(dir_row)

        # Interval row
        box.add(Gtk.Label(label="Rotation interval (seconds):", xalign=0))
        self.interval_spin = Gtk.SpinButton()
        self.interval_spin.set_adjustment(
            Gtk.Adjustment(value=current_interval, lower=5, upper=86400, step_increment=10)
        )
        self.interval_spin.set_value(current_interval)
        box.add(self.interval_spin)

        box.show_all()

    def _on_browse(self, _btn):
        chooser = Gtk.FileChooserDialog(
            title="Select wallpaper directory",
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        chooser.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL,
            "Select", Gtk.ResponseType.OK,
        )
        if chooser.run() == Gtk.ResponseType.OK:
            self.dir_entry.set_text(chooser.get_filename())
        chooser.destroy()

    def get_values(self):
        return self.dir_entry.get_text().strip(), int(self.interval_spin.get_value())


# ── Tray application ──────────────────────────────────────────────────────────

class TrayApp:
    def __init__(self):
        self._status: dict = {}
        self._paused = False
        self._connected = False

        # AppIndicator setup
        self.indicator = AppIndicator.Indicator.new(
            "wallpaper-manager",
            "preferences-desktop-wallpaper",   # fallback icon name from system theme
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Wallpaper Manager")

        self._build_menu()

        # Poll daemon every 2 seconds via GLib main loop
        GLib.timeout_add_seconds(2, self._poll)
        self._poll()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        self.menu = Gtk.Menu()

        # Status items (non-clickable)
        self.item_status = Gtk.MenuItem(label="⏳ Connecting…")
        self.item_status.set_sensitive(False)
        self.menu.append(self.item_status)

        self.item_wallpaper = Gtk.MenuItem(label="")
        self.item_wallpaper.set_sensitive(False)
        self.menu.append(self.item_wallpaper)

        self.item_timer = Gtk.MenuItem(label="")
        self.item_timer.set_sensitive(False)
        self.menu.append(self.item_timer)

        self.menu.append(Gtk.SeparatorMenuItem())

        # Controls
        self.item_next = Gtk.MenuItem(label="⏭  Next wallpaper")
        self.item_next.connect("activate", lambda _: self._cmd_next())
        self.menu.append(self.item_next)

        self.item_toggle = Gtk.MenuItem(label="⏸  Pause rotation")
        self.item_toggle.connect("activate", lambda _: self._cmd_toggle())
        self.menu.append(self.item_toggle)

        self.menu.append(Gtk.SeparatorMenuItem())

        # Settings
        item_settings = Gtk.MenuItem(label="⚙  Settings…")
        item_settings.connect("activate", lambda _: self._open_settings())
        self.menu.append(item_settings)

        self.menu.append(Gtk.SeparatorMenuItem())

        # Quit
        item_quit = Gtk.MenuItem(label="✕  Quit")
        item_quit.connect("activate", lambda _: Gtk.main_quit())
        self.menu.append(item_quit)

        self.menu.show_all()
        self.indicator.set_menu(self.menu)

    # ── Polling ───────────────────────────────────────────────────────────────

    def _poll(self) -> bool:
        """Called by GLib timer — runs in main thread, safe to update UI."""
        status = send_command({"action": "status"})
        if status is None:
            self._connected = False
            GLib.idle_add(self._update_ui_disconnected)
        else:
            self._connected = True
            self._status = status
            GLib.idle_add(self._update_ui_connected)
        return True  # keep timer running

    def _force_poll(self):
        GLib.timeout_add(700, self._poll)

    # ── UI updates ────────────────────────────────────────────────────────────

    def _update_ui_disconnected(self):
        self.indicator.set_icon_full("dialog-error", "Daemon offline")
        self.item_status.set_label("🔴  Daemon is not running")
        self.item_wallpaper.set_label("")
        self.item_timer.set_label("")
        self.item_next.set_sensitive(False)
        self.item_toggle.set_sensitive(False)

    def _update_ui_connected(self):
        s = self._status
        paused = s.get("paused", False)

        icon = "media-playback-pause" if paused else "preferences-desktop-wallpaper"
        self.indicator.set_icon_full(icon, "Wallpaper Manager")

        state = "⏸ paused" if paused else "running"
        self.item_status.set_label(f"🟢  Daemon {state}")

        name = Path(s.get("current", "")).name or "—"
        count = s.get("count", 0)
        self.item_wallpaper.set_label(f"🖼  {name}  ({count} images)")

        if paused:
            self.item_timer.set_label("⏸  Rotation paused")
            self.item_toggle.set_label("▶  Resume rotation")
        else:
            countdown = s.get("countdown", 0)
            interval = s.get("interval", 0)
            self.item_timer.set_label(
                f"⏱  Next in {format_interval(countdown)}  /  {format_interval(interval)}"
            )
            self.item_toggle.set_label("⏸  Pause rotation")

        self.item_next.set_sensitive(True)
        self.item_toggle.set_sensitive(True)

    # ── Commands ──────────────────────────────────────────────────────────────

    def _cmd_next(self):
        threading.Thread(target=lambda: send_command({"action": "next"}), daemon=True).start()
        self._force_poll()

    def _cmd_toggle(self):
        threading.Thread(target=lambda: send_command({"action": "toggle"}), daemon=True).start()
        self._force_poll()

    def _open_settings(self):
        current_dir = self._status.get("dir", str(Path.home() / "wallpapers"))
        current_interval = self._status.get("interval", 300)

        dlg = SettingsDialog(None, current_dir, current_interval)
        response = dlg.run()

        if response == Gtk.ResponseType.OK:
            new_dir, new_interval = dlg.get_values()
            errors = []

            if new_dir != current_dir:
                res = send_command({"action": "set_dir", "dir": new_dir})
                if not res or not res.get("ok"):
                    errors.append(f"Directory: {res.get('error') if res else 'Daemon unavailable'}")

            if new_interval != current_interval:
                res = send_command({"action": "set_interval", "interval": new_interval})
                if not res or not res.get("ok"):
                    errors.append(f"Interval: {res.get('error') if res else 'Daemon unavailable'}")

            if errors:
                err_dlg = Gtk.MessageDialog(
                    transient_for=None,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Settings error",
                )
                err_dlg.format_secondary_text("\n".join(errors))
                err_dlg.run()
                err_dlg.destroy()

            self._force_poll()

        dlg.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = TrayApp()
    Gtk.main()
