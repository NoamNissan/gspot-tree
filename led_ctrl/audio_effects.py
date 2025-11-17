#!/usr/bin/env python3
"""
Audio Effects System - Real-time audio analysis and music visualization effects
"""

import time
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

try:
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("⚠️  Audio not available - install with: pip install sounddevice numpy")

from .pipeline_demo import Effect, Color
from .colors_array import Colors

# Global audio configuration
SAMPLING_RATE = 16000  # Default 16kHz for better compatibility

@dataclass
class AudioData:
    """Real-time audio analysis data"""
    bass: float = 0.0
    mid: float = 0.0  
    high: float = 0.0
    overall: float = 0.0
    is_beat: bool = False
    timestamp: float = 0.0

class RealTimeAudioProvider:
    """Real-time audio analysis using sounddevice"""
    
    def __init__(self, sample_rate=None, block_size=512, num_bands=3, dynamic_window=1.0):
        self.sample_rate = sample_rate or SAMPLING_RATE
        self.block_size = block_size
        self.num_bands = num_bands
        
        # Dynamic range tracking
        self.dynamic_window = dynamic_window
        self.last_reset = time.time()
        self.band_mins = [0.0] * num_bands
        self.band_maxs = [0.0] * num_bands
        self.prev_band_mins = [0.0] * num_bands
        self.prev_band_maxs = [1.0] * num_bands  # Default range
        self.first_sample = True
        
        # Audio levels (thread-safe)
        self.bass = 0.0
        self.mid = 0.0
        self.high = 0.0
        self.overall = 0.0
        
        # Dynamic band levels
        self.band_levels = [0.0] * num_bands
        
        # Beat detection
        self.beat_threshold = 0.3
        self.last_bass = 0.0
        self.is_beat = False
        self.last_beat_time = 0.0
        
        # Audio stream
        self.stream = None
        self.running = False
        
        # Calculate frequency bins dynamically based on num_bands
        self._calculate_frequency_bins()
        
        # Legacy properties for backward compatibility
        self.bass_bins = self.frequency_bins[0] if num_bands >= 1 else slice(0, 0)
        self.mid_bins = self.frequency_bins[1] if num_bands >= 2 else slice(0, 0)
        self.high_bins = self.frequency_bins[2] if num_bands >= 3 else slice(0, 0)
    
    def _calculate_frequency_bins(self):
        """Calculate frequency bins based on number of bands and sample rate"""
        max_freq = self.sample_rate // 2  # Nyquist frequency
        
        if self.num_bands == 3:
            # Original 3-band setup
            if max_freq <= 8000:  # 16kHz sampling
                frequencies = [0, 250, 2000, max_freq]
            else:  # 48kHz sampling
                frequencies = [0, 250, 4000, max_freq]
        elif self.num_bands == 6:
            # 6-band setup
            if max_freq <= 8000:  # 16kHz sampling
                frequencies = [0, 60, 150, 400, 1000, 2500, max_freq]
            else:  # 48kHz sampling
                frequencies = [0, 60, 250, 500, 2000, 4000, max_freq]
        elif self.num_bands == 9:
            # 9-band setup
            if max_freq <= 8000:  # 16kHz sampling
                frequencies = [0, 60, 120, 200, 350, 600, 1200, 2500, 5000, max_freq]
            else:  # 48kHz sampling
                frequencies = [0, 60, 120, 250, 500, 1000, 2000, 4000, 8000, max_freq]
        else:
            # Linear division for other band counts
            frequencies = []
            for i in range(self.num_bands + 1):
                freq = (i * max_freq) // self.num_bands
                frequencies.append(freq)
        
        # Convert frequencies to bin indices
        self.frequency_bins = []
        for i in range(len(frequencies) - 1):
            start_bin = int(frequencies[i] * self.block_size / self.sample_rate)
            end_bin = int(frequencies[i + 1] * self.block_size / self.sample_rate) + 1
            self.frequency_bins.append(slice(start_bin, end_bin))
    
    def audio_callback(self, indata, frames, time, status):
        """Real-time audio processing callback"""
        if status:
            print(f"Audio callback status: {status}")
        
        try:
            # Get mono audio data
            audio_data = indata[:, 0] if indata.shape[1] > 1 else indata.flatten()
            
            # Fast FFT analysis
            fft = np.fft.rfft(audio_data)
            magnitude = np.abs(fft)
            
            # Extract all frequency bands dynamically
            band_values = []
            for i, freq_bin in enumerate(self.frequency_bins):
                band_value = np.mean(magnitude[freq_bin])
                band_values.append(band_value)
            
            # Apply scaling to all bands
            scales = [0.05, 0.1, 0.2] * (self.num_bands // 3 + 1)  # Repeat scaling pattern
            scaled_bands = []
            for i, (band_value, scale) in enumerate(zip(band_values, scales[:self.num_bands])):
                scaled_band = min(1.0, np.log10(band_value * scale + 1) / np.log10(2))
                scaled_bands.append(scaled_band)
            
            # Dynamic range processing
            current_time = time.inputBufferAdcTime
            
            # Reset every window period
            if current_time - self.last_reset > self.dynamic_window or self.first_sample:
                # Save current range for scaling
                if not self.first_sample:
                    self.prev_band_mins = self.band_mins.copy()
                    self.prev_band_maxs = self.band_maxs.copy()
                
                # Start new accumulation
                self.band_mins = scaled_bands.copy()
                self.band_maxs = scaled_bands.copy()
                self.last_reset = current_time
                self.first_sample = False
            else:
                # Accumulate current window
                for i in range(len(scaled_bands)):
                    self.band_mins[i] = min(self.band_mins[i], scaled_bands[i])
                    self.band_maxs[i] = max(self.band_maxs[i], scaled_bands[i])
            
            # Normalize using previous window's range
            normalized_bands = []
            for i in range(len(scaled_bands)):
                normalized = self._normalize_level(scaled_bands[i], self.prev_band_mins[i], self.prev_band_maxs[i])
                normalized_bands.append(normalized)
            
            # Update band levels with normalized values
            self.band_levels = normalized_bands
            
            # Legacy compatibility - use first 3 bands (normalized)
            bass = normalized_bands[0] if len(normalized_bands) > 0 else 0.0
            mid = normalized_bands[1] if len(normalized_bands) > 1 else 0.0
            high = normalized_bands[2] if len(normalized_bands) > 2 else 0.0
            overall = sum(normalized_bands) / len(normalized_bands) if normalized_bands else 0.0
            
            # Simple beat detection (bass spike)
            current_time = time.inputBufferAdcTime
            beat_detected = False
            if bass > self.beat_threshold and bass > self.last_bass * 1.5:
                if current_time - self.last_beat_time > 0.1:  # Minimum 100ms between beats
                    beat_detected = True
                    self.last_beat_time = current_time
            
            # Update thread-safe values (legacy compatibility)
            self.bass = bass
            self.mid = mid
            self.high = high
            self.overall = overall
            self.is_beat = beat_detected
            self.last_bass = bass
            
        except Exception as e:
            print(f"Audio processing error: {e}")
    
    def _normalize_level(self, value, min_val, max_val):
        """Normalize value using min/max range"""
        range_size = max_val - min_val
        if range_size < 0.01:  # Prevent division by zero
            return 0.5
        normalized = (value - min_val) / range_size
        return max(0.0, min(1.0, normalized))
    
    def start(self):
        """Start real-time audio capture with device detection"""
        if not AUDIO_AVAILABLE:
            print("❌ Audio not available - install sounddevice and numpy")
            return
            
        try:
            # Print available devices for debugging
            print("🎵 Available audio devices:")
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    print(f"  {i}: {device['name']} (inputs: {device['max_input_channels']})")
            
            # Try to find best input device
            input_device = None
            
            # Look for system audio loopback devices first
            for i, device in enumerate(devices):
                name = device['name'].lower()
                if device['max_input_channels'] > 0:
                    # macOS system audio devices
                    if any(keyword in name for keyword in ['blackhole', 'soundflower']):
                        input_device = i
                        print(f"🎵 Found system audio device: {device['name']}")
                        break
                    # Linux monitor devices (but skip hardware loopback)
                    elif 'monitor' in name and 'loopback' not in name:
                        input_device = i
                        print(f"🎵 Found monitor device: {device['name']}")
                        break
                    # PulseAudio/PipeWire pulse device
                    elif 'pulse' in name:
                        input_device = i
                        print(f"🎵 Found pulse device: {device['name']}")
                        break
            
            # Fallback to default input device
            if input_device is None:
                input_device = sd.default.device[0]  # Default input
                default_device = devices[input_device]
                print(f"🎵 Using default input device: {default_device['name']}")
            
            # Start audio stream
            self.stream = sd.InputStream(
                callback=self.audio_callback,
                device=input_device,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype=np.float32
            )
            self.stream.start()
            self.running = True
            print(f"🎵 Audio analysis started (Device: {input_device}, SR: {self.sample_rate})")
            
        except Exception as e:
            print(f"❌ Failed to start audio stream: {e}")
            print("💡 Try:")
            print("   - Check microphone permissions")
            print("   - Install system audio loopback (BlackHole on Mac)")
            print("   - Test with: python -c 'import sounddevice; print(sounddevice.query_devices())'")
            self.running = False
    
    def stop(self):
        """Stop audio capture"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.running = False
            print("🎵 Audio analysis stopped")
    
    def get_current_audio_data(self) -> AudioData:
        """Get current audio analysis data"""
        return AudioData(
            bass=self.bass,
            mid=self.mid,
            high=self.high,
            overall=self.overall,
            is_beat=self.is_beat,
            timestamp=time.time()
        )

class MusicVisualizerEffect(Effect):
    """Music visualizer effect using real-time audio analysis"""
    
    def __init__(self, audio_provider: RealTimeAudioProvider, tree_structure=None, effect_id: str = None, led_pairing=True):
        super().__init__(effect_id)
        self.audio_provider = audio_provider
        self.tree_structure = tree_structure
        self.led_pairing = led_pairing
        
        # Ring amplitude effect state
        self._ring_amplitude_intensities = [0.0, 0.0, 0.0, 0.0, 0.0]
        
        self.parameters = {
            'mode': 'spectrum',     # spectrum, pulse, wave, strobe
            'sensitivity': 1.5,     # Audio sensitivity multiplier
            'color_cycle_period': 5.0,  # Color change period in seconds
            'color_morph': True,  # Smooth morphing vs discrete jumps
        }
        
        # Initialize boolean flags via update_parameters
        self.update_parameters({})
    
    def _set_led_range(self, result, start_idx, count, color):
        """Set count LEDs starting at start_idx to color"""
        if self.led_pairing:
            # Pair-aligned range
            pair_start = (start_idx // 2) * 2
            pair_count = ((start_idx + count - 1) // 2 + 1) * 2 - pair_start
            end_idx = min(pair_start + pair_count, len(result))
            # Vectorized assignment for entire pair range
            result.r[pair_start:end_idx] = color.r
            result.g[pair_start:end_idx] = color.g  
            result.b[pair_start:end_idx] = color.b
        else:
            # Vectorized assignment for range
            end_idx = min(start_idx + count, len(result))
            result.r[start_idx:end_idx] = color.r
            result.g[start_idx:end_idx] = color.g
            result.b[start_idx:end_idx] = color.b
    
    def update_parameters(self, new_params: Dict[str, Any]):
        """Update effect parameters and recompute cached flags"""
        super().update_parameters(new_params)
        self._color_morph = self.parameters.get('color_morph', True)
        
        # Color palette for spectrum cycling
        self.spectrum_colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green  
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (255, 128, 0),  # Orange
            (128, 0, 255),  # Purple
        ]
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        if not self.audio_provider.running:
            return colors
        
        # Get real-time audio data
        audio_data = self.audio_provider.get_current_audio_data()
        
        # Apply sensitivity
        bass = min(1.0, audio_data.bass * self.parameters['sensitivity'])
        mid = min(1.0, audio_data.mid * self.parameters['sensitivity'])
        high = min(1.0, audio_data.high * self.parameters['sensitivity'])
        overall = min(1.0, audio_data.overall * self.parameters['sensitivity'])
        
        # Route to visualization mode
        mode = self.parameters['mode']
        if mode == 'spectrum':
            return self._spectrum_visualization(colors, bass, mid, high, elapsed)
        elif mode == 'spectrum_enhanced':
            return self._spectrum_enhanced_visualization(colors, bass, mid, high, elapsed)
        elif mode == 'pulse':
            return self._pulse_visualization(colors, overall)
        elif mode == 'ring_amplitude':
            return self._ring_amplitude_visualization(colors, overall, elapsed)
        elif mode == 'wave':
            return self._wave_visualization(colors, bass, elapsed)
        elif mode == 'strobe':
            return self._strobe_visualization(colors, audio_data.is_beat, overall)
        else:
            return colors
    
    def _get_band_colors(self, elapsed, num_bands):
        """Get cycling colors for spectrum bands"""
        period = self.parameters['color_cycle_period']
        
        if self._color_morph:
            # Smooth morphing between colors
            cycle_position = (elapsed / period) % len(self.spectrum_colors)
            base_index = int(cycle_position)
            blend_factor = cycle_position - base_index
            
            band_colors = []
            for i in range(num_bands):
                current_idx = (base_index + i) % len(self.spectrum_colors)
                next_idx = (base_index + i + 1) % len(self.spectrum_colors)
                
                current_color = self.spectrum_colors[current_idx]
                next_color = self.spectrum_colors[next_idx]
                
                # Blend between current and next color
                blended_color = (
                    int(current_color[0] * (1 - blend_factor) + next_color[0] * blend_factor),
                    int(current_color[1] * (1 - blend_factor) + next_color[1] * blend_factor),
                    int(current_color[2] * (1 - blend_factor) + next_color[2] * blend_factor)
                )
                band_colors.append(blended_color)
            return band_colors
        else:
            # Discrete jumps (original behavior)
            base_index = int(elapsed / period) % len(self.spectrum_colors)
            band_colors = []
            for i in range(num_bands):
                color_index = (base_index + i) % len(self.spectrum_colors)
                band_colors.append(self.spectrum_colors[color_index])
            return band_colors
    
    def _spectrum_visualization(self, colors: Colors, bass: float, mid: float, high: float, elapsed: float) -> Colors:
        """3-band spectrum analyzer with cycling colors"""
        
        result = colors.copy()
        pixels_per_band = len(colors) // 3

        # Get cycling colors for 3 bands
        band_colors = self._get_band_colors(elapsed, 3)
        
        # Bass - left third
        bass_height = int(bass * pixels_per_band)
        for i in range(bass_height):
            if self.led_pairing:
                pair_idx = i // 2
                intensity = 1.0 - (pair_idx / max(1, pixels_per_band // 2)) * 0.3
            else:
                intensity = 1.0 - (i / pixels_per_band) * 0.3
            
            r, g, b = band_colors[0]
            color = Color(int(r * intensity), int(g * intensity), int(b * intensity))
            
            if self.led_pairing:
                pair_start = (i // 2) * 2
                if pair_start < len(result):
                    result[pair_start] = color
                if pair_start + 1 < len(result):
                    result[pair_start + 1] = color
            else:
                result[i] = color
        
        # Mid - middle third
        mid_height = int(mid * pixels_per_band)
        for i in range(mid_height):
            idx = pixels_per_band + i
            if self.led_pairing:
                pair_idx = i // 2
                intensity = 1.0 - (pair_idx / max(1, pixels_per_band // 2)) * 0.3
            else:
                intensity = 1.0 - (i / pixels_per_band) * 0.3
            
            r, g, b = band_colors[1]
            color = Color(int(r * intensity), int(g * intensity), int(b * intensity))
            
            if self.led_pairing:
                pair_start = (idx // 2) * 2
                if pair_start < len(result):
                    result[pair_start] = color
                if pair_start + 1 < len(result):
                    result[pair_start + 1] = color
            else:
                result[idx] = color
        
        # High - right third
        high_height = int(high * pixels_per_band)
        remaining = len(colors) - 2 * pixels_per_band
        for i in range(high_height):
            idx = 2 * pixels_per_band + i
            if self.led_pairing:
                pair_idx = i // 2
                intensity = 1.0 - (pair_idx / max(1, remaining // 2)) * 0.3
            else:
                intensity = 1.0 - (i / remaining) * 0.3
            
            r, g, b = band_colors[2]
            color = Color(int(r * intensity), int(g * intensity), int(b * intensity))
            
            if self.led_pairing:
                pair_start = (idx // 2) * 2
                if pair_start < len(result):
                    result[pair_start] = color
                if pair_start + 1 < len(result):
                    result[pair_start + 1] = color
            else:
                result[idx] = color
        
        return result
    
    def _spectrum_enhanced_visualization(self, colors: Colors, bass: float, mid: float, high: float, elapsed: float) -> Colors:
        """Enhanced multi-band spectrum analyzer with cycling colors"""
        
        result = colors.copy()
        
        # Get band levels from audio provider
        if hasattr(self, 'audio_provider') and hasattr(self.audio_provider, 'band_levels'):
            band_levels = self.audio_provider.band_levels
            num_bands = len(band_levels)
        else:
            # Fallback to 3-band mode
            band_levels = [bass, mid, high]
            num_bands = 3
        
        pixels_per_band = len(colors) // num_bands
        
        # Get cycling colors for all bands
        band_colors = self._get_band_colors(elapsed, num_bands)
        
        # Visualize each band
        start_offset = 0
        for band_idx in range(num_bands):
            band_level = band_levels[band_idx]
            r, g, b = band_colors[band_idx]
            
            # Calculate pixels for this band
            if band_idx == num_bands - 1:
                pixels_in_band = len(colors) - start_offset
            else:
                pixels_in_band = pixels_per_band
            
            # Light up pixels based on band level
            band_height = int(band_level * pixels_in_band)
            
            if band_height > 0:
                if self.led_pairing:
                    # Vectorized pair processing
                    num_pairs = band_height // 2
                    for pair_idx in range(num_pairs):
                        intensity = 1.0 - (pair_idx / max(1, pixels_in_band // 2)) * 0.3
                        color_vals = (int(r * intensity), int(g * intensity), int(b * intensity))
                        
                        led_start = start_offset + pair_idx * 2
                        if led_start + 1 < len(result):
                            result.r[led_start:led_start+2] = color_vals[0]
                            result.g[led_start:led_start+2] = color_vals[1]
                            result.b[led_start:led_start+2] = color_vals[2]
                else:
                    # Vectorized single LED processing
                    for i in range(band_height):
                        intensity = 1.0 - (i / pixels_in_band) * 0.3
                        led_idx = start_offset + i
                        if led_idx < len(result):
                            result.r[led_idx] = int(r * intensity)
                            result.g[led_idx] = int(g * intensity)
                            result.b[led_idx] = int(b * intensity)
            
            start_offset += pixels_in_band
        
        return result
    
    def _pulse_visualization(self, colors, overall: float):
        """Pulse base colors with audio - using raw overall level"""
        
        # Use raw overall level without compression
        # Smaller brightness range for more visible variations during music
        min_brightness = 0.05  # 5% minimum (very low)
        max_brightness = 1.0   # 100% maximum
        
        overall **= 3 # the higher the power the more dramatic strobe it looks

        # Map audio level directly to brightness range
        pulse_intensity = min_brightness + (overall * (max_brightness - min_brightness))
        
        # Use list comprehension like the old working version
        return [Color(
            int(c.r * pulse_intensity), 
            int(c.g * pulse_intensity), 
            int(c.b * pulse_intensity)
        ) for c in colors]
    
    def _ring_amplitude_visualization(self, colors: Colors, overall: float, elapsed: float) -> Colors:
        """Ring amplitude effect - ring position shows audio amplitude"""
        
        # Get configurable colors
        background_color = self.parameters.get('background_color', Color(0, 0, 50))  # Dark blue
        ring_color = self.parameters.get('ring_color', Color(255, 255, 255))  # White
        
        # Apply dramatic enhancement (same as pulse)
        enhanced_amplitude = overall
        
        # Map to 6 levels (0-5) with better sensitivity
        level = int(enhanced_amplitude * 10)  # Multiply by 10 instead of 6 for more sensitivity
        level = min(5, max(0, level))
        
        # Start with provided background colors (overlay approach)
        result = colors.copy()
        
        if self.parameters.get('fade_enabled', False):
            # FADE MODE: Use intensity tracking with decay
            decay_factor = self.parameters.get('decay_factor', 0.5)
            
            # Decay all rings
            for i in range(5):
                self._ring_amplitude_intensities[i] *= decay_factor
            
            # Set current ring to full intensity
            if level > 0:
                self._ring_amplitude_intensities[level - 1] = 1.0
            
            # Apply all rings with their current intensities
            fade_threshold = self.parameters.get('fade_threshold', 0.01)
            for ring_index in range(5):
                intensity = self._ring_amplitude_intensities[ring_index]
                if intensity > fade_threshold and self.tree_structure and hasattr(self.tree_structure, 'rings'):
                    if ring_index < len(self.tree_structure.rings):
                        # Blend ring color with background
                        faded_color = Color(
                            min(255, int(ring_color.r * intensity)),
                            min(255, int(ring_color.g * intensity)),
                            min(255, int(ring_color.b * intensity))
                        )
                        
                        ring_leds = self.tree_structure.rings[ring_index]
                        for led_idx in ring_leds:
                            if led_idx < len(result):
                                # Overlay on existing background
                                bg = result[led_idx]
                                result[led_idx] = Color(
                                    min(255, bg.r + faded_color.r),
                                    min(255, bg.g + faded_color.g),
                                    min(255, bg.b + faded_color.b)
                                )
        else:
            # NO FADE MODE: Original behavior - only current ring
            if level > 0 and self.tree_structure and hasattr(self.tree_structure, 'rings'):
                ring_index = level - 1
                if ring_index < len(self.tree_structure.rings):
                    ring_leds = self.tree_structure.rings[ring_index]
                    for led_idx in ring_leds:
                        if led_idx < len(result):
                            # Overlay ring color on background
                            bg = result[led_idx]
                            result[led_idx] = Color(
                                min(255, bg.r + ring_color.r),
                                min(255, bg.g + ring_color.g),
                                min(255, bg.b + ring_color.b)
                            )
        
        return result
    
    def _wave_visualization(self, colors: Colors, bass: float, elapsed: float) -> Colors:
        """Wave effect driven by bass"""
        wave_speed = 1.0 + bass * 4.0
        color_array = np.array([[c.r, c.g, c.b] for c in colors], dtype=np.float32)
        
        pixel_indices = np.arange(len(colors))
        wave_phases = (pixel_indices / len(colors) * 4 * np.pi - elapsed * wave_speed)
        wave_intensities = np.sin(wave_phases) * 0.5 + 0.5
        wave_intensities *= (0.2 + bass * 0.8)
        
        color_array *= wave_intensities[:, np.newaxis]
        return [Color(int(rgb[0]), int(rgb[1]), int(rgb[2])) for rgb in color_array]
    
    def _strobe_visualization(self, colors: Colors, is_beat: bool, overall: float) -> Colors:
        """Strobe on beats"""
        if is_beat and overall > 0.2:
            intensity = int(255 * min(1.0, overall * 2))
            return [Color(intensity, intensity, intensity)] * len(colors)
        else:
            dim = 0.1 + overall * 0.3
            return [Color(int(c.r * dim), int(c.g * dim), int(c.b * dim)) for c in colors]
