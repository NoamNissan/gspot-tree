#!/usr/bin/env python3
"""
LED Composer - High-level LED control for interactive tree
Manages state-based LED patterns and recipe transitions
"""

import asyncio
import time
import random
import math
import select
from .led_controller import Color
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional
import multiprocessing

from .pipeline_demo import PipelineController, TreeStructure
from .recipe_manager import RecipeManager, EffectConfig, FloatRange, ChoiceRange
from .tree_config import load_tree_config


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

    # Non basic states
    BIRTHDAY = "birthday"
    BAD_SONGS = "bad_songs"
    STARWARS = "starwars"


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
        self.recipe_manager = RecipeManager(self.controller, tree_structure)
        
        # State management
        self.current_state = ComposerState.IDLE
        self.state_start_time = time.time()
        self.last_activity_time = time.time()
        
        # Control flags
        self.running = False
        self.controller_task = None
        self.recipe_task = None
        
        # State configuration
        self.advertise_duration_limit = 30.0       # 
        self.feedback_timeout = 5.0          # Default feedback timeout
        self.strobe_duration = 1.0           # Default strobe duration
        
        # Parameter system - organized by state but flattened
        self.parameters = {
            # Flow
            'long_recipe_time': 45,
            'long_recipe_transition': 10,
            'short_recipe_time': 20,
            'short_recipe_transition': 5,

            # Debug
            'time_factor': 1,

            # General parameters (affect multiple states)
            'feedback_timeout': 5.0,
            'strobe_duration': 1.0,
            'strobe_frequency': 15.0,
            'strobe_duty_cycle': 0.25,
            
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

        if 'list' in kwargs and isinstance(kwargs['list'], ComposerState):
            new_state = kwargs['list']

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
            elif self.current_state == ComposerState.BIRTHDAY:
                await self._birthday_state_loop()
            elif self.current_state == ComposerState.BAD_SONGS:
                await self._bad_songs_state_loop()
            elif self.current_state == ComposerState.STARWARS:
                await self._starwars_state_loop()
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
    
    def _get_long_transition_recipe_times(self):
        factor = self.parameters['time_factor']
        transition_time = self.parameters['long_recipe_transition'] * factor
        long_recipe_time = self.parameters['long_recipe_time'] * factor

        return long_recipe_time, transition_time

    def _get_short_transition_recipe_times(self):
        factor = self.parameters['time_factor']
        transition_time = self.parameters['short_recipe_transition'] * factor
        short_recipe_time = self.parameters['short_recipe_time'] * factor
        return short_recipe_time, transition_time


    async def _play_recipe_playlist(self, recipes, state):
        """Play a randomized playlist of recipes while in given state"""
        while self.current_state == state:
            # Shuffle recipes but keep sequences intact
            random.shuffle(recipes)
            
            for item in recipes:
                if self.current_state != state:
                    break
                    
                if isinstance(item, list):
                    # Play sequence in order
                    for recipe_name, trans, duration in item:
                        await self._load_recipe(recipe_name, trans)
                        await self._sleep_while_in_state(duration)
                else:
                    # Single recipe
                    recipe_name, trans, duration = item
                    await self._load_recipe(recipe_name, trans)
                    await self._sleep_while_in_state(duration)

    # State-specific loops (each runs until state changes)
    async def _idle_state_loop(self):
        """Calm, serene patterns with slow changes"""
        long_recipe_time, transition_time = self._get_long_transition_recipe_times()
        
        # Define recipe playlist - tuples are (recipe_name, transition, duration)
        # Lists are sequences that play together
        recipes = [
            ("digital_rain", transition_time, long_recipe_time),
            ("ring_ripple", transition_time, long_recipe_time),
            [  # This sequence stays together
                ("rainbow_vortex", 5, long_recipe_time/3),
                ("rainbow_vortex_anti", 5, long_recipe_time/3),
                ("rainbow_blackout", 0, long_recipe_time/3),
            ],
            ("rainbow_rings", transition_time, long_recipe_time),
            ("ring_ripple", transition_time, long_recipe_time),
            ("sunset_breathing", transition_time, long_recipe_time),
            ("water_ripples", transition_time, long_recipe_time),
            ("fade_cycle", transition_time, long_recipe_time),
            ("fire_demo", transition_time, long_recipe_time),
            ("lava_lamp", transition_time/2, long_recipe_time/3),
            ("power_bars", transition_time, long_recipe_time),
            ("pair_blender", transition_time, long_recipe_time),
        ]
        
        await self._play_recipe_playlist(recipes, ComposerState.IDLE)

    async def _birthday_state_loop(self):
        short_recipe_time, transition_time = self._get_short_transition_recipe_times()
        await self._load_recipe("music_pulse_rainbow", 1.0)
        await self._sleep_while_in_state(short_recipe_time)

        await self._load_recipe("music_pulse_colors", 1.0)
        await self._sleep_while_in_state(short_recipe_time)
        
        # Auto-transition to single active
        await self.set_state(ComposerState.SINGLE_ACTIVE)

    async def _bad_songs_state_loop(self):
        short_recipe_time, transition_time = self._get_short_transition_recipe_times()
        # TODO: implement bad songs playlist
        await self._load_recipe("music_pulse_bad", transition_time)
        await self._sleep_while_in_state(short_recipe_time)
        await self.set_state(ComposerState.SINGLE_ACTIVE)

    async def _starwars_state_loop(self):
        short_recipe_time, transition_time = self._get_short_transition_recipe_times()
        await self._load_recipe("music_pulse_blue", transition_time)
        await self._sleep_while_in_state(short_recipe_time)
    
        await self.set_state(ComposerState.SINGLE_ACTIVE)
    
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

    async def _strobe_and_fade_feedback(self, color1, color2, current_state, next_state):
        """Strobe with edge-biased color then fade to black"""
        color = self._generate_edge_biased_color(color1, color2)
        
        # Strobe with configurable parameters
        await self.controller.trigger_strobe(
            self.parameters['strobe_frequency'], 
            self.parameters['strobe_duration'], 
            color
        )
        
        print("strobe complete, fading to black")
        remaining_time = self.parameters['feedback_timeout'] - self.parameters['strobe_duration']
        fade_recipe = self._create_fade_from_color_recipe(color, Color(0, 0, 0), remaining_time)
        await self.recipe_manager.apply_recipe(fade_recipe, transition_time=0.0)
        print("fade recipe applied - fading from strobe color to black")

        print("waiting for timeout...")
        await self._sleep_while_in_state(remaining_time)
        print("timeout complete")
        
        if self.current_state == current_state:
            print(f"🔄 Transitioning from {current_state} to {next_state}")
            await self.set_state(next_state)
        else:
            print(f"⚠️ Current state is {self.current_state}, not {current_state}")

    async def _single_feedback_loop(self):
        """Blue/cyan strobe for 2s then fade to black"""
        blue = Color(0, 0, 255)
        cyan = Color(0, 255, 255)
        await self._strobe_and_fade_feedback(blue, cyan, ComposerState.SINGLE_FEEDBACK, ComposerState.NOT_ACTIVE)
    
    async def _single_active_state_loop(self):
        """Happy, energetic music-reactive patterns"""
        short_recipe_time, transition_time = self._get_short_transition_recipe_times()
        
        recipes = [
            ("smart_music_spectrum", transition_time, short_recipe_time),
            ("music_pulse", transition_time, short_recipe_time),
            ("smart_spectrum_enhanced", transition_time, short_recipe_time),
        ]
        
        await self._play_recipe_playlist(recipes, ComposerState.SINGLE_ACTIVE)


    async def _couple_feedback_loop(self):
        """Red/purple strobe then fade to black"""
        red = Color(255, 0, 0)
        purple = Color(255, 0, 255)
        await self._strobe_and_fade_feedback(red, purple, ComposerState.COUPLE_FEEDBACK, ComposerState.NOT_ACTIVE)
    
    async def _couple_active_state_loop(self):
        """Euphoric red/pink/purple patterns"""
        short_recipe_time, transition_time = self._get_short_transition_recipe_times()
        
        recipes = [
            ("pink_smart_music_spectrum", transition_time, short_recipe_time),
            ("pink_smart_spectrum_enhanced", transition_time, short_recipe_time),
            ("music_pulse_couple", transition_time, short_recipe_time),
        ]
        
        await self._play_recipe_playlist(recipes, ComposerState.COUPLE_ACTIVE)
                
    async def _advertise_loop(self):
        """High-energy attention-grabbing patterns for 3 seconds"""
        import random
        scanner_recipes = ["scanner", "circle_scanner","complex_demo","glitch_matrix","rainbow_vortex_alternating"]

        while self.current_state == ComposerState.ADVERTISE:
            recipe = random.choice(scanner_recipes)
            await self._load_recipe(recipe, transition_time=5)
            await self._sleep_while_in_state(10)


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
        
    def _create_fade_to_black_recipe(self, start_color):
        """Create a recipe that fades from start_color to black"""
        from .recipe_manager import Recipe, BaseColorConfig, EffectConfig, TransitionMode
        from .led_controller import Color
        
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
        from .led_controller import Color
        black_recipe = self._create_solid_color_recipe(Color(0, 0, 0))
        await self.recipe_manager.apply_recipe(black_recipe, transition_time=1.0)
        print("🖤 NOT_ACTIVE: Set to black")
        
        # Stay in this state indefinitely until manually changed
        while self.current_state == ComposerState.NOT_ACTIVE:
            await asyncio.sleep(0.01)  # 10ms response time when LEDs are off
    
    def _create_fade_from_color_recipe(self, source_color, target_color, duration):
        """Create a recipe that sets source color then fades to target color"""
        from .recipe_manager import Recipe, BaseColorConfig, EffectConfig, TransitionMode
        
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
        from .recipe_manager import Recipe, BaseColorConfig, TransitionMode
        
        return Recipe(
            name="Solid Color",
            description="Solid color display",
            base_colors=BaseColorConfig(
                colors=[color],
                mode=TransitionMode.STATIC
            ),
            effects=[]
        )

    
    async def _load_recipe(self, recipe_name: str, transition_time: float = 2.0):
        """Load a recipe with smooth transition"""
        from .recipe_manager import RECIPES
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
    """Demo function showing LED Composer usage with CLI input"""
    composer = create_led_composer("tree_config.yaml", force_simulation=True, separate_process=False)
    
    try:
        await composer.start()
        
        print("🧪 LED Composer CLI Test")
        print("Commands: birthday, bad_songs, starwars, idle, single, couple, quit")
        
        # Start input loop
        import sys
        loop = asyncio.get_event_loop()
        
        while True:
            # Non-blocking input
            await asyncio.sleep(0.1)
            
            # Check for input (simple approach)
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline().strip().lower()
                
                if line == 'quit':
                    break
                elif line == 'birthday':
                    await composer.set_state(ComposerState.SINGLE_ACTIVE, list=ComposerState.BIRTHDAY)
                elif line == 'bad_songs':
                    await composer.set_state(ComposerState.SINGLE_ACTIVE, list=ComposerState.BAD_SONGS)
                elif line == 'starwars':
                    await composer.set_state(ComposerState.SINGLE_ACTIVE, list=ComposerState.STARWARS)
                elif line == 'idle':
                    await composer.set_state(ComposerState.IDLE)
                elif line == 'single':
                    await composer.set_state(ComposerState.SINGLE_ACTIVE)
                elif line == 'couple':
                    await composer.set_state(ComposerState.COUPLE_ACTIVE)
                else:
                    print(f"Unknown command: {line}")
        
    except KeyboardInterrupt:
        print("\n🎨 LED Composer demo interrupted")
    finally:
        await composer.stop()


if __name__ == "__main__":
    asyncio.run(demo())
