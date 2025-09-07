import sys
try:
    from evdev import InputDevice, categorize, ecodes, list_devices
    EVDEV_AVAILABLE = True
except Exception:
    # evdev is Linux-only; allow import on macOS/Windows and fail gracefully at runtime
    EVDEV_AVAILABLE = False
    InputDevice = None  # type: ignore
    categorize = None  # type: ignore
    ecodes = None  # type: ignore
    list_devices = None  # type: ignore
import time
import logging
import signal
import threading
from typing import Optional, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def find_rfid_device(target_description: str = "HID 5131:2007") -> Optional[str]:
    """
    Find the RFID device with the specified description.
    
    Args:
        target_description (str): The device description to look for
        
    Returns:
        Optional[str]: Path to the device if found, None otherwise
    """
    logger = logging.getLogger('RFIDDeviceFinder')

    if not EVDEV_AVAILABLE:
        logger.warning("evdev is not available on this platform (%s). RFID reader is disabled.", sys.platform)
        return None
    
    try:
        devices = list_devices()
        logger.info(f"Scanning {len(devices)} input devices for RFID reader...")
        
        for device_path in devices:
            try:
                device = InputDevice(device_path)
                device_info = device.info
                device_name = device.name
                device_phys = device.phys
                
                logger.debug(f"Device {device_path}: name='{device_name}', phys='{device_phys}'")
                
                # Check if this device matches our target description
                if target_description in device_name or target_description in str(device_info):
                    logger.info(f"Found RFID device: {device_path} - {device_name}")
                    return device_path
                    
            except Exception as e:
                logger.debug(f"Error reading device {device_path}: {e}")
                continue
        
        logger.warning(f"No device found with description '{target_description}'")
        logger.info("Available devices:")
        for device_path in devices:
            try:
                device = InputDevice(device_path)
                logger.info(f"  {device_path}: {device.name}")
            except Exception as e:
                logger.debug(f"  {device_path}: Error reading device info - {e}")
        
        return None
        
    except Exception as e:
        logger.error(f"Error scanning for devices: {e}")
        return None

