# DLNA Radio Streamer

[![Tests](https://github.com/rafalkalinski/stream-to-dlna/actions/workflows/tests.yml/badge.svg)](https://github.com/rafalkalinski/stream-to-dlna/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Stream internet radio to DLNA devices with automatic format detection and smart transcoding.

**Latest:** v0.4 - See [CHANGELOG](https://github.com/rafalkalinski/stream-to-dlna/blob/main/CHANGELOG.md) for release notes.

## Features

- **Interactive Web Console** at `http://localhost:5000` - test API endpoints and manage devices
- **Automatic DLNA device discovery** via SSDP/UPnP
- **Smart transcoding**: passthrough when device supports native format, FFmpeg transcoding when needed
- **Auto-select default device** on startup via `dlna.default_device_ip` config
- **Stream format caching** - reduces repeated format detection
- **Multi-device support** with persistent selection
- **Device cache** with background scan on startup
- **Direct connection** fallback for devices not responding to SSDP
- **REST API** for control and automation
- **Optional API key authentication** for protected endpoints
- **Optional rate limiting** support
- Filters MediaRenderer devices (excludes NAS/MediaServers)

## Quick Start

```bash
docker run -d \
  --name stream-to-dlna \
  --network host \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/data:/data \
  erkalina/stream-to-dlna:latest
```

Or use docker-compose.yaml from the repository.

## Configuration

Create `config.yaml`:

```yaml
radio:
  default_url: "https://your-radio-stream.com"

# Optional: Auto-select DLNA device on startup
dlna:
  default_device_ip: "192.168.0.100"

server:
  host: "0.0.0.0"
  port: 5000

streaming:
  port: 8080
  mp3_bitrate: "128k"

# Persistent storage for device cache and stream format cache
storage:
  data_dir: "/data"
  stream_cache_ttl: 86400  # 24 hours

# Optional: API authentication
security:
  api_auth_enabled: false
  # api_key: "your-secret-key"
```

Device configuration is done via API.

## Web Console

Open `http://localhost:5000` in your browser for the **interactive development console**:
- Device discovery and selection
- Playback control (play/stop)
- Status monitoring
- Real-time API output

Or use CLI/API directly:

```bash
# Get devices (force scan)
curl http://localhost:5000/devices?force_scan=true

# Select device by IP
curl -X POST http://localhost:5000/devices/select?ip=192.168.1.100

# Start playback
curl -X POST http://localhost:5000/play?streamUrl=https://stream.url

# Check status
curl http://localhost:5000/status

# Stop playback
curl -X POST http://localhost:5000/stop
```

## Tested Devices

- Panasonic SC-PMX9
- Samsung HW-Q90R

## Version History

- **v0.4** - Default device auto-select, stream format caching, enhanced AAC detection
- **v0.3** - Security features (API auth, rate limiting), reliability improvements
- **v0.2** - Development console, testing, device caching
- **v0.1** - Initial release with core DLNA streaming

See [CHANGELOG](https://github.com/rafalkalinski/stream-to-dlna/blob/main/CHANGELOG.md) for detailed release notes.

## Documentation

- **Full Documentation**: https://github.com/rafalkalinski/stream-to-dlna
- **Security Guide**: https://github.com/rafalkalinski/stream-to-dlna/blob/main/SECURITY.md
- **Changelog**: https://github.com/rafalkalinski/stream-to-dlna/blob/main/CHANGELOG.md
- **Issues**: https://github.com/rafalkalinski/stream-to-dlna/issues

## License

MIT License
