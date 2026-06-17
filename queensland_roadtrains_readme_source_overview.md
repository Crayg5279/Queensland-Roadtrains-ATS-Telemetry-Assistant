# Queensland Roadtrains Dispatcher / BigMac Assistant — README Source Overview

This document is a source overview for Codex to use when creating a proper GitHub README. It describes the current intent, expected setup, script behavior, runtime requirements, and the differences between the major voice/assistant systems.

> Working assumption: this overview is based on the current Queensland Roadtrains Dispatcher build around `v6.8b / v6.8c`, including Mick-Mode, telemetry alerts, story/check-in behavior, rest/weight/deadline handling, and the BigMac push-to-talk assistant.

---

## 1. Project Summary

**Queensland Roadtrains Dispatcher** is a local telemetry-driven voice companion script for American Truck Simulator / Euro Truck Simulator 2, tuned around an Australian Outback trucking roleplay setup.

The script watches live SCS telemetry, detects driving/job events, and plays short CB-radio-style voice responses from a dispatcher character named **Mick**. It also includes a push-to-talk assistant called **BigMac Assistant**, which can answer simple driver questions using live telemetry data.

The goal is immersion rather than pure automation. The system is designed to feel like a dispatcher, mechanic, or old-school roadtrain operator keeping tabs on the driver during a haul.

Primary use case:

- ATS with Australian Outback Map
- Queensland Roadtrains roleplay fleet
- Long-haul roadtrain work
- Offline/local voice playback
- Telemetry-triggered event alerts
- Optional AI-generated companion chatter
- Push-to-talk voice assistant for route/job questions

---

## 2. Core Features

### Telemetry Monitoring

The script reads live game telemetry and tracks:

- Current speed
- Speed limit
- Destination
- Cargo/job state
- Estimated distance remaining
- ETA / remaining time
- Fuel level
- Damage state
- Rest/fatigue timing
- Trailer attachment state
- Delivery screen / job completion state
- Job weight where available
- Deadline/urgency where available
- Fines or collision events where available
- Active driving time for Mick-Mode check-ins

### Voice Alert System

The script plays voice lines when specific events happen, such as:

- Job started
- Nearing destination
- Delivery completed
- Speeding
- Low fuel
- Critical fuel
- Rest needed soon
- Rest due now
- Collision or damage increase
- Speeding fine
- Collision fine
- Heavy load / weight-related callouts
- Deadline-sensitive job warnings

### Mick-Mode Companion System

Mick-Mode adds periodic dispatcher check-ins while driving. These are not necessarily tied to a critical event. They are used to reduce long quiet periods and make the truck feel like it is connected to a live depot/dispatcher.

Examples of Mick-Mode style:

- Asking how the truck is handling
- Commenting on the long road
- Mentioning the office, radio, heat, fans, coffee, or paperwork
- Light Australian banter
- Mild advice without being too intrusive

### BigMac Assistant

BigMac Assistant is a push-to-talk voice assistant for quick driver questions. It listens for a spoken question, classifies the intent, and answers using current telemetry.

Example questions:

- “What is my destination?”
- “What’s my ETA?”
- “How far out am I?”
- “How much fuel do I have?”
- “What’s my load weight?”
- “How long until I need rest?”
- “What’s the job deadline?”
- “Am I on a job?”
- “How damaged is the truck?”

BigMac is intended to be practical and quick, more like asking a co-driver or dispatcher for the current trip status.

---

## 3. Main Systems Explained

## 3.1 Telemetry Event Alerts

Telemetry alerts are short, event-driven messages.

They should:

- Trigger only when something meaningful happens
- Be short enough to sound like a real CB call
- Avoid repeating too often
- Respect cooldowns / hysteresis
- Interrupt silence only when needed
- Use cached audio where possible for fast playback

Example event alerts:

- Speed crosses warning threshold
- Fuel drops below low threshold
- Fuel drops below critical threshold
- Driver is close to the destination
- Job delivery screen appears
- Rest timer reaches warning levels
- Truck damage increases
- Speeding or collision fine occurs

The alert system is the “important stuff” layer.

---

## 3.2 Mick-Mode Alerts vs Mick-Mode Stories

Mick-Mode has two related but different styles of output.

### Mick-Mode Alerts

Mick-Mode alerts are tied to telemetry events.

They are reactive and should usually be short.

Examples:

