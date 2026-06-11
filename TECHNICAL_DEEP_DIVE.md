# Technical Deep Dive: Noisy Project

## Overview
I developed **Noisy** — a system-level ambient computing project designed for
edge hardware. The primary engineering challenge was deploying a real-time
audio-AI pipeline with emotion/mood mapping on extremely resource-constrained
hardware (Raspberry Pi Zero 2 WH, 512 MB RAM, 4 cores).

The classification core is **Sherpa-ONNX** running a **Zipformer audio-tagging**
model (int8 quantized). It maps AudioSet labels (laughter, applause, music
genres, animals, alarms, …) onto a 35-mood system — without a heavy LLM, so the
whole thing fits and runs on the Pi Zero 2.

To make this work on minimal hardware, I moved beyond standard application
development and implemented several architectural decisions to optimize
performance, robustness and user experience:

---

### 🚀 Key Engineering Achievements

#### 1. Edge Computing & Optimization
*   **Zero-Copy IPC via Shared Memory:** The audio engine runs as a separate,
    crash-isolated subprocess and publishes its results (detected labels,
    RMS intensity, beat speed) into a small fixed-layout **Shared Memory**
    block. The orchestrator reads them without serialization or copying.
*   **Ready-flag protocol:** A single status byte (bit `0x04` set last, cleared
    on read) signals "new data complete", avoiding torn reads between the two
    processes without locks.
*   **CPU-aware design:** Audio inference is int8-quantized and runs on 2
    threads; the renderer is pinned to a target frame budget. The system stays
    responsive on the Pi Zero 2's limited CPU and RAM.

#### 2. System Architecture & Lifecycle Management
*   **Orchestrator pattern:** A single master process (`noisy_orchestrator.py`)
    supervises the audio subprocess (restarted automatically on crash) and the
    renderer thread, and owns all decision logic — fast-track impulses, genre
    fingerprints, accumulator-based mood smoothing and context transitions.
*   **Idempotent Installation:** An automated installer handles dependency
    resolution, model download/extraction and hardware tuning in a single pass,
    deploying a deterministic file whitelist to a fixed path.
*   **Manifest-Driven Registry:** A JSON manifest is the single source of truth
    for version, service name, files, directories, runtime data and models —
    enabling a clean, fully manifest-driven uninstall ("Clean Uninstall") and a
    single place to read the version number from.
*   **Modular Decoupling:** Strict separation between UI/renderer, core logic
    (orchestrator) and the audio engine ensures fault tolerance — a crash in the
    audio subprocess cannot take down the renderer, and vice versa.

#### 3. Hardware-Software Co-Design
*   **Thermal Personality:** A unique feature that turns a hardware limitation
    (thermal load) into a character trait — as CPU temperature rises, the
    "Mochi" blob's eyelids droop and sweat particles appear.
*   **Dynamic Frequency Capping:** The orchestrator scales the CPU max frequency
    via sysfs — low frequency during silence/idle (saving power and heat), full
    frequency on audio activity.
*   **Adaptive Personality (AEI):** Four axes (energy, cheerful, shy, affection)
    evolve over days/weeks through genre affinity, a daily sound memory and slow
    decay — inspired by the Moflin concept — and are persisted to disk.

#### 4. UX & Persistence
*   **Live Web Dashboard:** A Flask UI runs as a thread inside the orchestrator
    and shares a single thread-safe `RuntimeConfig` instance with the renderer.
    Slider changes (brightness, animation speed) land directly in that shared
    object and take effect on the next frame — no extra IPC layer needed. Night
    window and auto-dim are persisted atomically (temp file + `os.replace`).
*   **Runtime Model Management:** The dashboard can download additional
    Sherpa-tagging models (`.tar.bz2`), validate them (scheme + extension check,
    size limit, path-traversal-safe extraction, presence of model + label files)
    and switch the active model at runtime; the orchestrator restarts the audio
    subprocess with the new model on the main thread to avoid SHM races.
*   **SD Card Preservation:** Logs default to a RAM disk (`/tmp`) and only touch
    the SD card in debug mode, significantly reducing write cycles and extending
    card longevity in an always-on appliance.

---

## Technical Stack summary
- **Language:** Python 3 (core logic), Flask (web UI)
- **AI & Audio:** Sherpa-ONNX (Zipformer audio-tagging, int8), PyAudio; resampling
  via NumPy (`numpy.interp`)
- **Graphics:** Pillow (PIL), NumPy-vectorized particle system
- **IPC & Concurrency:** Shared Memory (audio → orchestrator), threads
  (renderer, web UI, BLE beacon)
- **Connectivity:** BLE beacon via `btmgmt` (BlueZ); GPIO input via `lgpio`
- **Infrastructure:** systemd service, manifest-driven install/uninstall,
  DietPi headless
