#!/usr/bin/env python3
"""
LED Composer - High-level LED control for interactive tree
Manages state-based LED patterns and recipe transitions
"""

import asyncio
import time
import random
import math
from led_controller import Color
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional
import multiprocessing

from pipeline_demo import PipelineController, TreeStructure
from recipe_manager import RecipeManager
from tree_config import load_tree_config


class ComposerState(Enum):
    """LED Composer states"""
    IDLE = "idle"
    SINGLE_FEEDBACK = "single_feedback" 
    SINGLE_ACTIVE = "single_active"
    COUPLE_FEEDBACK = "couple_feedback"
    COUPLE_ACTIVE = "couple_active"
    ADVERTISE = "advertise"
    MANUAL = "manual"
    NOT_ACTIVE = "not_active"


class LEDComposerInterface(ABC):
    """Abstract interface for LED Composer implementations"""
    
    @abstractmethod
    async def start(self): 
        """Start the LED composer"""
        pass
    
    @abstractmethod
    async def stop(self): 
        """Stop the LED composer"""
        pass
    
    @abstractmethod
    async def set_state(self, new_state: ComposerState): 
        """Set the current state"""
        pass
    
    @abstractmethod
    def get_current_state(self) -> ComposerState: 
        """Get the current state"""
        pass
    
    @abstractmethod
    async def set_manual_recipe(self, recipe_name: str): 
        """Set manual recipe (admin mode)"""
        pass


