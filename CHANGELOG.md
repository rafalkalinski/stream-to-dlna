# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Activity log across devices** (0.6.2): every action (play, stop, speaker selection, scan) is broadcast as an `activity` event with the name of the device that made it and shown in the Activity log on all open players (last 50 replayed on connect); players also log speaker state changes (e.g. `PMX9: playing → stopped`). Device name is detected from the browser or set in Settings (`X-Client-Name` header). Log filters for events / API calls. Actions are also written to the container log.
- **Live updates** (0.6.1): new `GET /events` Server-Sent Events stream; the web player now updates instantly when playback is started/stopped or the speaker changes from another device. A single background monitor queries the speaker (~3 s) for all connected clients instead of each browser polling it. Falls back to polling if the stream is unavailable.

### Fixed
- **Add speaker by IP** (0.6.3): an unreachable IP no longer blocks a request for minutes (up to ~10 min: 30 port/path combinations × 5 s timeout × retries). Ports are now probed in parallel with a 1 s TCP connect, only open ports are queried, without retries, and the whole attempt is capped at 15 s.

### Changed
- Gunicorn threads raised from 4 to 16 (each open player holds one for its event stream; max 10 streams)

## [v0.6.0] - 2026-11-23

### Added
- **New web player GUI** replacing the API dev console: now playing card with live status, speaker picker with scan / add by IP, station list, activity log panel with raw API responses, API key setting, light/dark theme
- `/status` now includes `stream` (`url`, `transcoding`, `format`) while streaming

### Fixed
- **Live-stream DLNA flags**: streaming server now sends `DLNA.ORG_OP=00` and live-stream `DLNA.ORG_FLAGS=8D100000` (instead of seekable-content flags) in `contentFeatures.dlna.org`
- **Security**: patched CVEs in dependencies; `urllib3>=2.8.0` (CVE-2026-97689)

### Changed
- **CI / Docker image**: `latest` is rebuilt monthly (and on demand) from a fresh base image without layer cache, so Debian security patches are picked up without code changes; image now carries the real `APP_VERSION`; `vX.Y` tags are published as image tags
- **Config**: removed unused `performance.gunicorn_workers` / `gunicorn_threads` and `dlna_advanced` options — Gunicorn is fixed at 1 worker / 4 threads in the Dockerfile
- **Versioning**: `scripts/version.sh` is the single source of the version for CI, `make` and `deploy.sh`; `PATCH` now counts changes merged into `main` (first-parent commits) since the `vX.Y` tag, so each merge bumps it by one
- **Dev tooling**: updated dev dependencies (pytest 9, ruff, black, mypy, bandit), migrated ruff config to `[tool.ruff.lint]`, removed unused test deps and markers; `make docker-build`/`docker-test` now pass `APP_VERSION`
- **Docs**: README quick start uses the Docker Hub image, corrected build/deploy instructions, project structure, rate-limiting and API key notes; TESTING.md matches the actual test suite; removed obsolete `.env.example`

## [v0.5] - 2026-05-28

### Added
- **Mobile-first GUI**: Responsive layout for phones and tablets
  - Sticky quick-action bar (Play, Stop, Status) always visible at top
  - Section headings become collapsible accordions on mobile
  - Accordion state persisted in `localStorage` across page reloads
  - Output log panel dynamically fills freed space when accordions are collapsed
  - Desktop layout (horizontal split with draggable splitter) unchanged

### Fixed
- **DLNA compatibility with strict renderers (e.g. Samsung HW-Q90R)**:
  - Added `HEAD` request handler to streaming server — devices like Samsung verify the stream URI with HEAD before accepting `SetAVTransportURI`; without it, `716 Resource not found` was returned
  - Added DLNA compliance headers to HTTP responses: `transferMode.dlna.org: Streaming` and `contentFeatures.dlna.org` with proper MP3 profile and flags
  - Added DIDL-Lite XML metadata to `SetAVTransportURI` — strict DLNA renderers require `CurrentURIMetaData` with content class and protocol info
  - Fixed XML escaping of DIDL-Lite in SOAP body (must be escaped as a string value per UPnP spec)

### Changed
- **Auto-versioning**: Version is now baked into the Docker image at build time via `APP_VERSION` build arg and env var. `MAJOR.MINOR` comes from a git tag (e.g. `v0.5`), patch number is the commit count since that tag. To bump `MAJOR.MINOR`, create a new tag on the desired commit (e.g. `git tag v0.6 <commit>`).

## [v0.4] - 2026-01-17

User experience improvements, enhanced codec detection, and persistent stream format caching.

### Added
- **Default Device IP Configuration**: New `dlna.default_device_ip` config option for automatic device selection on startup
- **GUI Enter Key Support**: All input fields now respond to Enter key for improved usability
- **Enhanced AAC Detection**: Improved codec detection for AAC streams (supports audio/aac, audio/aacp, audio/adts, audio/m4a)
- **Stream Format Cache**: Persistent cache for stream format detection results with configurable TTL
  - Stores Content-Type and ffprobe results in `/data/stream_format_cache.json`
  - Configurable TTL (default: 24 hours)
  - Reduces unnecessary HEAD requests and ffprobe analysis
- **FFprobe Fallback**: Automatic fallback to ffprobe when streams don't return Content-Type header
  - Analyzes first 2 seconds / 1MB of stream
  - Maps codec (aac, mp3, flac, vorbis, opus) to MIME type
  - Results are cached for future requests
