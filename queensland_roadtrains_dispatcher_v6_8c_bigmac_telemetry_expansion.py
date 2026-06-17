import os
import glob
import json
import random
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
QWEN_DIR = BASE_DIR / "Qwen3-TTS"
QR_CACHE_DIR_PATH = QWEN_DIR / "qr-cache"
PIPER_DIR = BASE_DIR / "piper"
SOX_DIR = BASE_DIR / "sox-14.4.2"
TELEMETRY_SERVER_DIR = BASE_DIR / "ets2-telemetry-server-master" / "server"

try:
    from pynput import mouse as pynput_mouse
except ImportError:
    pynput_mouse = None

try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    sd = None
    np = None

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

import wave

# ------------------------------------------------------------
# Queensland Roadtrains CB Dispatcher
# ATS / Funbit Telemetry Server version
#
# v6.5 / MickMode 2.0 Isolated - Dynamic Voice Library + Ambient Mick Library
# - Keeps the v5 telemetry/event detection foundation
# - Removes live AI/TTS generation from the alert playback path
# - Alerts now play finished local audio clips instantly
# - Falls back to safe local/default speech if a clip is missing
# - Optional background AI/Qwen refresher slowly regenerates clips
# - Uses temp files + atomic replace so active clips are not half-written
# - v6.1 aligns runtime severities with the offline v6.1 voice library builder
# - v6.1 lowers posted-speed detection latency for in-game speed-limit alerts
# - v6.1 clean trims duplicate/dashboard-style CB alerts after playtesting
# - v6.2 adds event-context prompting so Mick reacts to the confirmed event only
# - MickMode 2.0 replaces live Ollama/Zira check-ins with a pre-recorded ambient Mick library
# - Adds middle-mouse push-to-talk telemetry assistant using local Whisper + Windows/Zira TTS
# - v6.8a adds Big Mac activation chime when middle mouse PTT opens
# - v6.8b adds Big Mac rest-time, trailer-weight, and improved deadline replies
# - v6.8c adds Big Mac game-time, fuel litres/range, air pressure, and coolant replies
#
# Runtime path:
# Telemetry -> Event -> Severity -> Local audio clip -> Playback
#
# Background path:
# Timer -> Ollama text -> Qwen TTS -> SoX radio filter -> Replace one clip
# ------------------------------------------------------------

URL = "http://localhost:25555/api/ets2/telemetry"

# Ollama local AI settings - used by the BACKGROUND generator only.
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"
USE_AI_MESSAGES = False

# Middle-mouse telemetry assistant.
# Hold middle mouse to talk, release to ask Big Mac a telemetry question.
TELEMETRY_ASSISTANT_ENABLED = True
TELEMETRY_ASSISTANT_VOICE = "Microsoft Zira Desktop"
TELEMETRY_ASSISTANT_MIN_SECONDS_BETWEEN_REQUESTS = 1.5
TELEMETRY_ASSISTANT_MODE = "ptt"  # ptt = voice question, readout = old one-click full status
TELEMETRY_ASSISTANT_WAKE_WORDS = ["big mac", "bigmac", "big mack"]
TELEMETRY_ASSISTANT_MIC_SAMPLE_RATE = 16000
TELEMETRY_ASSISTANT_MIN_RECORD_SECONDS = 0.35
TELEMETRY_ASSISTANT_MAX_RECORD_SECONDS = 12.0
TELEMETRY_ASSISTANT_WHISPER_MODEL = "base.en"
TELEMETRY_ASSISTANT_WHISPER_DEVICE = "cpu"
TELEMETRY_ASSISTANT_TEMP_WAV = str(QWEN_DIR / "bigmac_ptt_input.wav")
telemetry_assistant_last_request_time = 0.0
telemetry_assistant_recording = False
telemetry_assistant_frames = []
telemetry_assistant_stream = None
telemetry_assistant_record_start = 0.0
telemetry_assistant_whisper_model = None
telemetry_assistant_lock = threading.Lock()

# Mick Mode - isolated companion check-ins.
# This is separate from operational cached CB alerts.
# It uses Ollama + Windows TTS only; it does not call Qwen or cache generated audio.
MICK_MODE_ENABLED = True
MICK_MODE_TEXT_ONLY = False
MICK_MODE_TEST_MODE = False
MICK_MODE_SOURCE = "ambient_library"  # ambient_library only; no live Ollama for Mick Mode

# Test mode: frequent check-ins so you can quickly judge prompt quality.
MICK_TEST_INTERVAL_MIN_SECONDS = 120   # 2 minutes active driving
MICK_TEST_INTERVAL_MAX_SECONDS = 300   # 5 minutes active driving

# Final mode suggestion: enable later after testing.
MICK_FINAL_INTERVAL_MIN_SECONDS = 1200 # 20 minutes active driving
MICK_FINAL_INTERVAL_MAX_SECONDS = 1800 # 30 minutes active driving

# Timer only accumulates while these are true.
MICK_REQUIRE_UNPAUSED = True
MICK_REQUIRE_MOVING = True
MICK_MOVING_SPEED_KMH = 5
MICK_REQUIRE_JOB_ACTIVE = False

# Prevent Mick Mode from speaking too soon after an operational CB alert.
MICK_AFTER_ALERT_COOLDOWN_SECONDS = 120

# Keep generated check-ins out of the main cache. Text-only log for review.
# Defined after QR_CACHE_DIR below.

# Ollama text-generation settings for Mick Mode.
MICK_MODE_OLLAMA_TIMEOUT_SECONDS = 25
MICK_MODE_TEMPERATURE = 0.80
MICK_MODE_TOP_P = 0.90
MICK_MODE_NUM_PREDICT = 55
MICK_MODE_MAX_RETRIES = 5

# Words/phrases that force Mick Mode to retry instead of speaking/logging the line.
# Add new words here over time as weird outputs appear.
MICK_MODE_REJECT_WORDS = [
    "eta",
    "drop",
    "destination",
    "delivery",
    "stopover",
    "service stop",
    "service bay",
    "servo",
    "mackay",
    "cairns",
    "toowoomba",
    "ute",
    "cruisin",
    "cruising",
    "fuel's lookin",
    "fuel is looking",
    "fuel's gettin",
    "fuel is getting",
    "runnin' low on fuel",
    "running low on fuel",
    "running on fumes",
    "runnin' on fumes",
    "need to find some fuel",
    "fill up",
    "fill-up",
    "fillin",
    "filling",
    "last stop",
    "before morning",
    "this tired",
    "this tired ol",
    "my truck",
    "my rig",
    "gettin' on for a bit",
    "getting on for a bit",
    "right side of the",
    "fuel soon",
    "find some fuel",
    "thirsty",
    "first stop",
    "service station",
    "truck holding",
    "holding up",
    "rig holding",
    "driving",
    "on the roads",
    "on the road",
    "out there",
    "how's the road",
    "how's life treating",
    "what've you got",
    "funnin",
    "all systems",
    "maintenance done",
    "tinkering",
    "bits and bobs",
    "right track",
    "good night's drive",
]

# Session identity
DRIVER_NAME = "Donny"
UNIT_NUMBER = 5279
UNIT_SPOKEN = " ".join(str(UNIT_NUMBER))

# Dynamic voice library settings
QR_CACHE_DIR = str(QR_CACHE_DIR_PATH)
BIGMAC_CHIME_FILE = os.path.join(QR_CACHE_DIR, "bigmac_fx", "bigmac_chime.wav")
BIGMAC_PLAY_ACTIVATION_CHIME = True
MICK_MODE_LOG_FILE = os.path.join(QR_CACHE_DIR, "mick_checkin.log")
ACTIVE_AUDIO_DIR = os.path.join(QR_CACHE_DIR, "active")
MICK_MODE_AUDIO_DIR = os.path.join(ACTIVE_AUDIO_DIR, "MICK_MODE")
MICK_MODE_RECENT_CLIP_MEMORY = 25
recent_mick_mode_clips = []
FALLBACK_AUDIO_DIR = os.path.join(QR_CACHE_DIR, "fallback")
TEMP_AUDIO_DIR = os.path.join(QR_CACHE_DIR, "temp")
MANIFEST_DIR = os.path.join(QR_CACHE_DIR, "manifests")
MANIFEST_FILE = os.path.join(MANIFEST_DIR, "clips.json")

# WAV is strongly recommended. MP3 usually works through Windows MediaPlayer.
# OGG depends on installed Windows codecs, so keep OGG as experimental.
SUPPORTED_AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg")
DEFAULT_GENERATED_EXTENSION = ".wav"
CLIPS_PER_EVENT_SEVERITY = 3

# Playback behavior
PLAY_RADIO_FX = False

# Speed alert tuning.
# SPEEDING is the general absolute-speed nag.
# Posted speed-limit violations are routed into SPEEDING to avoid duplicate alerts.
SPEEDING_ABSOLUTE_TRIGGER_KMH = 105
SPEEDING_ABSOLUTE_RESET_KMH = 100
POSTED_SPEED_OVER_LIMIT_TRIGGER_KMH = 3
POSTED_SPEED_OVER_LIMIT_RESET_KMH = 1
POSTED_SPEED_TRIGGER_POLLS = 1

# Debug helper. Set True if you want console lines showing current speed/limit.
DEBUG_SPEED_LOGGING = False

# Fuel alert tuning. LOW_FUEL can escalate from low to medium before CRITICAL_FUEL.
FUEL_LOW_TRIGGER_PERCENT = 30
FUEL_MEDIUM_TRIGGER_PERCENT = 15
FUEL_CRITICAL_TRIGGER_PERCENT = 5
FUEL_ALERT_RESET_PERCENT = 35

# Damage / brake tuning. Kept near the top so later playtests can tune them easily.
DAMAGE_COLLISION_DELTA_TRIGGER = 0.005
DAMAGE_ENGINE_DELTA_TRIGGER = 0.02
MAJOR_DAMAGE_TRIGGER_TOTAL_WEAR = 0.35
MAJOR_DAMAGE_RESET_TOTAL_WEAR = 0.25
TRAILER_DAMAGE_DELTA_TRIGGER = 0.005
BRAKE_TEMP_MEDIUM_TRIGGER = 180
BRAKE_TEMP_HIGH_TRIGGER = 250
BRAKE_TEMP_RESET = 120

# Playtest-clean event policy.
# These are intentionally ignored over CB because they duplicate other events, feel dashboard-only,
# or were not useful/realistic during the v6.1 road test. Add them back later if needed.
DISABLED_RUNTIME_EVENTS = {
    "CAUGHT_SPEEDING",       # duplicate of SPEEDING; posted-limit speeding now routes to SPEEDING
    "BATTERY_WARNING",       # dashboard warning; not worth CB chatter
    "LATE_DELIVERY",        # Big Mac handles deadlines on request; avoid Zira fallback
    "AIR_PRESSURE_WARNING",  # dashboard/technical warning; often ferry/teleport related
    "AIR_PRESSURE_EMERGENCY",
    "OIL_PRESSURE_WARNING",
    "WATER_TEMP_WARNING",
    "ADBLUE_WARNING",
    "BRAKE_TEMP_WARNING",
    "ENGINE_OFF_ROLLING",    # not useful/realistic enough for this dispatcher
}

DEBUG_IGNORED_EVENTS = False

RADIO_FX_DIR = os.path.join(QR_CACHE_DIR, "radio_fx")
RADIO_INTRO_FILES = ["radio_intro.wav", "radio_click.wav"]
RADIO_OUTRO_FILES = ["radio_outro.wav", "radio_tail.wav"]

# Missing clip behavior.
# False = no live AI/Qwen during gameplay. If no local clip exists, use Windows TTS fallback.
ALLOW_LIVE_QWEN_ON_MISSING_CLIP = False
WINDOWS_FALLBACK_VOICE = "Microsoft Zira Desktop"

# Background regeneration settings.
ENABLE_BACKGROUND_GENERATOR = False
BACKGROUND_INITIAL_DELAY_SECONDS = 10
REGEN_INTERVAL_SECONDS_MIN = 30
REGEN_INTERVAL_SECONDS_MAX = 45
REQUIRE_CALM_FOR_GENERATION = True
MAX_GENERATION_SKIPS_BEFORE_FORCE = 3

