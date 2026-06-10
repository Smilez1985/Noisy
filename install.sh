#!/bin/bash
# ==========================================================
# Noisy Installer v5.1 (Orchestrator + Community Edition)
# Ausfuehren als root: sudo bash install.sh
#
# Voraussetzungen:
#   - Raspberry Pi Zero 2 WH (oder Pi 3/4/5)
#   - DietPi oder Raspberry Pi OS (Bookworm/Trixie)
#   - GamePi13 3D Acce Kit (ST7789 Display, GPIO Buttons)
#   - USB-Mikrofon
#   - SPI aktiviert (dietpi-config oder raspi-config)
#   - User 'noisy' existiert (adduser noisy)
#
# Was wird installiert:
#   - Python-Abhaengigkeiten (sherpa-onnx, pyaudio, st7789, lgpio, etc.)
#   - KI-Modell (Zipformer-small Audio Tagging, ~30MB)
#   - ALSA-Konfiguration (USB-Mic als Default)
#   - systemd Service (noisy.service, Auto-Start)
#   - CLI-Tool (noisy <befehl>)
#   - Berechtigungen (GPIO, SPI, Audio, CPU Freq)
# ==========================================================
set -e

APP_DIR="/home/noisy/noisy-app"
MOODS_DIR="$APP_DIR/moods"
MODELS_DIR="/home/noisy/models"
MODEL_SUBDIR="sherpa-onnx-zipformer-small-audio-tagging-2024-04-15"
MODEL_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/audio-tagging-models/${MODEL_SUBDIR}.tar.bz2"

echo "=== Noisy Installer v5.1 (Orchestrator) ==="
echo ""

# Pruefen ob als root ausgefuehrt
if [ "$(id -u)" -ne 0 ]; then
    echo "FEHLER: Bitte als root ausfuehren: sudo bash install.sh"
    exit 1
fi

# Pruefen ob User 'noisy' existiert
if ! id -u noisy &>/dev/null; then
    echo "User 'noisy' existiert nicht. Erstelle..."
    adduser --disabled-password --gecos "Noisy" noisy
    echo "  User 'noisy' erstellt."
fi

# 1. User + Gruppen
echo "[1/10] Berechtigungen..."
usermod -a -G spi,gpio,audio,video,i2c,input,bluetooth noisy 2>/dev/null || true
mkdir -p "$APP_DIR" "$MOODS_DIR" "$MODELS_DIR"
chown -R noisy:noisy /home/noisy/

# 2. System-Abhaengigkeiten (fuer pyaudio + lgpio)
echo "[2/10] System-Pakete..."
apt-get update -qq
apt-get install -y -qq python3-pip python3-dev portaudio19-dev \
    libasound2-dev libsndfile1-dev wget tar bzip2 bluez 2>/dev/null || true

# 3. Python Dependencies (lgpio statt gpiozero!)
echo "[3/10] Python Pakete..."
pip install --break-system-packages -q \
    sherpa-onnx pyaudio st7789 spidev Pillow numpy lgpio 2>/dev/null || \
pip install sherpa-onnx pyaudio st7789 spidev Pillow numpy lgpio

# 4. ALSA/JACK Warnungen unterdruecken
echo "[4/10] Audio-Konfiguration..."
ALSA_CONF="/etc/asound.conf"
if [ ! -f "$ALSA_CONF" ] || ! grep -q "pcm.!default" "$ALSA_CONF" 2>/dev/null; then
    cat > "$ALSA_CONF" << 'ASOUND'
# Noisy: USB-Mic als Default, JACK-Warnungen unterdruecken
pcm.!default {
    type hw
    card 0
}
ctl.!default {
    type hw
    card 0
}
ASOUND
    echo "  ALSA Default auf USB-Mic gesetzt"
else
    echo "  ALSA Config bereits vorhanden"
fi

# 5. Modell Download
if [ ! -f "$MODELS_DIR/$MODEL_SUBDIR/model.int8.onnx" ]; then
    echo "[5/10] Lade KI-Modell herunter (~30MB)..."
    cd "$MODELS_DIR"
    wget -q --show-progress "$MODEL_URL"
    tar xf "${MODEL_SUBDIR}.tar.bz2"
    rm -f "${MODEL_SUBDIR}.tar.bz2"
    chown -R noisy:noisy "$MODELS_DIR"
else
    echo "[5/10] Modell bereits vorhanden, ueberspringe..."
fi

