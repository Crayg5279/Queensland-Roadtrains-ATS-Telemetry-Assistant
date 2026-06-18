![Project screenshot](readme-assets/bigmac-title-image.png)

# Queensland Roadtrains Dispatcher

Queensland Roadtrains Dispatcher is a local telemetry-based CB radio companion for American Truck Simulator and Euro Truck Simulator 2. It adds Mick-Mode dispatcher alerts, immersive road stories, and a push-to-talk BigMac Assistant for live job, route, fuel, rest, and truck-status questions.

The project is built around an Australian Outback trucking roleplay setup for Queensland Roadtrains, with a dispatcher character named Mick keeping tabs on the driver during long-haul roadtrain work.

## Features

- Live SCS telemetry monitoring for speed, speed limit, fuel, damage, job status, destination, distance, ETA, rest timing, trailer state, and delivery state.
- CB-radio-style voice alerts for meaningful driving and job events.
- Mick-Mode companion check-ins for ambient dispatcher chatter during long drives.
- BigMac Assistant push-to-talk voice queries for quick telemetry answers.
- Local/offline voice playback using cached clips, generated voice lines, Windows TTS fallback, or optional local TTS systems.
- Optional local AI companion behavior through services such as Ollama.

## Main Systems

### Telemetry Event Alerts

Telemetry alerts are short event-driven messages that trigger when something important happens in-game. Examples include job start, nearing destination, delivery screen detection, speeding, low fuel, critical fuel, rest warnings, damage increases, fines, heavy-load callouts, and deadline-sensitive warnings.

Alerts are intended to be brief, practical, and resistant to spam through cooldowns and state tracking.

### Mick-Mode

Mick-Mode is the automatic dispatcher companion layer. It can speak in response to telemetry events, but it also provides occasional non-critical check-ins during active driving.

Mick is written as an older Queensland Roadtrains dispatcher and garage manager: practical, rough around the edges, mildly sarcastic, and protective without being too polished. His check-ins may mention the depot, radio, heat, fans, coffee, paperwork, Charleville, or long-haul trucking.

Alerts are triggered by events. Stories and check-ins are triggered by time, atmosphere, and immersion.

### BigMac Assistant

BigMac Assistant is separate from Mick-Mode. It only responds when push-to-talk is used.

Typical questions include:

- What is my destination?
- What is my ETA?
- How far out am I?
- How much fuel do I have?
- What is my load weight?
- How long until I need rest?
- What is the job deadline?
- Am I on a job?
- How damaged is the truck?

BigMac is intended to be direct, fast, telemetry-aware, and less theatrical than Mick.

## Requirements

### Recommended Environment

- Windows 10 or Windows 11
- American Truck Simulator or Euro Truck Simulator 2
- SCS Telemetry SDK plugin installed and working
- Python 3.10+
- Working audio output device
- Microphone if BigMac voice input is enabled

The intended roleplay setup is American Truck Simulator with the Australian Outback Map, but the dispatcher can still be useful in other telemetry-supported setups.

### Optional Local AI / TTS

Some builds may use optional local AI or voice systems:

- Ollama at `localhost:11434`
- A configured local model for companion check-ins
- Qwen3-TTS or another local TTS system
- Cached or pre-generated voice clip folders

If Ollama or a configured local AI service is not running, AI-driven Mick-Mode check-ins may fail or fall back depending on configuration.

## Installation Overview

1. Clone the repository.
2. Create a Python virtual environment.
3. Install the required Python dependencies.
4. Install and configure the SCS Telemetry SDK plugin.
5. Confirm telemetry data is available.
6. Configure script paths.
7. Configure audio or TTS backend.
8. Optionally configure Ollama or another local AI system.
9. Optionally configure BigMac push-to-talk input.
10. Run the dispatcher while ATS or ETS2 is open.

Example:

```powershell
git clone https://github.com/Crayg5279/Queensland-Roadtrains-ATS-Telemetry-Assistant.git
cd Queensland-Roadtrains-ATS-Telemetry-Assistant

python -m venv .venv
.\.venv\Scripts\activate

pip install -r requirements.txt
```

> Note: dependency installation may need to be adjusted to match the current script imports and enabled voice/assistant features.

## Running

Basic process:

1. Start ATS or ETS2.
2. Load into a profile.
3. Confirm the telemetry plugin is active.
4. Start the dispatcher script.
5. Begin driving.
6. Watch console output for status messages.
7. Use push-to-talk for BigMac Assistant if enabled.

Example:

