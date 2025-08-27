#!/bin/bash

echo "Installing WiFi Fallback AP Service..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Update package list and install required packages
echo "Installing required packages..."
apt update
apt install -y wireless-tools

# Copy script to system location
echo "Installing WiFi fallback script..."
cp wifi-fallback.sh /usr/local/bin/
chmod +x /usr/local/bin/wifi-fallback.sh

# Install systemd service
echo "Installing systemd service..."
cp wifi-fallback.service /etc/systemd/system/

# Reload systemd and enable service
echo "Enabling service..."
systemctl daemon-reload
systemctl enable wifi-fallback.service

echo ""
echo "Installation complete!"
echo ""
echo "The service will:"
echo "1. Wait 30 seconds after boot"
echo "2. Check if connected to any WiFi network"
echo "3. If not connected, start AP mode with:"
echo "   - SSID: tao"
echo "   - Password: tao-wifi"
echo "   - Uses NetworkManager's built-in AP functionality"
echo ""
echo "To test: Reboot the system without any WiFi available"
echo "Service status: systemctl status wifi-fallback.service"