# 6. Personality anlegen (nur beim allerersten Mal)
if [ ! -f "$APP_DIR/personality.json" ]; then
    echo "[6/10] Personality initialisieren..."
    python3 -c "
import json, time
data = {
    'birth_time': time.time(),
    'total_interactions': 0,
    'energy': 0.5, 'cheerful': 0.5, 'shy': 0.5, 'affection': 0.5,
    'mood_history': {},
    'last_save': time.time()
}
with open('$APP_DIR/personality.json', 'w') as f:
    json.dump(data, f, indent=2)
print('  Noisy geschluepft! birth_time gesetzt.')
"
    chown noisy:noisy "$APP_DIR/personality.json"
else
    echo "[6/10] Personality vorhanden, ueberspringe..."
fi

# 7. Raumkalibrierung
if [ ! -f "$APP_DIR/calibration.json" ]; then
    echo ""
    echo "[7/10] Raumkalibrierung"
    echo "  Noisy muss den Grundgeraeuschpegel deines Raumes messen."
    echo "  15 Sekunden Stille - kein Reden, keine Musik."
    echo ""
    cd "$APP_DIR"
    sudo -u noisy python3 "$APP_DIR/noisy_calibrate.py" 2>/dev/null || \
        echo "  WARNUNG: Kalibrierung fehlgeschlagen. Spaeter mit: noisy calibrate"
    echo ""
else
    echo "[7/10] Kalibrierung vorhanden, ueberspringe..."
    echo "  (Neu kalibrieren: noisy calibrate)"
fi

# 8. Alte Services + Aliases komplett bereinigen
echo "[8/10] Alte Reste bereinigen..."
systemctl stop noisy.service 2>/dev/null || true
systemctl stop noisy-face.service 2>/dev/null || true
systemctl stop noisy-audio.service 2>/dev/null || true
systemctl disable noisy-face.service 2>/dev/null || true
systemctl disable noisy-audio.service 2>/dev/null || true
rm -f /etc/systemd/system/noisy-face.service
rm -f /etc/systemd/system/noisy-audio.service
rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio
# Alte v4.0 Dateien
rm -f "$APP_DIR/noisy_moods.py"
rm -f "$APP_DIR/audio.log" "$APP_DIR/audio.log."*
# Alte Aliases komplett entfernen (wir nutzen jetzt noisy_cli.sh)
ALIAS_FILE="/home/noisy/.bash_aliases"
if [ -f "$ALIAS_FILE" ]; then
    sed -i '/noisy-/d' "$ALIAS_FILE" 2>/dev/null || true
    # Leere Datei loeschen
    [ ! -s "$ALIAS_FILE" ] && rm -f "$ALIAS_FILE"
fi
echo "  Bereinigt."

# 9. Systemd Service (EIN Service fuer alles)
echo "[9/10] Erstelle Noisy Service..."
cat > /etc/systemd/system/noisy.service << 'EOF'
[Unit]
Description=Noisy Orchestrator v5.1
After=network.target sound.target bluetooth.target

[Service]
Type=simple
ExecStartPre=+/bin/chmod 666 /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq
ExecStart=/usr/bin/python3 /home/noisy/noisy-app/noisy_orchestrator.py
WorkingDirectory=/home/noisy/noisy-app
Restart=always
RestartSec=5
User=noisy
Environment=PYTHONUNBUFFERED=1

# SHM aufraeumen bei Stop
ExecStopPost=/bin/rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio

[Install]
WantedBy=multi-user.target
EOF

# 10. CLI-Script, Sudoers, CPU Freq Berechtigungen
echo "[10/10] CLI + Berechtigungen..."

# CLI-Script ausfuehrbar machen und verlinken
if [ -f "$APP_DIR/noisy_cli.sh" ]; then
    chmod +x "$APP_DIR/noisy_cli.sh"
    ln -sf "$APP_DIR/noisy_cli.sh" /usr/local/bin/noisy
fi

