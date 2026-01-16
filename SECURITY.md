# Security Guide - Stream-to-DLNA

## Overview

This document describes the security architecture, best practices, and considerations when deploying Stream-to-DLNA.

## Security Features

### Input Validation

All user inputs are strictly validated:

- **IP Address Validation** (`validate_ip_address`):
  - Strict regex pattern matching
  - Range validation (0-255 per octet)
  - Prevents command injection, path traversal

- **URL Validation** (`validate_stream_url`):
  - SSRF protection (blocks localhost, AWS metadata, IPv6 loopback)
  - Scheme whitelist (http/https only)
  - Allows private IPs for local streaming use cases

- **Boolean Validation** (`validate_boolean_string`):
  - Exact match only ('true' or 'false')
  - Case-sensitive

### Process-Level File Locking

- State file (`/app/state.json`) uses `fcntl` for inter-process locking
- Prevents race conditions in multi-worker environments
- Shared lock for reads, exclusive lock for writes

### FFmpeg Security

- **Protocol Whitelist**: FFmpeg is restricted to safe protocols (http,https,tcp,tls)
- **PID Tracking**: Orphaned processes are detected and cleaned up on startup
- **Stderr Buffer Limit**: Prevents memory exhaustion from excessive FFmpeg output
- **Configurable**: All security parameters are in `config.yaml`

### HTTP Client with Connection Pooling

- Reuses connections for better performance
- Configurable pool size
- Built-in retry logic with exponential backoff
- Protects against connection exhaustion

### Authentication & Authorization

#### Default Configuration: OPEN ACCESS

**CRITICAL SECURITY WARNING:**

By default, Stream-to-DLNA runs with **NO AUTHENTICATION**. This means:
- Suitable for **trusted home networks only**
- **NEVER expose to internet** without authentication
- **NEVER run in production** without authentication

**Default config values:**
```yaml
security:
  api_auth_enabled: false  # NO AUTH - all endpoints open
  rate_limit_enabled: false  # NO LIMITS - can be abused
```

#### Enabling API Key Authentication (REQUIRED for Production)

**Step 1:** Generate strong API key
```bash
# Generate 32-character random key
openssl rand -hex 32
# Example output: a1b2c3d4e5f6...
```

**Step 2:** Enable authentication in `config.yaml`
```yaml
security:
  api_auth_enabled: true
  api_key: "a1b2c3d4e5f6789..." # Your generated key
```

**Step 3:** Restart the application

**Step 4:** All protected endpoints now require API key:
```bash
# FAILS - No API key
curl -X POST http://localhost:5000/play
# Response: 401 Unauthorized

# WORKS - Valid API key
curl -X POST http://localhost:5000/play \
  -H "X-API-Key: a1b2c3d4e5f6789..."
# Response: 200 OK
```

#### Endpoint Access Control

**Protected Endpoints** (require `X-API-Key` when `api_auth_enabled: true`):
- `POST /devices/select` - Device selection (can affect playback)
- `POST /play` - Start playback (state-changing operation)
- `POST /stop` - Stop playback (state-changing operation)

**Public Endpoints** (always accessible, even with auth enabled):
- `GET /` - Web console (read-only UI)
- `GET /health` - Health check (monitoring)
- `GET /devices` - List devices (read-only)
- `GET /devices/current` - Current device info (read-only)
- `GET /status` - Playback status (read-only)

**Rationale:** Only state-changing operations require authentication. Read-only monitoring endpoints remain public for health checks and dashboards.

#### Rate Limiting (Recommended)

Enable rate limiting to prevent API abuse:

**Step 1:** Install Flask-Limiter
```bash
pip install Flask-Limiter==3.5.0
```

**Step 2:** Enable in `config.yaml`
```yaml
security:
  rate_limit_enabled: true
  rate_limit_default: "100 per hour"  # Adjust based on your needs
```

**Important:** Rate limiting applies to **ALL endpoints** when enabled, including public ones.

#### API Key Management Best Practices

**Storage:**
- Store in environment variables
- Use secrets management (Vault, AWS Secrets Manager)
- Restrict file permissions (`chmod 600 config.yaml`)
- Never commit to git
- Never log or expose in error messages

