# Polar Cloud Integration for MainsailOS

## Overview

This integration adds Polar Cloud connectivity to MainsailOS, allowing users to register their 3D printers with Polar Cloud for remote monitoring and management. The integration uses Socket.IO for real-time communication with the Polar Cloud servers.

## Components

### 1. Backend Service (`polar_cloud.py`)
- **Location**: `/home/pi/polar-cloud/polar_cloud.py`
- **Purpose**: Main service that handles Socket.IO communication with Polar Cloud
- **Features**:
  - Socket.IO client with automatic reconnection
  - Registration with username/PIN
  - Real-time status monitoring
  - Image upload capabilities
  - Print job management
  - Configuration management

### 2. Moonraker Plugin (`polar_cloud_moonraker.py`)
- **Location**: `/home/pi/moonraker/moonraker/components/polar_cloud.py`
- **Purpose**: Provides API endpoints for the web interface
- **Endpoints**:
  - `GET /server/polar_cloud/status` - Get current status
  - `POST /server/polar_cloud/register` - Register with Polar Cloud
  - `POST /server/polar_cloud/unregister` - Disconnect from Polar Cloud
  - `GET/POST /server/polar_cloud/config` - Get/update configuration

### 3. Web Interface (`polar_cloud_web.html`)
- **Location**: `/home/pi/polar-cloud/web/index.html`
- **URL**: `http://your-printer-ip/polar-cloud/`
- **Purpose**: Standalone web interface for Polar Cloud management
- **Features**:
  - Real-time status display
  - Registration form with email/PIN and machine type selection
  - Modern, responsive design
  - Direct API integration

### 4. System Service (`polar_cloud.service`)
- **Location**: `/etc/systemd/system/polar_cloud.service`
- **Purpose**: Manages the Polar Cloud service lifecycle
- **Features**:
  - Auto-start on boot
  - Restart on failure
  - Proper user permissions
  - Virtual environment isolation

## Socket.IO Communication

### Why Socket.IO?
The integration uses Socket.IO instead of raw WebSockets because:
- **Protocol compatibility**: Polar Cloud servers use Socket.IO protocol
- **Automatic reconnection**: Built-in connection management
- **Event-based messaging**: Structured communication with named events
- **Fallback support**: Automatic transport fallback if WebSocket fails

### Connection Details
- **Server URL**: `https://printer4.polar3d.com` (Socket.IO endpoint)
- **Transport**: WebSocket (primary), with automatic fallbacks
- **Events**: Welcome, registration, status updates, print commands, etc.

## Installation Process

The integration is installed via the `56-polar-cloud` module during image build:

1. **Dependencies**: Installs Socket.IO client and other required packages
2. **Virtual Environment**: Creates isolated Python environment with dependencies
3. **Service Files**: Copies service files to appropriate locations
4. **Moonraker Configuration**: Adds plugin configuration to `moonraker.conf`
5. **Web Interface**: Creates standalone web interface accessible via nginx
6. **Permissions**: Sets proper file ownership and permissions
7. **Service Activation**: Enables the systemd service

## Dependencies

### Python Packages (installed in virtual environment)
- `python-socketio[client]>=5.0` - Socket.IO client library
- `cryptography>=3.0` - RSA key generation and signing
- `Pillow>=8.0` - Image processing for webcam uploads
- `requests>=2.25` - HTTP client for API calls
- `aiohttp>=3.7` - Async HTTP support for Socket.IO

### System Packages
- `python3-socketio` - System Socket.IO package
- `python3-pycryptodome` - Cryptography support
- `python3-requests` - HTTP client
- `python3-pil` - Image processing

## Client Identification

### MNSL Prefix
The integration uses the **"MNSL"** client identifier to distinguish Mainsail printers from other client types in the Polar Cloud:

- **OctoPrint printers**: Use "OP" prefix
- **Mainsail printers**: Use "MNSL" prefix  
- **Native Polar3D printers**: Use "P3D" prefix

This identifier is sent in:
- **Registration messages**: When registering the printer with Polar Cloud
- **Hello messages**: When establishing connection after registration
- **Status updates**: In ongoing status reports to the cloud

### Why This Matters
The client identifier helps Polar Cloud:
- Distinguish between different printer management systems
- Apply appropriate UI and feature sets
- Track usage statistics by client type
- Provide targeted support and updates

## User Experience

After building and flashing the image:

### Option 1: Web Interface (Recommended)

1. **Open your web browser** and navigate to your printer's IP address
2. **Add `/polar-cloud/` to the URL**: `http://your-printer-ip/polar-cloud/`
3. **You'll see the Polar Cloud configuration page** with:
   - Real-time connection status
   - Registration form with dynamic printer types
   - Connect/Disconnect buttons

### Option 2: Manual Configuration

1. **Edit the configuration file** in Mainsail:
   - Go to the **Config Files** section in Mainsail
   - Open `polar_cloud.conf`
   - Fill in your `username` and `pin`
   - Optionally adjust `machine_type` and `printer_type`
   - Save the file

2. **Restart the service**:
   ```bash
   sudo systemctl restart polar_cloud
   ```

3. **Check the logs** to verify registration:
   ```bash
   sudo journalctl -u polar_cloud -f
   ```

### How Both Methods Work

- **Web Interface**: Uses the Moonraker plugin API to update the config file and restart the service
- **Manual Configuration**: The service automatically detects credentials in the config file and attempts registration on startup
- **Socket.IO Connection**: The service establishes a Socket.IO connection and handles all real-time communication

### Status Indicators
- **Green dot**: Connected and registered via Socket.IO
- **Orange dot**: Service active but not registered
- **Gray dot**: Service inactive

## Why This Approach?

### Previous Approach (Failed)
We initially tried to inject JavaScript into Mainsail's interface, but this approach failed because:

1. **Mainsail is a Vue.js SPA**: It dynamically generates its interface, not static HTML
2. **Pre-built releases**: MainsailOS downloads pre-built Mainsail releases from GitHub
3. **No plugin system**: Mainsail doesn't have an official frontend plugin architecture
4. **Timing issues**: Our script would run before Vue.js rendered the interface

### Current Approach (Working)
The standalone web interface approach works because:

1. **Independent of Mainsail**: Doesn't rely on Mainsail's internal structure
2. **Direct API access**: Communicates directly with our Moonraker plugin
3. **Nginx integration**: Served alongside Mainsail via the same web server
4. **Reliable access**: Always available at a predictable URL
5. **Socket.IO backend**: Robust real-time communication with Polar Cloud

## Configuration Files

### Polar Cloud Configuration (`polar_cloud.conf`)
```ini
[polar_cloud]
# Polar Cloud Server Configuration (Socket.IO endpoint)
server_url = https://printer4.polar3d.com

# User Credentials
username = 
pin = 
serial_number = 

# Printer Configuration
machine_type = Cartesian
printer_type = Cartesian

# Image Settings
max_image_size = 150000

# Debug Settings
verbose = false

# Connection Settings
status_interval = 60
```

### Moonraker Configuration
```ini
[polar_cloud]
# Polar Cloud plugin configuration

[update_manager polar_cloud]
type: git_repo
channel: stable
path: ~/polar-cloud
origin: https://github.com/mainsail-crew/polar-cloud.git
managed_services: polar_cloud
primary_branch: main
```

### Service Configuration
```ini
[Unit]
Description=Polar Cloud Service
After=network.target moonraker.service
Wants=network.target

[Service]
Type=simple
User=pi
Group=pi
ExecStart=/home/pi/polar-cloud/venv/bin/python /home/pi/polar-cloud/polar_cloud.py
Restart=always
RestartSec=10
WorkingDirectory=/home/pi/polar-cloud
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

### Nginx Configuration
The installation automatically adds this location block to `/etc/nginx/sites-available/mainsail`:

```nginx
location /polar-cloud/ {
    alias /home/pi/polar-cloud/web/;
    try_files $uri $uri/ /polar-cloud/index.html;
}
```

## Testing

### Socket.IO Connection Test
A test script is provided to verify Socket.IO connectivity:

```bash
# Run the test script
cd /home/pi/polar-cloud
./venv/bin/python test_socketio.py
```

This will attempt to connect to the Polar Cloud Socket.IO server and report the results.

## Troubleshooting

### Socket.IO Connection Issues
1. Check that the service is running: `sudo systemctl status polar_cloud`
2. Verify the server URL in config: `cat /home/pi/printer_data/config/polar_cloud.conf`
3. Test Socket.IO connectivity: `cd /home/pi/polar-cloud && ./venv/bin/python test_socketio.py`
4. Check for firewall issues blocking HTTPS/WebSocket connections

### Web Interface Not Accessible
1. Check that nginx is running: `sudo systemctl status nginx`
2. Verify the nginx configuration was updated: `grep -A3 "polar-cloud" /etc/nginx/sites-available/mainsail`
3. Restart nginx: `sudo systemctl restart nginx`
4. Check nginx error logs: `sudo tail -f /var/log/nginx/error.log`

### Service Issues
```bash
# Check service status
sudo systemctl status polar_cloud

# View service logs
sudo journalctl -u polar_cloud -f

# Restart service
sudo systemctl restart polar_cloud

# Check virtual environment
/home/pi/polar-cloud/venv/bin/python -c "import socketio; print('Socket.IO available')"
```

### Common Issues
1. **"Module not found" errors**: Virtual environment may not be properly set up
2. **Connection timeouts**: Check network connectivity and firewall settings
3. **Registration failures**: Verify username/PIN credentials are correct
4. **Image upload failures**: Check webcam accessibility and image size limits

## File Locations Summary

```
/home/pi/polar-cloud/
├── polar_cloud.py              # Main service
├── polar_cloud.conf            # Configuration
├── polar_cloud.service         # Service definition
└── web/
    └── index.html              # Web interface

/home/pi/printer_data/moonraker/plugins/
└── polar_cloud_moonraker.py    # Moonraker plugin

/etc/systemd/system/
└── polar_cloud.service         # System service

/home/pi/printer_data/config/
└── moonraker.conf              # Updated with plugin config

/etc/nginx/sites-available/
└── mainsail                    # Updated with polar-cloud location
```

## Build Requirements

- Fixed package name: `python3-pycryptodome` (not `python3-cryptodome`)
- Proper directory creation before file operations
- Correct file ownership and permissions
- Service installation and activation
- Nginx configuration update

## Expected Behavior

1. **After Boot**: Polar Cloud service starts automatically
2. **Web Interface**: Accessible at `http://your-printer-ip/polar-cloud/`
3. **Registration**: Users can register via the standalone web interface
4. **Status Updates**: Real-time status display
5. **Persistence**: Configuration survives reboots
6. **Updates**: Managed via Moonraker's update manager

## Access Instructions

### For Users
1. **Navigate to**: `http://your-printer-ip/polar-cloud/`
2. **Or from Mainsail**: You can bookmark the Polar Cloud page for easy access
3. **Mobile friendly**: The interface works on phones and tablets

### Integration with Mainsail
While the interface is separate from Mainsail, users can:
- Open it in a new tab alongside Mainsail
- Bookmark it for quick access
- Use it on mobile devices while monitoring prints in Mainsail

## Notes

- The integration uses a standalone approach for maximum reliability
- All API calls are handled through Moonraker for security
- The service automatically handles reconnection and error recovery
- Configuration is stored in standard locations for easy management
- The web interface is responsive and works on all devices 