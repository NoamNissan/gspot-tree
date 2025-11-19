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
from dataclasses import dataclass
from .constants import NEOPIXEL_SLEEP_RATE

@dataclass
class TreeStructure:
    """Tree LED structure with rings and branches"""
    rings: List[List[int]]     # rings[ring_idx] = [led_indices...]
    branches: List[List[int]]  # branches[branch_idx] = [led_indices...]
    
    def __post_init__(self):
        """Calculate skewed branches after initialization"""
        self.skewed_branches = self._calculate_skewed_branches()
    
    def _calculate_skewed_branches(self) -> List[List[int]]:
        """Create skewed branch groupings"""
        if not self.branches:
            return []
        
        # Find max branch length
        max_length = max(len(branch) for branch in self.branches)
        skewed = []
        
        for led_pos in range(max_length):
            skewed_group = []
            for branch_idx, branch in enumerate(self.branches):
                # Take LED at position led_pos from branch branch_idx
                if led_pos < len(branch):
                    skewed_group.append(branch[led_pos])
            if skewed_group:
                skewed.append(skewed_group)
        
        return skewed

# Global pipeline configuration
PIPELINE_FPS = 240  # 240 FPS for very smooth effects
from .led_controller import Color
from .colors_array import Colors

class TransitionMode(Enum):
    STATIC = "static"
    CYCLE = "cycle"
    FADE = "fade"
    RANDOM = "random"
    PAIR_BLEND = "pair_blend"

class BlendMode(Enum):
    REPLACE = "replace"
    MULTIPLY = "multiply"
    ADD = "add"
    OVERLAY = "overlay"

@dataclass
class BaseColorLayer:
    """Base color layer that provides the foundation colors"""
    colors: Colors
    transition_mode: TransitionMode = TransitionMode.STATIC
    transition_speed: float = 1.0
    current_position: float = 0.0
    
    def get_colors(self, num_pixels: int, elapsed: float) -> Colors:
        """Get base colors for all pixels"""
        if not self.colors:
            return Colors(num_pixels)
        
        if self.transition_mode == TransitionMode.STATIC:
            # Pick one random color
            color = random.choice(self.colors)
            color_list = [color] * num_pixels
            return Colors(color_list)
        
        elif self.transition_mode == TransitionMode.CYCLE:
            # Cycle through colors over time
            self.current_position = (elapsed * self.transition_speed) % len(self.colors)
            color_index = int(self.current_position)
            color_list = [self.colors[color_index]] * num_pixels
            return Colors(color_list)
        
        elif self.transition_mode == TransitionMode.FADE:
            # Smooth fade between colors
            self.current_position = (elapsed * self.transition_speed) % len(self.colors)
            color1_idx = int(self.current_position) % len(self.colors)
            color2_idx = (color1_idx + 1) % len(self.colors)
            blend_factor = self.current_position - int(self.current_position)
            
            blended_color = self.colors[color1_idx].blend(self.colors[color2_idx], blend_factor)
            color_list = [blended_color] * num_pixels
            return Colors(color_list)
        
        elif self.transition_mode == TransitionMode.PAIR_BLEND:
            # Alternating LEDs blend: even LEDs go color1→color2, odd LEDs go color2→color1
            if len(self.colors) < 2:
                color_list = [self.colors[0]] * num_pixels
                return Colors(color_list)
            
            self.current_position = (elapsed * self.transition_speed) % 2
            blend_factor = self.current_position if self.current_position < 1 else 2 - self.current_position
            
            color_list = []
            for i in range(num_pixels):
                if i % 2 == 0:
                    color_list.append(self.colors[0].blend(self.colors[1], blend_factor))
                else:
                    color_list.append(self.colors[1].blend(self.colors[0], blend_factor))
            return Colors(color_list)
        
        else:  # RANDOM
            # Random color selection
            random.seed(int(elapsed * self.transition_speed))
            color = random.choice(self.colors)
            color_list = [color] * num_pixels
            return Colors(color_list)

