"""
Mock neopixel library for LED simulation
"""
import tkinter as tk
import math
import random
import socket
import threading
import json
import sys
from typing import Tuple, List
from constants import PERSISTENT_GUI_PORT
from ascii_tree_pairs import generate_ascii_tree_with_pairs, load_tree_config



# Global persistent GUI instance
_persistent_gui = None
_persistent_mode = False

def set_persistent_mode(enabled: bool):
    """Enable or disable persistent GUI mode"""
    global _persistent_mode
    _persistent_mode = enabled

class PersistentGUI:
    """Persistent GUI that can be shared across multiple app runs"""
    
    def __init__(self, num_pixels: int, verbose: bool = True, tree_structure=None, ascii: bool = False):
        self.num_pixels = num_pixels
        self.verbose = verbose
        self.tree_structure = tree_structure
        self.ascii_mode = ascii
        
        # Load tree config for ASCII mode
        if ascii:
            if tree_structure:
                # Convert flattened branches back to pair format for ASCII
                paired_branches = []
                for branch_leds in tree_structure.branches:
                    pairs = []
                    for i in range(0, len(branch_leds), 2):
                        if i + 1 < len(branch_leds):
                            pairs.append([branch_leds[i], branch_leds[i + 1]])
                    paired_branches.append(pairs)
                self.tree_config_cache = {'branches': paired_branches}
                print(f"🌲 ASCII mode initialized with converted tree_structure")
            else:
                self.tree_config_cache = load_tree_config('tree_config.yaml')
                print(f"🌲 ASCII mode initialized with tree config from YAML")
        
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
        
        if self.tree_structure:
            # Use structured layout based on tree configuration
            pair_positions = self._generate_structured_layout(center_x, center_y, max_radius, inner_radius)
        else:
            # Use original random layout
            pair_positions = self._generate_random_layout(center_x, center_y, max_radius, inner_radius)
        
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
            current_pixels = [(0, 0, 0)] * self.num_pixels if self.ascii_mode else None
            
            while True:
                data = client.recv(1024)
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
                                if self.ascii_mode and current_pixels and command['index'] < len(current_pixels):
                                    current_pixels[command['index']] = tuple(command['color'])
                                self.root.after(0, lambda idx=command['index'], col=command['color']: self._update_pixel(idx, col))
                            elif command['type'] == 'bulk_update':
                                if self.verbose:
                                    print(f"   Bulk update: {len(command['pixels'])} LEDs")
                                if self.ascii_mode and current_pixels:
                                    for i, pixel in enumerate(command['pixels']):
                                        if i < len(current_pixels):
                                            current_pixels[i] = tuple(pixel)
                                self.root.after(0, lambda pixels=command['pixels']: self._update_all_pixels(pixels))
                            elif command['type'] == 'update_all_pixels':
                                if self.verbose:
                                    print(f"   Bulk update: {len(command['pixels'])} LEDs")
                                if self.ascii_mode and current_pixels:
                                    for i, pixel in enumerate(command['pixels']):
                                        if i < len(current_pixels):
                                            current_pixels[i] = tuple(pixel)
                                self.root.after(0, lambda pixels=command['pixels']: self._update_all_pixels(pixels))
                            elif command['type'] == 'show':
                                if self.verbose:
                                    print(f"   Show command (ASCII mode: {self.ascii_mode})")
                                # Always update GUI
                                self.root.after(0, lambda: self.canvas.update_idletasks())
                                # Also print ASCII if enabled
                                if self.ascii_mode:
                                    ascii_art = generate_ascii_tree_with_pairs(current_pixels, self.tree_config_cache)
                                    print('\033[2J\033[H')  # Clear screen and move cursor to top
                                    print(ascii_art)
                                    print(f"\nWhite LEDs: {sum(1 for r, g, b in current_pixels if (r, g, b) == (255, 255, 255))}")
                                    print("Branch labels: 00-19 (two digits for each branch)")
                                    print("LED pairs shown as adjacent characters (e.g., 'ww' = white pair, 'br' = blue-red pair)")
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON error: {e} - Line: {line}")
                
        except Exception as e:
            print(f"Client handler error: {e}")
            import traceback
            traceback.print_exc()
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
    
    def _generate_random_layout(self, center_x, center_y, max_radius, inner_radius):
        """Generate random LED layout (original behavior)"""
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
        
        return pair_positions
    
    def _generate_structured_layout(self, center_x, center_y, max_radius, inner_radius):
        """Generate structured LED layout based on tree configuration"""
        pair_positions = []
        num_branches = len(self.tree_structure.branches)
        line_angle_step = 2 * math.pi / num_branches
        available_length = max_radius - inner_radius - 40
        
        # Define prototypes
        three_pair_positions = [0.10, 0.55, 1.00]  # 10%, 55%, 100%
        two_pair_positions = [0.325, 0.775]          # 32.5%, 77.5%
        
        for branch_idx, branch_leds in enumerate(self.tree_structure.branches):
            line_angle = branch_idx * line_angle_step
            
            # Determine number of pairs from branch LED count
            num_pairs = len(branch_leds) // 2
            
            # Choose prototype based on pair count
            if num_pairs == 3:
                positions = three_pair_positions
            elif num_pairs == 2:
                positions = two_pair_positions
            else:
                # Fallback for other counts
                positions = [0.3, 0.7] if num_pairs == 2 else [0.15, 0.55, 0.95]
            
            for pair_idx in range(min(num_pairs, len(positions))):
                # Calculate position along branch with small random error
                base_distance = inner_radius + 20 + positions[pair_idx] * available_length
                distance_error = random.uniform(-5, 5)  # Small random error
                r = base_distance + distance_error
                
                pair_center_x = center_x + r * math.cos(line_angle)
                pair_center_y = center_y + r * math.sin(line_angle)
                
                # Apply random orientation (preserve existing behavior)
                base_angle = line_angle + math.pi/2
                random_offset = random.uniform(-math.pi/4, math.pi/4)
                pair_angle = base_angle + random_offset
                pair_positions.append((pair_center_x, pair_center_y, pair_angle))
        
        return pair_positions
    
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
    
    def __init__(self, pin, num_pixels: int, brightness: float = 1.0, auto_write: bool = True, tree_structure=None, pixel_order=None):
        self.num_pixels = num_pixels
        self.brightness = brightness
        self.auto_write = auto_write
        self.tree_structure = tree_structure
        self._pixels = [(0, 0, 0)] * num_pixels
        self._closed = False
        self._dirty = False  # Track if pixels have changed
        
        global _persistent_gui, _persistent_mode
        
        if _persistent_mode:
            # Try to connect to persistent GUI
            self._connect_to_persistent_gui()
        else:
            # Create own GUI (original behavior)
            self._create_own_gui()
    
    def _connect_to_persistent_gui(self):
        """Connect to persistent GUI via socket"""
        self.client_socket = None
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect(('localhost', PERSISTENT_GUI_PORT))
            print("🖥️ Connected to persistent GUI")
        except:
            print("🖥️ No persistent GUI found, creating new one...")
            self._create_own_gui()
    
    def _create_own_gui(self):
        """Create own GUI window (original behavior)"""
        self.client_socket = None
        self.root = tk.Tk()
        self.root.title(f"LED Simulator - {self.num_pixels} pixels")
        self.canvas = tk.Canvas(self.root, width=1000, height=800, bg='black')
        self.canvas.pack()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        # Create LED visualization
        self.circles = []
        center_x, center_y = 500, 400
        max_radius = 300
        inner_radius = max_radius / 5
        led_size = 5
        pair_spacing = 12
        
        if self.tree_structure:
            # Use structured layout based on tree configuration
            pair_positions = self._generate_structured_layout(center_x, center_y, max_radius, inner_radius)
        else:
            # Use original random layout
            pair_positions = self._generate_random_layout(center_x, center_y, max_radius, inner_radius)
        
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
        num_lines = 20
        line_angle_step = 2 * math.pi / num_lines
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
    
    def __setitem__(self, key, value):
        """Set pixel color(s) - supports single pixels, slices, and bytearrays"""
        if isinstance(key, slice):
            # Bulk assignment - handle different input types
            if isinstance(value, bytearray):
                # Convert bytearray([R,G,B,R,G,B,...]) to tuples
                num_pixels = len(value) // 3
                for i in range(min(num_pixels, self.num_pixels)):
                    r = value[i * 3 + 0]
                    g = value[i * 3 + 1] 
                    b = value[i * 3 + 2]
                    self._set_single_pixel(i, (r, g, b))
            elif isinstance(value, (list, tuple)):
                # Handle list/tuple of RGB tuples
                for i, color in enumerate(value):
                    if i >= self.num_pixels:
                        break
                    self._set_single_pixel(i, color)
            else:
                raise TypeError(f"Unsupported bulk assignment type: {type(value)}")
        else:
            # Single pixel assignment
            self._set_single_pixel(key, value)
    
    def _set_single_pixel(self, index: int, color: Tuple[int, int, int]):
        """Set a single pixel color"""
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
        else:
            # Update own GUI
            r, g, b = color
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            self.canvas.itemconfig(self.circles[index], fill=hex_color)
            self.root.update_idletasks()
    
    def show(self):
        """Update all pixels"""
        if self._closed or not self._dirty:
            return
        
        self._dirty = False
        
        # ASCII mode - print tree to console via persistent GUI
        global _persistent_gui
        if _persistent_gui and hasattr(_persistent_gui, 'ascii_mode') and _persistent_gui.ascii_mode:
            try:
                tree_config = _persistent_gui.tree_config_cache if hasattr(_persistent_gui, 'tree_config_cache') else load_tree_config('tree_config.yaml')
                ascii_art = generate_ascii_tree_with_pairs(self._pixels, tree_config)
                # Clear screen and print tree
                print('\033[2J\033[H')  # Clear screen and move cursor to top
                print(ascii_art)
                print(f"\nWhite LEDs: {sum(1 for r, g, b in self._pixels if (r, g, b) == (255, 255, 255))}")
                print("Branch labels: 00-19 (two digits for each branch)")
                print("LED pairs shown as adjacent characters (e.g., 'ww' = white pair, 'br' = blue-red pair)")
                return
            except Exception as e:
                print(f"ASCII mode error: {e}")
        
        if self.client_socket:
            try:
                # Send bulk update (more efficient)
                pixels_array = [[r, g, b] for r, g, b in self._pixels]
                command = {
                    'type': 'bulk_update',
                    'pixels': pixels_array
                }
                message = json.dumps(command) + '\n'
                self.client_socket.send(message.encode())
                
                # Then send show command
                command = {'type': 'show'}
                message = json.dumps(command) + '\n'
                self.client_socket.send(message.encode())
            except:
                pass
        else:
            for i, color in enumerate(self._pixels):
                self._update_pixel(i, color)
            self.root.update()
    
    def fill(self, color: Tuple[int, int, int]):
        """Fill all pixels with the same color"""
        for i in range(self.num_pixels):
            self[i] = color
    
    def _generate_random_layout(self, center_x, center_y, max_radius, inner_radius):
        """Generate random LED layout (original behavior)"""
        print("⚠️ WARNING - SIMULATION IN RANDOM LAYOUT")
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
        
        return pair_positions
    
    def _generate_structured_layout(self, center_x, center_y, max_radius, inner_radius):
        """Generate structured LED layout based on tree configuration"""
        print("✅ SIMULATION USING TREE LAYOUT")
        pair_positions = []
        num_branches = len(self.tree_structure.branches)
        line_angle_step = 2 * math.pi / num_branches
        available_length = max_radius - inner_radius - 15
        
        # Define prototypes
        three_pair_positions = [0.10, 0.6, 1.00]  # 10%, 55%, 100%
        two_pair_positions = [0.35, 0.8]          # 32.5%, 77.5%
        
        for branch_idx, branch_leds in enumerate(self.tree_structure.branches):
            line_angle = branch_idx * line_angle_step
            
            # Determine number of pairs from branch LED count
            num_pairs = len(branch_leds) // 2
            
            # Choose prototype based on pair count
            if num_pairs == 3:
                positions = three_pair_positions
            elif num_pairs == 2:
                positions = two_pair_positions
            else:
                print("Invalid tree configuration")
                assert(0)
            
            for pair_idx in range(min(num_pairs, len(positions))):
                # Calculate position along branch with small random error
                base_distance = inner_radius + 5 + positions[pair_idx] * available_length
                distance_error = random.uniform(-10, 10)  # Small random error
                r = base_distance + distance_error
                
                pair_center_x = center_x + r * math.cos(line_angle)
                pair_center_y = center_y + r * math.sin(line_angle)
                
                # Apply random orientation (preserve existing behavior)
                base_angle = line_angle + math.pi/2
                random_offset = random.uniform(-math.pi/4, math.pi/4)
                pair_angle = base_angle + random_offset
                pair_positions.append((pair_center_x, pair_center_y, pair_angle))
        
        return pair_positions
    
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

def start_persistent_gui(num_pixels: int = 100, verbose: bool = True, tree_structure=None, ascii: bool = False):
    """Start persistent GUI in separate process"""
    global _persistent_gui
    if _persistent_gui is None:
        _persistent_gui = PersistentGUI(num_pixels, verbose=verbose, tree_structure=tree_structure, ascii=ascii)
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

neopixel_module.RGB="RGB"

