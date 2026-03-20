#!/usr/bin/env python3
"""
Wallpaper Manager TUI
Communicates with wallpaper-daemon via Unix socket.
"""

import json
import socket
import time
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Button, Label, Input, DirectoryTree
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual import on

SOCKET_PATH = Path.home() / ".config" / "wallpaper-manager" / "daemon.sock"
CONFIG_FILE = Path.home() / ".config" / "wallpaper-manager" / "config.json"


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


def daemon_running() -> bool:
    return SOCKET_PATH.exists() and send_command({"action": "status"}) is not None


def format_interval(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m" if m else f"{h}h"


class DirPickerScreen(ModalScreen):
    CSS = """
    DirPickerScreen { align: center middle; }
    #dir-picker-container {
        width: 70; height: 30;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #dir-picker-title {
        text-align: center; color: $accent;
        text-style: bold; margin-bottom: 1;
    }
    DirectoryTree { height: 20; border: solid $primary-darken-2; }
    #dir-picker-buttons { margin-top: 1; align: center middle; }
    """

    def __init__(self, current_dir: str):
        super().__init__()
        self.current_dir = current_dir
        self.selected_path = current_dir

    def compose(self) -> ComposeResult:
        with Container(id="dir-picker-container"):
            yield Label("📁  Vyber adresár s wallpapermi", id="dir-picker-title")
            yield DirectoryTree(str(Path.home()), id="dir-tree")
            with Horizontal(id="dir-picker-buttons"):
                yield Button("✓ Potvrdiť", variant="success", id="confirm-dir")
                yield Button("✗ Zrušiť", variant="error", id="cancel-dir")

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected):
        self.selected_path = str(event.path)

    @on(Button.Pressed, "#confirm-dir")
    def confirm(self):
        self.dismiss(self.selected_path)

    @on(Button.Pressed, "#cancel-dir")
    def cancel(self):
        self.dismiss(None)


