#!/bin/bash

# ==========================================================
# Noisy Installer v0.8 (Production Ready)
# Ausfuehren als root: sudo bash install.sh
# ==========================================================
set -e

GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}--- Noisy v0.8 Professional Installer ---${NC}"

# 0. Vorbereitungen
if [ "$(id -u)" -ne 0 ]; then
    echo "FEHLER: Bitte als root ausfuehren: sudo bash install.sh"
    exit 1
fi

# Projekt-Pfade (Dynamisch basierend auf Standort des Scripts)
PROJECT_PATH=$(realpath $(dirname "$(readlink -f "$BASH_SOURCE")"))
MODELS_DIR="/home/noisy/models"

# Sicherstellen, dass User 'noisy' existiert
if ! id -u noisy &>/dev/null; then
    echo "User 'noisy' wird erstellt..."
    adduser --disabled-password --gecos "Noisy" noisy
fi

# 1. System-Abhaengigkeiten (Audio, Display, Models)
echo "[1/9] Installiere System-Pakete..."
apt update -qq
apt install -y -qq python3-pip python3-dev portaudio19-dev \
    libasound2-dev libsndfile1-dev wget tar bzip2 ffmpeg curl git

# 2. Python Bibliotheken
echo "[2/9] Installiere Python Pakete..."
python3 -m pip install --upgrade pip
# Wir nutzen 'lgpio' für die Buttons und st7789 für das Display
python3 -m pip install numpy pyaudio st7789 Pillow lgpio spidev

# 3. Verzeichnisse & Berechtigungen
echo "[3/9] Konfiguriere Verzeichnisse..."
mkdir -p "$MODELS_DIR" /var/log/noisy/dev_logs
chown -R noisy:noisy /home/noisy/
chown -R noisy:noisy /var/log/noisy

# 4. ALSA-Konfiguration (USB-Mikrofon als Default setzen)
echo "[4/9] Konfiguriere Audio-Schnittstellen..."
ALSA_CONF="/etc/asound.conf"
if [ ! -f "$ALSA_CONF" ] || ! grep -q "pcm.!default" "$ALSA_CONF" 2>/dev/null; then
    cat > "$ALSA_CONF" << 'ASOUND'
pcm.!default {
    type hw
    card 0
}
ctl.!default {
    type hw
    card 0
}
ASOUND
    echo "  ALSA Default auf Card 0 (USB-Mic) gesetzt."
fi

# 5. Modell-Downloads (Die echten URLs aus v5.1 übernommen)
echo "[5/9] Prüfe KI-Modelle..."
MODEL_SUBDIR="sherpa-onnx-zipformer-small-audio-tagging-2024-04-15"
# Tagging Modell
if [ ! -f "$MODELS_DIR/$MODEL_SUBDIR/model.int8.onnx" ]; then
    echo "  Lade Audio Tagging Modell herunter..."
    cd "$MODELS_DIR"
    wget -q --show-progress "https://github.com/k2-fsa/sherpa-onnx/releases/download/audio-tagging-models/${MODEL_SUBDIR}.tar.bz2"
    tar xf "${MODEL_SUBDIR}.tar.bz2"
    rm -f "${MODEL_SUBDIR}.tar.bz2"
else
    echo "  Modell bereits vorhanden."
fi

# 6. Sudoers & Berechtigungen (Für CPU Freq und Systemd ohne Passwort)
echo "[6/9] Konfiguriere Sicherheits-Berechtigungen..."
cat > /etc/sudoers.d/noisy << 'SUDOERS'
noisy ALL=(ALL) NOPASSWD: /usr/bin/systemctl start noisy.service
noisy ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop noisy.service
noisy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart noisy.service
noisy ALL=(ALL) NOPASSWD: /usr/bin/systemctl status noisy.service
noisy ALL=(ALL) NOPASSWD: /usr/bin/rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio
noisy ALL=(ALL) NOPASSWD: /usr/bin/btmgmt power on
noisy ALL=(ALL) NOPASSWD: /usr/bin/btmgmt power off
SUDOERS
chmod 440 /etc/sudoers.d/noisy

# CPU Frequenz Regel (udev)
CPUFREQ_RULE="/etc/udev/rules.d/99-noisy-cpufreq.rules"
cat > "$CPUFREQ_RULE" << 'UDEV'
KERNEL=="cpu0", SUBSYSTEM=="cpu", ACTION=="add", \
  RUN+="/bin/chmod 666 /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq"
UDEV
# Sofort anwenden
chmod 666 /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null || true

# 7. Alte Reste bereinigen
echo "[7/9] Bereinige alte Konfigurationen..."
systemctl stop noisy.service 2>/dev/null || true
rm -f /etc/systemd/system/noisy-face.service
rm -f /etc/systemd/system/noisy-audio.service

# 8. Systemd Service erstellen (V0.8 Orchestrator)
echo "[8/9] Erstelle Noisy Service..."
cat > /etc/systemd/system/noisy.service << EOF
[Unit]
Description=Noisy Mochi AI Display
After=network.target sound.target

[Service]
ExecStartPre=+/bin/chmod 666 /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq
ExecStart=/usr/bin/python3 $PROJECT_PATH/launch_noisy.py
WorkingDirectory=$PROJECT_PATH
StandardOutput=inherit
StandardError=inherit
Restart=always
RestartSec=5
User=noisy
Environment=PYTHONUNBUFFERED=1

# SHM aufräumen bei Stop
ExecStopPost=/bin/rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio

[Install]
WantedBy=multi-user.target
EOF

# 9. Finalisierung
echo "[9/9] Aktiviere Service..."
systemctl daemon-reload
systemctl enable noisy
systemctl restart noisy

echo -e "${GREEN}=== Installation abgeschlossen! ===${NC}"
echo "Noisy läuft jetzt im Hintergrund."
echo "Status abfragen: systemctl status noisy"