# Qwen3-TTS local voice settings - used by the BACKGROUND generator only.
QWEN_MODEL_PATH = str(QWEN_DIR / "models" / "Qwen3-TTS-12Hz-0.6B-Base")
QWEN_OUTPUT_DIR = str(QWEN_DIR)

# SoX radio filter settings
SOX_EXE = str(SOX_DIR / "sox.exe")
RADIO_SAMPLE_RATE = "8000"

# Mick reference voice sample
MICK_REF_AUDIO = str(BASE_DIR / "mick-samples" / "[australian old man war veteran ]Good ......f it..mp3")
MICK_REF_TEXT = (
    "Good work, Donnie. Dad would have called that tidy work. "
    "Workshop saw that one, mate. No point rushing, Donnie. "
    "You'll get there when you get there. Fine log, mate. Don't make a habit of it."
)

# Cached Qwen model/prompt for the background generator.
qwen_model = None
mick_voice_prompt = None
sf_module = None
qwen_lock = threading.Lock()

# Dispatcher state
# Mick Mode state
last_operational_alert_real_time = 0

startup_synced = False

had_active_job = False
last_job_key = None
last_destination = "unknown destination"

route_seen_for_job = False
destination_arrival_announced = False
delivery_screen_announced = False

low_fuel_warned = False
medium_fuel_warned = False
critical_fuel_warned = False
speed_warned = False
speed_limit_warned = False
headlight_warned = False
wrong_lane_warned = False
late_delivery_warned = False

last_engine_damage = None
last_total_truck_wear = None
last_trailer_wear = None
major_damage_warned = False

rest_2h_warned = False
rest_1h_warned = False
rest_due_warned = False

air_pressure_warned = False
air_pressure_emergency_warned = False
oil_pressure_warned = False
water_temp_warned = False
battery_warned = False
adblue_warned = False
brake_temp_warned = False
park_brake_moving_warned = False
engine_off_rolling_warned = False

# Counters prevent one-frame weirdness from triggering chatter.
speed_limit_counter = 0
headlight_counter = 0
wrong_lane_counter = 0
late_delivery_counter = 0
park_brake_counter = 0
engine_off_counter = 0
brake_temp_counter = 0

# Placeholders kept so the legacy global statement inside check_events stays harmless.
reverse_warned = False
beacons_announced = False
last_cruise_on = False
last_beacons_on = False
reverse_counter = 0


def get_telemetry():
    response = requests.get(URL, timeout=3)
    response.raise_for_status()
    return response.json()


def parse_game_minutes(time_string):
    if not time_string:
        return None

    try:
        dt = datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%SZ")
        days_as_minutes = (dt.day - 1) * 24 * 60
        return days_as_minutes + (dt.hour * 60) + dt.minute
    except Exception:
        return None


def parse_game_hour(time_string):
    if not time_string:
        return None

    try:
        dt = datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%SZ")
        return dt.hour
    except Exception:
        return None


def spoken_cleanup(message):
    """
    Keeps acronyms radio-friendly for generated TTS.
    """
    replacements = {
        "ETA": "E T A",
        "GPS": "G P S",
        "UHF": "U H F",
        "km/h": "kilometers an hour",
        "km": "kilometers",
    }

    spoken = message
    for old, new in replacements.items():
        spoken = spoken.replace(old, new)

    return spoken


def ensure_voice_library_dirs():
    for folder in [ACTIVE_AUDIO_DIR, FALLBACK_AUDIO_DIR, TEMP_AUDIO_DIR, MANIFEST_DIR, RADIO_FX_DIR]:
        os.makedirs(folder, exist_ok=True)


def load_qwen_mick():
    """
    Lazy-load Qwen3-TTS only when the background generator needs it.
    This keeps game startup and live alert playback light.
    """
    global qwen_model
    global mick_voice_prompt
    global sf_module

    with qwen_lock:
        if qwen_model is not None and mick_voice_prompt is not None and sf_module is not None:
            return

        print("[GENERATOR] Loading Qwen3-TTS Mick voice model...")

        import torch
        import soundfile as sf
        from qwen_tts import Qwen3TTSModel

        model_kwargs = {}

        if torch.cuda.is_available():
            print("[GENERATOR] CUDA detected. Using GPU for background Qwen3-TTS.")
            model_kwargs["device_map"] = "cuda"
            model_kwargs["torch_dtype"] = torch.float16
        else:
            print("[GENERATOR] CUDA not detected. Using CPU. Generation may be slow.")
            model_kwargs["device_map"] = "cpu"

        qwen_model = Qwen3TTSModel.from_pretrained(
            QWEN_MODEL_PATH,
            **model_kwargs
        )

        print("[GENERATOR] Building Mick voice prompt...")
        mick_voice_prompt = qwen_model.create_voice_clone_prompt(
            ref_audio=MICK_REF_AUDIO,
            ref_text=MICK_REF_TEXT,
            x_vector_only_mode=False
        )

        sf_module = sf
        print("[GENERATOR] Mick voice ready.")


def apply_radio_filter_paths(raw_input, radio_output):
    subprocess.run(
        [
            SOX_EXE,
            raw_input,
            radio_output,
            "rate",
            RADIO_SAMPLE_RATE,
            "highpass",
            "300",
            "lowpass",
            "3400",
            "compand",
            "0.1,0.3",
            "-60,-60,-20,-10,0,-3"
        ],
        check=True,
        capture_output=True
    )

def fallback_message(event, context):
    driver = context.get("driver_name", DRIVER_NAME)

    messages = {
        "JOB_STARTED": f"Job accepted, {driver}. Cargo drop off is on GPS.",
        "ARRIVING_DESTINATION": f"You're at the turnaround point, {driver}. Secure the load.",
        "DELIVERY_SCREEN": f"Delivery confirmed, {driver}. Stand by.",
        "LOW_FUEL": f"Heads up mate, fuel's getting low. Find a servo.",
        "CRITICAL_FUEL": f"Mate, fuel's critical. Stop at the next servo.",
        "SPEEDING": f"Ease up mate, you're running a bit hot.",
        "CAUGHT_SPEEDING": f"Fine logged, mate. Keep it legal from here.",
        "HEADLIGHTS_OFF": f"Lights are off, mate. Sort that before compliance sees it.",
        "WRONG_LANE": f"Wrong lane warning, mate. Bring it back where it belongs.",
        "COLLISION": f"Incident recorded, mate. Damage report received.",
        "TRAILER_DAMAGE": f"Workshop saw that, mate. Trailer damage recorded.",
        "MAJOR_DAMAGE": f"Workshop wants a word, mate. Service required immediately.",
        "DAMAGE": f"Workshop notified, mate. Engine wear recorded.",
        "LATE_DELIVERY": f"Heads up mate, delivery is overdue.",
        "REST_2H": f"Rest acknowledged, mate. Two hours remaining.",
        "REST_1H": f"Heads up mate, one hour left on the clock.",
        "REST_DUE": f"Mate, rest is due now. Park it up.",
        "AIR_PRESSURE_WARNING": f"Workshop notified, mate. Air pressure warning recorded.",
        "AIR_PRESSURE_EMERGENCY": f"Air pressure emergency, mate. Pull it up safely.",
        "OIL_PRESSURE_WARNING": f"Workshop notified, mate. Oil pressure warning.",
        "WATER_TEMP_WARNING": f"Workshop notified, mate. Engine temperature warning.",
        "BATTERY_WARNING": f"Workshop notified, mate. Battery voltage warning.",
        "ADBLUE_WARNING": f"Compliance warning, mate. AdBlue warning recorded.",
        "BRAKE_TEMP_WARNING": f"Workshop notified, mate. Brake temperature high.",
        "PARK_BRAKE_MOVING": f"Mate, park brake's dragging. Sort that out.",
        "ENGINE_OFF_ROLLING": f"Mate, engine's off while rolling. That's not ideal.",
    }

    return messages.get(event, f"Copy that, {driver}. Stand by.")

EVENT_CONTEXT = {
    "JOB_STARTED": "Donny has started a new run.",
    "ARRIVING_DESTINATION": "Donny is nearly finished with the run.",
    "DELIVERY_SCREEN": "Donny has successfully completed the run.",

    "SPEEDING": "Donny is driving faster than he should be.",
    "LOW_FUEL": "The truck is starting to run low on fuel.",
    "CRITICAL_FUEL": "The truck is almost out of fuel.",

    "COLLISION": "Donny has damaged the truck.",
    "TRAILER_DAMAGE": "Donny has damaged the trailer.",
    "MAJOR_DAMAGE": "The truck has suffered significant damage.",
    "DAMAGE": "The truck has developed fresh wear or damage.",

    "REST_2H": "Donny has time left, but should start planning a rest.",
    "REST_1H": "Donny should think seriously about stopping for rest soon.",
    "REST_DUE": "Donny needs to stop and rest now.",

    "PARK_BRAKE_MOVING": "Donny is moving while something feels like it is dragging.",
}

EVENT_SEVERITY_CONTEXT = {
    ("SPEEDING", "low"): "This is a light nudge, not a panic.",
    ("SPEEDING", "medium"): "This is a firmer warning, but still brotherly.",
    ("SPEEDING", "high"): "This is clearly too fast and needs attention.",

    ("LOW_FUEL", "low"): "This is an early heads-up, not an emergency.",
    ("LOW_FUEL", "medium"): "This is more serious, but not empty yet.",
    ("CRITICAL_FUEL", "critical"): "This is urgent because the truck is nearly empty.",

    ("COLLISION", "low"): "This was a small knock or scrape.",
    ("COLLISION", "medium"): "This was a noticeable hit.",
    ("COLLISION", "high"): "This was a hard hit.",
    ("TRAILER_DAMAGE", "low"): "The trailer has taken a small scrape.",
    ("TRAILER_DAMAGE", "medium"): "The trailer has taken noticeable damage.",
    ("TRAILER_DAMAGE", "high"): "The trailer has taken serious damage.",
    ("DAMAGE", "low"): "This is minor fresh wear.",
    ("DAMAGE", "medium"): "This is noticeable fresh wear.",
    ("DAMAGE", "high"): "This is serious fresh wear.",
    ("MAJOR_DAMAGE", "critical"): "This is serious enough that repairs should happen soon.",

    ("REST_2H", "standard"): "This is an early rest reminder.",
    ("REST_1H", "medium"): "This is a stronger rest reminder.",
    ("REST_DUE", "critical"): "This is urgent because Donny needs to stop now.",

    ("PARK_BRAKE_MOVING", "medium"): "This is a practical warning that something feels wrong while moving.",
}


def get_event_context(event, context):
    return EVENT_CONTEXT.get(event, "Donny has done something Mick needs to react to over the radio.")


def get_event_severity_context(event, context):
    severity = context.get("severity")
    return EVENT_SEVERITY_CONTEXT.get((event, severity), "React at a natural level for this event.")


