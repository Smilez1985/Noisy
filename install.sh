#!/bin/bash

# ==========================================================
# Noisy Installer (Orchestrator Edition)
# Version wird zur Laufzeit aus manifest.json gelesen.
# Ausfuehren als root aus dem Git-Checkout heraus:
#     sudo bash install.sh
#
# Deployt den Orchestrator-Stack (noisy_orchestrator.py + moods/ + Module)
# nach /home/noisy/noisy-app und richtet den systemd-Service ein.
# ==========================================================
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ----------------------------------------------------------
# 0. Root-Check
# ----------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}FEHLER: Bitte als root ausfuehren: sudo bash install.sh${NC}"
    exit 1
fi

# ----------------------------------------------------------
# 1. Pfade
# ----------------------------------------------------------
SOURCE_DIR=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)
DEPLOY_DIR="/home/noisy/noisy-app"
MODELS_DIR="/home/noisy/models"
MODEL_SUBDIR="sherpa-onnx-zipformer-small-audio-tagging-2024-04-15"

# Version aus dem Manifest lesen (Single Source of Truth).
# Bewusst ohne jq, da jq erst weiter unten installiert wird.
VERSION=$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
    "$SOURCE_DIR/manifest.json" 2>/dev/null | head -n1)
if [ -z "$VERSION" ]; then
    VERSION="unbekannt"
fi

echo -e "${GREEN}--- Noisy v$VERSION Orchestrator Installer ---${NC}"
echo "  Quelle:  $SOURCE_DIR"
echo "  Ziel:    $DEPLOY_DIR"

# ----------------------------------------------------------
# 2. User 'noisy' + Gruppen
# ----------------------------------------------------------
echo "[1/11] Pruefe User 'noisy'..."
if ! id -u noisy &>/dev/null; then
    echo "  User 'noisy' wird erstellt..."
    adduser --disabled-password --gecos "Noisy" noisy
fi

# Relevante Gruppen zuweisen (nur wenn vorhanden)
for grp in audio spi gpio i2c bluetooth; do
    if getent group "$grp" >/dev/null 2>&1; then
        usermod -aG "$grp" noisy
    fi
done

# ----------------------------------------------------------
# 3. System-Pakete
# ----------------------------------------------------------
echo "[2/11] Installiere System-Pakete..."
apt update -qq
apt install -y -qq \
    python3-pip python3-dev \
    portaudio19-dev libasound2-dev libsndfile1-dev \
    wget tar bzip2 ffmpeg curl git jq bluez rsync

# ----------------------------------------------------------
# 4. Python-Pakete
# ----------------------------------------------------------
echo "[3/11] Installiere Python-Pakete..."

# Erkennen ob pip --break-system-packages braucht (Bookworm/DietPi)
PIP_FLAGS=""
if python3 -m pip install --help 2>/dev/null | grep -q "break-system-packages"; then
    PIP_FLAGS="--break-system-packages"
fi

python3 -m pip install --upgrade $PIP_FLAGS pip
python3 -m pip install $PIP_FLAGS \
    numpy pyaudio sherpa-onnx st7789 Pillow lgpio spidev flask

# ----------------------------------------------------------
# 5. Deploy: v5-Artefakte nach DEPLOY_DIR kopieren
# ----------------------------------------------------------
echo "[4/11] Deploye Anwendung nach $DEPLOY_DIR..."
mkdir -p "$DEPLOY_DIR"

# Whitelist der zu deployenden Dateien (deterministisch)
V5_FILES=(
    "noisy_orchestrator.py"
    "noisy_audio.py"
    "noisy_render.py"
    "noisy_personality.py"
    "noisy_input.py"
    "noisy_beacon.py"
    "noisy_config.py"
    "noisy_calibrate.py"
    "noisy_debug.py"
    "noisy_runtime.py"
    "web_ui.py"
    "noisy_cli.sh"
    "uninstall.sh"
    "manifest.json"
)

MISSING=0
for f in "${V5_FILES[@]}"; do
    if [ -f "$SOURCE_DIR/$f" ]; then
        cp "$SOURCE_DIR/$f" "$DEPLOY_DIR/$f"
    else
        echo -e "  ${RED}FEHLT:${NC} $f"
        MISSING=1
    fi
done

# moods/ Paket (zwingend erforderlich)
if [ -d "$SOURCE_DIR/moods" ]; then
    rm -rf "$DEPLOY_DIR/moods"
    cp -r "$SOURCE_DIR/moods" "$DEPLOY_DIR/moods"
else
    echo -e "  ${RED}FEHLT: moods/ Verzeichnis${NC}"
    MISSING=1
fi

# Doku (optional)
for f in "README.md" "CHANGELOG.md"; do
    [ -f "$SOURCE_DIR/$f" ] && cp "$SOURCE_DIR/$f" "$DEPLOY_DIR/$f"
done

if [ "$MISSING" -ne 0 ]; then
    echo -e "${RED}FEHLER: Kritische Dateien fehlen. Installation abgebrochen.${NC}"
    exit 1
fi

# Ausfuehrbar machen
chmod +x "$DEPLOY_DIR/noisy_cli.sh" "$DEPLOY_DIR/uninstall.sh" 2>/dev/null || true

# ----------------------------------------------------------
# 6. Verzeichnisse & Berechtigungen
# ----------------------------------------------------------
echo "[5/11] Konfiguriere Berechtigungen..."
mkdir -p "$MODELS_DIR"
chown -R noisy:noisy /home/noisy/

