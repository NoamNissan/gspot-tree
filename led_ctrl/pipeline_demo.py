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

class RainbowEffect(Effect):
    """Rainbow color overlay"""
    
    def __init__(self, effect_id: str = None):
        super().__init__(effect_id)
        self.parameters = {
            'speed': 1.0,
            'density': 1.0  # How compressed the rainbow is
        }
    
    def _apply_effect(self, colors: List[Color], elapsed: float) -> List[Color]:
        # Calculate rainbow hues for all pixels at once
        pixel_indices = np.arange(len(colors))
        hues = (pixel_indices / len(colors) * self.parameters['density'] + elapsed * self.parameters['speed']) % 1.0
        
        # Convert HSV to RGB vectorized
        rainbow_rgb = self._hsv_to_rgb_vectorized(hues, 1.0, 1.0)
        
        if self.blend_mode == BlendMode.REPLACE:
            # Replace with rainbow colors
            return [Color(int(rgb[0]), int(rgb[1]), int(rgb[2])) for rgb in rainbow_rgb]
        else:
            # Multiply with original colors
            color_array = np.array([[c.r, c.g, c.b] for c in colors], dtype=np.float32)
            blended = color_array * rainbow_rgb / 255.0
            return [Color(int(rgb[0]), int(rgb[1]), int(rgb[2])) for rgb in blended]
    
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
        self.pixels = MockNeoPixel(pin, num_pixels, brightness=1.0, auto_write=False)
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
