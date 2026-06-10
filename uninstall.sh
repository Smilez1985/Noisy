#!/bin/bash

# Noisy Uninstaller - Manifest-Driven Edition
# Target: Raspberry Pi Zero 2 WH / DietPi / Raspberry Pi OS

set -e # Stop on error if something critical fails

APP_DIR="/home/noisy/noisy-app"
MANIFEST_FILE="$APP_DIR/manifest.json"

# Prüfen, ob das Manifest existiert
if [ ! -f "$MANIFEST_FILE" ]; then
    echo "❌ Error: manifest.json not found in $APP_DIR."
    echo "I don't know what to uninstall. Please ensure you are running this from the correct directory."
    exit 1
fi

# Auslesen der Daten aus dem Manifest mittels jq
VERSION=$(jq -r '.version' "$MANIFEST_FILE")
SERVICE=$(jq -r '.service' "$MANIFEST_FILE")
FILES=($(jq -r '.files[]' "$MANIFEST_FILE"))

echo "⚠️ Warning: This will completely remove Noisy v$VERSION and all associated data."
read -p "Are you sure? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Aborted."
    exit 0
fi

echo "🗑️ Removing system services..."
# Stoppe den Dienst falls aktiv
if systemctl is-active --quiet "$SERVICE"; then
    sudo systemctl stop "$SERVICE"
fi

# Deaktiviere und lösche die Systemd-Konfiguration
sudo systemctl disable "$SERVICE" 2>/dev/null || true
sudo rm -f "/etc/systemd/system/$SERVICE"
sudo systemctl daemon-reload

echo "🗑️ Removing core files..."
for file in "${FILES[@]}"; do
    FILE_PATH="$APP_DIR/$file"
    if [ -f "$FILE_PATH" ]; then
        echo "Removing $file..."
        rm "$FILE_PATH"
    fi
done

echo "🗑️ Removing models directory..."
if [ -d "$APP_DIR/models" ]; then
    rm -rf "$APP_DIR/models"
fi

# Lösche die Konfigurationsdateien zum Schluss
rm -f "$APP_DIR/config.json"
rm -f "$MANIFEST_FILE"

echo "-------------------------------------------------------"
echo "✅ Noisy v$VERSION has been completely removed."
echo "-------------------------------------------------------"
