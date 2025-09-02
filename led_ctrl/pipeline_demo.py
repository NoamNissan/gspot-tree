#!/usr/bin/env python3
"""
Layered Effects Pipeline - Composable LED effects system
"""

import asyncio
import argparse
import math
import time
import random
import uuid
import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from led_controller import Color
from mock_neopixel import MockNeoPixel

class TransitionMode(Enum):
    STATIC = "static"
    CYCLE = "cycle"
    FADE = "fade"
    RANDOM = "random"

class BlendMode(Enum):
    REPLACE = "replace"
    MULTIPLY = "multiply"
    ADD = "add"
    OVERLAY = "overlay"

@dataclass
class BaseColorLayer:
    """Base color layer that provides the foundation colors"""
    colors: List[Color]
    transition_mode: TransitionMode = TransitionMode.STATIC
    transition_speed: float = 1.0
    current_position: float = 0.0
    
    def get_colors(self, num_pixels: int, elapsed: float) -> List[Color]:
        """Get base colors for all pixels"""
        if not self.colors:
            return [Color(0, 0, 0)] * num_pixels
        
        if self.transition_mode == TransitionMode.STATIC:
            # Single color or repeat pattern
            return [self.colors[i % len(self.colors)] for i in range(num_pixels)]
        
        elif self.transition_mode == TransitionMode.CYCLE:
            # Cycle through colors over time
            self.current_position = (elapsed * self.transition_speed) % len(self.colors)
            color_index = int(self.current_position)
            return [self.colors[color_index]] * num_pixels
        
        elif self.transition_mode == TransitionMode.FADE:
            # Smooth fade between colors
            self.current_position = (elapsed * self.transition_speed) % len(self.colors)
            color1_idx = int(self.current_position) % len(self.colors)
            color2_idx = (color1_idx + 1) % len(self.colors)
            blend_factor = self.current_position - int(self.current_position)
            
            blended_color = self.colors[color1_idx].blend(self.colors[color2_idx], blend_factor)
            return [blended_color] * num_pixels
        
        else:  # RANDOM
            # Random color selection
            random.seed(int(elapsed * self.transition_speed))
            color = random.choice(self.colors)
            return [color] * num_pixels

class Effect:
    """Base class for all effects"""
    
    def __init__(self, effect_id: str = None):
        self.effect_id = effect_id or str(uuid.uuid4())
        self.enabled = True
        self.parameters = {}
        self.blend_mode = BlendMode.MULTIPLY
        self.internal_state = {}
        self.start_time = time.time()
    
    def apply(self, colors: List[Color], elapsed: float) -> List[Color]:
        """Apply effect to color array"""
        if not self.enabled:
            return colors
        return self._apply_effect(colors, elapsed)
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        """Override this in subclasses"""
        return colors
    
    def update_parameters(self, parameters: Dict[str, Any]):
        """Update effect parameters"""
        self.parameters.update(parameters)

class BreathingEffect(Effect):
    """Breathing intensity effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 1.0,
            'min_intensity': 0.3,
            'max_intensity': 1.0
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        # Calculate breathing intensity
        phase = math.sin(elapsed * self.parameters['speed'] * 2 * math.pi) * 0.5 + 0.5
        intensity = (self.parameters['min_intensity'] + 
                    (self.parameters['max_intensity'] - self.parameters['min_intensity']) * phase)
        
        # Convert colors to numpy array for vectorized operations
        color_array = np.array([[c.r, c.g, c.b] for c in colors], dtype=np.float32)
        
        # Apply intensity vectorized
        color_array *= intensity
        
        # Convert back to Color objects
        return [Color(int(rgb[0]), int(rgb[1]), int(rgb[2])) for rgb in color_array]

class StrobeEffect(Effect):
    """Strobe flashing effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'frequency': 5.0,
            'duty_cycle': 0.1  # 10% on, 90% off
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        cycle_time = 1.0 / self.parameters['frequency']
        phase = (elapsed % cycle_time) / cycle_time
        
        if phase < self.parameters['duty_cycle']:
            # Strobe on - full intensity
            return colors
        else:
            # Strobe off - dark
            return [Color(0, 0, 0)] * len(colors)

