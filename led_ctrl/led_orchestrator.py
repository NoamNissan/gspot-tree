#!/usr/bin/env python3
"""
Recipe System - Data-driven LED effect configurations with smart transitions
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import numpy as np
import sounddevice as sd
import threading
import time
import socket
import json
from .led_controller import Color
# Global audio configuration
SAMPLING_RATE = 16000  # Default 16kHz for better compatibility

from .constants import PERSISTENT_GUI_PORT
from .pipeline_demo import (
    PipelineController, TransitionMode, BreathingEffect, 
    StrobeEffect, SparkleEffect, WaveEffect, RandomFlashEffect, RainbowEffect, LavaLampEffect,
    FireEffect, MeltEffect, FadeEffect, ScanEffect, MarchingEffect, BlocksEffect,
    CrawlerEffect, WaterEffect, GlitchEffect, MetroEffect, PowerEffect, RainEffect, WalkingEffect,
    BlendMode, Effect
)

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
    
    def __init__(self, sample_rate=None, block_size=512):
        self.sample_rate = sample_rate or SAMPLING_RATE
        self.block_size = block_size
        
        # Audio levels (thread-safe)
        self.bass = 0.0
        self.mid = 0.0
        self.high = 0.0
        self.overall = 0.0
        
        # Beat detection
        self.beat_threshold = 0.3
        self.last_bass = 0.0
        self.is_beat = False
        self.last_beat_time = 0.0
        
        # Audio stream
        self.stream = None
        self.running = False
        
        # Pre-calculate frequency bin indices for proper musical ranges
        self.bass_bins = slice(0, int(250 * block_size / self.sample_rate))     # 0-250Hz (musical bass)
        self.mid_bins = slice(int(250 * block_size / self.sample_rate), 
                             int(4000 * block_size / self.sample_rate))          # 250-4000Hz (vocals, instruments)
        self.high_bins = slice(int(4000 * block_size / self.sample_rate), 
                              block_size // 2)                              # 4000Hz+ (cymbals, harmonics)
    
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
            
            # Extract frequency bands
            bass = np.mean(magnitude[self.bass_bins])
            mid = np.mean(magnitude[self.mid_bins])
            high = np.mean(magnitude[self.high_bins])
            
            # Much gentler scaling for music - use logarithmic scaling
            # Music has sustained high levels, need more dynamic range
            bass_scale = 0.05   # Very gentle scaling
            mid_scale = 0.1     # Gentle scaling  
            high_scale = 0.2    # Moderate scaling
            
            # Apply logarithmic scaling for better music dynamics
            bass = min(1.0, np.log10(bass * bass_scale + 1) / np.log10(2))  # Log scale
            mid = min(1.0, np.log10(mid * mid_scale + 1) / np.log10(2))
            high = min(1.0, np.log10(high * high_scale + 1) / np.log10(2))
            overall = (bass + mid + high) / 3
            
            # Simple beat detection (bass spike)
            current_time = time.inputBufferAdcTime
            beat_detected = False
            if bass > self.beat_threshold and bass > self.last_bass * 1.5:
                if current_time - self.last_beat_time > 0.1:  # Minimum 100ms between beats
                    beat_detected = True
                    self.last_beat_time = current_time
            
            # Update thread-safe values
            self.bass = bass
            self.mid = mid
            self.high = high
            self.overall = overall
            self.is_beat = beat_detected
            self.last_bass = bass
            
        except Exception as e:
            print(f"Audio processing error: {e}")
    
    def start(self):
        """Start real-time audio capture with device detection"""
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
                    if any(keyword in name for keyword in ['blackhole', 'soundflower', 'loopback']):
                        input_device = i
                        print(f"🎵 Found system audio device: {device['name']}")
                        break
                    # Linux monitor devices  
                    elif 'monitor' in name:
                        input_device = i
                        print(f"🎵 Found monitor device: {device['name']}")
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
    
    def __init__(self, audio_provider: RealTimeAudioProvider, effect_id: str = None):
        super().__init__(effect_id)
        self.audio_provider = audio_provider
        self.parameters = {
            'mode': 'spectrum',     # spectrum, pulse, wave, strobe
            'sensitivity': 1.5,     # Audio sensitivity multiplier
            'bass_boost': 2.0       # Extra bass emphasis
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        if not self.audio_provider.running:
            return colors
        
        # Get real-time audio data
        audio_data = self.audio_provider.get_current_audio_data()
        
        # Apply sensitivity and bass boost
        bass = min(1.0, audio_data.bass * self.parameters['sensitivity'] * self.parameters['bass_boost'])
        mid = min(1.0, audio_data.mid * self.parameters['sensitivity'])
        high = min(1.0, audio_data.high * self.parameters['sensitivity'])
        overall = min(1.0, audio_data.overall * self.parameters['sensitivity'])
        
        # Apply visualization based on mode
        mode = self.parameters['mode']
        
        if mode == 'spectrum':
            return self._spectrum_visualization(colors, bass, mid, high)
        elif mode == 'pulse':
            return self._pulse_visualization(colors, overall)
        elif mode == 'wave':
            return self._wave_visualization(colors, bass, elapsed)
        elif mode == 'strobe':
            return self._strobe_visualization(colors, audio_data.is_beat, overall)
        else:
            return colors
    
    def _spectrum_visualization(self, colors: List[Color], bass: float, mid: float, high: float) -> List[Color]:
        """3-band spectrum analyzer"""
        result = []
        pixels_per_band = len(colors) // 3
        
        # Bass (red) - left third
        bass_height = int(bass * pixels_per_band)
        for i in range(pixels_per_band):
            if i < bass_height:
                intensity = 1.0 - (i / pixels_per_band) * 0.3
                result.append(Color(int(255 * intensity), 0, 0))
            else:
                result.append(Color(0, 0, 0))
        
        # Mid (green) - middle third
        mid_height = int(mid * pixels_per_band)
        for i in range(pixels_per_band):
            if i < mid_height:
                intensity = 1.0 - (i / pixels_per_band) * 0.3
                result.append(Color(0, int(255 * intensity), 0))
            else:
                result.append(Color(0, 0, 0))
        
        # High (blue) - right third
        high_height = int(high * pixels_per_band)
        remaining = len(colors) - len(result)
        for i in range(remaining):
            if i < high_height:
                intensity = 1.0 - (i / remaining) * 0.3
                result.append(Color(0, 0, int(255 * intensity)))
            else:
                result.append(Color(0, 0, 0))
        
        return result
    
    def _pulse_visualization(self, colors: List[Color], overall: float) -> List[Color]:
        """Pulse base colors with audio - with dynamic range compression"""
        
        # Dynamic range compression for music
        # Maps 0.0-1.0 input to a smaller output range so music variations are visible
        compressed_overall = overall ** 0.5  # Square root compression
        
        # Smaller brightness range for more visible variations during music
        min_brightness = 0.05  # 5% minimum (very low)
        max_brightness = 1.0   # 100% maximum
        
        # Map compressed audio level to brightness range
        pulse_intensity = min_brightness + (compressed_overall * (max_brightness - min_brightness))
        
        return [Color(
            int(c.r * pulse_intensity), 
            int(c.g * pulse_intensity), 
            int(c.b * pulse_intensity)
        ) for c in colors]
    
    def _wave_visualization(self, colors: List[Color], bass: float, elapsed: float) -> List[Color]:
        """Wave effect driven by bass"""
        wave_speed = 1.0 + bass * 4.0
        color_array = np.array([[c.r, c.g, c.b] for c in colors], dtype=np.float32)
        
        pixel_indices = np.arange(len(colors))
        wave_phases = (pixel_indices / len(colors) * 4 * np.pi - elapsed * wave_speed)
        wave_intensities = np.sin(wave_phases) * 0.5 + 0.5
        wave_intensities *= (0.2 + bass * 0.8)
        
        color_array *= wave_intensities[:, np.newaxis]
        return [Color(int(rgb[0]), int(rgb[1]), int(rgb[2])) for rgb in color_array]
    
    def _strobe_visualization(self, colors: List[Color], is_beat: bool, overall: float) -> List[Color]:
        """Strobe on beats"""
        if is_beat and overall > 0.2:
            intensity = int(255 * min(1.0, overall * 2))
            return [Color(intensity, intensity, intensity)] * len(colors)
        else:
            dim = 0.1 + overall * 0.3
            return [Color(int(c.r * dim), int(c.g * dim), int(c.b * dim)) for c in colors]

@dataclass
class BaseColorConfig:
    """Base color configuration"""
    colors: List[Color]
    mode: TransitionMode = TransitionMode.STATIC
    speed: float = 1.0

@dataclass
class EffectConfig:
    """Effect configuration"""
    effect_type: str
    parameters: Dict[str, Any]
    enabled: bool = True

@dataclass
class Recipe:
    """Complete recipe definition"""
    name: str
    base_colors: BaseColorConfig
    effects: List[EffectConfig]
    description: str = ""

class RecipeManager:
    """Manages recipe transitions and effect lifecycle"""
    
    def __init__(self, controller: PipelineController):
        self.controller = controller
        self.current_recipe: Optional[Recipe] = None
        self.active_effects: Dict[str, str] = {}  # effect_type -> effect_id
        
    async def apply_recipe(self, recipe: Recipe, transition_time: float = 2.0):
        """Apply a recipe with smart transitions"""
        print(f"🍽️ Applying recipe: {recipe.name}")
        # print(stack_trace())
        # print("--------------------------------")
        if self.current_recipe is None:
            # First recipe - apply directly
            print("Applying recipe directly")
            await self._apply_recipe_direct(recipe)
        else:
            # Transition from current recipe
            print("Transitioning to recipe")
            await self._transition_to_recipe(recipe, transition_time)
        
        self.current_recipe = recipe
        print(f"✅ Recipe '{recipe.name}' applied successfully")
    
    async def _apply_recipe_direct(self, recipe: Recipe):
        """Apply recipe directly (first time)"""
        # Set base colors
        self.controller.pipeline.set_base_colors(
            recipe.base_colors.colors,
            recipe.base_colors.mode,
            recipe.base_colors.speed
        )
        
        # Add all effects
        for effect_config in recipe.effects:
            if effect_config.enabled:
                effect_id = await self._create_effect(effect_config)
                self.active_effects[effect_config.effect_type] = effect_id
    
    async def _transition_to_recipe(self, new_recipe: Recipe, transition_time: float):
        """Smart transition between recipes"""
        
        # 1. Update base colors (always smooth)
        await self._transition_base_colors(new_recipe.base_colors, transition_time / 3)
        
        # 2. Handle effects intelligently
        await self._transition_effects(new_recipe.effects, transition_time * 2 / 3)
    
    async def _transition_base_colors(self, new_base: BaseColorConfig, transition_time: float):
        """Transition base colors smoothly"""
        print(f"🎨 Transitioning base colors...")
        
        # For now, direct change (could add crossfade later)
        self.controller.pipeline.set_base_colors(
            new_base.colors,
            new_base.mode,
            new_base.speed
        )
        
        await asyncio.sleep(transition_time)
    
    async def _transition_effects(self, new_effects: List[EffectConfig], transition_time: float):
        """Smart effect transitions"""
        print(f"⚡ Transitioning effects...")
        
        # Categorize effects
        new_effect_types = {e.effect_type for e in new_effects if e.enabled}
        current_effect_types = set(self.active_effects.keys())
        
        # Effects to keep (update parameters)
        keep_effects = current_effect_types & new_effect_types
        # Effects to remove
        remove_effects = current_effect_types - new_effect_types
        # Effects to add
        add_effects = new_effect_types - current_effect_types
        
        # Step 1: Update existing effects
        for effect_config in new_effects:
            if effect_config.effect_type in keep_effects:
                await self._update_effect_parameters(effect_config)
        
        # Step 2: Gradually remove old effects
        removal_delay = transition_time / max(len(remove_effects), 1) if remove_effects else 0
        for effect_type in remove_effects:
            print(f"  🗑️ Removing {effect_type}")
            if effect_type in self.active_effects:
                effect_id = self.active_effects[effect_type]
                removed = self.controller.pipeline.remove_effect(effect_id)
                if removed:
                    del self.active_effects[effect_type]
                    print(f"    ✅ Successfully removed {effect_type}")
                else:
                    print(f"    ❌ Failed to remove {effect_type} (ID: {effect_id})")
            else:
                print(f"    ⚠️ Effect {effect_type} not in active_effects")
            if removal_delay > 0:
                await asyncio.sleep(removal_delay)
        
        # Step 3: Gradually add new effects
        addition_delay = transition_time / max(len(add_effects), 1) if add_effects else 0
        for effect_config in new_effects:
            if effect_config.effect_type in add_effects and effect_config.enabled:
                print(f"  ➕ Adding {effect_config.effect_type}")
                effect_id = await self._create_effect(effect_config)
                self.active_effects[effect_config.effect_type] = effect_id
                if addition_delay > 0:
                    await asyncio.sleep(addition_delay)
    
    async def _update_effect_parameters(self, effect_config: EffectConfig):
        """Update parameters of existing effect"""
        print(f"  🔧 Updating {effect_config.effect_type} parameters")
        effect_id = self.active_effects[effect_config.effect_type]
        effect = self.controller.pipeline.get_effect(effect_id)
        if effect:
            effect.update_parameters(effect_config.parameters)
    
    async def _create_effect(self, effect_config: EffectConfig) -> str:
        """Create and add effect to pipeline"""
        effect_type = effect_config.effect_type
        
        if effect_type == "breathing":
            effect = BreathingEffect()
        elif effect_type == "strobe":
            effect = StrobeEffect()
        elif effect_type == "sparkle":
            effect = SparkleEffect()
        elif effect_type == "wave":
            effect = WaveEffect()
        elif effect_type == "random_flash":
            effect = RandomFlashEffect()
        elif effect_type == "rainbow":
            effect = RainbowEffect()
            effect.blend_mode = BlendMode.REPLACE  # Replace base colors with rainbow
        elif effect_type == "lava_lamp":
            effect = LavaLampEffect()
        elif effect_type == "fire":
            effect = FireEffect()
        elif effect_type == "melt":
            effect = MeltEffect()
        elif effect_type == "fade":
            effect = FadeEffect()
        elif effect_type == "scan":
            effect = ScanEffect()
        elif effect_type == "marching":
            effect = MarchingEffect()
        elif effect_type == "blocks":
            effect = BlocksEffect()
        elif effect_type == "crawler":
            effect = CrawlerEffect()
        elif effect_type == "water":
            effect = WaterEffect()
        elif effect_type == "glitch":
            effect = GlitchEffect()
        elif effect_type == "metro":
            effect = MetroEffect()
        elif effect_type == "power":
            effect = PowerEffect()
        elif effect_type == "rain":
            effect = RainEffect()
        elif effect_type == "walking":
            effect = WalkingEffect()
        elif effect_type == "spectrum":
            effect = SpectrumEffect(self.controller.num_pixels)
        elif effect_type == "energy":
            effect = EnergyEffect(self.controller.num_pixels)
        elif effect_type == "wavelength":
            effect = WavelengthEffect(self.controller.num_pixels)
        elif effect_type == "scroll":
            effect = ScrollEffect(self.controller.num_pixels)
        elif effect_type == "bars":
            effect = BarsEffect(self.controller.num_pixels)
        elif effect_type == "music_visualizer":
            # Get or create global audio provider
            if not hasattr(self, 'audio_provider'):
                self.audio_provider = RealTimeAudioProvider()
                self.audio_provider.start()
            effect = MusicVisualizerEffect(self.audio_provider)
        else:
            raise ValueError(f"Unknown effect type: {effect_type}")
        
        effect.update_parameters(effect_config.parameters)
        return self.controller.pipeline.add_effect(effect)

# Simple Rainbow Effect for better visual quality
class SpectrumEffect(Effect):
    """LedFx-style spectrum analyzer effect"""
    
    def __init__(self, num_leds: int, color: Color = Color(0, 0, 255), **kwargs):
        from .pipeline_demo import Effect as PipelineEffect
        PipelineEffect.__init__(self)
        self.num_leds = num_leds
        self.color = color
        self.num_bands = 8
        self.band_width = num_leds // self.num_bands
        
    def _apply_effect(self, colors, elapsed: float):
        from .led_controller import Color
        import colorsys
        
        result = [Color(0, 0, 0)] * len(colors)
        
        # Simulate frequency bands
        for band in range(self.num_bands):
            # Simulate intensity based on time and band
            intensity = 0.3 + 0.7 * abs(np.sin(elapsed * 2 + band * 0.8))
            height = int(intensity * self.band_width)
            
            # Color based on frequency
            hue = band / self.num_bands * 0.8
            rgb = colorsys.hsv_to_rgb(hue, 1.0, intensity)
            color = Color(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
            
            start_led = band * self.band_width
            for i in range(height):
                if start_led + i < len(colors):
                    result[start_led + i] = color
                    
        return result

class EnergyEffect(Effect):
    """LedFx-style energy effect"""
    
    def __init__(self, num_leds: int, **kwargs):
        from .pipeline_demo import Effect as PipelineEffect
        PipelineEffect.__init__(self)
        self.num_leds = num_leds
        
    def _apply_effect(self, colors, elapsed: float):
        from .led_controller import Color
        import time
        
        # Simulate energy levels
        energy = 0.5 + 0.5 * abs(np.sin(elapsed * 2))
        
        # Energy-based color
        if energy > 0.8:
            base_color = (255, 255, 0)  # Yellow
        elif energy > 0.5:
            base_color = (255, 100, 0)  # Orange
        else:
            base_color = (255, 0, 0)    # Red
            
        result = []
        for i in range(len(colors)):
            variation = 0.8 + 0.2 * np.sin(elapsed * 5 + i * 0.1)
            brightness = energy * variation
            
            result.append(Color(
                int(base_color[0] * brightness),
                int(base_color[1] * brightness), 
                int(base_color[2] * brightness)
            ))
            
        return result

class WavelengthEffect(Effect):
    """LedFx-style wavelength effect"""
    
    def __init__(self, num_leds: int, **kwargs):
        from .pipeline_demo import Effect as PipelineEffect
        PipelineEffect.__init__(self)
        self.num_leds = num_leds
        
    def _apply_effect(self, colors, elapsed: float):
        from .led_controller import Color
        import colorsys
        
        result = []
        for i in range(len(colors)):
            # Traveling wave
            wave = np.sin(2 * np.pi * (i / 20.0 - elapsed * 2))
            
            if wave > 0:
                hue = 0.1 - wave * 0.1  # Red to orange
                brightness = wave
            else:
                hue = 0.6 + abs(wave) * 0.1  # Blue to cyan
                brightness = abs(wave)
                
            rgb = colorsys.hsv_to_rgb(hue, 1.0, brightness)
            result.append(Color(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255)))
            
        return result

class ScrollEffect(Effect):
    """LedFx-style scroll effect"""
    
    def __init__(self, num_leds: int, **kwargs):
        from .pipeline_demo import Effect as PipelineEffect
        PipelineEffect.__init__(self)
        self.num_leds = num_leds
        self.pattern_length = 20
        self.pattern = []
        
        # Create rainbow pattern
        import colorsys
        for i in range(self.pattern_length):
            hue = i / self.pattern_length
            rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            self.pattern.append((int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255)))
            
    def _apply_effect(self, colors, elapsed: float):
        from .led_controller import Color
        import time
        
        # Scroll speed
        speed = 5.0
        offset = int(elapsed * speed) % self.pattern_length
        
        result = []
        for i in range(len(colors)):
            pattern_idx = (i + offset) % self.pattern_length
            color = self.pattern[pattern_idx]
            result.append(Color(color[0], color[1], color[2]))
            
        return result

class BarsEffect(Effect):
    """LedFx-style bars effect"""
    
    def __init__(self, num_leds: int, **kwargs):
        from .pipeline_demo import Effect as PipelineEffect
        PipelineEffect.__init__(self)
        self.num_leds = num_leds
        self.num_bars = 10
        self.bar_width = num_leds // self.num_bars
        
    def _apply_effect(self, colors, elapsed: float):
        from .led_controller import Color
        import colorsys
        
        result = [Color(0, 0, 0)] * len(colors)
        
        for bar in range(self.num_bars):
            # Simulate frequency data
            freq_data = 0.2 + 0.8 * abs(np.sin(elapsed * 4 + bar * 0.6))
            bar_height = int(freq_data * self.bar_width)
            hue = bar / self.num_bars * 0.8
            
            start_led = bar * self.bar_width
            for i in range(self.bar_width):
                led_idx = start_led + i
                if led_idx < len(colors) and i < bar_height:
                    brightness = 1.0 - (i / self.bar_width) * 0.5
                    rgb = colorsys.hsv_to_rgb(hue, 1.0, brightness)
                    result[led_idx] = Color(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
                    
        return result
    """Simple rainbow effect like the old demo"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 0.5
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        """Apply smooth rainbow across all pixels using vectorized operations"""
        num_pixels = len(colors)
        
        # Vectorized hue calculation
        pixel_indices = np.arange(num_pixels)
        hues = (pixel_indices / num_pixels + elapsed * self.parameters['speed']) % 1.0
        
        # Vectorized HSV to RGB conversion
        rgb_array = self._hsv_to_rgb_vectorized(hues)
        
        # Convert to Color objects
        return [Color(int(rgb[0]), int(rgb[1]), int(rgb[2])) for rgb in rgb_array]
    
    def _hsv_to_rgb_vectorized(self, hues: np.ndarray) -> np.ndarray:
        """Vectorized HSV to RGB conversion (s=1.0, v=1.0)"""
        h = hues % 1.0
        c = 1.0  # v * s = 1.0 * 1.0
        x = c * (1 - np.abs((h * 6) % 2 - 1))
        
        # Create output array
        rgb = np.zeros((len(h), 3))
        
        # Vectorized conditions for each hue sector
        sector0 = h < 1/6
        sector1 = (h >= 1/6) & (h < 2/6)
        sector2 = (h >= 2/6) & (h < 3/6)
        sector3 = (h >= 3/6) & (h < 4/6)
        sector4 = (h >= 4/6) & (h < 5/6)
        sector5 = h >= 5/6
        
        # Assign RGB values for each sector
        rgb[sector0] = np.column_stack([np.full(np.sum(sector0), c), x[sector0], np.zeros(np.sum(sector0))])
        rgb[sector1] = np.column_stack([x[sector1], np.full(np.sum(sector1), c), np.zeros(np.sum(sector1))])
        rgb[sector2] = np.column_stack([np.zeros(np.sum(sector2)), np.full(np.sum(sector2), c), x[sector2]])
        rgb[sector3] = np.column_stack([np.zeros(np.sum(sector3)), x[sector3], np.full(np.sum(sector3), c)])
        rgb[sector4] = np.column_stack([x[sector4], np.zeros(np.sum(sector4)), np.full(np.sum(sector4), c)])
        rgb[sector5] = np.column_stack([np.full(np.sum(sector5), c), np.zeros(np.sum(sector5)), x[sector5]])
        
        return rgb * 255

