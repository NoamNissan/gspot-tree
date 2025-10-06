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

RFID_DECODER_LOG_LEVEL = logging.INFO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def find_rfid_devices(target_description: str = "HID 5131:2007") -> list[str]:
    """
    Find all RFID devices with the specified description.
    
    Args:
        target_description (str): The device description to look for
        
    Returns:
        list[str]: List of paths to matching devices, empty list if none found
    """
    logger = logging.getLogger('RFIDDeviceFinder')

    if not EVDEV_AVAILABLE:
        logger.warning("evdev is not available on this platform (%s). RFID reader is disabled.", sys.platform)
        return []
    
    matching_devices = []
    device_info_cache = {}  # Cache device info to avoid creating InputDevice objects twice
    
    try:
        devices = list_devices()
        logger.info(f"Scanning {len(devices)} input devices for RFID reader...")
        print("devices", devices)
        for device_path in devices:
            try:
                device = InputDevice(device_path)
                device_info = device.info
                device_name = device.name
                device_phys = device.phys
                
                # Cache the device info for potential logging later
                device_info_cache[device_path] = {
                    'name': device_name,
                    'info': device_info,
                    'phys': device_phys
                }
                
                logger.debug(f"Device {device_path}: name='{device_name}', phys='{device_phys}'")
                
                # Check if this device matches our target description
                if target_description in device_name or target_description in str(device_info):
                    logger.info(f"Found RFID device: {device_path} - {device_name}")
                    matching_devices.append(device_path)
                    
            except Exception as e:
                logger.debug(f"Error reading device {device_path}: {e}")
                # Store error info for logging
                device_info_cache[device_path] = {'error': str(e)}
                continue
        
        if not matching_devices:
            logger.warning(f"No devices found with description '{target_description}'")
            logger.info("Available devices:")
            for device_path in devices:
                if device_path in device_info_cache:
                    device_info = device_info_cache[device_path]
                    if 'error' in device_info:
                        logger.info(f"  {device_path}: Error reading device info - {device_info['error']}")
                    else:
                        logger.info(f"  {device_path}: {device_info['name']}")
                else:
                    logger.info(f"  {device_path}: Unknown device")
        else:
            logger.info(f"Found {len(matching_devices)} matching RFID devices")
        
        return matching_devices
        
    except Exception as e:
        logger.error(f"Error scanning for devices: {e}")
        return []


def find_rfid_device(target_description: str = "HID 5131:2007") -> Optional[str]:
    """
    Find the first RFID device with the specified description (backward compatibility).
    
    Args:
        target_description (str): The device description to look for
        
    Returns:
        Optional[str]: Path to the first matching device if found, None otherwise
    """
    devices = find_rfid_devices(target_description)
    return devices[0] if devices else None

