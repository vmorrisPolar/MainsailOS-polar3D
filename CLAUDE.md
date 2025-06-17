# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

MainsailOS is a Raspberry Pi OS-based distribution for 3D printers that includes Klipper firmware, Moonraker API server, and Mainsail web interface. This fork specifically integrates Polar Cloud connectivity via Socket.IO.

## Development Commands

### Image Building
Images are built automatically via GitHub Actions when changes are pushed. For local development:

```bash
# Local builds use CustomPiOS framework
# See: https://github.com/guysoft/CustomPiOS
```

### Service Management
```bash
# Polar Cloud service management
sudo systemctl status polar_cloud
sudo systemctl restart polar_cloud
sudo journalctl -u polar_cloud -f

# Other core services
sudo systemctl status klipper
sudo systemctl status moonraker
sudo systemctl status nginx
```

### Testing
```bash
# Test Socket.IO connectivity
cd /home/pi/polar-cloud
./venv/bin/python test_socketio.py

# Test Moonraker plugin
cd /home/pi/polar-cloud
python3 test_plugin.py
```

## Architecture

### Core Components
- **Modules**: Located in `modules/` directory
  - `generic/`: Common modules for all platforms
  - `raspberry/`: Raspberry Pi-specific modules
  - `armbian/`: Armbian-specific modules
  - `special/`: Board-specific modules

### Polar Cloud Integration
This fork adds Polar Cloud connectivity with these key components:

1. **Backend Service** (`modules/generic/files/polar-cloud/polar_cloud.py`)
   - Socket.IO client connecting to `https://printer4.polar3d.com`
   - Uses "MNSL" client identifier to distinguish from OctoPrint ("OP") and native Polar3D ("P3D")
   - Handles registration, status monitoring, and print job management

2. **Moonraker Plugin** (`polar_cloud_moonraker.py`)
   - Provides REST API endpoints for web interface
   - Installed to `/home/pi/moonraker/moonraker/components/polar_cloud.py`

3. **Web Interface** (`polar_cloud_web.html`)
   - Standalone interface accessible at `http://printer-ip/polar-cloud/`
   - Independent of Mainsail's Vue.js structure

4. **System Service** (`polar_cloud.service`)
   - Systemd service with auto-restart
   - Uses virtual environment at `/home/pi/polar-cloud/venv/`

### Socket.IO Implementation
The integration uses Socket.IO instead of raw WebSockets because:
- Polar Cloud servers require Socket.IO protocol
- Provides automatic reconnection and transport fallback
- Event-based messaging system
- Better error handling and connection management

## File Structure

```
modules/generic/
├── 56-polar-cloud              # Installation module
└── files/polar-cloud/
    ├── polar_cloud.py          # Main service
    ├── polar_cloud_moonraker.py # Moonraker plugin
    ├── polar_cloud_web.html    # Web interface
    ├── polar_cloud.service     # Systemd service
    ├── polar_cloud.conf        # Configuration template
    ├── requirements.txt        # Python dependencies
    ├── test_socketio.py        # Connection test
    └── diagnose_moonraker.py   # Diagnostic tool
```

## Configuration

### Build Configuration
- `config.yml`: Defines image variants (Raspberry Pi, Orange Pi, etc.)
- `cliff.toml`: Changelog generation using conventional commits

### Polar Cloud Configuration
Configuration stored in `/home/pi/printer_data/config/polar_cloud.conf`:
- Server URL: `https://printer4.polar3d.com` (Socket.IO endpoint)
- User credentials: username/PIN from Polar Cloud registration
- Machine type: Cartesian, Delta, etc.
- Debug settings: verbose logging flag

## Dependencies

### Python Packages (Virtual Environment)
- `python-socketio[client]>=5.0` - Socket.IO client
- `cryptography>=3.0` - RSA key generation
- `Pillow>=8.0` - Image processing
- `requests>=2.25` - HTTP client
- `aiohttp>=3.7` - Async HTTP for Socket.IO

### System Packages
- `python3-socketio` - System Socket.IO package
- `python3-pycryptodome` - Cryptography support
- `python3-requests` - HTTP client
- `python3-pil` - Image processing

## Commit Conventions

Follow conventional commits format:
- `feat:` - New features
- `fix:` - Bug fixes
- `refactor:` - Code refactoring
- `docs:` - Documentation changes
- `chore:` - Maintenance tasks

## Polar Cloud Registration Protocol

### Registration Flow
The Polar Cloud uses a specific registration protocol that must be followed exactly:

1. **Initial Connection**: Connect to `https://printer4.polar3d.com` via Socket.IO
2. **Welcome Event**: Server sends `welcome` event with challenge string
3. **Registration Request**: Send `register` event with user credentials and public key
4. **Registration Response**: Server responds with `registerResponse` event
5. **Disconnect/Reconnect**: Disconnect and reconnect as per protocol
6. **Hello Authentication**: Use `hello` event with serial number for subsequent connections

### Critical Registration Response Format
The `registerResponse` must be handled as a JSON object with exact format:
```json
{
    "serialNumber": "assigned-printer-serial",
    "status": "SUCCESS", 
    "reason": "SUCCESS"
}
```

**Common Bug**: If the code receives `"SUCCESS"` as a string instead of the JSON object above, it indicates the registration request format is incorrect or the server is not recognizing the request properly.

### Hello Command Field Requirements
The `hello` command must include these exact field names:
- `MAC` (not `macAddress`) - Network MAC address
- `printerMake` - Must be the actual printer model selected by user (e.g., "Ender 3", "Prusa Mini") for correct slicing profiles
- `camOff` - Integer (0=camera enabled, 1=camera disabled) to inform Polar Cloud UI layout
- `mfgSn` - Manufacturer serial number (use "MNSL-" prefix + MAC for Mainsail identification)

### Registration State Management
- **First-time registration**: No `serial_number` in config → sends `register` command
- **Subsequent connections**: Has `serial_number` in config → sends `hello` command
- **Serial number storage**: Saved to `/home/pi/printer_data/config/polar_cloud.conf`

### Socket.IO Event Handlers Required
Essential event handlers for proper registration:
- `connect` - Track connection state and update status file
- `disconnect` - Reset connection state, hello flag, and update status file
- `connect_error` - Handle connection failures
- `welcome` - Receive challenge and determine register vs hello
- `registerResponse` - Handle registration success/failure and save serial number
- `helloResponse` - Handle authentication success/failure and update status file

### Real-time Status Communication
The service writes real-time status to `/tmp/polar_cloud_status.json` which includes:
- `connected`: Socket.IO connection state
- `authenticated`: Hello authentication success state
- `serial_number`: Current assigned serial number
- `username`: Configured username
- `last_update`: Timestamp of last status update
- `webcam_enabled`: Camera configuration state

The Moonraker plugin reads this file to provide accurate status to the web interface.

## Troubleshooting

### Registration Issues
1. **"Registration failed: SUCCESS"**
   - Indicates server returned string "SUCCESS" instead of expected JSON object
   - Check registration request format matches protocol specification
   - Verify all required fields are present in register event

2. **Repeated Registration Attempts**
   - Service keeps trying to register instead of using hello command
   - Check if serial number is being saved to config file properly
   - Verify `registerResponse` handler is extracting and saving `serialNumber` field
   - Ensure disconnect/reconnect cycle completes after successful registration

3. **Socket.IO Connection Loops**
   - Service connects but immediately disconnects
   - Check event handlers are properly configured
   - Verify reconnection settings allow automatic reconnection
   - Review logs for connection errors or event handling exceptions

4. **Web Interface Shows Incorrect Status**
   - Web interface displays "Service Inactive" or outdated information
   - Check if status file `/tmp/polar_cloud_status.json` exists and is being updated
   - Restart both `polar_cloud` and `moonraker` services
   - Verify Moonraker plugin can read the status file

5. **Printer Type Not Displayed in Web Interface**
   - Dropdown shows "Select printer type..." instead of selected value
   - Caused by race condition between loading options and setting value
   - Check browser console for JavaScript errors
   - Ensure machine type is selected before printer type options load

### Common Issues
1. **Socket.IO Connection Failures**
   - Check server URL format (must be `https://` not `wss://`)
   - Verify virtual environment has correct packages
   - Test with `test_socketio.py` script

2. **Service Start Failures**
   - Check file permissions on `/home/pi/polar-cloud/`
   - Verify virtual environment is properly created
   - Check systemd service logs

3. **Web Interface Not Accessible**
   - Ensure nginx configuration includes polar-cloud location
   - Verify files are in `/home/pi/polar-cloud/web/`
   - Check nginx error logs

### Development Workflow
1. Make changes to files in `modules/generic/files/polar-cloud/`
2. Test changes in development environment
3. Run appropriate tests (Socket.IO, plugin, etc.)
4. Commit with conventional commit format
5. Push to trigger GitHub Actions build

## Key Differences from Standard WebSocket Implementation

This implementation uses Socket.IO instead of raw WebSockets:
- Event-driven architecture with named events
- Automatic reconnection handling
- Protocol compatibility with Polar Cloud servers
- Built-in error handling and logging
- Transport fallback capabilities

When working with the Polar Cloud integration, always consider Socket.IO-specific patterns and avoid raw WebSocket approaches.