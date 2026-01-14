# DLNA Radio Streamer

Stream internet radio to DLNA-enabled devices with smart transcoding and multi-device support.

## Features

- **Network Discovery**: Automatically scan and discover DLNA devices on your network
- **Smart Transcoding**: Automatically detects stream format and device capabilities
  - Passthrough mode when device supports native format
  - FFmpeg transcoding when needed (AAC → MP3, etc.)
- **Multi-Device Support**: Scan, select, and switch between multiple DLNA devices
- **Persistent Device Selection**: Remembers your selected device across restarts
- **REST API**: Full control via HTTP endpoints
- **Docker-based deployment**: Easy setup with Docker Compose
- **Home Assistant integration ready**
- **YAML configuration**

## Architecture

The application provides two streaming modes:

**Passthrough Mode** (when device supports native format):
1. Detects stream format via HTTP headers
2. Checks device capabilities using UPnP GetProtocolInfo
3. Sends stream URL directly to DLNA device (no transcoding)

**Transcoding Mode** (when transcoding is needed):
1. Uses FFmpeg to fetch and transcode the stream to MP3
2. Serves the transcoded stream via HTTP
3. Instructs the DLNA device to play the transcoded stream

The mode is automatically selected based on stream format and device capabilities.

## Requirements

- Docker and Docker Compose
- DLNA-compatible device on the same network
- Network connectivity between the Docker host and DLNA device

## Installation

1. Clone the repository:
```bash
git clone https://github.com/rafalkalinski/stream-to-dlna.git
cd stream-to-dlna
```

2. Edit `config.yaml` with your settings:
```yaml
dlna:
  host: "192.168.1.100"  # Your DLNA device address

radio:
  default_url: "https://stream.radio357.pl"
```

3. Start the service:
```bash
docker-compose up -d
```

## Configuration

Edit `config.yaml`:

```yaml
# DLNA device settings
dlna:
  host: "192.168.1.100"   # Your DLNA device address (IP, hostname, or domain)

# Radio streaming settings
radio:
  default_url: "https://stream.radio357.pl"

# API server settings
server:
  host: "0.0.0.0"         # Bind to all interfaces
  port: 5000              # REST API port

# Streaming settings
streaming:
  port: 8080              # Port for transcoded MP3 stream
  mp3_bitrate: "128k"     # MP3 encoding bitrate

  # Optional: Public URL for reverse proxy (e.g., Nginx Proxy Manager)
  # public_url: "http://radio.yourdomain.local"

# Optional: Advanced DLNA settings (uncomment if needed)
# dlna_advanced:
#   port: 8080         # DLNA control port (default: 8080)
#   protocol: "http"   # Protocol: http or https (default: http)
```

## API Endpoints

### Device Discovery

#### Scan Network for DLNA Devices

Discover all DLNA MediaRenderer devices on your network:

```bash
GET /scan?timeout=5
```

Response:
```json
{
  "devices": [
    {
      "id": "uuid-1234-5678",
      "friendly_name": "Panasonic SC-PMX9",
      "manufacturer": "Panasonic",
      "model_name": "SC-PMX9",
      "host": "192.168.1.100",
      "port": 8080,
      "location": "http://192.168.1.100:8080/description.xml",
      "control_url": "http://192.168.1.100:8080/AVTransport/ctrl"
    }
  ],
  "count": 1
}
```

#### Select a Device

Select a DLNA device and detect its capabilities:

```bash
# Using device_id from /scan
POST /device/select?device_id=uuid-1234-5678

# Or send full device info in JSON body
POST /device/select
{
  "device_id": "uuid-1234-5678",
  "device_info": { ... }
}
```

Response:
```json
{
  "status": "selected",
  "device": {
    "id": "uuid-1234-5678",
    "friendly_name": "Panasonic SC-PMX9",
    "manufacturer": "Panasonic",
    "model_name": "SC-PMX9",
    "host": "192.168.1.100",
    "capabilities": {
      "supports_mp3": true,
      "supports_aac": false,
      "supports_flac": false,
      "supports_wav": true,
      "supports_ogg": false
    }
  }
}
```

