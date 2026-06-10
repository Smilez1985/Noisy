#!/bin/bash

# Noisy Full Installation Script - Registry & Versioning Edition
# Target: Raspberry Pi Zero 2 WH / DietPi / Raspberry Pi OS
# Version: 0.6

set -e # Stop on error

VERSION="0.6"
APP_DIR="/home/noisy/noisy-app"
MANIFEST_FILE="$APP_DIR/manifest.json"

echo "🚀 Starting Noisy Installation v$VERSION..."

# --- 1. System Update & Core Tools ---
echo "🔄 Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y
# Hinzufügen von jq für die Manifest-Verarbeitung
sudo apt-get install -y wget git bc python3-pip python3-dev ffmpeg \
    libasound2-dev portaudio19-dev libportaudio2 libffi-dev jq

# --- 2. Python Dependencies ---
echo "📦 Installing all required Python libraries..."
python3 -m pip install --upgrade pip
python3 -m pip install numpy pyaudio cairo pillow sherpa-onnx librosa flask requests

# --- 3. Directory & Model Setup ---
MODEL_DIR="$APP_DIR/models"
if [ ! -d "$MODEL_DIR" ]; then
    echo "📁 Creating models directory..."
    sudo mkdir -p "$MODEL_DIR"
    sudo chown -R $USER:$USER "$MODEL_DIR"
fi

# Modell-Downloads (Idempotent)
MODELS=(
    "sherpa-onnx-zipformer-small-audio-tagging-2024-04-15.onnx"
    "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17-int8.onnx"
)

URLS=(
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.9.0/sherpa-onnx-zipformer-small-audio-tagging-2024-04-15.onnx"
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.9.0/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17-int8.onnx"
)

for i in "${!MODELS[@]}"; do
    FILENAME=${MODELS[$i]}
    URL=${URLS[$i]}
    TARGET="$MODEL_DIR/$FILENAME"

    if [ ! -f "$TARGET" ]; then
        echo "📥 Downloading $FILENAME..."
        wget -q --show-progress -O "$TARGET" "$URL"
    else
        echo "✅ $FILENAME already exists."
    fi
done

# --- 4. Hardware & Systemd Configuration ---
echo "⚙️ Configuring CPU frequency rules..."
if ! command -v cpufreq-set >/dev/null 2>&1; then
    sudo apt-get install -y cpufrequtils
fi

if ! grep -q "noisy ALL=(ALL:ALL)" /etc/sudoers.d/noisy 2>/dev/null; then
    echo "noisy ALL=(ALL:ALL) NOPASSWD: cpufreq-set" | sudo tee /etc/sudoers.d/noisy > /null
fi

SERVICE_NAME="noisy-face.service"
cat <<EOF > "$APP_DIR/$SERVICE_NAME"
[Unit]
Description=Noisy Mood Mochi Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 noisy_main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

if [ ! -f "/etc/systemd/system/$SERVICE_NAME" ]; then
    sudo mv "$APP_DIR/$SERVICE_NAME" /etc/systemd/system/$SERVICE_NAME
fi

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

# --- 5. Versioning & Manifest Logic ---
echo "📝 Processing version tags and manifest..."

# Liste der Dateien, die eine interne Version besitzen sollen
CORE_FILES=(
    "noisy_main.py"
    "audio_processor.py"
    "config_manager.py"
    "web_ui.py"
)

for file in "${CORE_FILES[@]}"; do
    FILE_PATH="$APP_DIR/$file"
    if [ -f "$FILE_PATH" ]; then
        # Prüfe, ob die Datei schon eine Version hat und ob sie aktuell ist
        CURRENT_VERSION=$(grep "^# Version=" "$FILE_PATH" | cut -d'"' -f2)
        
        if [[ "$CURRENT_VERSION" != "v$VERSION" ]]; then
            echo "🔄 Updating version tag in $file to v$VERSION..."
            # Nutze sed, um die Zeile zu ersetzen oder einzufügen
            if grep -q "# Version=" "$FILE_PATH"; then
                sed -i "s/^# Version=.*/# Version=\"v$VERSION\"/" "$FILE_PATH"
            else
                sed -i "1i # Version=\"v$VERSION\"" "$FILE_PATH"
            fi
        else
            echo "✅ $file is already at v$VERSION."
        fi
    fi
done

# Erzeuge das Manifest (Registry) für den Uninstaller
FILES_JSON=$(printf '%s\n' "${CORE_FILES[@]}" | jq -R . | jq -s -c .)
MODELS_JSON=$(printf '%s\n' "${MODELS[@]}" | jq -R . | jq -s -c .)

cat <<EOF > "$MANIFEST_FILE"
{
  "version": "$VERSION",
  "install_id": "$(date +%s)",
  "files": $FILES_JSON,
  "models": $MODELS_JSON,
  "service": "$SERVICE_NAME",
  "install_date": "$(date)"
}
EOF

echo "-------------------------------------------------------"
echo "🎉 Installation of Noisy v$VERSION complete."
echo "Registry has been updated. Uninstaller is ready."
echo "-------------------------------------------------------"
