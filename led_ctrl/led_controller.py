import asyncio
import time
import math
import random
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional, Callable, Dict, Any
import colorsys
from .colors_array import Colors

# Configuration
BREATHING_MIN_INTENSITY = 0.2  # Minimum intensity for breathing animation (0.0 = fully off, 1.0 = full brightness)

# Try to import real neopixel, fall back to mock
try:
    import board
    import neopixel
    SIMULATION_MODE = False
except ImportError:
    # Import mock modules
    from .mock_neopixel import MockNeoPixel as neopixel_class, MockBoard as board
    neopixel = type('neopixel', (), {'NeoPixel': neopixel_class})
    SIMULATION_MODE = True

class TransitionType(Enum):
    CUTOFF = "cutoff"
    FADE = "fade"

class AnimationType(Enum):
    SOLID = "solid"
    RAINBOW = "rainbow"
    RAINBOW_CYCLE = "rainbow_cycle"
    COLOR_WIPE = "color_wipe"
    THEATER_CHASE = "theater_chase"
    BREATHING = "breathing"
    TWINKLE = "twinkle"
    FIRE = "fire"
    MUSIC_REACTIVE = "music_reactive"
    RED_PINK_FLASH = "red_pink_flash"

@dataclass
class Color:
    r: int
    g: int
    b: int
    
    def __post_init__(self):
        self.r = max(0, min(255, self.r))
        self.g = max(0, min(255, self.g))
        self.b = max(0, min(255, self.b))
    
    def to_tuple(self) -> Tuple[int, int, int]:
        return (self.r, self.g, self.b)
    
    def blend(self, other: 'Color', ratio: float) -> 'Color':
        """Blend with another color. ratio=0 is self, ratio=1 is other"""
        return Color(
            int(self.r + (other.r - self.r) * ratio),
            int(self.g + (other.g - self.g) * ratio),
            int(self.b + (other.b - self.b) * ratio)
        )
    
    @classmethod
    def from_hsv(cls, h: float, s: float, v: float) -> 'Color':
        """Create color from HSV values (0-1 range)"""
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return cls(int(r * 255), int(g * 255), int(b * 255))

@dataclass
class Animation:
    animation_type: AnimationType
    colors: Colors
    duration: float = 5.0  # seconds
    speed: float = 1.0     # animation speed multiplier
    intensity: float = 1.0  # brightness multiplier
    reverse: bool = False
    params: Dict[str, Any] = None

@dataclass
class Program:
    animations: List[Animation]
    transitions: List[TransitionType]
    loop: bool = True