def build_ai_prompt(event, context):
    driver_name = context.get("driver_name", DRIVER_NAME)
    event_context = get_event_context(event, context)
    severity_context = get_event_severity_context(event, context)

    return f"""
You are Mick from Queensland Roadtrains.

You are speaking directly to your younger brother Donny over a UHF radio.

Queensland Roadtrains is a small family-owned trucking company founded by your father in 1962. Your father is now retired and you and Donny help keep the business running.

You are not a dispatcher.
You are not a manager.
You are not a compliance officer.
You are not a GPS.
You are not an AI assistant.

You are simply a truck driver and company owner having a quick chat with your brother over the radio.

You have spent most of your life around trucks, workshops, cattle stations, roadhouses and country towns. Trucking is second nature to you.

Your personality:
- Male
- Australian
- Queensland country accent
- Around 55-60 years old
- Relaxed
- Practical
- Friendly
- Dry sense of humour
- Occasionally sarcastic
- Never rude
- Never angry
- Never corporate
- Never formal

You enjoy giving Donny a bit of harmless stick.
You often make observations instead of giving instructions.
You sound like somebody who has known Donny his entire life.
You occasionally joke about Dad, the truck, the workshop, running the company, Donny's driving, or everyday trucking life.
You never sound overly enthusiastic.
You never sound uninterested.
You sound like a bloke leaning back in his chair with a coffee, talking over the radio.

The goal is to sound like two brothers running a trucking company together.

Speech style:
- Natural Australian English
- Casual conversation
- One sentence only
- 10-15 words preferred
- Never more than 20 words
- Quick radio transmission
- Sounds natural when spoken aloud
- Prefer Donny or mate over unit numbers

Hard rules:
- React only to the confirmed event meaning.
- You may make jokes, but only about the confirmed event meaning.
- Never invent the cause of the event.
- Never invent mechanical faults.
- Never invent tyre problems.
- Never invent workshop repairs.
- Never invent people, places, loads, cargo, customers, roads, directions, distances, ETAs, inspections, or outside conversations.
- Never read telemetry.
- Never narrate game data.
- Never mention percentages.
- Never mention exact speeds.
- Never mention exact distances.
- Never mention GPS information.
- Never mention route information.
- Never mention coordinates.
- Never mention game mechanics.
- Never explain what happened.
- Never sound like a warning system.
- Never sound like a dispatcher reading a screen.
- Never sound like a customer service representative.
- Never mention menus, screens, UI, prompts, telemetry, data, scripts, or sensors.
- Do not use emojis.
- No quotation marks.
- No stage directions.
- No prefixes like Mick:, Dispatch:, Radio:, CB:, or Queensland Roadtrains:.

Avoid phrases such as:
- Warning detected
- System alert
- Notification received
- Compliance issue
- Operator
- Vehicle
- Dispatch received
- Job assigned
- Telemetry
- Route update
- Insurance
- Claim
- Customer
- Manager
- Email
- Ticket
- Paperwork

Good examples:
Easy up mate, we're hauling freight, not chasing trophies.
Dad would've had a few words about that little stunt.
That's one way to keep the workshop boys entertained.
Looking good mate, nearly got this one wrapped up now.
Another day at the office and somehow you're still employed.
We'll call that a win before the truck changes its mind.
Good work mate, reckon Dad would've liked that one.
Bit rough on the gear there, Donny.
That's the sort of thing the workshop writes stories about.
Not bad mate, I'll let you have that one.

Driver name:
{driver_name}

Current Event:
{event}

Event Meaning:
{event_context}

Event Severity Meaning:
{severity_context}

Generate one radio message now.
""".strip()

def clean_ai_message(message, event=None):
    message = message.strip()

    unwanted_prefixes = [
        "Mick:",
        "Dispatch:",
        "Queensland Roadtrains:",
        "Radio:",
        "CB:",
        "Barry:",
        "Workshop:",
        "Compliance:",
    ]

    for prefix in unwanted_prefixes:
        if message.lower().startswith(prefix.lower()):
            message = message[len(prefix):].strip()

    message = message.splitlines()[0].strip()
    message = message.strip('"').strip("'").strip()

    if not message:
        return None

    lower = message.lower()

    # Reject model output that invents other people or unit-style robot chatter.
    forbidden_identity_bits = [
        "craig",
        "unit 8099",
        "unit 2345",
        "unit 3145",
        "unit 3456",
    ]

    for bad in forbidden_identity_bits:
        if bad in lower:
            return None

    # If it uses a unit number at all, only allow the old locked number.
    if "unit " in lower and "unit 5279" not in lower:
        return None


    forbidden_story_bits = [
        "flat tyre",
        "flat tire",
        "back tyre",
        "front tyre",
        "tyre's gone",
        "tire's gone",
        "pickup",
        "pick up",
        "customer",
        "cargo",
        "load of",
        "farm",
        "roadworks",
        "inspection",
    ]

    for bad in forbidden_story_bits:
        if bad in lower:
            return None

    # Prevent Ollama from mixing multiple event types into one radio call.
    event_phrase_groups = {
        "JOB_STARTED": ["job accepted", "new job", "assignment"],
        "DELIVERY_SCREEN": ["delivery confirmed", "delivery complete", "job complete"],
        "CAUGHT_SPEEDING": ["fine logged", "fine received", "speeding fine"],
        "COLLISION": ["incident recorded", "collision", "damage recorded"],
        "TRAILER_DAMAGE": ["trailer damage"],
        "DAMAGE": ["engine wear", "engine damage"],
        "MAJOR_DAMAGE": ["service required", "major damage", "workshop notified"],
        "LATE_DELIVERY": ["overdue"],
        "REST_2H": ["rest acknowledged", "two hours"],
        "REST_1H": ["one hour", "rest warning"],
        "REST_DUE": ["rest due"],
        "SPEEDING": ["reduce speed", "speed"],
        "HEADLIGHTS_OFF": ["headlights", "lights"],
    }

    matched_groups = set()
    for group, phrases in event_phrase_groups.items():
        for phrase in phrases:
            if phrase in lower:
                matched_groups.add(group)
                break

    if event and matched_groups:
        allowed = {event}

        if event in {"COLLISION", "TRAILER_DAMAGE", "DAMAGE", "MAJOR_DAMAGE"}:
            allowed.update({"COLLISION", "TRAILER_DAMAGE", "DAMAGE", "MAJOR_DAMAGE"})

        if event in {"SPEEDING", "CAUGHT_SPEEDING"}:
            allowed.update({"SPEEDING", "CAUGHT_SPEEDING"})

        if not matched_groups.issubset(allowed):
            return None

    words = message.split()
    if len(words) > 16:
        message = " ".join(words[:16]).rstrip(",.;:") + "."

    return message

def generate_ai_message(event, context):
    context = dict(context)
    context.setdefault("severity", determine_severity(event, context))
    prompt = build_ai_prompt(event, context)

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.55,
            "top_p": 0.85,
            "num_predict": 35
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=20)
        response.raise_for_status()
        result = response.json()
        message = clean_ai_message(result.get("response", ""), event)

        if message:
            return message

    except Exception as e:
        print(f"AI message failed, using fallback: {e}")

    return fallback_message(event, context)


# v6 runtime does not call make_message; live AI is reserved for the background generator.


def get_context(data):
    game = data.get("game", {})
    truck = data.get("truck", {})
    trailer = data.get("trailer", {})
    job = data.get("job", {})
    navigation = data.get("navigation", {})

    game_paused = game.get("paused", False)
    game_time = game.get("time")
    game_hour = parse_game_hour(game_time)
    rest_minutes = parse_game_minutes(game.get("nextRestStopTime"))

    speed_raw = truck.get("speed", 0)
    speed_kmh = abs(speed_raw)
    raw_speed_negative = speed_raw < -2

    speed_limit = navigation.get("speedLimit", 0) or 0

    fuel = truck.get("fuel", 0)
    fuel_capacity = truck.get("fuelCapacity", 1)
    fuel_percent = (fuel / fuel_capacity) * 100 if fuel_capacity else 0

    adblue = truck.get("adblue", 0)
    adblue_capacity = truck.get("adblueCapacity", 1)
    adblue_percent = (adblue / adblue_capacity) * 100 if adblue_capacity else 0

    wear_engine = truck.get("wearEngine", 0)
    wear_transmission = truck.get("wearTransmission", 0)
    wear_cabin = truck.get("wearCabin", 0)
    wear_chassis = truck.get("wearChassis", 0)
    wear_wheels = truck.get("wearWheels", 0)

    truck_wear_total = (
        wear_engine +
        wear_transmission +
        wear_cabin +
        wear_chassis +
        wear_wheels
    ) / 5

    engine_damage_percent = wear_engine * 100
    truck_wear_percent = truck_wear_total * 100

    trailer_wear = trailer.get("wear", 0)
    trailer_wear_percent = trailer_wear * 100

    lights_parking = truck.get("lightsParkingOn", False)
    lights_low = truck.get("lightsBeamLowOn", False)
    lights_high = truck.get("lightsBeamHighOn", False)
    headlights_on = bool(lights_low or lights_high)

    source_city = job.get("sourceCity")
    source_company = job.get("sourceCompany")
    destination_city = job.get("destinationCity")
    destination_company = job.get("destinationCompany")
    income = job.get("income", 0)

    cargo_name = (
        job.get("cargo")
        or job.get("cargoName")
        or job.get("cargo_name")
        or job.get("cargoId")
        or job.get("cargo_id")
        or "unknown cargo"
    )
    cargo_mass = (
        job.get("cargoMass")
        or job.get("cargo_mass")
        or job.get("cargoWeight")
        or job.get("cargo_weight")
        or job.get("mass")
        or trailer.get("mass")
        or 0
    )

    deadline_minutes = parse_game_minutes(job.get("remainingTime"))
    is_overdue = deadline_minutes is not None and deadline_minutes <= 0

    estimated_distance = navigation.get("estimatedDistance", 0) or 0

    job_key = f"{source_city}|{source_company}|{destination_city}|{destination_company}|{income}"

    return {
        "driver_name": DRIVER_NAME,
        "unit_number": UNIT_NUMBER,
        "game_paused": game_paused,
        "game_time": game_time,
        "game_hour": game_hour,
        "rest_minutes": rest_minutes,
        "speed_kmh": speed_kmh,
        "raw_speed_negative": raw_speed_negative,
        "speed_limit": speed_limit,
        "fuel_percent": fuel_percent,
        "fuel_litres": fuel,
        "fuel_capacity_litres": fuel_capacity,
        "fuel_average_consumption": truck.get("fuelAverageConsumption", 0),
        "fuel_warning_on": truck.get("fuelWarningOn", False),
        "adblue_percent": adblue_percent,
        "adblue_warning_on": truck.get("adblueWarningOn", False),
        "engine_damage": wear_engine,
        "engine_damage_percent": engine_damage_percent,
        "truck_wear_total": truck_wear_total,
        "truck_wear_percent": truck_wear_percent,
        "trailer_wear": trailer_wear,
        "trailer_wear_percent": trailer_wear_percent,
        "lights_parking_on": lights_parking,
        "lights_low_on": lights_low,
        "lights_high_on": lights_high,
        "headlights_on": headlights_on,
        "engine_on": truck.get("engineOn", False),
        "electric_on": truck.get("electricOn", False),
        "park_brake_on": truck.get("parkBrakeOn", False),
        "motor_brake_on": truck.get("motorBrakeOn", False),
        "retarder_brake": truck.get("retarderBrake", 0),
        "brake_temperature": truck.get("brakeTemperature", 0),
        "air_pressure": truck.get("airPressure", 0),
        "air_pressure_warning_on": truck.get("airPressureWarningOn", False),
        "air_pressure_emergency_on": truck.get("airPressureEmergencyOn", False),
        "oil_pressure": truck.get("oilPressure", 0),
        "oil_pressure_warning_on": truck.get("oilPressureWarningOn", False),
        "water_temperature": truck.get("waterTemperature", 0),
        "water_temperature_warning_on": truck.get("waterTemperatureWarningOn", False),
        "battery_voltage": truck.get("batteryVoltage", 0),
        "battery_voltage_warning_on": truck.get("batteryVoltageWarningOn", False),
        "source": source_city or "unknown source",
        "destination": destination_city or "unknown destination",
        "income": income,
        "cargo_name": cargo_name,
        "cargo_mass": cargo_mass,
        "deadline_minutes": deadline_minutes,
        "is_overdue": is_overdue,
        "estimated_distance": estimated_distance,
        "estimated_time": navigation.get("estimatedTime"),
        "job_key": job_key,
        "has_job_data": bool(destination_city and income),
    }