class LEDComposer(LEDComposerInterface):
    """Single-process LED Composer implementation"""
    
    def __init__(self, tree_config_path: str, force_simulation: bool = False):
        # Load tree configuration
        tree_data = load_tree_config(tree_config_path, verbose=True)
        tree_structure = TreeStructure(tree_data['rings'], tree_data['branches'])
        num_pixels = sum(len(branch) for branch in tree_structure.branches)
        
        # Initialize pipeline components
        self.controller = PipelineController(num_pixels, force_simulation=force_simulation, tree_structure=tree_structure)
        self.recipe_manager = RecipeManager(self.controller)
        
        # State management
        self.current_state = ComposerState.IDLE
        self.state_start_time = time.time()
        self.last_activity_time = time.time()
        
        # Control flags
        self.running = False
        self.controller_task = None
        self.recipe_task = None
        
        # State configuration
        self.auto_advertise_timeout = 0.0    # Default: never auto-advertise
        self.advertise_duration = 3.0        # 3 seconds of advertise
        self.manual_timeout = 600.0          # 10 minutes manual -> advertise
        self.feedback_timeout = 5.0          # Default feedback timeout
        self.strobe_duration = 1.0           # Default strobe duration
        
        # Parameter system - organized by state but flattened
        self.parameters = {
            # General parameters (affect multiple states)
            'feedback_timeout': 5.0,
            'strobe_duration': 1.0,
            
            # Single feedback parameters
            'single_strobe_frequency': 15.0,
            'single_strobe_duty_cycle': 0.25,
            
            # Couple feedback parameters  
            'couple_strobe_frequency': 15.0,
            'couple_strobe_duty_cycle': 0.25,
            
            # Idle parameters
            'idle_breathing_speed': 0.5,
            'idle_breathing_min': 0.3,
            'idle_breathing_max': 1.0,
        }
        
        print(f"🎨 LED Composer initialized: {num_pixels} pixels, {len(tree_structure.branches)} branches")
    
    async def start(self):
        """Start the LED composer and its loops"""
        if self.running:
            return
            
        print("🚀 Starting LED Composer...")
        
        # Start pipeline controller
        await self.controller.start()
        self.controller_task = asyncio.create_task(self.controller.run_loop())
        
        # Start recipe randomizer
        self.recipe_task = asyncio.create_task(self._recipe_randomizer_loop())
        
        self.running = True
        print("✅ LED Composer started")
    
    async def stop(self):
        """Stop the LED composer"""
        if not self.running:
            return
            
        print("🛑 Stopping LED Composer...")
        self.running = False
        
        # Cancel tasks
        if self.recipe_task:
            self.recipe_task.cancel()
        if self.controller_task:
            self.controller_task.cancel()
            
        # Stop controller
        await self.controller.stop()
        print("✅ LED Composer stopped")
    
    def get_params(self) -> dict:
        """Get all parameters sorted by relevance"""
        return dict(sorted(self.parameters.items()))
    
    def set_params(self, params: dict):
        """Update parameters and sync with instance variables"""
        self.parameters.update(params)
        # Sync commonly used parameters to instance variables
        self.feedback_timeout = self.parameters['feedback_timeout']
        self.strobe_duration = self.parameters['strobe_duration']
    
    async def set_state(self, new_state: ComposerState, **kwargs):
        """Immediately switch to new state with optional feedback timeout"""
        if self.current_state == new_state:
            return
            
        print(f"🎵 State change: {self.current_state.value} → {new_state.value}")
        
        # Cancel current recipe logic
        if self.recipe_task:
            self.recipe_task.cancel()
        
        # Update state
        self.current_state = new_state
        self.state_start_time = time.time()
        self.last_activity_time = time.time()
        
        # Update parameters from kwargs
        if kwargs:
            self.set_params(kwargs)
        
        # Store feedback timeout and strobe duration for feedback states
        if new_state in [ComposerState.SINGLE_FEEDBACK, ComposerState.COUPLE_FEEDBACK]:
            self.feedback_timeout = self.parameters['feedback_timeout']
            self.strobe_duration = self.parameters['strobe_duration']
        
        # Restart recipe randomizer with new state
        if self.running:
            self.recipe_task = asyncio.create_task(self._recipe_randomizer_loop())
    
    def get_current_state(self) -> ComposerState:
        """Get current state"""
        return self.current_state
    
    async def set_auto_advertise_timeout(self, timeout: float):
        """Set auto-advertise timeout (0 = never)"""
        self.auto_advertise_timeout = timeout
        print(f"🕐 Auto-advertise timeout set to {timeout}s ({'never' if timeout == 0 else f'{timeout}s'})")

    async def set_manual_recipe(self, recipe_name: str):
        """Set manual recipe and switch to manual mode"""
        await self.set_state(ComposerState.MANUAL)
        await self._load_recipe(recipe_name, transition_time=0.5)
        print(f"🎛️ Manual recipe loaded: {recipe_name}")
    
    async def _recipe_randomizer_loop(self):
        """Main recipe randomization loop - delegates to state-specific loops"""
        try:
            if self.current_state == ComposerState.IDLE:
                await self._idle_state_loop()
            elif self.current_state == ComposerState.SINGLE_FEEDBACK:
                await self._single_feedback_loop()
            elif self.current_state == ComposerState.SINGLE_ACTIVE:
                await self._single_active_state_loop()
            elif self.current_state == ComposerState.COUPLE_FEEDBACK:
                await self._couple_feedback_loop()
            elif self.current_state == ComposerState.COUPLE_ACTIVE:
                await self._couple_active_state_loop()
            elif self.current_state == ComposerState.ADVERTISE:
                await self._advertise_loop()
            elif self.current_state == ComposerState.MANUAL:
                await self._manual_loop()
            elif self.current_state == ComposerState.NOT_ACTIVE:
                await self._not_active_loop()
        except KeyboardInterrupt as e:
            print(f"🛑 User interrupted recipe loop: {e}")
            self.running = False
            return
        except EOFError as e:
            print(f"🛑 EOF in recipe loop: {e}")
            self.running = False
            return
        except Exception as e:
            # Raise unexpected exceptions
            print(f"❌ RECIPE RANDOMIZER EXCEPTION: {e}")
            print(f"❌ Exception type: {type(e)}")
            import traceback
            traceback.print_exc()
            print("❌ STOPPING COMPOSER DUE TO EXCEPTION")
            self.running = False
            raise  # Re-raise to crash the program
    
    # State-specific loops (each runs until state changes)
    async def _idle_state_loop(self):
        """Calm, serene patterns with slow changes"""
        while self.current_state == ComposerState.IDLE:
            # Sunset breathing for 60 seconds
            await self._load_recipe("sunset_breathing", transition_time=15.0)
            await self._sleep_while_in_state(60)
            
            if self.current_state != ComposerState.IDLE:
                break
                
            # Water ripples for 45 seconds
            await self._load_recipe("water_ripples", transition_time=15.0)
            await self._sleep_while_in_state(45)
            
            if self.current_state != ComposerState.IDLE:
                break
                
            # Fade cycle for 50 seconds
            await self._load_recipe("fade_cycle", transition_time=15.0)
            await self._sleep_while_in_state(50)
    
    def _generate_edge_biased_color(self, color1, color2):
        """Generate edge-biased color between two colors"""
        u = random.random()
        bias = u * u * u  # Cubic for stronger edge bias
        if random.random() < 0.5:
            bias = 1 - bias
        
        # Interpolate between color1 and color2
        r = int(color1.r + (color2.r - color1.r) * bias)
        g = int(color1.g + (color2.g - color1.g) * bias)
        b = int(color1.b + (color2.b - color1.b) * bias)
        
        return Color(r, g, b)

    async def _single_feedback_loop(self):
        """Blue/cyan strobe for 2s then fade to black"""
        # Generate blue-cyan edge-biased color
        blue = Color(0, 0, 255)
        cyan = Color(0, 255, 255)
        color = self._generate_edge_biased_color(blue, cyan)
        
        print("strobe")
        # Strobe with configurable parameters
        await self.controller.trigger_strobe(
            self.parameters['single_strobe_frequency'], 
            self.parameters['strobe_duration'], 
            color
        )
        
        print("strobe complete, fading to black")
        # Create a custom fade recipe with the exact strobe color as source
        # Use remaining time as fade duration
        remaining_time = self.parameters['feedback_timeout'] - self.parameters['strobe_duration']  # Total timeout minus strobe time
        fade_recipe = self._create_fade_from_color_recipe(color, Color(0, 0, 0), remaining_time)
        await self.recipe_manager.apply_recipe(fade_recipe, transition_time=0.0)
        print("fade recipe applied - fading from strobe color to black")

        # Wait for remaining time
        print("waiting for timeout...")
        await self._sleep_while_in_state(remaining_time)  # Wait for fade to complete
        print("timeout complete")
        
        # Auto-transition to not_active after recipe finishes
        if self.current_state == ComposerState.SINGLE_FEEDBACK:
            print("🔄 Transitioning from SINGLE_FEEDBACK to NOT_ACTIVE")
            await self.set_state(ComposerState.NOT_ACTIVE)
        else:
            print(f"⚠️ Current state is {self.current_state}, not SINGLE_FEEDBACK")
    
    async def _single_active_state_loop(self):
        """Happy, energetic music-reactive patterns"""
        while self.current_state == ComposerState.SINGLE_ACTIVE:
            # Smart music spectrum - stays active until state changes
            await self._load_recipe("smart_music_spectrum", transition_time=2.0)
            
            # Keep running music spectrum until state changes
            while self.current_state == ComposerState.SINGLE_ACTIVE:
                await self._sleep_while_in_state(30)  # Check every 30 seconds
    
    async def _couple_feedback_loop(self):
        """Red/purple strobe then fade to black"""
        # Generate red-purple edge-biased color
        red = Color(255, 0, 0)
        purple = Color(255, 0, 255)
        color = self._generate_edge_biased_color(red, purple)
        
        print("strobe")
        # Strobe with configurable parameters
        await self.controller.trigger_strobe(
            self.parameters['couple_strobe_frequency'], 
            self.parameters['strobe_duration'], 
            color
        )
        
        print("strobe complete, fading to black")
        # Create a custom fade recipe with the exact strobe color as source
        # Use remaining time as fade duration
        remaining_time = self.parameters['feedback_timeout'] - self.parameters['strobe_duration']  # Total timeout minus strobe time
        fade_recipe = self._create_fade_from_color_recipe(color, Color(0, 0, 0), remaining_time)
        await self.recipe_manager.apply_recipe(fade_recipe, transition_time=0.0)
        print("fade recipe applied - fading from strobe color to black")
        
        # Wait for remaining time
        print("waiting for timeout...")
        await self._sleep_while_in_state(remaining_time)  # Wait for fade to complete
        print("timeout complete")
        
        # Auto-transition to not_active after recipe finishes
        if self.current_state == ComposerState.COUPLE_FEEDBACK:
            print("🔄 Transitioning from COUPLE_FEEDBACK to NOT_ACTIVE")
            await self.set_state(ComposerState.NOT_ACTIVE)
        else:
            print(f"⚠️ Current state is {self.current_state}, not COUPLE_FEEDBACK")
    
    async def _couple_active_state_loop(self):
        """Euphoric red/pink/purple patterns"""
        while self.current_state == ComposerState.COUPLE_ACTIVE:
            # Fire demo for 35 seconds
            await self._load_recipe("fire_demo", transition_time=2.5)
            await self._sleep_while_in_state(35)
            
            if self.current_state != ComposerState.COUPLE_ACTIVE:
                break
                
            # Lava lamp for 30 seconds
            await self._load_recipe("lava_lamp", transition_time=3.0)
            await self._sleep_while_in_state(30)
            
            if self.current_state != ComposerState.COUPLE_ACTIVE:
                break
                
            # Power bars for 40 seconds
            await self._load_recipe("power_bars", transition_time=2.0)
            await self._sleep_while_in_state(40)
    
    async def _advertise_loop(self):
        """High-energy attention-grabbing patterns for 3 seconds"""
        import random
        scanner_recipes = ["scanner", "circle_scanner"]
        recipe = random.choice(scanner_recipes)
        await self._load_recipe(recipe, transition_time=0.1)
        await self._sleep_while_in_state(self.advertise_duration)
        
        # Auto-transition back to idle
        if self.current_state == ComposerState.ADVERTISE:
            await self.set_state(ComposerState.IDLE)
    
    async def _manual_loop(self):
        """Manual mode - just wait until state changes"""
        while self.current_state == ComposerState.MANUAL:
            await asyncio.sleep(1.0)
    
    async def _sleep_while_in_state(self, duration: float):
        """Sleep for duration but wake up if state changes"""
        end_time = time.time() + duration
        while time.time() < end_time and self.running:
            if self.current_state != getattr(self, '_sleep_state', self.current_state):
                break
            await asyncio.sleep(0.5)  # Check every 500ms
        
        # Check for auto-transitions during sleep
        await self._check_auto_transitions()
    
    def _create_fade_to_black_recipe(self, start_color):
        """Create a recipe that fades from start_color to black"""
        from recipe_manager import Recipe, BaseColorConfig, EffectConfig, TransitionMode
        from led_controller import Color
        
        return Recipe(
            name="Fade to Black",
            description="Fade from color to black",
            base_colors=BaseColorConfig(
                colors=[start_color, Color(0, 0, 0)],  # Start color to black
                mode=TransitionMode.FADE,
                speed=0.4  # Slow fade
            ),
            effects=[]  # No additional effects
        )
    
    async def _not_active_loop(self):
        """Not active state - stays black until instructed otherwise"""
        # Create a black recipe and apply it
        from led_controller import Color
        black_recipe = self._create_solid_color_recipe(Color(0, 0, 0))
        await self.recipe_manager.apply_recipe(black_recipe, transition_time=1.0)
        print("🖤 NOT_ACTIVE: Set to black")
        
        # Stay in this state indefinitely until manually changed
        while self.current_state == ComposerState.NOT_ACTIVE:
            await asyncio.sleep(0.01)  # 10ms response time when LEDs are off
    
    def _create_fade_from_color_recipe(self, source_color, target_color, duration):
        """Create a recipe that sets source color then fades to target color"""
        from recipe_manager import Recipe, BaseColorConfig, EffectConfig, TransitionMode
        
        return Recipe(
            name="Fade From Color",
            description=f"Set source color then fade to target over {duration}s",
            base_colors=BaseColorConfig(
                colors=[source_color],  # Set exact source color first
                mode=TransitionMode.STATIC
            ),
            effects=[
                EffectConfig("fade_to_color", {"target_color": target_color, "duration": duration})
            ]
        )
    
    def _create_solid_color_recipe(self, color):
        """Create a recipe with solid color"""
        from recipe_manager import Recipe, BaseColorConfig, TransitionMode
        
        return Recipe(
            name="Solid Color",
            description="Solid color display",
            base_colors=BaseColorConfig(
                colors=[color],
                mode=TransitionMode.STATIC
            ),
            effects=[]
        )
    
    async def _check_auto_transitions(self):
        """Check for automatic state transitions"""
        # Skip auto-advertise if timeout is 0 (disabled)
        if self.auto_advertise_timeout == 0.0:
            return
            
        elapsed_since_activity = time.time() - self.last_activity_time
        
        # Auto-transition to advertise after inactivity from any state
        if elapsed_since_activity > self.auto_advertise_timeout:
            await self.set_state(ComposerState.ADVERTISE)

    
    async def _load_recipe(self, recipe_name: str, transition_time: float = 2.0):
        """Load a recipe with smooth transition"""
        from recipe_manager import RECIPES
        if recipe_name not in RECIPES:
            raise ValueError(f"Recipe '{recipe_name}' not found in RECIPES")
        
        recipe = RECIPES[recipe_name]
        print(f"🎵 Loading recipe: {recipe_name} (transition: {transition_time}s)")
        await self.recipe_manager.apply_recipe(recipe, transition_time)


