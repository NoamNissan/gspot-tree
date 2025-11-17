#!/usr/bin/env python3
"""
Recipe System - Data-driven LED effect configurations with smart transitions
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import numpy as np
import time
try:
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    print("⚠️  Missing audio dependencies. Install with: pip install sounddevice numpy")
    AUDIO_AVAILABLE = False
    sd = None
import threading
import time
import socket
import json
from led_controller import Color
# Global audio configuration
STROBE_FREQ = 15.0     # Default strobe frequency

from constants import PERSISTENT_GUI_PORT
from audio_effects import AudioData, RealTimeAudioProvider, SAMPLING_RATE, MusicVisualizerEffect
from recipe_manager import BaseColorConfig, EffectConfig, Recipe, RecipeManager, RECIPES, LED_CRAWL_BLINK_DURATION, BANDS_OVERRIDE
from pipeline_demo import (
    PipelineController, TransitionMode, BreathingEffect, 
    StrobeEffect, ColorStrobeEffect, SparkleEffect, WaveEffect, RandomFlashEffect, RainbowEffect, LavaLampEffect,
    FireEffect, MeltEffect, FadeEffect, ScanEffect, CircleScanEffect, MarchingEffect, BlocksEffect,
    CrawlerEffect, WaterEffect, GlitchEffect, MetroEffect, PowerEffect, RainEffect, WalkingEffect,
    SpectrumEffect, EnergyEffect, WavelengthEffect, ScrollEffect, BarsEffect,
    BlendMode, Effect, PIPELINE_FPS
)

async def wait_for_input(force_simulation=False):

    timeout = 2

    """Wait for user input - polling method for simulation, simple method for embedded"""
    if force_simulation:
        sleep_interval = 0.1
        acc_seconds = 0
        # Simulation mode: use polling to avoid Tkinter conflicts
        import sys
        import select
        print("Press Enter to continue...")
        while True:
            if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                sys.stdin.readline()
                print("Continuing...")
                break
            await asyncio.sleep(sleep_interval)
            acc_seconds += sleep_interval
            if timeout and acc_seconds > timeout:
                return
    else:
        # Real hardware mode: use simple async input
        if timeout:
            await asyncio.sleep(timeout)
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, input, "Press Enter: ")



async def demo_recipe_transitions(num_pixels: int = 100, force_simulation: bool = False, tree_structure = None):
    """Demonstrate recipe transitions"""
    controller = PipelineController(num_pixels, force_simulation=force_simulation, tree_structure=tree_structure)
    await controller.start()
    
    try:
        # Start rendering loop
        render_task = asyncio.create_task(controller.run_loop())
        
        # Create recipe manager
        recipe_manager = RecipeManager(controller, tree_structure)
        
        print("🍽️ Recipe Transition Demo")
        print("Press Ctrl+C to stop at any time")
        
        # Ring ripple effect
        #await asyncio.sleep(6)
        
            # avoid white, rings not working due to tree structure, fix simultor to use configuration
        await recipe_manager.apply_recipe(RECIPES["ring_ripple"])
        await wait_for_input(force_simulation=force_simulation)


        # Branch sweep effect  

            # colors=[Color(50, 0, 0)],  # Very dark red base
            # EffectConfig("branch_sweep", {"speed": 1.0, "color": Color(255, 0, 0)})

            # colors=[Color(0, 0, 50)],  # Very dark red base
            # EffectConfig("branch_sweep", {"speed": 0.8, "color": Color(0, 0, 255)})

        await recipe_manager.apply_recipe(RECIPES["branch_sweep"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)
        

        
        # Rainbow rings effect
        await recipe_manager.apply_recipe(RECIPES["rainbow_rings"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)
        
        # Rainbow branches effect
        await recipe_manager.apply_recipe(RECIPES["rainbow_branches"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)
        
        # Rainbow vortex effect
            # need to do slower
        await recipe_manager.apply_recipe(RECIPES["rainbow_vortex"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)
        
        # Rainbow vortex alternating effect
            # good for music
        await recipe_manager.apply_recipe(RECIPES["rainbow_vortex_alternating"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)
        
        # Rainbow branches skewed effect
        await recipe_manager.apply_recipe(RECIPES["rainbow_branches_skewed"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)
        
        # Apply complex_demo

            # very messy can be like a strobe when you chip in
        await recipe_manager.apply_recipe(RECIPES["complex_demo"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)
        
        # Pure rainbow effect
        await recipe_manager.apply_recipe(RECIPES["rainbow"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)


        
        # Transition to sunset_breathing (breathing continues, other effects change)
        await recipe_manager.apply_recipe(RECIPES["sunset_breathing"], transition_time=3.0)
        await wait_for_input(force_simulation=force_simulation)
        
        # Transition to rainbow_wave

            # this one is not nice very messy
        await recipe_manager.apply_recipe(RECIPES["rainbow_wave"], transition_time=3.0)
        await wait_for_input(force_simulation=force_simulation)

        
        # LedFx-style spectrum analyzer
        await recipe_manager.apply_recipe(RECIPES["spectrum_analyzer"], transition_time=3.0)
        await wait_for_input(force_simulation=force_simulation)
        


        # Energy pulse effect
            # messy
        await recipe_manager.apply_recipe(RECIPES["energy_pulse"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)


        
        # Wavelength flow

            #nice! for music as transition
        await recipe_manager.apply_recipe(RECIPES["wavelength_flow"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)
    

        # Rainbow scroll
        await recipe_manager.apply_recipe(RECIPES["rainbow_scroll"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)


        # Frequency bars
            # too fast need a bit slower
        await recipe_manager.apply_recipe(RECIPES["frequency_bars"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)


        
        # New effects showcase
        print("🔥 Showcasing new effects...")

        # Circle scanner effect

            # epiliptic acts as stobe (good for short periods)
            # consider to make it not white 
        await recipe_manager.apply_recipe(RECIPES["circle_scanner"], transition_time=0.0)
        await wait_for_input(force_simulation=force_simulation)

        # Fire effect
        await recipe_manager.apply_recipe(RECIPES["fire_demo"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)
        

        # Scanner effect
            # also try
            # EffectConfig("scan", {"speed":0.5, "width": 3})

        await recipe_manager.apply_recipe(RECIPES["scanner"], transition_time=1.0)
        await wait_for_input(force_simulation=force_simulation)


        # Water ripples
        await recipe_manager.apply_recipe(RECIPES["water_ripples"], transition_time=4.0)
        await wait_for_input(force_simulation=force_simulation)


        # Glitch matrix
        # need to make glitch duration much much shorter as opposed to the breathing
        await recipe_manager.apply_recipe(RECIPES["glitch_matrix"], transition_time=1.0)
        await wait_for_input(force_simulation=force_simulation)



        
        # Digital rain
            # cool check if can make dropets more blue
        await recipe_manager.apply_recipe(RECIPES["digital_rain"], transition_time=2.0)
        await wait_for_input(force_simulation=force_simulation)
        

        # Music spectrum analyzer
            # cool but need more to bit lit and less to flicker (increase normaliztion time)
        await recipe_manager.apply_recipe(RECIPES["smart_music_spectrum"], transition_time=3.0)
        await wait_for_input(force_simulation=force_simulation)
        
        # Music spectrum analyzer
            #messy
        await recipe_manager.apply_recipe(RECIPES["music_spectrum_c"], transition_time=3.0)
        await wait_for_input(force_simulation=force_simulation)



        # Enhanced spectrum analyzer
            #messy
        await recipe_manager.apply_recipe(RECIPES["spectrum_enhanced_c"], transition_time=3.0)
        await wait_for_input(force_simulation=force_simulation)
        
        # Enhanced spectrum analyzer with 9 bands
            # ok but 3 is best
        await recipe_manager.apply_recipe(RECIPES["spectrum_enhanced_9"], transition_time=3.0)
        await wait_for_input(force_simulation=force_simulation)
        
        # Music pulse effect
            # flickery but cool
        await recipe_manager.apply_recipe(RECIPES["music_pulse"], transition_time=3.0)
        await wait_for_input(force_simulation=force_simulation)
        

        # Stroboscopic demo: Blue/Magenta breathing vs Direct white strobe
        print("🔥 Starting stroboscopic demo...")
        
        # Stroboscopic cycle: 5s breathing + 5s strobe (15Hz, 25Hz, 35Hz), repeat 3 times
        strobe_frequencies = [10.0, 15.0, 20.0]

        # do not use white for strobing or big tree chunks only for a few leds
        strobe_colors = [
            Color(0, 255, 0),  # White
            Color(255, 0, 0),      # Red  
            Color(0, 0, 255)       # Blue
        ]
        
            # green strobe is nice

            # magic happens around 10Hz need to change duty cycle that will be more dark time and less light time instead of same same

        for cycle in range(3):
            print(f"   Cycle {cycle + 1}/3: Breathing phase...")
            await recipe_manager.apply_recipe(RECIPES["blue_magenta_breathing"], transition_time=0.0)
            await wait_for_input(force_simulation=force_simulation)
            
            print(f"   Cycle {cycle + 1}/3: Direct {strobe_colors[cycle]} strobe phase...")
            freq = strobe_frequencies[cycle]
            color = strobe_colors[cycle]
            await controller.trigger_strobe(freq, 5.0, color)  # Direct hardware strobe with color
            await wait_for_input(force_simulation=force_simulation)
        
        # Back to sunset_breathing (smooth transition)
        await recipe_manager.apply_recipe(RECIPES["sunset_breathing"], transition_time=3.0)
        await wait_for_input(force_simulation=force_simulation)
        
        print("🍽️ Recipe demo completed!")
        render_task.cancel()
        
    except KeyboardInterrupt:
        print("\n🍽️ Recipe demo interrupted")
    finally:
        await controller.stop()

async def run_single_recipe(recipe_name: str, num_pixels: int = 100, force_simulation: bool = False, strobe_color: Color = Color(255, 255, 255), tree_structure = None):
    """Run a single recipe continuously"""
    if recipe_name not in RECIPES:
        print(f"❌ Recipe '{recipe_name}' not found!")
        print(f"Available recipes: {', '.join(RECIPES.keys())}")
        return
    
    # Load tree structure if available
    tree_structure = tree_structure
    
    controller = PipelineController(num_pixels, force_simulation=force_simulation, tree_structure=tree_structure)
    await controller.start()
    
    try:
        # Special handling for color_strobe - use direct hardware strobe
        if recipe_name == "color_strobe":
            print(f"🔥 Direct color strobe mode at {STROBE_FREQ} Hz")
            print(f"   Color: RGB({strobe_color.r}, {strobe_color.g}, {strobe_color.b})")
            print("Press Ctrl+C to stop")
            print("🚫 BYPASSING PIPELINE - Direct hardware control")
            
            # DON'T start the render loop - we're bypassing it completely
            
            # Continuous direct strobe in 3-second bursts
            while True:
                await controller.trigger_strobe(STROBE_FREQ, 3.0, strobe_color)  # 3 second bursts
                
        else:
            # Normal recipe handling
            # Start rendering loop
            render_task = asyncio.create_task(controller.run_loop())
            
            # Create recipe manager
            recipe_manager = RecipeManager(controller, tree_structure)
            
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

async def set_led_range(range_str: str, num_pixels: int = 100, force_simulation: bool = False, tree_structure=None):
    """Set specific LED range to white, all others black"""
    controller = PipelineController(num_pixels, force_simulation=force_simulation, tree_structure=tree_structure)
    await controller.start()
    
    try:
        # Start rendering loop
        render_task = asyncio.create_task(controller.run_loop())
        
        # Parse range string
        led_indices = []
        parts = range_str.split(',')  # Split by comma first
        
        for part in parts:
            if '-' in part:
                # Range: "5-10"
                start, end = map(int, part.split('-'))
                led_indices.extend(range(start, end + 1))
                print(f"💡 Adding LED range {start}-{end}")
            else:
                # Single: "5"
                led_indices.append(int(part))
                print(f"💡 Adding LED {part}")
        
        print(f"💡 Total LEDs to light: {sorted(led_indices)}")
        
        # Validate indices
        for idx in led_indices:
            if idx < 0 or idx >= num_pixels:
                print(f"❌ Invalid LED index: {idx} for {num_pixels} LEDs")
                return
        
        # Create colors array - black with white LEDs
        colors = [Color(0, 0, 0)] * num_pixels
        for idx in led_indices:
            colors[idx] = Color(255, 255, 255)
        
        # Set colors and hold
        controller.pipeline.set_base_colors(colors, TransitionMode.STATIC)
        
        print(f"   Selected LEDs are white, others are black")
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
    parser.add_argument('--recipe', type=str, help='Run specific recipe directly (complex_demo, sunset_breathing, rainbow_wave, rainbow, music_spectrum, music_spectrum_c, spectrum_enhanced, spectrum_enhanced_c, spectrum_enhanced_9, music_pulse)')
    parser.add_argument('--bands', type=int, help='Override number of frequency bands (default: recipe setting)')
    parser.add_argument('--strobe-freq', type=float, default=15.0, help='White strobe frequency in Hz (default: 15.0)')
    parser.add_argument('--strobe-color', type=str, default='255,255,255', help='Strobe color as R,G,B (default: 255,255,255 for white)')
    parser.add_argument('--fps', type=int, help=f'Pipeline FPS for effect calculations (default: {PIPELINE_FPS})')
    parser.add_argument('--set-led-range', type=str, help='Light up LEDs: "5" (single), "1,3,7" (list), "5-10" (range), "1,3,5-8" (mixed)')
    parser.add_argument('--set-branch', type=int, help='Light up specific branch index (0-19)')
    parser.add_argument('--set-ring', type=int, help='Light up specific ring index (0-4)')
    parser.add_argument('--led-crawl', action='store_true', help='LED crawl mode - progressively light up LEDs with blinking')
    parser.add_argument('--persistent-gui', action='store_true', help='Use persistent GUI that stays open between runs')
    parser.add_argument('--simulation', action='store_true', help='Run in simulation mode with GUI (default: real LEDs)')
    parser.add_argument('--high-fidelity', action='store_true', help='Use 48kHz audio sampling (default: 16kHz for better compatibility)')
    parser.add_argument('--start-blank', action='store_true', help='Clear all LEDs to black before starting')
    parser.add_argument('--clear-all', action='store_true', help='Clear all LEDs to black and exit')
    parser.add_argument('--crawl-blink-time', type=float, default=2.0, help='Blink duration per LED in crawl mode (default: 2.0 seconds)')
    parser.add_argument('--tree-config', type=str, help='Path to tree configuration YAML file')
    
    args = parser.parse_args()
    
    print(f"🍽️ Recipe System")
    print(f"  Pixels: {args.pixels}")
    
    # Set global FPS if provided
    if args.fps:
        import pipeline_demo
        pipeline_demo.PIPELINE_FPS = args.fps
        print(f"  FPS: {args.fps}")
    else:
        print(f"  FPS: {PIPELINE_FPS} (default)")

    # Parse strobe color
    try:
        r, g, b = map(int, args.strobe_color.split(','))
        strobe_color = Color(r, g, b)
        print(f"  Strobe color: RGB({r}, {g}, {b})")
    except ValueError:
        print(f"❌ Invalid strobe color format: {args.strobe_color}")
        print("   Use format: R,G,B (e.g., 255,0,0 for red)")
        return
    
    # Set audio sampling rate
    global SAMPLING_RATE, STROBE_FREQ
    import recipe_manager
    STROBE_FREQ = args.strobe_freq
    if args.high_fidelity:
        SAMPLING_RATE = 48000
        print(f"  Audio: High-fidelity mode (48kHz)")
    else:
        print(f"  Audio: Standard mode (16kHz)")
    
    # Set bands override
    if args.bands:
        recipe_manager.BANDS_OVERRIDE = args.bands
        print(f"  Bands: Override to {args.bands} frequency bands")
    
    # Enable persistent GUI mode if requested
    if args.persistent_gui:
        import mock_neopixel
        mock_neopixel.set_persistent_mode(True)
        print(f"  GUI: Persistent mode enabled")
    
    # Clear all LEDs if requested
    if args.start_blank:
        print(f"  Clearing all LEDs to black...")
        await clear_all_leds(args.pixels, args.persistent_gui)
        # Brief pause to ensure clear completes before next command
        await asyncio.sleep(0.2)
    
    # Load tree configuration if provided
    tree_structure = None
    if args.tree_config:
        try:
            from tree_config import load_tree_config
            from pipeline_demo import TreeStructure
            
            tree_data = load_tree_config(args.tree_config, verbose=True)
            
            # Count total LEDs in config
            total_config_leds = 0
            for ring in tree_data['rings']:
                total_config_leds = max(total_config_leds, max(ring) + 1 if ring else 0)
            for branch in tree_data['branches']:
                total_config_leds = max(total_config_leds, max(branch) + 1 if branch else 0)
            
            # Warn if discarding LEDs
            if total_config_leds > args.pixels:
                discarded = total_config_leds - args.pixels
                print(f"⚠️  WARNING: Tree config has {total_config_leds} LEDs, but --pixels is {args.pixels}")
                print(f"   Discarding {discarded} LEDs (indices {args.pixels}-{total_config_leds-1})")
            
            # Filter LEDs to only include those within pixel range
            filtered_rings = []
            for ring in tree_data['rings']:
                filtered_ring = [led for led in ring if led < args.pixels]
                if filtered_ring:  # Only add non-empty rings
                    filtered_rings.append(filtered_ring)
            
            filtered_branches = []
            for branch in tree_data['branches']:
                filtered_branch = [led for led in branch if led < args.pixels]
                if filtered_branch:  # Only add non-empty branches
                    filtered_branches.append(filtered_branch)
            
            tree_structure = TreeStructure(
                rings=filtered_rings,
                branches=filtered_branches
            )
            
            print(f"🌲 Tree config loaded: {len(tree_structure.rings)} rings, {len(tree_structure.branches)} branches")
            print(f"   Filtered to {args.pixels} LEDs")
            
        except Exception as e:
            print(f"❌ Failed to load tree config: {e}")
    
    # Determine simulation mode - default is real LEDs
    force_simulation = args.simulation
    
    if args.set_led_range:
        print(f"  Mode: Set LED Range ({args.set_led_range})")
        await set_led_range(args.set_led_range, args.pixels, force_simulation, tree_structure)
    elif args.set_branch is not None:
        if not tree_structure:
            print("❌ Tree structure required for --set-branch")
            return
        if args.set_branch < 0 or args.set_branch >= len(tree_structure.branches):
            print(f"❌ Invalid branch index: {args.set_branch}. Valid range: 0-{len(tree_structure.branches)-1}")
            return
        
        # Get LEDs for this branch - flatten the pairs
        branch_leds = []
        print(f"🔍 Branch {args.set_branch} raw data: {tree_structure.branches[args.set_branch]}")
        for led_pair in tree_structure.branches[args.set_branch]:
            print(f"🔍 Processing led_pair: {led_pair} (type: {type(led_pair)})")
            if isinstance(led_pair, list):
                branch_leds.extend(led_pair)  # [26, 27] -> add 26, 27
            else:
                branch_leds.append(led_pair)  # single LED
        
        print(f"🔍 Flattened branch LEDs: {branch_leds}")
        led_string = ','.join(map(str, branch_leds))
        print(f"  Mode: Set Branch {args.set_branch} (LEDs: {led_string})")
        await set_led_range(led_string, args.pixels, force_simulation, tree_structure)
    elif args.set_ring is not None:
        if not tree_structure:
            print("❌ Tree structure required for --set-ring")
            return
        if args.set_ring < 0 or args.set_ring >= len(tree_structure.rings):
            print(f"❌ Invalid ring index: {args.set_ring}. Valid range: 0-{len(tree_structure.rings)-1}")
            return
        
        # Get LEDs for this ring - flatten if needed
        ring_leds = []
        print(f"🔍 Ring {args.set_ring} raw data: {tree_structure.rings[args.set_ring]}")
        for led_item in tree_structure.rings[args.set_ring]:
            print(f"🔍 Processing led_item: {led_item} (type: {type(led_item)})")
            if isinstance(led_item, list):
                ring_leds.extend(led_item)  # [2, 3] -> add 2, 3
            else:
                ring_leds.append(led_item)  # single LED
        
        print(f"🔍 Flattened ring LEDs: {ring_leds}")
        led_string = ','.join(map(str, ring_leds))
        print(f"  Mode: Set Ring {args.set_ring} (LEDs: {led_string})")
        await set_led_range(led_string, args.pixels, force_simulation, tree_structure)
    elif args.clear_all:
        print(f"  Mode: Clear All LEDs")
        controller = PipelineController(args.pixels, force_simulation=force_simulation, tree_structure=tree_structure)
        await controller.start()
        try:
            for i in range(args.pixels):
                controller.pixels[i] = (0, 0, 0)
            controller.pixels.show()
            print("✅ All LEDs cleared to black")
        finally:
            await controller.stop()
        return
    elif args.led_crawl:
        print(f"  Mode: LED Crawl")
        await led_crawl(args.pixels, args.crawl_blink_time, force_simulation)
    elif args.recipe:
        print(f"  Mode: Single recipe ({args.recipe})")
        await run_single_recipe(args.recipe, args.pixels, force_simulation, strobe_color, tree_structure)
    else:
        print(f"  Mode: Full demo sequence")
        await demo_recipe_transitions(args.pixels, force_simulation, tree_structure)

if __name__ == "__main__":
    asyncio.run(main())