def check_events(data):
    global startup_synced, had_active_job, last_job_key, last_destination
    global route_seen_for_job, destination_arrival_announced, delivery_screen_announced
    global low_fuel_warned, medium_fuel_warned, critical_fuel_warned, speed_warned, speed_limit_warned
    global headlight_warned, wrong_lane_warned, reverse_warned, late_delivery_warned
    global last_engine_damage, last_total_truck_wear, last_trailer_wear, major_damage_warned
    global rest_2h_warned, rest_1h_warned, rest_due_warned
    global air_pressure_warned, air_pressure_emergency_warned, oil_pressure_warned
    global water_temp_warned, battery_warned, adblue_warned, brake_temp_warned
    global park_brake_moving_warned, engine_off_rolling_warned, beacons_announced
    global last_cruise_on, last_beacons_on
    global speed_limit_counter, headlight_counter, wrong_lane_counter, reverse_counter
    global late_delivery_counter, park_brake_counter, engine_off_counter, brake_temp_counter

    context = get_context(data)

    job_key = context["job_key"]
    has_job_data = context["has_job_data"]
    estimated_distance = context["estimated_distance"]
    game_paused = context["game_paused"]
    rest_minutes = context["rest_minutes"]

    route_is_moving_job = has_job_data and estimated_distance > 300

    if not startup_synced:
        startup_synced = True
        had_active_job = route_is_moving_job
        route_seen_for_job = route_is_moving_job
        last_job_key = job_key if has_job_data else None
        last_destination = context["destination"]
        last_engine_damage = context["engine_damage"]
        last_total_truck_wear = context["truck_wear_total"]
        last_trailer_wear = context["trailer_wear"]
        major_damage_warned = context["truck_wear_total"] >= MAJOR_DAMAGE_TRIGGER_TOTAL_WEAR

        if rest_minutes is not None:
            rest_2h_warned = rest_minutes <= 120
            rest_1h_warned = rest_minutes <= 60
            rest_due_warned = rest_minutes <= 0

        late_delivery_warned = context["is_overdue"]
        air_pressure_warned = context["air_pressure_warning_on"]
        air_pressure_emergency_warned = context["air_pressure_emergency_on"]
        oil_pressure_warned = context["oil_pressure_warning_on"]
        water_temp_warned = context["water_temperature_warning_on"]
        battery_warned = context["battery_voltage_warning_on"]
        adblue_warned = context["adblue_warning_on"]
        return None, context

    if has_job_data:
        last_destination = context["destination"]

    if route_is_moving_job:
        route_seen_for_job = True

    if route_is_moving_job and not had_active_job:
        had_active_job = True
        route_seen_for_job = True
        last_job_key = job_key
        destination_arrival_announced = False
        delivery_screen_announced = False
        late_delivery_warned = context["is_overdue"]
        return "JOB_STARTED", context

    if route_is_moving_job and had_active_job and job_key != last_job_key:
        last_job_key = job_key
        route_seen_for_job = True
        destination_arrival_announced = False
        delivery_screen_announced = False
        late_delivery_warned = context["is_overdue"]
        return "JOB_STARTED", context

    if has_job_data and route_seen_for_job and estimated_distance < 300 and not destination_arrival_announced:
        destination_arrival_announced = True
        return "ARRIVING_DESTINATION", context

    if has_job_data and route_seen_for_job and destination_arrival_announced and game_paused and not delivery_screen_announced:
        delivery_screen_announced = True
        had_active_job = False
        route_seen_for_job = False
        context["destination"] = last_destination
        return "DELIVERY_SCREEN", context

    if has_job_data and context["is_overdue"] and not late_delivery_warned:
        late_delivery_counter += 1
        if late_delivery_counter >= 3:
            late_delivery_warned = True
            return "LATE_DELIVERY", context
    else:
        late_delivery_counter = 0

    if rest_minutes is not None:
        if rest_minutes <= 0 and not rest_due_warned:
            rest_due_warned = True
            rest_1h_warned = True
            rest_2h_warned = True
            return "REST_DUE", context
        if rest_minutes <= 60 and not rest_1h_warned:
            rest_1h_warned = True
            rest_2h_warned = True
            return "REST_1H", context
        if rest_minutes <= 120 and not rest_2h_warned:
            rest_2h_warned = True
            return "REST_2H", context
        if rest_minutes > 120:
            rest_2h_warned = False
            rest_1h_warned = False
            rest_due_warned = False

    if context["air_pressure_emergency_on"] and not air_pressure_emergency_warned:
        air_pressure_emergency_warned = True
        return "AIR_PRESSURE_EMERGENCY", context
    if not context["air_pressure_emergency_on"]:
        air_pressure_emergency_warned = False

    if context["air_pressure_warning_on"] and not air_pressure_warned:
        air_pressure_warned = True
        return "AIR_PRESSURE_WARNING", context
    if not context["air_pressure_warning_on"]:
        air_pressure_warned = False

    if context["oil_pressure_warning_on"] and context["engine_on"] and not oil_pressure_warned:
        oil_pressure_warned = True
        return "OIL_PRESSURE_WARNING", context
    if not context["oil_pressure_warning_on"]:
        oil_pressure_warned = False

    if context["water_temperature_warning_on"] and not water_temp_warned:
        water_temp_warned = True
        return "WATER_TEMP_WARNING", context
    if not context["water_temperature_warning_on"]:
        water_temp_warned = False

    if context["battery_voltage_warning_on"] and context["engine_on"] and not battery_warned:
        battery_warned = True
        return "BATTERY_WARNING", context
    if not context["battery_voltage_warning_on"]:
        battery_warned = False

    if context["adblue_warning_on"] and not adblue_warned:
        adblue_warned = True
        return "ADBLUE_WARNING", context
    if not context["adblue_warning_on"]:
        adblue_warned = False

    if context["park_brake_on"] and context["speed_kmh"] > 5:
        park_brake_counter += 1
        if park_brake_counter >= 2 and not park_brake_moving_warned:
            park_brake_moving_warned = True
            return "PARK_BRAKE_MOVING", context
    else:
        park_brake_counter = 0
    if not context["park_brake_on"]:
        park_brake_moving_warned = False

    if not context["engine_on"] and context["speed_kmh"] > 10:
        engine_off_counter += 1
        if engine_off_counter >= 2 and not engine_off_rolling_warned:
            engine_off_rolling_warned = True
            return "ENGINE_OFF_ROLLING", context
    else:
        engine_off_counter = 0
    if context["engine_on"]:
        engine_off_rolling_warned = False

    if context["brake_temperature"] >= BRAKE_TEMP_MEDIUM_TRIGGER:
        brake_temp_counter += 1
        if brake_temp_counter >= 3 and not brake_temp_warned:
            brake_temp_warned = True
            return "BRAKE_TEMP_WARNING", context
    else:
        brake_temp_counter = 0
    if context["brake_temperature"] < BRAKE_TEMP_RESET:
        brake_temp_warned = False

    game_hour = context["game_hour"]
    is_night = game_hour is not None and (game_hour >= 18 or game_hour < 6)
    if is_night and not context["headlights_on"] and context["speed_kmh"] > 5:
        headlight_counter += 1
        if headlight_counter >= 3 and not headlight_warned:
            headlight_warned = True
            return "HEADLIGHTS_OFF", context
    else:
        headlight_counter = 0
    if context["headlights_on"] or not is_night:
        headlight_warned = False

    if DEBUG_SPEED_LOGGING and context["speed_kmh"] > 5:
        print(
            f"[DEBUG SPEED] speed={context['speed_kmh']:.0f} km/h "
            f"limit={context['speed_limit']:.0f} km/h "
            f"over={context['speed_kmh'] - context['speed_limit']:.0f} km/h"
        )

    # Posted speed-limit alert. v6.1 clean routes this into SPEEDING/<severity>
    # so the dispatcher uses the existing Mick SPEEDING library instead of duplicate CAUGHT_SPEEDING alerts.
    if (
        context["speed_limit"] > 0
        and context["speed_kmh"] > context["speed_limit"] + POSTED_SPEED_OVER_LIMIT_TRIGGER_KMH
    ):
        speed_limit_counter += 1
        if speed_limit_counter >= POSTED_SPEED_TRIGGER_POLLS and not speed_limit_warned:
            speed_limit_warned = True
            speed_warned = True
            return "SPEEDING", context
    else:
        speed_limit_counter = 0

    if (
        context["speed_limit"] > 0
        and context["speed_kmh"] <= context["speed_limit"] + POSTED_SPEED_OVER_LIMIT_RESET_KMH
    ):
        speed_limit_warned = False
        if context["speed_kmh"] < SPEEDING_ABSOLUTE_RESET_KMH:
            speed_warned = False

    if context["raw_speed_negative"] and context["speed_kmh"] > 10:
        wrong_lane_counter += 1
        if wrong_lane_counter >= 3 and not wrong_lane_warned:
            wrong_lane_warned = True
            return "WRONG_LANE", context
    else:
        wrong_lane_counter = 0
    if not context["raw_speed_negative"]:
        wrong_lane_warned = False

    # Absolute-speed alert. This also maps to SPEEDING/<severity>.
    if context["speed_kmh"] > SPEEDING_ABSOLUTE_TRIGGER_KMH and not speed_warned:
        speed_warned = True
        return "SPEEDING", context
    if context["speed_kmh"] < SPEEDING_ABSOLUTE_RESET_KMH:
        speed_warned = False

    if (context["fuel_warning_on"] or context["fuel_percent"] <= FUEL_CRITICAL_TRIGGER_PERCENT) and not critical_fuel_warned:
        critical_fuel_warned = True
        medium_fuel_warned = True
        low_fuel_warned = True
        return "CRITICAL_FUEL", context
    if context["fuel_percent"] <= FUEL_MEDIUM_TRIGGER_PERCENT and not medium_fuel_warned:
        medium_fuel_warned = True
        low_fuel_warned = True
        return "LOW_FUEL", context
    if context["fuel_percent"] <= FUEL_LOW_TRIGGER_PERCENT and not low_fuel_warned:
        low_fuel_warned = True
        return "LOW_FUEL", context
    if context["fuel_percent"] > FUEL_ALERT_RESET_PERCENT and not context["fuel_warning_on"]:
        low_fuel_warned = False
        medium_fuel_warned = False
        critical_fuel_warned = False

    if last_total_truck_wear is None:
        last_total_truck_wear = context["truck_wear_total"]
    elif context["truck_wear_total"] > last_total_truck_wear + DAMAGE_COLLISION_DELTA_TRIGGER:
        last_total_truck_wear = context["truck_wear_total"]
        return "COLLISION", context
    elif context["truck_wear_total"] > last_total_truck_wear:
        last_total_truck_wear = context["truck_wear_total"]

    if last_trailer_wear is None:
        last_trailer_wear = context["trailer_wear"]
    elif context["trailer_wear"] > last_trailer_wear + TRAILER_DAMAGE_DELTA_TRIGGER:
        last_trailer_wear = context["trailer_wear"]
        return "TRAILER_DAMAGE", context
    elif context["trailer_wear"] > last_trailer_wear:
        last_trailer_wear = context["trailer_wear"]

    if context["truck_wear_total"] >= MAJOR_DAMAGE_TRIGGER_TOTAL_WEAR and not major_damage_warned:
        major_damage_warned = True
        return "MAJOR_DAMAGE", context
    if context["truck_wear_total"] < MAJOR_DAMAGE_RESET_TOTAL_WEAR:
        major_damage_warned = False

    if last_engine_damage is None:
        last_engine_damage = context["engine_damage"]
    elif context["engine_damage"] > last_engine_damage + DAMAGE_ENGINE_DELTA_TRIGGER:
        last_engine_damage = context["engine_damage"]
        return "DAMAGE", context
    elif context["engine_damage"] > last_engine_damage:
        last_engine_damage = context["engine_damage"]

    return None, context




def normalize_event_name(event):
    return str(event).strip().upper()


def normalize_severity_name(severity):
    return str(severity).strip().lower()


