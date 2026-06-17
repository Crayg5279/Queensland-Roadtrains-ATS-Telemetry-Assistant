import json
import os
import queue
import threading
import time
import winreg
from dataclasses import dataclass, asdict
from itertools import count
from pathlib import Path

try:
    import keyboard
except ImportError:
    keyboard = None

try:
    import pythoncom
    import win32com.client
except ImportError:
    pythoncom = None
    win32com = None


# ============================================================
# BIG MAC TELEMETRY TTS CONFIG
# ============================================================

QWEN_DIR = Path(__file__).resolve().parent
TELEMETRY_JSON = str(QWEN_DIR / "qr-cache" / "telemetry_state.json")

# For now, David is confirmed working on your system.
# Later, try values like:
#   "Zira"
#   "Catherine"
#   "Australia"
#   ""
#
# Blank value = auto-select Australian voice if SAPI can see one,
# otherwise use Windows default.
PREFERRED_VOICE_CONTAINS = "Zira"

TTS_RATE = 0
TTS_VOLUME = 100

PRINT_ONECORE_VOICES = True
PRINT_SAPI_VOICES = True


# ============================================================
# TELEMETRY STATE
# ============================================================

@dataclass
class TelemetryState:
    fuel_percent: float = 24.0
    route_distance_km: float = 2.0
    route_time_min: float = 5.0
    speed_kmh: float = 82.0
    speed_limit_kmh: float = 100.0
    truck_damage_percent: float = 8.0
    trailer_damage_percent: float = 2.0
    destination: str = "the destination"
    truck_name: str = "Big Mac"
    has_active_job: bool = True


# ============================================================
# VOICE DEBUG
# ============================================================

def list_onecore_voices():
    """
    Lists newer Windows OneCore voices.

    These may appear in Windows Settings under language packs,
    but they usually do NOT appear in old SAPI.SpVoice.
    """
    base_paths = [
        r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens",
        r"SOFTWARE\WOW6432Node\Microsoft\Speech_OneCore\Voices\Tokens",
    ]

    print("[BIG MAC] Checking OneCore Windows voices...")

    found_any = False

    for base_path in base_paths:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path) as root:
                index = 0

                while True:
                    try:
                        token_name = winreg.EnumKey(root, index)

                        with winreg.OpenKey(root, token_name) as token:
                            try:
                                voice_name = winreg.QueryValueEx(token, "")[0]
                            except Exception:
                                voice_name = token_name

                            print(f"  - OneCore: {voice_name}")
                            found_any = True

                        index += 1

                    except OSError:
                        break

        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"[BIG MAC] Could not read OneCore voices from {base_path}: {e}")

    if not found_any:
        print("  - No OneCore voices found or accessible.")


# ============================================================
# WINDOWS SAPI TTS
# ============================================================

class WindowsTTS:
    def __init__(self):
        if win32com is None or pythoncom is None:
            raise RuntimeError("pywin32 is not installed. Run: python -m pip install pywin32")

        self.queue = queue.PriorityQueue()
        self.running = True
        self.ready = threading.Event()
        self.counter = count()

        self.worker = threading.Thread(target=self._speak_worker, daemon=True)
        self.worker.start()

        self.ready.wait(timeout=5)

    def _select_voice(self, voice):
        """
        Selects a Windows SAPI voice.

        Priority:
        1. PREFERRED_VOICE_CONTAINS, if set
        2. Australian-looking voice, if SAPI can see one
        3. Default Windows SAPI voice
        """
        try:
            voices = voice.GetVoices()

            preferred = None
            australian = None

            if PRINT_SAPI_VOICES:
                print("[BIG MAC] Installed Windows SAPI voices:")

            for i in range(voices.Count):
                v = voices.Item(i)
                desc = v.GetDescription()
                desc_lower = desc.lower()

                if PRINT_SAPI_VOICES:
                    print(f"  - {desc}")

                if PREFERRED_VOICE_CONTAINS:
                    if PREFERRED_VOICE_CONTAINS.lower() in desc_lower:
                        preferred = v
                        break

                if (
                    "australia" in desc_lower
                    or "australian" in desc_lower
                    or "en-au" in desc_lower
                    or "catherine" in desc_lower
                    or "hayley" in desc_lower
                    or "james" in desc_lower
                ):
                    australian = v

            if preferred:
                voice.Voice = preferred
                print(f"[BIG MAC] Selected preferred Windows TTS voice: {preferred.GetDescription()}")
                return

            if australian:
                voice.Voice = australian
                print(f"[BIG MAC] Selected Australian Windows TTS voice: {australian.GetDescription()}")
                return

            print("[BIG MAC] No preferred/Australian SAPI voice found. Using default voice.")

        except Exception as e:
            print(f"[BIG MAC] Voice selection failed. Using default voice. Error: {e}")

    def speak(self, text: str, priority: int = 5):
        """
        Lower priority number speaks first.

        priority 1 = urgent
        priority 4 = telemetry response
        priority 7 = casual chatter
        """
        if not text or not self.running:
            return

        self.queue.put((priority, time.time(), next(self.counter), text))

    def _speak_worker(self):
        """
        SAPI/COM must be initialized inside the thread that uses it.
        """
        pythoncom.CoInitialize()

        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            voice.Rate = TTS_RATE
            voice.Volume = TTS_VOLUME

            self._select_voice(voice)
            self.ready.set()

            while self.running:
                try:
                    priority, created, seq, text = self.queue.get(timeout=0.25)
                except queue.Empty:
                    continue

                if text == "__STOP__":
                    self.queue.task_done()
                    break

                try:
                    print(f"[BIG MAC TTS] {text}")
                    voice.Speak(text)
                except Exception as e:
                    print(f"[BIG MAC] TTS failed: {e}")

                self.queue.task_done()

        except Exception as e:
            self.ready.set()
            print(f"[BIG MAC] TTS engine failed to initialize: {e}")

        finally:
            pythoncom.CoUninitialize()

    def stop(self):
        self.running = False
        self.queue.put((0, time.time(), next(self.counter), "__STOP__"))