- “Ease up, mate. You’re pushing past the limit.”
- “Fuel’s getting low. Grab a servo when you can.”
- “You’re nearly there, Donny. Bring her in clean.”
- “That knock didn’t sound cheap. Keep an eye on the damage.”

Mick-Mode alerts should be prioritized because they are based on something actually happening in-game.

### Mick-Mode Stories / Check-ins

Mick-Mode stories are non-critical ambient chatter.

They are usually triggered by active driving time rather than a specific event. They are meant to make the drive feel alive without annoying the player.

Examples:

- Mick checking in from the depot
- Mick talking about the old Queensland Roadtrains office
- Mick mentioning Dad, the founder
- Mick commenting on paperwork, the radio, fans, heat, coffee, dust, or long-haul trucking
- Light banter about the road, truck, or conditions

Stories/check-ins should:

- Be less frequent than alerts
- Avoid interrupting important telemetry warnings
- Pause when the game is paused or the player is inactive
- Avoid sounding too random or unrelated
- Stay in-character
- Not over-explain game mechanics

Simple rule:

> Alerts are triggered by events. Stories are triggered by time, atmosphere, and immersion.

---

## 3.3 BigMac Assistant

BigMac Assistant is separate from Mick-Mode.

Mick-Mode speaks automatically. BigMac only responds when the user presses push-to-talk and asks a question.

BigMac should be:

- Direct
- Fast
- Telemetry-aware
- Less theatrical than Mick
- Focused on answering the question

Example flow:

1. User presses the PTT key.
2. Script records microphone input.
3. Speech is transcribed.
4. Transcript is matched to an intent.
5. Intent is answered using current telemetry.
6. Response is spoken through the selected TTS/playback system.

Example console output:

```text
[TELEMETRY ASSISTANT] PTT recording started...
[TELEMETRY ASSISTANT] Heard: What is my destination?
[TELEMETRY ASSISTANT] Intent: destination
[TELEMETRY ASSISTANT] You are heading to jackiesfarm.
```

BigMac currently works best with hard-coded, reliable telemetry intents. It should not guess when telemetry is unavailable.

---

## 4. Prerequisites

## 4.1 Operating System

Recommended:

- Windows 10 or Windows 11

The script has been developed and tested around a Windows environment. Windows TTS fallback support is expected.

Linux/macOS may require changes to:

- TTS backend
- Audio playback
- Push-to-talk input handling
- File paths
- Microphone recording

---

## 4.2 Game Requirements

Expected game environment:

- American Truck Simulator, preferably current supported build
- SCS Telemetry SDK plugin installed and working
- Game telemetry exposed to the script through the expected local method
- Optional: Australian Outback Map for intended roleplay setting

The script should still be able to run with other maps, but some roleplay assumptions are built around Australian Outback hauling.

---

## 4.3 Python Requirements

Recommended:

- Python 3.10+
- `pip`
- Virtual environment recommended

Codex should inspect the script imports and produce the exact `requirements.txt`.

Expected dependency categories may include:

- HTTP/local telemetry reading, such as `requests`
- Audio playback, such as `pygame`, `playsound`, or similar
- Keyboard/mouse/PTT handling, such as `keyboard`, `pynput`, or similar
- Speech recognition/transcription if BigMac voice input is enabled
- Windows TTS support if fallback speech is used
- Optional Ollama/local LLM integration if AI companion check-ins are enabled

Do not assume every dependency is required. Codex should verify imports directly from the script.

---

## 4.4 Optional AI Requirements

Some builds may use optional local AI systems.

Possible optional services:

- Ollama running locally at `localhost:11434`
- A configured local model for companion check-ins
- Qwen3-TTS or another local TTS system
- Pre-generated/cached voice clip folders

If Ollama is not running, Mick-Mode AI check-ins may fail or fall back depending on configuration.

Common Ollama-related console issue:

```text
[MICK MODE] Ollama check-in failed: HTTPConnectionPool(host='localhost', port=11434)
```

This usually means Ollama is not open, the model is not loaded, or the configured endpoint is unavailable.

---

## 4.5 Audio / Voice Requirements

Depending on build configuration, the script may use:

- Pre-recorded MP3/WAV clips
- Cached generated voice clips
- Windows TTS fallback
- Local dynamic clip library
- Optional Qwen3-TTS generated lines
- Optional AI-generated text sent to TTS

Expected audio folders may include categories such as:

```text
qr-cache/
  standard/
  medium/
  high/
  generated/
  stories/
  mick_checkin.log
```