class LEDController:
    """Unified LED controller that works with real or simulated LEDs"""
    
    def __init__(self, 
                 num_pixels: int,
                 pin: int = 18,
                 brightness: float = 1.0,
                 force_simulation: bool = False):
        
        self.num_pixels = num_pixels
        self.brightness = brightness
        self.current_pixels = Colors(num_pixels)
        
        # Initialize NeoPixel (real or mock)
        if force_simulation or SIMULATION_MODE:
            print("Using LED simulation mode")
            self.pixels = neopixel.NeoPixel(pin, num_pixels, brightness=brightness, auto_write=False)
        else:
            print("Using real LED hardware")
            self.pixels = neopixel.NeoPixel(
                getattr(board, f'D{pin}'), 
                num_pixels, 
                brightness=brightness,
                auto_write=False
            )
        
        # Control state
        self.running = False
        self.current_program: Optional[Program] = None
        self.animation_task: Optional[asyncio.Task] = None
        
    async def start(self) -> None:
        """Start the LED controller"""
        self.running = True
        
    async def stop(self) -> None:
        """Stop the LED controller"""
        self.running = False
        if self.animation_task:
            self.animation_task.cancel()
            try:
                await self.animation_task
            except asyncio.CancelledError:
                pass
        self.pixels.deinit()
    
    async def set_program(self, 
                         program: Program, 
                         transition: TransitionType = TransitionType.CUTOFF) -> None:
        """Set a new program with optional transition"""
        
        if self.animation_task:
            self.animation_task.cancel()
        
        self.current_program = program
        self.animation_task = asyncio.create_task(
            self._run_program(program, transition)
        )
    
    async def _run_program(self, 
                          program: Program, 
                          transition: TransitionType) -> None:
        """Run a program with animations and transitions"""
        
        animation_index = 0
        
        while self.running and program == self.current_program:
            animation = program.animations[animation_index]
            next_animation_index = (animation_index + 1) % len(program.animations)
            next_animation = (program.animations[next_animation_index] 
                            if len(program.animations) > 1 else None)
            
            # Get transition type for this animation
            transition_type = (program.transitions[animation_index] 
                             if animation_index < len(program.transitions) 
                             else TransitionType.CUTOFF)
            
            await self._execute_animation(animation, next_animation, transition_type)
            
            animation_index = next_animation_index
            if not program.loop and animation_index == 0:
                break
    
    async def _execute_animation(self, 
                               animation: Animation, 
                               next_animation: Optional[Animation],
                               transition: TransitionType) -> None:
        """Execute a single animation"""
        
        start_time = time.time()
        
        while time.time() - start_time < animation.duration and self.running:
            elapsed = time.time() - start_time
            progress = elapsed / animation.duration
            
            # Calculate animation colors
            animation_colors = self._calculate_animation_colors(animation, elapsed)
            
            # Apply transition if we're near the end and have a next animation
            if (next_animation and transition == TransitionType.FADE and 
                progress > 0.8):  # Start transition in last 20%
                transition_progress = (progress - 0.8) / 0.2
                next_colors = self._calculate_animation_colors(next_animation, 0)
                
                for i in range(len(animation_colors)):
                    animation_colors[i] = animation_colors[i].blend(
                        next_colors[i], transition_progress)
            
            # Update pixels
            self.current_pixels = animation_colors
            for i, color in enumerate(animation_colors):
                if i < len(self.pixels):
                    self.pixels[i] = color.to_tuple()
            
            self.pixels.show()
            await asyncio.sleep(1/60)  # 60 FPS
    
    def _calculate_animation_colors(self, animation: Animation, elapsed: float) -> Colors:
        """Calculate colors for an animation at given time"""
        
        if animation.animation_type == AnimationType.SOLID:
            return self._solid_animation(animation)
        
        elif animation.animation_type == AnimationType.RAINBOW:
            return self._rainbow_animation(animation, elapsed)
        
        elif animation.animation_type == AnimationType.RAINBOW_CYCLE:
            return self._rainbow_cycle_animation(animation, elapsed)
        
        elif animation.animation_type == AnimationType.COLOR_WIPE:
            return self._color_wipe_animation(animation, elapsed)
        
        elif animation.animation_type == AnimationType.THEATER_CHASE:
            return self._theater_chase_animation(animation, elapsed)
        
        elif animation.animation_type == AnimationType.BREATHING:
            return self._breathing_animation(animation, elapsed)
        
        elif animation.animation_type == AnimationType.TWINKLE:
            return self._twinkle_animation(animation, elapsed)
        
        elif animation.animation_type == AnimationType.FIRE:
            return self._fire_animation(animation, elapsed)
        
        elif animation.animation_type == AnimationType.RED_PINK_FLASH:
            return self._red_pink_flash_animation(animation, elapsed)
        
        return Colors(self.num_pixels)
    
    def _solid_animation(self, animation: Animation) -> Colors:
        """Solid color animation"""
        if not animation.colors:
            return Colors(self.num_pixels)
        
        colors = []
        for i in range(self.num_pixels):
            color_index = i % len(animation.colors)
            base_color = animation.colors[color_index]
            colors.append(Color(
                int(base_color.r * animation.intensity),
                int(base_color.g * animation.intensity),
                int(base_color.b * animation.intensity)
            ))
        return colors
    
    def _rainbow_animation(self, animation: Animation, elapsed: float) -> Colors:
        """Static rainbow across all pixels"""
        colors = []
        for i in range(self.num_pixels):
            hue = i / self.num_pixels
            color = Color.from_hsv(hue, 1.0, animation.intensity)
            colors.append(color)
        return colors
    
    def _rainbow_cycle_animation(self, animation: Animation, elapsed: float) -> Colors:
        """Cycling rainbow animation"""
        colors = []
        cycle_offset = (elapsed * animation.speed) % 1.0
        
        for i in range(self.num_pixels):
            hue = (i / self.num_pixels + cycle_offset) % 1.0
            color = Color.from_hsv(hue, 1.0, animation.intensity)
            colors.append(color)
        return colors
    
    def _color_wipe_animation(self, animation: Animation, elapsed: float) -> Colors:
        """Color wipe animation"""
        if not animation.colors:
            return Colors(self).num_pixels
        
        colors = Colors(self).num_pixels
        
        # Calculate how many pixels should be lit
        cycle_time = 2.0 / animation.speed  # 2 seconds per cycle
        cycle_progress = (elapsed % cycle_time) / cycle_time
        
        if cycle_progress < 0.5:
            # Wipe forward
            lit_pixels = int(cycle_progress * 2 * self.num_pixels)
            color = animation.colors[0]
            for i in range(min(lit_pixels, self.num_pixels)):
                colors[i] = Color(
                    int(color.r * animation.intensity),
                    int(color.g * animation.intensity),
                    int(color.b * animation.intensity)
                )
        else:
            # Wipe backward (clear)
            clear_progress = (cycle_progress - 0.5) * 2
            lit_pixels = int((1 - clear_progress) * self.num_pixels)
            color = animation.colors[0]
            for i in range(lit_pixels):
                colors[i] = Color(
                    int(color.r * animation.intensity),
                    int(color.g * animation.intensity),
                    int(color.b * animation.intensity)
                )
        
        return colors
    
    def _theater_chase_animation(self, animation: Animation, elapsed: float) -> Colors:
        """Theater chase animation"""
        if not animation.colors:
            return Colors(self).num_pixels
        
        colors = Colors(self).num_pixels
        chase_speed = animation.speed * 10  # Make it faster
        offset = int(elapsed * chase_speed) % 3
        
        color = animation.colors[0]
        for i in range(self.num_pixels):
            if i % 3 == offset:
                colors[i] = Color(
                    int(color.r * animation.intensity),
                    int(color.g * animation.intensity),
                    int(color.b * animation.intensity)
                )
        
        return colors
    
    def _breathing_animation(self, animation: Animation, elapsed: float) -> Colors:
        """Breathing animation with sinusoidal intensity"""
        if not animation.colors:
            return Colors(self).num_pixels
        
        # Use squared sine wave for more time at higher intensities
        raw_sine = (math.sin(elapsed * animation.speed * 2 * math.pi) + 1) / 2
        breath_intensity = raw_sine * raw_sine  # Square it to spend more time bright
        final_intensity = animation.intensity * (BREATHING_MIN_INTENSITY + (1 - BREATHING_MIN_INTENSITY) * breath_intensity)
        
        colors = []
        for i in range(self.num_pixels):
            color_index = i % len(animation.colors)
            base_color = animation.colors[color_index]
            colors.append(Color(
                int(base_color.r * final_intensity),
                int(base_color.g * final_intensity),
                int(base_color.b * final_intensity)
            ))
        return colors
    
    def _twinkle_animation(self, animation: Animation, elapsed: float) -> Colors:
        """Twinkle animation with random sparkles"""
        if not animation.colors:
            return Colors(self).num_pixels
        
        colors = []
        base_color = animation.colors[0]
        
        for i in range(self.num_pixels):
            # Base dim color
            dim_intensity = animation.intensity * 0.1
            
            # Random twinkle
            if random.random() < 0.05 * animation.speed:  # 5% chance per frame
                twinkle_intensity = animation.intensity
            else:
                twinkle_intensity = dim_intensity
            
            colors.append(Color(
                int(base_color.r * twinkle_intensity),
                int(base_color.g * twinkle_intensity),
                int(base_color.b * twinkle_intensity)
            ))
        
        return colors
    
    def _fire_animation(self, animation: Animation, elapsed: float) -> Colors:
        """Fire animation with flickering orange/red colors"""
        colors = []
        
        # Use speed to control flicker rate
        flicker_seed = int(elapsed * animation.speed * 10)  # Slower changes with lower speed
        random.seed(flicker_seed)  # Consistent flicker based on time and speed
        
        for i in range(self.num_pixels):
            # Create flickering fire effect
            flicker = random.uniform(0.5, 1.0)
            heat = random.uniform(0.7, 1.0) * animation.intensity * flicker
            
            # Fire colors: red to orange to yellow
            if heat < 0.3:
                # Dark red
                colors.append(Color(int(255 * heat * 3), 0, 0))
            elif heat < 0.6:
                # Red to orange
                colors.append(Color(255, int(255 * (heat - 0.3) * 3), 0))
            else:
                # Orange to yellow
                colors.append(Color(255, 255, int(255 * (heat - 0.6) * 2.5)))
        
        return colors

    def _red_pink_flash_animation(self, animation: Animation, elapsed: float) -> Colors:
        """Red-pink breathing with single random LED flash"""
        colors = []
        
        # Slow breathing between red and pink
        breath_intensity = (math.sin(elapsed * animation.speed * 2 * math.pi) + 1) / 2
        breath_intensity = breath_intensity * breath_intensity  # Square for more time bright
        final_intensity = animation.intensity * (BREATHING_MIN_INTENSITY + (1 - BREATHING_MIN_INTENSITY) * breath_intensity)
        
        # Base colors: red and pink (no white in base)
        red = Color(255, 0, 0)
        pink = Color(255, 192, 203)
        base_color = red.blend(pink, breath_intensity)
        
        # Apply base breathing color to all LEDs
        for i in range(self.num_pixels):
            colors.append(Color(
                int(base_color.r * final_intensity),
                int(base_color.g * final_intensity),
                int(base_color.b * final_intensity)
            ))
        
        # Flash one random LED more frequently (every 0.2 seconds) for 10ms
        flash_cycle = elapsed % 0.2  # 0.2 second cycle = 5Hz
        if flash_cycle < 0.01:  # First 10ms of each cycle
            # Pick a random LED to flash (use elapsed to seed for consistency)
            random.seed(int(elapsed * 10))  # More variation in seed
            flash_led = random.randint(0, self.num_pixels - 1)
            colors[flash_led] = Color(255, 255, 255)  # White flash
        
        return colors