# Configuration
LED_CRAWL_BLINK_DURATION = 2.0  # seconds per LED blink

# Recipe Definitions
RECIPES = {
    "complex_demo": Recipe(
        name="Complex Demo",
        description="Multi-effect demonstration",
        base_colors=BaseColorConfig(
            colors=[Color(255, 0, 0)],  # Start with red
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("breathing", {"speed": 0.5, "min_intensity": 0.3}),
            EffectConfig("sparkle", {"density": 0.1}),
            EffectConfig("wave", {"speed": 1.0}),
            # EffectConfig("strobe", {"frequency": 3.0})
        ]
    ),
    
    "sunset_breathing": Recipe(
        name="Sunset Breathing",
        description="Calm red-pink transition with breathing and flashes",
        base_colors=BaseColorConfig(
            colors=[Color(255, 0, 0), Color(255, 192, 203)],
            mode=TransitionMode.FADE,
            speed=0.1
        ),
        effects=[
            EffectConfig("breathing", {"speed": 0.3, "min_intensity": 0.2}),
            EffectConfig("random_flash", {"frequency": 2.0})
        ]
    ),
    
    "rainbow_wave": Recipe(
        name="Rainbow Wave",
        description="Rainbow colors with wave effect",
        base_colors=BaseColorConfig(
            colors=[
                Color(255, 0, 0), Color(255, 127, 0), Color(255, 255, 0),
                Color(0, 255, 0), Color(0, 0, 255), Color(75, 0, 130), Color(148, 0, 211)
            ],
            mode=TransitionMode.CYCLE,
            speed=0.5
        ),
        effects=[
            EffectConfig("wave", {"speed": 2.0, "amplitude": 0.3}),
            EffectConfig("sparkle", {"density": 0.05})
        ]
    ),
    
    "rainbow": Recipe(
        name="Pure Rainbow",
        description="Classic rainbow cycling effect",
        base_colors=BaseColorConfig(
            colors=[Color(255, 255, 255)],  # Dummy base color
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("rainbow", {"speed": 0.5})
        ]
    ),
    
    "music_spectrum": Recipe(
        name="Music Spectrum Analyzer",
        description="Real-time audio spectrum visualization",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "spectrum", "sensitivity": 1.5, "bass_boost": 2.0})
        ]
    ),
    
    "music_pulse": Recipe(
        name="Music Pulse",
        description="Colors pulse with music",
        base_colors=BaseColorConfig(
            colors=[Color(255, 0, 0), Color(0, 0, 255)],  # Red-blue fade
            mode=TransitionMode.FADE,
            speed=0.2
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "pulse", "sensitivity": 1.0})  # Much lower sensitivity
        ]
    ),
    
    "spectrum_analyzer": Recipe(
        name="Spectrum Analyzer",
        description="LedFx-style spectrum analyzer bars",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("spectrum", {"sensitivity": 1.0})
        ]
    ),
    
    "energy_pulse": Recipe(
        name="Energy Pulse",
        description="Energy-based color changes",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("energy", {"sensitivity": 1.2})
        ]
    ),
    
    "wavelength_flow": Recipe(
        name="Wavelength Flow",
        description="Traveling wavelength effect",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("wavelength", {"speed": 1.0})
        ]
    ),
    
    "rainbow_scroll": Recipe(
        name="Rainbow Scroll",
        description="Scrolling rainbow pattern",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("scroll", {"speed": 1.5})
        ]
    ),
    
    "frequency_bars": Recipe(
        name="Frequency Bars",
        description="Audio frequency bar visualization",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("bars", {"sensitivity": 1.0})
        ]
    ),
    
    "lava_lamp": Recipe(
        name="Lava Lamp",
        description="Smooth flowing lava lamp effect",
        base_colors=BaseColorConfig(
            colors=[Color(255, 100, 0), Color(255, 0, 100)],  # Orange to magenta
            mode=TransitionMode.FADE,
            speed=0.1
        ),
        effects=[
            EffectConfig("lava_lamp", {"speed": 1.0, "contrast": 0.6})
        ]
    ),
    
    "fire_demo": Recipe(
        name="Fire Demo",
        description="Flickering fire effect",
        base_colors=BaseColorConfig(
            colors=[Color(255, 100, 0), Color(255, 0, 0)],  # Orange to red
            mode=TransitionMode.FADE,
            speed=0.1
        ),
        effects=[
            EffectConfig("fire", {"speed": 0.06, "intensity": 10})
        ]
    ),
    
    "scanner": Recipe(
        name="Scanner",
        description="Cylon eye scanner effect",
        base_colors=BaseColorConfig(
            colors=[Color(255, 0, 0)],  # Red
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("scan", {"speed": 3.0, "width": 8})
        ]
    ),
    
    "digital_rain": Recipe(
        name="Digital Rain",
        description="Matrix-style digital rain",
        base_colors=BaseColorConfig(
            colors=[Color(0, 255, 0)],  # Green
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("rain", {"speed": 2.0, "density": 0.15})
        ]
    ),
    
    "melt_flow": Recipe(
        name="Melt Flow",
        description="Melting color flow effect",
        base_colors=BaseColorConfig(
            colors=[Color(255, 0, 255), Color(0, 255, 255)],  # Magenta to cyan
            mode=TransitionMode.FADE,
            speed=0.2
        ),
        effects=[
            EffectConfig("melt", {"speed": 0.8, "reactivity": 0.6})
        ]
    ),
    
    "water_ripples": Recipe(
        name="Water Ripples",
        description="Calm water ripple effect",
        base_colors=BaseColorConfig(
            colors=[Color(0, 100, 255), Color(0, 200, 255)],  # Blue water
            mode=TransitionMode.FADE,
            speed=0.1
        ),
        effects=[
            EffectConfig("water", {"speed": 0.8, "ripples": 4})
        ]
    ),
    
    "marching_ants": Recipe(
        name="Marching Ants",
        description="Classic marching ants pattern",
        base_colors=BaseColorConfig(
            colors=[Color(255, 255, 255)],  # White
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("marching", {"speed": 2.0, "size": 3})
        ]
    ),
    
    "glitch_matrix": Recipe(
        name="Glitch Matrix",
        description="Digital glitch corruption",
        base_colors=BaseColorConfig(
            colors=[Color(0, 255, 0), Color(255, 0, 0)],  # Green to red
            mode=TransitionMode.FADE,
            speed=0.3
        ),
        effects=[
            EffectConfig("glitch", {"intensity": 0.3, "speed": 7.0})
        ]
    ),
    
    "power_bars": Recipe(
        name="Power Bars",
        description="Power level visualization",
        base_colors=BaseColorConfig(
            colors=[Color(0, 255, 0), Color(255, 255, 0), Color(255, 0, 0)],  # Green to yellow to red
            mode=TransitionMode.FADE,
            speed=0.1
        ),
        effects=[
            EffectConfig("power", {"level": 1.0, "direction": 1})  # Full power = all LEDs
        ]
    ),
    
    "fade_cycle": Recipe(
        name="Fade Cycle",
        description="Smooth color fade cycling",
        base_colors=BaseColorConfig(
            colors=[Color(255, 0, 0), Color(0, 255, 0), Color(0, 0, 255)],  # RGB cycle
            mode=TransitionMode.FADE,
            speed=0.1
        ),
        effects=[
            EffectConfig("fade", {"speed": 1.0})
        ]
    ),
    
    "color_blocks": Recipe(
        name="Color Blocks",
        description="Moving color blocks",
        base_colors=BaseColorConfig(
            colors=[Color(255, 0, 255), Color(255, 255, 0)],  # Magenta to yellow
            mode=TransitionMode.FADE,
            speed=0.2
        ),
        effects=[
            EffectConfig("blocks", {"speed": 1.5, "block_size": 6})
        ]
    ),
    
    "pixel_crawler": Recipe(
        name="Pixel Crawler",
        description="Crawling pixel with tail",
        base_colors=BaseColorConfig(
            colors=[Color(0, 255, 255)],  # Cyan
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("crawler", {"speed": 2.5, "tail_length": 12})
        ]
    ),
    
    "metro_beat": Recipe(
        name="Metro Beat",
        description="Metronome beat flash",
        base_colors=BaseColorConfig(
            colors=[Color(255, 255, 255)],  # White
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("metro", {"bpm": 120, "flash_duration": 0.1})
        ]
    ),
    
    "walking_lights": Recipe(
        name="Walking Lights",
        description="White lights walking back and forth",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base (effect creates white)
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("walking", {"width": 2, "speed": 5, "direction_change_time": 6.0})
        ]
    ),
    
    "blue_magenta_breathing": Recipe(
        name="Blue Magenta Breathing",
        description="Blue to magenta breathing colors",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 255), Color(255, 0, 255)],  # Blue to magenta
            mode=TransitionMode.FADE,
            speed=0.2
        ),
        effects=[
            EffectConfig("breathing", {"speed": 0.4, "min_intensity": 0.3})
        ]
    ),
    
    "white_strobe": Recipe(
        name="White Strobe",
        description="High-frequency white strobe (stroboscopic effect)",
        base_colors=BaseColorConfig(
            colors=[Color(255, 255, 255)],  # White
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("strobe", {"frequency": 100.0, "duty_cycle": 0.5})  # True stroboscopic range
        ]
    )
}

