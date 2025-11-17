import asyncio
import threading
import multiprocessing
from concurrent.futures import Future
from typing import Optional

# Integrate with LED controller stack
from led_ctrl.led_orchestrator import PipelineController
from led_ctrl.led_composer import LEDComposer, ComposerState
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
        self._led_composer: Optional[LEDComposer] = None
        self._render_task: Optional[asyncio.Task] = None
        self._loop_ready: Optional[threading.Event] = None
        self._music_task: Optional[Future] = None

        print(f'Initiating light controller with {num_pixels} pixels')
        # Start background runtime in a separate thread
        self._start_background_runtime()

    # Public API
    def wait_until_ready(self, timeout_seconds: float = 5.0) -> bool:
        """Block until the background loop and LED composer are ready."""
        import time
        
        # Wait for the loop to be created and running
        if self._loop_ready:
            if not self._loop_ready.wait(timeout_seconds):
                print("Timeout waiting for event loop to be ready")
                return False
        
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self._loop and self._led_composer and self._loop.is_running():
                return True
            time.sleep(0.05)
        
        print(f"Timeout waiting for ready state. Loop: {bool(self._loop)}, Composer: {bool(self._led_composer)}, Running: {self._loop.is_running() if self._loop else False}")
        return bool(self._loop and self._led_composer and self._loop.is_running())

    def start_single_active(self, chip_type: ChipType = ChipType.SINGLE):
        """Start a music-reactive recipe (e.g., pulse to music)."""
        print(f"Starting music in LightController for {chip_type} chip")
        def _apply():
            return self._led_composer.set_state(ComposerState.SINGLE_ACTIVE, transition_time=0.5)
        
        self._cancel_music_task()
        future = self._submit_coroutine(_apply)
        if future:
            self._music_task = future
            future.add_done_callback(self._on_music_task_done)

    def start_party(self):
        """Start party mode with cycling non-music-reactive LED patterns."""
        print("Starting party mode in LightController - using ADVERTISE state for party patterns")
        self._cancel_music_task()
        def _apply():
            return self._led_composer.set_state(ComposerState.ADVERTISE)
        
        future = self._submit_coroutine(_apply)
        if future:
            self._music_task = future
            future.add_done_callback(self._on_music_task_done)

    def stop_music(self):
        """Switch to a calm breathing-style recipe."""
        print("Stopping music in LightController")
        self._cancel_music_task()
        def _apply():
            return self._led_composer.set_state(ComposerState.IDLE)

        self._submit_coroutine(_apply)

    def start_single_feedback(self):
        """Start single feedback state."""
        print("Starting single feedback state in LightController")
        self._cancel_music_task()
        def _apply():
            return self._led_composer.set_state(ComposerState.SINGLE_FEEDBACK, transition_time=0.5)

        self._submit_coroutine(_apply)

    def start_couple_feedback(self):
        """Start couple feedback state."""
        print("Starting couple feedback state in LightController")
        self._cancel_music_task()
        def _apply():
            return self._led_composer.set_state(ComposerState.COUPLE_FEEDBACK, transition_time=0.5)

        self._submit_coroutine(_apply)

    def start_couple_active(self):
        """Start couple active state."""
        print("Starting couple active state in LightController")
        self._cancel_music_task()
        def _apply():
            return self._led_composer.set_state(ComposerState.COUPLE_ACTIVE, transition_time=0.5)

        self._submit_coroutine(_apply)

    def start_advertise(self):
        """Start advertise state."""
        print("Starting advertise state in LightController")
        self._cancel_music_task()
        def _apply():
            return self._led_composer.set_state(ComposerState.ADVERTISE, transition_time=0.5)

        self._submit_coroutine(_apply)

    def start_manual(self):
        """Start manual state."""
        print("Starting manual state in LightController")
        self._cancel_music_task()
        def _apply():
            return self._led_composer.set_state(ComposerState.MANUAL, transition_time=0.5)

        self._submit_coroutine(_apply)

    def start_idle(self):
        """Start idle state."""
        print("Starting idle state in LightController")
        self._cancel_music_task()
        def _apply():
            return self._led_composer.set_state(ComposerState.IDLE, transition_time=0.5)

        self._submit_coroutine(_apply)

    def shutdown(self):
        """Cleanly stop rendering and background loop."""
        if not self._loop:
            return

        def _cleanup_coro():
            async def _inner():
                # Stop LED composer if used
                if self._led_composer:
                    try:
                        await self._led_composer.stop()
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
        # Create LED composer (which creates its own controller)
        print("Starting background runtime in LightController")
        import os
        tree_config_path = os.path.join("led_ctrl", "tree_config.yaml")
        self._led_composer = LEDComposer(tree_config_path, force_simulation=self.simulation)
        self._controller = self._led_composer.controller
        
        # Add an event to signal when the loop is ready
        self._loop_ready = threading.Event()

        # Spawn background thread only for the long-running render loop and async recipe application
        def _runner():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            async def _run():
                # Start LED composer
                print("Starting LED composer")
                await self._led_composer.start()
                # Start render loop
                print("Starting render loop")
                self._render_task = asyncio.create_task(self._controller.run_loop())
                # Signal that the loop is ready
                self._loop_ready.set()
                print("Event loop is ready and running")

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
        if not self._loop or not self._led_composer:
            print("No loop or LED composer")
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