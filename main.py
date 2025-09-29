from sound_controller import SoundController
from light_controller import LightController
from state_manager import StateManager
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
SINGLE_CHIP_DIR = os.path.join(SONGS_DIR, "single_chip")
DOUBLE_CHIP_DIR = os.path.join(SONGS_DIR, "double_chip")


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


def get_songs_in_directory(directory_path):
    """Return list of audio files inside a specific directory (non-recursive)."""
    songs = []
    try:
        for filename in os.listdir(directory_path):
            if filename.lower().endswith((".mp3", ".wav", ".ogg", ".flac")):
                songs.append(os.path.join(directory_path, filename))
    except Exception as e:
        print(f"Error reading songs directory '{directory_path}': {e}")
    return songs


class RFIDHandler:
    def __init__(self, sound_controller, light_controller, code_to_song, state_manager: StateManager):
        self.sound = sound_controller
        self.light = light_controller
        self.state = state_manager
        self.code_to_song = code_to_song
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
                self._handle_double_chip()
                
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
                
                # For single chip, pick a random song from SINGLE_CHIP_DIR
                single_songs = get_songs_in_directory(SINGLE_CHIP_DIR)
                if single_songs:
                    selected_song = random.choice(single_songs)
                    print(f"Single chip confirmed. Playing random single-chip song: {selected_song}")
                    self.state.start_song(selected_song)
                else:
                    print(f"No songs found in {SINGLE_CHIP_DIR}")

    def _handle_double_chip(self):
        """Handle the case where two chips were detected within the window."""
        with self.processing_lock:
            # Dual chip case - pick a random song from DOUBLE_CHIP_DIR
            double_songs = get_songs_in_directory(DOUBLE_CHIP_DIR)
            if double_songs:
                random_song = random.choice(double_songs)
                print(f"Dual chip detected! Playing random double-chip song: {random_song}")
                self.state.start_song(random_song)
            else:
                print(f"No songs found in {DOUBLE_CHIP_DIR}")
            # Clear the recent codes after handling
            self.recent_codes.clear()


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
    light = LightController(simulation=True, persistent_gui=False)
    state = StateManager(sound, light)
    mode = _detect_operating_mode()
    rfid = RFIDReader(mode=mode)
    code_to_song = load_rfid_song_mapping(CSV_FILE)
    # Create the RFID handler
    handler = RFIDHandler(sound, light, code_to_song, state)

    # Ensure idle state on startup after light controller is ready
    try:
        light.wait_until_ready(5.0)
    except Exception:
        pass
    state.go_idle()

    print(f"Operating mode: {mode.value}")
    print("Ready for RFID scans. Scan a tag to play a song.")
    print("Scan two tags within 5 seconds for a random song!")
    
    # Get the GUI instance for main thread control
    gui_instance = light.get_gui_instance()
    
    # Start RFID reading in a background thread
    def rfid_worker():
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
    
    # Start RFID reading in background thread
    rfid_thread = threading.Thread(target=rfid_worker, daemon=True)
    rfid_thread.start()
    
    # Start GUI mainloop in main thread
    if gui_instance:
        try:
            gui_instance.start_mainloop()
        except KeyboardInterrupt:
            print("\nShutting down...")
    else:
        # If no GUI, just wait for the RFID thread
        try:
            rfid_thread.join()
        except KeyboardInterrupt:
            print("\nShutting down...")

if __name__ == "__main__":
    main()