**Rotation:**
- Rotate API keys every 90 days
- Rotate immediately if compromised
- Use different keys for dev/staging/production

**Example with environment variable:**
```bash
# .env file (not committed to git)
STREAM_TO_DLNA_API_KEY="a1b2c3d4e5f6789..."

# docker-compose.yaml
environment:
  - API_KEY=${STREAM_TO_DLNA_API_KEY}
```

```yaml
# config.yaml
security:
  api_auth_enabled: true
  api_key: ${API_KEY}  # Read from environment
```

## Deployment Security Considerations

### Critical: Docker Host Network Mode

**Issue:** Docker Compose uses `network_mode: host` for SSDP multicast discovery.

**Risk:** The container has unrestricted access to all network interfaces and ports on the host.

**Mitigations:**
1. Run container on a trusted network only
2. Use firewall rules to restrict container access
3. Consider using `macvlan` network for bridge mode networks (see README.md)

**Example iptables rules:**
```bash
# Allow only specific outbound connections
iptables -A OUTPUT -p tcp --dport 80 -j ACCEPT   # HTTP
iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT  # HTTPS
iptables -A OUTPUT -p udp --dport 1900 -j ACCEPT # SSDP
iptables -A OUTPUT -j DROP
```

### Critical: State File Exposure

**Issue:** `/app/state.json` contains device IPs and network topology.

**Risk:** If exposed via volume mount, reveals internal network structure.

**Mitigation:**
```yaml
# docker-compose.yaml
volumes:
  - ./config.yaml:/app/config.yaml:ro  # Read-only
  - state-data:/app                     # Named volume (not host path)
```

### Medium: Gunicorn Configuration

**Recommended Configuration:**
- **Workers:** 1 (prevents state inconsistency)
- **Threads:** 4+ (handles concurrent requests)

```yaml
# config.yaml
performance:
  gunicorn_workers: 1
  gunicorn_threads: 4
```

### Medium: Stream URL Validation

Private IPs (10.x, 172.16-31.x, 192.168.x.x) are **allowed** by default for local streaming.

To block all private IPs, edit `app/main.py`:
```python
# Uncomment lines 168-173 in validate_stream_url()
if hostname.startswith('10.'):
    return False
if hostname.startswith('172.') and 16 <= int(hostname.split('.')[1]) <= 31:
    return False
if hostname.startswith('192.168.'):
    return False
```

## Secure Deployment Checklist

- [ ] Enable API authentication in production (`api_auth_enabled: true`)
- [ ] Enable rate limiting (`rate_limit_enabled: true`)
- [ ] Use read-only config volume mount
- [ ] Use named Docker volume for state file (not host path)
- [ ] Set strong API key (minimum 32 characters, random)
- [ ] Configure firewall rules for host network mode
- [ ] Set Gunicorn workers to 1
- [ ] Review and adjust timeout values for your network
- [ ] Use HTTPS reverse proxy (nginx, Traefik) if exposing to WAN
- [ ] Enable Docker logging with rotation (see docker-compose.yaml)
- [ ] Regularly update dependencies (`pip install -U -r requirements.txt`)

## Reverse Proxy Configuration

### Nginx Example

```nginx
server {
    listen 443 ssl http2;
    server_name radio.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Pass API key from client
        proxy_set_header X-API-Key $http_x_api_key;
    }

    # Rate limiting (additional layer)
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
}
```

## Reporting Security Issues

**DO NOT** create public GitHub issues for security vulnerabilities.

Contact: [Your security contact email/method]

## Security Audit Log

| Date | Auditor | Findings | Status |
|------|---------|----------|--------|
| 2026-01-16 | Principal Developer | Multi-worker race conditions | Fixed |
| 2026-01-16 | Principal Developer | FFmpeg process leaks | Fixed |
| 2026-01-16 | Principal Developer | SSRF protection review | Implemented |
| 2026-01-16 | Principal Developer | Input validation audit | Comprehensive |

## License

Security features and documentation are part of Stream-to-DLNA and follow the MIT License.
