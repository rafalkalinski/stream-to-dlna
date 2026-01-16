# DLNA Radio Streamer

Stream internet radio to DLNA devices with automatic format detection and smart transcoding.

## Features

- Automatic DLNA device discovery via SSDP/UPnP
- Smart transcoding: passthrough when device supports native format, FFmpeg transcoding when needed
- Multi-device support with persistent selection
- Device cache with 2-hour TTL and background scan on startup
- Direct connection fallback for devices not responding to SSDP
- REST API for control and automation
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

## API Usage

Open `http://localhost:5000` in browser for interactive dev console, or use CLI:

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

## Documentation

Full documentation: https://github.com/rafalkalinski/stream-to-dlna

## License

MIT License