- **Persistent Storage Configuration**: New `storage.data_dir` config option for Docker volume mounting
- **Stream Detection Logging**: Enhanced logging for troubleshooting transcoding decisions

### Changed
- **Auto-Select Logic**: Devices configured with `default_device_ip` are automatically selected after discovery scan
- **Codec Detection**: Expanded AAC MIME type recognition for better passthrough mode detection
- **Logging Verbosity**: Added detailed logs for stream redirects, Content-Type detection, and transcoding decisions
- **Data Directory**: All persistent data now stored in configurable directory (default: `/data`)

### Fixed
- **AAC Passthrough**: Streams with AAC codec now correctly use passthrough mode when device supports it
  - Fixed issue with streams that redirect and don't return Content-Type header
  - FFprobe fallback ensures codec is detected even without HTTP headers
- **Stream Redirect Handling**: Better logging for streams with multiple redirects

## [v0.3] - 2026-01-16

Major security, performance, and reliability improvements with principal developer code review.

### Added - Security
- **API Key Authentication**: Optional authentication for protected endpoints (`/play`, `/stop`, `/devices/select`)
- **Rate Limiting Support**: Optional Flask-Limiter integration for API abuse prevention
- **FFmpeg Protocol Whitelist**: Restricts FFmpeg to safe protocols (http,https,tcp,tls)
- **SECURITY.md**: Comprehensive security documentation and deployment guide
- **Input Sanitization**: Header length limits for additional security

### Added - Reliability
- **Process-Level File Locking**: fcntl-based locking for state.json to prevent race conditions
- **FFmpeg PID Tracking**: Automatic cleanup of orphaned FFmpeg processes on startup
- **FFmpeg Stderr Buffer Limit**: Prevents memory leaks from excessive FFmpeg output (configurable max lines)
- **HTTP Connection Pooling**: Reusable HTTP connections with retry logic and exponential backoff
- **Application Context Pattern**: Thread-safe state management (foundation for future improvements)

### Added - Configuration
- **Configurable Timeouts**: All network timeouts now in config.yaml (http_request, stream_detection, device_discovery, ffmpeg_startup)
- **Performance Tuning**: Configurable Gunicorn workers/threads, connection pool sizes
- **FFmpeg Settings**: Configurable chunk size, stderr limits, protocol whitelist

### Changed
- **Single-Worker Architecture**: Recommended gunicorn_workers=1 for consistent state management
- **HTTP Client Migration**: All requests now use connection pooling via HTTPClient singleton
- **AudioStreamer Parameters**: Now accepts chunk_size, max_stderr_lines, protocol_whitelist
- **Config Expansion**: Extended config.yaml with security, performance, timeouts, and FFmpeg sections

### Fixed
- **Multi-Worker Race Conditions**: Process-level locking prevents state corruption
- **Orphaned FFmpeg Processes**: PID tracking ensures cleanup after crashes
- **HTTP Port Conflicts**: SO_REUSEADDR with proper state management
- **Memory Leaks**: FFmpeg stderr buffer limiting prevents unbounded growth
- **Connection Exhaustion**: Connection pooling reuses HTTP connections

### Documentation
- Added SECURITY.md with comprehensive deployment security guide
- Updated README.md with new features and detailed security configuration
- Enhanced config.example.yaml with all available options and security warnings
- Added security checklist for production deployments
- Clarified authentication model: disabled by default, optional to enable
- Documented protected vs public endpoints
- Added API key generation and management best practices

## [v0.2] - 2026-01-16

Major update with testing infrastructure, development tools, and improved reliability.

### Added
- **Development Console**: Interactive web UI at `/` for API testing and device management
- **Comprehensive Test Suite**: Unit and integration tests with pytest
- **CI/CD Pipeline**: GitHub Actions workflow for automated testing and Docker builds
- **Device Caching**: Persistent cache with configurable TTL (default 2 hours)
- **Background Device Scan**: Automatic device discovery on startup with incremental caching
- **SSRF Protection**: Security validation for stream URLs
- **Development Tools**: Automated setup script (`dev-setup.sh`) and dev dependencies
- **Code Quality**: Linting (ruff), formatting (black), and security scanning (bandit)

### Changed
- Improved error handling and validation across all API endpoints
- Enhanced `/status` endpoint with consistent response format
- Better logging for device discovery failures
- Config file moved to `config.example.yaml` template (user creates own `config.yaml`)

### Fixed
- Device cache reliability issues
- Test failures and pytest-asyncio compatibility
- GUI timeout field handling
- Inconsistent /status responses

## [v0.1] - 2024

Initial release with core DLNA streaming functionality.

### Added
- **DLNA Streaming**: Stream internet radio to DLNA/UPnP devices
- **Smart Transcoding**: Automatic passthrough when device supports format, FFmpeg transcoding when needed
- **SSDP Discovery**: Network device discovery with UPnP
- **REST API**: Full control via HTTP endpoints
  - `/play` - Start playback
  - `/stop` - Stop playback
  - `/status` - Get current status
  - `/scan` - Scan for devices
- **Docker Deployment**: Docker and docker-compose support
- **Configuration**: YAML-based configuration with reverse proxy support
- **Multi-device Support**: Device selection and management

### Supported Features
- Format detection via HTTP headers
- Device capability checking (GetProtocolInfo)
- Gunicorn production server
- Health check endpoint
- Tested with Panasonic SC-PMX9 and Samsung HW-Q90R