async def demo_recipe_transitions(num_pixels: int = 100, force_simulation: bool = False):
    """Demonstrate recipe transitions"""
    controller = PipelineController(num_pixels, force_simulation=force_simulation)
    await controller.start()
    
    try:
        # Start rendering loop
        render_task = asyncio.create_task(controller.run_loop())
        
        # Create recipe manager
        recipe_manager = RecipeManager(controller)
        
        print("🍽️ Recipe Transition Demo")
        print("Press Ctrl+C to stop at any time")
        
        # Apply complex_demo
        await recipe_manager.apply_recipe(RECIPES["complex_demo"])
        await asyncio.sleep(5)  # Reduced from 10
        
        # Pure rainbow effect
        await recipe_manager.apply_recipe(RECIPES["rainbow"], transition_time=2.0)
        await asyncio.sleep(4)  # Reduced from 8
        
        # Transition to sunset_breathing (breathing continues, other effects change)
        await recipe_manager.apply_recipe(RECIPES["sunset_breathing"], transition_time=3.0)
        await asyncio.sleep(4)  # Reduced from 8
        
        # Transition to rainbow_wave
        await recipe_manager.apply_recipe(RECIPES["rainbow_wave"], transition_time=3.0)
        await asyncio.sleep(4)  # Reduced from 8
        
        # LedFx-style spectrum analyzer
        await recipe_manager.apply_recipe(RECIPES["spectrum_analyzer"], transition_time=3.0)
        await asyncio.sleep(4)  # Reduced from 8
        
        # Energy pulse effect
        await recipe_manager.apply_recipe(RECIPES["energy_pulse"], transition_time=2.0)
        await asyncio.sleep(3)  # Reduced from 6
        
        # Wavelength flow
        await recipe_manager.apply_recipe(RECIPES["wavelength_flow"], transition_time=2.0)
        await asyncio.sleep(3)  # Reduced from 6
        
        # Rainbow scroll
        await recipe_manager.apply_recipe(RECIPES["rainbow_scroll"], transition_time=2.0)
        await asyncio.sleep(3)  # Reduced from 6
        
        # Frequency bars
        await recipe_manager.apply_recipe(RECIPES["frequency_bars"], transition_time=2.0)
        await asyncio.sleep(4)  # Reduced from 8
        
        # New effects showcase
        print("🔥 Showcasing new effects...")
        
        # Fire effect
        await recipe_manager.apply_recipe(RECIPES["fire_demo"], transition_time=2.0)
        await asyncio.sleep(4)
        
        # Scanner effect
        await recipe_manager.apply_recipe(RECIPES["scanner"], transition_time=1.0)
        await asyncio.sleep(3)
        
        # Water ripples
        await recipe_manager.apply_recipe(RECIPES["water_ripples"], transition_time=2.0)
        await asyncio.sleep(4)
        
        # Glitch matrix
        await recipe_manager.apply_recipe(RECIPES["glitch_matrix"], transition_time=1.0)
        await asyncio.sleep(3)
        
        # Digital rain
        await recipe_manager.apply_recipe(RECIPES["digital_rain"], transition_time=2.0)
        await asyncio.sleep(4)
        
        # Music spectrum analyzer
        await recipe_manager.apply_recipe(RECIPES["music_spectrum"], transition_time=3.0)
        await asyncio.sleep(10)
        
        # Music pulse effect
        await recipe_manager.apply_recipe(RECIPES["music_pulse"], transition_time=3.0)
        await asyncio.sleep(10)
        
        # Stroboscopic demo: Blue/Magenta breathing vs White strobe
        print("🔥 Starting stroboscopic demo...")
        
        # Stroboscopic cycle: 10s breathing + 5s strobe, repeat 3 times
        for cycle in range(3):
            print(f"   Cycle {cycle + 1}/3: Breathing phase...")
            await recipe_manager.apply_recipe(RECIPES["blue_magenta_breathing"], transition_time=0.0)
            await asyncio.sleep(10.0)
            
            print(f"   Cycle {cycle + 1}/3: Strobe phase...")
            await recipe_manager.apply_recipe(RECIPES["white_strobe"], transition_time=0.0)
            await asyncio.sleep(5.0)
        
        # Back to sunset_breathing (smooth transition)
        await recipe_manager.apply_recipe(RECIPES["sunset_breathing"], transition_time=3.0)
        await asyncio.sleep(8)
        
        print("🍽️ Recipe demo completed!")
        render_task.cancel()
        
    except KeyboardInterrupt:
        print("\n🍽️ Recipe demo interrupted")
    finally:
        await controller.stop()