class RFIDDecoder:
    """
    A class that encapsulates RFID decoding logic and provides a clean interface
    for reading RFID codes from a device.
    """
    
    def __init__(self, device_path: Optional[str] = None, log_level: int = logging.INFO):
        """
        Initialize the RFID decoder with the specified device path or auto-detect.
        
        Args:
            device_path (Optional[str]): Path to the RFID input device. If None, auto-detect.
            log_level (int): Logging level (default: logging.INFO)
        """
        # Configure logger for this instance
        self.logger = logging.getLogger('RFIDDecoder')
        self.logger.setLevel(log_level)
        
        if not EVDEV_AVAILABLE:
            raise RuntimeError(
                "RFID reader requires 'evdev', which is only available on Linux. "
                f"Current platform: {sys.platform}. Run on a Linux device (e.g., Raspberry Pi)."
            )

        # Auto-detect device if not provided
        if device_path is None:
            self.logger.info("No device path provided, auto-detecting RFID device...")
            device_path = find_rfid_device()
            if device_path is None:
                raise RuntimeError("Could not find RFID device with description 'HID 5131:2007'")
        
        self.device_path = device_path
        self.device = None
        self.buffer = []
        self.is_running = False
        self.on_rfid_scanned: Optional[Callable[[str], None]] = None
        self._shutdown_event = threading.Event()
        
        # Key mapping for RFID reader
        self.key_map = {
            ecodes.KEY_0: '0',
            ecodes.KEY_1: '1',
            ecodes.KEY_2: '2',
            ecodes.KEY_3: '3',
            ecodes.KEY_4: '4',
            ecodes.KEY_5: '5',
            ecodes.KEY_6: '6',
            ecodes.KEY_7: '7',
            ecodes.KEY_8: '8',
            ecodes.KEY_9: '9',
            ecodes.KEY_ENTER: '\n',
        }
        
        self.logger.info(f"RFIDDecoder initialized with device: {device_path}")
        self.logger.debug(f"Key map: {self.key_map}")
    
    def set_callback(self, callback: Callable[[str], None]):
        """
        Set a callback function to be called when an RFID code is scanned.
        
        Args:
            callback (Callable[[str], None]): Function that takes a string parameter (the RFID code)
        """
        self.on_rfid_scanned = callback
        self.logger.info("Callback function set")
    
    def start(self):
        """
        Start reading from the RFID device.
        """
        try:
            self.device = InputDevice(self.device_path)
            self.is_running = True
            self.logger.info(f"RFID Reader started on {self.device_path}")
            self.logger.info(f"Device name: {self.device.name}")
            self.logger.info(f"Device capabilities: {self.device.capabilities()}")
            
            for event in self.device.read_loop():
                if not self.is_running or self._shutdown_event.is_set():
                    self.logger.info("Stopping RFID reader loop")
                    break
                    
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    self.logger.debug(f"Key event: scancode={key_event.scancode}, keystate={key_event.keystate}")
                    
                    if key_event.keystate == key_event.key_down:
                        key = key_event.scancode
                        self.logger.info(f"Key pressed: scancode={key}")
                        
                        if key in self.key_map:
                            char = self.key_map[key]
                            self.logger.info(f"Mapped scancode {key} to character: '{char}'")
                            
                            if char == '\n':
                                code = ''.join(self.buffer)
                                self.logger.info(f"Enter key pressed, completing RFID code: '{code}'")
                                self.logger.info(f"Buffer contents before clearing: {self.buffer}")
                                self._handle_rfid_code(code)
                                self.buffer = []
                                self.logger.debug("Buffer cleared")
                            else:
                                self.buffer.append(char)
                                self.logger.info(f"Added character '{char}' to buffer. Current buffer: {self.buffer}")
                        else:
                            self.logger.warning(f"Unknown scancode: {key} (not in key_map)")
                else:
                    self.logger.debug(f"Non-key event: type={event.type}")
                                
        except KeyboardInterrupt:
            self.logger.info("KeyboardInterrupt received in start() method")
            self.stop()
        except Exception as e:
            self.logger.error(f"Error reading from RFID device: {e}")
            self.stop()
            raise
    
    def stop(self):
        """
        Stop reading from the RFID device.
        """
        self.logger.info("Stopping RFID decoder...")
        self.is_running = False
        self._shutdown_event.set()
        if self.device:
            try:
                self.device.close()
                self.logger.info("Device closed")
            except Exception as e:
                self.logger.error(f"Error closing device: {e}")
        self.logger.info("RFID Reader stopped.")
    
    def _handle_rfid_code(self, code: str):
        """
        Handle a scanned RFID code.
        
        Args:
            code (str): The scanned RFID code
        """
        self.logger.info(f"Processing RFID code: '{code}' (length: {len(code)})")
        print(f"Scanned RFID: {code}")
        if self.on_rfid_scanned:
            self.logger.debug("Calling callback function")
            self.on_rfid_scanned(code)
        else:
            self.logger.debug("No callback function set")
    
    def read_rfid(self) -> Optional[str]:
        """
        Read a single RFID code and return it.
        This method blocks until a complete RFID code is scanned.
        
        Returns:
            Optional[str]: The scanned RFID code, or None if interrupted
        """
        if not self.device:
            self.device = InputDevice(self.device_path)
            self.logger.info(f"Initialized device for single read: {self.device_path}")
        
        self.logger.info("Starting single RFID read operation")
        
        try:
            for event in self.device.read_loop():
                if self._shutdown_event.is_set():
                    self.logger.info("Shutdown requested during single read")
                    return None
                    
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    self.logger.debug(f"Key event: scancode={key_event.scancode}, keystate={key_event.keystate}")
                    
                    if key_event.keystate == key_event.key_down:
                        key = key_event.scancode
                        self.logger.info(f"Key pressed: scancode={key}")
                        
                        if key in self.key_map:
                            char = self.key_map[key]
                            self.logger.info(f"Mapped scancode {key} to character: '{char}'")
                            
                            if char == '\n':
                                code = ''.join(self.buffer)
                                self.logger.info(f"Enter key pressed, completing RFID code: '{code}'")
                                self.logger.info(f"Buffer contents before clearing: {self.buffer}")
                                self.buffer = []
                                self.logger.debug("Buffer cleared")
                                return code
                            else:
                                self.buffer.append(char)
                                self.logger.info(f"Added character '{char}' to buffer. Current buffer: {self.buffer}")
                        else:
                            self.logger.warning(f"Unknown scancode: {key} (not in key_map)")
                else:
                    self.logger.debug(f"Non-key event: type={event.type}")
                    
        except KeyboardInterrupt:
            self.logger.info("KeyboardInterrupt received during single read")
            self.stop()
            return None
        except Exception as e:
            self.logger.error(f"Error reading RFID: {e}")
            self.stop()
            return None
    
    def request_shutdown(self):
        """
        Request shutdown of the decoder.
        """
        self.logger.info("Shutdown requested")
        self._shutdown_event.set()
        self.stop()

def main():
    """
    Main function for standalone usage.
    """
    # Set up logging for standalone mode
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    decoder = RFIDDecoder(log_level=logging.INFO)
    
    def print_rfid(code: str):
        print(f"RFID Code: {code}")
    
    decoder.set_callback(print_rfid)
    
    try:
        decoder.start()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received in main(). Shutting down...")
        decoder.stop()

if __name__ == "__main__":
    main()