class SparkleEffect(Effect):
    """Random sparkle effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'density': 0.05,  # 5% of pixels sparkle
            'brightness': 1.0
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        result = colors.copy()
        
        # Add random sparkles
        for i in range(len(colors)):
            if random.random() < self.parameters['density']:
                # Sparkle this pixel
                sparkle_intensity = random.uniform(0.5, 1.0) * self.parameters['brightness']
                result[i] = Color(
                    min(255, int(colors[i].r + 255 * sparkle_intensity)),
                    min(255, int(colors[i].g + 255 * sparkle_intensity)),
                    min(255, int(colors[i].b + 255 * sparkle_intensity))
                )
        
        return result

class WaveEffect(Effect):
    """Traveling wave effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 2.0,
            'wavelength': 20,
            'amplitude': 0.5
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        # Convert colors to numpy array
        color_array = np.array([[c.r, c.g, c.b] for c in colors], dtype=np.float32)
        
        # Calculate wave intensities for all pixels at once
        pixel_indices = np.arange(len(colors))
        wave_phases = (pixel_indices / self.parameters['wavelength'] - elapsed * self.parameters['speed']) * 2 * np.pi
        wave_intensities = np.sin(wave_phases) * self.parameters['amplitude'] + (1 - self.parameters['amplitude'])
        
        # Apply wave intensities vectorized
        color_array *= wave_intensities[:, np.newaxis]  # Broadcast to RGB channels
        
        # Convert back to Color objects
        return [Color(int(rgb[0]), int(rgb[1]), int(rgb[2])) for rgb in color_array]

class RandomFlashEffect(Effect):
    """Random single LED flash effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'frequency': 1.0,  # 1Hz - once per second
            'flash_duration': 0.01,  # 10ms flash
            'flash_color': Color(255, 255, 255)  # White flash
        }
        self.last_flash_time = 0
        self.current_flash_pixel = -1
        self.flash_start_time = 0
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        result = colors.copy()
        
        # Check if it's time for a new flash (every 1 second)
        if elapsed - self.last_flash_time >= (1.0 / self.parameters['frequency']):
            # Start new flash
            self.last_flash_time = elapsed
            self.flash_start_time = elapsed
            # Pick random LED
            self.current_flash_pixel = random.randint(0, len(colors) - 1)
        
        # Check if we're currently in a flash
        flash_elapsed = elapsed - self.flash_start_time
        if (self.current_flash_pixel >= 0 and 
            flash_elapsed < self.parameters['flash_duration']):
            # Flash the selected pixel
            result[self.current_flash_pixel] = self.parameters['flash_color']
        
        return result

class LavaLampEffect(Effect):
    """Lava lamp flowing effect with smooth color transitions"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 1.0,
            'contrast': 0.6  # Difference between light and dark spots
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        # Vectorized time calculations
        t1 = elapsed * self.parameters['speed']
        t2 = elapsed * self.parameters['speed'] * 2
        
        # Vectorized position array
        positions = np.linspace(0, 1, num_pixels)
        
        # Vectorized wave calculations
        w1 = np.sin(t1 + positions * np.pi * 2)
        w2 = np.sin(t2 - positions * np.pi * 2)
        w3 = np.sin(positions + w1 + w2)
        
        # Vectorized intensity calculation
        intensity = (w1 + 0.1) * (w2 + 0.1) * (w3 + 0.1)
        intensity = np.clip(intensity, 0, 1)
        
        # Apply contrast
        contrast = 1 - self.parameters['contrast']
        intensity = np.power(intensity + contrast, 2)
        intensity = np.clip(intensity, 0, 1)
        
        # Apply to base colors
        result = []
        for i, base_color in enumerate(colors):
            mult = intensity[i]
            result.append(Color(
                int(base_color.r * mult),
                int(base_color.g * mult),
                int(base_color.b * mult)
            ))
        
        return result

