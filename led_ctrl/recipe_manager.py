#!/usr/bin/env python3
"""
Recipe Management System - Moved from led_orchestrator.py
"""

import asyncio
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Union
from .pipeline_demo import BlackoutEffect, PinkCompressor

# Parameter Range Classes for Smart Recipes
@dataclass
class ParameterRange:
    """Base class for parameter ranges"""
    pass

@dataclass 
class FloatRange(ParameterRange):
    min_val: float
    max_val: float
    
    def resolve(self) -> float:
        return random.uniform(self.min_val, self.max_val)

@dataclass
class IntRange(ParameterRange):
    min_val: int
    max_val: int
    
    def resolve(self) -> int:
        return random.randint(self.min_val, self.max_val)

@dataclass
class ChoiceRange(ParameterRange):
    choices: List[Any]
    
    def resolve(self) -> Any:
        return random.choice(self.choices)

from .pipeline_demo import (
    PipelineController, TransitionMode, BreathingEffect, 
    StrobeEffect, ColorStrobeEffect, SparkleEffect, WaveEffect, RandomFlashEffect, RainbowEffect, LavaLampEffect,
    FireEffect, MeltEffect, FadeEffect, ScanEffect, CircleScanEffect, MarchingEffect, BlocksEffect,
    CrawlerEffect, WaterEffect, GlitchEffect, MetroEffect, PowerEffect, RainEffect, WalkingEffect,
    SpectrumEffect, EnergyEffect, WavelengthEffect, ScrollEffect, BarsEffect, RotationEffect,
    BlendMode, Effect, Color
)
from .audio_effects import MusicVisualizerEffect, RealTimeAudioProvider, AUDIO_AVAILABLE

@dataclass
class BaseColorConfig:
    """Base color configuration with smart parameter support"""
    colors: Union[List[Color], ChoiceRange]
    mode: Union[TransitionMode, ChoiceRange] = TransitionMode.STATIC
    speed: Union[float, FloatRange] = 1.0
    
    def resolve_config(self) -> 'BaseColorConfig':
        """Resolve ranges to actual config"""
        resolved_colors = self.colors.resolve() if isinstance(self.colors, ChoiceRange) else self.colors
        resolved_mode = self.mode.resolve() if isinstance(self.mode, ChoiceRange) else self.mode
        resolved_speed = self.speed.resolve() if isinstance(self.speed, FloatRange) else self.speed
        
        return BaseColorConfig(
            colors=resolved_colors,
            mode=resolved_mode, 
            speed=resolved_speed
        )

@dataclass
class EffectConfig:
    """Effect configuration with smart parameter support"""
    effect_type: str
    parameters: Dict[str, Union[Any, ParameterRange]]
    enabled: bool = True
    
    def resolve_parameters(self) -> Dict[str, Any]:
        """Resolve parameter ranges to actual values"""
        resolved = {}
        for key, value in self.parameters.items():
            if isinstance(value, ParameterRange):
                resolved[key] = value.resolve()
            else:
                resolved[key] = value  # Fixed value
        return resolved

@dataclass
class Recipe:
    """Complete recipe definition"""
    name: str
    base_colors: BaseColorConfig
    effects: List[EffectConfig]
    description: str = ""
