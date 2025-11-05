import pygame
import os
import sys
import subprocess
from rfid_reader import OperatingMode
from constants import ChipType

class SoundController:
    def __init__(self, songs_dir="songs", mode: OperatingMode | None = None):
        self.songs_dir = songs_dir
        self.mode = mode
        # Attempt to configure PulseAudio loopback on Raspberry Pi if requested
        self._maybe_setup_pi_loopback()
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

    def _run_cmd(self, args):
        try:
            return subprocess.run(args, check=True, text=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Command failed: {' '.join(args)}\nstdout: {e.stdout}\nstderr: {e.stderr}")
            raise

    def _pactl_list_sinks(self):
        try:
            res = self._run_cmd(["pactl", "list", "short", "sinks"]).stdout
            return res.splitlines()
        except Exception as e:
            print(f"Failed to list sinks via pactl: {e}")
            return []

    def _find_hdmi_sink_name(self) -> str:
        # Find a sink whose name ends with "hdmi.hdmi-stereo" (suffix match)
        sinks = self._pactl_list_sinks()
        suffix = "hdmi.hdmi-stereo"
        for line in sinks:
            # pactl list short sinks => index\tname\tdriver\t... ; we want the second column
            parts = line.split('\t')
            if len(parts) >= 2:
                name = parts[1]
                if name.endswith(suffix):
                    return name
        return ""

    def _maybe_setup_pi_loopback(self):
        if self.mode != OperatingMode.RASPBERRY_PI:
            return

        try:
            # 1) Create null sink
            try:
                self._run_cmd([
                    "pactl", "load-module", "module-null-sink",
                    "sink_name=loopback_out",
                    "sink_properties=device.description=LoopbackOut",
                ])
            except Exception:
                # Module may already be loaded; continue
                pass

            # 2) Detect HDMI sink by suffix; error if none match
            hdmi_sink = self._find_hdmi_sink_name()
            if not hdmi_sink:
                sinks = '\n'.join(self._pactl_list_sinks())
                print("No HDMI sink ending with 'hdmi.hdmi-stereo' found. Available sinks:\n" + sinks)
                # Exit with error as requested
                sys.exit(1)

            # 3) Connect loopback from null sink monitor to HDMI sink
            try:
                self._run_cmd([
                    "pactl", "load-module", "module-loopback",
                    "source=loopback_out.monitor",
                    f"sink={hdmi_sink}",
                ])
            except Exception:
                # Module may already be loaded; continue
                pass

            # 4) Set defaults: sink to loopback_out, source to its monitor
            try:
                self._run_cmd(["pactl", "set-default-sink", "loopback_out"])
                self._run_cmd(["pactl", "set-default-source", "loopback_out.monitor"])
            except Exception:
                pass

            # 5) Optionally direct pygame to use loopback_out; not mandatory
            try:
                os.environ.setdefault("SDL_AUDIODRIVER", "pulseaudio")
                # Some SDL versions accept PULSE_SINK/PULSE_SOURCE
                os.environ.setdefault("PULSE_SINK", "loopback_out")
                os.environ.setdefault("PULSE_SOURCE", "loopback_out.monitor")
            except Exception:
                pass

            print("Raspberry Pi PulseAudio loopback configured (LoopbackOut -> HDMI).")
        except SystemExit:
            raise
        except Exception as e:
            print(f"Failed to configure Raspberry Pi PulseAudio loopback: {e}")

    def play_song(self, filename, chip_type: ChipType = ChipType.SINGLE):
        if not self.audio_available:
            print(f"Audio not available - would play: {filename} (chip_type: {chip_type})")
            return
            
        filepath = filename
        if not os.path.isfile(filepath):
            print(f"Song file not found: {filepath}")
            return
        try:
            self._is_stopped = False
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            print(f"Playing: {filename} (chip_type: {chip_type})")
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

    def play_sound_effect(self, filename):
        """Play a short sound effect without blocking. Returns immediately."""
        if not self.audio_available:
            print(f"Audio not available - would play sound effect: {filename}")
            return
            
        filepath = filename
        if not os.path.isfile(filepath):
            print(f"Sound effect file not found: {filepath}")
            return
        try:
            # Use pygame.mixer.Sound for short sounds that don't need to block
            sound = pygame.mixer.Sound(filepath)
            sound.play()
            print(f"Playing sound effect: {filename}")
        except Exception as e:
            print(f"Error playing sound effect: {e}")