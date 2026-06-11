# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/),
versioning follows [Semantic Versioning](https://semver.org/).

> **Versioning note:** The version counter was reset to the `0.x` line
> (release target: `1.0.0`). An earlier rewrite labelled *v0.8* was
> discarded; the current basis is the orchestrator architecture
> (previously tracked internally as *v5*). `manifest.json` is now the
> single source of truth for the version number.

## [0.9.0] - 2026-06-11

### Added (Baseline — orchestrator architecture)
- **Process-isolated orchestrator:** `noisy_orchestrator.py` runs the
  audio engine (`noisy_audio.py`) as a crash-isolated subprocess and the
  renderer as a thread, with health checks and automatic restart.
- **Real-time audio tagging:** Sherpa-ONNX (Zipformer, int8) maps AudioSet
  labels to moods, including auto-gain, beat detection and resampling.
- **Mood system:** 35 moods across 5 groups (music, emotions, body,
  environment, idle) via a registry with component-based overrides
  (`moods/` package).
- **Decision engine:** fast-track impulse reactions, genre fingerprints,
  accumulator-based mood smoothing, context transitions, time-of-day
  awareness and per-mood minimum durations.
- **Personality (Moflin-style AEI):** energy/cheerful/shy/affection axes
  that evolve over days through genre affinity, daily sound memory and
  slow decay.
- **Component-based renderer:** ST7789 240x240 output with particles,
  blink engine, accessories, thermal droopy eyes, identity HUD and a
  night gesture.
- **Connectivity & input:** BLE beacon (Social Mode) via `btmgmt`, GPIO
  button handling (lgpio, GamePi13 layout).
- **System integration:** thermal personality, CPU frequency capping,
  privacy-first logging (`/tmp` by default, SD card in debug mode) and a
  central CLI (`noisy <command>`).

### Changed
- **Installer** rewritten for the orchestrator stack: deploy-copy to
  `/home/noisy/noisy-app`, installs the previously missing `sherpa-onnx`
  plus `bluez` and `jq`, and extends sudoers for the BLE beacon
  (`btmgmt add-adv`/`rm-adv`).
- **Versioning** single-sourced from `manifest.json` — installer, CLI,
  config and debug tool all derive the number, no hardcoded strings.
- **Uninstaller** is fully manifest-driven: removes app files, the
  `moods/` package, models at the correct path (`/home/noisy/models`),
  and the sudoers/udev/CLI-symlink integration.

### Removed
- **Discarded the broken "v0.8" rewrite branch** (`launch_noisy.py`,
  `audio_processor.py`, `config_manager.py`, `noisy_main.py`,
  `config.json`, `web_ui.py`). It reimplemented only a small subset of
  the system (no ML, no personality) and did not run: invalid PyAudio
  `options=` argument, a `nonlocal` declaration on a module global, and a
  config schema that mismatched the shipped `config.json`.
