# Polar Cloud Migration Guide: MainsailOS to goofoo3d-orion

This guide documents the process of porting the Polar Cloud integration from MainsailOS to the goofoo3d-orion project, which uses Fluidd instead of Mainsail and includes an LVGL touchscreen interface.

## Overview

### Source Project: MainsailOS-polar3D
- **Platform**: Raspberry Pi OS
- **Web Interface**: Mainsail (Vue.js)
- **Architecture**: Python Socket.IO service + Moonraker plugin
- **Build System**: CustomPiOS

### Target Project: goofoo3d-orion
- **Platform**: ARM64 (RK3328) Armbian
- **Web Interface**: Fluidd (Vue.js) + LVGL touchscreen
- **Architecture**: C++ with existing WebSocket infrastructure
- **Build System**: CMake + Debian packaging

## Core Components to Migrate

### 1. Python Socket.IO Service (`polar_cloud.py`)
**Source**: `/modules/generic/files/polar-cloud/polar_cloud.py`
**Target**: `/project_client/rk3328-goofoolvgl-skiprs/src/polar_cloud/`

This is the heart of the Polar Cloud integration. It can be reused with minimal modifications.

### 2. Moonraker Plugin (`polar_cloud_moonraker.py`)
**Source**: `/modules/generic/files/polar-cloud/polar_cloud_moonraker.py`
**Target**: `/moonraker/moonraker/components/polar_cloud.py`

The Moonraker plugin provides REST API endpoints and can be used as-is since both projects use Moonraker.

### 3. System Service (`polar_cloud.service`)
**Source**: `/modules/generic/files/polar-cloud/polar_cloud.service`
**Target**: `/project_client/rk3328-goofoolvgl-skiprs/MKSPKG/usr/lib/systemd/system/`

### 4. Configuration Template (`polar_cloud.conf`)
**Source**: `/modules/generic/files/polar-cloud/polar_cloud.conf`
**Target**: `/project_client/rk3328-goofoolvgl-skiprs/doc/default_files/`

### 5. Python Requirements
**Source**: `/modules/generic/files/polar-cloud/requirements.txt`
**Target**: Add to build system dependencies

## Migration Steps

### Phase 1: Core Service Integration

#### Step 1.1: Create Directory Structure
```bash
mkdir -p /project_client/rk3328-goofoolvgl-skiprs/src/polar_cloud
mkdir -p /project_client/rk3328-goofoolvgl-skiprs/MKSPKG/usr/lib/systemd/system
mkdir -p /project_client/rk3328-goofoolvgl-skiprs/MKSPKG/opt/polar-cloud
```

#### Step 1.2: Copy Core Files
Copy these files from MainsailOS:
- `polar_cloud.py` → `/MKSPKG/opt/polar-cloud/`
- `polar_cloud_moonraker.py` → `/moonraker/moonraker/components/`
- `requirements.txt` → `/MKSPKG/opt/polar-cloud/`
- `polar_cloud.conf` → `/doc/default_files/`

#### Step 1.3: Adapt Service File
Modify `polar_cloud.service` for goofoo3d paths:
```ini
[Unit]
Description=Polar Cloud Socket.IO Service for goofoo3d
After=network-online.target moonraker.service
Wants=network-online.target

[Service]
Type=simple
User=pi
ExecStart=/opt/polar-cloud/venv/bin/python /opt/polar-cloud/polar_cloud.py
Restart=always
RestartSec=10
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

#### Step 1.4: Update File Paths
In `polar_cloud.py`, update paths:
```python
# Change from:
CONFIG_FILE = '/home/pi/printer_data/config/polar_cloud.conf'
STATUS_FILE = '/home/pi/printer_data/logs/polar_cloud_status.json'