Exact folders may vary by build.

Codex should document the actual folder names used by the current script.

---

## 4.6 Microphone Requirements

Required only for BigMac Assistant voice input.

Needs:

- Working microphone
- Push-to-talk key or mouse binding
- Speech recognition/transcription dependency
- Permission for Python/script to access microphone

If voice input is disabled, BigMac may not be available unless a typed/debug command mode exists.

---

## 5. Installation Overview

Suggested Git repo setup:

```text
queensland-roadtrains-dispatcher/
  README.md
  requirements.txt
  config.example.json
  scripts/
    queensland_roadtrains_dispatcher.py
  cache/
    README.md
  docs/
    README_SOURCE_OVERVIEW.md
  samples/
    README.md
```

Recommended setup steps:

1. Clone the repository.
2. Create a Python virtual environment.
3. Install dependencies.
4. Install/configure the SCS Telemetry SDK plugin.
5. Confirm telemetry data is available.
6. Configure script paths.
7. Configure audio/TTS backend.
8. Optional: configure Ollama/local AI.
9. Optional: configure BigMac PTT input.
10. Run the script while ATS/ETS2 is open.

Example commands:

```bash
git clone <repo-url>
cd queensland-roadtrains-dispatcher

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
```

---

## 6. Configuration Items Codex Should Extract

Codex should review the script and document these values clearly:

### Paths

- Cache folder
- Voice clip folders
- Log folder
- Qwen/Ollama paths, if used
- Any hard-coded local paths

Local development paths should be replaced with configurable values.

Example local dev path that should not be hard-coded in a public README:

```text
E:\AI Development\Qwen3-TTS\qr-cache
```

Recommended replacement:

```text
QR_CACHE_DIR=./cache
```

### Game / Telemetry

- Telemetry endpoint or file source
- Polling rate
- Timeout behavior
- Required plugin version/format

### Voice

- Selected TTS backend
- Fallback TTS backend
- Cache behavior
- Clip category mapping
- Audio file type support

### Mick-Mode

- Enabled/disabled flag
- Check-in interval
- Active-driving-only behavior
- Pause/inactive detection
- Ollama/local AI settings
- Story cooldowns

### BigMac Assistant

- Enabled/disabled flag
- PTT key/button
- Recording duration
- Speech transcription backend
- Supported intents
- Fallback response when intent is unknown

### Alert Thresholds

- Speeding threshold
- Speed clear threshold
- Low fuel threshold
- Critical fuel threshold
- Rest warning thresholds
- Near-destination distance threshold
- Job completion detection threshold
- Damage change threshold
- Cooldowns for repeated alerts

---

## 7. How to Run the Script

Basic run process:

1. Start ATS/ETS2.
2. Load into profile.
3. Confirm telemetry plugin is active.
4. Start the dispatcher script.
5. Begin driving.
6. Watch console output for status messages.
7. Use PTT for BigMac Assistant if enabled.

Example command:

```bash
python queensland_roadtrains_dispatcher_v6_8c.py
```

Or, if using a cleaned Git repo structure:

```bash
python scripts/queensland_roadtrains_dispatcher.py
```

Expected startup console messages may include:

```text
[CB RADIO] Queensland Roadtrains radio network online.
[CB RADIO] Driver profile loaded: Donny
[VOICE] Runtime backend: local dynamic clip library
[VOICE] Cache folder: <cache path>
[MICK MODE] Companion check-ins enabled
[MICK MODE] Log file: <log path>
[TELEMETRY ASSISTANT] Ready for PTT
```

If using a fallback voice system, console output may include:

```text
[VOICE] Missing clip fallback: Windows TTS
```

---

## 8. What the Script Does During Gameplay

While running, the script continuously loops through these tasks:

1. Reads telemetry data.
2. Normalizes telemetry values.
3. Detects current game/job state.
4. Compares current state against previous state.
5. Triggers alerts only when state changes or thresholds are crossed.
6. Applies cooldowns to prevent repeated spam.
7. Plays matching cached audio or TTS fallback.
8. Tracks active driving time for Mick-Mode.
9. Periodically generates or plays Mick-Mode check-ins.
10. Listens for BigMac PTT input if enabled.
11. Logs important status/debug messages.

---

## 9. Event / Alert Categories

Possible alert categories:

```text
JOB_STARTED
ARRIVING_DESTINATION
DELIVERY_SCREEN
DELIVERY_COMPLETED
SPEEDING
CAUGHT_SPEEDING
SPEEDING_FINE
COLLISION
COLLISION_FINE
LOW_FUEL
CRITICAL_FUEL
REST_2H
REST_1H
REST_DUE
HEADLIGHTS_OFF_AT_NIGHT
DAMAGE_INCREASED
HEAVY_LOAD
DEADLINE_WARNING
TRAILER_ATTACHED
TRAILER_DETACHED
```

Some categories may be disabled, removed, or folded into other systems depending on the current build.

Previously removed or deprioritized categories may include:

- Engine-off rolling warnings
- Battery warnings
- Dashboard-style warnings already handled by the game UI
- Duplicate caught-speeding alerts that overlap with speeding alerts

Codex should document only categories present in the current script.

---

## 10. Current Design Preferences

Voice/personality preferences:

- Australian dispatcher tone
- Older but not elderly
- Around late 50s to early 60s
- Brotherly banter
- Mild sarcasm
- Not too goofy
- Not too polished
- Short, natural radio lines
- Generally 10–15 words for event lines
- Avoid overly long AI monologues during active driving

Mick character notes:

- Dispatcher / garage manager for Queensland Roadtrains
- Works from an old office
- Dark wood, old fans, paperwork, radio, old computer/fax vibe
- Experienced, practical, a bit rough around the edges
- Cares about the driver but covers it with jokes
- Dad founded the company around 1962 and is now retired
- Company base: Charleville, Queensland

Driver profile:

```text
Driver: Donny
Company: Queensland Roadtrains
Base: Charleville, Queensland
```

---

## 11. BigMac Assistant Supported Intent Overview

Codex should inspect the intent matcher and document exact supported phrases.

Expected intent categories:

### Destination

Answers the current job destination.

Example:

```text
User: What is my destination?
Assistant: You are heading to <destination>.
```

### ETA / Remaining Time

Answers the estimated time remaining or arrival estimate if telemetry supports it.

Example:

```text
User: What’s my ETA?
Assistant: You are about <time> out.
```

### Distance Remaining

Answers remaining distance to destination.

Example:

```text
User: How far out am I?
Assistant: You have about <distance> to go.
```

### Fuel

Answers fuel percentage or current fuel status.

Example:

```text
User: How much fuel do I have?
Assistant: You are sitting around <fuel>% fuel.
```

### Job Status

Answers whether the driver is currently on a job.

Example:

```text
User: Am I loaded?
Assistant: Yes, you are currently hauling to <destination>.
```

### Weight

Answers current cargo/load weight if available.

Example:

```text
User: What’s my weight?
Assistant: You are pulling about <weight>.
```

### Deadline

Answers job deadline or urgency if available.

Example:

```text
User: When is this due?
Assistant: Deadline is <deadline/status>.
```

### Rest

Answers fatigue/rest timer if available.

Example:

```text
User: How long until I need rest?
Assistant: You have about <time> before rest is due.
```

### Damage

Answers current truck/trailer damage if available.

Example:

```text
User: How damaged is the truck?
Assistant: Truck damage is currently around <damage>%.
```

### Unknown Intent

Should politely say it does not know or that telemetry is unavailable.

Example:

```text
I don’t have that info from telemetry right now.
```

---

## 12. Alert Priority Model

Recommended priority order:

1. Safety/critical alerts
   - Collision
   - Damage increase
   - Critical fuel
   - Rest due
2. Job-state alerts
   - Job started
   - Near destination
   - Delivery completed
3. Driving behavior alerts
   - Speeding
   - Fines
4. Planning alerts
   - Low fuel
   - Deadline warnings
   - Heavy load reminders
5. Ambient companion chatter
   - Mick-Mode stories/check-ins

Stories should never block urgent alerts.

---

## 13. Cooldown / Anti-Spam Behavior

The script should prevent repetitive alerts.

Expected behavior:

- Speeding triggers once above threshold
- Speeding resets only after dropping below clear threshold
- Fuel alerts trigger once per threshold crossing
- Rest alerts trigger at specific time thresholds
- Damage alerts trigger only when damage increases
- Delivery screen triggers once per completed job
- Mick-Mode check-ins use active driving time only
- Paused menu/inactive time should not count toward Mick-Mode timing

Example speeding hysteresis:

```text
Warn when speed > 105 km/h
Clear warning state when speed < 100 km/h
```