class LEDComposerProcess(LEDComposerInterface):
    """Multi-process LED Composer implementation"""
    
    def __init__(self, tree_config_path: str, force_simulation: bool = False):
        self.tree_config_path = tree_config_path
        self.force_simulation = force_simulation
        self.command_queue = multiprocessing.Queue()
        self.response_queue = multiprocessing.Queue()
        self.process = None
        self._current_state = ComposerState.IDLE
    
    async def start(self):
        """Start the LED composer in separate process"""
        print("🚀 Starting LED Composer (multi-process)...")
        self.process = multiprocessing.Process(
            target=self._run_in_process,
            args=(self.tree_config_path, self.force_simulation, self.command_queue, self.response_queue)
        )
        self.process.start()
        print("✅ LED Composer process started")
    
    async def stop(self):
        """Stop the LED composer process"""
        if self.process:
            self.command_queue.put(('stop',))
            self.process.join(timeout=5.0)
            if self.process.is_alive():
                self.process.terminate()
            print("✅ LED Composer process stopped")
    
    async def set_state(self, new_state: ComposerState):
        """Send state change command to process"""
        self.command_queue.put(('set_state', new_state))
        self._current_state = new_state
    
    def get_current_state(self) -> ComposerState:
        """Get cached current state"""
        return self._current_state
    
    async def set_manual_recipe(self, recipe_name: str):
        """Send manual recipe command to process"""
        self.command_queue.put(('set_manual_recipe', recipe_name))
        self._current_state = ComposerState.MANUAL
    
    @staticmethod
    def _run_in_process(tree_config_path: str, force_simulation: bool, command_queue, response_queue):
        """Run LED composer in separate process"""
        async def process_main():
            composer = LEDComposer(tree_config_path, force_simulation)
            await composer.start()
            
            try:
                while True:
                    # Check for commands
                    try:
                        command = command_queue.get_nowait()
                        if command[0] == 'stop':
                            break
                        elif command[0] == 'set_state':
                            await composer.set_state(command[1])
                        elif command[0] == 'set_manual_recipe':
                            await composer.set_manual_recipe(command[1])
                    except:
                        pass  # No command available
                    
                    await asyncio.sleep(0.1)
                    
            finally:
                await composer.stop()
        
        asyncio.run(process_main())


