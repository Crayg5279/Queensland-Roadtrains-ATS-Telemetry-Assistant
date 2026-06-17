# Changelog

## v6.8c - 2026-06-17

### Added
- Added Big Mac telemetry replies for game time.
- Added fuel litre and fuel range responses.
- Added air pressure responses.
- Added coolant temperature responses.

### Release Files
- `queensland_roadtrains_dispatcher_v6_8c_bigmac_telemetry_expansion.py`
- `queensland_roadtrains_dispatcher_v6_8b_bigmac_rest_weight_deadline.py`
- `queensland_roadtrains_dispatcher_v6_8a_bigmac_expansion_pack.py`
- `queensland_roadtrains_dispatcher_v6_8a_bigmac_chime.py`
- `Qwen3-TTS/qr-cache/bigmac_fx/bigmac_chime.wav`
- `Previous Versions/`

### Notes
- `v6.8c` should be uploaded ahead of `v6.8b` and `v6.8a` as the newest dispatcher build in this set.
- The `Previous Versions/` folder is included as the historical dispatcher archive, covering earlier builds from the original dispatcher through `v6.8`.

## Previous Versions Included

These archived dispatcher builds are included under `Previous Versions/`, listed newest to oldest:

- `v6.8` - `queensland_roadtrains_dispatcher_v6_8_bigmac_dest_cargo_deadline.py`
- `v6.7` - `queensland_roadtrains_dispatcher_v6_7_middle_mouse_ptt_bigmac.py`
- `v6.6` - `queensland_roadtrains_dispatcher_v6_6_middle_mouse_telemetry.py`
- `v6.4` - `queensland_roadtrains_dispatcher_v6_4_mick_qwen_tts.py`
- `v6.3` - `queensland_roadtrains_dispatcher_v6_3_audio_test.py`
- `v6.2a` - `queensland_roadtrains_dispatcher_v6_2a_mick_mode_tts_test_reject_words.py`
- `v6.2a` - `queensland_roadtrains_dispatcher_v6_2a_mick_mode_tts_test.py`
- `v6.2a` - `queensland_roadtrains_dispatcher_v6_2a_mick_mode_text_test_FIXED.py`
- `v6.2a` - `queensland_roadtrains_dispatcher_v6_2a_mick_mode_text_test.py`
- `v6.2a` - `queensland_roadtrains_dispatcher_v6_2a_mick_mode_ISOLATED_CONTEXT.py`
- `v6.2a` - `queensland_roadtrains_dispatcher_v6_2a_mick_mode_DEBUG_CONTEXT.py`
- `v6.2` - `queensland_roadtrains_dispatcher_v6_2_final.py`
- `v6.2` - `queensland_roadtrains_dispatcher_v6_2_dynamic_voice_library.py`
- `v6.1` - `queensland_roadtrains_dispatcher_v6_1_dynamic_voice_library.py`
- `v6.1` - `queensland_roadtrains_dispatcher_v6_1_clean_dynamic_voice_library.py`
- `v6` - `queensland_roadtrains_dispatcher_v6_dynamic_voice_library.py`
- `v5.1` - `queensland_roadtrains_dispatcher_v5_1_low_latency_qwen.py`
- `v5` - `queensland_roadtrains_dispatcher_v5_qwen_mick.py`
- `v4.4.3b` - `queensland_roadtrains_dispatcher_v4_4_3b_donny_mick.py`
- `v4.4.3a` - `queensland_roadtrains_dispatcher_v4_4_3a_ai_event_guard.py`
- `v4.4.3` - `queensland_roadtrains_dispatcher_v4_4_3_bugfix.py`
- `v4.4.2` - `queensland_roadtrains_dispatcher_v4_4_2_clean_connectors.py`
- `v4.4` - `queensland_roadtrains_dispatcher_v4_4_piper_alan.py`
- `v4.3` - `queensland_roadtrains_dispatcher_v4_3_departments.py`
- `v4.2` - `queensland_roadtrains_dispatcher_v4_2_delivery_fix.py`
- `v4.1` - `queensland_roadtrains_dispatcher_v4_1_damage_fines_ai.py`
- `v4` - `queensland_roadtrains_dispatcher_v4_ai.py`
- `v3.2` - `queensland_roadtrains_dispatcher_v3_2_generic.py`
- `v3.1` - `queensland_roadtrains_dispatcher_v3_1_fines.py`
- `v3` - `queensland_roadtrains_dispatcher_v3_rest.py`
- `v2` - `queensland_roadtrains_dispatcher_v2.py`
- `MickMode 2.0` - `queensland_roadtrains_dispatcher_MickMode_2_0_isolated.py`
- `original` - `queensland_roadtrains_dispatcher.py`

## v6.8b - 2026-06-17

### Added
- Added Big Mac rest-time replies.
- Added trailer-weight replies.
- Improved deadline replies.

### Release Files
- `queensland_roadtrains_dispatcher_v6_8b_bigmac_rest_weight_deadline.py`
- `queensland_roadtrains_dispatcher_v6_8a_bigmac_expansion_pack.py`
- `queensland_roadtrains_dispatcher_v6_8a_bigmac_chime.py`
- `Qwen3-TTS/qr-cache/bigmac_fx/bigmac_chime.wav`

### Notes
- `v6.8b` should be uploaded ahead of `v6.8a`, but behind `v6.8c`.
- This release builds on `v6.8a`, which added the Big Mac activation chime.

## v6.8a - 2026-06-17

### Added
- Added the Big Mac activation chime for middle-mouse push-to-talk startup.
- Added `BIGMAC_CHIME_FILE` and `BIGMAC_PLAY_ACTIVATION_CHIME` settings so the chime can be found and toggled.
- Added `play_bigmac_chime()` to play the local in-cab chime when the telemetry assistant opens.
- Added startup logging for the configured Big Mac activation chime path.

### Release Files
- `queensland_roadtrains_dispatcher_v6_8a_bigmac_expansion_pack.py`
- `queensland_roadtrains_dispatcher_v6_8a_bigmac_chime.py`
- `Qwen3-TTS/qr-cache/bigmac_fx/bigmac_chime.wav`
- `Previous Versions/`

### Notes
- The two `v6_8a` dispatcher Python files are currently identical copies.
- This release builds on `v6.8`, which added Big Mac destination, cargo, and deadline telemetry responses.
- The `Previous Versions/` folder is included as the historical dispatcher archive, covering earlier builds from the original dispatcher through `v6.8`.