This prevents alerts from repeating constantly around the speed limit.

---

## 14. Logging

The script may write logs for debugging and runtime visibility.

Expected logs:

- Console startup state
- Voice backend selected
- Cache path
- Mick-Mode status
- Ollama status/errors
- BigMac PTT transcript
- Intent classification
- Telemetry event triggers
- Missing clip fallback notices

Example log path:

```text
qr-cache/mick_checkin.log
```

Codex should document actual log behavior and whether logs are safe to commit.

Recommended `.gitignore` entries:

```gitignore
__pycache__/
*.pyc
.venv/
qr-cache/
cache/generated/
*.log
*.wav
*.mp3
.env
config.local.json
```

If sample clips are intentionally included, keep them in a dedicated `samples/` folder and document licensing/ownership.

---

## 15. Known Limitations / Notes

- Local AI generation may be slow depending on hardware.
- GPU-based TTS can cause game frame drops.
- Windows TTS fallback may sound less immersive.
- Ollama must be running if AI check-ins depend on it.
- BigMac intent matching is only as good as the phrase parser/transcription.
- Telemetry fields may be missing depending on plugin/game/map/job state.
- Some alerts may not fire if the game does not expose the required telemetry.
- Hard-coded local file paths should be moved into config before public release.
- The script may currently be Windows-first.
- Audio cache folders may not exist on a fresh install.
- The README should separate required features from optional experimental features.

---

## 16. Suggested README Structure for Codex

Codex can convert this overview into a GitHub README with this structure:

```text
# Queensland Roadtrains Dispatcher

## Overview
## Features
## Requirements
## Installation
## Configuration
## Running the Script
## Telemetry Setup
## Voice / Audio Setup
## Mick-Mode
## BigMac Assistant
## Supported Alerts
## Troubleshooting
## Project Structure
## Roadmap
## Credits / License
```

---

## 17. Troubleshooting Guide

### No voice plays

Check:

- Audio output device
- Cache folder path
- File format support
- Missing clip fallback
- Windows TTS availability
- Console errors

### Telemetry is not updating

Check:

- Game is running
- Profile is loaded
- Telemetry plugin is installed
- Telemetry endpoint/file is accessible
- Script is pointed at the correct source
- Firewall is not blocking local connections

### Ollama check-ins fail

Check:

- Ollama is open
- Model is installed
- Local endpoint is reachable
- Script is using the correct model name
- AI check-ins are enabled only if intended

### BigMac does not hear anything

Check:

- Microphone permissions
- Correct input device
- PTT key/button binding
- Recording duration
- Speech recognition dependency
- Console transcript output

### Alerts repeat too much

Check:

- Cooldown values
- Threshold clear/reset values
- State tracking variables
- Event flags
- Whether telemetry is flickering around a boundary

### Delivery completion does not trigger

Check:

- Delivery screen detection
- `had_active_job`
- `has_active_job`
- `last_job_key`
- `last_destination`
- Distance threshold logic
- Pause-only detection behavior

---

## 18. Roadmap Ideas

Possible future improvements:

- Move all settings to `config.json`
- Add `.env` support
- Create clean `requirements.txt`
- Split script into modules
- Add typed telemetry model
- Add debug dashboard
- Add CLI flags
- Add setup wizard
- Add test mode with fake telemetry
- Add typed BigMac command mode
- Add better phrase matching for BigMac
- Add map/time/weather/gas-price support if reliable data sources are available
- Add per-profile character settings
- Add more voice packs
- Add README screenshots/log examples
- Add sample audio category pack

---

## 19. Recommended Refactor Notes for Codex

Codex should consider splitting the current monolithic script into modules like:

```text
src/
  main.py
  config.py
  telemetry.py
  events.py
  alerts.py
  voice.py
  mick_mode.py
  bigmac.py
  intents.py
  logging_utils.py
```

Possible classes:

```text
TelemetryClient
TelemetryState
EventDetector
AlertManager
VoiceEngine
MickModeManager
BigMacAssistant
IntentMatcher
CooldownManager
```

This would make the project easier to test, extend, and document.

---

## 20. One-Sentence README Pitch

Queensland Roadtrains Dispatcher is a local telemetry-based CB radio companion for ATS/ETS2 that adds Mick-Mode dispatcher alerts, immersive road stories, and a push-to-talk BigMac Assistant for live job, route, fuel, rest, and truck-status questions.
