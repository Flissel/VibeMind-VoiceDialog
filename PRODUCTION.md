# Production Deployment Guide

## Overview

This guide covers deploying Voice Dialog to a production environment with proper security, monitoring, and reliability.

## Current Status: NOT Production Ready

**Major gaps that MUST be addressed:**

1. ✅ API key management (fixed - use `.env` template)
2. ✅ Structured logging (implemented)
3. ✅ Configuration management (implemented)
4. ✅ Unicode handling (fixed)
5. ❌ IPC authentication (still using NULL DACL)
6. ❌ Comprehensive error handling (partial)
7. ❌ Health monitoring endpoints (missing)
8. ❌ Metrics collection (missing)
9. ❌ Deployment packaging (missing)
10. ❌ Multi-instance support (not tested)

## Pre-Deployment Checklist

### 1. Security Audit

- [ ] **Review SECURITY.md** and address all items
- [ ] Revoke any exposed API keys
- [ ] Generate production API keys with usage limits
- [ ] Implement IPC authentication (see "IPC Security" below)
- [ ] Enable input validation on all endpoints
- [ ] Configure rate limiting
- [ ] Set up secrets management (Azure Key Vault, AWS Secrets Manager, etc.)

### 2. Configuration

- [ ] Copy `.env.template` to `.env`
- [ ] Set production API keys
- [ ] Configure MoireTracker path for production environment
- [ ] Set log level to `INFO` or `WARNING`
- [ ] Configure log rotation (max 10MB, keep 5 backups)
- [ ] Set appropriate timeouts

**Production `.env` example:**
```bash
OPENAI_API_KEY=sk-prod-... # Production key with usage limits
ELEVENLABS_API_KEY=... # If using TTS
MOIRE_TRACKER_PATH=C:\Program Files\VoiceDialog\MoireTracker
LOG_LEVEL=INFO
LOG_FILE=C:\ProgramData\VoiceDialog\Logs\voice_dialog.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=10
```

### 3. Build and Test

- [ ] Build MoireTracker in Release mode
- [ ] Run full integration test suite: `python tests/test_end_to_end.py`
- [ ] Verify all 8 tests pass
- [ ] Test error scenarios (MoireTracker crash, network issues, etc.)
- [ ] Load testing (concurrent requests, sustained load)
- [ ] Memory leak testing (run for 24+ hours)

### 4. Infrastructure

- [ ] Install system dependencies
- [ ] Configure Windows service or systemd (Linux)
- [ ] Set up log aggregation (Splunk, ELK stack, etc.)
- [ ] Configure monitoring (Prometheus, Datadog, etc.)
- [ ] Set up alerting (PagerDuty, etc.)
- [ ] Configure backup and disaster recovery

## Installation Steps

### 1. System Requirements

**Minimum:**
- Windows 10/11 or Windows Server 2019+
- 4 GB RAM
- 2 CPU cores
- 1 GB disk space
- Visual Studio 2022 Build Tools (for MoireTracker)

**Recommended:**
- Windows 11 or Windows Server 2022
- 8 GB RAM
- 4 CPU cores
- 10 GB disk space (for logs)
- Dedicated GPU (for better MoireTracker performance)

### 2. Python Environment

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Build MoireTracker

```bash
cd C:\Path\To\Moire

# Configure
"tools\cmake-3.28.1-windows-x86_64\bin\cmake.exe" -B build -G "Visual Studio 17 2022" -A x64

# Build Release
"tools\cmake-3.28.1-windows-x86_64\bin\cmake.exe" --build build --config Release --target MoireTracker

# Verify
build\Release\MoireTracker.exe --version
```

### 4. Configuration

```bash
cd C:\Path\To\voice_dialog

# Copy template
copy .env.template .env

# Edit .env with production values
notepad .env
```

### 5. Validation

```bash
# Test configuration
python -c "from python.config import validate_config; validate_config(strict=True)"

# Test logging
python -c "from python.logger import get_logger; logger = get_logger('test'); logger.info('Test message')"

# Run health check
python python/tests/test_end_to_end.py
```

## Monitoring

### Health Endpoints

Implement these health check endpoints (TODO):

```python
# /health - Basic health check
{
  "status": "healthy",
  "timestamp": "2025-01-10T12:34:56Z",
  "version": "1.0.0"
}

# /health/ready - Ready to accept requests
{
  "status": "ready",
  "moire_connected": true,
  "api_key_valid": true
}

# /health/live - Service is alive
{
  "status": "alive",
  "uptime_seconds": 3600
}
```

### Metrics to Monitor

1. **Service Metrics:**
   - Uptime
   - Request rate
   - Error rate
   - Response latency (p50, p95, p99)

2. **MoireTracker Metrics:**
   - Connection status
   - Desktop scan success rate
   - Element detection count
   - IPC latency

3. **Resource Metrics:**
   - CPU usage
   - Memory usage
   - Disk space (logs)
   - Process count

### Logging

**Log Levels:**
- `DEBUG`: Detailed diagnostic information (not for production)
- `INFO`: Normal operation events
- `WARNING`: Warning messages (recoverable errors)
- `ERROR`: Error events (requires attention)
- `CRITICAL`: Critical failures (service degradation)