class RFIDDecoder:
    """
    A class that encapsulates RFID decoding logic and provides a clean interface
    for reading RFID codes from one or multiple devices.
    """
    
    def __init__(self, device_path: Optional[str] = None, log_level: int = RFID_DECODER_LOG_LEVEL):
        """
        Initialize the RFID decoder with the specified device path(s) or auto-detect.
        
        Args:
            device_path (Optional[str]): Path to a single RFID input device, or None to auto-detect all.
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

        # Auto-detect devices if not provided
        if device_path is None:
            self.logger.info("No device path provided, auto-detecting RFID devices...")
            device_paths = find_rfid_devices()
            if not device_paths:
                raise RuntimeError("Could not find any RFID devices with description 'HID 5131:2007'")
        else:
            device_paths = [device_path]
        
        self.device_paths = device_paths
        self.devices = {}  # Dictionary to store device objects by path
        self.device_buffers = {}  # Dictionary to store buffers for each device
        self.is_running = False
        self.on_rfid_scanned: Optional[Callable[[str], None]] = None
        self._shutdown_event = threading.Event()
        self._device_threads = {}  # Dictionary to store device reader threads
        
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
        
        # Initialize buffers for each device
        for path in self.device_paths:
            self.device_buffers[path] = []
        
        self.logger.info(f"RFIDDecoder initialized with {len(self.device_paths)} device(s): {self.device_paths}")
        self.logger.debug(f"Key map: {self.key_map}")
    
    def set_callback(self, callback: Callable[[str], None]):
        """
        Set a callback function to be called when an RFID code is scanned.
        
        Args:
            callback (Callable[[str], None]): Function that takes a string parameter (the RFID code)
        """
        self.on_rfid_scanned = callback
        self.logger.info("Callback function set")
    
    def _process_device_events(self, device_path: str, device):
        """
        Process events from a single RFID device.
        
        Args:
            device_path (str): Path to the device
            device: The InputDevice object
        """
        for event in device.read_loop():
            if not self.is_running or self._shutdown_event.is_set():
                self.logger.info(f"Stopping RFID reader loop for device {device_path}")
                break
                
            if event.type == ecodes.EV_KEY:
                key_event = categorize(event)
                self.logger.debug(f"Device {device_path} - Key event: scancode={key_event.scancode}, keystate={key_event.keystate}")
                
                if key_event.keystate == key_event.key_down:
                    key = key_event.scancode
                    self.logger.debug(f"Device {device_path} - Key pressed: scancode={key}")
                    
                    if key in self.key_map:
                        char = self.key_map[key]
                        self.logger.debug(f"Device {device_path} - Mapped scancode {key} to character: '{char}'")
                        
                        if char == '\n':
                            code = ''.join(self.device_buffers[device_path])
                            self.logger.debug(f"Device {device_path} - Enter key pressed, completing RFID code: '{code}'")
                            self.logger.debug(f"Device {device_path} - Buffer contents before clearing: {self.device_buffers[device_path]}")
                            self._handle_rfid_code(code)
                            self.device_buffers[device_path] = []
                            self.logger.debug(f"Device {device_path} - Buffer cleared")
                        else:
                            self.device_buffers[device_path].append(char)
                            self.logger.debug(f"Device {device_path} - Added character '{char}' to buffer. Current buffer: {self.device_buffers[device_path]}")
                    else:
                        self.logger.warning(f"Device {device_path} - Unknown scancode: {key} (not in key_map)")
            else:
                self.logger.debug(f"Device {device_path} - Non-key event: type={event.type}")

    def _read_from_device(self, device_path: str):
        """
        Read from a single RFID device in a separate thread.
        
        Args:
            device_path (str): Path to the device to read from
        """
        try:
            device = InputDevice(device_path)
            self.devices[device_path] = device
            self.logger.info(f"RFID Reader started on {device_path}")
            self.logger.info(f"Device name: {device.name}")
            self.logger.info(f"Device capabilities: {device.capabilities()}")
            
            # Process device events
            self._process_device_events(device_path, device)
                                
        except KeyboardInterrupt:
            self.logger.info(f"KeyboardInterrupt received in device reader thread for {device_path}")
        except OSError as e:
            # Device might have been disconnected or become unresponsive
            self.logger.warning(f"Device {device_path} became unresponsive: {e}")
        except Exception as e:
            self.logger.error(f"Error reading from RFID device {device_path}: {e}")
        finally:
            if device_path in self.devices:
                try:
                    self.devices[device_path].close()
                    self.logger.info(f"Device {device_path} closed")
                except Exception as e:
                    self.logger.error(f"Error closing device {device_path}: {e}")

    def start(self):
        """
        Start reading from all RFID devices in separate threads.
        """
        self.is_running = True
        self.logger.info(f"Starting RFID Reader on {len(self.device_paths)} device(s)")
        
        # Start a thread for each device
        for device_path in self.device_paths:
            thread = threading.Thread(
                target=self._read_from_device, 
                args=(device_path,),
                name=f"RFIDReader-{device_path}",
                daemon=True
            )
            self._device_threads[device_path] = thread
            thread.start()
            self.logger.info(f"Started thread for device: {device_path}")
        
        # Wait for all threads to complete
        for device_path, thread in self._device_threads.items():
            try:
                thread.join()
            except KeyboardInterrupt:
                self.logger.info("KeyboardInterrupt received in start() method")
                self.stop()
                break
            except Exception as e:
                self.logger.error(f"Error in device thread {device_path}: {e}")
    
    def stop(self):
        """
        Stop reading from all RFID devices.
        """
        self.logger.info("Stopping RFID decoder...")
        self.is_running = False
        self._shutdown_event.set()
        
        # Close all devices
        for device_path, device in self.devices.items():
            try:
                device.close()
                self.logger.info(f"Device {device_path} closed")
            except Exception as e:
                self.logger.error(f"Error closing device {device_path}: {e}")
        
        # Wait for all threads to finish
        for device_path, thread in self._device_threads.items():
            try:
                if thread.is_alive():
                    thread.join(timeout=0.3)  # Wait up to 1 second for thread to finish
                    if thread.is_alive():
                        self.logger.warning(f"Thread for device {device_path} did not finish within timeout - this is normal if device is unresponsive")
            except Exception as e:
                self.logger.error(f"Error waiting for thread {device_path}: {e}")
        
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
        This method blocks until a complete RFID code is scanned from any device.
        
        Returns:
            Optional[str]: The scanned RFID code, or None if interrupted
        """
        if not self.device_paths:
            self.logger.error("No devices available for single read")
            return None
        
        # Use the first available device for single read
        device_path = self.device_paths[0]
        device = InputDevice(device_path)
        self.logger.info(f"Initialized device for single read: {device_path}")
        
        # Use a temporary buffer for this single read operation
        temp_buffer = []
        
        self.logger.info("Starting single RFID read operation")
        
        try:
            for event in device.read_loop():
                if self._shutdown_event.is_set():
                    self.logger.info("Shutdown requested during single read")
                    return None
                    
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    self.logger.debug(f"Key event: scancode={key_event.scancode}, keystate={key_event.keystate}")
                    
                    if key_event.keystate == key_event.key_down:
                        key = key_event.scancode
                        self.logger.debug(f"Key pressed: scancode={key}")
                        
                        if key in self.key_map:
                            char = self.key_map[key]
                            self.logger.debug(f"Mapped scancode {key} to character: '{char}'")
                            
                            if char == '\n':
                                code = ''.join(temp_buffer)
                                self.logger.debug(f"Enter key pressed, completing RFID code: '{code}'")
                                self.logger.debug(f"Buffer contents before clearing: {temp_buffer}")
                                temp_buffer = []
                                self.logger.debug("Buffer cleared")
                                return code
                            else:
                                temp_buffer.append(char)
                                self.logger.debug(f"Added character '{char}' to buffer. Current buffer: {temp_buffer}")
                        else:
                            self.logger.warning(f"Unknown scancode: {key} (not in key_map)")
                else:
                    self.logger.debug(f"Non-key event: type={event.type}")
                    
        except KeyboardInterrupt:
            self.logger.info("KeyboardInterrupt received during single read")
            return None
        except Exception as e:
            self.logger.error(f"Error reading RFID: {e}")
            return None
        finally:
            try:
                device.close()
            except Exception as e:
                self.logger.error(f"Error closing device during single read: {e}")
    
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
