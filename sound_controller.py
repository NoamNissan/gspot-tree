import pygame
import os
import sys

class SoundController:
    def __init__(self, songs_dir="songs"):
        self.songs_dir = songs_dir
        self._init_audio()
        self._is_stopped = False

    def _init_audio(self):
        """Initialize pygame mixer with fallback options for Raspberry Pi"""
        try:
            # Try default initialization first
            pygame.mixer.init()
            print("Audio initialized successfully")
        except pygame.error as e:
            print(f"Default audio init failed: {e}")
            try:
                # Try with specific parameters for Raspberry Pi
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
                print("Audio initialized with custom parameters")
            except pygame.error as e2:
                print(f"Custom audio init failed: {e2}")
                try:
                    # Try with minimal parameters
                    pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=256)
                    print("Audio initialized with minimal parameters")
                except pygame.error as e3:
                    print(f"All audio initialization attempts failed: {e3}")
                    print("Audio playback will be disabled")
                    self.audio_available = False
                    return
        
        self.audio_available = True

    def play_song(self, filename):
        if not self.audio_available:
            print(f"Audio not available - would play: {filename}")
            return
            
        filepath = os.path.join(self.songs_dir, filename)
        if not os.path.isfile(filepath):
            print(f"Song file not found: {filepath}")
            return
        try:
            self._is_stopped = False
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            print(f"Playing: {filename}")
            while pygame.mixer.music.get_busy() and not self._is_stopped:
                pygame.time.Clock().tick(10)
        except Exception as e:
            print(f"Error playing song: {e}")

    def stop(self):
        """Stop playback if possible. Idempotent."""
        if not hasattr(pygame, "mixer"):
            return
        try:
            self._is_stopped = True
            pygame.mixer.music.stop()
        except Exception:
            pass