class FireEffect(Effect):
    """Flickering fire simulation with sparks"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 0.04,
            'intensity': 8,
            'fade_chance': 0.5
        }
        self.spark_pixels = None
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        if self.spark_pixels is None:
            self.spark_pixels = np.zeros(num_pixels, dtype=np.float32)
        
        # Create new sparks randomly
        new_sparks = np.random.random(num_pixels) < self.parameters['speed']
        self.spark_pixels[new_sparks] = np.random.random(np.sum(new_sparks)) * self.parameters['intensity']
        
        # Fade existing sparks
        fade_mask = np.random.random(num_pixels) < self.parameters['fade_chance']
        self.spark_pixels[fade_mask] *= 0.8
        
        # Apply fire effect to base colors
        result = []
        for i, base_color in enumerate(colors):
            intensity = min(1.0, self.spark_pixels[i])
            result.append(Color(
                min(255, int(base_color.r * (0.5 + intensity * 0.5))),
                min(255, int(base_color.g * (0.3 + intensity * 0.3))),
                int(base_color.b * 0.1)
            ))
        return result

class MeltEffect(Effect):
    """Melting/dripping effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 0.5,
            'reactivity': 0.5
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        # Create melting pattern
        positions = np.linspace(0, 1, num_pixels)
        melt_wave = np.sin(elapsed * self.parameters['speed'] + positions * np.pi * 4)
        melt_intensity = (melt_wave + 1) * 0.5  # Normalize to 0-1
        
        result = []
        for i, base_color in enumerate(colors):
            mult = melt_intensity[i]
            result.append(Color(
                int(base_color.r * mult),
                int(base_color.g * mult),
                int(base_color.b * mult)
            ))
        return result

class FadeEffect(Effect):
    """Smooth color fading through gradients"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 0.5
        }
        self.fade_index = 0.0
        self.forward = True
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        # Update fade index
        self.fade_index += 0.0015 * self.parameters['speed']
        if self.fade_index > 1:
            self.fade_index = 1
            self.forward = not self.forward
        self.fade_index = self.fade_index % 1
        
        fade_mult = self.fade_index if self.forward else 1 - self.fade_index
        
        result = []
        for base_color in colors:
            result.append(Color(
                int(base_color.r * fade_mult),
                int(base_color.g * fade_mult),
                int(base_color.b * fade_mult)
            ))
        return result

class ScanEffect(Effect):
    """Scanner/cylon eye effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 2.0,
            'width': 5
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        # Calculate scanner position
        cycle_time = 2.0 / self.parameters['speed']
        phase = (elapsed % cycle_time) / cycle_time
        if phase > 0.5:
            phase = 1.0 - phase
        scanner_pos = phase * 2 * (num_pixels - 1)
        
        # Create scanner beam
        positions = np.arange(num_pixels)
        distances = np.abs(positions - scanner_pos)
        intensities = np.maximum(0, 1 - distances / self.parameters['width'])
        
        result = []
        for i, base_color in enumerate(colors):
            mult = intensities[i]
            result.append(Color(
                int(base_color.r * mult),
                int(base_color.g * mult),
                int(base_color.b * mult)
            ))
        return result

class MarchingEffect(Effect):
    """Marching ants pattern"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 1.0,
            'size': 4
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        # Create marching pattern
        offset = elapsed * self.parameters['speed'] * self.parameters['size']
        positions = np.arange(num_pixels) + offset
        pattern = (positions // self.parameters['size']) % 2
        
        result = []
        for i, base_color in enumerate(colors):
            mult = pattern[i]
            result.append(Color(
                int(base_color.r * mult),
                int(base_color.g * mult),
                int(base_color.b * mult)
            ))
        return result

class BlocksEffect(Effect):
    """Moving color blocks"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 1.0,
            'block_size': 8
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        # Create moving blocks
        offset = elapsed * self.parameters['speed'] * self.parameters['block_size']
        positions = (np.arange(num_pixels) + offset) % (self.parameters['block_size'] * 2)
        block_pattern = positions < self.parameters['block_size']
        
        result = []
        for i, base_color in enumerate(colors):
            mult = 1.0 if block_pattern[i] else 0.3
            result.append(Color(
                int(base_color.r * mult),
                int(base_color.g * mult),
                int(base_color.b * mult)
            ))
        return result

