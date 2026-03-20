#!/usr/bin/env python3
"""
Wallpaper Daemon
Runs as a systemd user service, rotates wallpapers and listens for commands via Unix socket.
"""

import json
import os
import random
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path

CONFIG_FILE = Path.home() / ".config" / "wallpaper-manager" / "config.json"
SOCKET_PATH = Path.home() / ".config" / "wallpaper-manager" / "daemon.sock"
LOG_FILE = Path.home() / ".config" / "wallpaper-manager" / "daemon.log"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

DEFAULT_CONFIG = {
    "wallpaper_dir": str(Path.home() / "wallpapers"),
    "interval": 300,
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_wallpapers(directory: str) -> list[str]:
    try:
        return [
            str(p) for p in Path(directory).rglob("*")
            if p.suffix.lower() in IMAGE_EXTENSIONS and p.is_file()
        ]
    except Exception:
        return []


def set_wallpaper(path: str) -> bool:
    try:
        uri = f"file://{path}"
        env = os.environ.copy()
        # needed for gsettings to work from a service
        if "DBUS_SESSION_BUS_ADDRESS" not in env:
            # try to find it
            uid = os.getuid()
            env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
            check=True, capture_output=True, env=env
        )
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
            check=True, capture_output=True, env=env
        )
        return True
    except Exception as e:
        log(f"ERROR set_wallpaper: {e}")
        return False


def get_current_wallpaper() -> str:
    try:
        env = os.environ.copy()
        uid = os.getuid()
        if "DBUS_SESSION_BUS_ADDRESS" not in env:
            env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.background", "picture-uri"],
            capture_output=True, text=True, check=True, env=env
        )
        uri = result.stdout.strip().strip("'\"")
        return uri[7:] if uri.startswith("file://") else uri
    except Exception:
        return ""


def log(message: str):
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{t}] {message}\n"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception:
        pass
    print(line, end="", flush=True)


class WallpaperDaemon:
    def __init__(self):
        self.config = load_config()
        self.running = True
        self.paused = False
        self.countdown = self.config["interval"]
        self.current_wallpaper = get_current_wallpaper()
        self._skip_event = threading.Event()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def pick_and_set(self):
        wallpapers = get_wallpapers(self.config["wallpaper_dir"])
        if not wallpapers:
            log("No wallpapers found")
            return False
        # avoid repeating the same wallpaper
        others = [w for w in wallpapers if w != self.current_wallpaper]
        path = random.choice(others if others else wallpapers)
        if set_wallpaper(path):
            self.current_wallpaper = path
            log(f"SET {Path(path).name}")
            return True
        return False

    def rotation_loop(self):
        log("Rotation loop started")
        while self.running:
            if self.paused:
                time.sleep(1)
                continue

            interval = self.config["interval"]
            self.countdown = interval

            for remaining in range(interval, 0, -1):
                if not self.running:
                    return
                if self.paused:
                    # wait while paused, reset countdown after unpause
                    while self.paused and self.running:
                        time.sleep(1)
                    self.countdown = self.config["interval"]
                    break
                if self._skip_event.is_set():
                    self._skip_event.clear()
                    break
                self.countdown = remaining
                time.sleep(1)
            else:
                self.pick_and_set()
                continue
            # skip was triggered
            self.pick_and_set()

    def handle_command(self, cmd: dict) -> dict:
        action = cmd.get("action")

        if action == "status":
            wallpapers = get_wallpapers(self.config["wallpaper_dir"])
            return {
                "ok": True,
                "paused": self.paused,
                "countdown": self.countdown,
                "current": self.current_wallpaper,
                "dir": self.config["wallpaper_dir"],
                "interval": self.config["interval"],
                "count": len(wallpapers),
            }

        elif action == "next":
            self._skip_event.set()
            return {"ok": True}

        elif action == "pause":
            self.paused = True
            log("Paused")
            return {"ok": True}

        elif action == "resume":
            self.paused = False
            log("Resumed")
            return {"ok": True}

        elif action == "toggle":
            self.paused = not self.paused
            log("Paused" if self.paused else "Resumed")
            return {"ok": True, "paused": self.paused}

        elif action == "set_dir":
            d = cmd.get("dir", "")
            if not Path(d).is_dir():
                return {"ok": False, "error": f"Adresár neexistuje: {d}"}
            with self._lock:
                self.config["wallpaper_dir"] = d
                save_config(self.config)
            log(f"Dir set to {d}")
            return {"ok": True}

        elif action == "set_interval":
            try:
                secs = int(cmd.get("interval", 0))
                if secs < 5:
                    return {"ok": False, "error": "Minimálny interval je 5 sekúnd"}
                with self._lock:
                    self.config["interval"] = secs
                    save_config(self.config)
                self.countdown = secs
                self._skip_event.set()  # reset current timer
                log(f"Interval set to {secs}s")
                return {"ok": True}
            except ValueError:
                return {"ok": False, "error": "Neplatná hodnota"}

        elif action == "stop":
            self.running = False
            return {"ok": True}

        return {"ok": False, "error": f"Unknown action: {action}"}

    def socket_server(self):
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as srv:
            srv.bind(str(SOCKET_PATH))
            srv.listen(5)
            srv.settimeout(1.0)
            log(f"Socket listening at {SOCKET_PATH}")

            while self.running:
                try:
                    conn, _ = srv.accept()
                    threading.Thread(
                        target=self._handle_conn, args=(conn,), daemon=True
                    ).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        log(f"Socket error: {e}")

        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

    def _handle_conn(self, conn):
        with conn:
            try:
                data = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if data.endswith(b"\n"):
                        break
                cmd = json.loads(data.decode())
                result = self.handle_command(cmd)
                conn.sendall(json.dumps(result).encode() + b"\n")
            except Exception as e:
                log(f"Connection error: {e}")

    def run(self):
        log("Wallpaper daemon starting")
        self.pick_and_set()

        rotation_thread = threading.Thread(target=self.rotation_loop, daemon=True)
        rotation_thread.start()

        def handle_signal(sig, frame):
            log("Shutting down...")
            self.running = False

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        self.socket_server()
        rotation_thread.join(timeout=3)
        log("Daemon stopped")


if __name__ == "__main__":
    daemon = WallpaperDaemon()
    daemon.run()
