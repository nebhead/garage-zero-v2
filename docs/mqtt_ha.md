# MQTT Home Assistant Integration

## Overview

The MQTT integration provides automatic discovery and real-time control of your garage doors in Home Assistant. This is a significant improvement over the previous REST API method.

### Benefits

- **Zero YAML Configuration**: Doors auto-discover in Home Assistant
- **Real-time Updates**: Instant status changes, no polling delays
- **Bi-directional Control**: Commands from HA instantly reach your garage
- **Future-proof**: MQTT protocol is stable and widely supported
- **Native Integration**: Appears as proper garage door cover entities

---

## Prerequisites

### 1. MQTT Broker

You need an MQTT broker running. The easiest option is Mosquitto.

**Install on Raspberry Pi:**
```bash
sudo apt-get update
sudo apt-get install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

**Or use Home Assistant's Mosquitto add-on:**
- Navigate to: Settings → Add-ons → Add-on Store
- Install "Mosquitto broker"
- Start the add-on

### 2. Python MQTT Client

Install the paho-mqtt library on your Raspberry Pi:

```bash
pip3 install paho-mqtt
```

### 3. Configure Home Assistant MQTT Integration

In Home Assistant:
1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "MQTT"
4. Enter your broker details:
   - Broker: `localhost` (or your broker's IP)
   - Port: `1883`
   - Username/Password: (if configured)

---

## Configuration

### In Garage-Zero Web Interface

1. Navigate to **Settings** page
2. Scroll to **MQTT Home Assistant Integration** section
3. Configure the following:

| Setting | Description | Default |
|---------|-------------|---------|
| **Enable MQTT Integration** | Toggle to enable/disable | `false` |
| **MQTT Broker Address** | IP or hostname of your broker | `localhost` |
| **MQTT Port** | Port number | `1883` |
| **Username** | MQTT authentication username (optional) | _(empty)_ |
| **Password** | MQTT authentication password (optional) | _(empty)_ |
| **Discovery Prefix** | Home Assistant's discovery prefix | `homeassistant` |
| **Base Topic** | Base topic for garage-zero messages | `garage-zero` |

4. Click **Save MQTT Settings**
5. The control script will automatically reload with new settings

### Manual Configuration (settings.json)

You can also edit `settings.json` directly:

```json
{
  "mqtt_ha": {
    "enabled": true,
    "broker": "192.168.1.100",
    "port": 1883,
    "username": "",
    "password": "",
    "discovery_prefix": "homeassistant",
    "base_topic": "garage-zero"
  }
}
```

---

## How It Works

### Discovery

When the control script starts with MQTT enabled:
1. It publishes discovery messages to Home Assistant
2. Each door appears as a **Cover** entity
3. Device information includes manufacturer, model, and version

**Discovery Topic Format:**
```
homeassistant/cover/{door_id}/config
```

**Example Discovery Payload:**
```json
{
  "name": "First Door",
  "unique_id": "garage_zero_20210929165655292866",
  "command_topic": "garage-zero/20210929165655292866/set",
  "state_topic": "garage-zero/20210929165655292866/state",
  "device_class": "garage",
  "payload_open": "OPEN",
  "payload_close": "CLOSE",
  "payload_stop": "STOP",
  "state_open": "open",
  "state_closed": "closed",
  "device": {
    "identifiers": ["garage_zero_20210929165655292866"],
    "name": "First Door",
    "manufacturer": "Garage-Zero",
    "model": "v2"
  }
}
```

### State Updates

The control script publishes door states every cycle:
- **States**: `open`, `closed`, `opening`, `closing`, `unknown`
- **Topic**: `garage-zero/{door_id}/state`
- Updates happen in real-time when sensors change

### Commands

Home Assistant sends commands to control doors:
- **Topic**: `garage-zero/{door_id}/set`
- **Payloads**: `OPEN`, `CLOSE`, `STOP`
- All commands trigger the door button (toggle behavior)

---

## Using in Home Assistant

### Lovelace Dashboard

Once configured, your garage doors appear automatically in:
- **Devices & Services** → MQTT
- **Overview** dashboard (if auto-generated)

**Add to Dashboard:**
```yaml
type: entities
entities:
  - entity: cover.first_door
  - entity: cover.second_door
```

**Or use the Garage Card:**
```yaml
type: button
entity: cover.first_door
icon: mdi:garage
tap_action:
  action: toggle
