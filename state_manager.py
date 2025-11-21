from enum import Enum
from threading import RLock, Thread, Timer
from typing import Optional, Callable
from constants import ChipType, PENDING_SOUND_FILE


class SystemState(Enum):
    IDLE = "IDLE"
    PENDING = "PENDING"
    PLAYING = "PLAYING"
    PARTY = "PARTY"


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
        self._current_chip_type: Optional[ChipType] = None  # Track chip type for current song
        self._playback_thread: Optional[Thread] = None
        self._manual_recipe_override: Optional[str] = None  # Track manual recipe override during music
        self._lock = RLock()
        print("StateManager initialized: state=IDLE")

    def get_state(self) -> SystemState:
        with self._lock:
            return self._state

    def start_song(self, song_filename: str, chip_type: ChipType = ChipType.SINGLE, callback: Optional[Callable[[], None]] = None) -> None:
        """
        Start playing a song. Returns immediately while playback happens in a background thread.
        
        Args:
            song_filename: Path to the song file to play
            chip_type: Type of chip (single or double)
            callback: Optional callback function to call when song finishes (or is stopped)
        """
        with self._lock:
            print(f"StateManager.start_song called: song='{song_filename}', chip_type='{chip_type}'")
            # If already playing something else, stop first
            if self._state == SystemState.PLAYING:
                print("A song is already playing. Stopping current song before starting new one.")
                self._unsafe_stop_audio()
                # Wait for previous playback thread to finish if it exists
                if self._playback_thread and self._playback_thread.is_alive():
                    # Note: We don't join here as it might block, but we've stopped the audio
                    pass
            
            # Set state before releasing lock
            self._current_song = song_filename
            self._current_chip_type = chip_type  # Store chip type for restoring music-reactive pattern
            self._state = SystemState.PLAYING
            print(f"State updated: PLAYING (song='{self._current_song}', chip_type='{chip_type}')")
        
        # Define playback coroutine that will be used for both single and double chip types
        def playback_coroutine():
            """Coroutine that runs in background thread to play the song."""
            try:
                print(f"Starting audio playback: {song_filename}")
                self.sound.play_song(song_filename, chip_type)
            except Exception as e:
                print(f"Error during playback: {e}")
            finally:
                # When play_song returns, the song has ended or was stopped
                # Call the callback if provided and if still in PLAYING state
                # (if end_song was called manually, state might already be IDLE)
                if callback:
                    should_call_callback = False
                    with self._lock:
                        # Only call callback if still in PLAYING state
                        # (end_song might have already been called manually)
                        if self._state == SystemState.PLAYING:
                            should_call_callback = True
                        else:
                            print(f"Playback finished but state is already {self._state}, skipping callback")
                    
                    # Call callback outside of lock to avoid nested lock acquisition
                    if should_call_callback:
                        try:
                            callback()
                        except Exception as e:
                            print(f"Error in playback callback: {e}")
        
        try:
            if chip_type == ChipType.DOUBLE:
                print(f"Switching lights to couple_feedback for {chip_type} chip")
                self.light.start_couple_feedback()
                # After 5 seconds, switch to couple_active and start music
                def switch_to_active_and_start_music():
                    try:
                        with self._lock:
                            # Only switch if still in PLAYING state
                            if self._state == SystemState.PLAYING:
                                try:
                                    print(f"Switching lights to couple_active for {chip_type} chip")
                                    self.light.start_couple_active()
                                except Exception as e:
                                    print(f"Warning: Failed to switch lights to couple_active: {e}")
                                # Start music playback now
                                self._playback_thread = Thread(target=playback_coroutine, daemon=True)
                                self._playback_thread.start()
                                print(f"Playback started in background thread for: {song_filename}")
                            else:
                                print(f"State is {self._state}, not starting music playback")
                    except Exception as e:
                        print(f"Warning: Error in switch_to_active_and_start_music: {e}")
                Timer(5.0, switch_to_active_and_start_music).start()
            else:
                print(f"Switching lights to music mode for {chip_type} chip")
                self.light.start_single_active(chip_type)
                # Start playback immediately for single chip type
                self._playback_thread = Thread(target=playback_coroutine, daemon=True)
                self._playback_thread.start()
                print(f"Playback started in background thread for: {song_filename}")
        except Exception:
            # Light failures should not prevent audio
            print("Warning: Failed to switch lights to music mode")
            # Still start playback even if lights failed
            if chip_type != ChipType.DOUBLE:
                self._playback_thread = Thread(target=playback_coroutine, daemon=True)
                self._playback_thread.start()
                print(f"Playback started in background thread for: {song_filename}")
            pass

    def end_song(self) -> None:
        with self._lock:
            print("StateManager.end_song called")
            self._unsafe_stop_audio()
            self._enter_idle_lights()
            self._current_song = None
            self._current_chip_type = None
            self._manual_recipe_override = None  # Clear manual override when song ends
            self._state = SystemState.IDLE
            print("State updated: IDLE (song=None)")

    def go_idle(self) -> None:
        print("StateManager.go_idle called -> transitioning to IDLE")
        with self._lock:
            self._unsafe_stop_audio()
            self._enter_idle_lights()
            self._current_song = None
            self._current_chip_type = None
            self._manual_recipe_override = None  # Clear manual override when going idle
            self._state = SystemState.IDLE
            print("State updated: IDLE (song=None)")

    def go_pending(self) -> None:
        """Switch to pending state with flashing blue lights and play pending sound."""
        print("StateManager.go_pending called -> transitioning to PENDING")
        with self._lock:
            self._unsafe_stop_audio()
            try:
                print("Switching lights to pending (blue flashing)")
                self.light.start_single_feedback()
            except Exception:
                print("Warning: Failed to switch lights to pending state")
                pass
            try:
                # Play pending state sound effect
                pending_sound_file = PENDING_SOUND_FILE
                print(f"Playing pending state sound: {pending_sound_file}")
                self.sound.play_sound_effect(pending_sound_file)
            except Exception:
                print("Warning: Failed to play pending state sound")
                pass
            self._current_song = None
            self._state = SystemState.PENDING
            print("State updated: PENDING")

    def go_party(self) -> None:
        """Switch to party state with lights but no music playback."""
        print("StateManager.go_party called -> transitioning to PARTY")
        with self._lock:
            self._unsafe_stop_audio()
            try:
                print("Switching lights to party mode (cycling party patterns, no music)")
                self.light.start_party()
            except Exception:
                print("Warning: Failed to switch lights to party mode")
                pass
            self._current_song = None
            self._state = SystemState.PARTY
            print("State updated: PARTY")

    def can_start_led_recipe(self) -> bool:
        """
        Check if LED recipes can be started.
        Recipes can only run when not playing music.
        
        Returns:
            True if recipes can be started, False if a song is currently playing
        """
        with self._lock:
            if self._state == SystemState.PLAYING:
                print("Cannot start LED recipe: song is currently playing")
                return False
            return True

    def start_led_recipe(self, recipe_name: str) -> bool:
        """
        Start an LED recipe. Can override music-reactive patterns when music is playing.
        
        Args:
            recipe_name: Name of the recipe to run
            
        Returns:
            True if recipe was started, False if recipe not found
        """
        with self._lock:
            # If music is playing, override the music-reactive pattern
            if self._state == SystemState.PLAYING:
                print(f"Starting LED recipe '{recipe_name}' to override music-reactive pattern")
                success = self.light.run_recipe(recipe_name)
                if success:
                    self._manual_recipe_override = recipe_name
                    print(f"StateManager: Started LED recipe '{recipe_name}' (overriding music-reactive pattern)")
                return success
            
            # If not playing music, stop any current audio and go to idle lights first
            self._unsafe_stop_audio()
            self._enter_idle_lights()
            
            # Run the recipe
            success = self.light.run_recipe(recipe_name)
            if success:
                self._manual_recipe_override = recipe_name
                print(f"StateManager: Started LED recipe '{recipe_name}'")
            return success

    def clear_all_leds(self) -> None:
        """Clear all LEDs to black. Works even when playing music."""
        self.light.clear_all_leds()

    def set_led_range(self, range_str: str) -> bool:
        """
        Set specific LED range to white. Only works when not playing music.
        
        Args:
            range_str: Range string like "5" or "5,10"
            
        Returns:
            True if range was set, False if music is playing
        """
        with self._lock:
            if self._state == SystemState.PLAYING:
                print("Cannot set LED range: song is currently playing")
                return False
            
            self._unsafe_stop_audio()
            self._enter_idle_lights()
            self.light.set_led_range(range_str)
            return True

    def set_ring(self, ring_id: int) -> bool:
        """
        Set specific ring to white. Only works when not playing music.
        
        Args:
            ring_id: Ring index to set
            
        Returns:
            True if ring was set, False if music is playing
        """
        with self._lock:
            if self._state == SystemState.PLAYING:
                print("Cannot set ring: song is currently playing")
                return False
            
            self._unsafe_stop_audio()
            self._enter_idle_lights()
            self.light.set_ring(ring_id)
            return True

    def set_branch(self, branch_id: int) -> bool:
        """
        Set specific branch to white. Only works when not playing music.
        
        Args:
            branch_id: Branch index to set
            
        Returns:
            True if branch was set, False if music is playing
        """
        with self._lock:
            if self._state == SystemState.PLAYING:
                print("Cannot set branch: song is currently playing")
                return False
            
            self._unsafe_stop_audio()
            self._enter_idle_lights()
            self.light.set_branch(branch_id)
            return True

    def led_crawl(self, blink_duration: float = 2.0) -> bool:
        """
        Start LED crawl mode. Only works when not playing music.
        
        Args:
            blink_duration: Duration in seconds per LED blink
            
        Returns:
            True if crawl was started, False if music is playing
        """
        with self._lock:
            if self._state == SystemState.PLAYING:
                print("Cannot start LED crawl: song is currently playing")
                return False
            
            self._unsafe_stop_audio()
            self._enter_idle_lights()
            self.light.led_crawl(blink_duration)
            return True

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
            self.light.start_idle()
        except Exception:
            print("Warning: Failed to switch lights to idle breathing")
            pass

    def stop_manual_recipe_override(self) -> bool:
        """
        Stop manual recipe override and return control to music-reactive pattern (if music is playing).
        
        Returns:
            True if override was stopped, False if no override was active
        """
        with self._lock:
            if self._manual_recipe_override is None:
                return False
            
            print(f"Stopping manual recipe override '{self._manual_recipe_override}'")
            self._manual_recipe_override = None
            
            # If music is playing, return to music-reactive pattern
            if self._state == SystemState.PLAYING:
                print("Returning control to music-reactive pattern")
                # Use stored chip type to restore the correct music-reactive pattern
                if self._current_chip_type == ChipType.DOUBLE:
                    self.light.start_couple_active()
                else:
                    # Default to single active for SINGLE chip type or if chip type is unknown
                    self.light.start_single_active()
            else:
                # If not playing music, go to idle
                self._enter_idle_lights()
            
            return True

    def get_manual_recipe_override(self) -> Optional[str]:
        """
        Get the currently active manual recipe override (if any).
        
        Returns:
            Recipe name if override is active, None otherwise
        """
        with self._lock:
            return self._manual_recipe_override