class Effect:
    """Base class for all effects"""
    
    def __init__(self, effect_id: str = None):
        self.effect_id = effect_id or str(uuid.uuid4())
        self.enabled = True
        self.parameters = {}
        self.blend_mode = BlendMode.MULTIPLY
        self.internal_state = {}
        self.start_time = time.time()
    
    def apply(self, colors: Colors, elapsed: float) -> Colors:
        """Apply effect to color array"""
        if not self.enabled:
            return colors
        return self._apply_effect(colors, elapsed)
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        """Override this in subclasses"""
        return colors
    
    def update_parameters(self, parameters: Dict[str, Any]):
        """Update effect parameters, resolving any Range objects"""
        from .recipe_manager import FloatRange, ChoiceRange
        resolved = {}
        for key, value in parameters.items():
            while isinstance(value, (FloatRange, ChoiceRange)):
                value = value.resolve()
            resolved[key] = value
        self.parameters.update(resolved)

class BreathingEffect(Effect):
    """Breathing intensity effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 1.0,
            'min_intensity': 0.3,
            'max_intensity': 1.0
        }
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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

class FadeToColorEffect(Effect):
    """Fade from current colors to target color over time"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'target_color': Color(0, 0, 0),  # Target color to fade to
            'duration': 2.0,  # Duration in seconds
            'start_time': None  # Will be set when effect starts
        }
        self.initial_colors = None
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        # Initialize start time and capture initial colors
        if self.parameters['start_time'] is None:
            self.parameters['start_time'] = elapsed
            # Convert numpy types to regular ints to avoid overflow
            self.initial_colors = [Color(int(colors[i].r), int(colors[i].g), int(colors[i].b)) for i in range(len(colors))]
        
        # Calculate fade progress (0.0 to 1.0)
        fade_elapsed = elapsed - self.parameters['start_time']
        progress = min(fade_elapsed / self.parameters['duration'], 1.0)
        
        # If fade is complete, return target color and stop
        if progress >= 1.0:
            target = self.parameters['target_color']
            result = Colors(len(colors))
            for i in range(len(colors)):
                result[i] = Color(target.r, target.g, target.b)
            return result
        
        # Interpolate between initial colors and target color
        target = self.parameters['target_color']
        result = Colors(len(colors))
        
        for i in range(len(colors)):
            initial = self.initial_colors[i]
            # Linear interpolation - no numpy clipping needed since we converted to int
            r = int(initial.r + (target.r - initial.r) * progress)
            g = int(initial.g + (target.g - initial.g) * progress)
            b = int(initial.b + (target.b - initial.b) * progress)
            result[i] = Color(r, g, b)
        
        return result

class StrobeEffect(Effect):
    """Strobe flashing effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'frequency': 5.0,
            'duty_cycle': 0.1  # 10% on, 90% off
        }
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        cycle_time = 1.0 / self.parameters['frequency']
        phase = (elapsed % cycle_time) / cycle_time
        
        if phase < self.parameters['duty_cycle']:
            # Strobe on - full intensity
            return colors
        else:
            # Strobe off - dark
            return Colors(len(colors))

class ColorStrobeEffect(Effect):
    """Color strobe effect - accepts any color"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'frequency': 10.0,  # Hz - strobes per second
            'color': Color(255, 255, 255)  # Default white, can be overridden
        }

    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        cycle_time = 1.0 / self.parameters['frequency']
        phase = (elapsed % cycle_time) / cycle_time
        
        if phase < 0.5:  # 50% duty cycle - on for half the cycle
            # Strobe on - use specified color
            return [self.parameters['color']] * len(colors)
        else:
            # Strobe off - black
            return Colors(len(colors))

class RingRippleEffect(Effect):
    """Ring ripple effect using tree structure"""
    
    def __init__(self, tree_structure: TreeStructure = None, mask: List[int] = None, effect_id: str = None):
        super().__init__(effect_id)
        self.tree_structure = tree_structure
        self.mask = mask or list(range(len(tree_structure.rings))) if tree_structure else []
        self.parameters = {
            'speed': 2.0,
            'color': Color(0, 255, 255),
            'fade_time': 0.5,
            'direction': 'out'
        }
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        if not self.tree_structure:
            return colors

        speed = self.parameters['speed']
        fade_time = self.parameters['fade_time']
        direction = self.parameters['direction']
        effect_color = self.parameters['color']
        
        cycle_time = len(self.mask) / speed
        phase = (elapsed % cycle_time) / cycle_time
        
        if direction == 'in':
            phase = 1.0 - phase
            
        current_ring = phase * len(self.mask)
        result = colors.copy()
        
        for i, ring_idx in enumerate(self.mask):
            if ring_idx < len(self.tree_structure.rings):
                ring_distance = abs(i - current_ring)
                
                if ring_distance < fade_time * len(self.mask):
                    intensity = max(0, 1.0 - ring_distance / (fade_time * len(self.mask)))
                    
                    for led_idx in self.tree_structure.rings[ring_idx]:
                        if led_idx < len(result):
                            # Additive blending with overflow protection
                            result[led_idx] = Color(
                                min(255, int(result[led_idx].r) + int(effect_color.r * intensity)),
                                min(255, int(result[led_idx].g) + int(effect_color.g * intensity)),
                                min(255, int(result[led_idx].b) + int(effect_color.b * intensity))
                            )
        
        return result

