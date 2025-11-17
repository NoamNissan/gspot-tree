#!/usr/bin/env python3
"""
LED Composer CLI Demo
Interactive command-line interface for testing LED Composer states and recipes
"""

import asyncio
import sys
from .led_composer import create_led_composer, ComposerState


class LEDComposerCLI:
    def __init__(self):
        self.composer = None
        self.running = False
    
    async def start(self):
        """Start the LED composer and CLI"""
        print("🎨 LED Composer CLI Demo")
        print("=" * 40)
        
        # Initialize composer
        self.composer = create_led_composer("tree_config.yaml", force_simulation=True, separate_process=False)
        await self.composer.start()
        self.running = True
        
        print("✅ LED Composer started")
        
        # Run menu in background task so it doesn't block
        menu_task = asyncio.create_task(self.show_menu())
        
        try:
            await menu_task
        except asyncio.CancelledError:
            pass
    
    async def wait_for_input_choice(self):
        """Wait for user input - polling method for simulation"""
        import sys
        import select
        print("Enter choice (0-17): ", end='', flush=True)
        
        while True:
            if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                choice = sys.stdin.readline().strip()
                return choice
            await asyncio.sleep(0.1)
    
    async def show_menu(self):
        """Show interactive menu"""
        while self.running:
            print("\n" + "=" * 40)
            print("🎛️  LED COMPOSER CONTROL PANEL")
            print("=" * 40)
            print(f"Current State: {self.composer.get_current_state().value.upper()}")
            print()
            
            # State options
            print("📍 SET STATE:")
            print("1. Idle (calm breathing)")
            print("2. Single Person Feedback (blue strobe)")
            print("3. Single Person Active (happy dance)")
            print("4. Couple Feedback (red/purple strobe)")
            print("5. Couple Active (romantic patterns)")
            print("6. Advertise (attention burst)")
            print()
            
            # Control options
            print("⚙️  CONTROL:")
            print("7. Show Parameters")
            print("8. Show All Recipes")
            print("0. Quit")
            print()
            
            # Manual options - show first few recipes
            print("🎵 MANUAL RECIPES (first 8):")
            from .recipe_manager import RECIPES
            recipe_items = list(RECIPES.items())
            
            for i, (recipe_key, recipe) in enumerate(recipe_items[:8], 9):
                print(f"{i}. Manual: {recipe.name}")
            
            print(f"... and {len(recipe_items) - 8} more (use option 8 to see all)")
            print()
            
            try:
                choice = await self.wait_for_input_choice()
                if choice.strip():  # Only handle non-empty choices
                    await self.handle_choice(choice, recipe_items)
            except KeyboardInterrupt:
                print("\n🛑 Interrupted")
                break
            except EOFError:
                print("\n🛑 EOF")
                break
    
    async def handle_choice(self, choice: str, recipe_items):
        """Handle user menu choice"""
        try:
            if choice == "0":
                await self.quit()
            elif choice == "1":
                await self.set_state(ComposerState.IDLE)
            elif choice == "2":
                await self.set_state(ComposerState.SINGLE_FEEDBACK)
            elif choice == "3":
                await self.set_state(ComposerState.SINGLE_ACTIVE)
            elif choice == "4":
                await self.set_state(ComposerState.COUPLE_FEEDBACK)
            elif choice == "5":
                await self.set_state(ComposerState.COUPLE_ACTIVE)
            elif choice == "6":
                await self.set_state(ComposerState.ADVERTISE)
            elif choice == "7":
                await self.show_parameters()
            elif choice == "8":
                await self.show_all_recipes()
            elif choice.isdigit() and 9 <= int(choice) <= 16:
                # Manual recipe selection from first 8
                recipe_index = int(choice) - 9
                if recipe_index < len(recipe_items) and recipe_index < 8:
                    recipe_key, recipe = recipe_items[recipe_index]
                    await self.set_manual_recipe(recipe_key)
                else:
                    print("❌ Recipe index out of range")
                    return
            else:
                print("❌ Invalid choice. Please enter 0-16.")
                return
            
            # Brief pause to see the change
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    async def set_state(self, state: ComposerState):
        """Set composer state"""
        print(f"🔄 Setting state to: {state.value.upper()}")
        await self.composer.set_state(state)
        print(f"✅ State changed to: {state.value.upper()}")
    
    async def set_manual_recipe(self, recipe_name: str):
        """Set manual recipe"""
        print(f"🎵 Loading manual recipe: {recipe_name}")
        await self.composer.set_manual_recipe(recipe_name)
        print(f"✅ Manual recipe loaded: {recipe_name}")
    
    async def show_all_recipes(self):
        """Show all recipes and allow direct selection"""
        from recipe_manager import RECIPES
        recipe_items = list(RECIPES.items())
        
        print("\n🎵 ALL RECIPES:")
        print("=" * 50)
        for i, (recipe_key, recipe) in enumerate(recipe_items):
            print(f"{i:2d}. {recipe.name}")
        print("=" * 50)
        
        try:
            print("Enter recipe number (or press Enter to cancel): ", end='', flush=True)
            
            # Use async input like the main menu
            import sys
            import select
            while True:
                if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                    choice = sys.stdin.readline().strip()
                    break
                await asyncio.sleep(0.1)
            
            if choice == "":
                return
            
            recipe_index = int(choice)
            if 0 <= recipe_index < len(recipe_items):
                recipe_key, recipe = recipe_items[recipe_index]
                await self.set_manual_recipe(recipe_key)
            else:
                print("❌ Invalid recipe number")
        except ValueError:
            print("❌ Please enter a valid number")
    
    async def show_parameters(self):
        """Show current parameters"""
        print("\n📊 CURRENT PARAMETERS:")
        print("=" * 40)
        params = self.composer.get_params()
        for key, value in params.items():
            print(f"{key}: {value}")
        print("=" * 40)
    
    async def quit(self):
        """Quit the demo"""
        print("🛑 Shutting down LED Composer...")
        self.running = False
        if self.composer:
            await self.composer.stop()
        print("✅ LED Composer stopped")
        print("👋 Goodbye!")


async def main():
    """Main CLI demo function"""
    cli = LEDComposerCLI()
    
    try:
        await cli.start()
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if cli.composer:
            await cli.composer.stop()


if __name__ == "__main__":
    asyncio.run(main())