#### Get Current Device

View the currently selected device:

```bash
GET /device/current
```

Response:
```json
{
  "device": {
    "id": "uuid-1234-5678",
    "friendly_name": "Panasonic SC-PMX9",
    "capabilities": { ... }
  }
}
```

### Playback Control

#### Start Playback

Start streaming with smart transcoding:

```bash
# Use default stream URL from config.yaml
POST /play

# Provide a custom stream URL
POST /play?streamUrl=https://stream.radio357.pl

# Override device for this playback
POST /play?streamUrl=https://stream.radio357.pl&device_id=uuid-1234-5678
```

Response:
```json
{
  "status": "playing",
  "stream_url": "https://stream.radio357.pl",
  "playback_url": "https://stream.radio357.pl",
  "transcoding": false,
  "format": "audio/mpeg"
}
```

**Note**: `transcoding: false` means passthrough mode (device plays native format). `transcoding: true` means FFmpeg is transcoding the stream.

#### Stop Playback

Stop streaming:

```bash
POST /stop
```

Response:
```json
{
  "status": "stopped"
}
```

### Status and Health

#### Check Status

Get current playback status:

```bash
GET /status
```

Response:
```json
{
  "streaming": true,
  "dlna": {
    "state": "PLAYING",
    "status": "OK"
  }
}
```

#### Health Check

Check if the service is running:

```bash
GET /health
```

Response:
```json
{
  "status": "ok",
  "streaming": false
}
```

## Troubleshooting

### DLNA device not responding

1. Verify the device host address in `config.yaml`
2. Check network connectivity:
```bash
docker exec dlna-radio-streamer ping 192.168.1.100
# or for hostnames
docker exec dlna-radio-streamer ping panasonic.local
```

3. Some devices use different control URLs. Check device documentation or use a UPnP discovery tool.

### FFmpeg transcoding issues

View FFmpeg logs:
```bash
docker logs dlna-radio-streamer
```

Common issues:
- Invalid stream URL
- Network connectivity problems
- Unsupported audio codec (though AAC should work)

### Stream not playing on device

1. Verify DLNA device can reach the Docker host
2. Check firewall rules on the Docker host

## Workflow Examples

### Quick Start with Device Discovery

```bash
# 1. Scan for devices
curl http://localhost:5000/scan

# 2. Select a device (copy device_id from scan results)
curl -X POST "http://localhost:5000/device/select?device_id=uuid-1234-5678"

# 3. Start playing radio
curl -X POST "http://localhost:5000/play?streamUrl=https://stream.radio357.pl"

# 4. Stop playback
curl -X POST http://localhost:5000/stop
```

### Using Multiple Devices

```bash
# Play on device A
curl -X POST "http://localhost:5000/play?device_id=uuid-device-a&streamUrl=https://radio1.com"

# Switch to device B (without changing selected device)
curl -X POST "http://localhost:5000/play?device_id=uuid-device-b&streamUrl=https://radio2.com"
```

## Development

### Project Structure

```
stream-to-dlna/
├── app/
│   ├── __init__.py
│   ├── main.py          # Flask API application
│   ├── config.py        # Configuration management
│   ├── dlna_client.py   # DLNA/UPnP client with capabilities detection
│   ├── streamer.py      # FFmpeg transcoding & passthrough
│   ├── discovery.py     # SSDP/UPnP device discovery
│   └── device_manager.py # Device state management
├── config.yaml          # Configuration file
├── state.json           # Device state (auto-generated)
├── requirements.txt     # Python dependencies
├── Dockerfile
├── docker-compose.yaml
├── LICENSE
└── README.md
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Tested Devices

- Panasonic SC-PMX9

If you test this with other devices, please open an issue to let us know.

## Acknowledgments

- FFmpeg for audio transcoding
- Flask for the REST API framework
- UPnP/DLNA protocol specifications
