from enum import Enum
from threading import RLock
from typing import Optional
from constants import ChipType


class SystemState(Enum):
    IDLE = "IDLE"
    PLAYING = "PLAYING"


class StateManager:
    """
    Orchestrates sound and light together.

    Responsibilities:
    - start_song: play audio and switch lights to music-reactive scene
    - end_song: stop audio and return lights to idle breathing
    - go_idle: ensure no audio and breathing effect is active
    """

    def __init__(self, sound_controller, light_controller):
        self.sound = sound_controller
        self.light = light_controller
        self._state = SystemState.IDLE
        self._current_song: Optional[str] = None
        self._lock = RLock()
        print("StateManager initialized: state=IDLE")

    def get_state(self) -> SystemState:
        with self._lock:
            return self._state

    def start_song(self, song_filename: str, chip_type: ChipType = ChipType.SINGLE) -> None:
        with self._lock:
            print(f"StateManager.start_song called: song='{song_filename}', chip_type='{chip_type}'")
            # If already playing something else, stop first
            if self._state == SystemState.PLAYING:
                print("A song is already playing. Stopping current song before starting new one.")
                self._unsafe_stop_audio()
            try:
                print(f"Switching lights to music mode for {chip_type} chip")
                self.light.start_music(chip_type)
            except Exception:
                # Light failures should not prevent audio
                print("Warning: Failed to switch lights to music mode")
                pass
            try:
                print(f"Starting audio playback: {song_filename}")
                self.sound.play_song(song_filename, chip_type)
            finally:
                # If play blocks until completion, ensure we go idle afterwards
                self._current_song = song_filename
                self._state = SystemState.PLAYING
                print(f"State updated: PLAYING (song='{self._current_song}')")

            # When play_song returns, the song has likely ended (current implementation blocks)
            # Transition to idle to keep lights coherent
            self.go_idle()

    def end_song(self) -> None:
        with self._lock:
            print("StateManager.end_song called")
            self._unsafe_stop_audio()
            self._enter_idle_lights()
            self._current_song = None
            self._state = SystemState.IDLE
            print("State updated: IDLE (song=None)")

    def go_idle(self) -> None:
        print("StateManager.go_idle called -> transitioning to IDLE")
        with self._lock:
            self._unsafe_stop_audio()
            self._enter_idle_lights()
            self._current_song = None
            self._state = SystemState.IDLE
            print("State updated: IDLE (song=None)")

    # Internal helpers (must be called under lock)
    def _unsafe_stop_audio(self) -> None:
        try:
            if hasattr(self.sound, "stop"):
                print("Stopping audio playback")
                self.sound.stop()
        except Exception:
            print("Warning: Failed to stop audio")
            pass

    def _enter_idle_lights(self) -> None:
        try:
            print("Switching lights to idle breathing")
            self.light.stop_music()
        except Exception:
            print("Warning: Failed to switch lights to idle breathing")
            pass