```powershell
python queensland_roadtrains_dispatcher_v6_8c_bigmac_telemetry_expansion.py
```

Expected console messages may include:

```text
[CB RADIO] Queensland Roadtrains radio network online.
[CB RADIO] Driver profile loaded: Donny
[VOICE] Runtime backend: local dynamic clip library
[MICK MODE] Companion check-ins enabled
[TELEMETRY ASSISTANT] Ready for PTT
```

## Configuration Areas

Important configuration areas include:

- Telemetry endpoint or file source
- Cache and voice clip folders
- Audio playback backend
- Windows TTS fallback
- Qwen/Ollama paths if used
- Mick-Mode enabled state and check-in interval
- BigMac enabled state, push-to-talk binding, and recording duration
- Alert thresholds and cooldowns
- Low fuel, critical fuel, speeding, rest, destination, damage, and deadline thresholds

Local development paths should be moved into configurable values where possible. For example, prefer a configurable value such as `QR_CACHE_DIR=./cache` rather than a hard-coded local machine path.

## Supported Alert Concepts

Possible alert categories include:

- `JOB_STARTED`
- `ARRIVING_DESTINATION`
- `DELIVERY_SCREEN`
- `DELIVERY_COMPLETED`
- `SPEEDING`
- `CAUGHT_SPEEDING`
- `SPEEDING_FINE`
- `COLLISION`
- `COLLISION_FINE`
- `LOW_FUEL`
- `CRITICAL_FUEL`
- `REST_2H`
- `REST_1H`
- `REST_DUE`
- `HEADLIGHTS_OFF_AT_NIGHT`
- `DAMAGE_INCREASED`
- `HEAVY_LOAD`
- `DEADLINE_WARNING`
- `TRAILER_ATTACHED`
- `TRAILER_DETACHED`

Some categories may be disabled, removed, or combined depending on the current build.

## BigMac Intent Concepts

BigMac Assistant is expected to answer telemetry-backed questions in these areas:

- Destination
- ETA or remaining time
- Distance remaining
- Fuel level
- Current job status
- Load weight
- Job deadline
- Rest timer
- Truck or trailer damage

When telemetry is unavailable or the question is unknown, BigMac should avoid guessing and give a short fallback response.

## Troubleshooting

### No Voice Plays

Check the audio output device, cache folder path, file format support, missing clip fallback, Windows TTS availability, and console errors.

### Telemetry Is Not Updating

Check that the game is running, a profile is loaded, the telemetry plugin is installed, the telemetry endpoint or file is accessible, and local firewall settings are not blocking access.

### Ollama Check-ins Fail

Check that Ollama is open, the model is installed, the local endpoint is reachable, the configured model name is correct, and AI check-ins are enabled intentionally.

### BigMac Does Not Hear Anything

Check microphone permissions, input device selection, push-to-talk binding, recording duration, speech recognition dependencies, and console transcript output.

### Alerts Repeat Too Much

Check cooldown values, threshold clear/reset values, state tracking variables, event flags, and whether telemetry is flickering around a threshold.

### Delivery Completion Does Not Trigger

Check delivery screen detection, active job state tracking, last job/destination tracking, distance threshold logic, and pause-only detection behavior.

## Known Limitations

- Local AI generation may be slow depending on hardware.
- GPU-based TTS can affect game performance.
- Windows TTS fallback may sound less immersive.
- Ollama must be running if AI check-ins depend on it.
- BigMac intent matching depends on transcription quality and phrase matching.
- Telemetry fields may be missing depending on plugin, game, map, or job state.
- Some alerts may not fire if the game does not expose the required telemetry.
- The current build is Windows-first.
- Fresh installs may need cache folders or voice assets configured.

## Roadmap Ideas

- Move all settings to `config.json`.
- Add `.env` support.
- Create a clean `requirements.txt`.
- Split the dispatcher into modules.
- Add a typed telemetry model.
- Add a debug dashboard.
- Add CLI flags.
- Add a setup wizard.
- Add fake telemetry test mode.
- Add typed BigMac command mode.
- Improve BigMac phrase matching.
- Add per-profile character settings.
- Add more voice packs.
- Add README screenshots and log examples.

## Character Notes

Default roleplay profile:

```text
Driver: Donny
Company: Queensland Roadtrains
Base: Charleville, Queensland
```

Mick is the Queensland Roadtrains dispatcher and garage manager. Dad founded the company around 1962 and is now retired. The tone should stay short, natural, Australian, practical, and radio-like rather than long or overly polished.

## Source Overview

This README was generated from `queensland_roadtrains_readme_source_overview.md`.
