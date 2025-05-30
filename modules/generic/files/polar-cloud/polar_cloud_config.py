#!/usr/bin/env python3
"""
Polar Cloud Configuration Manager for MainsailOS
"""

import configparser
import os
import sys
import argparse
import subprocess

CONFIG_FILE = '/home/pi/printer_data/config/polar_cloud.conf'
SERVICE_NAME = 'polar_cloud'

def load_config():
    """Load configuration from file"""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    else:
        # Create default config
        config['polar_cloud'] = {
            'server_url': 'wss://status-dev.polar3d.com',
            'username': '',
            'pin': '',
            'machine_type': 'Cartesian',
            'printer_type': 'Cartesian',
            'verbose': 'false',
            'max_image_size': '150000'
        }
    return config

def save_config(config):
    """Save configuration to file"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        config.write(f)

def set_credentials(username, pin):
    """Set Polar Cloud credentials"""
    config = load_config()
    config['polar_cloud']['username'] = username
    config['polar_cloud']['pin'] = pin
    # Clear serial number to force re-registration
    if 'serial_number' in config['polar_cloud']:
        del config['polar_cloud']['serial_number']
    save_config(config)
    print(f"Credentials set for user: {username}")
    print("Serial number cleared - will re-register on next connection")

def show_config():
    """Show current configuration"""
    config = load_config()
    print("Current Polar Cloud Configuration:")
    print("=" * 40)
    for key, value in config['polar_cloud'].items():
        if key == 'pin' and value:
            print(f"{key}: {'*' * len(value)}")
        else:
            print(f"{key}: {value}")

def clear_registration():
    """Clear registration data"""
    config = load_config()
    if 'serial_number' in config['polar_cloud']:
        del config['polar_cloud']['serial_number']
        save_config(config)
        print("Registration data cleared")
    else:
        print("No registration data found")

def service_control(action):
    """Control the Polar Cloud service"""
    try:
        if action == 'status':
            result = subprocess.run(['systemctl', 'is-active', SERVICE_NAME], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Service {SERVICE_NAME} is {result.stdout.strip()}")
            else:
                print(f"Service {SERVICE_NAME} is inactive")
        else:
            subprocess.run(['sudo', 'systemctl', action, SERVICE_NAME], check=True)
            print(f"Service {SERVICE_NAME} {action} completed")
    except subprocess.CalledProcessError as e:
        print(f"Error controlling service: {e}")
    except FileNotFoundError:
        print("systemctl not found - service control not available")

def main():
    parser = argparse.ArgumentParser(description='Polar Cloud Configuration Manager')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Set credentials command
    cred_parser = subparsers.add_parser('set-credentials', help='Set Polar Cloud credentials')
    cred_parser.add_argument('username', help='Polar Cloud username/email')
    cred_parser.add_argument('pin', help='Polar Cloud PIN')
    
    # Show config command
    subparsers.add_parser('show', help='Show current configuration')
    
    # Clear registration command
    subparsers.add_parser('clear-registration', help='Clear registration data')
    
    # Service control commands
    service_parser = subparsers.add_parser('service', help='Control Polar Cloud service')
    service_parser.add_argument('action', choices=['start', 'stop', 'restart', 'status', 'enable', 'disable'],
                               help='Service action')
    
    args = parser.parse_args()
    
    if args.command == 'set-credentials':
        set_credentials(args.username, args.pin)
    elif args.command == 'show':
        show_config()
    elif args.command == 'clear-registration':
        clear_registration()
    elif args.command == 'service':
        service_control(args.action)
    else:
        parser.print_help()

if __name__ == '__main__':
    main() 