# Stream-to-DLNA Radio Streamer

Stream internet radio to DLNA devices via REST API with real-time AAC to MP3 transcoding.

## Features

- Real-time audio transcoding (AAC → MP3) using FFmpeg
- DLNA/UPnP device control (AVTransport)
- REST API for remote control
- Home Assistant integration ready
- Docker container with Gunicorn production server
- Reverse proxy support (Nginx Proxy Manager)

## Quick Start

```bash
docker run -d \
  --name stream-to-dlna \
  -p 5000:5000 \
  -p 8080:8080 \
  -v ./config.yaml:/app/config.yaml:ro \
  rafalkalinski/stream-to-dlna:latest
```

## Configuration

Create `config.yaml`:

```yaml
dlna:
  host: "192.168.1.100"  # Your DLNA device IP

radio:
  default_url: "https://stream.radio357.pl"

streaming:
  port: 8080
  mp3_bitrate: "128k"
```

## API Endpoints

- `POST /play` - Start streaming (optional `?streamUrl=...`)
- `POST /stop` - Stop streaming
- `GET /status` - Get playback status
- `GET /health` - Health check

## Tested Devices

- Panasonic SC-PMX9

## Links

- [GitHub Repository](https://github.com/rafalkalinski/stream-to-dlna)
- [Documentation](https://github.com/rafalkalinski/stream-to-dlna/blob/main/README.md)
- [Issues](https://github.com/rafalkalinski/stream-to-dlna/issues)

## License

MIT License - Open Source