class WallpaperManagerApp(App):
    CSS = """
    Screen { background: #0d1117; }
    Header { background: #161b22; color: #58a6ff; text-style: bold; }
    Footer { background: #161b22; color: #8b949e; }

    #main-layout { width: 100%; height: 100%; padding: 1 2; }

    .card {
        border: solid #30363d;
        background: #161b22;
        padding: 1 2;
        margin-bottom: 1;
        height: auto;
    }
    .card-title {
        color: #58a6ff; text-style: bold; margin-bottom: 1;
    }

    #daemon-warning {
        background: #3d1f00;
        border: solid #d29922;
        color: #d29922;
        padding: 1 2;
        margin-bottom: 1;
        text-align: center;
    }

    #current-wallpaper { color: #e6edf3; }
    #wallpaper-count { color: #8b949e; }
    #timer-display { color: #3fb950; text-style: bold; }
    #status-dot { text-style: bold; }

    #btn-row { height: auto; margin-bottom: 1; }

    Button { margin-right: 1; }
    #btn-next { background: #58a6ff; color: #0d1117; }
    #btn-next:hover { background: #79c0ff; }
    #btn-toggle { background: #3fb950; color: #0d1117; }
    #btn-toggle.paused { background: #d29922; color: #0d1117; }

    .setting-row { height: 3; margin-bottom: 1; align: left middle; }
    .setting-label { width: 22; color: #8b949e; }

    Input {
        width: 30; background: #0d1117;
        border: solid #30363d; color: #e6edf3;
    }
    Input:focus { border: solid #58a6ff; }

    #btn-apply-dir, #btn-apply-interval {
        background: #161b22; border: solid #30363d;
        color: #e6edf3; margin-left: 1;
    }

    #log-card { border: solid #30363d; background: #161b22; padding: 1 2; height: 1fr; }
    #log-content { color: #8b949e; height: 1fr; overflow-y: auto; }
    """

    BINDINGS = [
        ("n", "next_wallpaper", "Ďalší"),
        ("space", "toggle_rotation", "Play/Pause"),
        ("r", "refresh", "Obnoviť"),
        ("q", "quit", "Koniec"),
    ]

    TITLE = "🖼  Wallpaper Manager"

    paused: reactive[bool] = reactive(False)
    connected: reactive[bool] = reactive(False)

    def __init__(self):
        super().__init__()
        self.log_lines: list[str] = []
        self._status_cache: dict = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main-layout"):
            yield Static("⚠  Daemon nebeží. Spusti: systemctl --user start wallpaper-daemon", id="daemon-warning")

            with Container(classes="card"):
                yield Label("◈  Aktuálny stav", classes="card-title")
                yield Label("", id="status-dot")
                yield Label("", id="current-wallpaper")
                yield Label("", id="wallpaper-count")
                yield Label("", id="timer-display")

            with Container(classes="card"):
                yield Label("◈  Ovládanie", classes="card-title")
                with Horizontal(id="btn-row"):
                    yield Button("⏭  Ďalší wallpaper", id="btn-next")
                    yield Button("⏸  Pozastaviť", id="btn-toggle")

            with Container(classes="card"):
                yield Label("◈  Nastavenia", classes="card-title")
                with Horizontal(classes="setting-row"):
                    yield Label("📁 Adresár:", classes="setting-label")
                    yield Input("", id="input-dir")
                    yield Button("Vybrať", id="btn-apply-dir")
                with Horizontal(classes="setting-row"):
                    yield Label("⏱  Interval (sek):", classes="setting-label")
                    yield Input("", id="input-interval")
                    yield Button("Použiť", id="btn-apply-interval")

            with Container(id="log-card"):
                yield Label("◈  Denník", classes="card-title")
                yield Static("", id="log-content")

        yield Footer()

    def on_mount(self):
        self.action_refresh()
        self.set_interval(2.0, self.action_refresh)

    def action_refresh(self):
        status = send_command({"action": "status"})
        if status is None:
            self.connected = False
            self.query_one("#daemon-warning").display = True
            self.query_one("#status-dot", Static).update("🔴  Daemon nie je spustený")
            self.query_one("#timer-display", Static).update("")
            return

        self.connected = True
        self.query_one("#daemon-warning").display = False
        self._status_cache = status
        self.paused = status.get("paused", False)

        dot = self.query_one("#status-dot", Static)
        dot.update("🟢  Daemon beží" + ("  ⏸ pozastavené" if self.paused else ""))

        current = status.get("current", "")
        name = Path(current).name if current else "—"
        self.query_one("#current-wallpaper", Static).update(f"🖼  {name}")

        count = status.get("count", 0)
        d = status.get("dir", "")
        self.query_one("#wallpaper-count", Static).update(f"📂 {d}  ({count} obrázkov)")

        if not self.paused:
            countdown = status.get("countdown", 0)
            interval = status.get("interval", 0)
            self.query_one("#timer-display", Static).update(
                f"⏱  Ďalšia zmena za: {format_interval(countdown)}  /  interval: {format_interval(interval)}"
            )
        else:
            self.query_one("#timer-display", Static).update("⏸  Rotácia pozastavená")

        dir_input = self.query_one("#input-dir", Input)
        if not dir_input.value:
            dir_input.value = status.get("dir", "")

        interval_input = self.query_one("#input-interval", Input)
        if not interval_input.value:
            interval_input.value = str(status.get("interval", 300))

        self._update_toggle_btn()

    def _update_toggle_btn(self):
        btn = self.query_one("#btn-toggle", Button)
        if self.paused:
            btn.label = "▶  Spustiť"
            btn.add_class("paused")
        else:
            btn.label = "⏸  Pozastaviť"
            btn.remove_class("paused")

    def _add_log(self, message: str):
        t = time.strftime("%H:%M:%S")
        self.log_lines.append(f"[{t}] {message}")
        if len(self.log_lines) > 20:
            self.log_lines = self.log_lines[-20:]
        self.query_one("#log-content", Static).update("\n".join(self.log_lines))

    @on(Button.Pressed, "#btn-next")
    def action_next_wallpaper(self):
        res = send_command({"action": "next"})
        if res and res.get("ok"):
            self._add_log("⏭  Manuálna zmena wallpaperu")
            self.set_timer(0.8, self.action_refresh)
        else:
            self._add_log("✗ Daemon nedostupný")

    @on(Button.Pressed, "#btn-toggle")
    def action_toggle_rotation(self):
        res = send_command({"action": "toggle"})
        if res and res.get("ok"):
            paused = res.get("paused", False)
            self._add_log("⏸  Pozastavené" if paused else "▶  Spustené")
            self.action_refresh()
        else:
            self._add_log("✗ Daemon nedostupný")

    @on(Button.Pressed, "#btn-apply-dir")
    def pick_directory(self):
        current = self.query_one("#input-dir", Input).value
        def on_dismiss(result):
            if result:
                self.query_one("#input-dir", Input).value = result
                self._apply_dir(result)
        self.push_screen(DirPickerScreen(current), on_dismiss)

    @on(Button.Pressed, "#btn-apply-interval")
    def apply_interval(self):
        val = self.query_one("#input-interval", Input).value
        try:
            secs = int(val)
            res = send_command({"action": "set_interval", "interval": secs})
            if res and res.get("ok"):
                self._add_log(f"✓ Interval: {format_interval(secs)}")
                self.action_refresh()
            else:
                self._add_log(f"✗ {res.get('error') if res else 'Daemon nedostupný'}")
        except ValueError:
            self._add_log("✗ Neplatná hodnota intervalu")

    @on(Input.Submitted, "#input-dir")
    def apply_dir_from_input(self, event: Input.Submitted):
        self._apply_dir(event.value)

    @on(Input.Submitted, "#input-interval")
    def apply_interval_from_input(self):
        self.apply_interval()

    def _apply_dir(self, path: str):
        res = send_command({"action": "set_dir", "dir": path})
        if res and res.get("ok"):
            self._add_log(f"✓ Adresár: {path}")
            self.action_refresh()
        else:
            self._add_log(f"✗ {res.get('error') if res else 'Daemon nedostupný'}")


if __name__ == "__main__":
    app = WallpaperManagerApp()
    app.run()
