"""
Usage Logger - Logs RFID reader interactions and song playback events.

This module logs events related to direct RFID reader usage:
- When a chip is touched on the RFID reader (with chip code)
- When a song starts (with song name and mode: single/double chip)
"""

import os
import json
import time
from datetime import datetime
from threading import Lock
from typing import Optional


class UsageLogger:
    """
    Logger for RFID reader usage events.
    Logs only interactions from the RFID reader, not from web controller.
    """
    
    def __init__(self, log_file: str = "rfid_usage.log"):
        """
        Initialize the usage logger.
        
        Args:
            log_file: Name of the log file (will be created in project directory)
        """
        # Get the directory where this script is located (project root)
        project_dir = os.path.dirname(os.path.abspath(__file__))
        self.log_file_path = os.path.join(project_dir, log_file)
        self._lock = Lock()
    
    def _write_log_entry(self, entry_type: str, data: dict):
        """
        Write a log entry to the file.
        
        Args:
            entry_type: Type of event (e.g., "chip_touch", "song_start")
            data: Additional data for the log entry
        """
        with self._lock:
            timestamp = datetime.now().isoformat()
            log_entry = {
                "timestamp": timestamp,
                "type": entry_type,
                **data
            }
            
            try:
                # Append to log file
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            except Exception as e:
                # Don't crash the main application if logging fails
                print(f"Error writing to usage log: {e}")
    
    def log_chip_touch(self, chip_code: str):
        """
        Log when a chip is touched on the RFID reader.
        
        Args:
            chip_code: The RFID chip code that was detected
        """
        self._write_log_entry("chip_touch", {
            "chip_code": chip_code
        })
    
    def log_song_start(self, song_filename: str, mode: str, chip_code: Optional[str] = None):
        """
        Log when a song starts from RFID reader interaction.
        
        Args:
            song_filename: Path to the song file that started playing
            mode: Mode of interaction - "single_chip" or "double_chip" (couple mode)
            chip_code: Optional chip code(s) that triggered the song (can be None for double chip mode with two chips)
        """
        # Extract just the filename from the path for cleaner logs
        song_name = os.path.basename(song_filename)
        
        self._write_log_entry("song_start", {
            "song": song_name,
            "song_path": song_filename,
            "mode": mode,
            "chip_code": chip_code
        })
    
    def get_log_file_path(self) -> str:
        """
        Get the path to the log file.
        
        Returns:
            Absolute path to the log file
        """
        return self.log_file_path

