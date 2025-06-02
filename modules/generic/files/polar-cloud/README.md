# Polar Cloud Service for MainsailOS

This service connects MainsailOS printers to the Polar Cloud platform, enabling remote monitoring and control.

## Protocol Implementation

This implementation follows the Polar Cloud protocol as defined in the OctoPrint-PolarCloud plugin. The service properly implements the required message flow:

### Registration Flow (First Time)
1. **Connect** to `https://printer4.polar3d.com`
2. **Receive welcome.json** with challenge string
3. **Send register.json** with credentials and public key
4. **Receive registerResponse.json** with serial number
5. **Disconnect and reconnect** (as per protocol)

### Normal Connection Flow
1. **Connect** to `https://printer4.polar3d.com`
2. **Receive welcome.json** with challenge string
3. **Generate RSA signature** of challenge using private key
4. **Send hello.json** with signed challenge
5. **Receive helloResponse.json** confirming authentication
6. **Send status.json** updates every 10 seconds (only when changed)
7. **Upload camera images** using pre-signed POST URLs

## Features

- ✅ Proper RSA key pair generation and management
- ✅ Digital signature authentication with challenge/response
- ✅ Automatic registration with username/PIN
- ✅ Real-time printer status reporting
- ✅ **Camera image uploads with pre-signed POST URLs**
- ✅ **Automatic idle image uploads every 60 seconds**
- ✅ **Printing image uploads every 10 seconds during cloud prints**
- ✅ Webcam image capture and transmission
- ✅ Temperature monitoring
- ✅ Print progress tracking
- ✅ Moonraker API integration
- ✅ Configurable settings
- ✅ Systemd service integration

## Camera Image Upload System

The service implements the Polar Cloud's camera image upload protocol using pre-signed POST URLs:

### Upload Types and Intervals

- **Idle Images**: Uploaded every **60 seconds** when printer is idle or printing local jobs
- **Printing Images**: Uploaded every **10 seconds** when printing jobs from the Polar Cloud
- **Timelapse Videos**: Uploaded after completing cloud print jobs (future feature)

### How It Works

1. **Request Upload URLs**: Service requests pre-signed POST URLs from Polar Cloud using `getUrl` command
2. **Receive URLs**: Polar Cloud responds with `getUrlResponse` containing AWS S3 pre-signed URLs
3. **Capture Images**: Service captures JPEG images from MainsailOS webcam
4. **Upload Images**: Images are uploaded directly to AWS S3 using the pre-signed URLs
5. **URL Management**: URLs are cached and automatically renewed when they expire (typically 24 hours)

### Image Processing

- Images are automatically resized to stay under the configured size limit (default: 150KB)
- Images are converted to RGB JPEG format with 85% quality
- Multiple webcam URL locations are tried automatically
- Failed uploads are logged and retried on the next cycle

## Installation

The service is automatically installed as part of MainsailOS. Files are located at:

- Service: `/home/pi/polar-cloud/polar_cloud.py`
- Config: `/home/pi/printer_data/config/polar_cloud.conf`
- Keys: `/home/pi/printer_data/config/polar_cloud_key.pem`
- Logs: `/home/pi/printer_data/logs/polar_cloud.log`

## Configuration

### Set Credentials

```bash
# Set your Polar Cloud credentials
python3 /home/pi/polar-cloud/polar_cloud_config.py set-credentials your-email@example.com your-pin

# Show current configuration
python3 /home/pi/polar-cloud/polar_cloud_config.py show

# Clear registration to force re-registration
python3 /home/pi/polar-cloud/polar_cloud_config.py clear-registration
```

### Service Management

```bash
# Start the service
sudo systemctl start polar-cloud

# Stop the service
sudo systemctl stop polar-cloud

# Restart the service
sudo systemctl restart polar-cloud

# Check service status
sudo systemctl status polar-cloud

# Enable auto-start on boot
sudo systemctl enable polar-cloud

# View logs
journalctl -u polar-cloud -f
```

Or use the configuration script:

```bash
# Service control via config script
python3 /home/pi/polar-cloud/polar_cloud_config.py service start
python3 /home/pi/polar-cloud/polar_cloud_config.py service status
python3 /home/pi/polar-cloud/polar_cloud_config.py service restart
```

## Configuration File

The configuration file is located at `/home/pi/printer_data/config/polar_cloud.conf`:

```ini
[polar_cloud]
server_url = https://printer4.polar3d.com
username = your-email@example.com
pin = your-pin
machine_type = Cartesian
printer_type = Cartesian
verbose = false
max_image_size = 150000
serial_number = (auto-generated after registration)
```

## Protocol Messages

### Registration Messages

**register.json** (sent to server):
```json
{
  "register": {
    "mfg": "mnsl",
    "email": "user@example.com",
    "pin": "1234",
    "publicKey": "-----BEGIN PUBLIC KEY-----\n...",
    "macAddress": "AA:BB:CC:DD:EE:FF",
    "machineType": "Cartesian",
    "printerType": "Cartesian"
  }
}
```

