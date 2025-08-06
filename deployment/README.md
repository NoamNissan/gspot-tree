# GSpot Tree Deployment Scripts

This directory contains deployment scripts for the GSpot Tree project.

## Scripts

### `install`
The installation script that sets up the GSpot Tree as a systemd service on the Raspberry Pi.

**Usage:**
```bash
# On the Raspberry Pi, run as root:
sudo ./deployment/install
```

**What it does:**
- Creates the application directory at `/home/gspot/gspot-tree`
- Copies all application files
- Installs Python dependencies
- Creates and enables a systemd service called `gspot-tree`
- Starts the service and configures it to run on boot

### `update`
The update script that copies the latest code from your development machine to the Raspberry Pi and restarts the service.

**Usage:**
```bash
# On your development machine, from the project root:
./deployment/update
```

**What it does:**
- Syncs all project files to the Raspberry Pi (excluding git files, cache, etc.)
- Updates Python dependencies on the Pi
- Restarts the systemd service
- Shows the service status

## Configuration

Before using the `update` script, you need to configure the Raspberry Pi connection details:

1. Edit `deployment/update` and update these variables:
   ```bash
   PI_HOSTNAME="gspot.local"  # Change to your Pi's hostname or IP
   PI_USER="gspot"            # Change if using a different user
   ```

2. Ensure SSH key-based authentication is set up between your development machine and the Raspberry Pi.

## Prerequisites

### On the Raspberry Pi:
- Raspberry Pi OS (or compatible Linux distribution)
- Python 3.6+
- pip
- Audio output configured

### On the Development Machine:
- rsync (install with `brew install rsync` on macOS or `sudo apt-get install rsync` on Ubuntu)
- SSH access to the Raspberry Pi
- SSH key-based authentication configured

## Service Management

Once installed, you can manage the service using standard systemctl commands:

```bash
# Check service status
sudo systemctl status gspot-tree

# View logs
sudo journalctl -u gspot-tree -f

# Stop the service
sudo systemctl stop gspot-tree

# Start the service
sudo systemctl start gspot-tree

# Restart the service
sudo systemctl restart gspot-tree

# Disable auto-start on boot
sudo systemctl disable gspot-tree

# Enable auto-start on boot
sudo systemctl enable gspot-tree
```

## Troubleshooting

### Service won't start
1. Check the logs: `sudo journalctl -u gspot-tree -f`
2. Verify Python dependencies are installed: `pip3 list`
3. Check file permissions: `ls -la /home/gspot/gspot-tree/`
4. Test the application manually: `cd /home/gspot/gspot-tree && python3 main.py`

### Update script fails
1. Verify SSH connectivity: `ssh gspot@gspot.local`
2. Check if rsync is installed on your development machine
3. Ensure the Pi hostname/IP is correct in the update script
4. Verify the Pi is on the same network as your development machine

### Audio issues
1. Check audio output: `aplay -l`
2. Verify ALSA is configured: `alsamixer`
3. Test audio: `speaker-test -t wav -c 2`
4. Check if the service has audio group permissions 