import sys
import logging
import signal
import threading
from typing import Optional
from enum import Enum
from rfid_decoder import RFIDDecoder

class OperatingMode(Enum):
    """Enumeration for RFID reader operating modes."""
    LINUX = "linux"
    RASPBERRY_PI = "raspberry_pi"
    MACOS = "macos"

class RFIDReader:
    """
    RFID Reader that supports multiple modes:
    - Linux mode: Reads from standard input
    - macOS mode: Reads from standard input
    - Raspberry Pi mode: Uses RFIDDecoder to read from hardware device
    """
    
    def __init__(self, mode: OperatingMode = OperatingMode.RASPBERRY_PI, device_path: Optional[str] = None):
        """
        Initialize the RFID reader with the specified mode.
        
        Args:
            mode (OperatingMode): Either OperatingMode.LINUX or OperatingMode.RASPBERRY_PI
            device_path (Optional[str]): Path to RFID device (only used in raspberry_pi mode). 
                                       If None, will auto-detect the RFID device.
        """
        self.mode = mode
        self.device_path = device_path
        self.is_running = False
        self._shutdown_event = threading.Event()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        if self.mode in (OperatingMode.LINUX, OperatingMode.MACOS):
            self.input_stream = sys.stdin
            self.rfid_decoder = None
        elif self.mode == OperatingMode.RASPBERRY_PI:
            self.input_stream = None
            # Pass None to auto-detect, or the specified device_path
            self.rfid_decoder = RFIDDecoder(device_path, log_level=logging.DEBUG)
        else:
            raise ValueError(
                f"Invalid mode: {mode}. Must be OperatingMode.LINUX, OperatingMode.MACOS, or OperatingMode.RASPBERRY_PI"
            )
    
    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals (SIGINT, SIGTERM).
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        print(f"\nReceived signal {signum}. Shutting down gracefully...")
        self._shutdown_event.set()
        self.stop_continuous_reading()
        sys.exit(0)
    
    def get_next_code(self) -> Optional[str]:
        """
        Blocks until a line is read from the input stream, then returns the stripped code.
        
        Returns:
            Optional[str]: The RFID code, or None if interrupted/error
        """
        if self.mode in (OperatingMode.LINUX, OperatingMode.MACOS):
            try:
                code = self.input_stream.readline()
                if self._shutdown_event.is_set():
                    return None
                return code.strip()
            except KeyboardInterrupt:
                print("\nKeyboardInterrupt received. Shutting down...")
                return None
        elif self.mode == OperatingMode.RASPBERRY_PI:
            try:
                return self.rfid_decoder.read_rfid()
            except KeyboardInterrupt:
                print("\nKeyboardInterrupt received. Shutting down...")
                self.stop_continuous_reading()
                return None
    
    def start_continuous_reading(self, callback):
        """
        Start continuous reading mode (only available in raspberry_pi mode).
        
        Args:
            callback: Function to call when RFID code is scanned
        """
        if self.mode != OperatingMode.RASPBERRY_PI:
            raise ValueError("Continuous reading is only available in raspberry_pi mode")
        
        self.is_running = True
        self.rfid_decoder.set_callback(callback)
        
        try:
            self.rfid_decoder.start()
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt received during continuous reading. Shutting down...")
            self.stop_continuous_reading()
        except Exception as e:
            print(f"Error during continuous reading: {e}")
            self.stop_continuous_reading()
    
    def stop_continuous_reading(self):
        """
        Stop continuous reading mode (only available in raspberry_pi mode).
        """
        self.is_running = False
        if self.mode == OperatingMode.RASPBERRY_PI and self.rfid_decoder:
            self.rfid_decoder.stop()
    
    def get_mode(self) -> OperatingMode:
        """
        Get the current mode.
        
        Returns:
            OperatingMode: Current mode
        """
        return self.mode
    
    def is_shutdown_requested(self) -> bool:
        """
        Check if shutdown has been requested.
        
        Returns:
            bool: True if shutdown is requested
        """
        return self._shutdown_event.is_set()