**registerResponse.json** (received from server):
```json
{
  "registerResponse": {
    "success": true,
    "serialNumber": "MNSL-12345678"
  }
}
```

### Authentication Messages

**welcome.json** (received from server):
```json
{
  "welcome": {
    "challenge": "random-challenge-string"
  }
}
```

**hello.json** (sent to server):
```json
{
  "hello": {
    "serialNumber": "MNSL-12345678",
    "protocol": "2",
    "macAddress": "AA:BB:CC:DD:EE:FF",
    "localIP": "192.168.1.100",
    "signature": "base64-encoded-signature",
    "machineType": "Cartesian",
    "printerType": "Cartesian"
  }
}
```

**helloResponse.json** (received from server):
```json
{
  "helloResponse": {
    "success": true
  }
}
```

### Image Upload Messages

**getUrl.json** (sent to server):
```json
{
  "getUrl": {
    "serialNumber": "MNSL-12345678",
    "method": "post",
    "type": "idle",
    "jobId": "optional-for-printing-type"
  }
}
```

**getUrlResponse.json** (received from server):
```json
{
  "getUrlResponse": {
    "status": "SUCCESS",
    "serialNumber": "MNSL-12345678",
    "type": "idle",
    "expires": 86400,
    "maxSize": 150000,
    "contentType": "image/jpeg",
    "method": "post",
    "url": "https://s3.amazonaws.com/polar3d.com",
    "fields": {
      "key": "files/printer/MNSL-12345678/snapshot.jpg",
      "acl": "public-read",
      "bucket": "polar3d.com",
      "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
      "X-Amz-Credential": "...",
      "X-Amz-Date": "20240101T000000Z",
      "Policy": "...",
      "X-Amz-Signature": "..."
    }
  }
}
```

### Status Messages

**status.json** (sent to server every 10 seconds):
```json
{
  "status": {
    "serialNumber": "MNSL-12345678",
    "status": "0",
    "protocol": "2",
    "progress": "",
    "estimatedTime": "0",
    "printSeconds": "0",
    "file": "",
    "temps": [
      {
        "name": "extruder",
        "actual": 25.0,
        "target": 0.0
      },
      {
        "name": "bed",
        "actual": 23.0,
        "target": 0.0
      }
    ],
    "clientType": "MNSL"
  }
}
```

### Job Completion Messages

**job.json** (sent to server when cloud jobs complete or are cancelled):
```json
{
  "job": {
    "serialNumber": "MNSL-12345678",
    "jobId": "MNSL-12345678-178137",
    "state": "completed",
    "printSeconds": 227,
    "filamentUsed": 167,
    "bytesRead": 50845,
    "fileSize": 50845,
    "tool0": 145.8,
    "targetTool0": 0,
    "bed": 23.0,
    "targetBed": 0,
    "progress": "Complete",
    "progressDetail": "Printing Job: MNSL-12345678-178137 Percent Complete: 100.0%",
    "estimatedTime": "105"
  }
}
```

**Job states:**
- `"completed"` - Job finished successfully
- `"canceled"` - Job was cancelled or failed

## Cloud-to-Printer Commands

The service implements all required commands from the Polar Cloud to the printer:

### ✅ **Implemented Commands**

#### **welcome** - Authentication Challenge
- **Purpose**: Provides challenge string for RSA signature authentication
- **Action**: Extracts challenge and triggers registration or hello flow
- **Response**: Sends `register` or `hello` command

#### **registerResponse** - Registration Result  
- **Purpose**: Confirms printer registration success/failure
- **Action**: Saves serial number, manages disconnect/reconnect flow
- **Response**: Sends `hello` command after reconnection

#### **helloResponse** - Authentication Result
- **Purpose**: Confirms successful authentication
- **Action**: Starts status reporting loop and requests upload URLs
- **Response**: Begins sending `status` updates every 10 seconds

#### **print** - Start Cloud Print Job
- **Purpose**: Initiates printing of cloud-based gcode files
- **Action**: Downloads gcode file and starts print via Moonraker API
- **Implementation**: 
  - Downloads gcode from provided URL
  - Saves to `/home/pi/printer_data/gcodes/polar_cloud_{jobId}.gcode`
  - Starts print using Moonraker `/printer/print/start` endpoint
  - Tracks job progress and enables printing image uploads

#### **cancel** - Cancel Current Print
- **Purpose**: Cancels the currently running print job
- **Action**: Executes cancel via Moonraker API
- **Implementation**: 
  - Calls Moonraker `/printer/print/cancel` endpoint
  - Resets cloud job tracking state
  - Sends job completion notification with "canceled" state

#### **pause** - Pause Current Print
- **Purpose**: Pauses the currently running print job
- **Action**: Executes pause via Moonraker API
- **Implementation**: Calls Moonraker `/printer/print/pause` endpoint

