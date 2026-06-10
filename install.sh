#!/bin/bash

# Noisy Installer - Full Automation
# Designed for Raspberry Pi Zero 2 WH (DietPi / Raspberry Pi OS)

set -e # Stop script on error

echo "🚀 Starting Noisy Installation..."

# 1. System Updates & Basic Tools
echo "🔄 Updating system and installing dependencies..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3-pip python3-dev ffmpeg wget git libasound2-dev portaudio19-dev libportaudio2 libffi-dev bc

# 2. Install Python Dependencies
echo "📦 Installing Python libraries..."
python3 -m pip install --upgrade pip
python3 -m pip install numpy pyaudio cairo pillow sherpa-onnx librosa

# 3. Model Directory Setup
MODEL_DIR="/home/noisy/models"
if [ ! -d "$MODEL_DIR" ]; then
    echo "📁 Creating models directory at $MODEL_DIR..."
    sudo mkdir -p "$MODEL_DIR"
    sudo chown -R $USER:$USER "$MODEL_DIR"
fi

# 4. Automated Model Download (The Zero-Hürden Hack)
# We only download if the files don't exist already.
echo "🔍 Checking for required models..."

# Define Models and URLs (Stable v1.9.0 versions)
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
        echo "✅ $FILENAME already exists. Skipping download."
    fi
done

# 5. Permissions & Frequency Capping Setup
echo "⚙️ Configuring system permissions..."
# Allow cpufreq-set without constant sudo prompts (if needed)
if ! command -v cpufreq-set >/dev/null 2>&1; then
    sudo apt-get install -y cpufrequtils
fi

# 6. Create Systemd Service for Autostart
echo "🛠 Setting up autostart service..."
cat <<EOF > /home/noisy/noisy_face.service
[Unit]
Description=Noisy Mood Mochi Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/noisy/noisy-app
ExecStart=/usr/bin/python3 noisy_main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Move service to system folder if it doesn't exist or create it
sudo mv /home/noisy/noisy_face.service /etc/systemd/system/noisy-face.service 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl enable noisy-face.service

echo "-------------------------------------------------------"
echo "🎉 INSTALLATION COMPLETE!"
echo "-------------------------------------------------------"
echo "1. Restart your Pi or run: sudo systemctl restart noisy-face"
echo "2. To debug, run: python3 /home/noisy/noisy-app/noisy_debug.py"
echo "3. Noisy is now ready to mirror your vibe."
echo "-------------------------------------------------------"