# ============================================================
# TELEMETRY FILE READING
# ============================================================

def write_demo_json():
    """
    Creates a demo telemetry JSON file so the script can be tested immediately.

    Later, your live ATS telemetry script should overwrite this file.
    """
    os.makedirs(os.path.dirname(TELEMETRY_JSON), exist_ok=True)

    if os.path.exists(TELEMETRY_JSON):
        return

    demo = asdict(TelemetryState())

    with open(TELEMETRY_JSON, "w", encoding="utf-8") as f:
        json.dump(demo, f, indent=2)

    print(f"[BIG MAC] Demo telemetry file created: {TELEMETRY_JSON}")


def load_telemetry_state() -> TelemetryState:
    """
    Reads telemetry_state.json.

    The key names are intentionally flexible so we can map your existing
    ATS telemetry output without rewriting everything.
    """
    state = TelemetryState()

    if not os.path.exists(TELEMETRY_JSON):
        return state

    try:
        with open(TELEMETRY_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        state.fuel_percent = float(
            data.get("fuel_percent",
            data.get("fuelPercent",
            data.get("fuel", state.fuel_percent)))
        )

        state.route_distance_km = float(
            data.get("route_distance_km",
            data.get("routeDistanceKm",
            data.get("estimated_distance_km",
            data.get("estimated_distance", state.route_distance_km))))
        )

        state.route_time_min = float(
            data.get("route_time_min",
            data.get("routeTimeMin",
            data.get("estimated_time_min",
            data.get("eta_min", state.route_time_min))))
        )

        state.speed_kmh = float(
            data.get("speed_kmh",
            data.get("speedKmh",
            data.get("speed_kph",
            data.get("speed", state.speed_kmh))))
        )

        state.speed_limit_kmh = float(
            data.get("speed_limit_kmh",
            data.get("speedLimitKmh",
            data.get("speed_limit_kph",
            data.get("speed_limit", state.speed_limit_kmh))))
        )

        state.truck_damage_percent = float(
            data.get("truck_damage_percent",
            data.get("truckDamagePercent",
            data.get("truck_damage",
            data.get("damage_truck", state.truck_damage_percent))))
        )

        state.trailer_damage_percent = float(
            data.get("trailer_damage_percent",
            data.get("trailerDamagePercent",
            data.get("trailer_damage",
            data.get("damage_trailer", state.trailer_damage_percent))))
        )

        state.destination = str(
            data.get("destination",
            data.get("destination_name", state.destination))
        )

        state.truck_name = str(
            data.get("truck_name",
            data.get("truckName", state.truck_name))
        )

        state.has_active_job = bool(
            data.get("has_active_job",
            data.get("hasActiveJob", state.has_active_job))
        )

    except Exception as e:
        print(f"[BIG MAC] Failed to read telemetry JSON. Using demo/default values. Error: {e}")

    return state


# ============================================================
# TELEMETRY REPLIES
# ============================================================

def reply_fuel(state: TelemetryState) -> str:
    fuel = round(state.fuel_percent)

    if fuel <= 5:
        return f"Fuel level is critical at {fuel} percent."
    if fuel <= 15:
        return f"Fuel level is low at {fuel} percent."

    return f"Fuel level is at {fuel} percent."


def reply_distance(state: TelemetryState) -> str:
    if not state.has_active_job:
        return "There is no active job right now."

    km = state.route_distance_km
    mins = round(state.route_time_min)

    if km <= 0:
        return "Route distance is not available right now."

    if km < 1:
        return f"You are less than one kilometre from {state.destination}. Estimated arrival is {mins} minutes."

    return f"You are {km:.1f} kilometres from {state.destination}. Estimated arrival is {mins} minutes."


def reply_damage(state: TelemetryState) -> str:
    truck = round(state.truck_damage_percent)
    trailer = round(state.trailer_damage_percent)

    if truck >= 30:
        return f"Truck damage is critical at {truck} percent. Trailer damage is at {trailer} percent."

    if truck >= 15:
        return f"Truck damage is getting high at {truck} percent. Trailer damage is at {trailer} percent."

    return f"Truck damage is at {truck} percent. Trailer damage is at {trailer} percent."


def reply_speed(state: TelemetryState) -> str:
    speed = round(state.speed_kmh)
    limit = round(state.speed_limit_kmh)

    if limit <= 0:
        return f"Current speed is {speed} kilometres per hour. I do not have the speed limit available."

    return f"Current speed is {speed} kilometres per hour. The speed limit is {limit}."


def reply_status(state: TelemetryState) -> str:
    fuel = round(state.fuel_percent)
    damage = round(state.truck_damage_percent)

    if not state.has_active_job:
        return (
            f"{state.truck_name} is not currently on an active job. "
            f"Fuel level is {fuel} percent. "
            f"Truck damage is {damage} percent."
        )

    return (
        f"{state.truck_name} is heading to {state.destination}. "
        f"Fuel is at {fuel} percent. "
        f"Distance remaining is {state.route_distance_km:.1f} kilometres. "
        f"Truck damage is {damage} percent."
    )


# ============================================================
# COMMAND HANDLING
# ============================================================

def handle_command(command: str, tts: WindowsTTS):
    state = load_telemetry_state()

    if command == "fuel":
        tts.speak(reply_fuel(state), priority=4)

    elif command == "distance":
        tts.speak(reply_distance(state), priority=4)

    elif command == "damage":
        tts.speak(reply_damage(state), priority=4)

    elif command == "speed":
        tts.speak(reply_speed(state), priority=4)

    elif command == "status":
        tts.speak(reply_status(state), priority=4)

    else:
        tts.speak("I do not have that reading available right now.", priority=6)


def print_hotkeys():
    print("")
    print("[BIG MAC] Hotkeys:")
    print("  F8  = Fuel level")
    print("  F9  = Distance and ETA")
    print("  F10 = Damage")
    print("  F11 = Speed and speed limit")
    print("  F12 = Overall status")
    print("  ESC = Exit")
    print("")


def console_fallback(tts: WindowsTTS):
    """
    Fallback if the keyboard module is missing or global hotkeys are blocked.
    """
    print("[BIG MAC] Console command fallback active.")
    print("Type: fuel, distance, damage, speed, status, or exit")

    while True:
        cmd = input("> ").strip().lower()

        if cmd in ("exit", "quit", "q"):
            break

        handle_command(cmd, tts)


# ============================================================
# MAIN
# ============================================================

def main():
    print("[BIG MAC] Telemetry TTS v0.2 starting...")

    if PRINT_ONECORE_VOICES:
        list_onecore_voices()

    write_demo_json()

    tts = WindowsTTS()
    tts.speak("Big Mac telemetry voice is online.", priority=3)

    print_hotkeys()

    if keyboard is None:
        print("[BIG MAC] keyboard package not installed. Run: python -m pip install keyboard")
        console_fallback(tts)
        tts.speak("Big Mac telemetry voice shutting down.", priority=3)
        time.sleep(1)
        tts.stop()
        return

    keyboard.add_hotkey("F8", lambda: handle_command("fuel", tts))
    keyboard.add_hotkey("F9", lambda: handle_command("distance", tts))
    keyboard.add_hotkey("F10", lambda: handle_command("damage", tts))
    keyboard.add_hotkey("F11", lambda: handle_command("speed", tts))
    keyboard.add_hotkey("F12", lambda: handle_command("status", tts))

    try:
        keyboard.wait("esc")

    except KeyboardInterrupt:
        pass

    finally:
        tts.speak("Big Mac telemetry voice shutting down.", priority=3)
        time.sleep(1)
        tts.stop()


if __name__ == "__main__":
    main()
