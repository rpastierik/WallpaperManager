# Changelog

Všetky dôležité zmeny sú zaznamenané v tomto súbore.
Formát vychádza z [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.1.0] - 2026-03-20

### Zmenené
- Architektúra rozdelená na daemon + TUI ovládač
- Daemon beží ako systemd user service nezávisle od TUI
- TUI komunikuje s daemonom cez Unix socket (`daemon.sock`)
- Rotácia wallpaperov prežije zatvorenie terminálu aj reštart systému

### Pridané
- `wallpaper_daemon.py` — samostatný daemon proces
- `wallpaper-daemon.service` — systemd user service jednotka
- Socket server v daemone pre príkazy: `status`, `next`, `toggle`, `pause`, `resume`, `set_dir`, `set_interval`, `stop`
- Automatické nastavenie `DBUS_SESSION_BUS_ADDRESS` pre správne fungovanie `gsettings` zo service
- Logovanie daemona do `~/.config/wallpaper-manager/daemon.log`
- Indikátor stavu daemona v TUI (🟢 / 🔴)
- Varovanie v TUI ak daemon nebeží

### Opravené
- Wallpaper sa neopakuje dvakrát za sebou (ak je dostupný iný)

---

## [1.0.0] - 2026-03-20

### Pridané
- Prvé vydanie
- TUI rozhranie pomocou knižnice `textual`
- Náhodné striedanie wallpaperov z adresára a všetkých podadresárov
- Nastaviteľný interval striedania
- Grafický file picker pre výber adresára (DirectoryTree)
- Tlačidlo na okamžitú zmenu wallpaperu
- Pauza / spustenie rotácie
- Denník posledných zmien s časovými pečiatkami
- Podpora formátov: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`
- Konfigurácia ukladaná do `~/.config/wallpaper-manager/config.json`
- Klávesové skratky: `N` (ďalší), `Space` (pauza), `Q` (koniec)
- Kompatibilita s GNOME + Wayland cez `gsettings`