def create_led_composer(tree_config_path: str, force_simulation: bool = False, separate_process: bool = False) -> LEDComposerInterface:
    """Factory function to create appropriate LEDComposer implementation"""
    if separate_process:
        return LEDComposerProcess(tree_config_path, force_simulation)
    else:
        return LEDComposer(tree_config_path, force_simulation)


async def demo():
    """Demo function showing LED Composer usage"""
    composer = create_led_composer("tree_config.yaml", force_simulation=True, separate_process=False)
    
    try:
        await composer.start()
        
        # Simulate user interactions
        print("🧪 Testing state transitions...")
        
        await asyncio.sleep(2)
        await composer.set_state(ComposerState.SINGLE_FEEDBACK)
        
        await asyncio.sleep(5)  # Should auto-transition to SINGLE_ACTIVE
        
        await asyncio.sleep(3)
        await composer.set_state(ComposerState.COUPLE_FEEDBACK)
        
        await asyncio.sleep(5)  # Should auto-transition to COUPLE_ACTIVE
        
        await asyncio.sleep(3)
        await composer.set_manual_recipe("custom_pattern")
        
        await asyncio.sleep(5)
        await composer.set_state(ComposerState.IDLE)
        
        # Let it run for a bit
        await asyncio.sleep(10)
        
    except KeyboardInterrupt:
        print("\n🎨 LED Composer demo interrupted")
    finally:
        await composer.stop()


if __name__ == "__main__":
    asyncio.run(demo())
