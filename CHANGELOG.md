Changelog
All notable changes to this project will be published here.

[0.8.0] - (Current Release)
Added
Multi-process Orchestrator: Introduced launch_noisy.py to run Audio and UI as independent processes for increased stability.
Dev-Mode Hardware Integration: Added GPIO polling for Pin 13; pressing the button toggles Dev-Mode via Shared Memory, triggering a red visual frame and debug stats.
Silent Reboot Mechanism: Implemented automated stream recovery in audio_processor with a fallback to a system reboot if hardware errors persist.
Systemd Service: Integrated Noisy as a background service for auto-start on boot with dedicated logging paths (/var/log/noisy).
Udev Rules & Sudoers: Added persistent permissions for CPU frequency scaling and systemctl management without password prompts.
Heartbeat Watchdog: Implemented continuous heartbeat monitoring in the Shared Memory buffer to detect Audio Engine hangs.

Changed
Installer Overhaul: Updated install.sh to handle ALSA default mapping, model downloads (Sherpa-ONNX), and multi-process service setup.
Config Manager: Added logging path definitions and hardware pin configurations to the main config schema.

[0.7.0] 
Added
Input Validation: Implemented clamping for real-time UI parameters (brightness, speed) in config_manager.py.
Heartbeat Support: Initial implementation of heartbeat counters in Shared Memory for process monitoring.

[0.6.0] 
Added
Web UI Dashboard: A Flask-based control panel for real-time manipulation of brightness, animation speed, and day/night settings.
Shared Memory Architecture: Implemented zero-copy communication between the Audio Engine and Renderer to ensure low latency on Pi Zero 2 hardware.
Configuration Manager: New config_manager.py handles live RAM updates (for immediate preview) and JSON persistence (for permanent storage).
Thermal Personality Hack: Integrated CPU temperature monitoring; Noisy now physically reacts to heat by drooping eyelids and slowing down.
Manifest & Lifecycle Management: Added an idempotent install.sh with version tracking and a manifest.json-based uninstall.sh for clean environment management.
Advanced Audio Engine: Integration of Sherpa-ONNX (SenseVoice) for high-fidelity emotion detection (Laughter, Music, Screams).

Changed
Core Rendering: Refactored noisy_main.py to use dynamic color mapping from the configuration file instead of hardcoded values.
Installer: Transitioned to a versioned installer that automatically handles dependency checks and model downloads.