**Log Retention:**
- Keep 10 rotating log files (100MB total)
- Archive to long-term storage daily
- Retain archives for 30 days (compliance)

## IPC Security Hardening

### Current Vulnerability

```cpp
// INSECURE: NULL DACL allows any process access
SetSecurityDescriptorDacl(&sd, TRUE, NULL, FALSE);
```

### Secure Implementation (TODO)

```cpp
// Create proper ACL restricting access
PSECURITY_DESCRIPTOR pSD = (PSECURITY_DESCRIPTOR)LocalAlloc(LPTR, SECURITY_DESCRIPTOR_MIN_LENGTH);
InitializeSecurityDescriptor(pSD, SECURITY_DESCRIPTOR_REVISION);

// Create ACL allowing only specific users/groups
PACL pACL = CreateRestrictiveACL();  // Implementation needed
SetSecurityDescriptorDacl(pSD, TRUE, pACL, FALSE);

sa.lpSecurityDescriptor = pSD;
```

### Shared Secret Authentication (TODO)

Add authentication to IPC commands:

```python
# Client sends HMAC signature with each command
hmac_key = os.getenv('MOIRE_IPC_SECRET')
signature = hmac.new(hmac_key, command_bytes, hashlib.sha256).digest()

# Server validates signature before processing
if not validate_signature(command, signature):
    raise AuthenticationError("Invalid signature")
```

## Deployment Options

### Option 1: Windows Service

Use `nssm` (Non-Sucking Service Manager):

```bash
# Download nssm from https://nssm.cc/
nssm install VoiceDialog "C:\Path\To\venv\Scripts\python.exe" "C:\Path\To\voice_dialog\python\agent_orchestrator.py"

# Configure
nssm set VoiceDialog AppDirectory "C:\Path\To\voice_dialog\python"
nssm set VoiceDialog AppStdout "C:\ProgramData\VoiceDialog\Logs\service.log"
nssm set VoiceDialog AppStderr "C:\ProgramData\VoiceDialog\Logs\service_error.log"

# Start
nssm start VoiceDialog
```

### Option 2: Task Scheduler

Create scheduled task to run on system startup:

```bash
schtasks /create /tn "VoiceDialog" /tr "C:\Path\To\venv\Scripts\python.exe C:\Path\To\voice_dialog\python\agent_orchestrator.py" /sc onstart /ru SYSTEM
```

### Option 3: Docker (Future)

```dockerfile
# TODO: Create Dockerfile
FROM python:3.11-windowsservercore
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "python/agent_orchestrator.py"]
```

## Disaster Recovery

### Backup Strategy

**What to backup:**
- Configuration files (`.env`, `config.json`)
- Calibration data (`grid_calibration.json`)
- Log files (recent)
- Application state (if any)

**Backup schedule:**
- Configuration: On change + daily
- Logs: Daily rotation to archive storage
- State: Hourly if stateful

### Recovery Procedures

**Service failure:**
1. Check logs for errors
2. Verify MoireTracker is running
3. Restart service
4. If fails, restore from backup and retry

**Data corruption:**
1. Stop service
2. Restore configuration from backup
3. Recalibrate if needed
4. Restart and validate

## Performance Tuning

### Optimization Targets

- Startup time: < 10 seconds
- IPC latency: < 100ms
- Desktop scan: < 2 seconds
- Memory usage: < 500MB
- CPU usage: < 20% (idle), < 50% (active)

### Tuning Parameters

**MoireTracker:**
- ROI size (trade-off: accuracy vs speed)
- Scan interval (how often to rescan desktop)
- Detection threshold (trade-off: recall vs precision)

**Voice Dialog:**
- Log level (DEBUG = slower)
- Timeout values (balance responsiveness vs reliability)
- Reconnect attempts (balance recovery vs fail-fast)

## Troubleshooting

### Common Issues

**1. MoireTracker won't start**
- Check log: `voice_dialog.log`
- Verify exe exists at configured path
- Check dependencies (DirectX, Visual C++ Runtime)
- Try manual start for detailed error

**2. IPC connection failures**
- Verify MoireTracker is running
- Check shared memory permissions
- Look for firewall/antivirus interference

**3. High CPU usage**
- Check if desktop scanning too frequent
- Verify GPU acceleration enabled
- Review log level (DEBUG adds overhead)

**4. Memory leaks**
- Monitor with Task Manager over time
- Check for unclosed resources in logs
- May need process restart (schedule nightly)

## Rollback Plan

If deployment fails:

1. Stop new service
2. Restore previous version from backup
3. Verify configuration
4. Start previous version
5. Investigate failure in logs
6. Fix issues in development
7. Retry deployment

## Support Contacts

- Technical Lead: [Contact info]
- On-call: [PagerDuty/phone]
- Vendor Support: [If applicable]

## Next Steps

After initial deployment:

1. Monitor for 24 hours continuously
2. Review logs daily for first week
3. Collect performance metrics
4. User feedback sessions
5. Plan next iteration improvements
