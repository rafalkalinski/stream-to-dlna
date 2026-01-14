# DLNA Radio Streamer

Stream internet radio to DLNA devices with automatic format detection and smart transcoding.

## Features

- Network discovery with SSDP/UPnP
- Smart transcoding: passthrough when device supports native format, FFmpeg when transcoding needed
- Multi-device support with persistent device selection
- Device cache with configurable TTL (default 2 hours)
- Background device scan on startup
- Direct device connection fallback when SSDP fails
- MediaRenderer filtering (excludes MediaServers like NAS devices)
- REST API for full control
- Docker-based deployment

## Quick Start

```bash
git clone https://github.com/rafalkalinski/stream-to-dlna.git
cd stream-to-dlna

# Edit config.yaml with your settings
docker-compose up -d

# Scan for devices
curl http://localhost:5000/scan

# Select device
curl -X POST http://localhost:5000/devices/select -H "Content-Type: application/json" \
  -d '{"device_id": "your-device-id"}'

# Play radio
curl -X POST http://localhost:5000/play
```

## Configuration

Edit `config.yaml`:

```yaml
dlna:
  host: "192.168.1.100"

radio:
  default_url: "https://stream.radio357.pl"

server:
  host: "0.0.0.0"
  port: 5000

streaming:
  port: 8080
  mp3_bitrate: "128k"
  # public_url: "http://radio.yourdomain.local"
```

## API Reference

### Device Discovery

**Scan network for DLNA devices**
```bash
GET /scan?timeout=5&force=false&max_cache_age=7200
```
Parameters:
- `timeout`: Scan timeout in seconds (default: 5, max: 15)
- `force`: Force new scan ignoring cache (default: false)
- `max_cache_age`: Cache TTL in seconds (default: 7200 = 2 hours)

Response:
```json
{
  "devices": [{"id": "...", "friendly_name": "Device", "host": "192.168.1.100", ...}],
  "count": 1,
  "from_cache": true,
  "cache_age_seconds": 120
}
```

**Get cached devices**
```bash
GET /devices
```

**Select device**
```bash
POST /devices/select
Content-Type: application/json

{"device_id": "uuid-1234"} or {"host": "192.168.1.100"}
```
Supports selection by device_id or IP address. Uses cache first, falls back to scan, then direct connection.

**Get current device**
```bash
GET /devices/current
```

### Playback Control

**Start playback**
```bash
POST /play?streamUrl=https://stream.radio357.pl
```
Parameters:
- `streamUrl`: Stream URL (optional, uses default from config)
- `device_id`: Override device for this playback (optional)

Response indicates whether passthrough or transcoding is used.

**Stop playback**
```bash
POST /stop
```

### Status

**Get status**
```bash
GET /status
```
Returns streaming status, DLNA device state, and current device info.

**Health check**
```bash
GET /health
```

## Architecture

### Streaming Modes

**Passthrough Mode** (when device supports native format):
- Detects stream format via HTTP headers
- Checks device capabilities using UPnP GetProtocolInfo
- Sends stream URL directly to device

**Transcoding Mode** (when transcoding needed):
- FFmpeg transcodes stream to MP3
- Serves transcoded stream via HTTP
- Device plays from local server

Mode is automatically selected based on format detection and device capabilities.

### Device Discovery

1. Background scan on startup (10s timeout)
2. Results cached with 2-hour TTL
3. Manual refresh via `/scan?force=true`
4. Direct connection fallback when SSDP fails

Only MediaRenderer devices (with AVTransport service) are discovered. MediaServer devices like NAS are filtered out.

## Docker Networking

For SSDP multicast discovery to work, use either:

**Option 1: Host network**
```yaml
network_mode: host
```

**Option 2: Macvlan network** (recommended for production)
```yaml
networks:
  your-macvlan:  # IP from DHCP or static
  your-bridge:   # For reverse proxy access
```

## Troubleshooting

**Device not found in scan:**
- Try longer timeout: `/scan?timeout=10`
- Use direct connection: `POST /devices/select` with `{"host": "192.168.1.100"}`
- Verify multicast works: check Docker network mode

**Playback fails:**
- Check logs: `docker logs stream-to-dlna`
- Verify device is accessible from container
- Check firewall rules

**Cache not updating:**
- Force refresh: `/scan?force=true`
- Adjust TTL: `/scan?max_cache_age=3600`

## Development

### Project Structure

```
stream-to-dlna/
├── app/
│   ├── main.py           # Flask API
│   ├── config.py         # Configuration
│   ├── dlna_client.py    # DLNA/UPnP client
│   ├── streamer.py       # FFmpeg transcoding
│   ├── discovery.py      # SSDP discovery
│   └── device_manager.py # Device state management
├── config.yaml
├── Dockerfile
└── docker-compose.yaml
```

### Tested Devices

- Panasonic SC-PMX9
- Samsung HW-Q90R

## License

MIT License - see LICENSE file for details.