class CrawlerEffect(Effect):
    """Crawling pixel effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 2.0,
            'tail_length': 10
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        # Calculate crawler position
        crawler_pos = (elapsed * self.parameters['speed']) % num_pixels
        
        # Create tail effect
        positions = np.arange(num_pixels)
        distances = np.minimum(
            np.abs(positions - crawler_pos),
            np.abs(positions - crawler_pos + num_pixels),
        )
        distances = np.minimum(distances, np.abs(positions - crawler_pos - num_pixels))
        
        intensities = np.maximum(0, 1 - distances / self.parameters['tail_length'])
        
        result = []
        for i, base_color in enumerate(colors):
            mult = intensities[i]
            result.append(Color(
                int(base_color.r * mult),
                int(base_color.g * mult),
                int(base_color.b * mult)
            ))
        return result

class WaterEffect(Effect):
    """Water ripple simulation"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 1.0,
            'ripples': 3
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        # Create water ripples
        positions = np.linspace(0, 1, num_pixels)
        ripple_sum = np.zeros(num_pixels)
        
        for i in range(self.parameters['ripples']):
            phase_offset = i * np.pi / self.parameters['ripples']
            ripple = np.sin(elapsed * self.parameters['speed'] + positions * np.pi * 4 + phase_offset)
            ripple_sum += ripple
        
        intensities = (ripple_sum / self.parameters['ripples'] + 1) * 0.5
        intensities = np.clip(intensities, 0, 1)
        
        result = []
        for i, base_color in enumerate(colors):
            mult = intensities[i]
            result.append(Color(
                int(base_color.r * mult),
                int(base_color.g * mult),
                int(base_color.b * mult)
            ))
        return result

class GlitchEffect(Effect):
    """Digital glitch/corruption effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'intensity': 0.3,
            'speed': 5.0
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        # Create glitch pattern
        glitch_trigger = np.sin(elapsed * self.parameters['speed']) > 0.7
        if glitch_trigger:
            # Random glitch pixels
            glitch_mask = np.random.random(num_pixels) < self.parameters['intensity']
            glitch_colors = np.random.randint(0, 256, (num_pixels, 3))
        else:
            glitch_mask = np.zeros(num_pixels, dtype=bool)
            glitch_colors = np.zeros((num_pixels, 3))
        
        result = []
        for i, base_color in enumerate(colors):
            if glitch_mask[i]:
                result.append(Color(
                    int(glitch_colors[i, 0]),
                    int(glitch_colors[i, 1]),
                    int(glitch_colors[i, 2])
                ))
            else:
                result.append(base_color)
        return result

class MetroEffect(Effect):
    """Metronome/beat visualization"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'bpm': 120,
            'flash_duration': 0.1
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        # Calculate beat timing
        beat_interval = 60.0 / self.parameters['bpm']
        beat_phase = (elapsed % beat_interval) / beat_interval
        
        # Flash on beat
        if beat_phase < self.parameters['flash_duration']:
            intensity = 1.0 - (beat_phase / self.parameters['flash_duration'])
        else:
            intensity = 0.3
        
        result = []
        for base_color in colors:
            result.append(Color(
                int(base_color.r * intensity),
                int(base_color.g * intensity),
                int(base_color.b * intensity)
            ))
        return result

