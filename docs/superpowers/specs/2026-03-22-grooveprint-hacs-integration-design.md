# Grooveprint HACS Integration Design

## Overview

A Home Assistant Community Store (HACS) custom integration that exposes a Grooveprint vinyl fingerprinting server and its companion listening app to Home Assistant for automation.

The integration connects to two services:
- **Grooveprint server** (FastAPI, default port 8457) — provides now-playing state and track metadata via SSE
- **Listening app** (iOS/Android, default port 8458) — controls audio capture start/stop

## Configuration

Config flow with two required inputs:

| Field | Label | Default | Validation |
|-------|-------|---------|------------|
| `server_url` | Server URL | `http://localhost:8457` | `GET /health` returns 200 |
| `listener_url` | Listening app URL | `http://localhost:8458` | `GET /status` returns 200 |

Unique ID derived from server URL (trailing slash stripped) to prevent duplicates. If a config entry with the same unique ID already exists, the flow aborts with an "already configured" message.

**Known limitation:** If the server's IP/hostname changes, the user must delete and re-add the integration. An options flow for reconfiguring URLs is out of scope for v1.

## File Structure

```
custom_components/grooveprint/
├── __init__.py          # Setup, coordinator creation, platform forwarding
├── manifest.json        # HACS metadata, domain "grooveprint"
├── config_flow.py       # Config UI: server URL + listening app URL
├── coordinator.py       # SSE connection + listening app polling
├── media_player.py      # Now-playing entity with track info & cover art
├── sensor.py            # Raw server status entity
├── switch.py            # Start/stop listening toggle
├── const.py             # Domain, defaults, platform list
├── strings.json         # UI strings for config flow
└── translations/
    └── en.json          # English translations
```

Root file: `hacs.json` for HACS marketplace metadata.

## Coordinator

`GrooveprintCoordinator` extends `DataUpdateCoordinator` and manages two connections.

### Update Mechanism

- `update_interval` is set to `None` (SSE is push-based, no periodic polling by the coordinator itself).
- When SSE events arrive, the coordinator calls `async_set_updated_data()` to push new state to all entities.
- Listening app polling runs as a separate `asyncio.Task` alongside the SSE task, with its own 5-second loop.
- `_async_update_data()` simply returns the current cached state (used only for initial refresh).

### Lifecycle

- `async_setup_entry` in `__init__.py` creates the coordinator, calls `coordinator.async_start()` (which spawns the SSE and polling background tasks), then calls `async_config_entry_first_refresh()`.
- `async_unload_entry` calls `coordinator.async_stop()` (which cancels both background tasks and closes the aiohttp session).

### SSE Connection (Grooveprint server)

- Connects to `GET /now-playing/stream` using `aiohttp`
- Parses SSE `data:` lines as JSON, calls `async_set_updated_data()` on each event
- On startup: initial fetch from `GET /now-playing` to populate state before SSE connects
- On connection drop: auto-reconnect after 5 seconds
- Heartbeat comment lines (`:` prefix) are ignored for data purposes but used for connection health monitoring. If no data or heartbeat arrives within 60 seconds, the connection is treated as dead and reconnection is triggered.

### Listening App Polling

- Polls `GET /status` on the listening app every 5 seconds in a separate `asyncio.Task`
- Stores boolean `is_listening` in coordinator data
- Connection failure marks switch as unavailable without affecting server entities

### Data Shape

```python
{
    "status": "idle" | "listening" | "playing",
    "track": "Song Name",         # None when not playing
    "artist": "Artist Name",      # None when not playing
    "album": "Album Name",        # None when not playing
    "album_id": 123,              # None when not playing
    "cover_url": "/albums/123/cover",  # None when not playing
    "year": 2024,                 # None when not playing
    "duration_s": 240.0,          # None when not playing
    "elapsed_s": 45.2,            # None when not playing
    "score": 25,                  # Match strength (min 15 = stable). None when not playing
    "confidence": 3.5,            # Ratio of best to second-best match. Higher = more certain. None when not playing
    "side": "A",                  # Vinyl side. None when not playing
    "position": 2,                # Track position on side. None when not playing
    "track_number": 3,            # None when not playing
    "discogs_url": "https://...", # None when not playing
    "is_listening": True,         # From listening app. None if app unreachable
    "listener_available": True    # False if listening app is unreachable
}
```

Track-related fields are `None` when server status is not `playing`. This is the standard HA convention — entities return `None` for unavailable attributes.

## Entities

All entities are grouped under one device called "Grooveprint".

### media_player.grooveprint

Read-only media player showing the currently playing track.

**State mapping:**
| Server status | MediaPlayerState |
|---------------|-----------------|
| `playing` | `PLAYING` |
| `listening` | `IDLE` |
| `idle` | `STANDBY` |
| server unreachable | `unavailable` |

**Standard attributes:**
- `media_title` — track name
- `media_artist` — artist
- `media_album_name` — album
- `media_duration` — duration in seconds
- `media_position` — elapsed seconds
- `media_position_updated_at` — set to `utc_now()` on each SSE update with position data (required for HA UI to interpolate playback progress between updates)
- `media_content_type` — `music`
- `entity_picture` — constructed from `cover_url` field: `{server_url}{cover_url}`

**Extra state attributes** (for automations):
- `side`, `position`, `track_number`, `year`, `score`, `confidence`, `discogs_url`

**Supported features:** None (read-only).

### sensor.grooveprint_status

Raw server status as an enum sensor.

**State:** `idle`, `listening`, or `playing`
**Device class:** `enum`
**Icon by state:**
- `idle` → `mdi:sleep`
- `listening` → `mdi:ear-hearing`
- `playing` → `mdi:music-circle`

### switch.grooveprint_listening

Controls the listening app's audio capture.

**State:** On when listening app reports active, off otherwise.
**Turn on:** `POST {listener_url}/start`
**Turn off:** `POST {listener_url}/stop`
**Icon:** `mdi:microphone` (on) / `mdi:microphone-off` (off)

## Error Handling

### SSE Connection Failures
- Connection refused or stream drops → mark media_player and sensor as `unavailable`
- Retry every 5 seconds with logging
- Preserve last known state briefly during reconnection

### Listening App Failures
- Connection refused or timeout → mark switch as `unavailable`
- Continue polling; switch becomes available again on next successful poll
- Does not affect server entities

### Independence
Server and listening app failures are isolated. One going down does not affect the other's entities.

### Config Flow Validation
- Server URL unreachable → error: "Cannot connect to Grooveprint server"
- Listening app URL unreachable → error: "Cannot connect to listening app"
- Duplicate server URL → abort: "Already configured"
- Both must validate before config entry is created

### HA Restart
Coordinator reconnects SSE and resumes polling on startup. No persistent state needed.

## Dependencies

- `aiohttp` — async HTTP client for SSE and REST calls (included with Home Assistant)
- Home Assistant >= 2024.1.0

## HACS Configuration

`hacs.json`:
```json
{
  "name": "Grooveprint",
  "homeassistant": "2024.1.0",
  "render_readme": true
}
```

`manifest.json`:
```json
{
  "domain": "grooveprint",
  "name": "Grooveprint",
  "codeowners": [],
  "config_flow": true,
  "documentation": "https://github.com/leolobato/grooveprint-hass",
  "integration_type": "hub",
  "iot_class": "local_push",
  "issue_tracker": "https://github.com/leolobato/grooveprint-hass/issues",
  "requirements": [],
  "version": "1.0.0"
}
```
