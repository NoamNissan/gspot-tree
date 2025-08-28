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
from led_controller import Color
from pipeline_demo import (
    PipelineController, TransitionMode, BreathingEffect, 
    StrobeEffect, SparkleEffect, WaveEffect, RandomFlashEffect, Effect
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
    
    def __init__(self, sample_rate=22050, block_size=512):
        self.sample_rate = sample_rate
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
        self.bass_bins = slice(0, int(250 * block_size / sample_rate))     # 0-250Hz (musical bass)
        self.mid_bins = slice(int(250 * block_size / sample_rate), 
                             int(4000 * block_size / sample_rate))          # 250-4000Hz (vocals, instruments)
        self.high_bins = slice(int(4000 * block_size / sample_rate), 
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
        
        if self.current_recipe is None:
            # First recipe - apply directly
            await self._apply_recipe_direct(recipe)
        else:
            # Transition from current recipe
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
            effect_id = self.active_effects[effect_type]
            self.controller.pipeline.remove_effect(effect_id)
            del self.active_effects[effect_type]
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

# Recipe Definitions
RECIPES = {
    "recipe1": Recipe(
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
            EffectConfig("strobe", {"frequency": 3.0})
        ]
    ),
    
    "recipe2": Recipe(
        name="Red-Pink Breathing",
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
    
    "recipe3": Recipe(
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
    )
}

async def demo_recipe_transitions(num_pixels: int = 100):
    """Demonstrate recipe transitions"""
    controller = PipelineController(num_pixels, force_simulation=True)
    await controller.start()
    
    try:
        # Start rendering loop
        render_task = asyncio.create_task(controller.run_loop())
        
        # Create recipe manager
        recipe_manager = RecipeManager(controller)
        
        print("🍽️ Recipe Transition Demo")
        
        # Apply recipe1
        await recipe_manager.apply_recipe(RECIPES["recipe1"])
        await asyncio.sleep(8)
        
        # Transition to recipe2 (breathing continues, other effects change)
        await recipe_manager.apply_recipe(RECIPES["recipe2"], transition_time=3.0)
        await asyncio.sleep(8)
        
        # Transition to recipe3
        await recipe_manager.apply_recipe(RECIPES["recipe3"], transition_time=3.0)
        await asyncio.sleep(8)
        
        # Music spectrum analyzer
        await recipe_manager.apply_recipe(RECIPES["music_spectrum"], transition_time=3.0)
        await asyncio.sleep(10)
        
        # Music pulse effect
        await recipe_manager.apply_recipe(RECIPES["music_pulse"], transition_time=3.0)
        await asyncio.sleep(10)
        
        # Back to recipe2 (smooth transition)
        await recipe_manager.apply_recipe(RECIPES["recipe2"], transition_time=3.0)
        await asyncio.sleep(5)
        
        print("🍽️ Recipe demo completed!")
        render_task.cancel()
        
    except KeyboardInterrupt:
        print("\n🍽️ Recipe demo interrupted")
    finally:
        await controller.stop()

async def run_single_recipe(recipe_name: str, num_pixels: int = 100):
    """Run a single recipe continuously"""
    if recipe_name not in RECIPES:
        print(f"❌ Recipe '{recipe_name}' not found!")
        print(f"Available recipes: {', '.join(RECIPES.keys())}")
        return
    
    controller = PipelineController(num_pixels, force_simulation=True)
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

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Recipe System Demo')
    parser.add_argument('--pixels', type=int, default=100, help='Number of pixels (default: 100)')
    parser.add_argument('--recipe', type=str, help='Run specific recipe directly (recipe1, recipe2, recipe3, music_spectrum, music_pulse)')
    
    args = parser.parse_args()
    
    print(f"🍽️ Recipe System")
    print(f"  Pixels: {args.pixels}")
    
    if args.recipe:
        print(f"  Mode: Single recipe ({args.recipe})")
        await run_single_recipe(args.recipe, args.pixels)
    else:
        print(f"  Mode: Full demo sequence")
        await demo_recipe_transitions(args.pixels)

if __name__ == "__main__":
    asyncio.run(main())