class PowerEffect(Effect):
    """Power level bars"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'level': 0.5,
            'direction': 1  # 1 for left-to-right, -1 for right-to-left
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        # Calculate power bar
        fill_pixels = int(num_pixels * self.parameters['level'])
        
        result = []
        for i, base_color in enumerate(colors):
            if self.parameters['direction'] > 0:
                active = i < fill_pixels
            else:
                active = i >= (num_pixels - fill_pixels)
            
            mult = 1.0 if active else 0.1
            result.append(Color(
                int(base_color.r * mult),
                int(base_color.g * mult),
                int(base_color.b * mult)
            ))
        return result

class WalkingEffect(Effect):
    """Walking white lights that bounce back and forth with constantly changing speed"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'width': 1,  # Number of consecutive white lights
            'speed': 2.0,  # Base speed of movement
            'direction_change_time': 3.0  # Max time before switching direction
        }
        self.last_direction_change = 0.0
        self.current_direction = 1  # 1 for forward, -1 for backward
        self.next_change_time = np.random.uniform(0.5, self.parameters['direction_change_time'])
        self.position = 0.0
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        # Continuously randomize speed (changes every frame)
        current_speed = np.random.uniform(0.3, 2.5) * self.parameters['speed']
        
        # Check if it's time to change direction
        if elapsed - self.last_direction_change >= self.next_change_time:
            self.current_direction *= -1  # Reverse direction
            self.last_direction_change = elapsed
            # Bias toward forward direction - forward lasts much longer than backward
            if self.current_direction == 1:  # Now moving forward
                self.next_change_time = np.random.uniform(1.5, self.parameters['direction_change_time'])
            else:  # Now moving backward
                self.next_change_time = np.random.uniform(0.2, self.parameters['direction_change_time'] * 0.4)
        
        # Update position based on current direction and randomized speed
        dt = 0.016  # Approximate frame time
        self.position += self.current_direction * current_speed * dt
        
        # Clamp position to valid range
        max_pos = num_pixels - self.parameters['width']
        if self.position < 0:
            self.position = 0
            self.current_direction = 1
        elif self.position > max_pos:
            self.position = max_pos
            self.current_direction = -1
        
        start_pos = int(self.position)
        
        # Vectorized LED creation
        pixel_indices = np.arange(num_pixels)
        active_mask = (pixel_indices >= start_pos) & (pixel_indices < start_pos + self.parameters['width'])
        
        # Calculate brightness for active pixels
        if self.parameters['width'] > 2:
            # Vectorized brightness calculation
            group_center = start_pos + (self.parameters['width'] - 1) / 2
            distances = np.abs(pixel_indices - group_center)
            max_distance = (self.parameters['width'] - 1) / 2
            brightness = np.where(active_mask, 1.0 - (distances / max_distance) * 0.2, 0.0)
            brightness = np.clip(brightness, 0.0, 1.0)
        else:
            # Width 1 or 2 - full brightness for active pixels
            brightness = active_mask.astype(float)
        
        # Convert to Color objects
        result = []
        for i in range(num_pixels):
            if active_mask[i]:
                b = brightness[i]
                result.append(Color(int(255 * b), int(255 * b), int(255 * b)))
            else:
                result.append(Color(0, 0, 0))
        
        return result