# Helper functions to create common programs
def create_rainbow_program() -> Program:
    """Create a rainbow cycling program"""
    animations = [
        Animation(AnimationType.RAINBOW_CYCLE, [], 10.0, speed=0.5)
    ]
    return Program(animations, [TransitionType.CUTOFF], loop=True)

def create_color_wipe_program(colors: Colors) -> Program:
    """Create a color wipe program"""
    animations = []
    for color in colors:
        animations.append(Animation(AnimationType.COLOR_WIPE, [color], 3.0, speed=1.0))
    
    transitions = [TransitionType.CUTOFF] * len(animations)
    return Program(animations, transitions, loop=True)

def create_theater_chase_program(colors: Colors) -> Program:
    """Create a theater chase program"""
    animations = []
    for color in colors:
        animations.append(Animation(AnimationType.THEATER_CHASE, [color], 4.0, speed=1.0))
    
    transitions = [TransitionType.CUTOFF] * len(animations)
    return Program(animations, transitions, loop=True)

def create_breathing_program(colors: Colors) -> Program:
    """Create a breathing program"""
    animations = []
    for color in colors:
        animations.append(Animation(AnimationType.BREATHING, [color], 6.0, speed=0.15))
    
    transitions = [TransitionType.FADE] * len(animations)
    return Program(animations, transitions, loop=True)

