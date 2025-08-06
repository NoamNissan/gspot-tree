# Troubleshooting Audio Issues on Raspberry Pi

## Common Audio Problems

### 0. "No internal audio devices found" Error
If you see this message in raspi-config or when checking audio devices:

**Solution 1: Update and install audio packages**
```bash
sudo apt update
sudo apt upgrade
sudo apt install python3-pygame
sudo apt install libasound2-dev
sudo apt install pulseaudio pulseaudio-utils
```

**Solution 2: Enable audio in config**
```bash
# Edit config file
sudo nano /boot/config.txt

# Add or uncomment these lines:
dtparam=audio=on
dtoverlay=disable-bt
```

**Solution 3: Check audio modules**
```bash
# Check if audio modules are loaded
lsmod | grep snd

# If empty, load them manually
sudo modprobe snd_bcm2835
sudo modprobe snd_pcm
sudo modprobe snd_timer
```

**Solution 4: Reboot and test**
```bash
sudo reboot

# After reboot, test audio
speaker-test -t wav -c 2
```

### 1. ALSA Audio Device Error
If you get errors like "Couldn't open audio device" or "Unknown error 524":

**Solution 1: Check audio output**
```bash
# Check if audio is enabled
sudo raspi-config
# Navigate to System Options > Audio > Force 3.5mm ('headphone') jack

# Or check current audio output
amixer get Master
```

**Solution 2: Install/update audio packages**
```bash
sudo apt update
sudo apt install python3-pygame
sudo apt install libasound2-dev
```

**Solution 3: Set default audio device**
```bash
# Create/edit ALSA config
sudo nano /etc/asound.conf

# Add these lines:
pcm.!default {
    type hw
    card 0
    device 0
}

ctl.!default {
    type hw
    card 0
}
```

### 2. No Sound Output
**Check volume levels:**
```bash
# Set volume to 100%
amixer set Master 100%
amixer set PCM 100%

# Or use alsamixer for interactive control
alsamixer
```

### 3. HDMI Audio Issues
If using HDMI audio:
```bash
# Force HDMI audio
sudo raspi-config
# Navigate to System Options > Audio > Force HDMI
```

### 4. Test Audio
Test if audio works at system level:
```bash
# Test with aplay
speaker-test -t wav -c 2

# Or play a test file
aplay /usr/share/sounds/alsa/Front_Left.wav
```

## Running the Script
If audio still doesn't work, the script will now run without audio and just print what it would play. You can still test the RFID functionality this way.

## Additional Debugging
Run the script with verbose output to see what's happening:
```bash
python3 main.py
```

The script will now try multiple audio initialization methods and provide detailed feedback about what's working or not. 