class RainEffect(Effect):
    """Rain droplet effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 2.0,
            'density': 0.1
        }
        self.droplets = None
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        if self.droplets is None:
            self.droplets = np.zeros(num_pixels, dtype=np.float32)
        
        # Create new droplets
        new_drops = np.random.random(num_pixels) < self.parameters['density'] * 0.01
        self.droplets[new_drops] = 1.0
        
        # Move droplets down and fade
        self.droplets *= 0.95  # Fade
        
        result = []
        for i, base_color in enumerate(colors):
            drop_intensity = self.droplets[i]
            result.append(Color(
                min(255, int(base_color.r + drop_intensity * 100)),
                min(255, int(base_color.g + drop_intensity * 100)),
                min(255, int(base_color.b + drop_intensity * 255))
            ))
        return result

class RainbowEffect(Effect):
    """Rainbow color overlay"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 1.0,
            'density': 1.0  # How compressed the rainbow is
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        """Apply smooth rainbow across all pixels using simple HSV conversion"""
        result = []
        
        for i, color in enumerate(colors):
            # Calculate hue for this pixel
            hue = (i / len(colors) * self.parameters['density'] + elapsed * self.parameters['speed']) % 1.0
            
            # Simple HSV to RGB conversion
            import colorsys
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            
            if self.blend_mode == BlendMode.REPLACE:
                result.append(Color(int(r * 255), int(g * 255), int(b * 255)))
            else:
                # Multiply with original color
                result.append(Color(
                    int(color.r * r),
                    int(color.g * g), 
                    int(color.b * b)
                ))
        
        return result
    
    def _hsv_to_rgb_vectorized(self, h: np.ndarray, s: float, v: float) -> np.ndarray:
        """Vectorized HSV to RGB conversion"""
        h = h % 1.0
        c = v * s
        x = c * (1 - np.abs((h * 6) % 2 - 1))
        m = v - c
        
        # Create RGB arrays
        rgb = np.zeros((len(h), 3))
        
        # Vectorized conditions
        mask1 = h < 1/6
        mask2 = (h >= 1/6) & (h < 2/6)
        mask3 = (h >= 2/6) & (h < 3/6)
        mask4 = (h >= 3/6) & (h < 4/6)
        mask5 = (h >= 4/6) & (h < 5/6)
        mask6 = h >= 5/6
        
        rgb[mask1] = np.column_stack([c, x[mask1], np.zeros(np.sum(mask1))])
        rgb[mask2] = np.column_stack([x[mask2], c, np.zeros(np.sum(mask2))])
        rgb[mask3] = np.column_stack([np.zeros(np.sum(mask3)), c, x[mask3]])
        rgb[mask4] = np.column_stack([np.zeros(np.sum(mask4)), x[mask4], c])
        rgb[mask5] = np.column_stack([x[mask5], np.zeros(np.sum(mask5)), c])
        rgb[mask6] = np.column_stack([c, np.zeros(np.sum(mask6)), x[mask6]])
        
        return (rgb + m) * 255
    
    def _hsv_to_rgb(self, h: float, s: float, v: float) -> tuple:
        """Convert HSV to RGB"""
        h = h % 1.0
        c = v * s
        x = c * (1 - abs((h * 6) % 2 - 1))
        m = v - c
        
        if h < 1/6:
            r, g, b = c, x, 0
        elif h < 2/6:
            r, g, b = x, c, 0
        elif h < 3/6:
            r, g, b = 0, c, x
        elif h < 4/6:
            r, g, b = 0, x, c
        elif h < 5/6:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        
        return r + m, g + m, b + m

class EffectPipeline:
    """Main effects pipeline that combines base colors with effects"""
    
    def __init__(self, num_pixels: int):
        self.num_pixels = num_pixels
        self.base_layer = BaseColorLayer([Color(255, 255, 255)])  # Default white
        self.effects: List[Effect] = []
        self.output_buffer: List[Color] = [Color(0, 0, 0)] * num_pixels
    
    def render_frame(self, elapsed: float) -> List[Color]:
        """Render a single frame through the pipeline"""
        # 1. Get base colors
        colors = self.base_layer.get_colors(self.num_pixels, elapsed)
        
        # 2. Apply each enabled effect in order
        for effect in self.effects:
            if effect.enabled:
                colors = effect.apply(colors, elapsed)
        
        # 3. Store in output buffer and return
        self.output_buffer = colors
        return colors
    
    def set_base_colors(self, colors: List[Color], mode: TransitionMode = TransitionMode.STATIC, speed: float = 1.0):
        """Update base color layer"""
        self.base_layer.colors = colors
        self.base_layer.transition_mode = mode
        self.base_layer.transition_speed = speed
    
    def add_effect(self, effect: Effect) -> str:
        """Add an effect to the pipeline"""
        self.effects.append(effect)
        return effect.effect_id
    
    def remove_effect(self, effect_id: str) -> bool:
        """Remove an effect by ID"""
        for i, effect in enumerate(self.effects):
            if effect.effect_id == effect_id:
                del self.effects[i]
                return True
        return False
    
    def get_effect(self, effect_id: str) -> Optional[Effect]:
        """Get effect by ID"""
        for effect in self.effects:
            if effect.effect_id == effect_id:
                return effect
        return None
    
    def enable_effect(self, effect_id: str, enabled: bool) -> bool:
        """Enable/disable an effect"""
        effect = self.get_effect(effect_id)
        if effect:
            effect.enabled = enabled
            return True
        return False