def determine_severity(event, context):
    """
    Converts the old v5 event-only trigger into v6 event + severity.
    This lets the same trigger have calmer or more dramatic audio pools.
    """
    event = normalize_event_name(event)
    speed = context.get("speed_kmh", 0) or 0
    speed_limit = context.get("speed_limit", 0) or 0
    fuel = context.get("fuel_percent", 100) or 100
    truck_wear = context.get("truck_wear_percent", 0) or 0
    trailer_wear = context.get("trailer_wear_percent", 0) or 0
    engine_damage = context.get("engine_damage_percent", 0) or 0
    brake_temp = context.get("brake_temperature", 0) or 0

    if event == "SPEEDING":
        # Prefer posted-limit severity when available; otherwise fall back to absolute road speed.
        over = speed - speed_limit if speed_limit else 0
        if speed_limit and over >= 25:
            return "high"
        if speed_limit and over >= 12:
            return "medium"
        if speed_limit and over >= POSTED_SPEED_OVER_LIMIT_TRIGGER_KMH:
            return "low"
        if speed >= 120:
            return "high"
        if speed >= 112:
            return "medium"
        return "low"

    if event == "CAUGHT_SPEEDING":
        # Kept for legacy compatibility, but the runtime no longer emits this event.
        over = speed - speed_limit if speed_limit else 0
        if over >= 25:
            return "high"
        if over >= 12:
            return "medium"
        return "low"

    if event == "LOW_FUEL":
        if fuel <= FUEL_MEDIUM_TRIGGER_PERCENT:
            return "medium"
        return "low"

    if event == "CRITICAL_FUEL":
        return "critical"

    if event in {"COLLISION", "TRAILER_DAMAGE", "DAMAGE"}:
        if truck_wear >= 25 or trailer_wear >= 20 or engine_damage >= 20:
            return "high"
        if truck_wear >= 10 or trailer_wear >= 10 or engine_damage >= 10:
            return "medium"
        return "low"

    if event == "MAJOR_DAMAGE":
        return "critical"

    if event == "BRAKE_TEMP_WARNING":
        if brake_temp >= BRAKE_TEMP_HIGH_TRIGGER:
            return "high"
        return "medium"

    if event in {"AIR_PRESSURE_EMERGENCY", "REST_DUE"}:
        return "critical"

    if event in {"REST_1H", "PARK_BRAKE_MOVING", "ENGINE_OFF_ROLLING"}:
        return "medium"

    if event in {"REST_2H", "JOB_STARTED", "ARRIVING_DESTINATION", "DELIVERY_SCREEN"}:
        return "standard"

    return "standard"


def get_clip_search_dirs(event, severity):
    event = normalize_event_name(event)
    severity = normalize_severity_name(severity)

    return [
        os.path.join(ACTIVE_AUDIO_DIR, event, severity),
        os.path.join(ACTIVE_AUDIO_DIR, event, "standard"),
        os.path.join(ACTIVE_AUDIO_DIR, event),
        os.path.join(FALLBACK_AUDIO_DIR, event, severity),
        os.path.join(FALLBACK_AUDIO_DIR, event, "standard"),
        os.path.join(FALLBACK_AUDIO_DIR, event),
        FALLBACK_AUDIO_DIR,
    ]


def list_audio_files(folder):
    files = []
    if not os.path.isdir(folder):
        return files

    for ext in SUPPORTED_AUDIO_EXTENSIONS:
        files.extend(glob.glob(os.path.join(folder, f"*{ext}")))

    return [f for f in files if os.path.isfile(f)]


def pick_local_clip(event, severity):
    for folder in get_clip_search_dirs(event, severity):
        candidates = list_audio_files(folder)
        if candidates:
            return random.choice(candidates)
    return None


def powershell_single_quote(value):
    return str(value).replace("'", "''")


def play_audio_file(path):
    """
    Plays a local clip and waits for completion.
    Windows MediaPlayer handles WAV/MP3 well. OGG needs Windows codec support.
    """
    safe_path = powershell_single_quote(os.path.abspath(path))

    ps = f"""
Add-Type -AssemblyName PresentationCore
$player = New-Object System.Windows.Media.MediaPlayer
$player.Open([Uri]'{safe_path}')
$player.Volume = 1.0
$player.Play()
while (-not $player.NaturalDuration.HasTimeSpan) {{ Start-Sleep -Milliseconds 50 }}
$ms = [int]$player.NaturalDuration.TimeSpan.TotalMilliseconds + 150
Start-Sleep -Milliseconds $ms
$player.Close()
""".strip()

    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)


def play_bigmac_chime():
    """Play Big Mac's short in-cab activation chime, if present."""
    if not BIGMAC_PLAY_ACTIVATION_CHIME:
        return

    try:
        if BIGMAC_CHIME_FILE and os.path.isfile(BIGMAC_CHIME_FILE):
            play_audio_file(BIGMAC_CHIME_FILE)
        else:
            print(f"[TELEMETRY ASSISTANT] Big Mac chime not found: {BIGMAC_CHIME_FILE}")
    except Exception as e:
        print(f"[TELEMETRY ASSISTANT] Big Mac chime failed: {e}")


def maybe_play_radio_fx(kind):
    if not PLAY_RADIO_FX:
        return

    names = RADIO_INTRO_FILES if kind == "intro" else RADIO_OUTRO_FILES
    candidates = [os.path.join(RADIO_FX_DIR, name) for name in names]
    existing = [path for path in candidates if os.path.isfile(path)]

    if existing:
        play_audio_file(random.choice(existing))


def windows_tts_fallback(message):
    safe_message = powershell_single_quote(spoken_cleanup(message))
    safe_voice = powershell_single_quote(WINDOWS_FALLBACK_VOICE)

    subprocess.run([
        "powershell",
        "-NoProfile",
        "-Command",
        f"Add-Type -AssemblyName System.Speech; "
        f"$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$voice.SelectVoice('{safe_voice}'); "
        f"$voice.Rate = 1; "
        f"$voice.Volume = 100; "
        f"$voice.Speak('{safe_message}')"
    ], check=False)





def telemetry_assistant_tts(message):
    """Speak a short telemetry response through Windows SAPI/Zira."""
    safe_message = powershell_single_quote(spoken_cleanup(message))
    safe_voice = powershell_single_quote(TELEMETRY_ASSISTANT_VOICE)

    subprocess.run([
        "powershell",
        "-NoProfile",
        "-Command",
        f"Add-Type -AssemblyName System.Speech; "
        f"$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$voice.SelectVoice('{safe_voice}'); "
        f"$voice.Rate = 1; "
        f"$voice.Volume = 100; "
        f"$voice.Speak('{safe_message}')"
    ], check=False)


def format_km_from_meters(value):
    try:
        km = float(value or 0) / 1000.0
    except Exception:
        return None

    if km <= 0:
        return None
    if km < 1:
        return "less than one kilometer"
    return f"{km:.1f} kilometers"


def format_minutes(value):
    try:
        mins = int(round(float(value or 0)))
    except Exception:
        return None

    if mins <= 0:
        return None
    if mins < 60:
        return f"about {mins} minutes"

    hours = mins // 60
    rem = mins % 60
    if rem == 0:
        return f"about {hours} hour" if hours == 1 else f"about {hours} hours"
    return f"about {hours} hour {rem} minutes" if hours == 1 else f"about {hours} hours {rem} minutes"


