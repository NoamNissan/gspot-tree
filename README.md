# Orchestrator for Raspberry Pi

This project is designed to run on a Raspberry Pi and orchestrate sound and light controllers, as well as interact with an RFID reader. The RFID reader identifies as a keyboard (STB-IN), and each scan triggers the playback of a song associated with the scanned code.

## Features
- Waits for RFID events (keyboard input)
- Matches RFID codes to song files using a CSV mapping file
- Plays songs through the audio controller
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

## Requirements
See `requirements.txt` for dependencies.