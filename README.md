# DLNA Radio Streamer

[![Tests](https://github.com/rafalkalinski/stream-to-dlna/actions/workflows/tests.yml/badge.svg)](https://github.com/rafalkalinski/stream-to-dlna/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/docker/pulls/erkalina/stream-to-dlna.svg)](https://hub.docker.com/r/erkalina/stream-to-dlna)
[![Version](https://img.shields.io/badge/version-v0.6.x-blue.svg)](CHANGELOG.md)
[![Security](https://img.shields.io/badge/security-reviewed-green.svg)](SECURITY.md)

Stream internet radio to DLNA devices with automatic format detection and smart transcoding.

**Latest:** v0.6 — new web player GUI (now playing, speakers, stations, activity log). See [CHANGELOG](CHANGELOG.md) for details.

## Features

### Core Functionality
- **Web player** at `http://localhost:5000` — now playing card with Play/Stop, speaker picker with network scan, station list
  - Responsive (phone and desktop), light and dark theme
  - Live status polling (shows the real speaker state, transcoding mode and source format)
  - Activity log panel with raw API requests/responses for debugging
  - Optional API key entry in Settings (stored in the browser)
- Network discovery with SSDP/UPnP
- Smart transcoding: passthrough when device supports native format, FFmpeg when transcoding needed
  - Enhanced AAC codec detection (audio/aac, audio/aacp, audio/adts, audio/m4a)
  - FFprobe fallback for streams without Content-Type header
  - Persistent cache for stream format detection (configurable TTL)
- Multi-device support with persistent device selection
  - **Auto-select default device**: Configure `dlna.default_device_ip` for automatic selection on startup
- Device cache with configurable TTL (default 2 hours)
- Background device scan on startup
- Direct device connection fallback when SSDP fails
- MediaRenderer filtering (excludes MediaServers like NAS devices)
- REST API for full control
- Docker-based deployment

### Performance & Reliability
- HTTP connection pooling for improved performance
- Process-level file locking (fcntl) for multi-worker safety
- FFmpeg process tracking and orphan cleanup
- Configurable timeouts for all network operations
- Stderr buffer limiting to prevent memory leaks
- Single-worker architecture for consistent state management (fixed in the Dockerfile)
- DLNA compliance headers (`transferMode`, `contentFeatures`) for strict renderers
- DIDL-Lite metadata in `SetAVTransportURI` for Samsung and other picky devices
- HEAD request handler on streaming server (required by Samsung HW-Q90R)

### Security
- Comprehensive input validation (IP, URL, boolean)
- SSRF protection (blocks localhost, AWS metadata, IPv6 loopback)
- FFmpeg protocol whitelist (http,https,tcp,tls)
- Optional API key authentication
- Optional rate limiting (Flask-Limiter, requires a custom image — see below)
- See [SECURITY.md](SECURITY.md) for full security documentation

## Quick Start

### Production (prebuilt image from Docker Hub)

```bash
mkdir stream-to-dlna && cd stream-to-dlna
curl -o config.yaml https://raw.githubusercontent.com/rafalkalinski/stream-to-dlna/main/config.example.yaml
# Edit config.yaml with your settings

docker run -d \
  --name stream-to-dlna \
  --network host \
  --restart unless-stopped \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/data:/data \
  erkalina/stream-to-dlna:latest
```

The container needs to be on the same L2 network as your DLNA devices (SSDP discovery uses multicast). Use `--network host` or a `macvlan` network with a dedicated LAN IP.

#### Image updates

`erkalina/stream-to-dlna:latest` is built by GitHub Actions on every push to `main` and **rebuilt monthly** from a fresh base image to pick up Debian security patches. Version tags (`v0.6`, ...) are published as separate image tags. Pull the image regularly to stay patched.

Versioning: `MAJOR.MINOR` comes from the latest `vMAJOR.MINOR` git tag, `PATCH` is the number of changes merged into `main` since that tag (`scripts/version.sh`) — e.g. `v0.6` → `0.6.0`, next merge → `0.6.1`. The running version is shown in the web player.

### Build from source

```bash
git clone https://github.com/rafalkalinski/stream-to-dlna.git
cd stream-to-dlna
cp config.example.yaml config.yaml   # edit as needed

# Quick: build locally with version from git tags and smoke-test /health
make docker-build
make docker-test

# Or run with the bundled compose file (host networking, ./data volume)
docker compose up -d --build
```

For a repeatable build-and-deploy workflow, copy `deploy.sh.example` to `deploy.sh` and create your own `docker-compose.deploy.yaml` (volume paths, network). Then:

```bash
./deploy.sh -b      # git pull + build image (version from git tags)
./deploy.sh -d      # replace the running container
./deploy.sh -b -d   # both
```

### Logging

Edit `docker-compose.yaml` to control log verbosity:
```yaml
environment:
  - LOG_LEVEL=INFO   # Production: INFO or WARNING
  - LOG_LEVEL=DEBUG  # Development: DEBUG for detailed logs
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

# Open the web player in browser
open http://localhost:5000

# Or use CLI:
# Get devices
curl http://localhost:5000/devices?force_scan=true

# Select device
curl -X POST http://localhost:5000/devices/select?ip=192.168.1.100

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

# Optional: Auto-select DLNA device on startup
dlna:
  default_device_ip: "192.168.1.100"

server:
  host: "0.0.0.0"
  port: 5000

streaming:
  internal_port: 8080
  mp3_bitrate: "128k"
  # external_url: "http://radio.yourdomain.local"

# Persistent storage (optional, defaults shown)
storage:
  data_dir: "/data"          # Docker volume mount point
  stream_cache_ttl: 86400    # 24 hours

# Network timeouts (optional, defaults shown)
timeouts:
  http_request: 10
  stream_detection: 5
  device_discovery: 10
  ffmpeg_startup: 10

# Security settings (optional)
security:
  rate_limit_enabled: false
  # rate_limit_default: "100 per hour"
  api_auth_enabled: false
  # api_key: "your-secret-api-key-here"

# Performance settings (optional, defaults shown)
performance:
  connection_pool_size: 10
  connection_pool_maxsize: 20

# FFmpeg settings (optional, defaults shown)
ffmpeg:
  chunk_size: 8192
  max_stderr_lines: 1000
  protocol_whitelist: "http,https,tcp,tls"
```

Note: Devices are discovered automatically and selected via the GUI/API; `dlna.default_device_ip` is optional.

Gunicorn always runs with 1 worker and 4 threads (set in the Dockerfile). A single worker is required — the streaming server and playback state live in-process.

### Security Configuration

**By default, the API is OPEN without authentication.** This is suitable for trusted local networks only.

For production deployments, **you MUST enable security features:**

#### 1. API Key Authentication (Strongly Recommended)

**Default state:** `api_auth_enabled: false` - **all endpoints are accessible without authentication**

**To enable authentication:**

```yaml
# config.yaml
security:
  api_auth_enabled: true
  api_key: "your-32-character-random-key-here"  # Generate with: openssl rand -hex 32
```

**Protected endpoints** (require `X-API-Key` header when auth is enabled):
- `POST /devices/select` - Device selection
- `POST /play` - Start playback
- `POST /stop` - Stop playback

**Public endpoints** (always accessible):
- `GET /` - Web console
- `GET /health` - Health check
- `GET /devices` - List devices
- `GET /devices/current` - Current device
- `GET /status` - Playback status

**Usage with authentication enabled:**
```bash
# Without API key - returns 401 Unauthorized
curl -X POST http://localhost:5000/play

# With valid API key - works
curl -X POST http://localhost:5000/play \
  -H "X-API-Key: your-32-character-random-key-here"
```

#### 2. Rate Limiting (Optional)

**Default state:** `rate_limit_enabled: false` - **no rate limiting applied**

**To enable rate limiting:**

1. Install Flask-Limiter. It is **not included** in the official Docker image — uncomment `Flask-Limiter` in `requirements.txt` and build your own image (or `pip install Flask-Limiter` for a local install). Without it, the setting is ignored with a warning in the logs.

2. Enable in config:
```yaml
security:
  rate_limit_enabled: true
  rate_limit_default: "100 per hour"  # Adjust as needed
```

**Important:** Rate limiting applies to ALL endpoints when enabled.

#### Security Best Practices

**DO** for production:
- Enable API authentication (`api_auth_enabled: true`)
- Use strong random API key (minimum 32 characters)
- Store API key securely (environment variables, secrets manager)
- Enable rate limiting to prevent abuse
- Use HTTPS reverse proxy (nginx, Traefik)
- Run behind firewall with restricted access

**DON'T** for production:
- Leave authentication disabled (`api_auth_enabled: false`)
- Use weak or guessable API keys
- Expose directly to internet without reverse proxy
- Commit API keys to git

See [SECURITY.md](SECURITY.md) for comprehensive security guide and deployment checklist.

## API Reference

### Web Player

Open `http://localhost:5000` in a browser. The *Activity log* panel at the bottom shows every API request and its JSON response.

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

**Get cached streams**
```bash
GET /streams/cached
```
Returns list of cached stream formats (used by GUI tags).

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
Returns streaming status, DLNA device state, current device info, and — while streaming — the source stream (`stream.url`, `stream.transcoding`, `stream.format`).

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
3. Manual refresh via `/devices?force_scan=true`
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
- Force refresh: `/devices?force_scan=true`

## Development

### Project Structure

```
stream-to-dlna/
├── app/
│   ├── main.py            # Flask API, playback orchestration, input validation
│   ├── config.py          # Configuration loader
│   ├── app_context.py     # Shared application state
│   ├── device_manager.py  # Device selection, cache and state file
│   ├── discovery.py       # SSDP discovery
│   ├── dlna_client.py     # DLNA/UPnP client (AVTransport, GetProtocolInfo)
│   ├── streamer.py        # FFmpeg transcoding + internal HTTP streaming server
│   ├── stream_cache.py    # Stream format detection cache
│   ├── http_client.py     # Pooled HTTP client
│   ├── security.py        # API key auth, rate limiting
│   ├── templates/dev.html # Web console
│   └── static/
├── tests/                 # pytest suite (see TESTING.md)
├── config.example.yaml
├── Dockerfile
├── docker-compose.yaml    # Build + run locally (host network)
├── deploy.sh.example      # Template for your own build/deploy script
└── Makefile               # Dev shortcuts: make help
```

### Tested Devices

- Panasonic SC-PMX9
- Samsung HW-Q90R

## License

MIT License - see LICENSE file for details.