def parse_estimated_time_minutes(value):
    """Funbit usually provides estimatedTime as 0001-01-01THH:MM:SSZ."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        return float(value) / 60.0 if value > 1000 else float(value)
    try:
        dt = datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ")
        return dt.hour * 60 + dt.minute + (dt.second / 60.0)
    except Exception:
        return None


def format_game_time(value):
    """Format Funbit game.time as a simple in-game clock."""
    if not value:
        return None
    try:
        dt = datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ")
        hour = dt.hour
        minute = dt.minute
        suffix = "AM" if hour < 12 else "PM"
        hour12 = hour % 12
        if hour12 == 0:
            hour12 = 12
        return f"{hour12}:{minute:02d} {suffix}"
    except Exception:
        return None


def format_litres(value):
    try:
        litres = float(value or 0)
    except Exception:
        return None
    if litres <= 0:
        return None
    if litres >= 100:
        return f"{round(litres)} litres"
    return f"{litres:.1f} litres"


def estimate_fuel_range_km(context):
    """Estimate range from fuel litres / average litres per kilometre."""
    try:
        fuel_litres = float(context.get("fuel_litres") or 0)
        consumption = float(context.get("fuel_average_consumption") or 0)
    except Exception:
        return None

    if fuel_litres <= 0 or consumption <= 0:
        return None

    range_km = fuel_litres / consumption
    if range_km <= 0:
        return None
    return range_km


def format_fuel_range(context):
    range_km = estimate_fuel_range_km(context)
    if range_km is None:
        return None
    if range_km < 1:
        return "less than one kilometer"
    if range_km < 100:
        return f"about {round(range_km)} kilometers"
    return f"about {round(range_km / 10) * 10} kilometers"


def format_cargo(context):
    cargo = str(context.get("cargo_name") or "unknown cargo").strip()
    mass = context.get("cargo_mass", 0)

    try:
        mass_float = float(mass or 0)
    except Exception:
        mass_float = 0

    # Funbit usually reports cargo mass in kilograms. If it is already small, treat as tonnes.
    tonnes = mass_float / 1000.0 if mass_float > 100 else mass_float

    if cargo.lower() in {"", "unknown", "unknown cargo", "none"}:
        if tonnes > 0:
            return f"{tonnes:.0f} tonnes of cargo"
        return None

    if tonnes > 0:
        if abs(tonnes - round(tonnes)) < 0.05:
            return f"{round(tonnes)} tonnes of {cargo}"
        return f"{tonnes:.1f} tonnes of {cargo}"

    return cargo


def format_trailer_weight(context):
    mass = context.get("cargo_mass", 0)
    try:
        mass_float = float(mass or 0)
    except Exception:
        return None

    if mass_float <= 0:
        return None

    tonnes = mass_float / 1000.0 if mass_float > 100 else mass_float
    if abs(tonnes - round(tonnes)) < 0.05:
        return f"{round(tonnes)} tonnes"
    return f"{tonnes:.1f} tonnes"


def describe_deadline_pressure(deadline_minutes):
    if deadline_minutes is None:
        return ""
    if deadline_minutes <= 0:
        return " The delivery deadline is overdue."
    if deadline_minutes <= 60:
        return " The clock is getting tight."
    if deadline_minutes <= 240:
        return " You still have time, but keep it moving."
    return " Plenty of time left."


def build_telemetry_assistant_status(context):
    fuel = round(context.get("fuel_percent", 0) or 0)
    fuel_litres_text = format_litres(context.get("fuel_litres"))
    fuel_range_text = format_fuel_range(context)
    game_time_text = format_game_time(context.get("game_time"))
    truck_damage = round(context.get("truck_wear_percent", 0) or 0)
    trailer_damage = round(context.get("trailer_wear_percent", 0) or 0)
    distance_text = format_km_from_meters(context.get("estimated_distance", 0))
    deadline_minutes = context.get("deadline_minutes")
    deadline_text = format_minutes(deadline_minutes)
    rest_text = format_minutes(context.get("rest_minutes"))
    cargo_text = format_cargo(context)
    weight_text = format_trailer_weight(context)
    destination = context.get("destination") or "the destination"
    has_job = bool(context.get("has_job_data"))

    parts = ["Big Mac telemetry."]

    if has_job and distance_text:
        parts.append(f"You are {distance_text} from {destination}.")
    elif has_job:
        parts.append(f"You are currently heading to {destination}.")
    else:
        parts.append("No active job is showing right now.")

    if has_job and cargo_text:
        parts.append(f"Load is {cargo_text}.")
    elif has_job and weight_text:
        parts.append(f"Trailer weight is {weight_text}.")
    if has_job and deadline_text:
        parts.append(f"Deadline is {deadline_text}.")
    if rest_text:
        parts.append(f"Required rest is in {rest_text}.")

    parts.append(f"Fuel is {fuel} percent.")
    parts.append(f"Truck damage is {truck_damage} percent.")
    parts.append(f"Trailer damage is {trailer_damage} percent.")

    return " ".join(parts)


def build_telemetry_assistant_reply(command, context):
    fuel = round(context.get("fuel_percent", 0) or 0)
    fuel_litres_text = format_litres(context.get("fuel_litres"))
    fuel_range_text = format_fuel_range(context)
    game_time_text = format_game_time(context.get("game_time"))
    truck_damage = round(context.get("truck_wear_percent", 0) or 0)
    trailer_damage = round(context.get("trailer_wear_percent", 0) or 0)
    speed = round(context.get("speed_kmh", 0) or 0)
    limit = round(context.get("speed_limit", 0) or 0)
    distance_text = format_km_from_meters(context.get("estimated_distance", 0))
    eta_text = format_minutes(parse_estimated_time_minutes(context.get("estimated_time")))
    deadline_minutes = context.get("deadline_minutes")
    deadline_text = format_minutes(deadline_minutes)
    rest_text = format_minutes(context.get("rest_minutes"))
    cargo_text = format_cargo(context)
    weight_text = format_trailer_weight(context)
    destination = context.get("destination") or "the destination"
    has_job = bool(context.get("has_job_data"))

    if command == "time":
        if game_time_text:
            return f"Current in-game time is {game_time_text}."
        return "Game time is not available right now."

    if command == "fuel_litres":
        if fuel_litres_text:
            return f"You currently have {fuel_litres_text} of fuel remaining."
        return "Fuel litre information is not available right now."

    if command == "fuel_range":
        if fuel_range_text:
            return f"Estimated fuel range is approximately {fuel_range_text}."
        return "Fuel range is not available right now."

    if command == "air_pressure":
        air = context.get("air_pressure", 0)
        try:
            air_value = round(float(air or 0))
        except Exception:
            air_value = 0
        if context.get("air_pressure_emergency_on"):
            return f"Air pressure is critical at {air_value} PSI."
        if context.get("air_pressure_warning_on"):
            return f"Air pressure is low at {air_value} PSI."
        if air_value > 0:
            return f"Air pressure is {air_value} PSI and operating normally."
        return "Air pressure information is not available right now."

    if command == "coolant":
        coolant = context.get("water_temperature", 0)
        try:
            coolant_value = round(float(coolant or 0))
        except Exception:
            coolant_value = 0
        if context.get("water_temperature_warning_on"):
            return f"Coolant temperature is high at {coolant_value} degrees Celsius."
        if coolant_value > 0:
            return f"Coolant temperature is {coolant_value} degrees Celsius and looks normal."
        return "Coolant temperature information is not available right now."

    if command == "fuel":
        if fuel <= 5:
            return f"Fuel is critical at {fuel} percent."
        if fuel <= 15:
            return f"Fuel is low at {fuel} percent."
        if fuel_litres_text:
            return f"Fuel is at {fuel} percent, with {fuel_litres_text} remaining."
        return f"Fuel is at {fuel} percent."

    if command == "destination":
        if not has_job:
            return "No active job is showing right now."
        return f"You are heading to {destination}."

    if command == "cargo":
        if not has_job:
            return "No active job is showing right now."
        if cargo_text:
            return f"You are hauling {cargo_text}."
        return "Cargo information is not available right now."

    if command == "deadline":
        if not has_job:
            return "No active job is showing right now."
        if context.get("is_overdue"):
            return "The delivery deadline is overdue."
        if deadline_text:
            return f"You have {deadline_text} before the delivery deadline.{describe_deadline_pressure(deadline_minutes)}"
        return "Deadline information is not available right now."

    if command == "rest":
        if rest_text:
            return f"You have {rest_text} before your next required rest."
        return "Rest timer information is not available right now."

    if command == "weight":
        if weight_text:
            return f"Current trailer weight is {weight_text}."
        return "Trailer weight information is not available right now."

    if command == "distance":
        if not has_job:
            return "No active job is showing right now."
        if distance_text and eta_text:
            return f"You are {distance_text} from {destination}. Arrival is {eta_text}."
        if distance_text:
            return f"You are {distance_text} from {destination}."
        if eta_text:
            return f"Arrival is {eta_text}."
        return "Distance is not available right now."

    if command == "damage":
        return f"Truck damage is {truck_damage} percent. Trailer damage is {trailer_damage} percent."

    if command == "speed":
        if limit > 0:
            return f"Current speed is {speed} kilometers an hour. Limit is {limit}."
        return f"Current speed is {speed} kilometers an hour. Speed limit is not available."

    if command == "status":
        return build_telemetry_assistant_status(context)

    return "I heard you, but I do not know which telemetry reading you wanted."


def normalize_bigmac_transcript(text):
    text = (text or "").strip().lower()
    text = text.replace("big mack", "big mac")
    text = text.replace("bigmac", "big mac")
    text = text.replace("big mac,", "big mac")
    text = text.replace("big mac.", "big mac")
    return text


def detect_telemetry_command(transcript):
    text = normalize_bigmac_transcript(transcript)

    # Wake word is optional for testing, but supported.
    for wake in TELEMETRY_ASSISTANT_WAKE_WORDS:
        text = text.replace(wake, "")
    text = text.strip(" ,.!?")

    if any(word in text for word in ["destination", "where am i headed", "where am i going", "where is this load going", "where's this load going"]):
        return "destination"

    if any(word in text for word in ["cargo", "load", "hauling", "haulin", "what am i carrying", "what's in the trailer", "whats in the trailer"]):
        return "cargo"

    if any(word in text for word in ["deadline", "due", "how much time", "time left", "time remaining", "going to make it", "make the deadline"]):
        return "deadline"

    if any(word in text for word in ["rest", "break", "sleep", "fatigue", "tired", "need to stop", "when do i need a break", "next required rest"]):
        return "rest"

    if any(word in text for word in ["weight", "weigh", "heavy", "tonnes", "tons", "trailer weight", "how heavy"]):
        return "weight"

    if any(word in text for word in ["what time", "current time", "time is it", "game time", "in-game time", "ingame time"]):
        return "time"

    if any(word in text for word in ["fuel range", "how far can i go", "range", "kilometers have i got left", "kilometres have i got left", "how many kilometers can i go", "how many kilometres can i go"]):
        return "fuel_range"

    if any(word in text for word in ["litres", "liters", "fuel in the tank", "diesel in the tank", "how much diesel", "how much fuel is in the tank"]):
        return "fuel_litres"

    if any(word in text for word in ["air pressure", "brake air", "air tank", "how's my air", "hows my air"]):
        return "air_pressure"

    if any(word in text for word in ["coolant", "engine temp", "engine temperature", "water temp", "water temperature", "how hot is the engine"]):
        return "coolant"

    if any(word in text for word in ["fuel", "diesel", "tank", "gas"]):
        return "fuel"

    if any(word in text for word in ["how long", "how far", "distance", "eta", "arrival", "arrive", "left", "remaining"]):
        return "distance"

    if any(word in text for word in ["damage", "wear", "condition", "truck damaged", "trailer damaged"]):
        return "damage"

    if any(word in text for word in ["speed", "limit", "fast", "slow"]):
        return "speed"

    if any(word in text for word in ["status", "update", "overview", "report", "reading"]):
        return "status"

    return None


def load_telemetry_assistant_whisper():
    global telemetry_assistant_whisper_model

    if WhisperModel is None:
        raise RuntimeError("faster-whisper is not installed. Run: python -m pip install faster-whisper")

    if telemetry_assistant_whisper_model is None:
        print(f"[TELEMETRY ASSISTANT] Loading Whisper model: {TELEMETRY_ASSISTANT_WHISPER_MODEL}")
        telemetry_assistant_whisper_model = WhisperModel(
            TELEMETRY_ASSISTANT_WHISPER_MODEL,
            device=TELEMETRY_ASSISTANT_WHISPER_DEVICE,
            compute_type="int8",
        )
        print("[TELEMETRY ASSISTANT] Whisper ready.")

    return telemetry_assistant_whisper_model


def save_telemetry_assistant_wav(path, audio, sample_rate):
    if audio is None or len(audio) == 0:
        raise RuntimeError("No microphone audio was recorded.")

    audio = np.asarray(audio, dtype=np.float32)
    audio = np.clip(audio, -1.0, 1.0)
    audio_i16 = (audio * 32767).astype(np.int16)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(audio_i16.tobytes())


def transcribe_telemetry_assistant_wav(path):
    model = load_telemetry_assistant_whisper()
    segments, info = model.transcribe(path, beam_size=1, language="en")
    transcript = " ".join(segment.text.strip() for segment in segments).strip()
    return transcript


def handle_telemetry_assistant_question(transcript):
    global telemetry_assistant_last_request_time

    now = time.time()
    if now - telemetry_assistant_last_request_time < TELEMETRY_ASSISTANT_MIN_SECONDS_BETWEEN_REQUESTS:
        return
    telemetry_assistant_last_request_time = now

    try:
        command = detect_telemetry_command(transcript)
        data = get_telemetry()
        context = get_context(data)
        message = build_telemetry_assistant_reply(command, context)
        print(f"[TELEMETRY ASSISTANT] Heard: {transcript}")
        print(f"[TELEMETRY ASSISTANT] Intent: {command or 'unknown'}")
        print(f"[TELEMETRY ASSISTANT] {message}")
        telemetry_assistant_tts(message)
    except Exception as e:
        message = "I do not have telemetry available right now."
        print(f"[TELEMETRY ASSISTANT] Failed: {e}")
        telemetry_assistant_tts(message)


def handle_telemetry_assistant_request():
    global telemetry_assistant_last_request_time

    if not TELEMETRY_ASSISTANT_ENABLED:
        return

    now = time.time()
    if now - telemetry_assistant_last_request_time < TELEMETRY_ASSISTANT_MIN_SECONDS_BETWEEN_REQUESTS:
        return

    telemetry_assistant_last_request_time = now

    try:
        data = get_telemetry()
        context = get_context(data)
        message = build_telemetry_assistant_status(context)
        print(f"[TELEMETRY ASSISTANT] {message}")
        telemetry_assistant_tts(message)
    except Exception as e:
        message = "I do not have telemetry available right now."
        print(f"[TELEMETRY ASSISTANT] Failed: {e}")
        telemetry_assistant_tts(message)


def telemetry_assistant_audio_callback(indata, frames, callback_time, status):
    global telemetry_assistant_frames
    if status:
        print(f"[TELEMETRY ASSISTANT] Mic status: {status}")
    telemetry_assistant_frames.append(indata.copy())


def start_telemetry_assistant_recording():
    global telemetry_assistant_recording, telemetry_assistant_frames, telemetry_assistant_stream, telemetry_assistant_record_start

    if sd is None or np is None:
        print("[TELEMETRY ASSISTANT] sounddevice/numpy missing. Run: python -m pip install sounddevice numpy")
        telemetry_assistant_tts("Microphone support is not installed yet.")
        return

    with telemetry_assistant_lock:
        if telemetry_assistant_recording:
            return

        play_bigmac_chime()

        telemetry_assistant_frames = []
        telemetry_assistant_record_start = time.time()
        telemetry_assistant_stream = sd.InputStream(
            samplerate=TELEMETRY_ASSISTANT_MIC_SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=telemetry_assistant_audio_callback,
        )
        telemetry_assistant_stream.start()
        telemetry_assistant_recording = True
        print("[TELEMETRY ASSISTANT] PTT recording started...")


def stop_telemetry_assistant_recording():
    global telemetry_assistant_recording, telemetry_assistant_frames, telemetry_assistant_stream

    with telemetry_assistant_lock:
        if not telemetry_assistant_recording:
            return

        elapsed = time.time() - telemetry_assistant_record_start
        stream = telemetry_assistant_stream
        frames = list(telemetry_assistant_frames)
        telemetry_assistant_stream = None
        telemetry_assistant_recording = False

    try:
        if stream:
            stream.stop()
            stream.close()
    except Exception:
        pass

    if elapsed < TELEMETRY_ASSISTANT_MIN_RECORD_SECONDS:
        print("[TELEMETRY ASSISTANT] PTT too short, ignored.")
        return

    if elapsed > TELEMETRY_ASSISTANT_MAX_RECORD_SECONDS:
        print("[TELEMETRY ASSISTANT] PTT recording was long; processing first captured audio anyway.")

    def worker():
        try:
            audio = np.concatenate(frames, axis=0).reshape(-1)
            save_telemetry_assistant_wav(TELEMETRY_ASSISTANT_TEMP_WAV, audio, TELEMETRY_ASSISTANT_MIC_SAMPLE_RATE)
            transcript = transcribe_telemetry_assistant_wav(TELEMETRY_ASSISTANT_TEMP_WAV)
            if not transcript:
                print("[TELEMETRY ASSISTANT] No speech detected.")
                telemetry_assistant_tts("I did not catch that.")
                return
            handle_telemetry_assistant_question(transcript)
        except Exception as e:
            print(f"[TELEMETRY ASSISTANT] PTT failed: {e}")
            telemetry_assistant_tts("I could not process the microphone audio.")

    threading.Thread(target=worker, daemon=True).start()


def start_telemetry_assistant():
    if not TELEMETRY_ASSISTANT_ENABLED:
        print("[TELEMETRY ASSISTANT] Disabled.")
        return

    if pynput_mouse is None:
        print("[TELEMETRY ASSISTANT] pynput is not installed. Run: python -m pip install pynput")
        return

    if TELEMETRY_ASSISTANT_MODE == "ptt":
        if sd is None or np is None:
            print("[TELEMETRY ASSISTANT] sounddevice/numpy missing. Run: python -m pip install sounddevice numpy")
        if WhisperModel is None:
            print("[TELEMETRY ASSISTANT] faster-whisper missing. Run: python -m pip install faster-whisper")

    def on_click(x, y, button, pressed):
        if button != pynput_mouse.Button.middle:
            return

        if TELEMETRY_ASSISTANT_MODE == "ptt":
            if pressed:
                start_telemetry_assistant_recording()
            else:
                stop_telemetry_assistant_recording()
        else:
            if pressed:
                thread = threading.Thread(target=handle_telemetry_assistant_request, daemon=True)
                thread.start()

    listener = pynput_mouse.Listener(on_click=on_click)
    listener.daemon = True
    listener.start()

    if TELEMETRY_ASSISTANT_MODE == "ptt":
        print("[TELEMETRY ASSISTANT] Middle mouse PTT enabled (Whisper + Zira).")
        print("[TELEMETRY ASSISTANT] Hold middle mouse, ask Big Mac, release to process.")
        if BIGMAC_PLAY_ACTIVATION_CHIME:
            print(f"[TELEMETRY ASSISTANT] Big Mac activation chime: {BIGMAC_CHIME_FILE}")
    else:
        print("[TELEMETRY ASSISTANT] Middle mouse telemetry readout enabled (Zira).")

def play_dispatch_event(event, severity, context):
    clip = pick_local_clip(event, severity)

    if clip:
        print(f"[CB RADIO] Playing {event}/{severity}: {clip}")
        maybe_play_radio_fx("intro")
        play_audio_file(clip)
        maybe_play_radio_fx("outro")
        return

    # No local clip exists yet. Keep the truck moving with a light fallback.
    message = fallback_message(event, context)
    print(f"[CB RADIO] Missing clip for {event}/{severity}. Fallback: {message}")

    if ALLOW_LIVE_QWEN_ON_MISSING_CLIP:
        try:
            temp_target = os.path.join(TEMP_AUDIO_DIR, f"live_{event}_{severity}_{int(time.time())}.wav")
            generate_qwen_clip(message, temp_target)
            maybe_play_radio_fx("intro")
            play_audio_file(temp_target)
            maybe_play_radio_fx("outro")
            return
        except Exception as e:
            print(f"[VOICE] Live Qwen fallback failed, using Windows TTS: {e}")

    windows_tts_fallback(message)


def default_generation_context(event, severity):
    """
    Background generation usually does not need live telemetry.
    These sane defaults keep prompts from crashing when no current context exists.
    """
    return {
        "driver_name": DRIVER_NAME,
        "unit_number": UNIT_NUMBER,
        "fuel_percent": 8 if severity == "critical" else 18,
        "speed_kmh": 124 if severity == "high" else 114 if severity == "medium" else 108,
        "speed_limit": 100,
        "truck_wear_percent": 35 if severity in {"critical", "high"} else 12,
        "trailer_wear_percent": 18 if severity == "high" else 6,
        "engine_damage_percent": 20 if severity == "high" else 5,
        "brake_temperature": 260 if severity == "high" else 190,
    }


def generation_event_pool():
    # Only include events that are still useful over CB in the cleaned v6.2 runtime.
    # Technical/dashboard-only alerts can be added back later with matching audio folders.
    return {
        "JOB_STARTED": ["standard"],
        "ARRIVING_DESTINATION": ["standard"],
        "DELIVERY_SCREEN": ["standard"],
        "LOW_FUEL": ["low", "medium"],
        "CRITICAL_FUEL": ["critical"],
        "SPEEDING": ["low", "medium", "high"],
        "COLLISION": ["low", "medium", "high"],
        "TRAILER_DAMAGE": ["low", "medium", "high"],
        "MAJOR_DAMAGE": ["critical"],
        "DAMAGE": ["low", "medium", "high"],
        "REST_2H": ["standard"],
        "REST_1H": ["medium"],
        "REST_DUE": ["critical"],
        "PARK_BRAKE_MOVING": ["medium"],
    }


def choose_generation_target():
    pool = generation_event_pool()
    event = random.choice(list(pool.keys()))
    severity = random.choice(pool[event])
    slot = random.randint(1, CLIPS_PER_EVENT_SEVERITY)
    return event, severity, slot


def generated_clip_path(event, severity, slot):
    event = normalize_event_name(event)
    severity = normalize_severity_name(severity)
    folder = os.path.join(ACTIVE_AUDIO_DIR, event, severity)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{event.lower()}_{severity}_{slot:02d}{DEFAULT_GENERATED_EXTENSION}")


def generate_qwen_clip(message, target_path):
    """
    Generates one finished radio-filtered clip to target_path.
    Uses temp raw/radio files, then atomically replaces target_path.
    """
    ensure_voice_library_dirs()
    load_qwen_mick()

    target_path = os.path.abspath(target_path)
    temp_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    raw_temp = os.path.join(TEMP_AUDIO_DIR, f"qwen_raw_{temp_id}.wav")
    radio_temp = os.path.join(TEMP_AUDIO_DIR, f"qwen_radio_{temp_id}.wav")

    spoken_message = spoken_cleanup(message)

    with qwen_lock:
        wavs, sample_rate = qwen_model.generate_voice_clone(
            text=spoken_message,
            voice_clone_prompt=mick_voice_prompt,
            x_vector_only_mode=False,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            max_new_tokens=2048,
        )

        sf_module.write(raw_temp, wavs[0], sample_rate)

    apply_radio_filter_paths(raw_temp, radio_temp)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    os.replace(radio_temp, target_path)

    for leftover in [raw_temp, radio_temp]:
        try:
            if os.path.exists(leftover):
                os.remove(leftover)
        except Exception:
            pass


def update_manifest(event, severity, slot, message, clip_path):
    ensure_voice_library_dirs()
    manifest = {}

    if os.path.isfile(MANIFEST_FILE):
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    key = f"{normalize_event_name(event)}/{normalize_severity_name(severity)}/{slot:02d}"
    manifest[key] = {
        "event": normalize_event_name(event),
        "severity": normalize_severity_name(severity),
        "slot": slot,
        "message": message,
        "clip_path": clip_path,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    temp_manifest = MANIFEST_FILE + ".tmp"
    with open(temp_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    os.replace(temp_manifest, MANIFEST_FILE)


def game_is_calm_enough_for_generation(skip_count):
    if not REQUIRE_CALM_FOR_GENERATION:
        return True

    if skip_count >= MAX_GENERATION_SKIPS_BEFORE_FORCE:
        print("[GENERATOR] Force-running after repeated calm-check skips.")
        return True

    try:
        data = get_telemetry()
        context = get_context(data)
        if context.get("game_paused"):
            return True
        if context.get("speed_kmh", 0) < 3:
            return True
        return False
    except Exception:
        # If telemetry is offline, generation is safe because ATS probably is not driving.
        return True


def background_generator_loop():
    ensure_voice_library_dirs()
    print(f"[GENERATOR] Background refresher enabled. First check in {BACKGROUND_INITIAL_DELAY_SECONDS}s.")
    time.sleep(BACKGROUND_INITIAL_DELAY_SECONDS)

    skip_count = 0

    while True:
        wait_seconds = random.randint(REGEN_INTERVAL_SECONDS_MIN, REGEN_INTERVAL_SECONDS_MAX)
        time.sleep(wait_seconds)

        if not game_is_calm_enough_for_generation(skip_count):
            skip_count += 1
            print("[GENERATOR] Skipping refresh; truck is not calm enough.")
            continue

        skip_count = 0
        event, severity, slot = choose_generation_target()
        context = default_generation_context(event, severity)

        try:
            print(f"[GENERATOR] Refreshing {event}/{severity} slot {slot:02d}...")
            message = generate_ai_message(event, context)
            target = generated_clip_path(event, severity, slot)
            generate_qwen_clip(message, target)
            update_manifest(event, severity, slot, message, target)
            print(f"[GENERATOR] Updated {event}/{severity} slot {slot:02d}: {message}")
        except Exception as e:
            print(f"[GENERATOR] Refresh failed: {e}")


def start_background_generator():
    if not ENABLE_BACKGROUND_GENERATOR:
        print("[GENERATOR] Background refresher disabled.")
        return

    thread = threading.Thread(target=background_generator_loop, daemon=True)
    thread.start()



def pick_mick_mode_interval_seconds():
    if MICK_MODE_TEST_MODE:
        return random.randint(MICK_TEST_INTERVAL_MIN_SECONDS, MICK_TEST_INTERVAL_MAX_SECONDS)
    return random.randint(MICK_FINAL_INTERVAL_MIN_SECONDS, MICK_FINAL_INTERVAL_MAX_SECONDS)


def describe_time_of_day(game_hour):
    if game_hour is None:
        return "unknown"
    if 5 <= game_hour < 12:
        return "morning"
    if 12 <= game_hour < 17:
        return "arvo"
    if 17 <= game_hour < 21:
        return "evening"
    return "night"


def describe_job_progress(context):
    distance = context.get("estimated_distance", 0) or 0
    has_job = context.get("has_job_data", False)
    if not has_job:
        return "no active run"
    if distance > 25000:
        return "early in the run"
    if distance > 3000:
        return "midway through the run"
    if distance > 300:
        return "nearly wrapped up"
    return "right near the end"


def describe_fuel_state(context):
    fuel = context.get("fuel_percent", 100) or 100
    if fuel <= FUEL_CRITICAL_TRIGGER_PERCENT:
        return "nearly empty"
    if fuel <= FUEL_MEDIUM_TRIGGER_PERCENT:
        return "getting very low"
    if fuel <= FUEL_LOW_TRIGGER_PERCENT:
        return "getting low"
    return "good"


def describe_truck_health(context):
    truck_wear = context.get("truck_wear_percent", 0) or 0
    trailer_wear = context.get("trailer_wear_percent", 0) or 0
    engine_damage = context.get("engine_damage_percent", 0) or 0
    worst = max(truck_wear, trailer_wear, engine_damage)
    if worst >= 30:
        return "rough"
    if worst >= 15:
        return "a bit tired"
    if worst >= 5:
        return "slightly worn"
    return "good"


def describe_rest_state(context):
    rest = context.get("rest_minutes")
    if rest is None:
        return "unknown"
    if rest <= 0:
        return "rest due"
    if rest <= 60:
        return "getting tired"
    if rest <= 120:
        return "rest later"
    return "fresh enough"


DEPOT_TOPICS = [
    "coffee",
    "fans",
    "fax machine",
    "CRT monitor",
    "workshop boys",
    "yard",
    "old trucks",
    "Dad",
    "radio chatter",
    "paperwork pile",
    "lunchroom kettle",
    "hot office",
]


def describe_depot_topic():
    return random.choice(DEPOT_TOPICS)


def describe_depot_mood(context):
    hour = context.get("game_hour")
    if hour is not None and 11 <= hour < 17:
        return random.choice(["hot", "slow", "quiet"])
    if hour is not None and (hour >= 21 or hour < 5):
        return random.choice(["quiet", "slow"])
    return random.choice(["quiet", "busy", "hot", "slow"])


def describe_mick_location(context, mood=None):
    mood = mood or describe_depot_mood(context)
    if mood == "hot":
        return random.choice(["office", "lunchroom", "workshop"])
    return random.choice(["office", "workshop", "yard", "lunchroom"])


def mick_mode_context_summary(context):
    # Mick Mode intentionally ignores live truck/job telemetry.
    # Operational alerts handle fuel, damage, rest, speed, job, and delivery states.
    mood = describe_depot_mood(context)
    return {
        "time_of_day": describe_time_of_day(context.get("game_hour")),
        "depot_mood": mood,
        "mick_location": describe_mick_location(context, mood),
        "depot_topic": describe_depot_topic(),
    }

def build_mick_mode_prompt(context):
    summary = mick_mode_context_summary(context)
    return f"""
