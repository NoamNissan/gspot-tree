import asyncio
import threading
import multiprocessing
from typing import Optional

# Integrate with LED controller stack
from led_ctrl.led_orchestrator import PipelineController, RecipeManager, RECIPES


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

        # If running in simulation with GUI, start persistent GUI in a separate process on the main thread
        if self.simulation and self.persistent_gui:
            try:
                from led_ctrl import mock_neopixel as _mn
                _mn.set_persistent_mode(True)
                self._gui_process = multiprocessing.Process(
                    target=_mn.start_persistent_gui,
                    args=(self.num_pixels, False),
                    daemon=True,
                    name="LED-Persistent-GUI",
                )
                self._gui_process.start()
            except Exception:
                # Fall back silently; background runtime may still run headless
                self._gui_process = None

        self._start_background_runtime()

    # Public API
    def start_music(self):
        """Start a music-reactive recipe (e.g., pulse to music)."""
        def _apply():
            return self._recipe_manager.apply_recipe(RECIPES["music_pulse"], transition_time=1.0)

        self._submit_coroutine(_apply)

    def stop_music(self):
        """Switch to a calm breathing-style recipe."""
        def _apply():
            return self._recipe_manager.apply_recipe(RECIPES["sunset_breathing"], transition_time=1.0)

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
        def _runner():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            async def _start():
                self._controller = PipelineController(self.num_pixels, force_simulation=self.simulation)
                # Optional persistent GUI setup is handled inside led_ctrl when enabled globally
                await self._controller.start()
                self._recipe_manager = RecipeManager(self._controller)
                self._render_task = asyncio.create_task(self._controller.run_loop())

                # Start with a neutral calm state
                await self._recipe_manager.apply_recipe(RECIPES["sunset_breathing"], transition_time=0)

            self._loop.run_until_complete(_start())
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
            return
        try:
            asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)
        except Exception:
            pass