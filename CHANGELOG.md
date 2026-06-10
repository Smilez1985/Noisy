# Changelog

All notable changes to this project will be published here.

## [0.6.0] - 2026-02-14 (Current Release)

### Added
- **Web UI Dashboard:** A Flask-based control panel for real-time manipulation of brightness, animation speed, and day/night settings.
- **Shared Memory Architecture:** Implemented zero-copy communication between the Audio Engine and Renderer to ensure low latency on Pi Zero 2 hardware.
- **Configuration Manager:** New `config_manager.py` handles live RAM updates (for immediate preview) and JSON persistence (for permanent storage).
- **Thermal Personality Hack:** Integrated CPU temperature monitoring; Noisy now physically reacts to heat by drooping eyelids and slowing down.
- **Manifest & Lifecycle Management:** Added an idempotent `install.sh` with version tracking and a `manifest.json`-based `uninstall.sh` for clean environment management.
- **Advanced Audio Engine:** Integration of `Sherpa-ONNX` (SenseVoice) for high-fidelity emotion detection (Laughter, Music, Screams).

### Changed
- **Core Rendering:** Refactored `noisy_main.py` to use dynamic color mapping from the configuration file instead of hardcoded values.
- **Installer:** Transitioned to a versioned installer that automatically handles dependency checks and model downloads.

---
*Note: The next major milestone will focus on "Model Management" (seamless switching between different AI personalities).*
