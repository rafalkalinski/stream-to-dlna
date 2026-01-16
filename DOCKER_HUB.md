# DLNA Radio Streamer

[![Tests](https://github.com/rafalkalinski/stream-to-dlna/actions/workflows/tests.yml/badge.svg)](https://github.com/rafalkalinski/stream-to-dlna/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Stream internet radio to DLNA devices with automatic format detection and smart transcoding.

**Latest:** v0.2 - See [CHANGELOG](https://github.com/rafalkalinski/stream-to-dlna/blob/main/CHANGELOG.md) for release notes.

## Features

- **Interactive Web Console** at `http://localhost:5000` - test API endpoints and manage devices
- **Automatic DLNA device discovery** via SSDP/UPnP
- **Smart transcoding**: passthrough when device supports native format, FFmpeg transcoding when needed
- **Multi-device support** with persistent selection
- **Device cache** with 2-hour TTL and background scan on startup
- **Direct connection** fallback for devices not responding to SSDP
- **REST API** for control and automation
- **Comprehensive test suite** with CI/CD via GitHub Actions
- Filters MediaRenderer devices (excludes NAS/MediaServers)

## Quick Start

```bash
docker run -d \
  --name stream-to-dlna \
  --network host \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  rafalkalinski/stream-to-dlna:latest
```

Or use docker-compose.yaml from the repository.

## Configuration

Create `config.yaml`:

```yaml
radio:
  default_url: "https://your-radio-stream.com"

server:
  host: "0.0.0.0"
  port: 5000

streaming:
  port: 8080
  mp3_bitrate: "128k"
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
curl -X POST "http://localhost:5000/devices/select?ip=192.168.1.100"

# Start playback
curl -X POST http://localhost:5000/play?streamUrl=https://stream.url

# Check status
curl http://localhost:5000/status

# Stop playback
curl -X POST http://localhost:5000/stop
```

## Docker Networking

For SSDP multicast to work:
- Use `network_mode: host` (simplest)
- Or use macvlan network (recommended for production)

See repository README for detailed networking configuration.

## Tested Devices

- Panasonic SC-PMX9
- Samsung HW-Q90R

## Version History

- **v0.2** - Development console, comprehensive testing, device caching, reliability improvements
- **v0.1** - Initial release with core DLNA streaming functionality

See [CHANGELOG](https://github.com/rafalkalinski/stream-to-dlna/blob/main/CHANGELOG.md) for detailed release notes.

## Documentation

- **Full Documentation**: https://github.com/rafalkalinski/stream-to-dlna
- **Changelog**: https://github.com/rafalkalinski/stream-to-dlna/blob/main/CHANGELOG.md
- **Issues**: https://github.com/rafalkalinski/stream-to-dlna/issues

## License

MIT License