# Sudoers fuer den noisy-User
cat > /etc/sudoers.d/noisy << 'SUDOERS'
noisy ALL=(ALL) NOPASSWD: /usr/bin/systemctl start noisy.service
noisy ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop noisy.service
noisy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart noisy.service
noisy ALL=(ALL) NOPASSWD: /usr/bin/systemctl status noisy.service
noisy ALL=(ALL) NOPASSWD: /usr/bin/rm -f /dev/shm/noisy_mood
noisy ALL=(ALL) NOPASSWD: /usr/bin/rm -f /dev/shm/noisy_audio
noisy ALL=(ALL) NOPASSWD: /usr/bin/rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio
noisy ALL=(ALL) NOPASSWD: /usr/bin/btmgmt power on
noisy ALL=(ALL) NOPASSWD: /usr/bin/btmgmt power off
noisy ALL=(ALL) NOPASSWD: /usr/bin/btmgmt add-adv *
noisy ALL=(ALL) NOPASSWD: /usr/bin/btmgmt rm-adv *
noisy ALL=(ALL) NOPASSWD: /usr/sbin/btmgmt power on
noisy ALL=(ALL) NOPASSWD: /usr/sbin/btmgmt power off
noisy ALL=(ALL) NOPASSWD: /usr/sbin/btmgmt add-adv *
noisy ALL=(ALL) NOPASSWD: /usr/sbin/btmgmt rm-adv *
SUDOERS
chmod 440 /etc/sudoers.d/noisy

# CPU Frequency Capping: noisy-User darf scaling_max_freq schreiben
# udev-Regel erstellt permanente Berechtigung
CPUFREQ_RULE="/etc/udev/rules.d/99-noisy-cpufreq.rules"
cat > "$CPUFREQ_RULE" << 'UDEV'
# Noisy: CPU Frequency Capping (Stromsparen bei Idle)
KERNEL=="cpu0", SUBSYSTEM=="cpu", ACTION=="add", \
  RUN+="/bin/chmod 666 /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq"
UDEV
# Sofort anwenden (ohne Reboot)
chmod 666 /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null || true

# Alle Python-Scripts ausfuehrbar
chmod +x "$APP_DIR"/*.py 2>/dev/null || true

# config.txt Hinweis pruefen
echo ""
echo "WICHTIG: Folgende Zeilen muessen in /boot/config.txt stehen:"
echo "  dtoverlay=lcd1inch3_ST7789"
echo "  gpio=25=op,dh"
echo "  hdmi_force_hotplug=1"
echo "(Siehe GamePi13 setup.txt fuer Details)"
echo ""

# Aktivieren + Starten
systemctl daemon-reload
systemctl enable noisy.service
rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio
systemctl restart noisy.service

sleep 2

echo ""
echo "=== Noisy v5.1 installiert! ==="
echo ""
echo "Architektur:"
echo "  noisy_orchestrator.py  - Masterprozess"
echo "    -> noisy_audio.py    - Audio (Subprocess, eigene Log-Datei)"
echo "    -> noisy_render.py   - Renderer (Thread, Health-Check)"
echo "    -> noisy_input.py    - GPIO Buttons (lgpio Polling)"
echo "  moods/                 - 35 Moods in 5 Gruppen"
echo ""
echo "Features:"
echo "  - Moflin A.E.I. Personality (Energie, Frohsinn, Scheu, Zuneigung)"
echo "  - Tageszeit-Bewusstsein (Morgen/Abend/Nacht-Verhalten)"
echo "  - Thermal-Personality (CPU-Temperatur beeinflusst Verhalten)"
echo "  - CPU Frequency Capping (600MHz idle, 1GHz aktiv)"
echo "  - Night Gestures (genervtes Aufwachen nachts)"
echo "  - Renderer Health-Check (Auto-Restart bei Absturz)"
echo "  - Privacy-First Logging (RAM bei Normal, SD bei Debug)"
echo ""
echo "Alle Befehle ueber: noisy <befehl>"
echo ""
echo "  noisy restart      Neustart"
echo "  noisy stop         Stoppen"
echo "  noisy start        Starten"
echo "  noisy status       Status anzeigen"
echo "  noisy log          Log live verfolgen"
echo "  noisy personality  AEI-Werte anzeigen"
echo "  noisy moods        Alle Moods anzeigen"
echo "  noisy calibrate    Raum neu kalibrieren"
echo "  noisy debug-on     Debug AN (Log auf SD)"
echo "  noisy debug-off    Debug AUS (Log in /tmp)"
echo "  noisy uninstall    Deinstallieren"
echo "  noisy version      Version"
echo ""

# Status pruefen
if systemctl is-active --quiet noisy.service; then
    echo "Status: Noisy laeuft!"
else
    echo "WARNUNG: Noisy laeuft NICHT. Pruefen mit:"
    echo "  noisy log"
    echo "  journalctl -u noisy.service -n 50"
fi
echo ""