You are Mick from Queensland Roadtrains.

You are speaking to your younger brother Donny over a UHF radio.

This is NOT an operational alert.
This is NOT a dispatcher instruction.
This is NOT GPS guidance.
This is NOT telemetry reporting.

All operational alerts are handled separately by recorded radio clips.
Your only job is casual depot-side conversation between those alerts.

WHO YOU ARE
- Your name is Mick.
- You are about 58 years old.
- You and Donny run Queensland Roadtrains, a small family trucking company founded by your father in 1962.
- Dad is retired now, but his influence is still felt around the company.
- You are practical, relaxed, warm, dry-humoured, and quietly confident.
- You give Donny harmless stick, but you genuinely care about him.

WHERE YOU ARE
- You are physically at the Queensland Roadtrains depot.
- You may be in the office, workshop, yard, or lunchroom.
- You are not driving.
- You are not travelling.
- You are not at a servo, roadhouse, truck stop, stopover, service bay, or on the highway.
- You are not physically with Donny.
- Donny is the one on the road.

WHAT YOU KNOW
You may only base your message on these four broad context items:
- time_of_day
- depot_mood
- mick_location
- depot_topic

Current allowed context:
- Time of day: {summary['time_of_day']}
- Depot mood: {summary['depot_mood']}
- Mick location: {summary['mick_location']}
- Depot topic: {summary['depot_topic']}

