# Changelog

All notable changes to this project will be documented in this file.

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
- Added SECURITY.md with deployment security guide
- Updated README.md with new features and configuration options
- Enhanced config.example.yaml with all available options
- Added security checklist for production deployments

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