class PipelineController:
    """High-level controller for the effects pipeline"""
    
    def __init__(self, num_pixels: int, pin: int = 18, force_simulation: bool = True):
        self.num_pixels = num_pixels
        self.pipeline = EffectPipeline(num_pixels)
        self.pixels = MockNeoPixel(pin, num_pixels, brightness=1.0, auto_write=True)
        self.running = False
        self.start_time = 0
    
    async def start(self):
        """Start the controller"""
        self.running = True
        self.start_time = time.time()
        print("Pipeline controller started")
    
    async def stop(self):
        """Stop the controller"""
        self.running = False
        self.pixels.deinit()
        print("Pipeline controller stopped")
    
    async def run_loop(self):
        """Main rendering loop"""
        while self.running:
            elapsed = time.time() - self.start_time
            
            # Render frame through pipeline
            colors = self.pipeline.render_frame(elapsed)
            
            # Update physical/mock LEDs
            for i, color in enumerate(colors):
                self.pixels[i] = (color.r, color.g, color.b)
            self.pixels.show()
            
            # 60 FPS
            await asyncio.sleep(1/60)
    
    # Convenience methods
    def set_solid_color(self, color: Color):
        """Set solid color base"""
        self.pipeline.set_base_colors([color], TransitionMode.STATIC)
    
    def set_rainbow(self, speed: float = 1.0):
        """Set rainbow cycling base"""
        rainbow_colors = []
        for i in range(12):  # 12 color rainbow
            hue = i / 12
            r, g, b = self._hsv_to_rgb(hue, 1.0, 1.0)
            rainbow_colors.append(Color(int(r * 255), int(g * 255), int(b * 255)))
        self.pipeline.set_base_colors(rainbow_colors, TransitionMode.FADE, speed)
    
    def add_breathing(self, speed: float = 1.0, min_intensity: float = 0.3, max_intensity: float = 1.0) -> str:
        """Add breathing effect"""
        effect = BreathingEffect()
        effect.update_parameters({'speed': speed, 'min_intensity': min_intensity, 'max_intensity': max_intensity})
        return self.pipeline.add_effect(effect)
    
    def add_strobe(self, frequency: float = 5.0) -> str:
        """Add strobe effect"""
        effect = StrobeEffect()
        effect.update_parameters({'frequency': frequency})
        return self.pipeline.add_effect(effect)
    
    def add_sparkle(self, density: float = 0.05) -> str:
        """Add sparkle effect"""
        effect = SparkleEffect()
        effect.update_parameters({'density': density})
        return self.pipeline.add_effect(effect)
    
    def add_wave(self, speed: float = 2.0) -> str:
        """Add wave effect"""
        effect = WaveEffect()
        effect.update_parameters({'speed': speed})
        return self.pipeline.add_effect(effect)
    
    def add_random_flash(self, frequency: float = 1.0) -> str:
        """Add random flash effect"""
        effect = RandomFlashEffect()
        effect.update_parameters({'frequency': frequency})
        return self.pipeline.add_effect(effect)
    
    def _hsv_to_rgb(self, h: float, s: float, v: float) -> tuple:
        """Convert HSV to RGB"""
        h = h % 1.0
        c = v * s
        x = c * (1 - abs((h * 6) % 2 - 1))
        m = v - c
        
        if h < 1/6:
            r, g, b = c, x, 0
        elif h < 2/6:
            r, g, b = x, c, 0
        elif h < 3/6:
            r, g, b = 0, c, x
        elif h < 4/6:
            r, g, b = 0, x, c
        elif h < 5/6:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        
        return r + m, g + m, b + m

