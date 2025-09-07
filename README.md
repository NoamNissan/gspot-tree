# Orchestrator for Raspberry Pi

This project is designed to run on a Raspberry Pi and orchestrate sound and light controllers, as well as interact with an RFID reader. The RFID reader identifies as a keyboard (STB-IN), and each scan triggers the playback of a song associated with the scanned code.

## Features
- Waits for RFID events (keyboard input)
- Matches RFID codes to song files using a CSV mapping file
- Plays songs through the audio controller
- **NEW: Dual RFID chip detection** - Scan two different RFID chips within 5 seconds to trigger a random song from the song library
- Light controller stub (no-op for now)

## Hardware
- Raspberry Pi (any model with USB and audio output)
- USB RFID reader (keyboard emulation)
- Audio output (speakers or headphones)
- (Optional) Light controller hardware

## Usage
1. Place your song files in the `songs/` directory. You can use any filename for your songs (e.g., `song1.mp3`, `mytrack.wav`).
2. In the project root, create a file named `rfid_songs.csv` with the following format:

   ```
   RFID_CODE,song_filename
   1234567890,song1.mp3
   9876543210,mytrack.wav
   ```
   Each line should contain an RFID code and the corresponding song filename, separated by a comma.
3. Run the main script: `python3 main.py`
4. Scan an RFID tag to play the corresponding song.

## Dual RFID Chip Feature
The system now supports a special dual-chip mode:
- **Single chip scan**: Plays the mapped song for that RFID code (after waiting 5 seconds to see if a second chip comes)
- **Dual chip scan**: If two different RFID chips are scanned within 5 seconds, the system plays a random song from the entire song library
- **Timing window**: The system waits 5 seconds after the first chip to see if a second chip is scanned

This feature adds an element of surprise and variety to the music selection, making the experience more interactive and fun.

## Testing
Run the test script to verify the dual RFID chip functionality:
```bash
python3 test_dual_rfid.py
```

## Requirements
See `requirements.txt` for dependencies.