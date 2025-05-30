#!/usr/bin/env python3
"""
Polar Cloud Service for MainsailOS
Connects printers to the Polar Cloud via websocket
"""

import asyncio
import websockets
import json
import logging
import os
import sys
import uuid
import hashlib
import base64
from datetime import datetime
import configparser
import requests
from PIL import Image
import io
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import socket
import time
import signal
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/pi/printer_data/logs/polar_cloud.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('polar_cloud')

class PolarCloudService:
    # Polar Cloud status constants (as integers)
    PSTATE_IDLE = 0
    PSTATE_SERIAL = 1         # Printing a local print over serial
    PSTATE_PREPARING = 2      # Preparing a cloud print (slicing)
    PSTATE_PRINTING = 3       # Printing a cloud print
    PSTATE_PAUSED = 4
    PSTATE_POSTPROCESSING = 5 # Performing post-print operations
    PSTATE_CANCELLING = 6     # Canceling a print originated from the cloud
    PSTATE_COMPLETE = 7       # Completed a print originated from the cloud
    PSTATE_UPDATING = 8       # Busy updating OctoPrint and/or plugins
    PSTATE_COLDPAUSED = 9
    PSTATE_CHANGINGFILAMENT = 10
    PSTATE_TCPIP = 11         # Printing a local print over TCP/IP
    PSTATE_ERROR = 12
    PSTATE_OFFLINE = 13

    def __init__(self, config_file='/home/pi/printer_data/config/polar_cloud.conf'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.websocket = None
        self.connected = False
        self.running = True
        self.serial_number = None
        self.private_key = None
        self.public_key = None
        self.challenge = None
        self.hello_sent = False
        self.status_interval = 10  # Send status every 10 seconds
        self.moonraker_url = "http://localhost:7125"
        self.last_status = None
        self.disconnect_on_register = True  # Enable disconnect after registration as per protocol
        self.disconnect_on_unregister = False
        
        # Image upload functionality
        self.upload_urls = {}  # Store pre-signed URLs by type
        self.last_image_upload = {}  # Track last upload time by type
        self.image_upload_intervals = {
            'idle': 60,      # Upload idle images every 60 seconds (1 minute)
            'printing': 10   # Upload printing images every 10 seconds
        }
        self.current_job_id = None
        self.is_printing_cloud_job = False
        
        # Job progress tracking
        self.job_start_time = None
        self.job_file_size = 0
        self.job_bytes_read = 0
        self.job_filament_used = 0
        
        # Load configuration
        self.load_config()
        
        # Generate or load keys
        self.ensure_keys()
        
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            # Create default config
            self.config['polar_cloud'] = {
                'server_url': 'wss://status-dev.polar3d.com',
                'username': '',
                'pin': '',
                'machine_type': 'Cartesian',
                'printer_type': 'Cartesian',
                'verbose': 'false',
                'max_image_size': '150000'
            }
            self.save_config()
    
    def save_config(self):
        """Save configuration to file"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def ensure_keys(self):
        """Generate or load RSA key pair"""
        key_file = '/home/pi/printer_data/config/polar_cloud_key.pem'
        
        if os.path.exists(key_file):
            # Load existing key
            with open(key_file, 'rb') as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
        else:
            # Generate new key pair
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            
            # Save private key
            with open(key_file, 'wb') as f:
                f.write(self.private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            # Set permissions
            os.chmod(key_file, 0o600)
        
        # Get public key
        self.public_key = self.private_key.public_key()
    
    def get_mac_address(self):
        """Get MAC address for printer identification"""
        mac = ':'.join(('%012X' % uuid.getnode())[i:i+2] for i in range(0, 12, 2))
        return mac
    
    def get_ip_address(self):
        """Get local IP address"""
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
    
    async def get_moonraker_data(self, endpoint):
        """Get data from Moonraker API"""
        try:
            response = requests.get(f"{self.moonraker_url}/{endpoint}", timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error getting Moonraker data from {endpoint}: {e}")
        return None
    
    async def get_job_progress(self):
        """Get detailed job progress information from Moonraker"""
        try:
            # Get virtual SD card info for file progress
            virtual_sdcard = await self.get_moonraker_data("printer/objects/query?virtual_sdcard")
            if virtual_sdcard and 'result' in virtual_sdcard and 'virtual_sdcard' in virtual_sdcard['result']:
                sdcard_data = virtual_sdcard['result']['virtual_sdcard']
                
                # Update job progress tracking
                if 'file_size' in sdcard_data:
                    self.job_file_size = sdcard_data['file_size']
                if 'file_position' in sdcard_data:
                    self.job_bytes_read = sdcard_data['file_position']
            
            # Get filament usage (if available from print_stats)
            print_stats = await self.get_moonraker_data("printer/objects/query?print_stats")
            if print_stats and 'result' in print_stats and 'print_stats' in print_stats['result']:
                stats_data = print_stats['result']['print_stats']
                if 'filament_used' in stats_data:
                    self.job_filament_used = stats_data['filament_used']
            
            return {
                'file_size': self.job_file_size,
                'bytes_read': self.job_bytes_read,
                'filament_used': self.job_filament_used
            }
        except Exception as e:
            logger.error(f"Error getting job progress: {e}")
            return {
                'file_size': 0,
                'bytes_read': 0,
                'filament_used': 0
            }
    
    async def get_printer_status(self):
        """Get current printer status from Moonraker"""
        printer_info = await self.get_moonraker_data("printer/info")
        printer_objects = await self.get_moonraker_data("printer/objects/query?print_stats&toolhead&extruder&heater_bed")
        
        status = {
            "serialNumber": self.serial_number or "unknown",
            "status": self.PSTATE_IDLE,  # Default to idle
            "protocol": "2",
            "progress": "",
            "estimatedTime": "0",
            "printSeconds": "0",
            "file": "",
            "temps": [],
            "clientType": "MNSL"  # Identify as Mainsail client
        }
        
        if printer_objects and 'result' in printer_objects:
            result = printer_objects['result']
            
            # Get print status
            if 'print_stats' in result and 'state' in result['print_stats']:
                klipper_state = result['print_stats']['state']
                
                # Map Klipper states to Polar Cloud states
                if klipper_state == "printing":
                    if self.is_printing_cloud_job:
                        status["status"] = self.PSTATE_PRINTING  # Cloud print
                    else:
                        status["status"] = self.PSTATE_SERIAL    # Local print over serial/USB
                elif klipper_state == "paused":
                    status["status"] = self.PSTATE_PAUSED
                elif klipper_state == "complete":
                    if self.is_printing_cloud_job:
                        status["status"] = self.PSTATE_COMPLETE  # Cloud print completed
                    else:
                        status["status"] = self.PSTATE_IDLE      # Local print completed, back to idle
                elif klipper_state == "error":
                    status["status"] = self.PSTATE_ERROR
                elif klipper_state == "standby":
                    status["status"] = self.PSTATE_IDLE
                else:
                    status["status"] = self.PSTATE_IDLE
                
                # Get print progress and time info
                if 'print_stats' in result:
                    print_stats = result['print_stats']
                    if 'print_duration' in print_stats:
                        status["printSeconds"] = str(int(print_stats['print_duration']))
                    if 'filename' in print_stats and print_stats['filename']:
                        status["file"] = print_stats['filename']
                    
                    # Add progress information for active prints
                    if klipper_state in ["printing", "paused"]:
                        # Calculate progress percentage if possible
                        if 'print_duration' in print_stats and 'estimated_time' in print_stats:
                            duration = print_stats['print_duration']
                            estimated = print_stats['estimated_time']
                            if estimated > 0:
                                progress_pct = min(100.0, (duration / estimated) * 100)
                                status["progress"] = f"{progress_pct:.1f}%"
                        
                        # Set progress detail
                        if self.is_printing_cloud_job and self.current_job_id:
                            status["progressDetail"] = f"Printing Job: {self.current_job_id} Percent Complete: {status.get('progress', '0%')}"
                        else:
                            status["progressDetail"] = f"Printing Local Job: {status.get('file', 'Unknown')} Percent Complete: {status.get('progress', '0%')}"
            
            # Get temperatures
            temps = []
            if 'extruder' in result:
                extruder = result['extruder']
                temps.append({
                    "name": "extruder",
                    "actual": extruder.get('temperature', 0),
                    "target": extruder.get('target', 0)
                })
            
            if 'heater_bed' in result:
                bed = result['heater_bed']
                temps.append({
                    "name": "bed",
                    "actual": bed.get('temperature', 0),
                    "target": bed.get('target', 0)
                })
            
            status["temps"] = temps
        
        return status
    
    async def capture_webcam_image(self):
        """Capture image from webcam and return as JPEG bytes"""
        try:
            # Try to get webcam image from standard locations
            webcam_urls = [
                "http://localhost/webcam/?action=snapshot",
                "http://localhost:8080/?action=snapshot",
                f"http://{self.get_ip_address()}/webcam/?action=snapshot"
            ]
            
            for url in webcam_urls:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        # Resize image if needed
                        image = Image.open(io.BytesIO(response.content))
                        
                        # Convert to RGB if needed
                        if image.mode != 'RGB':
                            image = image.convert('RGB')
                        
                        # Resize if image is too large
                        max_size = int(self.config.get('polar_cloud', 'max_image_size', fallback='150000'))
                        
                        # Estimate current size
                        buffer = io.BytesIO()
                        image.save(buffer, format='JPEG', quality=85)
                        current_size = len(buffer.getvalue())
                        
                        if current_size > max_size:
                            # Calculate scale factor
                            scale_factor = (max_size / current_size) ** 0.5
                            new_width = int(image.width * scale_factor)
                            new_height = int(image.height * scale_factor)
                            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        
                        # Return JPEG bytes
                        buffer = io.BytesIO()
                        image.save(buffer, format='JPEG', quality=85)
                        return buffer.getvalue()
                except Exception as e:
                    logger.debug(f"Failed to get image from {url}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error capturing webcam image: {e}")
        
        return None
    
    async def request_upload_url(self, upload_type, job_id=None):
        """Request a pre-signed POST URL for uploading images"""
        try:
            if not self.websocket or not self.serial_number:
                return None
            
            request_data = {
                "serialNumber": self.serial_number,
                "method": "post",
                "type": upload_type
            }
            
            # Add jobId for printing and timelapse uploads
            if upload_type in ['printing', 'timelapse'] and job_id:
                request_data["jobId"] = job_id
            
            await self.websocket.send(json.dumps({
                "getUrl": request_data
            }))
            
            logger.debug(f"Requested upload URL for type: {upload_type}")
            return True
        except Exception as e:
            logger.error(f"Error requesting upload URL: {e}")
            return False
    
    async def upload_image_to_cloud(self, image_data, upload_type):
        """Upload image data using pre-signed POST URL"""
        try:
            if upload_type not in self.upload_urls:
                logger.warning(f"No upload URL available for type: {upload_type}")
                return False
            
            url_info = self.upload_urls[upload_type]
            
            # Check if URL has expired
            if time.time() > url_info.get('expires_at', 0):
                logger.info(f"Upload URL for {upload_type} has expired, requesting new one")
                await self.request_upload_url(upload_type, self.current_job_id if upload_type == 'printing' else None)
                return False
            
            # Prepare form data for POST request
            files = {'file': ('image.jpg', image_data, 'image/jpeg')}
            data = url_info['fields']
            
            # Upload the image
            response = requests.post(url_info['url'], data=data, files=files, timeout=30)
            
            if response.status_code in [200, 201, 204]:
                logger.debug(f"Successfully uploaded {upload_type} image to cloud")
                self.last_image_upload[upload_type] = time.time()
                return True
            else:
                logger.error(f"Failed to upload {upload_type} image: HTTP {response.status_code}")
                logger.debug(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error uploading {upload_type} image: {e}")
            return False
    
    async def handle_image_uploads(self):
        """Handle periodic image uploads based on printer state"""
        try:
            # Determine current upload type based on printer state
            status = await self.get_printer_status()
            printer_status = status.get("status", self.PSTATE_IDLE)
            
            # Determine upload type and interval
            if printer_status == self.PSTATE_PRINTING and self.is_printing_cloud_job:  # Printing cloud job
                upload_type = "printing"
                interval = self.image_upload_intervals['printing']
            else:  # Idle or printing local job
                upload_type = "idle"
                interval = self.image_upload_intervals['idle']
            
            # Check if it's time to upload
            last_upload = self.last_image_upload.get(upload_type, 0)
            if time.time() - last_upload < interval:
                return
            
            # Capture image
            image_data = await self.capture_webcam_image()
            if not image_data:
                logger.debug("No webcam image available for upload")
                return
            
            # Ensure we have a valid upload URL
            if upload_type not in self.upload_urls:
                job_id = self.current_job_id if upload_type == 'printing' else None
                await self.request_upload_url(upload_type, job_id)
                return  # Wait for next cycle to upload
            
            # Upload the image
            success = await self.upload_image_to_cloud(image_data, upload_type)
            if success:
                logger.info(f"Uploaded {upload_type} image to Polar Cloud")
            
        except Exception as e:
            logger.error(f"Error in image upload handler: {e}")
    
    async def register_printer(self, username, pin):
        """Register printer with Polar Cloud"""
        try:
            # Create registration message
            public_key_pem = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
            
            registration_data = {
                "mfg": "mnsl",
                "email": username,
                "pin": pin,
                "publicKey": public_key_pem,
                "macAddress": self.get_mac_address(),
                "machineType": self.config.get('polar_cloud', 'machine_type', fallback='Cartesian'),
                "printerType": self.config.get('polar_cloud', 'printer_type', fallback='Cartesian'),
            }
            
            if self.websocket:
                await self.websocket.send(json.dumps({
                    "register": registration_data
                }))
                logger.info("Registration request sent to Polar Cloud with MNSL client identifier")
                return True
        except Exception as e:
            logger.error(f"Error registering printer: {e}")
        
        return False
    
    async def send_hello(self):
        """Send hello message to Polar Cloud"""
        try:
            if not self.challenge:
                logger.error("Cannot send hello: no challenge received")
                return
                
            hello_data = {
                "serialNumber": self.serial_number,
                "protocol": "2",
                "macAddress": self.get_mac_address(),
                "localIP": self.get_ip_address(),
                "signature": base64.b64encode(
                    self.private_key.sign(
                        self.challenge.encode('utf-8'),
                        padding.PKCS1v15(),
                        hashes.SHA256()
                    )
                ).decode('utf-8'),
                "machineType": self.config.get('polar_cloud', 'machine_type', fallback='Cartesian'),
                "printerType": self.config.get('polar_cloud', 'printer_type', fallback='Cartesian'),
            }
            
            if self.websocket:
                await self.websocket.send(json.dumps({
                    "hello": hello_data
                }))
                self.hello_sent = True
                logger.info("Hello message sent to Polar Cloud")
        except Exception as e:
            logger.error(f"Error sending hello: {e}")
    
    async def send_status(self):
        """Send printer status to Polar Cloud"""
        try:
            status = await self.get_printer_status()
            
            # Only send status if something has changed or it's been a while
            if self.last_status and status == self.last_status:
                return
            
            if self.websocket:
                await self.websocket.send(json.dumps({
                    "status": status
                }))
                self.last_status = status.copy()
                logger.debug("Status sent to Polar Cloud")
        except Exception as e:
            logger.error(f"Error sending status: {e}")
    
    async def handle_message(self, message):
        """Handle incoming message from Polar Cloud"""
        try:
            data = json.loads(message)
            logger.debug(f"Received message: {data}")
            
            if "welcome" in data:
                welcome_data = data["welcome"]
                self.challenge = welcome_data.get("challenge")
                logger.info(f"Received welcome from Polar Cloud with challenge: {self.challenge}")
                
                # Check if we need to register
                self.serial_number = self.config.get('polar_cloud', 'serial_number', fallback=None)
                username = self.config.get('polar_cloud', 'username', fallback='')
                pin = self.config.get('polar_cloud', 'pin', fallback='')
                
                if not self.serial_number and username and pin:
                    # Need to register
                    logger.info("No serial number found, attempting registration")
                    await self.register_printer(username, pin)
                elif self.serial_number:
                    # Already registered, send hello
                    logger.info("Serial number found, sending hello")
                    await self.send_hello()
                else:
                    logger.warning("No credentials configured for registration")
            
            elif "registerResponse" in data:
                response = data["registerResponse"]
                if response.get("success"):
                    self.serial_number = response.get("serialNumber")
                    
                    # Save serial number to config
                    self.config['polar_cloud']['serial_number'] = self.serial_number
                    self.save_config()
                    
                    logger.info(f"Successfully registered with serial number: {self.serial_number}")
                    
                    # Disconnect and reconnect as per protocol
                    if self.disconnect_on_register:
                        logger.info("Disconnecting after registration as per protocol")
                        await self.websocket.close()
                        self.connected = False
                        self.websocket = None
                        return
                    
                    # Send hello after successful registration
                    await self.send_hello()
                else:
                    logger.error(f"Registration failed: {response.get('reason', 'Unknown error')}")
            
            elif "helloResponse" in data:
                response = data["helloResponse"]
                if response.get("success"):
                    logger.info("Hello response received successfully")
                    # Start sending status updates and request initial upload URLs
                    if not hasattr(self, '_status_task') or self._status_task.done():
                        self._status_task = asyncio.create_task(self.status_loop())
                    
                    # Request initial upload URLs
                    await self.request_upload_url("idle")
                    
                else:
                    logger.error(f"Hello failed: {response.get('reason', 'Unknown error')}")
            
            elif "getUrlResponse" in data:
                response = data["getUrlResponse"]
                if response.get("status") == "SUCCESS":
                    upload_type = response.get("type")
                    expires_in = response.get("expires", 86400)  # Default 24 hours
                    
                    # Store the upload URL info
                    self.upload_urls[upload_type] = {
                        "url": response.get("url"),
                        "fields": response.get("fields", {}),
                        "maxSize": response.get("maxSize", 150000),
                        "contentType": response.get("contentType", "image/jpeg"),
                        "expires_at": time.time() + expires_in
                    }
                    
                    logger.info(f"Received upload URL for {upload_type}, expires in {expires_in} seconds")
                else:
                    logger.error(f"Failed to get upload URL: {response.get('message', 'Unknown error')}")
            
            elif "print" in data:
                # Handle print command
                print_data = data["print"]
                self.current_job_id = print_data.get("jobId")
                self.is_printing_cloud_job = True
                self.job_start_time = datetime.now().isoformat() + "Z"
                
                # Reset job tracking
                self.job_file_size = 0
                self.job_bytes_read = 0
                self.job_filament_used = 0
                
                logger.info(f"Received print command for job: {self.current_job_id}")
                
                # Request printing upload URL
                await self.request_upload_url("printing", self.current_job_id)
                
                # Execute print command via Moonraker
                await self.execute_print_command(print_data)
            
            elif "cancel" in data:
                # Handle cancel command
                logger.info("Received cancel command")
                
                # Execute cancel via Moonraker
                success = await self.execute_cancel_command()
                if success:
                    self.is_printing_cloud_job = False
                    self.current_job_id = None
                    self.job_start_time = None
            
            elif "pause" in data:
                # Handle pause command
                logger.info("Received pause command")
                
                # Execute pause via Moonraker
                await self.execute_pause_command()
            
            elif "resume" in data:
                # Handle resume command
                logger.info("Received resume command")
                
                # Execute resume via Moonraker
                await self.execute_resume_command()
            
            elif "delete" in data:
                # Handle delete command - reset printer to unregistered state
                logger.info("Received delete command - resetting printer to unregistered state")
                await self.execute_delete_command()
            
            elif "temperature" in data:
                # Handle temperature command
                temp_data = data["temperature"]
                logger.info(f"Received temperature command: {temp_data}")
                
                # Execute temperature control via Moonraker
                await self.execute_temperature_command(temp_data)
        
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def connect_websocket(self):
        """Connect to Polar Cloud websocket"""
        server_url = self.config.get('polar_cloud', 'server_url', fallback='wss://status-dev.polar3d.com')
        
        try:
            self.websocket = await websockets.connect(server_url)
            self.connected = True
            self.hello_sent = False
            self.challenge = None
            logger.info(f"Connected to Polar Cloud at {server_url}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to Polar Cloud: {e}")
            self.connected = False
            return False
    
    async def status_loop(self):
        """Send status updates and handle image uploads periodically"""
        while self.running and self.connected and self.hello_sent:
            try:
                await self.send_status()
                await self.handle_image_uploads()
                await self.monitor_print_completion()
                await asyncio.sleep(self.status_interval)
            except Exception as e:
                logger.error(f"Error in status loop: {e}")
                break
    
    async def run(self):
        """Main service loop"""
        logger.info("Starting Polar Cloud Service")
        
        while self.running:
            try:
                if not self.connected:
                    await self.connect_websocket()
                
                if self.websocket:
                    try:
                        # Listen for messages
                        message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                        await self.handle_message(message)
                    except asyncio.TimeoutError:
                        # No message received, continue
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("Websocket connection closed")
                        self.connected = False
                        self.websocket = None
                        self.hello_sent = False
                        await asyncio.sleep(5)  # Wait before reconnecting
                else:
                    await asyncio.sleep(5)  # Wait before trying to connect
            
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)
    
    def stop(self):
        """Stop the service"""
        logger.info("Stopping Polar Cloud Service")
        self.running = False

    async def send_job_completion(self, job_id, state, print_seconds=0, filament_used=0, bytes_read=0, file_size=0):
        """Send job completion notification to Polar Cloud"""
        try:
            if not self.websocket or not self.serial_number:
                return False
            
            # Get current printer status for additional fields
            status = await self.get_printer_status()
            
            job_data = {
                "serialNumber": self.serial_number,
                "jobId": job_id,
                "state": state,  # "completed" or "canceled"
            }
            
            # Add optional fields if available
            if print_seconds > 0:
                job_data["printSeconds"] = print_seconds
            if filament_used > 0:
                job_data["filamentUsed"] = filament_used
            if bytes_read > 0:
                job_data["bytesRead"] = bytes_read
            if file_size > 0:
                job_data["fileSize"] = file_size
            
            # Add temperature information if available
            temps = status.get("temps", [])
            for temp in temps:
                if temp["name"] == "extruder":
                    job_data["tool0"] = temp["actual"]
                    job_data["targetTool0"] = temp["target"]
                elif temp["name"] == "bed":
                    job_data["bed"] = temp["actual"]
                    job_data["targetBed"] = temp["target"]
            
            # Add progress information
            progress = status.get("progress", "")
            if progress:
                job_data["progress"] = progress
            
            progress_detail = status.get("progressDetail", "")
            if progress_detail:
                job_data["progressDetail"] = progress_detail
            
            # Add estimated time if available
            estimated_time = status.get("estimatedTime", "0")
            if estimated_time and estimated_time != "0":
                job_data["estimatedTime"] = estimated_time
            
            await self.websocket.send(json.dumps({
                "job": job_data
            }))
            
            logger.info(f"Sent job completion for {job_id}: {state}")
            return True
        except Exception as e:
            logger.error(f"Error sending job completion: {e}")
            return False
    
    async def monitor_print_completion(self):
        """Monitor for print completion and send job notifications"""
        try:
            status = await self.get_printer_status()
            printer_status = status.get("status", self.PSTATE_IDLE)
            
            # Check if a cloud job has completed
            if self.is_printing_cloud_job and self.current_job_id:
                # Get current job progress
                job_progress = await self.get_job_progress()
                
                if printer_status == self.PSTATE_COMPLETE:
                    # Cloud job completed successfully
                    print_seconds = int(status.get("printSeconds", "0"))
                    await self.send_job_completion(
                        self.current_job_id, 
                        "completed", 
                        print_seconds,
                        job_progress['filament_used'],
                        job_progress['bytes_read'],
                        job_progress['file_size']
                    )
                    
                    # Reset cloud job state
                    self.is_printing_cloud_job = False
                    self.current_job_id = None
                    self.job_start_time = None
                    
                elif printer_status in [self.PSTATE_IDLE, self.PSTATE_ERROR]:
                    # Cloud job was cancelled or failed
                    print_seconds = int(status.get("printSeconds", "0"))
                    await self.send_job_completion(
                        self.current_job_id, 
                        "canceled", 
                        print_seconds,
                        job_progress['filament_used'],
                        job_progress['bytes_read'],
                        job_progress['file_size']
                    )
                    
                    # Reset cloud job state
                    self.is_printing_cloud_job = False
                    self.current_job_id = None
                    self.job_start_time = None
                    
        except Exception as e:
            logger.error(f"Error monitoring print completion: {e}")

    async def execute_print_command(self, print_data):
        """Execute print command via Moonraker API"""
        try:
            # Extract print job information
            job_id = print_data.get("jobId")
            gcode_file = print_data.get("gcodeFile")
            stl_file = print_data.get("stlFile")
            config_file = print_data.get("configFile")
            
            logger.info(f"Executing print command for job {job_id}")
            
            if gcode_file:
                # Download and print gcode file
                logger.info(f"Downloading gcode file: {gcode_file}")
                
                # Download the gcode file
                response = requests.get(gcode_file, timeout=30)
                if response.status_code == 200:
                    # Save gcode file to printer
                    filename = f"polar_cloud_{job_id}.gcode"
                    filepath = f"/home/pi/printer_data/gcodes/{filename}"
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    
                    logger.info(f"Downloaded gcode file to {filepath}")
                    
                    # Start print via Moonraker
                    print_response = requests.post(
                        f"{self.moonraker_url}/printer/print/start",
                        json={"filename": filename},
                        timeout=10
                    )
                    
                    if print_response.status_code == 200:
                        logger.info(f"Successfully started print for job {job_id}")
                        return True
                    else:
                        logger.error(f"Failed to start print: {print_response.text}")
                        return False
                else:
                    logger.error(f"Failed to download gcode file: HTTP {response.status_code}")
                    return False
            else:
                logger.error("No gcode file provided in print command")
                return False
                
        except Exception as e:
            logger.error(f"Error executing print command: {e}")
            return False
    
    async def execute_cancel_command(self):
        """Execute cancel command via Moonraker API"""
        try:
            response = requests.post(f"{self.moonraker_url}/printer/print/cancel", timeout=10)
            if response.status_code == 200:
                logger.info("Successfully cancelled print")
                return True
            else:
                logger.error(f"Failed to cancel print: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error executing cancel command: {e}")
            return False
    
    async def execute_pause_command(self):
        """Execute pause command via Moonraker API"""
        try:
            response = requests.post(f"{self.moonraker_url}/printer/print/pause", timeout=10)
            if response.status_code == 200:
                logger.info("Successfully paused print")
                return True
            else:
                logger.error(f"Failed to pause print: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error executing pause command: {e}")
            return False
    
    async def execute_resume_command(self):
        """Execute resume command via Moonraker API"""
        try:
            response = requests.post(f"{self.moonraker_url}/printer/print/resume", timeout=10)
            if response.status_code == 200:
                logger.info("Successfully resumed print")
                return True
            else:
                logger.error(f"Failed to resume print: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error executing resume command: {e}")
            return False
    
    async def execute_delete_command(self):
        """Execute delete command - reset printer to unregistered state"""
        try:
            # Cancel any active print first
            await self.execute_cancel_command()
            
            # Clear registration data
            if 'polar_cloud' in self.config:
                if 'serial_number' in self.config['polar_cloud']:
                    del self.config['polar_cloud']['serial_number']
                self.save_config()
            
            # Reset internal state
            self.serial_number = None
            self.is_printing_cloud_job = False
            self.current_job_id = None
            self.job_start_time = None
            self.hello_sent = False
            
            # Clear upload URLs
            self.upload_urls.clear()
            
            logger.info("Printer reset to unregistered state")
            
            # Disconnect from cloud
            if self.websocket:
                await self.websocket.close()
                self.connected = False
                self.websocket = None
            
            return True
        except Exception as e:
            logger.error(f"Error executing delete command: {e}")
            return False
    
    async def execute_temperature_command(self, temp_data):
        """Execute temperature command via Moonraker API"""
        try:
            # Extract temperature settings
            tool0_temp = temp_data.get("tool0")
            bed_temp = temp_data.get("bed")
            
            success = True
            
            # Set extruder temperature
            if tool0_temp is not None:
                response = requests.post(
                    f"{self.moonraker_url}/printer/gcode/script",
                    json={"script": f"SET_HEATER_TEMPERATURE HEATER=extruder TARGET={tool0_temp}"},
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info(f"Set extruder temperature to {tool0_temp}°C")
                else:
                    logger.error(f"Failed to set extruder temperature: {response.text}")
                    success = False
            
            # Set bed temperature
            if bed_temp is not None:
                response = requests.post(
                    f"{self.moonraker_url}/printer/gcode/script",
                    json={"script": f"SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET={bed_temp}"},
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info(f"Set bed temperature to {bed_temp}°C")
                else:
                    logger.error(f"Failed to set bed temperature: {response.text}")
                    success = False
            
            return success
        except Exception as e:
            logger.error(f"Error executing temperature command: {e}")
            return False

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    global service
    if service:
        service.stop()

async def main():
    global service
    service = PolarCloudService()
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        await service.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        service.stop()

if __name__ == "__main__":
    service = None
    asyncio.run(main()) 