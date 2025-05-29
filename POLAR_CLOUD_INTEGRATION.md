# Polar Cloud Integration for MainsailOS

## Overview

This integration adds Polar Cloud connectivity to MainsailOS, allowing users to register their 3D printers with Polar Cloud for remote monitoring and management.

## Components

### 1. Backend Service (`polar_cloud.py`)
- **Location**: `/home/pi/polar_cloud/polar_cloud.py`
- **Purpose**: Main service that handles communication with Polar Cloud
- **Features**:
  - Registration with username/PIN
  - Automatic reconnection
  - Status monitoring
  - Configuration management

### 2. Moonraker Plugin (`polar_cloud_moonraker.py`)
- **Location**: `/home/pi/printer_data/moonraker/plugins/polar_cloud_moonraker.py`
- **Purpose**: Provides API endpoints for the web interface
- **Endpoints**:
  - `GET /server/polar_cloud/status` - Get current status
  - `POST /server/polar_cloud/register` - Register with Polar Cloud
  - `POST /server/polar_cloud/unregister` - Disconnect from Polar Cloud

### 3. Web Interface (`polar_cloud_ui.js`)
- **Location**: `/home/pi/mainsail/polar_cloud_ui.js`
- **Purpose**: Provides user interface for Polar Cloud management
- **Features**:
  - Smart injection into Mainsail's MACHINE tab
  - Fallback floating button if injection fails
  - Modal interface for registration
  - Real-time status updates

### 4. System Service (`polar_cloud.service`)
- **Location**: `/etc/systemd/system/polar_cloud.service`
- **Purpose**: Manages the Polar Cloud service lifecycle
- **Features**:
  - Auto-start on boot
  - Restart on failure
  - Proper user permissions

## Installation Process

The integration is installed via the `56-polar-cloud` module during image build:

1. **Dependencies**: Installs `python3-pycryptodome` and other required packages
2. **Service Files**: Copies service files to appropriate locations
3. **Moonraker Configuration**: Adds plugin configuration to `moonraker.conf`
4. **Web Interface**: Injects JavaScript into Mainsail's `index.html`
5. **Permissions**: Sets proper file ownership and permissions
6. **Service Activation**: Enables the systemd service

## User Experience

After building and flashing the image:

### Option 1: MACHINE Tab Integration (Primary)
- Navigate to the MACHINE tab in Mainsail
- Look for the "Polar Cloud Connection" card
- The card should appear alongside System Loads and Update Manager

### Option 2: Floating Button (Fallback)
- If the MACHINE tab integration fails, a blue cloud button (☁️) will appear in the bottom-right corner
- Click the button to open the Polar Cloud interface in a modal

### Registration Process
1. Enter your Polar Cloud email/username
2. Enter your PIN (obtained from Polar Cloud)
3. Select your machine type (Cartesian, Delta, CoreXY, Polar)
4. Select your printer type
5. Click "Connect"

### Status Indicators
- **Green dot**: Connected and registered
- **Orange dot**: Service active but not registered
- **Gray dot**: Service inactive

## Configuration Files

### Moonraker Configuration
```ini
[polar_cloud]
# Polar Cloud plugin configuration

[update_manager polar_cloud]
type: git_repo
channel: dev
path: ~/polar_cloud
origin: https://github.com/mainsail-crew/polar-cloud.git
managed_services: polar_cloud
primary_branch: main
```

### Service Configuration
```ini
[Unit]
Description=Polar Cloud Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/polar_cloud
ExecStart=/usr/bin/python3 /home/pi/polar_cloud/polar_cloud.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

### UI Not Appearing
1. Check browser console for JavaScript errors
2. Verify the script is loaded: look for `polar_cloud_ui.js` in Network tab
3. Look for the floating button as a fallback
4. Check that Mainsail is fully loaded before the script runs

### Service Issues
```bash
# Check service status
sudo systemctl status polar_cloud

# View service logs
sudo journalctl -u polar_cloud -f

# Restart service
sudo systemctl restart polar_cloud
```

### Moonraker Plugin Issues
```bash
# Check Moonraker logs
tail -f ~/printer_data/logs/moonraker.log

# Restart Moonraker
sudo systemctl restart moonraker
```

### API Testing
```bash
# Test status endpoint
curl http://localhost/server/polar_cloud/status

# Test registration (replace with actual credentials)
curl -X POST http://localhost/server/polar_cloud/register \
  -H "Content-Type: application/json" \
  -d '{"username":"your@email.com","pin":"1234","machine_type":"Cartesian","printer_type":"Cartesian"}'
```

## File Locations Summary

```
/home/pi/polar_cloud/
├── polar_cloud.py              # Main service
├── polar_cloud.conf            # Configuration
└── polar_cloud.service         # Service definition

/home/pi/printer_data/moonraker/plugins/
└── polar_cloud_moonraker.py    # Moonraker plugin

/home/pi/mainsail/
└── polar_cloud_ui.js           # Web interface

/etc/systemd/system/
└── polar_cloud.service         # System service

/home/pi/printer_data/config/
└── moonraker.conf              # Updated with plugin config
```

## Build Requirements

- Fixed package name: `python3-pycryptodome` (not `python3-cryptodome`)
- Proper directory creation before file operations
- Correct file ownership and permissions
- Service installation and activation

## Expected Behavior

1. **After Boot**: Polar Cloud service starts automatically
2. **Web Interface**: Loads when Mainsail is accessed
3. **Registration**: Users can register via web interface
4. **Status Updates**: Real-time status display
5. **Persistence**: Configuration survives reboots
6. **Updates**: Managed via Moonraker's update manager

## Testing

A test file `test_polar_ui.html` is included to verify the JavaScript functionality locally before building the full image.

## Notes

- The integration uses multiple fallback strategies to ensure the UI appears
- All API calls are handled through Moonraker for security
- The service automatically handles reconnection and error recovery
- Configuration is stored in standard locations for easy management 