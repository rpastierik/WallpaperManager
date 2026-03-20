# 🖼 Wallpaper Manager

Automatické náhodné striedanie wallpaperov pre **GNOME na Waylande**.

Skladá sa z dvoch častí:
- **`wallpaper_daemon.py`** — beží na pozadí ako systemd user service, rotuje wallpapery
- **`wallpaper_manager.py`** — TUI ovládač v termináli, komunikuje s daemonom cez Unix socket

---

## Požiadavky

- Python 3.10+
- GNOME + Wayland
- `textual` knižnica

```bash
pip install textual --break-system-packages
```

---

## Inštalácia

```bash
# 1. Skopíruj skripty
mkdir -p ~/.local/bin
cp wallpaper_daemon.py ~/.local/bin/
cp wallpaper_manager.py ~/.local/bin/

# 2. Nainštaluj systemd service
mkdir -p ~/.config/systemd/user
cp wallpaper-daemon.service ~/.config/systemd/user/

# 3. Spusti daemon
systemctl --user daemon-reload
systemctl --user enable wallpaper-daemon
systemctl --user start wallpaper-daemon
```

Daemon sa automaticky spustí po každom prihlásení.

---

## Použitie

### TUI ovládač

```bash
python3 ~/.local/bin/wallpaper_manager.py
```

| Klávesa | Akcia |
|---------|-------|
| `N` | Okamžitá zmena wallpaperu |
| `Space` | Pozastaviť / Spustiť rotáciu |
| `R` | Obnoviť stav |
| `Q` | Zavrieť TUI |

### Správa daemona

```bash
# Stav
systemctl --user status wallpaper-daemon

# Zastaviť / Spustiť / Reštartovať
systemctl --user stop wallpaper-daemon
systemctl --user start wallpaper-daemon
systemctl --user restart wallpaper-daemon

# Logy
journalctl --user -u wallpaper-daemon -f
```

---

## Konfigurácia

Konfig sa ukladá automaticky do `~/.config/wallpaper-manager/config.json`:

```json
{
  "wallpaper_dir": "/home/user/wallpapers",
  "interval": 300
}
```

| Parameter | Popis | Predvolená hodnota |
|-----------|-------|-------------------|
| `wallpaper_dir` | Adresár s wallpapermi (vrátane podadresárov) | `~/wallpapers` |
| `interval` | Interval striedania v sekundách | `300` (5 minút) |

Podporované formáty: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`

---

## Štruktúra súborov

```
~/.local/bin/
├── wallpaper_daemon.py       # daemon
└── wallpaper_manager.py      # TUI

~/.config/systemd/user/
└── wallpaper-daemon.service  # systemd service

~/.config/wallpaper-manager/
├── config.json               # konfigurácia
├── daemon.sock               # Unix socket (vytvára sa za behu)
└── daemon.log                # log súbor
```

---

## Riešenie problémov

**Daemon nebeží po reštarte:**
```bash
loginctl enable-linger $USER
systemctl --user daemon-reload
systemctl --user enable wallpaper-daemon
```

**Wallpaper sa nemení (Wayland/GNOME):**
```bash
# Over či gsettings funguje
gsettings get org.gnome.desktop.background picture-uri
```

**TUI hlási "Daemon nedostupný":**
```bash
systemctl --user start wallpaper-daemon
journalctl --user -u wallpaper-daemon -n 20
```