# ----------------------------------------------------------
# 7. KI-Modell (Zipformer Audio-Tagging)
# ----------------------------------------------------------
echo "[6/11] Pruefe KI-Modell..."
if [ ! -f "$MODELS_DIR/$MODEL_SUBDIR/model.int8.onnx" ]; then
    echo "  Lade Audio-Tagging-Modell herunter..."
    cd "$MODELS_DIR"
    wget -q --show-progress \
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/audio-tagging-models/${MODEL_SUBDIR}.tar.bz2"
    tar xf "${MODEL_SUBDIR}.tar.bz2"
    rm -f "${MODEL_SUBDIR}.tar.bz2"
    chown -R noisy:noisy "$MODELS_DIR"
else
    echo "  Modell bereits vorhanden."
fi

# ----------------------------------------------------------
# 8. ALSA-Konfiguration (USB-Mic als Default; Code waehlt zusaetzlich selbst)
# ----------------------------------------------------------
echo "[7/11] Konfiguriere Audio-Default..."
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
    echo "  ALSA Default auf Card 0 gesetzt (Fallback)."
fi

# ----------------------------------------------------------
# 9. Sudoers (Service-Steuerung, SHM-Cleanup, BLE-Beacon)
# ----------------------------------------------------------
echo "[8/11] Konfiguriere sudo-Berechtigungen..."

# btmgmt-Pfad dynamisch ermitteln (variiert je Distribution)
BTMGMT_PATH=$(command -v btmgmt || echo "/usr/bin/btmgmt")

SUDOERS_TMP=$(mktemp)
cat > "$SUDOERS_TMP" << SUDOERS
noisy ALL=(ALL) NOPASSWD: /usr/bin/systemctl start noisy.service
noisy ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop noisy.service
noisy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart noisy.service
noisy ALL=(ALL) NOPASSWD: /usr/bin/systemctl status noisy.service
noisy ALL=(ALL) NOPASSWD: /usr/bin/rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio
noisy ALL=(ALL) NOPASSWD: ${BTMGMT_PATH} power on
noisy ALL=(ALL) NOPASSWD: ${BTMGMT_PATH} power off
noisy ALL=(ALL) NOPASSWD: ${BTMGMT_PATH} add-adv *
noisy ALL=(ALL) NOPASSWD: ${BTMGMT_PATH} rm-adv *
SUDOERS

# Syntax validieren bevor wir es aktiv schalten
if visudo -c -f "$SUDOERS_TMP" >/dev/null 2>&1; then
    install -m 440 -o root -g root "$SUDOERS_TMP" /etc/sudoers.d/noisy
    echo "  sudoers-Regeln installiert und validiert."
else
    echo -e "  ${RED}FEHLER: sudoers-Syntax ungueltig, ueberspringe.${NC}"
fi
rm -f "$SUDOERS_TMP"

# ----------------------------------------------------------
# 10. CPU-Frequenz-Regel (udev) + CLI-Symlink
# ----------------------------------------------------------
echo "[9/11] Konfiguriere CPU-Freq & CLI..."
CPUFREQ_RULE="/etc/udev/rules.d/99-noisy-cpufreq.rules"
cat > "$CPUFREQ_RULE" << 'UDEV'
KERNEL=="cpu0", SUBSYSTEM=="cpu", ACTION=="add", \
  RUN+="/bin/chmod 666 /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq"
UDEV
chmod 666 /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null || true

# CLI verlinken
ln -sf "$DEPLOY_DIR/noisy_cli.sh" /usr/local/bin/noisy
chmod +x /usr/local/bin/noisy

# ----------------------------------------------------------
# 11. Alte Reste bereinigen + systemd-Service
# ----------------------------------------------------------
echo "[10/11] Bereinige alte Konfigurationen..."
systemctl stop noisy.service 2>/dev/null || true
# Alte v0.8 / Parallel-Services entfernen
rm -f /etc/systemd/system/noisy-face.service
rm -f /etc/systemd/system/noisy-audio.service

echo "[11/11] Erstelle systemd-Service..."
cat > /etc/systemd/system/noisy.service << EOF
[Unit]
Description=Noisy Mood-Mochi (v5 Orchestrator)
After=network.target sound.target bluetooth.target

[Service]
Type=simple
User=noisy
WorkingDirectory=$DEPLOY_DIR
ExecStartPre=+/bin/chmod 666 /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq
ExecStart=/usr/bin/python3 $DEPLOY_DIR/noisy_orchestrator.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

# Shared Memory aufraeumen bei Stop
ExecStopPost=/bin/rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio

[Install]
WantedBy=multi-user.target
EOF

# ----------------------------------------------------------
# Finalisierung
# ----------------------------------------------------------
systemctl daemon-reload
systemctl enable noisy.service
systemctl restart noisy.service

echo ""
echo -e "${GREEN}=== Installation von Noisy v$VERSION abgeschlossen! ===${NC}"
echo "Noisy laeuft jetzt als Service."
echo ""
echo "  Status:       noisy status   (oder: systemctl status noisy)"
echo "  Live-Log:     noisy log"
echo "  Live-Analyse: noisy debug"
echo ""
echo -e "${YELLOW}Web-Dashboard:${NC} im Browser erreichbar unter"
echo -e "      ${GREEN}http://<pi-ip>:8080${NC}"
echo "  (Helligkeit Tag/Nacht, Animation-Speed, Nacht-Fenster, Modell-Management)"
echo ""
echo -e "${YELLOW}WICHTIG:${NC} Fuer optimale Erkennung jetzt einmal kalibrieren"
echo "  (15s Stille noetig, Mikrofon angeschlossen):"
echo -e "      ${GREEN}noisy calibrate${NC}"
echo ""
echo "Hinweis: Falls das Display schwarz bleibt, pruefe ob SPI aktiv ist"
echo "  (dtparam=spi=on bzw. passendes ST7789-Overlay in config.txt)."
echo "  Ohne Display laeuft Noisy headless weiter (Audio/Mood im Log)."