class RecipeManager:
    """Manages recipe transitions and effect lifecycle"""
    
    def __init__(self, controller: PipelineController, tree_structure = None):
        self.controller = controller
        self.tree_structure = tree_structure
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
        """Apply recipe directly (first time) with smart parameter resolution"""
        # Resolve base color ranges to concrete values
        resolved_base_colors = recipe.base_colors.resolve_config()
        print(f"🎲 Smart Recipe: Base colors resolved to {len(resolved_base_colors.colors)} colors, mode={resolved_base_colors.mode}, speed={resolved_base_colors.speed:.2f}")
        
        # Set resolved base colors
        self.controller.pipeline.set_base_colors(
            resolved_base_colors.colors,
            resolved_base_colors.mode,
            resolved_base_colors.speed
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
    
    async def _transition_effects(self, new_effects: List[EffectConfig], transition_time: float, window_size: int = 1):
        """Smart effect transitions with blended swapping"""
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
        
        # Step 1: Update existing effects that are kept
        for effect_config in new_effects:
            if effect_config.effect_type in keep_effects:
                await self._update_effect_parameters(effect_config)
        
        # Step 2: Blended transition - swap effects in windows with overlap
        remove_list = list(remove_effects)
        add_list = [e for e in new_effects if e.effect_type in add_effects and e.enabled]
        
        max_items = max(len(remove_list), len(add_list))
        num_windows = (max_items + window_size - 1) // window_size  # Ceiling division
        window_delay = transition_time / max(num_windows, 1) if num_windows > 0 else 0
        
        for window in range(num_windows):
            start_idx = window * window_size
            end_idx = min(start_idx + window_size, max_items)
            
            # Add new effects in this window FIRST (creates overlap)
            for i in range(start_idx, end_idx):
                if i < len(add_list):
                    effect_config = add_list[i]
                    print(f"  ➕ Adding {effect_config.effect_type}")
                    effect_id = await self._create_effect(effect_config)
                    self.active_effects[effect_config.effect_type] = effect_id
            
            # Wait for overlap period
            if window_delay > 0:
                await asyncio.sleep(window_delay / 2)  # Half delay for overlap
            
            # Remove old effects in this window AFTER overlap
            for i in range(start_idx, end_idx):
                if i < len(remove_list):
                    effect_type = remove_list[i]
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
            
            # Wait remaining time between windows
            if window_delay > 0 and window < num_windows - 1:
                await asyncio.sleep(window_delay / 2)  # Remaining half delay
    
    async def _update_effect_parameters(self, effect_config: EffectConfig):
        """Update parameters of existing effect"""
        print(f"  🔧 Updating {effect_config.effect_type} parameters")
        effect_id = self.active_effects[effect_config.effect_type]
        effect = self.controller.pipeline.get_effect(effect_id)
        if effect:
            effect.update_parameters(effect_config.parameters)
    
    async def _create_effect(self, effect_config: EffectConfig) -> str:
        """Create and add effect to pipeline with smart parameter resolution"""
        effect_type = effect_config.effect_type
        
        # Resolve parameter ranges to concrete values
        resolved_params = effect_config.resolve_parameters()
        print(f"🎲 Smart Recipe: {effect_type} resolved params: {resolved_params}")
        
        if effect_type == "breathing":
            effect = BreathingEffect()
        elif effect_type == "strobe":
            effect = StrobeEffect()
        elif effect_type == "white_strobe":
            effect = ColorStrobeEffect()
            #effect.parameters['color'] = Color(255, 255, 255)  # Set to white
        elif effect_type == "ring_ripple":
            from .pipeline_demo import RingRippleEffect
            effect = RingRippleEffect(self.tree_structure)
        elif effect_type == "branch_sweep":
            from .pipeline_demo import BranchSweepEffect
            effect = BranchSweepEffect(self.tree_structure)
        elif effect_type == "rainbow_rings":
            from .pipeline_demo import RainbowRingsEffect
            effect = RainbowRingsEffect(self.tree_structure)
        elif effect_type == "rainbow_branches":
            from .pipeline_demo import RainbowBranchesEffect
            effect = RainbowBranchesEffect(self.tree_structure)
        elif effect_type == "rainbow_vortex":
            from .pipeline_demo import RainbowVortexEffect
            effect = RainbowVortexEffect(self.tree_structure)
        elif effect_type == "luminosity_scanner":
            from .pipeline_demo import LuminosityScannerEffect
            effect = LuminosityScannerEffect()
        elif effect_type == "luminosity_spiral":
            from .pipeline_demo import LuminositySpiralEffect
            effect = LuminositySpiralEffect(self.tree_structure)
        elif effect_type == "rainbow_branches_skewed":
            from .pipeline_demo import RainbowBranchesSkewedEffect
            effect = RainbowBranchesSkewedEffect(self.tree_structure)
        elif effect_type == "ring_colors":
            from .pipeline_demo import RingColorsEffect
            effect = RingColorsEffect(self.tree_structure)
        elif effect_type == "sparkle":
            effect = SparkleEffect()
        elif effect_type == "wave":
            effect = WaveEffect()
        elif effect_type == "random_flash":
            effect = RandomFlashEffect()
        elif effect_type == "rainbow":
            effect = RainbowEffect()
            effect.blend_mode = BlendMode.REPLACE
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
        elif effect_type == "circle_scan":
            effect = CircleScanEffect()
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
        elif effect_type == "blackout":
            effect = BlackoutEffect()
            effect.blend_mode = BlendMode.REPLACE
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
        elif effect_type == "rotation":
            effect = RotationEffect()
        elif effect_type == "pink_compressor":
            effect = PinkCompressor()
        elif effect_type == "music_visualizer":
            # Get or create global audio provider
            if not AUDIO_AVAILABLE:
                print("⚠️  Audio not available - install with: pip install sounddevice numpy")
                effect = BreathingEffect()  # Fallback to breathing effect
            else:
                if not hasattr(self, 'audio_provider'):
                    # Get num_bands from resolved params or CLI override
                    num_bands = BANDS_OVERRIDE or resolved_params.get('num_bands', 3)
                    self.audio_provider = RealTimeAudioProvider(num_bands=num_bands)
                    self.audio_provider.start()
                effect = MusicVisualizerEffect(self.audio_provider, self.tree_structure)
        elif effect_type == "fade_to_color":
            from .pipeline_demo import FadeToColorEffect
            effect = FadeToColorEffect()
        else:
            raise ValueError(f"Unknown effect type: {effect_type}")
        
        # Use resolved parameters instead of original parameters
        effect.update_parameters(resolved_params)
        return self.controller.pipeline.add_effect(effect)

# Configuration
LED_CRAWL_BLINK_DURATION = 2.0  # seconds per LED blink
STROBE_FREQ = 15.0     # Default strobe frequency
BANDS_OVERRIDE = None  # CLI override for number of bands (None = use recipe default)

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
            colors=[Color(200, 0, 0), Color(150, 0, 150)],
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
            EffectConfig("wave", {"speed":0.5, "amplitude": 0.}),
            EffectConfig("sparkle", {"density": 0.0025})
        ]
    ),

    # TODO avoid white base color here
    "rainbow": Recipe(
        name="Pure Rainbow",
        description="Classic rainbow cycling effect",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],
            mode=TransitionMode.STATIC,
        ),
        effects=[
            # EffectConfig("fade_to_color", {"target_color": Color(255, 255, 255), "duration": 5.0})
            EffectConfig("rainbow", {"speed": 0.2})
        ]
    ),
    
    # TODO avoid white base color here
    "rainbow_blackout": Recipe(
        name="Pure Rainbow",
        description="Classic rainbow cycling effect",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0), Color(255, 255, 255)],
            mode=TransitionMode.FADE,
        ),
        effects=[
            EffectConfig("rainbow", {"speed": 0.5})
            ,EffectConfig("blackout", {
                "shutdown_mode": ChoiceRange(["sequential"]),
                "restore_mode": ChoiceRange(["sequential", "instant"]),
                "shutdown_duration": FloatRange(4.0, 10.0),
                "restore_duration": FloatRange(10, 5.0),
                "hold_duration": 0.0
            })
        ]
    ),
    "smart_spectrum_enhanced": Recipe(
        name="Smart Spectrum Enhanced",
        description="Randomized enhanced spectrum with variable bands",
        base_colors=BaseColorConfig(
            colors=ChoiceRange([
                [Color(150, 0, 150), Color(0, 0, 150)],
                [Color(20, 0, 40), Color(0, 20, 40)],    # Dark purple fade
                [Color(40, 0, 0), Color(0, 0, 40)]       # Dark red-blue fade
            ]),
            mode=ChoiceRange([TransitionMode.STATIC, TransitionMode.FADE]),
            speed=FloatRange(0.01, 0.8)
        ),
        effects=[
            EffectConfig("music_visualizer", {
                "mode": "spectrum_enhanced",
                "num_bands": ChoiceRange([3, 6, 9, 12]),
                "sensitivity": FloatRange(0.8, 4.0),
                "color_morph": ChoiceRange([True, False])
            }),
            EffectConfig("rotation", { # always put rotation effect last on the effects list
                "speed": FloatRange(0.0, 9.0)
            })
        ]
    ),

    "smart_music_spectrum": Recipe(
        name="Smart Music Spectrum",
        description="Randomized music visualization with parameter ranges",
        base_colors=BaseColorConfig(
            colors=ChoiceRange([
                [Color(50, 50, 0)],
                [Color(50, 0, 50), Color(0, 0, 50)],      # Purple fade
                [Color(150, 0, 150), Color(0, 0, 150)],      # Purple fade
                [Color(255, 0, 0), Color(0, 0, 255)]      # Red-blue fade
            ]),
            mode=ChoiceRange([TransitionMode.STATIC, TransitionMode.FADE]),
            speed=FloatRange(0.01, 0.8)
        ),
        effects=[
            EffectConfig("music_visualizer", {
                "mode": "spectrum",
                "sensitivity": FloatRange(0.5, 3.0),
                "num_bands": ChoiceRange([3, 6, 9]),
                "color_morph": ChoiceRange([True, False])
            }),
            EffectConfig("rotation", { # always put rotation effect last on the effects list
                "speed": FloatRange(0.0, 12.0)
            })
        ]
    ),

    "pink_smart_spectrum_enhanced": Recipe(
        name="Pink smart Spectrum Enhanced",
        description="Randomized enhanced spectrum with variable bands",
        base_colors=BaseColorConfig(
            colors=ChoiceRange([
                [Color(150, 0, 150), Color(0, 0, 150)],
                [Color(20, 0, 40), Color(0, 20, 40)],    # Dark purple fade
                [Color(40, 0, 0), Color(0, 0, 40)]       # Dark red-blue fade
            ]),
            mode=ChoiceRange([TransitionMode.STATIC, TransitionMode.FADE]),
            speed=FloatRange(0.01, 0.8)
        ),
        effects=[
            EffectConfig("music_visualizer", {
                "mode": "spectrum_enhanced",
                "num_bands": ChoiceRange([3, 6, 9, 12]),
                "sensitivity": FloatRange(0.8, 4.0),
                "color_morph": ChoiceRange([True, False])            }),
            EffectConfig("rotation", { # always put rotation effect last on the effects list
                "speed": FloatRange(0.0, 9.0)
            }),
            EffectConfig("pink_compressor", {"reverse":True})
        ]
    ),

    "pink_smart_music_spectrum": Recipe(
        name="Smart Music Spectrum",
        description="Randomized music visualization with parameter ranges",
        base_colors=BaseColorConfig(
            colors=ChoiceRange([
                [Color(50, 50, 0)],
                [Color(50, 0, 50), Color(0, 0, 50)],      # Purple fade
                [Color(150, 0, 150), Color(0, 0, 150)],      # Purple fade
                [Color(255, 0, 0), Color(0, 0, 255)]      # Red-blue fade
            ]),
            mode=ChoiceRange([TransitionMode.STATIC, TransitionMode.FADE]),
            speed=FloatRange(0.01, 0.8)
        ),
        effects=[
            EffectConfig("music_visualizer", {
                "mode": "spectrum",
                "sensitivity": FloatRange(0.5, 3.0),
                "num_bands": ChoiceRange([3, 6, 9]),
                "color_morph": ChoiceRange([True, False])            }),
            EffectConfig("rotation", { # always put rotation effect last on the effects list
                "speed": FloatRange(0.0, 12.0)
            }),
            EffectConfig("pink_compressor", {"reverse":True})
        ]
    ),


    "pair_blender": Recipe(
        name="Pair Blender",
        description="Alternating LED pair blend effect",
        base_colors=BaseColorConfig(
            colors=ChoiceRange([
                [Color(0, 0, 50), Color(0, 0, 200)],   
                [Color(200, 0, 0), Color(0, 0, 0)],    
                [Color(200, 0, 0), Color(200, 0, 200)],
                [Color(200, 0, 0), Color(20, 0, 40)],  
                [Color(200, 200, 0), Color(20, 20, 0)] 
            ]),
            mode=TransitionMode.PAIR_BLEND,
            speed=FloatRange(0.1, 0.5) # ranodmize speed
        ),
        effects=[
            EffectConfig("random_flash", {"frequency": 2.0})
        ]
    ),

    "blackout": Recipe(
        name="Blackout",
        description="Random pixel shutdown and restore",
        base_colors=BaseColorConfig(
            colors=ChoiceRange([
                [Color(255, 0, 0)],
                [Color(0, 255, 0)],
                [Color(0, 0, 255)],
                [Color(255, 255, 0)]
            ]),
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("blackout", {
                "shutdown_mode": ChoiceRange(["sequential"]),
                "restore_mode": ChoiceRange(["sequential", "instant"]),
                "shutdown_duration": FloatRange(3.0, 10.0),
                "restore_duration": FloatRange(0.0, 5.0),
                "hold_duration": 0.0
            })
        ]
    ),

    "blackout_reverse": Recipe(
        name="Blackout Reverse",
        description="Instant shutdown, sequential restore, stay on",
        base_colors=BaseColorConfig(
            colors=ChoiceRange([
                [Color(255, 0, 0)],
                [Color(0, 255, 0)],
                [Color(0, 0, 255)],
                [Color(255, 255, 0)]
            ]),
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("blackout", {
                "shutdown_mode": "instant",
                "restore_mode": "sequential",
                "shutdown_duration": 0.0,
                "restore_duration": FloatRange(3.0, 10.0),
                "hold_duration": 0.1,
                "on_duration": FloatRange(2.0, 5.0)
            })
        ]
    ),

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
            colors=[Color(255, 0, 0), Color(150, 0, 150)],
            mode=TransitionMode.FADE,
            speed=0.1
        ),
        effects=[
            EffectConfig("breathing", {"speed": 0.3, "min_intensity": 0.2}),
            EffectConfig("random_flash", {"frequency": 2.0})
        ]
    ),

    "spectrum_enhanced": Recipe(
        name="Enhanced Spectrum Analyzer",
        description="Enhanced real-time audio spectrum visualization",
        base_colors=BaseColorConfig(
            colors=[Color(0, 50, 50)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "spectrum_enhanced", "sensitivity": 1.5, "num_bands": 6})
        ]
    ),

    "spectrum_enhanced_9": Recipe(
        name="Enhanced Spectrum Analyzer (9-Band)",
        description="Enhanced real-time audio spectrum visualization with 9 bands",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "spectrum_enhanced", "sensitivity": 1.5, "num_bands": 9})
        ]
    ),

    "spectrum_enhanced_12": Recipe(
        name="Enhanced Spectrum Analyzer (12-Band)",
        description="Enhanced real-time audio spectrum visualization with 12 bands",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "spectrum_enhanced", "sensitivity": 1.5, "num_bands": 12})
        ]
    ),


    "music_spectrum_morph": Recipe(
        name="Music Spectrum (Morphing Colors)",
        description="3-band spectrum with smooth color transitions",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "spectrum", "sensitivity": 1.5, "color_morph": True})
        ]
    ),



    "spectrum_enhanced_morph": Recipe(
        name="Enhanced Spectrum (Morphing Colors)",
        description="6-band spectrum with smooth color transitions",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "spectrum_enhanced", "sensitivity": 1.5, "num_bands": 6, "color_morph": True})
        ]
    ),


    "spectrum_enhanced_9_morph": Recipe(
        name="Enhanced Spectrum 9-Band (Morphing Colors)",
        description="9-band spectrum with smooth color transitions",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "spectrum_enhanced", "sensitivity": 1.5, "num_bands": 9, "color_morph": True})
        ]
    ),

    "spectrum_enhanced_12_morph": Recipe(
        name="Enhanced Spectrum 12-Band (Morphing Colors)",
        description="12-band spectrum with smooth color transitions",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "spectrum_enhanced", "sensitivity": 1.5, "num_bands": 12, "color_morph": True})
        ]
    ),
    
    "music_pulse": Recipe(
        name="Music Pulse",
        description="Colors pulse with music",
        base_colors=BaseColorConfig(
            colors=[Color(255, 0, 255), Color(0, 0, 255)],
            mode=TransitionMode.FADE,
            speed=0.2
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "pulse", "sensitivity": 1.0}),
            EffectConfig("random_flash", {"frequency": 2.0})
        ]
    ),
    
    "music_pulse_couple": Recipe(
        name="Music Pulse Couple",
        description="Red/pink colors pulse with music",
        base_colors=BaseColorConfig(
            colors=[Color(255, 0, 100), Color(255, 0, 0)],
            mode=TransitionMode.FADE,
            speed=0.2
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "pulse", "sensitivity": 1.0}),
            EffectConfig("random_flash", {"frequency": 2.0, "flash_color": Color(0, 255, 255)})
        ]
    ),

    "music_pulse_rainbow": Recipe(
        name="Music Pulse rainbow",
        description="Colors pulse with music",
        base_colors=BaseColorConfig(
            colors=[Color(255, 0, 255), Color(0, 0, 255)],
            mode=TransitionMode.FADE,
            speed=0.2
        ),
        effects=[
            EffectConfig("rainbow", {"speed": 0.2}),
            EffectConfig("music_visualizer", {"mode": "pulse", "sensitivity": 1.0}),
            EffectConfig("sparkle", {"density": 0.005, "period": 3, "duration": 0.15})
        ]
    ),

    "music_pulse_colors": Recipe(
        name="Music Pulse colors",
        description="Colors pulse with music",
        base_colors=BaseColorConfig(
            colors=[
                Color(255, 0, 0),      # Red
                Color(0, 255, 0),      # Green
                Color(0, 0, 255),      # Blue
                Color(255, 255, 0),    # Yellow
                Color(255, 0, 255),    # Magenta
                Color(0, 255, 255),    # Cyan
                Color(255, 255, 255),  # White
                Color(255, 128, 0)     # Orange
            ],
            mode=TransitionMode.FADE,
            speed=FloatRange(0.03,0.25)
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "pulse", "sensitivity": 1.0}),
            EffectConfig("luminosity_scanner", {
                "speed": FloatRange(0.01,0.3), 
                "width": 8, 
                "scan_mode": ChoiceRange(["bounce", "wrap"]),
                "intensity": FloatRange(0.2,1.0)  # 50% brightness boost
            }),
            EffectConfig("random_flash", {"frequency": 2.0, "flash_color": Color(0, 255, 255)})
        ]
    ),

    "music_pulse_bad": Recipe(
        name="Music Pulse bad",
        description="Colors pulse with music",
        base_colors=BaseColorConfig(
            colors=[
                Color(50, 50, 50),     # Dark gray
                Color(50, 50, 0),      # Dark yellow
                Color(0, 50, 0)        # Dark green
            ],
            mode=TransitionMode.FADE,
            speed=FloatRange(0.03, 0.25)
        ),
        effects=[
            EffectConfig("music_visualizer", {"mode": "pulse", "sensitivity": 1.0}),
            EffectConfig("luminosity_spiral", {
                "rotation_rate": 1.0,
                "num_arms": ChoiceRange([1,2,3]),
                "decay_rate": 120,
                "speed": FloatRange(0.1,3)  # 5 updates per second
            }),
            EffectConfig("sparkle", {"density": 0.055, "period": 10, "duration": 0.15})
        ]
    ),

    "music_pulse_blue": Recipe(
        name="Music Pulse blue",
        description="Colors pulse with music",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 120), Color(0, 0, 150)],
            mode=TransitionMode.FADE,
            speed=FloatRange(0.03, 0.25)
        ),
        effects=[
            EffectConfig("ring_ripple", {"speed": 1.0, "color": Color(0, 255, 255)}),
            EffectConfig("music_visualizer", {"mode": "pulse", "sensitivity": 1.0}),
            EffectConfig("sparkle", {"density": 0.055, "period": 15, "duration": 0.15})
        ]
    ),
    
    
    "ring_amplitude": Recipe(
        name="Ring Amplitude",
        description="Ring position shows audio amplitude",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 50)],  # Dark blue background
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("music_visualizer", {
                "mode": "ring_amplitude", 
                "sensitivity": 1.0,
                "background_color": Color(0, 0, 50),  # Dark blue
                "ring_color": Color(255, 255, 255)   # White
            })
        ]
    ),
    
    "spectrum_analyzer": Recipe(
        name="Spectrum Analyzer",
        description="LedFx-style spectrum analyzer bars",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0),Color(0, 0, 120)],  # Black base
            mode=TransitionMode.FADE
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
            EffectConfig("wavelength", {"speed": 0.5})
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
            colors=[Color(255, 150, 0), Color(210, 0, 0)],  # Orange to red
            mode=TransitionMode.FADE,
            speed=0.4
        ),
        effects=[
            EffectConfig("fire", {"speed": FloatRange(0.005,0.2), "intensity": 10})
        ]
    ),
    
    "circle_scanner": Recipe(
        name="Circle Scanner",
        description="Circular scanner that wraps around the strip",
        base_colors=BaseColorConfig(
            colors=[
                Color(255, 0, 0),      # Red
                Color(0, 255, 0),      # Green
                Color(0, 0, 255),      # Blue
                Color(255, 255, 0),    # Yellow
                Color(255, 0, 255),    # Magenta
                Color(0, 255, 255),    # Cyan
                Color(255, 255, 255),  # White
                Color(255, 128, 0)     # Orange
            ],
            mode=TransitionMode.RANDOM,
            speed=FloatRange(0.03,0.25)
        ),
        effects=[
            EffectConfig("circle_scan", {"speed": FloatRange(0.3,5), "width": 8})
        ]
    ),

    "scanner": Recipe(
        name="Scanner",
        description="Cylon eye scanner effect",
        base_colors=BaseColorConfig(
            colors=[
                Color(255, 0, 0),      # Red
                Color(0, 255, 0),      # Green
                Color(0, 0, 255),      # Blue
                Color(255, 255, 0),    # Yellow
                Color(255, 0, 255),    # Magenta
                Color(0, 255, 255),    # Cyan
                Color(255, 255, 255),  # White
                Color(255, 128, 0)     # Orange
            ],
            mode=TransitionMode.RANDOM,
            speed=FloatRange(0.03,0.25)
        ),
        effects=[
            EffectConfig("scan", {"speed":FloatRange(0.3,5), "width": 8})
        ]
    ),
    
    "digital_rain": Recipe(
        name="Digital Rain",
        description="Matrix-style digital rain",
        base_colors=BaseColorConfig(
            colors=[Color(0, 80, 0),Color(0, 140, 0)],
            mode=ChoiceRange([TransitionMode.FADE, TransitionMode.PAIR_BLEND]),
            speed=0.2
        ),
        effects=[
            EffectConfig("rain", {"speed": 3.0, "density": 0.12})
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
            speed=0.2
        ),
        effects=[
            EffectConfig("water", {"speed": 2, "ripples": 2}),
            EffectConfig("sparkle", {"density": 0.055, "period": 16, "duration": 0.15})
        ]
    ),
    
    "marching_ants": Recipe(
        name="Marching Ants",
        description="Classic marching ants pattern",
        base_colors=BaseColorConfig(
            colors=[Color(200, 0, 0),Color(0, 200, 0)],
            mode=TransitionMode.CYCLE,
            speed=0.1
        ),
        effects=[
            EffectConfig("marching", {"speed": 1, "size": 3})
            # ,EffectConfig("power", {"level": 1.0, "direction": 1})  # Full power = all LEDs

        ]
    ),
    
    "glitch_matrix": Recipe(
        name="Glitch Matrix",
        description="Digital glitch corruption",
        base_colors=BaseColorConfig(
            colors=[Color(0, 200, 0), Color(100, 0, 0)],  # Green to red
            mode=TransitionMode.FADE,
            speed=0.08
        ),
        effects=[
            EffectConfig("glitch", {"intensity": 0.05, "speed": 2})
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
            ,EffectConfig("blackout", {
                "shutdown_mode": ChoiceRange(["sequential"]),
                "restore_mode": ChoiceRange(["sequential", "instant"]),
                "shutdown_duration": FloatRange(3.0, 10.0),
                "restore_duration": FloatRange(0.0, 5.0),
                "hold_duration": 0.0
            })
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
            EffectConfig("fade", {"speed": 1.0}),
            EffectConfig("luminosity_scanner", {
                "speed": FloatRange(0.01,0.3), 
                "width": 8, 
                "scan_mode": ChoiceRange(["bounce", "wrap"]),
                "intensity": FloatRange(0.2,1.0)  # 50% brightness boost
            })
        ]
    ),
    
    "luminosity_spiral": Recipe(
        name="Luminosity Spiral",
        description="Galaxy spiral with rotating arms",
        base_colors=BaseColorConfig(
            colors=[Color(100, 0, 100)],
            mode=TransitionMode.STATIC,
            speed=0.01
        ),
        effects=[
            EffectConfig("luminosity_spiral", {
                "rotation_rate": 1.0,
                "num_arms": ChoiceRange([1,2,3]),
                "decay_rate": 120,
                "speed": FloatRange(0.1,3)  # 5 updates per second
            })
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
            EffectConfig("blocks", {"speed": 0.5, "block_size": 6})
        ]
    ),
    
    "pixel_crawler": Recipe(
        name="Pixel Crawler",
        description="Crawling pixel with tail",
        base_colors=BaseColorConfig(
            colors=[Color(0, 255, 255),Color(0, 255,0)],  # Cyan
            mode=TransitionMode.CYCLE
        ),
        effects=[
            EffectConfig("crawler", {"speed": 10, "tail_length": 40})
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
    
    "color_strobe": Recipe(
        name="Color Strobe",
        description="Color strobe at specified frequency",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base (will be overridden by strobe)
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("white_strobe", {"frequency": STROBE_FREQ})  # Use global frequency
        ]
    ),
    
    "ring_ripple": Recipe(
        name="Ring Ripple",
        description="Ripple effect through tree rings",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 80), Color(0, 0, 30)],
            mode=TransitionMode.FADE,
            speed=0.15
        ),
        effects=[
            EffectConfig("ring_ripple", {"speed": 1.0, "color": Color(0, 255, 255)})
        ]
    ),
    
    "branch_sweep": Recipe(
        name="Branch Sweep", 
        description="Sweep effect around tree branches",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 50), Color(50, 0, 50)],  # Very dark red blue
            mode=TransitionMode.FADE,
            speed=0.2
        ),
        effects=[
            EffectConfig("branch_sweep", {"speed": 0.6, "color": Color(0, 0, 255)})
        ]
    ),
    
    "rainbow_rings": Recipe(
        name="Rainbow Rings",
        description="Rainbow colors emanate through rings",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("rainbow_rings", {"speed": 0.1, "direction": "outward", "hue_spread": 0.27})
        ]
    ),
    
    "rainbow_branches": Recipe(
        name="Rainbow Branches",
        description="Rainbow colors cascade from branch to branch",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("rainbow_branches", {"speed": 0.1, "direction": "cw", "hue_spread": 0.4})
        ]
    ),
    
    "rainbow_vortex": Recipe(
        name="Rainbow Vortex",
        description="Each ring contains full rainbow spinning at different speeds",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("rainbow_vortex", {"base_speed": 0.4, "speed_ratio": 0.99, "direction": "cw", "alternating": False})
        ]
    ),

    "rainbow_vortex_anti": Recipe(
        name="Rainbow Vortex",
        description="Each ring contains full rainbow spinning at different speeds",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("rainbow_vortex", {"base_speed": 0.4, "speed_ratio": 1.0102, "direction": "cw", "alternating": False})
        ]
    ),
    
    "rainbow_vortex_alternating": Recipe(
        name="Rainbow Vortex Alternating",
        description="Each ring spins in alternating directions at different speeds",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("rainbow_vortex", {"base_speed": 1.5, "speed_ratio": 0.98, "direction": "cw", "alternating": True})
        ]
    ),
    

    "rainbow_branches_skewed": Recipe(
        name="Rainbow Branches Skewed",
        description="Rainbow colors through skewed branch groupings",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black base
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("rainbow_branches_skewed", {"speed": 0.01, "direction": "cw", "hue_spread": 1.0})
        ]
    ),
    
    "ring_colors": Recipe(
        name="Ring Colors",
        description="Each ring in different color",
        base_colors=BaseColorConfig(
            colors=[Color(0, 0, 0)],  # Black background
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("ring_colors", {})
        ]
    ),
    
    "fade_to_black": Recipe(
        name="Fade to Black",
        description="Fade current colors to black over time",
        base_colors=BaseColorConfig(
            colors=[Color(255, 255, 255)],  # White - should be replaced with actual source color
            mode=TransitionMode.STATIC
        ),
        effects=[
            EffectConfig("fade_to_color", {"target_color": Color(0, 0, 0), "duration": 2.0})
        ]
    )
}