class BranchSweepEffect(Effect):
    """Branch sweep effect using tree structure"""
    
    def __init__(self, tree_structure: TreeStructure = None, mask: List[int] = None, effect_id: str = None):
        super().__init__(effect_id)
        self.tree_structure = tree_structure
        self.mask = mask or list(range(len(tree_structure.branches))) if tree_structure else []
        self.parameters = {
            'speed': 1.0,
            'color': Color(255, 100, 0),
            'width': 3,
            'direction': 'cw'
        }
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        if not self.tree_structure:
            return colors
            
        speed = self.parameters['speed']
        width = self.parameters['width']
        direction = self.parameters['direction']
        effect_color = self.parameters['color']
        
        cycle_time = 1.0 / speed
        phase = (elapsed % cycle_time) / cycle_time
        
        if direction == 'ccw':
            phase = 1.0 - phase
            
        current_branch = phase * len(self.mask)
        result = colors.copy()
        
        for i in range(width):
            branch_pos = int((current_branch + i) % len(self.mask))
            branch_idx = self.mask[branch_pos]
            
            if branch_idx < len(self.tree_structure.branches):
                center_distance = abs(i - width // 2)
                intensity = max(0.3, 1.0 - center_distance / (width / 2))
                
                for led_idx in self.tree_structure.branches[branch_idx]:
                    if led_idx < len(result):
                        # Additive blending
                        result[led_idx] = Color(
                            min(255, result[led_idx].r + int(effect_color.r * intensity)),
                            min(255, result[led_idx].g + int(effect_color.g * intensity)),
                            min(255, result[led_idx].b + int(effect_color.b * intensity))
                        )
        
        return result

class RainbowRingsEffect(Effect):
    """Rainbow colors emanate through rings"""
    
    def __init__(self, tree_structure: TreeStructure = None, mask: List[int] = None, effect_id: str = None):
        super().__init__(effect_id)
        self.tree_structure = tree_structure
        self.mask = mask or list(range(len(tree_structure.rings))) if tree_structure else []
        self.parameters = {
            'speed': 1.0,
            'direction': 'outward',  # 'outward' or 'inward'
            'hue_spread': 1.0  # How much hue changes between rings
        }
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        if not self.tree_structure:
            return colors
            
        speed = self.parameters['speed']
        direction = self.parameters['direction']
        hue_spread = self.parameters['hue_spread']
        
        result = colors.copy()
        
        for i, ring_idx in enumerate(self.mask):
            if ring_idx < len(self.tree_structure.rings):
                # Calculate hue based on ring position and time
                if direction == 'inward':
                    ring_pos = len(self.mask) - 1 - i
                else:
                    ring_pos = i
                
                hue = (elapsed * speed + ring_pos * hue_spread / len(self.mask)) % 1.0
                
                # Convert HSV to RGB
                import colorsys
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                ring_color = Color(int(r * 255), int(g * 255), int(b * 255))
                
                for led_idx in self.tree_structure.rings[ring_idx]:
                    if led_idx < len(result):
                        # Additive blending
                        result[led_idx] = Color(
                            min(255, result[led_idx].r + ring_color.r),
                            min(255, result[led_idx].g + ring_color.g),
                            min(255, result[led_idx].b + ring_color.b)
                        )
        
        return result

class RainbowBranchesEffect(Effect):
    """Rainbow colors cascade from branch to branch"""
    
    def __init__(self, tree_structure: TreeStructure = None, mask: List[int] = None, effect_id: str = None):
        super().__init__(effect_id)
        self.tree_structure = tree_structure
        self.mask = mask or list(range(len(tree_structure.branches))) if tree_structure else []
        self.parameters = {
            'speed': 1.0,
            'direction': 'cw',  # 'cw' or 'ccw'
            'hue_spread': 1.0  # How much hue changes between branches
        }
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        if not self.tree_structure:
            return colors
            
        speed = self.parameters['speed']
        direction = self.parameters['direction']
        hue_spread = self.parameters['hue_spread']
        
        result = colors.copy()
        
        for i, branch_idx in enumerate(self.mask):
            if branch_idx < len(self.tree_structure.branches):
                # Calculate hue based on branch position and time
                if direction == 'ccw':
                    branch_pos = len(self.mask) - 1 - i
                else:
                    branch_pos = i
                
                hue = (elapsed * speed + branch_pos * hue_spread / len(self.mask)) % 1.0
                
                # Convert HSV to RGB
                import colorsys
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                branch_color = Color(int(r * 255), int(g * 255), int(b * 255))
                
                for led_idx in self.tree_structure.branches[branch_idx]:
                    if led_idx < len(result):
                        # Additive blending
                        result[led_idx] = Color(
                            min(255, result[led_idx].r + branch_color.r),
                            min(255, result[led_idx].g + branch_color.g),
                            min(255, result[led_idx].b + branch_color.b)
                        )
        
        return result

class RainbowVortexEffect(Effect):
    """Each ring contains full rainbow and spins at different speeds"""
    
    def __init__(self, tree_structure: TreeStructure = None, mask: List[int] = None, effect_id: str = None):
        super().__init__(effect_id)
        self.tree_structure = tree_structure
        self.mask = mask or list(range(len(tree_structure.rings))) if tree_structure else []
        self.parameters = {
            'base_speed': 1.0,
            'speed_ratio': 1.5,  # How much faster inner rings are
            'direction': 'cw',  # 'cw' or 'ccw'
            'alternating': False  # If true, rings alternate direction
        }
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        if not self.tree_structure:
            return colors
            
        base_speed = self.parameters['base_speed']
        speed_ratio = self.parameters['speed_ratio']
        direction = self.parameters['direction']
        alternating = self.parameters['alternating']
        
        result = colors.copy()
        
        for i, ring_idx in enumerate(self.mask):
            if ring_idx < len(self.tree_structure.rings):
                ring_leds = self.tree_structure.rings[ring_idx]
                if not ring_leds:
                    continue
                
                # Calculate individual speed for each ring
                ring_speed = base_speed * (speed_ratio ** i)
                
                # Apply direction and alternating
                if direction == 'ccw':
                    ring_speed = -ring_speed
                if alternating and i % 2 == 1:  # Odd rings reverse direction
                    ring_speed = -ring_speed
                
                # Each LED in ring gets different hue based on position + time
                for j, led_idx in enumerate(ring_leds):
                    if led_idx < len(result):
                        # Hue based on LED position in ring + spinning time offset
                        hue = (j / len(ring_leds) + elapsed * ring_speed) % 1.0
                        
                        # Convert HSV to RGB
                        import colorsys
                        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                        led_color = Color(int(r * 255), int(g * 255), int(b * 255))
                        
                        # Additive blending with overflow protection
                        result[led_idx] = Color(
                            min(255, int(result[led_idx].r) + led_color.r),
                            min(255, int(result[led_idx].g) + led_color.g),
                            min(255, int(result[led_idx].b) + led_color.b)
                        )
        
        return result

class RainbowBranchesSkewedEffect(Effect):
    """Rainbow colors cascade through skewed branch groupings"""
    
    def __init__(self, tree_structure: TreeStructure = None, mask: List[int] = None, effect_id: str = None):
        super().__init__(effect_id)
        self.tree_structure = tree_structure
        self.mask = mask or list(range(len(tree_structure.skewed_branches))) if tree_structure else []
        self.parameters = {
            'speed': 1.0,
            'direction': 'cw',  # 'cw' or 'ccw'
            'hue_spread': 1.0  # How much hue changes between skewed groups
        }
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        if not self.tree_structure:
            return colors
            
        speed = self.parameters['speed']
        direction = self.parameters['direction']
        hue_spread = self.parameters['hue_spread']
        
        result = colors.copy()
        
        for i, skewed_idx in enumerate(self.mask):
            if skewed_idx < len(self.tree_structure.skewed_branches):
                # Calculate hue based on skewed group position and time
                if direction == 'ccw':
                    group_pos = len(self.mask) - 1 - i
                else:
                    group_pos = i
                
                hue = (elapsed * speed + group_pos * hue_spread / len(self.mask)) % 1.0
                
                # Convert HSV to RGB
                import colorsys
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                group_color = Color(int(r * 255), int(g * 255), int(b * 255))
                
                for led_idx in self.tree_structure.skewed_branches[skewed_idx]:
                    if led_idx < len(result):
                        # Additive blending
                        result[led_idx] = Color(
                            min(255, result[led_idx].r + group_color.r),
                            min(255, result[led_idx].g + group_color.g),
                            min(255, result[led_idx].b + group_color.b)
                        )
        
        return result

class RotationEffect(Effect):
    """General rotation effect - rotates any visualization around the LED strip"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 0.0,  # Rotation speed (pixels per second, 0 = no rotation)
            'step_size': 2,  # Number of LEDs to rotate by each step (default: 2)
            'led_pairing': True,  # Use LED pairs instead of single LEDs (default: True)
        }
        self.rotation_offset = 0.0  # Current rotation position (float for smooth movement)
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        speed = self.parameters.get('speed', 0.0)
        step_size = self.parameters.get('step_size', 2)
        led_pairing = self.parameters.get('led_pairing', True)
        if speed == 0.0 or not colors:
            return colors
        
        # Update rotation position
        self.rotation_offset += speed * (1.0 / 240.0)  # Assuming 240 FPS
        self.rotation_offset = self.rotation_offset % len(colors)
        
        # Apply rotation with step_size
        start_index = int(self.rotation_offset / step_size) * step_size % len(colors)
        rotated = []
        
        for i in range(len(colors)):
            if led_pairing:
                # Use pairs: LEDs 0,1 get same color, 2,3 get same color, etc.
                pair_idx = i // 2
                source_pair_idx = (pair_idx + start_index // 2) % (len(colors) // 2)
                source_index = source_pair_idx * 2 + (i % 2)
            else:
                source_index = (i + start_index) % len(colors)
            rotated.append(colors[source_index])
        
        return rotated

class SparkleEffect(Effect):
    """Random sparkle effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'density': 0.05,  # 5% of pixels sparkle
            'brightness': 1.0,
            'period': 0.0,  # Seconds between sparkle bursts (0 = always sparkle)
            'duration': 0.0  # Seconds to sparkle after period (0 = single frame)
        }
        self.last_sparkle_time = 0.0
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        period = self.parameters.get('period', 0.0)
        duration = self.parameters.get('duration', 0.0)
        
        if period > 0:
            time_since_last = elapsed - self.last_sparkle_time
            
            # Check if we're in sparkle burst window
            if time_since_last < duration:
                # Currently sparkling
                pass
            elif time_since_last < period:
                # Waiting for next burst
                return colors
            else:
                # Start new burst
                self.last_sparkle_time = elapsed
        
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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

