# Grooveprint for Home Assistant

A [HACS](https://hacs.xyz) custom integration that connects your [Grooveprint](https://github.com/leolobato/grooveprint) vinyl fingerprinting server to Home Assistant.

## Features

- **Media Player** — shows the currently playing track with artist, album, cover art, and playback position
- **Status Sensor** — exposes the server state (`idle`, `listening`, `playing`) for use in automations
- **Listening Switch** — start and stop audio capture on the companion listening app

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations** and click the three-dot menu
3. Select **Custom repositories** and add this repository URL as an **Integration**
4. Search for "Grooveprint" and install it
5. Restart Home Assistant

### Manual

Copy the `custom_components/grooveprint` directory into your Home Assistant `config/custom_components/` directory and restart.

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **Grooveprint**
3. Enter your **Server URL** (e.g., `http://192.168.1.100:8457`)
4. Enter your **Listening app URL** (e.g., `http://192.168.1.101:8458`)

Both endpoints are validated during setup.

## Entities

All entities are grouped under a single **Grooveprint** device.

| Entity | Type | Description |
|--------|------|-------------|
| `media_player.grooveprint` | Media Player | Current track info, cover art, playback position |
| `sensor.grooveprint_status` | Sensor | Server status: `idle`, `listening`, or `playing` |
| `switch.grooveprint_listening` | Switch | Toggle audio capture on the listening app |

### Extra attributes (media player)

Available for automations via `state_attr()`:

- `side` — vinyl side (A/B)
- `position` — track position on side
- `track_number` — track number
- `year` — release year
- `score` — match strength
- `confidence` — match confidence ratio
- `discogs_url` — Discogs release URL

## Automation examples

```yaml
# Notify when a new track starts playing
automation:
  - alias: "Grooveprint now playing"
    trigger:
      - platform: state
        entity_id: media_player.grooveprint
        to: "playing"
    action:
      - service: notify.mobile_app
        data:
          title: "Now Playing"
          message: >
            {{ state_attr('media_player.grooveprint', 'media_artist') }} —
            {{ state_attr('media_player.grooveprint', 'media_title') }}
```

## Requirements

- Home Assistant 2024.1.0 or newer
- A running Grooveprint server
- The Grooveprint listening app (iOS/Android) on the same network

## License

[MIT](LICENSE)
