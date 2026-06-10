#!/bin/bash
# ==========================================================
# Noisy Uninstaller v5.0 (Orchestrator)
# Ausfuehren als root: sudo bash uninstall.sh
# ==========================================================
set -e

APP_DIR="/home/noisy/noisy-app"
MODELS_DIR="/home/noisy/models"

echo "=== Noisy Uninstaller v5.0 ==="
echo ""

# 1. Services
echo "[1/7] Services stoppen..."
# BLE Beacon stoppen falls aktiv
btmgmt rm-adv 1 2>/dev/null || true
btmgmt power off 2>/dev/null || true
systemctl stop noisy.service 2>/dev/null || true
systemctl disable noisy.service 2>/dev/null || true
rm -f /etc/systemd/system/noisy.service
# Alte v4 Services
systemctl stop noisy-face.service 2>/dev/null || true
systemctl stop noisy-audio.service 2>/dev/null || true
systemctl disable noisy-face.service 2>/dev/null || true
systemctl disable noisy-audio.service 2>/dev/null || true
rm -f /etc/systemd/system/noisy-face.service
rm -f /etc/systemd/system/noisy-audio.service
systemctl daemon-reload
echo "  Services entfernt."

# 2. SHM
echo "[2/7] Shared Memory..."
rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio
echo "  SHM bereinigt."

# 3. CLI-Link + Sudoers
echo "[3/7] CLI + Sudoers..."
rm -f /usr/local/bin/noisy
rm -f /etc/sudoers.d/noisy
echo "  CLI-Link und Sudoers entfernt."

# 4. Aliases
echo "[4/7] Shell-Aliases..."
ALIAS_FILE="/home/noisy/.bash_aliases"
if [ -f "$ALIAS_FILE" ]; then
    sed -i '/noisy/d' "$ALIAS_FILE" 2>/dev/null || true
    [ ! -s "$ALIAS_FILE" ] && rm -f "$ALIAS_FILE"
fi
echo "  Aliases bereinigt."

# 5. App-Dateien
echo "[5/7] App-Dateien..."
rm -f "$APP_DIR/noisy_orchestrator.py"
rm -f "$APP_DIR/noisy_audio.py"
rm -f "$APP_DIR/noisy_render.py"
rm -f "$APP_DIR/noisy_config.py"
rm -f "$APP_DIR/noisy_personality.py"
rm -f "$APP_DIR/noisy_calibrate.py"
rm -f "$APP_DIR/noisy_input.py"
rm -f "$APP_DIR/noisy_beacon.py"
rm -f "$APP_DIR/noisy_cli.sh"
rm -f "$APP_DIR/debug.flag"
rm -f "$APP_DIR/social.flag"
rm -rf "$APP_DIR/moods"
# Alte Dateien
rm -f "$APP_DIR/noisy_moods.py" "$APP_DIR/noisy_debug.py"
rm -f "$APP_DIR/audio_processor.py" "$APP_DIR/noisy_main.py" "$APP_DIR/noisy_idle.py"
# Logs
rm -f "$APP_DIR/noisy.log" "$APP_DIR/noisy.log."*
rm -f "$APP_DIR/audio.log" "$APP_DIR/audio.log."*
rm -f "$APP_DIR/debug.log"
rm -f "$APP_DIR/calibration.json"
rm -rf "$APP_DIR/__pycache__"
echo "  Scripts und Logs entfernt."

# 6. ALSA Config (optional)
echo "[6/7] Audio-Config..."
if [ -f "/etc/asound.conf" ] && grep -q "Noisy" /etc/asound.conf 2>/dev/null; then
    rm -f /etc/asound.conf
    echo "  ALSA Config entfernt."
else
    echo "  ALSA Config nicht von Noisy, ueberspringe."
fi

# 7. Optionale Daten
echo ""
echo "[7/7] Optionale Daten:"

if [ -f "$APP_DIR/personality.json" ]; then
    AGE=$(python3 -c "
import json, time
with open('$APP_DIR/personality.json') as f:
    d = json.load(f)
print(f\"{(time.time() - d.get('birth_time', time.time())) / 86400:.1f}\")
" 2>/dev/null || echo "?")
    echo ""
    read -p "  Persoenlichkeit loeschen? (Noisy ist $AGE Tage alt) [j/N]: " DEL_PERS
    if [ "$DEL_PERS" = "j" ] || [ "$DEL_PERS" = "J" ]; then
        rm -f "$APP_DIR/personality.json"
        echo "  Persoenlichkeit geloescht."
    else
        echo "  Persoenlichkeit bleibt erhalten."
    fi
fi

if [ -d "$MODELS_DIR" ] && [ "$(ls -A $MODELS_DIR 2>/dev/null)" ]; then
    MODEL_SIZE=$(du -sh "$MODELS_DIR" 2>/dev/null | cut -f1)
    echo ""
    read -p "  KI-Modelle loeschen? ($MODEL_SIZE) [j/N]: " DEL_MODELS
    if [ "$DEL_MODELS" = "j" ] || [ "$DEL_MODELS" = "J" ]; then
        rm -rf "$MODELS_DIR"
        echo "  Modelle geloescht."
    else
        echo "  Modelle bleiben (spart Download bei Neuinstall)."
    fi
fi

echo ""
echo "=== Noisy deinstalliert ==="
echo ""
echo "Noch vorhanden:"
echo "  - install.sh + uninstall.sh (in $APP_DIR)"
echo "  - Python-Pakete (sherpa-onnx, pyaudio, etc.)"
echo "  - User 'noisy'"
[ -f "$APP_DIR/personality.json" ] && echo "  - Persoenlichkeit"
[ -d "$MODELS_DIR" ] && echo "  - KI-Modelle"
echo ""