You must not use or imply any other live game or truck information.
Do not mention fuel level, truck health, rest status, job progress, delivery status, route, destination, ETA, cargo, speed, damage, or Donny's location.
You may read SDK data only for timing, but your words must only pertain to the four allowed context items above.

STYLE
- One sentence only.
- 8 to 16 words preferred.
- Never longer than 20 words.
- Natural Australian English.
- Casual UHF radio tone.
- Do not end every sentence with mate.
- Rotate naturally between Donny, mate, brother, old son, champ, or no nickname.
- Use Aussie slang occasionally, not as a caricature.
- If unsure, comment on the depot, office, fans, coffee, yard, workshop, or Dad.
- Prefer observations over questions.
- Do not invent specific work being performed.
- Do not say Mick is doing maintenance, tinkering, fixing, repairing, or working on parts.

GOOD EXAMPLES
Fans are working overtime in the office again.
Coffee's strong enough to wake the dead this morning.
Quiet around the yard today, which usually worries me.
Workshop boys are arguin' again, must be a normal Tuesday.
Dad would've found a way to blame both of us.
Not much happening here, which is probably a good sign.
Office is quiet tonight, almost makes me suspicious.
Lunchroom kettle's doing more work than half the workshop today.

BAD EXAMPLES
Fuel's getting low.
Need to find a servo.
What's your ETA?
How far are you from the destination?
How's the truck holding up?
Still running sweet out there.
I'm cruising along.
Just got to the next stopover.
Passing through Mackay.

Generate one natural UHF radio check-in from Mick to Donny now.
""".strip()

def clean_mick_mode_message(message):
    if not message:
        return None

    message = message.strip().splitlines()[0].strip()
    message = message.strip('"').strip("'").strip()

    unwanted_prefixes = ["Mick:", "Radio:", "UHF:", "CB:", "Dispatch:", "Queensland Roadtrains:"]
    for prefix in unwanted_prefixes:
        if message.lower().startswith(prefix.lower()):
            message = message[len(prefix):].strip()

    if not message:
        return None

    lower = message.lower()
    forbidden = [
        "telemetry", "sensor", "system alert", "warning detected", "gps", "coordinates",
        "customer", "client", "paperwork", "admin", "email", "phone", "called", "invoice",
        "flat tyre", "flat tire", "tyre's gone", "tire's gone", "repair shop",
        "brisbane", "sydney", "melbourne", "perth", "adelaide",
    ]
    if any(bad in lower for bad in forbidden):
        return None

    for bad in MICK_MODE_REJECT_WORDS:
        if bad.lower() in lower:
            print(f"[MICK MODE] Rejected line due to word: {bad}")
            return None

    words = message.split()
    if len(words) > 20:
        message = " ".join(words[:20]).rstrip(",.;:") + "."

    return message


def generate_mick_mode_message(context):
    prompt = build_mick_mode_prompt(context)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": MICK_MODE_TEMPERATURE,
            "top_p": MICK_MODE_TOP_P,
            "num_predict": MICK_MODE_NUM_PREDICT,
        },
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=MICK_MODE_OLLAMA_TIMEOUT_SECONDS)
    response.raise_for_status()
    result = response.json()
    return clean_mick_mode_message(result.get("response", ""))


def append_mick_mode_log(message, context):
    ensure_voice_library_dirs()
    summary = mick_mode_context_summary(context)
    timestamp = datetime.now().isoformat(timespec="seconds")
    os.makedirs(os.path.dirname(MICK_MODE_LOG_FILE), exist_ok=True)
    with open(MICK_MODE_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
        f.write(f"    context={json.dumps(summary, ensure_ascii=False)}\n")


def mick_mode_is_active_context(context):
    if MICK_REQUIRE_UNPAUSED and context.get("game_paused"):
        return False
    if MICK_REQUIRE_MOVING and (context.get("speed_kmh", 0) or 0) < MICK_MOVING_SPEED_KMH:
        return False
    if MICK_REQUIRE_JOB_ACTIVE and not context.get("has_job_data"):
        return False
    return True



def list_mick_mode_clips():
    if not os.path.isdir(MICK_MODE_AUDIO_DIR):
        return []

    clips = []
    for ext in SUPPORTED_AUDIO_EXTENSIONS:
        clips.extend(glob.glob(os.path.join(MICK_MODE_AUDIO_DIR, "**", f"*{ext}"), recursive=True))

    return [path for path in clips if os.path.isfile(path)]


def pick_mick_mode_ambient_clip():
    global recent_mick_mode_clips

    clips = list_mick_mode_clips()
    if not clips:
        return None

    available = [clip for clip in clips if clip not in recent_mick_mode_clips]
    if not available:
        available = clips
        recent_mick_mode_clips = []

    clip = random.choice(available)
    recent_mick_mode_clips.append(clip)
    if len(recent_mick_mode_clips) > MICK_MODE_RECENT_CLIP_MEMORY:
        recent_mick_mode_clips = recent_mick_mode_clips[-MICK_MODE_RECENT_CLIP_MEMORY:]

    return clip


def append_mick_mode_clip_log(clip_path, context):
    ensure_voice_library_dirs()
    timestamp = datetime.now().isoformat(timespec="seconds")
    try:
        rel = os.path.relpath(clip_path, MICK_MODE_AUDIO_DIR)
    except Exception:
        rel = os.path.basename(clip_path)

    os.makedirs(os.path.dirname(MICK_MODE_LOG_FILE), exist_ok=True)
    with open(MICK_MODE_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] AMBIENT_CLIP {rel}\n")


def mick_mode_loop():
    global last_operational_alert_real_time

    if not MICK_MODE_ENABLED:
        print("[MICK MODE] Disabled.")
        return

    target_seconds = pick_mick_mode_interval_seconds()
    active_seconds = 0.0
    last_tick = time.time()

    mode_label = "TEST" if MICK_MODE_TEST_MODE else "FINAL"
    print(f"[MICK MODE] Ambient library check-ins enabled ({mode_label}). First target: {target_seconds}s active driving.")
    print(f"[MICK MODE] Ambient folder: {MICK_MODE_AUDIO_DIR}")

    while True:
        time.sleep(5)
        now = time.time()
        delta = now - last_tick
        last_tick = now

        try:
            data = get_telemetry()
            context = get_context(data)
        except Exception as e:
            print(f"[MICK MODE] Waiting for telemetry: {e}")
            continue

        if not mick_mode_is_active_context(context):
            # Pause the timer. Do not reset it.
            continue

        active_seconds += delta

        if active_seconds < target_seconds:
            continue

        if now - last_operational_alert_real_time < MICK_AFTER_ALERT_COOLDOWN_SECONDS:
            # Operational radio had priority recently. Hold progress and try again next poll.
            continue

        clip = pick_mick_mode_ambient_clip()
        if not clip:
            print(f"[MICK MODE] No ambient clips found under: {MICK_MODE_AUDIO_DIR}")
        else:
            try:
                print(f"[MICK MODE] Playing ambient Mick clip: {clip}")
                append_mick_mode_clip_log(clip, context)
                maybe_play_radio_fx("intro")
                play_audio_file(clip)
                maybe_play_radio_fx("outro")
            except Exception as e:
                print(f"[MICK MODE] Ambient clip playback failed: {e}")

        active_seconds = 0.0
        target_seconds = pick_mick_mode_interval_seconds()
        print(f"[MICK MODE] Next target: {target_seconds}s active driving.")

def start_mick_mode():
    if not MICK_MODE_ENABLED:
        print("[MICK MODE] Text-only check-ins disabled.")
        return

    thread = threading.Thread(target=mick_mode_loop, daemon=True)
    thread.start()


def print_startup_banner():
    print("Queensland Roadtrains CB Dispatcher is running...")
    print("Waiting for telemetry events...")
    print("Press CTRL + C to stop.")
    print("---------------------------------------------")
    print("[CB RADIO] Queensland Roadtrains radio network online.")
    print("[CB RADIO] Driver profile loaded: Donny")
    print("[VOICE] Runtime backend: local dynamic clip library")
    print("[VOICE] Missing clip fallback: Windows TTS")
    print(f"[VOICE] Cache folder: {QR_CACHE_DIR}")
    print(f"[MICK MODE] Ambient library check-ins: {'enabled' if MICK_MODE_ENABLED else 'disabled'}")
    if MICK_MODE_ENABLED:
        print(f"[MICK MODE] Log file: {MICK_MODE_LOG_FILE}")
    print(f"[TELEMETRY ASSISTANT] Middle mouse readout: {'enabled' if TELEMETRY_ASSISTANT_ENABLED else 'disabled'}")


def main():
    global last_operational_alert_real_time
    ensure_voice_library_dirs()
    print_startup_banner()
    start_background_generator()
    start_mick_mode()
    start_telemetry_assistant()

    while True:
        try:
            data = get_telemetry()
            event, context = check_events(data)

            if event:
                event = normalize_event_name(event)
                if event in DISABLED_RUNTIME_EVENTS:
                    if DEBUG_IGNORED_EVENTS:
                        print(f"[CB RADIO] Ignored disabled event: {event}")
                    continue

                severity = determine_severity(event, context)
                print(f"[CB RADIO] Event detected: {event}/{severity}")
                play_dispatch_event(event, severity, context)
                last_operational_alert_real_time = time.time()

        except KeyboardInterrupt:
            print("\nDispatcher stopped.")
            break

        except Exception as e:
            print("Waiting for telemetry:", e)

        time.sleep(5)


if __name__ == "__main__":
    main()
