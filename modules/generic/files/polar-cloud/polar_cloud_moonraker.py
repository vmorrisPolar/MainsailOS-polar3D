#!/usr/bin/env python3
"""
Moonraker Plugin for Polar Cloud Configuration
Provides API endpoints for the UI to configure Polar Cloud settings
"""

import logging
import configparser
import os
import asyncio
import subprocess
import aiohttp
import json
from tornado.web import RequestHandler

class PolarCloudPlugin:
    def __init__(self, config):
        self.server = config.get_server()
        self.config_file = "/home/pi/printer_data/config/polar_cloud.conf"
        self.config = configparser.ConfigParser()
        self.load_config()
        
        # Register API endpoints
        self.server.register_endpoint(
            "/server/polar_cloud/status", ["GET"],
            self._handle_status_request
        )
        self.server.register_endpoint(
            "/server/polar_cloud/register", ["POST"],
            self._handle_register_request
        )
        self.server.register_endpoint(
            "/server/polar_cloud/unregister", ["POST"],
            self._handle_unregister_request
        )
        self.server.register_endpoint(
            "/server/polar_cloud/config", ["GET", "POST"],
            self._handle_config_request
        )
        self.server.register_endpoint(
            "/server/polar_cloud/printer-types", ["GET"],
            self._handle_printer_types_request
        )
        
        logging.info("Polar Cloud plugin loaded")
    
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
    
    async def _handle_status_request(self, web_request):
        """Handle status requests"""
        try:
            # Check if service is running
            result = subprocess.run(
                ["systemctl", "is-active", "polar_cloud.service"],
                capture_output=True, text=True
            )
            
            service_status = "active" if result.returncode == 0 else "inactive"
            
            return {
                "service_status": service_status,
                "registered": bool(self.config.get('polar_cloud', 'serial_number', fallback='')),
                "serial_number": self.config.get('polar_cloud', 'serial_number', fallback=''),
                "username": self.config.get('polar_cloud', 'username', fallback=''),
                "machine_type": self.config.get('polar_cloud', 'machine_type', fallback='Cartesian'),
                "printer_type": self.config.get('polar_cloud', 'printer_type', fallback='Cartesian')
            }
        except Exception as e:
            logging.error(f"Error getting polar cloud status: {e}")
            return {"error": str(e)}
    
    async def _handle_register_request(self, web_request):
        """Handle registration requests"""
        try:
            args = web_request.get_args()
            username = args.get('username', '')
            pin = args.get('pin', '')
            machine_type = args.get('machine_type', 'Cartesian')
            printer_type = args.get('printer_type', 'Cartesian')
            
            if not username or not pin:
                return {"error": "Username and PIN are required"}
            
            # Update config
            self.config['polar_cloud']['username'] = username
            self.config['polar_cloud']['pin'] = pin
            self.config['polar_cloud']['machine_type'] = machine_type
            self.config['polar_cloud']['printer_type'] = printer_type
            self.save_config()
            
            # Restart service to pick up new config
            try:
                subprocess.run(["systemctl", "restart", "polar_cloud.service"], check=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Error restarting polar cloud service: {e}")
                return {"error": "Failed to restart service"}
            
            return {"success": True, "message": "Registration initiated"}
            
        except Exception as e:
            logging.error(f"Error handling registration: {e}")
            return {"error": str(e)}
    
    async def _handle_unregister_request(self, web_request):
        """Handle unregistration requests"""
        try:
            # Clear registration data
            self.config['polar_cloud']['username'] = ''
            self.config['polar_cloud']['pin'] = ''
            self.config['polar_cloud']['serial_number'] = ''
            self.save_config()
            
            # Restart service
            try:
                subprocess.run(["systemctl", "restart", "polar_cloud.service"], check=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Error restarting polar cloud service: {e}")
                return {"error": "Failed to restart service"}
            
            return {"success": True, "message": "Unregistered successfully"}
            
        except Exception as e:
            logging.error(f"Error handling unregistration: {e}")
            return {"error": str(e)}
    
    async def _handle_config_request(self, web_request):
        """Handle configuration requests"""
        try:
            if web_request.get_method() == "GET":
                # Return current configuration
                return {
                    "server_url": self.config.get('polar_cloud', 'server_url', fallback='wss://status-dev.polar3d.com'),
                    "username": self.config.get('polar_cloud', 'username', fallback=''),
                    "machine_type": self.config.get('polar_cloud', 'machine_type', fallback='Cartesian'),
                    "printer_type": self.config.get('polar_cloud', 'printer_type', fallback='Cartesian'),
                    "max_image_size": self.config.get('polar_cloud', 'max_image_size', fallback='150000'),
                    "verbose": self.config.get('polar_cloud', 'verbose', fallback='false'),
                    "serial_number": self.config.get('polar_cloud', 'serial_number', fallback='')
                }
            else:
                # Update configuration
                args = web_request.get_args()
                
                for key in ['server_url', 'machine_type', 'printer_type', 'max_image_size', 'verbose']:
                    if key in args:
                        self.config['polar_cloud'][key] = str(args[key])
                
                self.save_config()
                
                # Restart service if needed
                try:
                    subprocess.run(["systemctl", "restart", "polar_cloud.service"], check=True)
                except subprocess.CalledProcessError as e:
                    logging.error(f"Error restarting polar cloud service: {e}")
                    return {"error": "Failed to restart service"}
                
                return {"success": True, "message": "Configuration updated"}
                
        except Exception as e:
            logging.error(f"Error handling config request: {e}")
            return {"error": str(e)}

    async def _handle_printer_types_request(self, web_request):
        """Handle printer types requests"""
        try:
            # Get machine type from query parameters for filtering
            args = web_request.get_args()
            machine_type = args.get('machine_type', 'cartesian').lower()
            
            # Fetch printer types from Polar Cloud API with machine type filter
            async with aiohttp.ClientSession() as session:
                api_url = f'https://polar3d.com/api/v1/printer_makes?filter={machine_type}'
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Extract printer type names from the API response
                        printer_types = []
                        
                        # The API returns {"printerMakes": [...]} structure
                        if isinstance(data, dict) and 'printerMakes' in data:
                            printer_makes = data['printerMakes']
                            if isinstance(printer_makes, list):
                                printer_types = printer_makes
                        elif isinstance(data, list):
                            # Fallback for direct array response
                            for item in data:
                                if isinstance(item, dict) and 'name' in item:
                                    printer_types.append(item['name'])
                                elif isinstance(item, str):
                                    printer_types.append(item)
                        
                        # Add "Other/Custom" option
                        if printer_types:
                            printer_types.append("Other/Custom")
                        
                        # If no printer types found, provide machine-type specific defaults
                        if not printer_types:
                            if machine_type.lower() == 'cartesian':
                                printer_types = ['Cartesian', 'Ender 3', 'Prusa MK3S', 'Other/Custom']
                            elif machine_type.lower() == 'delta':
                                printer_types = ['Delta', 'Rostock Max', 'FLSUN Q5', 'Other/Custom']
                            elif machine_type.lower() == 'belt':
                                printer_types = ['Belt', 'CR-30 3DPrintMill', 'iFactory One', 'Other/Custom']
                            else:
                                printer_types = ['Cartesian', 'Delta', 'Belt', 'Other/Custom']
                        
                        return {"printer_types": printer_types}
                    else:
                        logging.warning(f"Failed to fetch printer types from Polar Cloud API: {response.status}")
                        # Return default types if API fails
                        return {"printer_types": ['Cartesian', 'Delta', 'Belt', 'Other/Custom']}
        except Exception as e:
            logging.error(f"Error fetching printer types: {e}")
            # Return default types if there's an error
            return {"printer_types": ['Cartesian', 'Delta', 'Belt', 'Other/Custom']}

def load_component(config):
    return PolarCloudPlugin(config) 