class CircleScanEffect(Effect):
    """Circular scanner effect that wraps around"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 2.0,
            'width': 5
        }
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        # Calculate scanner position (wraps around instead of bouncing)
        cycle_time = 2.0 / self.parameters['speed']
        phase = (elapsed % cycle_time) / cycle_time
        scanner_pos = phase * (num_pixels - 1)  # 0 to (num_pixels - 1), same as ScanEffect
        
        # Create scanner beam (exact same as ScanEffect)
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

class ScanEffect(Effect):
    """Scanner/cylon eye effect"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 2.0,
            'width': 5
        }
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        # Create smooth fading marching pattern
        offset = elapsed * self.parameters['speed'] * self.parameters['size']
        positions = np.arange(num_pixels) + offset
        phase = (positions / self.parameters['size']) % 2
        
        result = []
        for i, base_color in enumerate(colors):
            # Smooth sine wave between 0.5 and 1.5
            brightness = 1.0 + 0.5 * np.sin(phase[i] * np.pi)
            result.append(Color(
                min(255, int(base_color.r * brightness)),
                min(255, int(base_color.g * brightness)),
                min(255, int(base_color.b * brightness))
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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

class PinkCompressor(Effect):
    """Changes all colors into shades of pink"""

    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters['reverse'] = False

    def _apply_effect(self, colors: Colors, elapsed: float) -> List[Color]:
        import colorsys

        result = []
        for c in colors:
            #r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
##            rgb_to_hsv
            h,s,v = colorsys.rgb_to_hsv(c.r, c.g, c.b)
            h = h/4 + 0.75
            if self.parameters['reverse'] is True:
                h = 0.75 - h
            
            
            r,g,b = colorsys.hsv_to_rgb(h, s, v)
            result.append(Color(r,g,b))
            

        return result

class WaterEffect(Effect):
    """Water ripple simulation"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 1.0,
            'ripples': 3
        }
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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

class BlackoutEffect(Effect):
    """Pixels turn off and return in random order"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'shutdown_mode': 'sequential',
            'restore_mode': 'sequential',
            'shutdown_duration': 3.0,
            'restore_duration': 3.0,
            'hold_duration': 0.5,
            'on_duration': 0.0
        }
        self.pixel_order = None
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        num_pixels = len(colors)
        if num_pixels == 0:
            return colors
        
        if self.pixel_order is None or len(self.pixel_order) != num_pixels:
            self.pixel_order = list(range(num_pixels))
            random.shuffle(self.pixel_order)
        
        shutdown_dur = self.parameters['shutdown_duration']
        hold_dur = self.parameters['hold_duration']
        restore_dur = self.parameters['restore_duration']
        on_dur = self.parameters['on_duration']
        cycle_dur = shutdown_dur + hold_dur + restore_dur + on_dur
        phase_time = elapsed % cycle_dur
        
        result = []
        for i, base_color in enumerate(colors):
            pixel_pos = self.pixel_order.index(i)
            
            if phase_time < shutdown_dur:
                if self.parameters['shutdown_mode'] == 'instant':
                    active = False
                else:
                    shutdown_progress = phase_time / shutdown_dur
                    active = pixel_pos >= (shutdown_progress * num_pixels)
            elif phase_time < shutdown_dur + hold_dur:
                active = False
            elif phase_time < shutdown_dur + hold_dur + restore_dur:
                restore_time = phase_time - shutdown_dur - hold_dur
                if self.parameters['restore_mode'] == 'instant':
                    active = True
                else:
                    restore_progress = restore_time / restore_dur
                    active = pixel_pos < (restore_progress * num_pixels)
            else:
                active = True
            
            if active:
                result.append(base_color)
            else:
                result.append(Color(0, 0, 0))
        
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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
                min(255, int(base_color.r + drop_intensity * 50)),
                min(255, int(base_color.g + drop_intensity * 50)),
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
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
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

class RingColorsEffect(Effect):
    """Each ring in different color"""
    
    def __init__(self, tree_structure=None):
        super().__init__()
        self.tree_structure = tree_structure
        # Ring colors: Red, Green, Blue, Yellow, Magenta
        self.ring_colors = [
            Color(255, 0, 0),    # Ring 0: Red
            Color(0, 255, 0),    # Ring 1: Green  
            Color(0, 0, 255),    # Ring 2: Blue
            Color(255, 255, 0),  # Ring 3: Yellow
            Color(255, 0, 255)   # Ring 4: Magenta
        ]
    
    def _apply_effect(self, colors: Colors, elapsed: float) -> Colors:
        """Apply ring colors"""
        if not self.tree_structure:
            return colors
            
        result = Colors(len(colors))  # Start with black
        
        # Color each ring
        for ring_idx, ring_leds in enumerate(self.tree_structure.rings):
            if ring_idx < len(self.ring_colors):
                ring_color = self.ring_colors[ring_idx]
                for led_idx in ring_leds:
                    if led_idx < len(result):
                        result[led_idx] = ring_color
        
        return result


class SpectrumEffect(Effect):
    """LedFx-style spectrum analyzer effect"""
    
    def __init__(self, num_leds: int = 100, color: Color = Color(0, 0, 255), **kwargs):
        super().__init__()
        self.num_leds = num_leds
        self.color = color
        self.num_bands = 8
        self.band_width = num_leds // self.num_bands
        
    def _apply_effect(self, colors, elapsed: float):
        import colorsys
        import numpy as np
        
        result = Colors(len(colors))
        
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
    
    def __init__(self, num_leds: int = 100, **kwargs):
        super().__init__()
        self.num_leds = num_leds
        
    def _apply_effect(self, colors, elapsed: float):
        import numpy as np
        
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
    
    def __init__(self, num_leds: int = 100, **kwargs):
        super().__init__()
        self.num_leds = num_leds
        
    def _apply_effect(self, colors, elapsed: float):
        import colorsys
        import numpy as np
        
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
    
    def __init__(self, num_leds: int = 100, **kwargs):
        super().__init__()
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
    
    def __init__(self, num_leds: int = 100, **kwargs):
        super().__init__()
        self.num_leds = num_leds
        self.num_bars = 10
        self.bar_width = num_leds // self.num_bars
        
    def _apply_effect(self, colors, elapsed: float):
        import colorsys
        import numpy as np
        
        result = Colors(len(colors))
        
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


class EffectPipeline:
    """Main effects pipeline that combines base colors with effects"""
    
    def __init__(self, num_pixels: int):
        self.num_pixels = num_pixels
        self.base_layer = BaseColorLayer([Color(255, 255, 255)])  # Default white
        self.effects: List[Effect] = []
        self.output_buffer: Colors = Colors(num_pixels)
    
    def render_frame(self, elapsed: float) -> Colors:
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
    
    def set_base_colors(self, colors: Colors, mode: TransitionMode = TransitionMode.STATIC, speed: float = 1.0):
        """Update base color layer"""
        # Ensure all parameters are resolved (not Range objects)
        from .recipe_manager import ChoiceRange, FloatRange
        
        resolved_colors = colors
        while isinstance(resolved_colors, ChoiceRange):
            resolved_colors = resolved_colors.resolve()
            
        resolved_mode = mode
        while isinstance(resolved_mode, ChoiceRange):
            resolved_mode = resolved_mode.resolve()
            
        resolved_speed = speed
        while isinstance(resolved_speed, (FloatRange, ChoiceRange)):
            resolved_speed = resolved_speed.resolve()
        
        self.base_layer.colors = resolved_colors
        self.base_layer.transition_mode = resolved_mode
        self.base_layer.transition_speed = resolved_speed
    
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

    GRB = 1
    RGB = 0
    
    def __init__(self, num_pixels: int, pin: int = 18, force_simulation: bool = False, tree_structure: TreeStructure = None):
        self.num_pixels = num_pixels
        self.pipeline = EffectPipeline(num_pixels)
        self.tree_structure = tree_structure
        
        # Import mock neopixel only if simulation is requested
        if force_simulation:
            from . import mock_neopixel  # This will monkey patch neopixel module
            print("Using LED simulation mode")
            import neopixel  # Import after monkey patching
            self.pixels = neopixel.NeoPixel(None, num_pixels, brightness=1.0, auto_write=False, tree_structure=tree_structure)
            self.simulation = True
            self.color_order = self.RGB
            self.sleep_rate = 1/1200
        else:
            # Now import neopixel - will be real or mock depending on above
            print("Using real LED hardware")
            import neopixel
            import board
            self.pixels = neopixel.NeoPixel(getattr(board, f'D{pin}'), num_pixels, brightness=1.0, auto_write=False, pixel_order=neopixel.RGB)
            self.simulation = False
            self.color_order = self.GRB
            self.sleep_rate = NEOPIXEL_SLEEP_RATE # 60 FPS
        
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
            try:
                elapsed = time.time() - self.start_time

                # Render frame through pipeline
                colors = self.pipeline.render_frame(elapsed)

                # Update physical/mock LEDs
                for i, color in enumerate(colors):
                    self.pixels[i] = (color.r, color.g, color.b)
                self.pixels.show()

                # Use global FPS setting
                await asyncio.sleep(self.sleep_rate)
            except KeyboardInterrupt as e:
                print(f"🛑 User interrupted render loop: {e}")
                self.running = False
                return
            except EOFError as e:
                print(f"🛑 EOF in render loop: {e}")
                self.running = False
                return
            except Exception as e:
                # Raise unexpected exceptions
                print(f"❌ ASYNCIO THREAD EXCEPTION: {e}")
                print(f"❌ Exception type: {type(e)}")
                import traceback
                traceback.print_exc()
                print("❌ STOPPING PROGRAM DUE TO EXCEPTION")
                self.running = False
                raise  # Re-raise to crash the program
    
    def trigger_strobe_sync(self, frequency: float, duration: float, color: Color = Color(255, 255, 255), duty_cycle: float = 0.2):
        """Synchronous direct strobe - use fill method with frequency compensation"""
        print(f"🔥 Starting {frequency}Hz {color} strobe for {duration}s (duty: {duty_cycle*100:.0f}%)...")
        
        # Non-linear compensation - more aggressive at higher frequencies
        # At 1Hz: ~0%, At 35Hz: ~25%
        if frequency <= 1:
            compensation_factor = 0
        else:
            # Quadratic growth: more compensation needed at higher frequencies
            normalized_freq = (frequency - 1) / 34  # 0 to 1 for 1Hz to 35Hz
            compensation_factor = min(0.25, normalized_freq ** 1.2 * 0.25)
        
        adjusted_frequency = frequency / (1 - compensation_factor)
        
        print(f"🔧 Compensation: {compensation_factor*100:.1f}% -> {adjusted_frequency:.1f} Hz internal")
        
        start_time = time.time()
        period = 1.0 / adjusted_frequency
        on_time = period * duty_cycle
        off_time = period * (1 - duty_cycle)
        cycle_count = 0
        
        # Try fill method first (should be fastest)
        try:
            color_tuple = (color.r, color.g, color.b)
            black_tuple = (0, 0, 0)
            
            while time.time() - start_time < duration:
                # Color ON
                self.pixels.fill(color_tuple)
                self.pixels.show()
                time.sleep(on_time)
                
                # Color OFF (black)
                self.pixels.fill(black_tuple)
                self.pixels.show()
                time.sleep(off_time)
                
                cycle_count += 1
                
        except AttributeError:
            print("Fill method not available, using slice assignment")
            # Fallback to slice assignment with pre-allocated arrays
            color_array = [(color.r, color.g, color.b)] * self.num_pixels
            black_array = [(0, 0, 0)] * self.num_pixels
            
            while time.time() - start_time < duration:
                self.pixels[:] = color_array
                self.pixels.show()
                time.sleep(on_time)
                
                self.pixels[:] = black_array
                self.pixels.show()
                time.sleep(off_time)
                
                cycle_count += 1
        
        elapsed = time.time() - start_time
        actual_freq = cycle_count / elapsed
        print(f"🔥 Strobe complete: {cycle_count} cycles in {elapsed:.2f}s = {actual_freq:.1f} Hz")

    async def trigger_strobe(self, frequency: float, duration: float, color: Color = Color(255, 255, 255), duty_cycle: float = 0.15):
        """Async wrapper for sync strobe"""
        self.trigger_strobe_sync(frequency, duration, color, duty_cycle)

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
    
    def add_fade_to_color(self, target_color: Color, duration: float = 2.0) -> str:
        """Add fade to color effect"""
        effect = FadeToColorEffect()
        effect.update_parameters({'target_color': target_color, 'duration': duration})
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
    
    def add_ring_ripple(self, mask: List[int] = None, speed: float = 2.0, color: Color = Color(0, 255, 255)) -> str:
        """Add ring ripple effect"""
        effect = RingRippleEffect(self.tree_structure, mask)
        effect.update_parameters({'speed': speed, 'color': color})
        return self.pipeline.add_effect(effect)
    
    def add_branch_sweep(self, mask: List[int] = None, speed: float = 1.0, color: Color = Color(255, 100, 0)) -> str:
        """Add branch sweep effect"""
        effect = BranchSweepEffect(self.tree_structure, mask)
        effect.update_parameters({'speed': speed, 'color': color})
        return self.pipeline.add_effect(effect)
    
    def add_ring_ripple(self, mask: List[int] = None, speed: float = 2.0, color: Color = Color(0, 255, 255)) -> str:
        """Add ring ripple effect"""
        effect = RingRippleEffect(self.tree_structure, mask)
        effect.update_parameters({'speed': speed, 'color': color})
        return self.pipeline.add_effect(effect)
    
    def add_branch_sweep(self, mask: List[int] = None, speed: float = 1.0, color: Color = Color(255, 100, 0)) -> str:
        """Add branch sweep effect"""
        effect = BranchSweepEffect(self.tree_structure, mask)
        effect.update_parameters({'speed': speed, 'color': color})
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
    controller = PipelineController(100, force_simulation=False)
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
    controller = PipelineController(100, force_simulation=False)
    await controller.start()
    
    try:
        # Start the rendering loop
        render_task = asyncio.create_task(controller.run_loop())
        
        print("🔴🩷 Recipe Demo 2: Red-Pink Transition + Breathing")
        
        # Set up red-pink fade transition with breathing
        #red_pink_colors = [Color(255, 0, 0), Color(255, 192, 203)]
        red_pink_colors = [Color(255, 0, 0), Color(150, 0, 150)]
        
        controller.pipeline.set_base_colors(red_pink_colors, TransitionMode.FADE, speed=0.01)
        
        # Add breathing effect
        breathing_id = controller.add_breathing(speed=0.1, min_intensity=0.1, max_intensity=1)
        
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
