# DLNA Radio Streamer

Stream internet radio to DLNA-enabled devices with automatic AAC to MP3 transcoding.

## Features

- REST API for controlling DLNA devices
- Automatic audio transcoding (AAC/HLS to MP3)
- Docker-based deployment
- Home Assistant integration ready
- YAML configuration
- Support for custom stream URLs

## Architecture

The application works as follows:

1. Receives HTTP request to start streaming
2. Uses FFmpeg to fetch and transcode the radio stream to MP3
3. Serves the transcoded stream via HTTP
4. Instructs the DLNA device to play the stream using UPnP/AVTransport protocol

## Requirements

- Docker and Docker Compose
- DLNA-compatible device on the same network
- Network connectivity between the Docker host and DLNA device

## Installation

### Using Docker Compose (recommended)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/stream-to-dlna.git
cd stream-to-dlna
```

2. Edit `config.yaml` with your settings:
```yaml
dlna:
  ip: "192.168.1.100"  # Your DLNA device IP
  port: 55000

radio:
  default_url: "http://your-radio-stream-url/stream.aac"
```

3. Start the service:
```bash
docker-compose up -d
```

### Manual Installation

1. Install Python 3.11+ and FFmpeg:
```bash
apt-get install python3 python3-pip ffmpeg
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Configure `config.yaml` and run:
```bash
python -m app.main
```

## Configuration

Edit `config.yaml`:

```yaml
# DLNA device settings
dlna:
  ip: "192.168.1.100"     # DLNA device IP address
  port: 55000             # DLNA control port

# Radio streaming settings
radio:
  default_url: "http://your-radio-stream-url/stream.aac"

# API server settings
server:
  host: "0.0.0.0"
  port: 5000

# Streaming settings
streaming:
  port: 8080              # Port for MP3 stream
  mp3_bitrate: "128k"     # MP3 encoding bitrate
```

## API Endpoints

### Start Playback

Start streaming to the DLNA device:

```bash
# Use default stream URL from config.yaml
POST /play

# Or provide a custom stream URL
POST /play?streamUrl=https://stream.radio357.pl/stream.aac
```

Examples:
```bash
# Using default URL
curl -X POST http://localhost:5000/play

# With custom URL
curl -X POST "http://localhost:5000/play?streamUrl=https://stream.radio357.pl/stream.aac"
```

Response:
```json
{
  "status": "playing",
  "stream_url": "https://stream.radio357.pl/stream.aac",
  "transcoded_url": "http://192.168.1.50:8080/stream.mp3"
}
```

### Stop Playback

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

### Check Status

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

### Health Check

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

## Home Assistant Integration

### Configuration

Add to your `configuration.yaml`:

```yaml
rest_command:
  radio_play:
    url: http://192.168.1.50:5000/play
    method: POST

  radio_play_custom:
    url: "http://192.168.1.50:5000/play?streamUrl={{ streamUrl }}"
    method: POST

  radio_stop:
    url: http://192.168.1.50:5000/stop
    method: POST
```

### Automation Example

Create an automation for a button:

```yaml
automation:
  - alias: "Radio Play on Button Press"
    trigger:
      - platform: event
        event_type: remote_button_pressed
        event_data:
          button: play
    action:
      - service: rest_command.radio_play

  - alias: "Radio Stop on Button Double Press"
    trigger:
      - platform: event
        event_type: remote_button_pressed
        event_data:
          button: play
          action: double_press
    action:
      - service: rest_command.radio_stop
```

## Troubleshooting

### DLNA device not responding

1. Verify the device IP address in `config.yaml`
2. Check network connectivity:
```bash
docker exec dlna-radio-streamer ping 192.168.1.100
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

1. Check if the stream is accessible:
```bash
curl http://192.168.1.50:8080/stream.mp3
```

2. Verify DLNA device can reach the Docker host
3. Check firewall rules on the Docker host

### Network mode issues

The Docker container uses `network_mode: host` to ensure the DLNA device can reach the streaming server. If you need to use bridge networking:

1. Change `docker-compose.yaml`:
```yaml
network_mode: bridge
ports:
  - "5000:5000"
  - "8080:8080"
```

2. Ensure the DLNA device can reach the Docker host IP on these ports

## Development

### Project Structure

```
stream-to-dlna/
├── app/
│   ├── __init__.py
│   ├── main.py          # Flask API application
│   ├── config.py        # Configuration management
│   ├── dlna_client.py   # DLNA/UPnP client
│   └── streamer.py      # FFmpeg streaming
├── config.yaml          # Configuration file
├── requirements.txt     # Python dependencies
├── Dockerfile
├── docker-compose.yaml
├── LICENSE
└── README.md
```

### Running Tests

Tests coming soon.

### Contributing

Contributions are welcome. Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Tested Devices

- Panasonic SC-PMX9

If you test this with other devices, please open an issue to let us know.

## Acknowledgments

- FFmpeg for audio transcoding
- Flask for the REST API framework
- UPnP/DLNA protocol specifications