# To:
CONFIG_FILE = '/usr/local/etc/polar_cloud.conf'
STATUS_FILE = '/var/log/polar_cloud_status.json'
```

### Phase 2: Build System Integration

#### Step 2.1: Add Python Dependencies to CMakeLists.txt
Add to `/project_client/rk3328-goofoolvgl-skiprs/CMakeLists.txt`:
```cmake
# Polar Cloud Python dependencies
set(POLAR_CLOUD_DEPS
    python3-venv
    python3-pip
    python3-dev
    python3-socketio
    python3-aiohttp
    python3-cryptography
    python3-pil
)
```

#### Step 2.2: Create Installation Script
Add to `release.sh` or create `install_polar_cloud.sh`:
```bash
#!/bin/bash
# Install Polar Cloud service
mkdir -p ${DESTDIR}/opt/polar-cloud
cp -r src/polar_cloud/* ${DESTDIR}/opt/polar-cloud/

# Create virtual environment
python3 -m venv ${DESTDIR}/opt/polar-cloud/venv
${DESTDIR}/opt/polar-cloud/venv/bin/pip install -r ${DESTDIR}/opt/polar-cloud/requirements.txt

# Install systemd service
cp MKSPKG/usr/lib/systemd/system/polar_cloud.service ${DESTDIR}/usr/lib/systemd/system/

# Install Moonraker component
cp moonraker/moonraker/components/polar_cloud.py ${DESTDIR}/usr/share/moonraker/moonraker/components/
```

### Phase 3: LVGL UI Integration

#### Step 3.1: Enable Existing Polar 3D UI Elements
The goofoo3d project already has Polar 3D UI placeholders. Enable them in:
- `/lvgl_draw_ui/draw_screen_token_page.cpp` - Token/registration page
- `/lvgl_draw_ui/draw_screen_build.cpp` - Cloud file listing

#### Step 3.2: Create C++ Interface
Create `/src/PolarCloudAPI.cpp`:
```cpp
#include "PolarCloudAPI.h"
#include "MoonrakerAPI.h"
#include <json/json.h>

class PolarCloudAPI {
private:
    MoonrakerAPI* moonraker;
    
public:
    PolarCloudAPI(MoonrakerAPI* api) : moonraker(api) {}
    
    bool getStatus(Json::Value& status) {
        return moonraker->sendRequest("server.polar_cloud.status", Json::Value(), status);
    }
    
    bool register(const std::string& username, const std::string& pin) {
        Json::Value params;
        params["username"] = username;
        params["pin"] = pin;
        return moonraker->sendRequest("server.polar_cloud.register", params);
    }
    
    bool disconnect() {
        return moonraker->sendRequest("server.polar_cloud.disconnect", Json::Value());
    }
};
```

#### Step 3.3: Update Token Page Handler
In `draw_screen_token_page.cpp`, add registration logic:
```cpp
static void polar3d_btn_event_cb(lv_obj_t * obj, lv_event_t event) {
    if (event == LV_EVENT_CLICKED) {
        // Get username and PIN from UI
        const char* username = lv_textarea_get_text(username_ta);
        const char* pin = lv_textarea_get_text(pin_ta);
        
        // Call Polar Cloud registration via Moonraker
        PolarCloudAPI polar(&moonraker);
        if (polar.register(username, pin)) {
            show_message("Registration initiated...");
        }
    }
}
```

### Phase 4: C++ WebSocket to Socket.IO Bridge (Optional)

Since goofoo3d uses WebSocketPP, you may want to create a bridge:

#### Step 4.1: Create Socket.IO Wrapper
```cpp
// SocketIOBridge.h
class SocketIOBridge {
private:
    std::string python_service_url = "http://localhost:8001";
    
public:
    bool sendCommand(const std::string& cmd, Json::Value& response);
    bool getStatus(Json::Value& status);
};
```

This allows the C++ code to communicate with the Python Socket.IO service via HTTP REST API.

### Phase 5: Configuration Integration

#### Step 5.1: Add to Local Configuration
Update `/doc/default_files/local_conf.ini`:
```ini
[polar_cloud]
enabled = false
username = 
pin = 
server_url = https://printer4.polar3d.com
```

#### Step 5.2: Create Configuration UI
Add Polar Cloud settings to the existing settings pages in LVGL.

## Key Differences and Considerations

### 1. File System Layout
- MainsailOS uses `/home/pi/` paths
- goofoo3d uses `/usr/local/`, `/opt/`, and `/var/` paths
- Update all hardcoded paths accordingly

### 2. User Permissions
- MainsailOS runs as `pi` user
- goofoo3d may use different user (check existing services)
- Update service file User= directive

### 3. Python Environment
- MainsailOS has Python pre-installed
- goofoo3d ARM64 image may need Python packages added to build

### 4. Web Interface
- MainsailOS integrates with Mainsail web UI
- goofoo3d has both Fluidd web and LVGL touchscreen
- Focus on LVGL integration, Fluidd can use Moonraker API

### 5. Network Management
- goofoo3d has existing WiFi management in `mks_wpa_cli.cpp`
- Ensure Polar Cloud service starts after network is ready

## Testing Strategy

### 1. Unit Testing
- Test Python service independently: `python3 polar_cloud.py --test`
- Test Moonraker plugin endpoints via curl
- Test C++ API wrapper with mock Moonraker

### 2. Integration Testing
- Verify service starts on boot
- Test registration flow through LVGL UI
- Verify status updates in both LVGL and Fluidd
- Test print job submission from Polar Cloud

### 3. Debug Tools
Port these debug scripts:
- `test_socketio.py` - Test Socket.IO connectivity
- `diagnose_moonraker.py` - Verify Moonraker plugin

## Common Issues and Solutions

### Issue 1: Python Package Conflicts
**Problem**: System Python packages conflict with venv
**Solution**: Use `--system-site-packages` when creating venv

### Issue 2: Service Start Order
**Problem**: Polar Cloud starts before network/Moonraker
**Solution**: Add proper systemd dependencies and delays

### Issue 3: LVGL Event Loop Blocking
**Problem**: Network calls block UI
**Solution**: Use async calls or separate thread for Polar Cloud API

### Issue 4: Cross-Compilation
**Problem**: Python packages need ARM64 compilation
**Solution**: Build on target or use pre-built wheels

## Maintenance Notes

### Version Management
- Track Polar Cloud protocol changes in both repos
- Keep Socket.IO client versions synchronized
- Document any goofoo3d-specific modifications

### Debugging
- Logs: `/var/log/polar_cloud.log`
- Status: `/var/log/polar_cloud_status.json`
- Service: `systemctl status polar_cloud`
- LVGL logs: Check existing log mechanism

### Updates
When updating from MainsailOS:
1. Compare `polar_cloud.py` for protocol changes
2. Update Moonraker plugin if API changes
3. Test registration flow completely
4. Verify all status fields are handled

## Resources

### MainsailOS Polar Cloud Files
- Implementation: `/modules/generic/files/polar-cloud/`
- Documentation: `/CLAUDE.md` (Polar Cloud section)
- Tests: `test_socketio.py`, `diagnose_moonraker.py`

### goofoo3d Integration Points
- LVGL UI: `/lvgl_draw_ui/draw_screen_*.cpp`
- Moonraker API: `/src/MoonrakerAPI.cpp`
- WebSocket: `/src/ws_client.cpp`
- Config: `/doc/default_files/`

### External Documentation
- Polar Cloud API: Internal protocol (see CLAUDE.md)
- Socket.IO Python: https://python-socketio.readthedocs.io/
- Moonraker API: https://moonraker.readthedocs.io/

## Conclusion

The migration is straightforward because:
1. The Python Socket.IO service is self-contained
2. Moonraker plugin works identically in both systems
3. goofoo3d already has UI placeholders for Polar Cloud
4. Existing WebSocket infrastructure can communicate with the service

The main work involves:
1. Adapting file paths and permissions
2. Integrating with the CMake build system
3. Connecting LVGL UI to the Moonraker API endpoints
4. Testing on the ARM64 platform

With this guide, you can implement Polar Cloud support in goofoo3d-orion when you have write access to test the integration.