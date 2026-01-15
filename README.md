# DLNA Radio Streamer

[![Tests](https://github.com/rafalkalinski/stream-to-dlna/actions/workflows/tests.yml/badge.svg)](https://github.com/rafalkalinski/stream-to-dlna/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/rafalkalinski/stream-to-dlna/branch/main/graph/badge.svg)](https://codecov.io/gh/rafalkalinski/stream-to-dlna)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/docker/pulls/erkalina/stream-to-dlna.svg)](https://hub.docker.com/r/erkalina/stream-to-dlna)

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

### Production (Docker)

```bash
git clone https://github.com/rafalkalinski/stream-to-dlna.git
cd stream-to-dlna

# Create your config from example
cp config.example.yaml config.yaml
# Edit config.yaml with your settings
docker-compose up -d
```

### Development (Local)

```bash
git clone https://github.com/rafalkalinski/stream-to-dlna.git
cd stream-to-dlna

# Automated setup
./dev-setup.sh

# Or manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest

# Open dev console in browser
open http://localhost:5000

# Or use CLI:
# Get devices
curl http://localhost:5000/devices?force_scan=true

# Select device
curl -X POST "http://localhost:5000/devices/select?ip=192.168.1.100"

# Play radio
curl -X POST http://localhost:5000/play
```

## Configuration

Create `config.yaml` from the example template:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`:

```yaml
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

Note: Device configuration is done via API (no manual IP configuration needed).

## API Reference

### Development Console

Open `http://localhost:5000` in browser for interactive API testing UI.

### Device Discovery

**Get devices**
```bash
GET /devices?force_scan=false
```
Returns cached devices by default. Use `force_scan=true` to perform new network scan.

**Select device**
```bash
POST /devices/select?ip=192.168.1.100
```
Selects device by IP. Uses cache first, falls back to scan, then attempts direct connection.

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

Response indicates whether passthrough or transcoding is used. Uses currently selected device from `/devices/select`.

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

## Troubleshooting

**Device not found in scan:**
- Try longer timeout: `/devices?force_scan=true&timeout=10`
- Use direct connection: `POST /devices/select?ip=192.168.1.100`

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
