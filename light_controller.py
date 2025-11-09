import asyncio
import threading
import multiprocessing
from concurrent.futures import Future
from typing import Optional

# Integrate with LED controller stack
from led_ctrl.led_orchestrator import PipelineController, RecipeManager, RECIPES
from constants import ChipType



class LightController:
    def __init__(self, num_pixels: int = 100, simulation: bool = False, persistent_gui: bool = False):
        self.num_pixels = num_pixels
        self.simulation = simulation
        self.persistent_gui = persistent_gui

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._gui_process: Optional[multiprocessing.Process] = None
        self._controller: Optional[PipelineController] = None
        self._recipe_manager: Optional[RecipeManager] = None
        self._render_task: Optional[asyncio.Task] = None
        self._loop_ready: Optional[threading.Event] = None
        self._music_task: Optional[Future] = None

        print(f'Initiating light controller with {num_pixels} pixels')
        # If running in simulation with GUI, start persistent GUI in a separate process
        # if self.simulation and self.persistent_gui:
        #     try:
        #         from led_ctrl import mock_neopixel as _mn
        #         self._gui_process = multiprocessing.Process(
        #             target=_mn.start_persistent_gui,
        #             args=(self.num_pixels, False),
        #             daemon=True,
        #             name="LED-Persistent-GUI",
        #         )
        #         self._gui_process.start()
        #     except Exception:
        #         # Fall back silently; background runtime may still run headless
        #         self._gui_process = None

        # Start background runtime in a separate thread
        self._start_background_runtime()

    # Public API
    def wait_until_ready(self, timeout_seconds: float = 5.0) -> bool:
        """Block until the background loop and recipe manager are ready."""
        import time
        
        # Wait for the loop to be created and running
        if self._loop_ready:
            if not self._loop_ready.wait(timeout_seconds):
                print("Timeout waiting for event loop to be ready")
                return False
        
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self._loop and self._recipe_manager and self._loop.is_running():
                return True
            time.sleep(0.05)
        
        print(f"Timeout waiting for ready state. Loop: {bool(self._loop)}, Manager: {bool(self._recipe_manager)}, Running: {self._loop.is_running() if self._loop else False}")
        return bool(self._loop and self._recipe_manager and self._loop.is_running())

    def start_music(self, chip_type: ChipType = ChipType.SINGLE):
        """Start a music-reactive recipe (e.g., pulse to music)."""
        print(f"Starting music in LightController for {chip_type} chip")
        def _apply():
            if chip_type == ChipType.DOUBLE:
                print(f"Applying music pulse recipe for {chip_type} chip")
                double_chip_recipes = [
                    
                    "pink_rainbow_wave",
                    "pink_spectrum_analyzer",
                    "pink_fire",
                ]
                return self._start_cycling_recipes(double_chip_recipes, 5)
            else:
                print(f"Starting cycling music recipes for {chip_type} chip")
                single_chip_recipes = [
                    # "music_spectrum",    # Real-time audio spectrum visualization
                    # "music_pulse",       # Colors pulse with music
                    "spectrum_analyzer", 
                    "rainbow_wave",  
                    "rainbow",
                    "wavelength_flow",
                    "rainbow_scroll",  
                    "fire_demo",
                ]
                return self._start_cycling_recipes(single_chip_recipes)

        self._cancel_music_task()
        future = self._submit_coroutine(_apply)
        if future:
            self._music_task = future
            future.add_done_callback(self._on_music_task_done)

    async def _start_cycling_recipes(self, cycling_recipes, sleep_interval=4.0):
        """Start cycling through three different music recipes with 4-second intervals."""
        
        
        print("Starting continuous cycling of music recipes")
        
        while True:
            for recipe_name in cycling_recipes:
                print(f"Applying {recipe_name} recipe")
                await self._recipe_manager.apply_recipe(RECIPES[recipe_name], transition_time=1.0)
                await asyncio.sleep(sleep_interval)  # Wait sleep_interval seconds before next recipe

    def stop_music(self):
        """Switch to a calm breathing-style recipe."""
        print("Stopping music in LightController")
        self._cancel_music_task()
        def _apply():
            return self._recipe_manager.apply_recipe(RECIPES["calm_rainbow_wave"], transition_time=1.0)

        self._submit_coroutine(_apply)

    def start_pending(self):
        """Start flashing blue lights for pending state."""
        print("Starting pending state in LightController - flashing blue lights")
        self._cancel_music_task()
        def _apply():
            return self._recipe_manager.apply_recipe(RECIPES["blue_flash"], transition_time=0.5)

        self._submit_coroutine(_apply)

    def shutdown(self):
        """Cleanly stop rendering and background loop."""
        if not self._loop:
            return

        def _cleanup_coro():
            async def _inner():
                # Stop audio provider if used
                if self._recipe_manager and hasattr(self._recipe_manager, "audio_provider"):
                    try:
                        self._recipe_manager.audio_provider.stop()
                    except Exception:
                        pass

                # Cancel render task and stop controller
                if self._render_task:
                    self._render_task.cancel()
                if self._controller:
                    try:
                        await self._controller.stop()
                    except Exception:
                        pass
            return _inner()

        fut = asyncio.run_coroutine_threadsafe(_cleanup_coro(), self._loop)
        try:
            fut.result(timeout=5)
        except Exception:
            pass

        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)

        # Stop persistent GUI process if started
        if self._gui_process and self._gui_process.is_alive():
            try:
                self._gui_process.terminate()
            except Exception:
                pass

    # Internal helpers
    def _start_background_runtime(self):
        # Create controller and start it on the main thread (not inside the background thread)
        print("Starting background runtime in LightController")
        self._controller = PipelineController(self.num_pixels, force_simulation=self.simulation)
        try:
            asyncio.run(self._controller.start())
        except RuntimeError:
            # Fallback if an event loop is already running on the main thread
            temp_loop = asyncio.new_event_loop()
            try:
                temp_loop.run_until_complete(self._controller.start())
            finally:
                temp_loop.close()

        # Create recipe manager on the main thread as well
        self._recipe_manager = RecipeManager(self._controller)
        
        # Add an event to signal when the loop is ready
        self._loop_ready = threading.Event()

        # Spawn background thread only for the long-running render loop and async recipe application
        def _runner():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            async def _run():
                # Start render loop
                print("Starting render loop")
                self._render_task = asyncio.create_task(self._controller.run_loop())
                # Signal that the loop is ready
                self._loop_ready.set()
                print("Event loop is ready and running")
                # Apply initial calm recipe
                # print("Applying initial calm recipe")
                # await self._recipe_manager.apply_recipe(RECIPES["sunset_breathing"], transition_time=0)

            self._loop.run_until_complete(_run())
            try:
                self._loop.run_forever()
            finally:
                try:
                    self._loop.close()
                except Exception:
                    pass

        self._thread = threading.Thread(target=_runner, name="LightControllerLoop", daemon=True)
        self._thread.start()

    def _submit_coroutine(self, coro_factory):
        if not self._loop or not self._recipe_manager:
            print("No loop or recipe manager")
            return
        
        if not self._loop.is_running():
            print("Event loop is not running")
            return
            
        try:
            return asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)
        except Exception as e:
            print(f"Error submitting coroutine: {e}")
            return None
    
    def _cancel_music_task(self):
        if self._music_task:
            if not self._music_task.done():
                self._music_task.cancel()
            self._music_task = None

    def _on_music_task_done(self, future: Future):
        if self._music_task is future:
            self._music_task = None

    def get_gui_instance(self):
        """Get the MockNeoPixel GUI instance for main thread control"""
        # print("Getting GUI instance, RETURNING NONE")
        # #TODO: Add persistent GUI support
        # return None

        # if self.simulation and self._controller and hasattr(self._controller, 'pixels'):
        if self.simulation and not self.persistent_gui:
            return self._controller.pixels
        return None