async def run_single_recipe(recipe_name: str, num_pixels: int = 100, force_simulation: bool = False):
    """Run a single recipe continuously"""
    if recipe_name not in RECIPES:
        print(f"❌ Recipe '{recipe_name}' not found!")
        print(f"Available recipes: {', '.join(RECIPES.keys())}")
        return
    
    controller = PipelineController(num_pixels, force_simulation=force_simulation)
    await controller.start()
    
    try:
        # Start rendering loop
        render_task = asyncio.create_task(controller.run_loop())
        
        # Create recipe manager
        recipe_manager = RecipeManager(controller)
        
        recipe = RECIPES[recipe_name]
        print(f"🍽️ Running recipe: {recipe.name}")
        print(f"   Description: {recipe.description}")
        print("   Press Ctrl+C to stop...")
        
        # Apply recipe
        await recipe_manager.apply_recipe(recipe, transition_time=0)
        
        # Run indefinitely until interrupted
        while True:
            await asyncio.sleep(1)
        
    except KeyboardInterrupt:
        print(f"\n🍽️ Recipe '{recipe_name}' stopped")
    finally:
        # Clean up audio if it was started
        if hasattr(recipe_manager, 'audio_provider'):
            recipe_manager.audio_provider.stop()
        await controller.stop()

async def clear_all_leds(num_pixels: int, use_persistent_gui: bool = False):
    """Clear all LEDs to black"""
    # Only needed for persistent GUI mode - regular mode starts blank anyway
    if use_persistent_gui:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(('localhost', PERSISTENT_GUI_PORT))
            
            # Send bulk update command (more efficient)
            command = {
                'type': 'update_all_pixels',
                'pixels': [[0, 0, 0]] * num_pixels
            }
            message = json.dumps(command) + '\n'
            client_socket.send(message.encode())
            
            client_socket.close()
            print("  Sent bulk clear command to persistent GUI")
        except Exception as e:
            print(f"  Failed to connect to persistent GUI: {e}")
    else:
        print("  Non-persistent mode starts blank automatically")

