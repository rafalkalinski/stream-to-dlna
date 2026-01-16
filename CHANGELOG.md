# Changelog

All notable changes to this project will be documented in this file.

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
