#!/bin/bash

# Wait 30 seconds after boot
sleep 30

# Check if connected to any WiFi network
if /usr/sbin/iwgetid -r >/dev/null 2>&1; then
    SSID=$(/usr/sbin/iwgetid -r)
    echo "Connected to WiFi network: $SSID, exiting"
    exit 0
fi

echo "Not connected to any WiFi network, starting AP mode"

# Create AP using nmcli
nmcli connection add type wifi ifname wlan0 con-name tao-ap autoconnect yes ssid tao
nmcli connection modify tao-ap 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared
nmcli connection modify tao-ap wifi-sec.key-mgmt wpa-psk
nmcli connection modify tao-ap wifi-sec.psk "tao-wifi"
nmcli connection up tao-ap

echo "AP mode started: SSID=tao, Password=tao-wifi"