#### **resume** - Resume Paused Print
- **Purpose**: Resumes a paused print job
- **Action**: Executes resume via Moonraker API
- **Implementation**: Calls Moonraker `/printer/print/resume` endpoint

#### **delete** - Reset to Unregistered State
- **Purpose**: Removes printer from cloud and resets to factory state
- **Action**: Comprehensive state reset and disconnection
- **Implementation**:
  - Cancels any active print jobs
  - Removes serial number from configuration
  - Resets all internal state variables
  - Clears upload URL cache
  - Disconnects from Polar Cloud websocket

#### **temperature** - Set Target Temperatures
- **Purpose**: Controls extruder and bed target temperatures
- **Action**: Sets temperatures via Moonraker gcode commands
- **Implementation**:
  - Sets extruder temperature: `SET_HEATER_TEMPERATURE HEATER=extruder TARGET={temp}`
  - Sets bed temperature: `SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET={temp}`

### **Command Integration with MainsailOS**

All commands integrate seamlessly with MainsailOS through the Moonraker API:

- **Print Management**: Uses Moonraker's print control endpoints
- **Temperature Control**: Executes gcode commands via Moonraker
- **File Management**: Downloads and manages gcode files in standard location
- **Status Reporting**: Monitors printer state through Moonraker objects
- **Error Handling**: Robust error handling with detailed logging

## Status Codes

The service maps Klipper printer states to Polar Cloud status codes as integers:

- `0` - Idle (default state, local print completed, standby)
- `1` - Printing (serial) - Local print job over USB/serial
- `2` - Preparing (slicing) - Cloud print being prepared
- `3` - Printing (cloud) - Cloud print job in progress
- `4` - Paused (any print job)
- `5` - Post-processing - Performing post-print operations
- `6` - Cancelling - Canceling a cloud print
- `7` - Complete - Cloud print completed successfully
- `8` - Updating - System updates in progress
- `9` - Cold paused - Paused with heaters off
- `10` - Changing filament - Filament change operation
- `11` - Printing (TCP/IP) - Local print over network
- `12` - Error - Print error or system error
- `13` - Offline - Printer offline/disconnected

### State Mapping Logic

The service intelligently maps Klipper states to appropriate Polar Cloud states:

- **Klipper "printing"** → Status `1` (serial) for local jobs, Status `3` (cloud) for cloud jobs
- **Klipper "paused"** → Status `4` (paused)
- **Klipper "complete"** → Status `7` (complete) for cloud jobs, Status `0` (idle) for local jobs
- **Klipper "error"** → Status `12` (error)
- **Klipper "standby"** → Status `0` (idle)

This ensures the Polar Cloud service correctly distinguishes between local and cloud print jobs.

## Webcam Configuration

For camera image uploads to work, ensure your MainsailOS webcam is properly configured:

### Standard Webcam URLs Tried
- `http://localhost/webcam/?action=snapshot`
- `http://localhost:8080/?action=snapshot`
- `http://[local-ip]/webcam/?action=snapshot`

### Webcam Setup
1. Connect a USB webcam to your Raspberry Pi
2. Ensure `mjpg-streamer` is running (usually automatic in MainsailOS)
3. Verify webcam works in Mainsail interface
4. The Polar Cloud service will automatically detect and use the webcam

## Security

- RSA 2048-bit key pairs are generated automatically
- Private keys are stored securely with 600 permissions
- Digital signatures use PKCS#1 v1.5 with SHA-256
- Challenge/response authentication prevents replay attacks
- Pre-signed URLs provide secure, time-limited access to cloud storage
- No sensitive data is logged

## Troubleshooting

### Check Service Status
```bash
sudo systemctl status polar-cloud
journalctl -u polar-cloud -f
```

### Common Issues

1. **Registration fails**: Check username/PIN credentials
2. **Connection fails**: Check network connectivity to printer4.polar3d.com
3. **No webcam images**: Verify webcam is accessible at standard URLs
4. **Status not updating**: Check Moonraker API connectivity
5. **Image uploads failing**: Check webcam configuration and network connectivity

### Camera Image Upload Issues

```bash
# Check if webcam is working
curl http://localhost/webcam/?action=snapshot -o test.jpg

# Check if mjpg-streamer is running
sudo systemctl status mjpg-streamer

# View detailed upload logs
journalctl -u polar-cloud -f | grep -i image
```

### Debug Mode
Enable verbose logging by editing the config file:
```ini
[polar_cloud]
verbose = true
```

Then restart the service:
```bash
sudo systemctl restart polar-cloud
```

## Dependencies

- Python 3.7+
- websockets
- cryptography
- Pillow (PIL)
- requests
- configparser

## License

This implementation is compatible with the GNU Affero General Public License v3.0 as used by the original OctoPrint-PolarCloud plugin. 