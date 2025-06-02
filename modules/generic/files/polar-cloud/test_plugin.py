#!/usr/bin/env python3
"""
Test script to verify the Polar Cloud Moonraker plugin loads correctly
"""

import sys
import os

# Mock the Moonraker config object for testing
class MockConfig:
    def __init__(self):
        self.server = MockServer()
    
    def get_server(self):
        return self.server

class MockServer:
    def __init__(self):
        self.endpoints = []
    
    def register_endpoint(self, path, methods, handler):
        self.endpoints.append((path, methods, handler))
        print(f"Registered endpoint: {methods} {path}")

def test_plugin_loading():
    """Test that the plugin can be loaded without errors"""
    print("Testing Polar Cloud plugin loading...")
    
    try:
        # Import the plugin
        sys.path.insert(0, os.path.dirname(__file__))
        from polar_cloud_moonraker import load_component
        
        # Create mock config
        config = MockConfig()
        
        # Load the component
        plugin = load_component(config)
        
        print(f"Plugin loaded successfully: {plugin.__class__.__name__}")
        print(f"Plugin name: {getattr(plugin, 'name', 'Not set')}")
        print(f"Registered {len(config.server.endpoints)} endpoints:")
        
        for path, methods, handler in config.server.endpoints:
            print(f"  {methods} {path} -> {handler.__name__}")
        
        return True
        
    except Exception as e:
        print(f"Error loading plugin: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_plugin_loading()
    sys.exit(0 if success else 1) 