async def set_led_range(range_str: str, num_pixels: int = 100, force_simulation: bool = False):
    """Set specific LED range to white, all others black"""
    controller = PipelineController(num_pixels, force_simulation=force_simulation)
    await controller.start()
    
    try:
        # Start rendering loop
        render_task = asyncio.create_task(controller.run_loop())
        
        # Parse range string
        if ',' in range_str:
            # Range: "5,10"
            start_idx, end_idx = map(int, range_str.split(','))
            print(f"💡 Setting LED range {start_idx} to {end_idx} (white)")
        else:
            # Single LED: "5"
            start_idx = end_idx = int(range_str)
            print(f"💡 Setting single LED {start_idx} (white)")
        
        # Validate indices
        if start_idx < 0 or end_idx >= num_pixels or start_idx > end_idx:
            print(f"❌ Invalid range: {start_idx}-{end_idx} for {num_pixels} LEDs")
            return
        
        # Create colors array - black with white range
        colors = [Color(0, 0, 0)] * num_pixels
        for i in range(start_idx, end_idx + 1):
            colors[i] = Color(255, 255, 255)
        
        # Set colors and hold
        controller.pipeline.set_base_colors(colors, TransitionMode.STATIC)
        
        print(f"   LEDs {start_idx}-{end_idx} are white, others are black")
        print("   Press Ctrl+C to stop...")
        
        # Hold the pattern
        while True:
            await asyncio.sleep(1.0)
        
    except KeyboardInterrupt:
        print(f"\n💡 LED range display stopped")
        render_task.cancel()
    except ValueError:
        print(f"❌ Invalid range format: '{range_str}'. Use '5' or '5,10'")
    finally:
        await controller.stop()