def create_fire_program() -> Program:
    """Create a fire effect program"""
    animations = [
        Animation(AnimationType.FIRE, [], 15.0, speed=0.3, intensity=0.8)
    ]
    return Program(animations, [TransitionType.CUTOFF], loop=True)

def create_red_pink_flash_program() -> Program:
    """Create red-pink breathing with flash program"""
    animations = [
        Animation(AnimationType.RED_PINK_FLASH, [], 20.0, speed=0.1, intensity=0.9)
    ]
    return Program(animations, [TransitionType.CUTOFF], loop=True)

# Example usage
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='LED Controller Demo')
    parser.add_argument('--simulate', action='store_true', 
                       help='Force simulation mode even if hardware is available')
    parser.add_argument('--pixels', type=int, default=100,
                       help='Number of LED pixels (default: 100)')
    parser.add_argument('--pin', type=int, default=18,
                       help='GPIO pin number (default: 18)')
    parser.add_argument('--brightness', type=float, default=0.8,
                       help='LED brightness 0.0-1.0 (default: 0.8)')
    
    args = parser.parse_args()
    
    # Create controller
    controller = LEDController(
        num_pixels=args.pixels,
        pin=args.pin,
        brightness=args.brightness,
        force_simulation=args.simulate
    )
    
    await controller.start()
    
    try:
        # Rainbow cycle
        print("Running rainbow cycle...")
        rainbow_program = create_rainbow_program()
        await controller.set_program(rainbow_program)
        await asyncio.sleep(10)
        
        # Color wipe
        print("Running color wipe...")
        colors = [Color(255, 0, 0), Color(0, 255, 0), Color(0, 0, 255)]
        wipe_program = create_color_wipe_program(colors)
        await controller.set_program(wipe_program, TransitionType.FADE)
        await asyncio.sleep(15)
        
        # Theater chase
        print("Running theater chase...")
        chase_colors = [Color(255, 255, 255), Color(255, 0, 0), Color(0, 0, 255)]
        chase_program = create_theater_chase_program(chase_colors)
        await controller.set_program(chase_program, TransitionType.FADE)
        await asyncio.sleep(15)
        
        # Fire effect
        print("Running fire effect...")
        fire_program = create_fire_program()
        await controller.set_program(fire_program, TransitionType.FADE)
        await asyncio.sleep(10)
        
    except KeyboardInterrupt:
        print("Interrupted by user")
    
    await controller.stop()

if __name__ == "__main__":
    asyncio.run(main())
