#!/bin/bash
# Script to update nginx configuration for better polar-cloud URL handling
# This script adds support for both /polar-cloud and /polar-cloud/ URLs

set -e

NGINX_CONFIG="/etc/nginx/sites-available/mainsail"
BACKUP_CONFIG="/etc/nginx/sites-available/mainsail.backup.$(date +%Y%m%d_%H%M%S)"

echo "Updating nginx configuration for polar-cloud URL handling..."

# Check if nginx config exists
if [ ! -f "$NGINX_CONFIG" ]; then
    echo "Error: Nginx configuration file not found at $NGINX_CONFIG"
    exit 1
fi

# Create backup
echo "Creating backup at $BACKUP_CONFIG"
cp "$NGINX_CONFIG" "$BACKUP_CONFIG"

# Check if polar-cloud configuration already exists
if grep -q "location.*polar-cloud" "$NGINX_CONFIG"; then
    echo "Polar-cloud configuration already exists. Checking if update is needed..."
    
    # Check if the redirect is already present
    if grep -q "location = /polar-cloud" "$NGINX_CONFIG"; then
        echo "Configuration is already up to date!"
        exit 0
    else
        echo "Updating existing configuration..."
        # Remove old polar-cloud location block
        sed -i '/location \/polar-cloud\//,/}/d' "$NGINX_CONFIG"
    fi
fi

# Add new configuration before the last closing brace
sed -i '/^}$/i\
\
    # Redirect /polar-cloud to /polar-cloud/ for user-friendliness\
    location = /polar-cloud {\
        return 301 $scheme://$host/polar-cloud/;\
    }\
\
    location /polar-cloud/ {\
        alias /home/pi/polar-cloud/web/;\
        try_files $uri $uri/ /polar-cloud/index.html;\
    }' "$NGINX_CONFIG"

# Test nginx configuration
echo "Testing nginx configuration..."
if nginx -t; then
    echo "Configuration test passed. Reloading nginx..."
    systemctl reload nginx
    echo "✅ Nginx configuration updated successfully!"
    echo "You can now access polar-cloud at both:"
    echo "  - http://your-printer-ip/polar-cloud"
    echo "  - http://your-printer-ip/polar-cloud/"
else
    echo "❌ Configuration test failed. Restoring backup..."
    cp "$BACKUP_CONFIG" "$NGINX_CONFIG"
    echo "Backup restored. Please check the configuration manually."
    exit 1
fi 