async def led_crawl(num_pixels: int = 100, blink_duration: float = 2.0, force_simulation: bool = False):
    """LED crawl mode - progressively light up LEDs with blinking"""
    controller = PipelineController(num_pixels, force_simulation=force_simulation)
    await controller.start()
    
    try:
        # Start rendering loop
        render_task = asyncio.create_task(controller.run_loop())
        
        print(f"🐛 LED Crawl Mode - {num_pixels} LEDs")
        print(f"   Blink duration: {blink_duration}s per LED")
        print("   Press Ctrl+C to stop...")
        
        for current_led in range(num_pixels):
            print(f"   LED {current_led}: blinking...")
            
            # Create colors: previous LEDs solid white, current LED blinks, rest black
            blink_start = time.time()
            while time.time() - blink_start < blink_duration:
                colors = [Color(0, 0, 0)] * num_pixels
                
                # Set previous LEDs to solid white
                for i in range(current_led):
                    colors[i] = Color(255, 255, 255)
                
                # Blink current LED (0.5s on/off cycle)
                if int((time.time() - blink_start) * 2) % 2 == 0:
                    colors[current_led] = Color(255, 255, 255)
                
                controller.pipeline.set_base_colors(colors, TransitionMode.STATIC)
                await asyncio.sleep(0.1)
            
            print(f"   LED {current_led}: solid white")
        
        # Final state - all LEDs solid white
        colors = [Color(255, 255, 255)] * num_pixels
        controller.pipeline.set_base_colors(colors, TransitionMode.STATIC)
        
        print("🐛 LED Crawl completed - all LEDs solid white")
        print("   Press Ctrl+C to stop...")
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
        
    except KeyboardInterrupt:
        print(f"\n🐛 LED Crawl stopped")
    finally:
        await controller.stop()

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Recipe System Demo')
    parser.add_argument('--pixels', type=int, default=100, help='Number of pixels (default: 100)')
    parser.add_argument('--recipe', type=str, help='Run specific recipe directly (complex_demo, sunset_breathing, rainbow_wave, rainbow, music_spectrum, music_pulse)')
    parser.add_argument('--set-led-range', type=str, help='Light up LED range: "5" (single LED) or "5,10" (range from 5 to 10)')
    parser.add_argument('--led-crawl', action='store_true', help='LED crawl mode - progressively light up LEDs with blinking')
    parser.add_argument('--persistent-gui', action='store_true', help='Use persistent GUI that stays open between runs')
    parser.add_argument('--simulation', action='store_true', help='Run in simulation mode with GUI (default: real LEDs)')
    parser.add_argument('--high-fidelity', action='store_true', help='Use 48kHz audio sampling (default: 16kHz for better compatibility)')
    parser.add_argument('--start-blank', action='store_true', help='Clear all LEDs to black before starting')
    parser.add_argument('--crawl-blink-time', type=float, default=2.0, help='Blink duration per LED in crawl mode (default: 2.0 seconds)')
    
    args = parser.parse_args()
    
    print(f"🍽️ Recipe System")
    print(f"  Pixels: {args.pixels}")
    
    # Set audio sampling rate
    global SAMPLING_RATE
    if args.high_fidelity:
        SAMPLING_RATE = 48000
        print(f"  Audio: High-fidelity mode (48kHz)")
    else:
        print(f"  Audio: Standard mode (16kHz)")
    
    # Enable persistent GUI mode if requested
    if args.persistent_gui:
        from . import mock_neopixel
        mock_neopixel.set_persistent_mode(True)
        print(f"  GUI: Persistent mode enabled")
    
    # Clear all LEDs if requested
    if args.start_blank:
        print(f"  Clearing all LEDs to black...")
        await clear_all_leds(args.pixels, args.persistent_gui)
        # Brief pause to ensure clear completes before next command
        await asyncio.sleep(0.2)
    
    # Determine simulation mode - default is real LEDs
    force_simulation = args.simulation
    
    if args.set_led_range:
        print(f"  Mode: Set LED Range ({args.set_led_range})")
        await set_led_range(args.set_led_range, args.pixels, force_simulation)
    elif args.led_crawl:
        print(f"  Mode: LED Crawl")
        await led_crawl(args.pixels, args.crawl_blink_time, force_simulation)
    elif args.recipe:
        print(f"  Mode: Single recipe ({args.recipe})")
        await run_single_recipe(args.recipe, args.pixels, force_simulation)
    else:
        print(f"  Mode: Full demo sequence")
        await demo_recipe_transitions(args.pixels, force_simulation)

if __name__ == "__main__":
    asyncio.run(main())
