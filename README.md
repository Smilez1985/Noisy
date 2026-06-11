





# **🎭 Noisy | The Mood-Mochi**

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Version](https://img.shields.io/badge/version-0.9.0-blue)
![Hardware: Raspberry Pi Zero 2 WH](https://img.shields.io/badge/hardware-Pi%20Zero%202_WH-blue)

**Noisy is a passive emotional companion that mirrors your environment through the prism of sound.**

> *It doesn't listen to commands. It listens to your life.*

---
<img width="644" height="458" alt="image" src="https://github.com/user-attachments/assets/f146a4ec-3b9b-480d-8cf7-3dde9c38653a" />   
---

---

https://github.com/user-attachments/assets/eaa5f762-81f1-40ed-a029-f727640b4aa6

---

## **🌟 The Concept**
Noisy is not a voice assistant like Alexa or Siri. It is a **digital shadow**.
Sitting in its prism, Noisy observes the vibrations of your room:
- It **headbangs** when you blast heavy metal. 🤘
- It **cringes and hides** during a horror-movie jumpscare. 😱
- It **gets sleepy** as the room goes quiet at night. 🥱
- It **literally feels heat:** as the Pi works harder, Noisy gets physically
  tired — its eyelids droop as the CPU temperature rises (Thermal Personality Hack).

Over days and weeks, Noisy also develops a **personality**: it remembers the
sounds it hears most, forms favourite music genres and shifts its baseline mood.

---

## **✨ Key Features**
- **🧠 Real-time sound recognition:** Powered by `Sherpa-ONNX` with a
  **Zipformer audio-tagging** model (int8). It maps AudioSet labels —
  laughter, applause, music, animals, alarms and more — onto **35 moods**
  in 5 groups, without a heavy LLM.
- **🎭 Adaptive personality (AEI):** four axes (energy, cheerful, shy,
  affection) that evolve over time via genre affinity, daily sound memory
  and slow decay — inspired by the Moflin concept.
- **🎨 Component-based rendering:** Uses `Pillow` (PIL) to assemble the
  avatar from reusable components (body, eyes, mouth, hair, accessories,
  particles), so each mood only defines its overrides.
- **🎛️ Live web dashboard:** A built-in Flask dashboard (port `8080`) lets
  you adjust day/night brightness, animation speed and the night-mode window
  live, and manage the AI model — download additional Sherpa-tagging models
  and switch the active one at runtime, no SSH required.
- **🌡️ Thermal awareness:** CPU temperature is mapped to character
  behaviour (drooping eyes, sweat particles) and to CPU frequency capping.
- **⚡ Zero-copy architecture:** Shared Memory carries label/mood data
  between the audio subprocess and the orchestrator, optimized for the
  Pi Zero 2's limited RAM.
- **📡 Social Mode (BLE):** broadcasts Noisy's personality state as a BLE
  beacon (visible e.g. with nRF Connect).
- **🌌 Prism/Cube display:** ST7789 240x240 SPI output with an optional
  180° rotation for the floating-hologram prism effect.
- **🔒 Privacy-first:** no cloud, no tracking; logs default to a RAM disk
  (`/tmp`) and only touch the SD card in debug mode.

---

## **🛠 Hardware Stack**
- **Host:** Raspberry Pi Zero 2 WH (DietPi, headless)
- **Display:** Waveshare GamePi13 (ST7789, 240x240 SPI)
- **Optics:** Prism cube for the floating-hologram effect (optional)
- **Audio:** USB mini microphone

---

## **🧩 Architecture**
Noisy runs as a single orchestrated service:

```
noisy_orchestrator.py  (master process)
  ├── noisy_audio.py    (subprocess, crash-isolated → Shared Memory)
  ├── noisy_render.py   (thread → ST7789 display)
  ├── web_ui.py         (thread → Flask dashboard on :8080)
  └── noisy_input.py    (GPIO buttons, GamePi13)
```

The orchestrator handles fast-track impulses, genre fingerprints,
accumulator-based mood smoothing, context transitions and personality
updates. Moods live in the `moods/` package as a registry of overrides.
The renderer and the web dashboard share a single thread-safe runtime
config, so dashboard changes take effect on the next rendered frame.

---

## **🚀 Getting Started**

### Prerequisites
- A Raspberry Pi Zero 2 WH with DietPi installed and SSH access.
- A USB microphone and the GamePi13 (ST7789) display.

### Installation
The installer deploys the app to `/home/noisy/noisy-app`, downloads the
AI model automatically, installs dependencies and registers the systemd
service plus the `noisy` CLI.

```bash
git clone https://github.com/Smilez1985/Noisy.git
cd Noisy
sudo bash install.sh
```

After installation, calibrate once in a quiet room (records 15 s of
ambient noise):

```bash
noisy calibrate
```

---

## **🎛 Web Dashboard**
Once Noisy is running, open the dashboard in any browser on the same network:

```
http://<pi-ip>:8080
```

From there you can, without touching the command line:
- adjust **day/night brightness** and **animation speed** live (changes apply
  immediately),
- set the **night-mode window** and toggle **auto-dim** (persisted across
  reboots),
- **manage AI models** — download additional Sherpa audio-tagging models
  (`.tar.bz2`) and switch the active model at runtime. Downloads are validated
  (https only, size-limited, path-traversal-safe) before being registered.

The built-in Zipformer tagging model is always available as a fallback and
cannot be removed.

---

## **🎛 CLI**
Everything is controlled through the `noisy` command:

| Command         | Description                                  |
| --------------- | -------------------------------------------- |
| `noisy status`  | Service status + debug state                 |
| `noisy log`     | Follow the live log                          |
| `noisy debug`   | Live AI analysis (labels, scores, beat)      |
| `noisy personality` | Show the AEI personality values          |
| `noisy moods`   | List all moods and label coverage            |
| `noisy calibrate` | Re-run room calibration                    |
| `noisy restart` / `stop` / `start` | Service control           |
| `noisy version` | Show version and architecture                |
| `noisy uninstall` | Manifest-driven removal                    |

> **Note:** Stop the service with `noisy stop` before running
> `noisy debug` — otherwise both processes fight over the microphone.

---

## **🎨 Customization**
Noisy is built for makers. You can change its personality without touching
the core logic:

- **Moods & sound mapping:** edit the files in the `moods/` package
  (e.g. `moods/idle.py`, `moods/musik.py`). Each mood maps AudioSet labels
  to a mood ID and defines body colour, physics, particles and accessories.
- **Look & animation:** adjust the `draw_*` methods in `noisy_render.py`
  to reshape the blob or add new accessories.
- **Tuning:** all thresholds, timeouts and gains live in `noisy_config.py`.

---

## **⚖️ Philosophy**
Noisy is an experiment in **ambient consciousness**. It is designed to be
transparent: no cloud data, no hidden tracking. It exists only to mirror
your vibe — an entity that evolves with its environment.

---

## **🤝 Collaboration (Human in the Loop)**
Noisy was created through *Vibe Coding* — a synergy of human vision and AI
orchestration, where hardware and code fused into something "living".

Made with **❤️** by *Smilez1985*
