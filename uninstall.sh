#!/bin/bash

# ==========================================================
# Noisy Uninstaller v5.0 - Manifest-Driven
# Aufruf: sudo bash uninstall.sh   (oder: noisy uninstall)
# ==========================================================
set -e

APP_DIR="/home/noisy/noisy-app"
MANIFEST_FILE="$APP_DIR/manifest.json"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ----------------------------------------------------------
# Vorbedingungen
# ----------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}Bitte als root ausfuehren: sudo bash uninstall.sh${NC}"
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo -e "${RED}FEHLER: jq nicht gefunden. Installieren mit: apt install jq${NC}"
    exit 1
fi

if [ ! -f "$MANIFEST_FILE" ]; then
    echo -e "${RED}FEHLER: manifest.json nicht gefunden in $APP_DIR.${NC}"
    echo "Unklar, was deinstalliert werden soll. Abbruch."
    exit 1
fi

# ----------------------------------------------------------
# Manifest auslesen
# ----------------------------------------------------------
VERSION=$(jq -r '.version // "unbekannt"' "$MANIFEST_FILE")
SERVICE=$(jq -r '.service // "noisy.service"' "$MANIFEST_FILE")
MODELS_DIR=$(jq -r '.models_dir // "/home/noisy/models"' "$MANIFEST_FILE")

mapfile -t FILES   < <(jq -r '.files[]?'         "$MANIFEST_FILE")
mapfile -t DIRS    < <(jq -r '.directories[]?'   "$MANIFEST_FILE")
mapfile -t RUNTIME < <(jq -r '.runtime_files[]?' "$MANIFEST_FILE")
mapfile -t MODELS  < <(jq -r '.models[]?'        "$MANIFEST_FILE")

echo -e "${YELLOW}WARNUNG:${NC} Dies entfernt Noisy v$VERSION samt KI-Modellen"
echo "und allen Personality-/Kalibrierungsdaten."
read -p "Fortfahren? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Abgebrochen."
    exit 0
fi

# ----------------------------------------------------------
# 1. Service stoppen, deaktivieren, entfernen
# ----------------------------------------------------------
echo -e "${GREEN}[1/7]${NC} Stoppe und entferne Service..."
systemctl stop "$SERVICE" 2>/dev/null || true
systemctl disable "$SERVICE" 2>/dev/null || true
rm -f "/etc/systemd/system/$SERVICE"
systemctl daemon-reload

# ----------------------------------------------------------
# 2. Shared Memory aufraeumen
# ----------------------------------------------------------
echo -e "${GREEN}[2/7]${NC} Raeume Shared Memory auf..."
rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio

# ----------------------------------------------------------
# 3. Anwendungsdateien, Runtime-Daten, Verzeichnisse
# ----------------------------------------------------------
echo -e "${GREEN}[3/7]${NC} Entferne Anwendungsdateien..."
for f in "${FILES[@]}"; do
    rm -f "$APP_DIR/$f"
done
for rf in "${RUNTIME[@]}"; do
    rm -f "$APP_DIR/$rf"
done
for d in "${DIRS[@]}"; do
    rm -rf "$APP_DIR/$d"
done
rm -rf "$APP_DIR/__pycache__" "$APP_DIR/moods/__pycache__" 2>/dev/null || true

# ----------------------------------------------------------
# 4. KI-Modelle
# ----------------------------------------------------------
echo -e "${GREEN}[4/7]${NC} Entferne KI-Modelle..."
for m in "${MODELS[@]}"; do
    rm -rf "$MODELS_DIR/$m"
done

# ----------------------------------------------------------
# 5. System-Integration (sudoers, udev, CLI-Symlink)
# ----------------------------------------------------------
echo -e "${GREEN}[5/7]${NC} Entferne System-Integration..."
rm -f /etc/sudoers.d/noisy
rm -f /etc/udev/rules.d/99-noisy-cpufreq.rules
rm -f /usr/local/bin/noisy

# ----------------------------------------------------------
# 6. Lifecycle-Dateien (Installer + Manifest)
# ----------------------------------------------------------
echo -e "${GREEN}[6/7]${NC} Entferne Lifecycle-Dateien..."
rm -f "$APP_DIR/install.sh"
rm -f "$MANIFEST_FILE"

# ----------------------------------------------------------
# 7. Optional: User 'noisy' samt Home entfernen
# ----------------------------------------------------------
echo -e "${GREEN}[7/7]${NC} Kernkomponenten entfernt."
echo ""
read -p "Auch User 'noisy' samt Home (/home/noisy) komplett loeschen? (y/n): " del_user

if [ "$del_user" = "y" ]; then
    if id -u noisy &>/dev/null; then
        deluser --remove-home noisy 2>/dev/null || userdel -r noisy 2>/dev/null || true
        echo "  User 'noisy' und /home/noisy entfernt."
    fi
    USER_REMOVED=1
else
    echo "  User 'noisy' und Home bleiben erhalten."
    USER_REMOVED=0
fi

echo ""
echo "-------------------------------------------------------"
echo -e "${GREEN}=== Noisy v$VERSION wurde entfernt. ===${NC}"
echo "-------------------------------------------------------"
echo "Hinweis: /etc/asound.conf wurde NICHT angetastet."
echo "Falls sie nur fuer Noisy gesetzt war, bei Bedarf manuell pruefen."
echo ""

# ----------------------------------------------------------
# Selbstloeschung (allerletzte Aktion)
# ----------------------------------------------------------
if [ "$USER_REMOVED" -ne 1 ]; then
    rm -f "$APP_DIR/uninstall.sh"
    rmdir "$APP_DIR" 2>/dev/null || true
fi
