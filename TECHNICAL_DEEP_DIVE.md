# Technical Deep Dive: Noisy Project

## Overview
I developed **Noisy** — a system-level ambient computing project designed for edge hardware. The primary engineering challenge was deploying a complex Audio AI (SenseVoice) with real-time emotion mapping on extremely resource-constrained hardware (Raspberry Pi Zero 2 WH). 

To achieve this, I moved beyond standard application development and implemented several architectural "hacks" to optimize performance and user experience:

---

### 🚀 Key Engineering Achievements

#### 1. Edge Computing & Optimization
*   **Zero-Copy Data Communication:** Implemented a **Shared Memory Hub** to facilitate communication between the Audio Engine and the Rendering Loop. 
*   **Performance Impact:** By bypassing traditional data copying, I optimized the system for specific hardware CPU cycles and RAM latencies, ensuring high FPS and low latency on minimal hardware.

#### 2. System Architecture & Lifecycle Management
*   **Idempotent Installation:** Designed an automated installer that handles dependency resolution, model management, and hardware tuning in a single pass.
*   **Manifest-Driven Registry:** Implemented a JSON-based manifest system to track the installation state (files, models, services), enabling a clean and reliable uninstallation process ("Clean Uninstall").
*   **Modular Decoupling:** Enforced a strict separation between the UI layer, Core Logic, and Audio Engine to ensure modularity and fault tolerance.

#### 3. Hardware-Software Co-Design
*   **Thermal Personality:** Developed a unique feature that transforms a hardware limitation (thermal throttling) into a character trait.
*   **Dynamic Frequency Capping:** By monitoring real-time CPU temperature, the system dynamically scales CPU frequency. This physical data is mapped to the "Mochi" blob’s behavior—making the entity appear physically tired as the hardware warms up.

#### 4. UX & Persistence (Vibe Philosophy)
*   **Live Preview Dashboard:** Developed a web-based UI that utilizes Shared Memory for real-time parameter updates. This provides users with an instantaneous "Preview Mode" for brightness and speed.
*   **SD Card Preservation:** By reading/writing primarily to RAM via the Shared Memory Hub, the system significantly reduces unnecessary SD card write cycles, extending hardware longevity in a persistent environment.

---

## Technical Stack summary
- **Language:** Python 3 (Core Logic), Flask (Web UI)
- **AI & Audio:** Sherpa-ONNX, Librosa, PyAudio
- **Graphics:** PyCairo, PIL (Pillow)
- **Infrastructure:** Shared Memory, Systemd, DietPi Headless
