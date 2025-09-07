"""
Mock neopixel library for LED simulation
"""
import tkinter as tk
import math
import random
import socket
import threading
import json
from typing import Tuple, List
from .constants import PERSISTENT_GUI_PORT

# Global persistent GUI instance
_persistent_gui = None
_persistent_mode = False

def set_persistent_mode(enabled: bool):
    """Enable or disable persistent GUI mode"""
    global _persistent_mode
    _persistent_mode = enabled

class PersistentGUI:
    """Persistent GUI that can be shared across multiple app runs"""
    
    def __init__(self, num_pixels: int, verbose: bool = True):
        self.num_pixels = num_pixels
        self.verbose = verbose
        self.root = tk.Tk()
        self.root.title(f"LED Simulator - {num_pixels} pixels (Persistent Mode)")
        self.canvas = tk.Canvas(self.root, width=1000, height=800, bg='black')
        self.canvas.pack()
        
        # Create LED visualization
        self._create_leds()
        
        # Socket server for receiving updates
        self.server_socket = None
        self.server_thread = None
        self._start_server()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
    def _create_leds(self):
        """Create LED circles in GUI"""
        self.circles = []
        center_x, center_y = 500, 400
        max_radius = 300
        inner_radius = max_radius / 5
        led_size = 5
        pair_spacing = 12
        
        # Draw circle boundaries first
        self.canvas.create_oval(
            center_x - max_radius, center_y - max_radius,
            center_x + max_radius, center_y + max_radius,
            outline='darkgray', width=1, fill=''
        )
        
        self.canvas.create_oval(
            center_x - inner_radius, center_y - inner_radius,
            center_x + inner_radius, center_y + inner_radius,
            outline='darkgray', width=1, fill=''
        )
        
        num_lines = 20
        line_angle_step = 2 * math.pi / num_lines
        
        # Draw radial lines
        for line in range(num_lines):
            angle = line * line_angle_step
            x1 = center_x + inner_radius * math.cos(angle)
            y1 = center_y + inner_radius * math.sin(angle)
            x2 = center_x + max_radius * math.cos(angle)
            y2 = center_y + max_radius * math.sin(angle)
            self.canvas.create_line(x1, y1, x2, y2, fill='darkgray', width=1)
        
        pair_positions = []
        
        for line in range(num_lines):
            pairs_on_line = random.randint(2, 3)
            line_angle = line * line_angle_step
            available_length = max_radius - inner_radius - 40
            segment_length = available_length / pairs_on_line
            
            for pair_idx in range(pairs_on_line):
                segment_start = inner_radius + 20 + pair_idx * segment_length
                segment_end = segment_start + segment_length
                r = random.uniform(segment_start, segment_end)
                
                pair_center_x = center_x + r * math.cos(line_angle)
                pair_center_y = center_y + r * math.sin(line_angle)
                
                base_angle = line_angle + math.pi/2
                random_offset = random.uniform(-math.pi/4, math.pi/4)
                pair_angle = base_angle + random_offset
                pair_positions.append((pair_center_x, pair_center_y, pair_angle))
        
        led_index = 0
        for pair_idx, (pair_center_x, pair_center_y, pair_angle) in enumerate(pair_positions):
            for led_in_pair in range(2):
                if led_index >= self.num_pixels:
                    break
                    
                offset = (led_in_pair - 0.5) * pair_spacing
                led_x = pair_center_x + offset * math.cos(pair_angle)
                led_y = pair_center_y + offset * math.sin(pair_angle)
                
                circle = self.canvas.create_oval(
                    led_x - led_size, led_y - led_size, 
                    led_x + led_size, led_y + led_size, 
                    fill='black', outline='gray', width=1
                )
                self.circles.append(circle)
                led_index += 1
            
            if led_index >= self.num_pixels:
                break
        
        while len(self.circles) < self.num_pixels:
            circle = self.canvas.create_oval(-10, -10, -5, -5, fill='black', outline='black')
            self.circles.append(circle)
        
        # Add text
        self.canvas.create_text(10, 10, text=f"LEDs 0-{self.num_pixels-1} ({self.num_pixels} pixels)", 
                               fill='white', anchor='nw')
    
    def _start_server(self):
        """Start socket server to receive LED updates"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('localhost', PERSISTENT_GUI_PORT))
            self.server_socket.listen(1)
            
            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.server_thread.start()
            print(f"🖥️ Persistent GUI server started on port {PERSISTENT_GUI_PORT}")
        except Exception as e:
            print(f"Failed to start GUI server: {e}")
    
    def _server_loop(self):
        """Server loop to handle LED update connections"""
        while True:
            try:
                client, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
            except:
                break
    
    def _handle_client(self, client):
        """Handle client connection for LED updates"""
        print("🔌 Client connected")
        try:
            buffer = ""
            while True:
                data = client.recv(1024)
                print(f"Received data: {data}")
                if not data:
                    break
                
                buffer += data.decode()
                
                # Process complete JSON messages
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            command = json.loads(line.strip())
                            if self.verbose:
                                print(f"📨 Received: {command}")
                            if command['type'] == 'update_pixel':
                                if self.verbose:
                                    print(f"   LED {command['index']} -> {command['color']}")
                                self.root.after(0, lambda idx=command['index'], col=command['color']: self._update_pixel(idx, col))
                            elif command['type'] == 'update_all_pixels':
                                if self.verbose:
                                    print(f"   Bulk update: {len(command['pixels'])} LEDs")
                                self.root.after(0, lambda pixels=command['pixels']: self._update_all_pixels(pixels))
                            elif command['type'] == 'show':
                                if self.verbose:
                                    print(f"   Show command")
                                self.root.after(0, lambda: self.canvas.update_idletasks())
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON error: {e} - Line: {line}")
                
        except Exception as e:
            print(f"Client handler error: {e}")
        finally:
            print("🔌 Client disconnected")
            client.close()
    
    def _update_pixel(self, index: int, color: Tuple[int, int, int]):
        """Update a single pixel in the GUI"""
        if self.verbose:
            print(f"🎨 GUI: Setting LED {index} to {color}")
        if index < len(self.circles):
            r, g, b = color
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            if self.verbose:
                print(f"   GUI: Circle {index} -> {hex_color}")
            self.canvas.itemconfig(self.circles[index], fill=hex_color)
            self.canvas.update_idletasks()
        else:
            if self.verbose:
                print(f"   GUI: ❌ Index {index} out of range")
    
    def _update_all_pixels(self, pixels: List[Tuple[int, int, int]]):
        """Update all pixels in the GUI efficiently"""
        for index, color in enumerate(pixels):
            if index < len(self.circles):
                r, g, b = color
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                self.canvas.itemconfig(self.circles[index], fill=hex_color)
        self.canvas.update_idletasks()
        if self.verbose:
            print(f"🎨 GUI: Updated {len(pixels)} LEDs")
    
    def _on_window_close(self):
        """Handle window close event"""
        if self.server_socket:
            self.server_socket.close()
        self.root.destroy()
        global _persistent_gui
        _persistent_gui = None
        print("🖥️ Persistent GUI closed")
    
    def run(self):
        """Run the GUI main loop"""
        self.root.mainloop()

class MockNeoPixel:
    """Mock NeoPixel class that can connect to persistent GUI or create its own"""
    
    def __init__(self, pin, num_pixels: int, brightness: float = 1.0, auto_write: bool = True):
        print("MockNeoPixel initialized")
        self.num_pixels = num_pixels
        self.brightness = brightness
        self.auto_write = auto_write
        self._pixels = [(0, 0, 0)] * num_pixels
        self._closed = False
        self._dirty = False  # Track if pixels have changed
        self._gui_created = False
        
        global _persistent_gui, _persistent_mode
        
        if _persistent_mode:
            # Try to connect to persistent GUI
            self._connect_to_persistent_gui()
        else:
            # Don't create GUI immediately - will be created when needed
            self._setup_gui_creation()
    
    def _setup_gui_creation(self):
        """Setup for GUI creation - will be created when mainloop is started"""
        print("Setting up for GUI creation")
        self.client_socket = None
        self.root = None
        self.canvas = None
        self.circles = []
    
    def _connect_to_persistent_gui(self):
        """Connect to persistent GUI via socket"""
        print("Connecting to persistent GUI")
        self.client_socket = None
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect(('localhost', PERSISTENT_GUI_PORT))
            print("🖥️ Connected to persistent GUI")
        except:
            print("🖥️ No persistent GUI found, creating new one...")
            self._setup_gui_creation()
    
    def create_gui(self):
        """Create the GUI - must be called from main thread"""
        if self._gui_created:
            return
        
        print("Creating GUI from main thread")
        self._create_own_gui()
        self._gui_created = True
    
    def start_mainloop(self):
        """Start the GUI mainloop - must be called from main thread"""
        if not self._gui_created:
            self.create_gui()
        
        if hasattr(self, 'root') and not self._closed:
            print("Starting GUI mainloop")
            self.root.mainloop()
    
    def _create_own_gui(self):
        """Create own GUI window (original behavior)"""
        print("Creating own GUI")
        self.client_socket = None
        self.root = tk.Tk()
        self.root.title(f"LED Simulator - {self.num_pixels} pixels")
        self.canvas = tk.Canvas(self.root, width=1000, height=800, bg='black')
        self.canvas.pack()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        # Create LED visualization (same as before)
        self.circles = []
        center_x, center_y = 500, 400
        max_radius = 300
        inner_radius = max_radius / 5
        led_size = 5
        pair_spacing = 12
        
        num_lines = 20
        line_angle_step = 2 * math.pi / num_lines
        
        pair_positions = []
        
        for line in range(num_lines):
            pairs_on_line = random.randint(2, 3)
            line_angle = line * line_angle_step
            available_length = max_radius - inner_radius - 40
            segment_length = available_length / pairs_on_line
            
            for pair_idx in range(pairs_on_line):
                segment_start = inner_radius + 20 + pair_idx * segment_length
                segment_end = segment_start + segment_length
                r = random.uniform(segment_start, segment_end)
                
                pair_center_x = center_x + r * math.cos(line_angle)
                pair_center_y = center_y + r * math.sin(line_angle)
                
                base_angle = line_angle + math.pi/2
                random_offset = random.uniform(-math.pi/4, math.pi/4)
                pair_angle = base_angle + random_offset
                pair_positions.append((pair_center_x, pair_center_y, pair_angle))
        
        led_index = 0
        for pair_idx, (pair_center_x, pair_center_y, pair_angle) in enumerate(pair_positions):
            for led_in_pair in range(2):
                if led_index >= self.num_pixels:
                    break
                    
                offset = (led_in_pair - 0.5) * pair_spacing
                led_x = pair_center_x + offset * math.cos(pair_angle)
                led_y = pair_center_y + offset * math.sin(pair_angle)
                
                circle = self.canvas.create_oval(
                    led_x - led_size, led_y - led_size, 
                    led_x + led_size, led_y + led_size, 
                    fill='black', outline='gray', width=1
                )
                self.circles.append(circle)
                led_index += 1
            
            if led_index >= self.num_pixels:
                break
        
        while len(self.circles) < self.num_pixels:
            circle = self.canvas.create_oval(-10, -10, -5, -5, fill='black', outline='black')
            self.circles.append(circle)
        
        # Draw circle boundaries and radial lines
        self.canvas.create_oval(
            center_x - max_radius, center_y - max_radius,
            center_x + max_radius, center_y + max_radius,
            outline='darkgray', width=1, fill=''
        )
        
        self.canvas.create_oval(
            center_x - inner_radius, center_y - inner_radius,
            center_x + inner_radius, center_y + inner_radius,
            outline='darkgray', width=1, fill=''
        )
        
        # Draw radial lines
        for line in range(num_lines):
            angle = line * line_angle_step
            x1 = center_x + inner_radius * math.cos(angle)
            y1 = center_y + inner_radius * math.sin(angle)
            x2 = center_x + max_radius * math.cos(angle)
            y2 = center_y + max_radius * math.sin(angle)
            self.canvas.create_line(x1, y1, x2, y2, fill='darkgray', width=1)
        
        # Add text
        self.canvas.create_text(10, 10, text=f"LEDs 0-{self.num_pixels-1} ({self.num_pixels} pixels)", 
                               fill='white', anchor='nw')
    
    def __setitem__(self, index: int, color: Tuple[int, int, int]):
        """Set pixel color"""
        if 0 <= index < self.num_pixels:
            r, g, b = color
            r = int(r * self.brightness)
            g = int(g * self.brightness)
            b = int(b * self.brightness)
            
            # Only update if color actually changed
            new_color = (r, g, b)
            if self._pixels[index] != new_color:
                self._pixels[index] = new_color
                self._dirty = True
                
                if self.auto_write:
                    self._update_pixel(index, new_color)
    
    def __getitem__(self, index: int) -> Tuple[int, int, int]:
        """Get pixel color"""
        return self._pixels[index]
    
    def _update_pixel(self, index: int, color: Tuple[int, int, int]):
        """Update a single pixel"""
        if self._closed:
            return
        
        if self.client_socket:
            # Send to persistent GUI
            try:
                command = {
                    'type': 'update_pixel',
                    'index': index,
                    'color': color
                }
                message = json.dumps(command) + '\n'
                self.client_socket.send(message.encode())
            except:
                pass
        elif hasattr(self, 'root') and self.root and hasattr(self, 'canvas') and self.canvas:
            # Update own GUI using thread-safe method
            def update_gui():
                if not self._closed and hasattr(self, 'canvas') and hasattr(self, 'circles') and index < len(self.circles):
                    r, g, b = color
                    hex_color = f"#{r:02x}{g:02x}{b:02x}"
                    self.canvas.itemconfig(self.circles[index], fill=hex_color)
            
            # Use root.after() for thread-safe GUI updates
            self.root.after(0, update_gui)
    
    def show(self):
        """Update all pixels"""
        if self._closed or not self._dirty:
            return
        
        self._dirty = False
        
        if self.client_socket:
            try:
                command = {'type': 'show'}
                message = json.dumps(command) + '\n'
                self.client_socket.send(message.encode())
            except:
                pass
        elif hasattr(self, 'root') and self.root:
            for i, color in enumerate(self._pixels):
                self._update_pixel(i, color)
            # Don't call root.update() here as it might block
    
    def fill(self, color: Tuple[int, int, int]):
        """Fill all pixels with the same color"""
        for i in range(self.num_pixels):
            self[i] = color
    
    def _on_window_close(self):
        """Handle window close event"""
        self._closed = True
        if hasattr(self, 'root'):
            self.root.destroy()
        print("\nGUI window closed - press Ctrl+C to stop")
    
    def deinit(self):
        """Clean up resources"""
        if self.client_socket:
            self.client_socket.close()
        try:
            if hasattr(self, 'root'):
                self.root.destroy()
        except:
            pass
    
    def __len__(self):
        return self.num_pixels

def start_persistent_gui(num_pixels: int = 100, verbose: bool = True):
    """Start persistent GUI in separate process"""
    global _persistent_gui
    if _persistent_gui is None:
        _persistent_gui = PersistentGUI(num_pixels, verbose=verbose)
        _persistent_gui.run()

# Mock board module
class MockBoard:
    D18 = 18
    D12 = 12
    D21 = 21

# Create mock modules that can be imported
import sys
from types import ModuleType

# Create mock neopixel module
neopixel_module = ModuleType('neopixel')
neopixel_module.NeoPixel = MockNeoPixel
sys.modules['neopixel'] = neopixel_module

# Create mock board module  
board_module = ModuleType('board')
board_module.D18 = MockBoard.D18
board_module.D12 = MockBoard.D12
board_module.D21 = MockBoard.D21
sys.modules['board'] = board_module
