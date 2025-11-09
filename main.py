from sound_controller import SoundController
from light_controller import LightController
from state_manager import StateManager, SystemState
from rfid_reader import RFIDReader, OperatingMode
import argparse
import sys
import platform
import os
import csv
import time
import random
import threading
import subprocess
from collections import deque
from constants import DUAL_CHIP_WINDOW, ChipType, NUM_PIXELS

SONGS_DIR = "songs"
CSV_FILE = "rfid_songs.csv"
STOP_CHIPS_FILE = "stop_chips.txt"

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


def load_stop_chips(txt_path):
    """Load chip IDs from a text file that should stop music playback.
    
    Returns:
        set: Set of chip IDs that trigger music stop
    """
    stop_chips = set()
    try:
        if not os.path.exists(txt_path):
            print(f"Stop chips file not found: {txt_path}. No stop chips configured.")
            return stop_chips
        
        with open(txt_path, "r") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    stop_chips.add(line)
        if stop_chips:
            print(f"Loaded {len(stop_chips)} stop chip(s) from {txt_path}: {stop_chips}")
        else:
            print(f"No stop chips loaded from {txt_path}")
    except Exception as e:
        print(f"Error reading stop chips file '{txt_path}': {e}")
    return stop_chips


class RFIDHandler:
    def __init__(self, sound_controller, light_controller, code_to_song, state_manager: StateManager, stop_chips: set):
        self.sound = sound_controller
        self.light = light_controller
        self.state = state_manager
        self.code_to_song = code_to_song
        self.stop_chips = stop_chips
        self.recent_codes = deque()  # Store recent codes with timestamps
        self.processing_lock = threading.Lock()
        self.pending_timer = None  # Timer for pending state timeout
        
    def handle_rfid_code(self, code):
        """Handle incoming RFID codes with dual-chip detection logic."""
        print(f"RFID code detected: {code}")
        with self.processing_lock:
            print(f"Processing code: {code}")
            # Normalize the code (strip whitespace) to ensure consistent matching
            normalized_code = code.strip() if code else code
            
            # Debug: print received code for troubleshooting
            current_state = self.state.get_state()
            if current_state == SystemState.PLAYING:
                print(f"RFID code received during playback: '{normalized_code}' (original: '{code}')")
            
            # Check if this is a stop chip - if so, stop music immediately regardless of state
            # This check happens BEFORE checking if music is playing, so stop chips always work
            if normalized_code in self.stop_chips:
                if current_state == SystemState.PLAYING:
                    print(f"Stop chip detected: '{normalized_code}'. Stopping music immediately and returning to idle.")
                    self.state.end_song()
                elif current_state == SystemState.PENDING:
                    print(f"Stop chip detected: '{normalized_code}'. Cancelling pending state and returning to idle.")
                    # Cancel pending timer if it's running
                    if self.pending_timer is not None:
                        self.pending_timer.cancel()
                        self.pending_timer = None
                    self.state.go_idle()
                    self.recent_codes.clear()
                else:
                    print(f"Stop chip detected: '{normalized_code}'. Already in idle state.")
                return
            
            # If a song is currently playing, completely ignore the chip (unless it's a stop chip, handled above)
            if current_state == SystemState.PLAYING:
                print(f"RFID code detected while playing: '{normalized_code}'. Ignoring - no effect.")
                return
            
            current_time = time.time()
            print(f"RFID code detected: {normalized_code}")
            
            # Use normalized code for all subsequent processing
            code = normalized_code
            
            # Add current code to recent codes
            self.recent_codes.append((code, current_time))
            
            # Remove codes older than our window
            while self.recent_codes and current_time - self.recent_codes[0][1] > DUAL_CHIP_WINDOW:
                self.recent_codes.popleft()
            
            # Check if we have two codes within the window
            if len(self.recent_codes) >= 2:
                # Only handle double chip if the two most recent codes are different
                if self.recent_codes[-1][0] != self.recent_codes[-2][0]:
                    # Cancel pending timer if it's running
                    if self.pending_timer is not None:
                        self.pending_timer.cancel()
                        self.pending_timer = None
                    self._handle_double_chip()
                
            elif len(self.recent_codes) == 1:
                # First chip detected - switch to pending state immediately
                print(f"First chip detected: {code}. Switching to pending state (flashing blue lights)")
                print(f"Waiting {DUAL_CHIP_WINDOW}s for second chip...")
                
                # Switch to pending state with blue flashing lights
                self.state.go_pending()
                
                # Cancel any existing pending timer
                if self.pending_timer is not None:
                    self.pending_timer.cancel()
                
                # Start a timer to handle single chip case if no second chip comes
                self.pending_timer = threading.Timer(DUAL_CHIP_WINDOW, self._handle_single_chip, args=[code])
                self.pending_timer.start()
    
    def _handle_single_chip(self, code):
        """Handle the case where only one chip was detected within the window."""
        with self.processing_lock:
            # Clear the pending timer reference
            self.pending_timer = None
            
            # Check if this code is still in recent_codes (meaning no second chip came)
            if any(c[0] == code for c in self.recent_codes):
                # Remove this code from recent_codes
                self.recent_codes = deque([c for c in self.recent_codes if c[0] != code])
                
                # For single chip, pick a random song from SINGLE_CHIP_DIR
                single_songs = get_songs_in_directory(SINGLE_CHIP_DIR)
                if single_songs:
                    selected_song = random.choice(single_songs)
                    print(f"Pending state ended - no second chip. Playing random single-chip song: {selected_song}")
                    self.state.start_song(selected_song, ChipType.SINGLE, callback=self.state.end_song)
                else:
                    print(f"No songs found in {SINGLE_CHIP_DIR}")
                    # If no songs found, return to idle
                    self.state.go_idle()

    def _handle_double_chip(self):
        """Handle the case where two chips were detected within the window."""
        print("Handling double chip - second chip detected during pending state")
        # Assumes caller holds self.processing_lock
        # Dual chip case - pick a random song from DOUBLE_CHIP_DIR
        double_songs = get_songs_in_directory(DOUBLE_CHIP_DIR)
        if double_songs:
            random_song = random.choice(double_songs)
            print(f"Dual chip detected! Playing random double-chip song: {random_song}")
            self.state.start_song(random_song, ChipType.DOUBLE, callback=self.state.end_song)
        else:
            print(f"No songs found in {DOUBLE_CHIP_DIR}")
            # If no songs found, return to idle
            self.state.go_idle()
        # Clear the recent codes after handling
        self.recent_codes.clear()