```

### Automations

**Example: Close garage at night**
```yaml
automation:
  - alias: "Close Garage at 10 PM"
    trigger:
      - platform: time
        at: "22:00:00"
    condition:
      - condition: state
        entity_id: cover.first_door
        state: "open"
    action:
      - service: cover.close_cover
        target:
          entity_id: cover.first_door
```

**Example: Notify if left open**
```yaml
automation:
  - alias: "Garage Open Too Long"
    trigger:
      - platform: state
        entity_id: cover.first_door
        to: "open"
        for:
          minutes: 15
    action:
      - service: notify.mobile_app
        data:
          message: "Garage door has been open for 15 minutes"
```

### Scripts

```yaml
script:
  toggle_garage:
    alias: "Toggle Garage Door"
    sequence:
      - service: cover.toggle
        target:
          entity_id: cover.first_door
```

---

## Troubleshooting

### Doors Not Appearing in Home Assistant

1. **Check MQTT Integration**: Settings → Devices & Services → MQTT
2. **Verify Broker Connection**: Use MQTT Explorer or mosquitto_sub:
   ```bash
   mosquitto_sub -h localhost -t "homeassistant/#" -v
   ```
3. **Check Logs**: Look in `/logs/` for MQTT errors
4. **Restart Control Script**:
   ```bash
   sudo supervisorctl restart control
   ```

### Connection Issues

**Test MQTT broker accessibility:**
```bash
mosquitto_pub -h YOUR_BROKER_IP -p 1883 -t "test" -m "hello"
```

**Check if paho-mqtt is installed:**
```bash
pip3 show paho-mqtt
```

### State Not Updating

1. Verify sensors are configured correctly
2. Check Redis contains door states:
   ```bash
   redis-cli HGETALL doorobj:20210929165655292866
   ```
3. Monitor MQTT traffic:
   ```bash
   mosquitto_sub -h localhost -t "garage-zero/#" -v
   ```

### Commands Not Working

1. Verify command topic subscription in logs
2. Test manually:
   ```bash
   mosquitto_pub -h localhost -t "garage-zero/YOUR_DOOR_ID/set" -m "OPEN"
   ```
3. Check door button configuration in settings

---

## Migration from REST API

If you're currently using the REST API method with YAML configuration:

1. **Enable MQTT** in Garage-Zero settings
2. **Remove old YAML** from Home Assistant's `configuration.yaml`:
   - Remove `sensor:` entries for garage doors
   - Remove `switch:` entries for garage doors
   - Remove `cover:` template entries
3. **Restart Home Assistant**
4. Doors will auto-discover within seconds

**You can run both** REST API and MQTT simultaneously during migration.

---

## Advanced Configuration

### Custom Topics

You can customize topics in `settings.json`:
```json
{
  "mqtt_ha": {
    "discovery_prefix": "homeassistant",
    "base_topic": "my-custom-garage"
  }
}
```

### Secure MQTT (TLS)

For TLS/SSL MQTT connections, you'll need to modify `mqtt_ha.py`:
```python
self.client.tls_set(ca_certs="/path/to/ca.crt")
```

### Multiple Brokers

Each garage-zero instance can connect to a different broker by configuring its own `settings.json`.

---

## Technical Details

### Topics Structure

| Topic | Purpose | Retained | QoS |
|-------|---------|----------|-----|
| `homeassistant/cover/{door_id}/config` | Discovery payload | Yes | 0 |
| `garage-zero/{door_id}/state` | Current state | Yes | 0 |
| `garage-zero/{door_id}/set` | Command topic | No | 0 |

### State Machine

```
closed → [OPEN cmd] → opening → [sensor triggered] → open
open → [CLOSE cmd] → closing → [sensor triggered] → closed
```

### Files Modified

- `mqtt_ha.py` - Main MQTT integration module
- `control.py` - Initializes and updates MQTT client
- `settings.json` - Configuration storage
- `app.py` - Web interface settings handler
- `templates/settings.html` - Settings UI

---

## Support

For issues or questions:
1. Check the logs in `/logs/` directory
2. Review the main [README.md](../README.md)
3. Open an issue on GitHub with:
   - Your configuration (sanitized)
   - Relevant log entries
   - Home Assistant version

---

## Future Enhancements

Potential improvements for future versions:
- Battery sensor support
- Obstruction detection
- Last operation timestamp
- SSL/TLS configuration in UI
- MQTT diagnostics panel
- Bridge mode for multiple garage-zero units
