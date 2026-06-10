# **🎭 Noisy | The Mood-Mochi**

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Hardware: Raspberry Pi Zero 2 WH](https://img.shields.io/badge/hardware-Pi%20Zero%202_WH-blue)

**Noisy is a passive emotional companion that mirrors your environment through the prism of sound.**

> *It doesn't listen to commands. It listens to your life.*

---

## **🌟 The Concept**
Noisy is not an AI assistant like Alexa or Siri. It is a **digital shadow**. 
Sitting in its holographic prism, Noisy observes the vibrations of your room:
- It **headbangs** when you blast Heavy Metal. 🤘
- It **cringes and hides** during a horror movie jumpscare. 😱
- It **sightly sways and feels sleepy** as the room goes quiet at night. 🥱
- It **literally feels heat**: As the Pi works harder, Noisy becomes physically tired—its eyelids drooping as the CPU temperature rises (Thermal Personality Hack).

---

## **✨ Key Features**
- **🧠 Real-time Emotion Detection:** Powered by `Sherpa-ONNX` & `SenseVoice`. Recognizes laughter, applause, music genres, and distinct emotions without heavy LLMs.
- **🎨 Fluid Rendering:** Uses `PyCairo` for anti-aliased vector graphics for that smooth "Mochi-Blob" look.
- **🌡️ Thermal Awareness:** A unique software governor maps real-time CPU temperatures to character behavior (Adaptive Fatigue).
- **⚡ Zero-Copy Architecture:** Utilizes Python `Shared Memory` for low-latency communication between the audio inference engine and the rendering loop, optimized for 512MB RAM.
- **🌌 Holographic Display:** Optimized specifically for the GamePi13 Prism Cube setup (SPI display with hardware rotation/flip).

---

## **🛠 Hardware Stack**
- **Host:** Raspberry Pi Zero 2 WH (DietPi Headless)
- **Display:** Waveshare GamePi13 (ST7789, 240x240 SPI)
- **Optics:** Prism Cube for the floating hologram effect
- **Audio:** USB Mini Microphone

---

## **🚀 Getting Started**

### Prerequisites
- A Raspberry Pi Zero 2 WH with DietPi installed.
- Access via SSH.
- The models must be placed in the `/home/noisy/models/` directory.

### Installation
1. **Clone the repo:**
   ```bash
   git clone https://github.com/Smilez1985/Noisy.git
   cd Noisy
   ```
   
The installer configures all services, shared memory segments, and the Noisy CLI (noisy log, noisy debug)

Run the installer: The script sets up cpufreq rules for frequency capping, installs dependencies, and configures systemd autostart.

 ```
chmod +x install.sh
sudo bash install.sh
 ```

Debug Mode: Test if the AI is recognizing your sounds correctly before starting the full experience:
 ```
python3 noisy_debug.py
 ```
**🎨 Customization & Vibe Coding**
Noisy was built for makers. You can change its personality without touching a single line of core logic:

Modify Moods: Edit vibe_db.json to map different sounds (e.g., "Dog Bark" or "Fart") to unique animations.
New Shapes: Modify the draw_mochi function in noisy_main.py to turn the blob into a tree, a flame, or any other vector shape.

**⚖️ Philosophy**
Noisy is an experiment in Ambient Consciousness. It is designed to be transparent: no cloud data, no hidden tracking. It exists only to mirror your vibe—it is a "Type File" that evolves with your environment.

**🤝 Collaboration (Human in the Loop)**
Noisy was created through Vibe Coding—a synergy of human vision and AI orchestration during an intense session where hardware and code fused into something "living"...

Made with **❤️** by *Smilez1985*

