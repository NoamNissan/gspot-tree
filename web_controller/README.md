# LED Web Controller

Control your LED effects from your phone browser!

## Setup

1. Install Flask:
```bash
pip3 install flask
```

2. Start the web server:
```bash
cd /home/tao/repo/gspot-tree/web_controller
python3 app.py
```

3. Open your phone browser and go to:
```
http://<raspberry-pi-ip>:5000
```

## Features

- 📱 **Mobile-friendly interface** - Works great on phones
- 🎵 **All LED recipes** - Music spectrum, pulse, rainbow, etc.
- ⚙️ **Adjustable LED count** - Set number of pixels
- 🔄 **Real-time status** - See what's currently running
- 🛑 **Stop button** - Kill all effects instantly

## Available Effects

- **Music Spectrum** - 3-band spectrum (bottom-up)
- **Music Spectrum Center** - 3-band spectrum (center-out)  
- **Enhanced Spectrum** - 6-band spectrum (bottom-up)
- **Enhanced Spectrum Center** - 6-band spectrum (center-out)
- **Enhanced Spectrum 9-Band** - 9-band spectrum
- **Music Pulse** - Colors pulse with music
- **Rainbow** - Classic rainbow cycling
- **Rainbow Wave** - Rainbow with wave effects
- **Sunset Breathing** - Calm red-pink breathing

## Usage

1. Set the number of LEDs (default: 60)
2. Tap any effect card to start it
3. The running effect will be highlighted
4. Use "Stop All Effects" to turn everything off

## Technical Details

- **Backend:** Flask web server
- **Process management:** Subprocess control of LED orchestrator
- **Auto-cleanup:** Kills previous effects when starting new ones
- **Status updates:** Real-time status every 2 seconds
