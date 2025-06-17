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
import json

class PolarCloudPlugin:
    def __init__(self, config):
        self.server = config.get_server()
        self.name = config.get_name()
        self.config_file = "/home/pi/printer_data/config/polar_cloud.conf"
        self.config = configparser.ConfigParser()
        self.load_config()
        
        # Register API endpoints using the correct Moonraker method
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
        
        logging.info("Polar Cloud plugin loaded successfully")

    async def component_init(self):
        """Called when all components have been loaded"""
        pass

    async def close(self):
        """Called when shutting down"""
        pass
    
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            # Create default config
            self.config['polar_cloud'] = {
                'server_url': 'https://printer4.polar3d.com',
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
            
            # Try to read real-time status from the service's status file
            status_file = '/tmp/polar_cloud_status.json'
            realtime_status = {}
            try:
                if os.path.exists(status_file):
                    with open(status_file, 'r') as f:
                        realtime_status = json.load(f)
            except Exception as e:
                logging.debug(f"Could not read status file: {e}")
            
            # Combine configuration and real-time status
            return {
                "service_status": service_status,
                "connected": realtime_status.get('connected', False),
                "authenticated": realtime_status.get('authenticated', False),
                "registered": bool(realtime_status.get('serial_number') or self.config.get('polar_cloud', 'serial_number', fallback='')),
                "serial_number": realtime_status.get('serial_number') or self.config.get('polar_cloud', 'serial_number', fallback=''),
                "username": realtime_status.get('username') or self.config.get('polar_cloud', 'username', fallback=''),
                "machine_type": realtime_status.get('machine_type') or self.config.get('polar_cloud', 'machine_type', fallback='Cartesian'),
                "printer_type": realtime_status.get('printer_type') or self.config.get('polar_cloud', 'printer_type', fallback='Cartesian'),
                "last_update": realtime_status.get('last_update', ''),
                "webcam_enabled": realtime_status.get('webcam_enabled', True)
            }
        except Exception as e:
            logging.error(f"Error getting polar cloud status: {e}")
            return {"error": str(e)}
    
    async def _handle_register_request(self, web_request):
        """Handle registration requests"""
        try:
            # Use the web_request methods to get parameters
            username = web_request.get_str('username', '')
            pin = web_request.get_str('pin', '')
            machine_type = web_request.get_str('machine_type', 'Cartesian')
            printer_type = web_request.get_str('printer_type', 'Cartesian')
            
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
            if web_request.get_action() == "GET":
                # Return current configuration
                return {
                    "server_url": self.config.get('polar_cloud', 'server_url', fallback='https://printer4.polar3d.com'),
                    "username": self.config.get('polar_cloud', 'username', fallback=''),
                    "machine_type": self.config.get('polar_cloud', 'machine_type', fallback='Cartesian'),
                    "printer_type": self.config.get('polar_cloud', 'printer_type', fallback='Cartesian'),
                    "max_image_size": self.config.get('polar_cloud', 'max_image_size', fallback='150000'),
                    "verbose": self.config.get('polar_cloud', 'verbose', fallback='false'),
                    "serial_number": self.config.get('polar_cloud', 'serial_number', fallback='')
                }
            else:
                # Update configuration
                for key in ['server_url', 'machine_type', 'printer_type', 'max_image_size', 'verbose']:
                    value = web_request.get_str(key, None)
                    if value is not None:
                        self.config['polar_cloud'][key] = value
                
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

def load_component(config):
    return PolarCloudPlugin(config) 