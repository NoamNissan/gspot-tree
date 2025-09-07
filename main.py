from sound_controller import SoundController
from light_controller import LightController
from rfid_reader import RFIDReader, OperatingMode
import sys
import platform
import os
import csv
import time
import random
import threading
from collections import deque

SONGS_DIR = "songs"
CSV_FILE = "rfid_songs.csv"
DUAL_CHIP_WINDOW = 5  # seconds to wait for second chip


def load_rfid_song_mapping(csv_path):
    mapping = {}
    try:
        with open(csv_path, newline="") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) >= 2:
                    code, filename = row[0].strip(), row[1].strip()
                    mapping[code] = filename
    except Exception as e:
        print(f"Error reading CSV mapping: {e}")
    return mapping


def get_all_songs():
    """Get a list of all available song files in the songs directory."""
    songs = []
    try:
        for filename in os.listdir(SONGS_DIR):
            if filename.lower().endswith(('.mp3', '.wav', '.ogg', '.flac')):
                songs.append(filename)
    except Exception as e:
        print(f"Error reading songs directory: {e}")
    return songs


class RFIDHandler:
    def __init__(self, sound_controller, light_controller, code_to_song, all_songs):
        self.sound = sound_controller
        self.light = light_controller
        self.code_to_song = code_to_song
        self.all_songs = all_songs
        self.recent_codes = deque()  # Store recent codes with timestamps
        self.processing_lock = threading.Lock()
        
    def handle_rfid_code(self, code):
        """Handle incoming RFID codes with dual-chip detection logic."""
        with self.processing_lock:
            current_time = time.time()
            print(f"RFID code detected: {code}")
            
            # Add current code to recent codes
            self.recent_codes.append((code, current_time))
            
            # Remove codes older than our window
            while self.recent_codes and current_time - self.recent_codes[0][1] > DUAL_CHIP_WINDOW:
                self.recent_codes.popleft()
            
            # Check if we have two codes within the window
            if len(self.recent_codes) >= 2:
                # Dual chip case - play random song
                if self.all_songs:
                    random_song = random.choice(self.all_songs)
                    print(f"Dual chip detected! Playing random song: {random_song}")
                    self.sound.play_song(random_song)
                else:
                    print("No songs available for random selection")
                
                # Clear the recent codes after handling
                self.recent_codes.clear()
                
            elif len(self.recent_codes) == 1:
                # Single chip case - wait to see if another comes
                print(f"Single chip detected: {code}. Waiting {DUAL_CHIP_WINDOW}s for second chip...")
                
                # Start a timer to handle single chip case if no second chip comes
                timer = threading.Timer(DUAL_CHIP_WINDOW, self._handle_single_chip, args=[code])
                timer.start()
    
    def _handle_single_chip(self, code):
        """Handle the case where only one chip was detected within the window."""
        with self.processing_lock:
            # Check if this code is still in recent_codes (meaning no second chip came)
            if any(c[0] == code for c in self.recent_codes):
                # Remove this code from recent_codes
                self.recent_codes = deque([c for c in self.recent_codes if c[0] != code])
                
                # Proceed with normal single chip behavior
                song_file = self.code_to_song.get(code)
                if not song_file:
                    print(f"No song mapped for code: {code}")
                    return
                print(f"Single chip confirmed. Playing mapped song: {song_file}")
                self.sound.play_song(song_file)


def _detect_operating_mode() -> OperatingMode:
    """Detect the operating mode based on the current OS/hardware."""
    try:
        if sys.platform == "darwin":
            return OperatingMode.MACOS
        # Detect Raspberry Pi by checking device tree model
        try:
            with open("/proc/device-tree/model", "r") as f:
                model = f.read().lower()
                if "raspberry pi" in model:
                    return OperatingMode.RASPBERRY_PI
        except Exception:
            pass
        # Fallback: if on Linux and not a Pi, treat as generic Linux (stdin)
        if sys.platform.startswith("linux"):
            return OperatingMode.LINUX
    except Exception:
        pass
    # Default to Linux stdin behavior if detection fails
    return OperatingMode.LINUX


def main():
    sound = SoundController(SONGS_DIR)
    light = LightController()
    mode = _detect_operating_mode()
    rfid = RFIDReader(mode=mode)
    code_to_song = load_rfid_song_mapping(CSV_FILE)
    all_songs = get_all_songs()
    
    # Create the RFID handler
    handler = RFIDHandler(sound, light, code_to_song, all_songs)

    print(f"Operating mode: {mode.value}")
    print("Ready for RFID scans. Scan a tag to play a song.")
    print("Scan two tags within 5 seconds for a random song!")
    
    # Use continuous mode on Raspberry Pi; otherwise read line-by-line from stdin
    if mode == OperatingMode.RASPBERRY_PI:
        try:
            rfid.start_continuous_reading(handler.handle_rfid_code)
        except KeyboardInterrupt:
            print("\nShutting down...")
            rfid.stop_continuous_reading()
    else:
        try:
            while True:
                code = rfid.get_next_code()
                if code is None:
                    break
                if code:
                    handler.handle_rfid_code(code)
        except KeyboardInterrupt:
            print("\nShutting down...")

if __name__ == "__main__":
    main()