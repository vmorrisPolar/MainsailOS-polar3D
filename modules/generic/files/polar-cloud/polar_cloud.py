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
        self.status_interval = 60  # Send status every 60 seconds
        self.moonraker_url = "http://localhost:7125"
        
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
                'server_url': 'wss://printer4.polar3d.com',
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
    
    async def get_printer_status(self):
        """Get current printer status from Moonraker"""
        printer_info = await self.get_moonraker_data("printer/info")
        printer_objects = await self.get_moonraker_data("printer/objects/query?print_stats&toolhead&extruder&heater_bed")
        
        status = {
            "serialNumber": self.serial_number or "unknown",
            "status": "0",  # Default to idle
            "protocol": "2",
            "progress": "",
            "estimatedTime": "0",
            "printSeconds": "0",
            "file": "",
            "temps": []
        }
        
        if printer_objects and 'result' in printer_objects:
            result = printer_objects['result']
            
            # Get print status
            if 'print_stats' in result and 'state' in result['print_stats']:
                state = result['print_stats']['state']
                if state == "printing":
                    status["status"] = "3"  # Printing
                elif state == "paused":
                    status["status"] = "4"  # Paused
                elif state == "complete":
                    status["status"] = "7"  # Complete
                elif state == "error":
                    status["status"] = "12"  # Error
                else:
                    status["status"] = "0"  # Idle
            
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
        """Capture image from webcam"""
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
                        
                        # Convert to base64
                        buffer = io.BytesIO()
                        image.save(buffer, format='JPEG', quality=85)
                        image_data = buffer.getvalue()
                        return base64.b64encode(image_data).decode('utf-8')
                except Exception as e:
                    logger.debug(f"Failed to get image from {url}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error capturing webcam image: {e}")
        
        return None
    
    async def register_printer(self, username, pin):
        """Register printer with Polar Cloud"""
        try:
            # Create registration message
            public_key_pem = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
            
            registration_data = {
                "email": username,
                "pin": pin,
                "publicKey": public_key_pem,
                "macAddress": self.get_mac_address(),
                "printerType": self.config.get('polar_cloud', 'printer_type', fallback='Cartesian'),
                "machineType": self.config.get('polar_cloud', 'machine_type', fallback='Cartesian')
            }
            
            if self.websocket:
                await self.websocket.send(json.dumps({
                    "register": registration_data
                }))
                logger.info("Registration request sent to Polar Cloud")
                return True
        except Exception as e:
            logger.error(f"Error registering printer: {e}")
        
        return False
    
    async def send_hello(self):
        """Send hello message to Polar Cloud"""
        try:
            hello_data = {
                "serialNumber": self.serial_number,
                "version": "2.0.0",
                "protocol": "2"
            }
            
            if self.websocket:
                await self.websocket.send(json.dumps({
                    "hello": hello_data
                }))
                logger.info("Hello message sent to Polar Cloud")
        except Exception as e:
            logger.error(f"Error sending hello: {e}")
    
    async def send_status(self):
        """Send printer status to Polar Cloud"""
        try:
            status = await self.get_printer_status()
            
            # Add webcam image if available
            image_data = await self.capture_webcam_image()
            if image_data:
                status["image"] = image_data
            
            if self.websocket:
                await self.websocket.send(json.dumps({
                    "status": status
                }))
                logger.debug("Status sent to Polar Cloud")
        except Exception as e:
            logger.error(f"Error sending status: {e}")
    
    async def handle_message(self, message):
        """Handle incoming message from Polar Cloud"""
        try:
            data = json.loads(message)
            logger.debug(f"Received message: {data}")
            
            if "registerResponse" in data:
                response = data["registerResponse"]
                if response.get("success"):
                    self.serial_number = response.get("serialNumber")
                    
                    # Save credentials to config
                    username = self.config.get('polar_cloud', 'username', fallback='')
                    pin = self.config.get('polar_cloud', 'pin', fallback='')
                    
                    self.config['polar_cloud']['serial_number'] = self.serial_number
                    self.save_config()
                    
                    logger.info(f"Successfully registered with serial number: {self.serial_number}")
                    
                    # Send hello after successful registration
                    await self.send_hello()
                else:
                    logger.error(f"Registration failed: {response.get('reason', 'Unknown error')}")
            
            elif "welcome" in data:
                logger.info("Received welcome from Polar Cloud")
                # Send hello in response to welcome
                await self.send_hello()
            
            elif "print" in data:
                # Handle print command
                print_data = data["print"]
                logger.info(f"Received print command: {print_data}")
                # TODO: Implement print handling
            
            elif "cancel" in data:
                # Handle cancel command
                logger.info("Received cancel command")
                # TODO: Implement cancel handling
            
            elif "pause" in data:
                # Handle pause command
                logger.info("Received pause command")
                # TODO: Implement pause handling
            
            elif "resume" in data:
                # Handle resume command
                logger.info("Received resume command")
                # TODO: Implement resume handling
            
            elif "temperature" in data:
                # Handle temperature command
                temp_data = data["temperature"]
                logger.info(f"Received temperature command: {temp_data}")
                # TODO: Implement temperature control
        
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def connect_websocket(self):
        """Connect to Polar Cloud websocket"""
        server_url = self.config.get('polar_cloud', 'server_url', fallback='wss://printer4.polar3d.com')
        
        try:
            self.websocket = await websockets.connect(server_url)
            self.connected = True
            logger.info(f"Connected to Polar Cloud at {server_url}")
            
            # If we have a serial number, send hello
            self.serial_number = self.config.get('polar_cloud', 'serial_number', fallback=None)
            if self.serial_number:
                await self.send_hello()
            
            return True
        except Exception as e:
            logger.error(f"Error connecting to Polar Cloud: {e}")
            self.connected = False
            return False
    
    async def status_loop(self):
        """Send status updates periodically"""
        while self.running:
            if self.connected and self.websocket and self.serial_number:
                await self.send_status()
            await asyncio.sleep(self.status_interval)
    
    async def run(self):
        """Main service loop"""
        logger.info("Starting Polar Cloud Service")
        
        while self.running:
            try:
                if not self.connected:
                    if await self.connect_websocket():
                        # Start status loop
                        asyncio.create_task(self.status_loop())
                
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