def check_sudo_permission():
    """Check if the process can run sudo commands."""
    try:
        # Try to run sudo with -n flag (non-interactive) to check if passwordless sudo is available
        result = subprocess.run(['sudo', '-n', 'true'], capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def setup_memory_permissions():
    """Execute sudo chmod 0666 /dev/mem to set proper permissions."""
    try:
        print("Setting up memory permissions...")
        result = subprocess.run(['sudo', 'chmod', '0666', '/dev/mem'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("Memory permissions set successfully.")
            return True
        else:
            print(f"Failed to set memory permissions: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("Timeout while setting memory permissions.")
        return False
    except Exception as e:
        print(f"Error setting memory permissions: {e}")
        return False


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
    # Check sudo permissions and setup memory permissions first
    print("Checking system permissions...")
    if not check_sudo_permission():
        print("Warning: Sudo permission not available. Some features may not work properly.")
        print("Please ensure this process can run sudo commands or run with appropriate permissions.")
    else:
        print("Sudo permission confirmed.")
        # Execute the chmod command to set memory permissions
        if not setup_memory_permissions():
            print("Warning: Failed to set memory permissions. Hardware access may be limited.")
    
    parser = argparse.ArgumentParser(description="GSpot Tree main controller")
    parser.add_argument("--simulation", dest="simulation", action="store_true", help="Run LED controller in simulation mode")
    parser.add_argument("--no-simulation", dest="simulation", action="store_false", help="Disable simulation mode")
    parser.add_argument("--persistent-gui", dest="persistent_gui", action="store_true", help="Keep mock LED GUI open persistently (simulation only)")
    parser.add_argument("--no-persistent-gui", dest="persistent_gui", action="store_false", help="Do not start persistent mock LED GUI")
    parser.set_defaults(simulation=False, persistent_gui=False)
    args = parser.parse_args()

    mode = _detect_operating_mode()
    sound = SoundController(SONGS_DIR, mode=mode)
    light = LightController(num_pixels=NUM_PIXELS, simulation=args.simulation, persistent_gui=args.persistent_gui)
    state = StateManager(sound, light)
    rfid = RFIDReader(mode=mode)
    code_to_song = load_rfid_song_mapping(CSV_FILE)
    stop_chips = load_stop_chips(STOP_CHIPS_FILE)
    # Create the RFID handler
    handler = RFIDHandler(sound, light, code_to_song, state, stop_chips)

    # Ensure idle state on startup after light controller is ready
    try:
        light.wait_until_ready(5.0)
    except Exception:
        pass
    state.go_idle()

    print(f"Operating mode: {mode.value}")
    
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
            except Exception as e:
                print(f"Error in RFID worker: {e}")
                rfid.stop_continuous_reading()
        else:
            try:
                while True:
                    if rfid.is_shutdown_requested():
                        break
                    code = rfid.get_next_code()
                    if code is None:
                        break
                    if code:
                        handler.handle_rfid_code(code)
            except KeyboardInterrupt:
                print("\nShutting down...")
            except Exception as e:
                print(f"Error in RFID worker: {e}")
    
    # Start RFID reading in background thread
    rfid_thread = threading.Thread(target=rfid_worker, daemon=True)
    rfid_thread.start()
    
    print("Ready for RFID scans. Scan a tag to play a song.")
    print("Scan two tags within 5 seconds for a random song!")

    # Start GUI mainloop in main thread
    if gui_instance:
        try:
            gui_instance.start_mainloop()
        except KeyboardInterrupt:
            print("\nShutting down...")
            rfid.stop_continuous_reading()
    else:
        # If no GUI, just wait for the RFID thread
        try:
            # Wait for the RFID thread with a timeout to allow for shutdown
            while rfid_thread.is_alive() and not rfid.is_shutdown_requested():
                rfid_thread.join(timeout=0.1)  # Check every 100ms
        except KeyboardInterrupt:
            print("\nShutting down...")
            rfid.stop_continuous_reading()
            # Wait a bit for threads to finish, but don't block indefinitely
            try:
                rfid_thread.join(timeout=2.0)
            except KeyboardInterrupt:
                print("Force shutdown...")
                pass
    
    # Check if shutdown was requested and exit
    if rfid.is_shutdown_requested():
        print("Shutdown requested, exiting...")
        sys.exit(0)

if __name__ == "__main__":
    main()