async def recipe_demo1():
    """Demonstrate the pipeline system"""
    controller = PipelineController(100, force_simulation=True)
    await controller.start()
    
    try:
        # Start the rendering loop
        render_task = asyncio.create_task(controller.run_loop())
        
        print("🎨 Pipeline Demo Starting...")
        
        # Demo 1: Solid red with breathing
        print("Demo 1: Solid red + breathing")
        controller.set_solid_color(Color(255, 0, 0))
        breathing_id = controller.add_breathing(speed=0.5)
        await asyncio.sleep(5)
        
        # Demo 2: Change to blue, keep breathing
        print("Demo 2: Change to blue (breathing continues)")
        controller.set_solid_color(Color(0, 0, 255))
        await asyncio.sleep(5)
        
        # Demo 3: Add sparkle effect
        print("Demo 3: Add sparkle effect")
        sparkle_id = controller.add_sparkle(density=0.1)
        await asyncio.sleep(5)
        
        # Demo 4: Change to rainbow, keep all effects
        print("Demo 4: Change to rainbow (all effects continue)")
        controller.set_rainbow(speed=0.3)
        await asyncio.sleep(5)
        
        # Demo 5: Remove sparkle, add wave
        print("Demo 5: Remove sparkle, add wave")
        controller.pipeline.remove_effect(sparkle_id)
        wave_id = controller.add_wave(speed=1.0)
        await asyncio.sleep(5)
        
        # Demo 6: Add strobe
        print("Demo 6: Add strobe effect")
        strobe_id = controller.add_strobe(frequency=3.0)
        await asyncio.sleep(5)
        
        print("🎨 Pipeline demo completed!")
        
        render_task.cancel()
        
    except KeyboardInterrupt:
        print("\n🎨 Pipeline demo interrupted")
    finally:
        await controller.stop()

async def recipe_demo2():
    """Red-pink transition with breathing effect"""
    controller = PipelineController(100, force_simulation=True)
    await controller.start()
    
    try:
        # Start the rendering loop
        render_task = asyncio.create_task(controller.run_loop())
        
        print("🔴🩷 Recipe Demo 2: Red-Pink Transition + Breathing")
        
        # Set up red-pink fade transition with breathing
        red_pink_colors = [Color(255, 0, 0), Color(255, 192, 203)]
        controller.pipeline.set_base_colors(red_pink_colors, TransitionMode.FADE, speed=0.1)
        
        # Add breathing effect
        breathing_id = controller.add_breathing(speed=0.3, min_intensity=0.2)
        
        # Add random flash effect (2Hz white flashes)
        flash_id = controller.add_random_flash(frequency=2.0)
        
        print("Running red-pink fade with breathing for 15 seconds...")
        await asyncio.sleep(15)
        
        print("🔴🩷 Recipe Demo 2 completed!")
        
        render_task.cancel()
        
    except KeyboardInterrupt:
        print("\n🔴🩷 Recipe Demo 2 interrupted")
    finally:
        await controller.stop()

async def main():
    parser = argparse.ArgumentParser(description='Layered Effects Pipeline Demo')
    parser.add_argument('--pixels', type=int, default=100, help='Number of pixels')
    parser.add_argument('--recipe', choices=['1', '2'], default='1', help='Which recipe demo to run')
    
    args = parser.parse_args()
    
    print(f"🎨 Layered Effects Pipeline Demo")
    print(f"  Pixels: {args.pixels}")
    print(f"  Recipe: {args.recipe}")
    print(f"  Architecture: Base Layer + Effect Pipeline")
    
    try:
        if args.recipe == '1':
            await recipe_demo1()
        elif args.recipe == '2':
            await recipe_demo2()
    except Exception as e:
        if "GUI window was closed" in str(e):
            print("\n🎨 GUI window closed")
        else:
            print(f"\n🎨 Demo error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
