# WiFi Fallback AP Mode Setup

This directory contains installation files to set up automatic WiFi fallback to AP mode on a Raspberry Pi using NetworkManager's built-in AP functionality.

## What it does

- Waits 30 seconds after boot
- Checks if connected to **any** WiFi network
- If not connected, automatically starts AP mode with:
  - **SSID**: `tao`
  - **Password**: `tao-wifi`
  - **Uses NetworkManager's shared connection** (automatic DHCP and routing)

## Installation

1. Copy this entire directory to your Raspberry Pi
2. Navigate to the directory
3. Run the installation script as root:

```bash
sudo ./install_ap_service.sh
```

## Files included

- `wifi-fallback.sh` - Main script using nmcli for AP creation
- `wifi-fallback.service` - Systemd service file
- `install_ap_service.sh` - Installation script
- `README.md` - This file

## How it works

The script uses NetworkManager's built-in AP functionality via `nmcli`:
- Creates a WiFi connection profile in AP mode
- Uses `ipv4.method shared` for automatic DHCP and internet sharing
- Much more reliable than manual hostapd/dnsmasq configuration

## Testing

To test the fallback functionality:

1. Disconnect from all WiFi networks or move out of range
2. Reboot the system
3. After 30 seconds, the system should start broadcasting "tao" WiFi network

## Monitoring

Check service status:
```bash
sudo systemctl status wifi-fallback.service
```

View service logs:
```bash
sudo journalctl -u wifi-fallback.service
```

Check NetworkManager connections:
```bash
nmcli connection show
```

## Manual operation

To manually trigger AP mode (for testing):
```bash
sudo /usr/local/bin/wifi-fallback.sh
```

To manually create AP:
```bash
nmcli connection up tao-ap
```

To stop AP mode:
```bash
nmcli connection down tao-ap
```

## Advantages over hostapd approach

- **Simpler**: Uses NetworkManager's built-in functionality
- **More reliable**: No conflicts between NetworkManager and hostapd
- **Automatic DHCP**: Built-in DHCP server and internet sharing
- **Better integration**: Works seamlessly with existing network management

## Uninstallation

To remove the service:
```bash
sudo systemctl disable wifi-fallback.service
sudo systemctl stop wifi-fallback.service
sudo rm /etc/systemd/system/wifi-fallback.service
sudo rm /usr/local/bin/wifi-fallback.sh
sudo nmcli connection delete tao-ap
sudo systemctl daemon-reload
```
