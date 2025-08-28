"""
Mock neopixel library for LED simulation
"""
import tkinter as tk
import math
import random
from typing import Tuple, List

class MockNeoPixel:
    """Mock NeoPixel class that simulates LED pairs in random positions within a circle"""
    
    def __init__(self, pin, num_pixels: int, brightness: float = 1.0, auto_write: bool = True):
        self.num_pixels = num_pixels
        self.brightness = brightness
        self.auto_write = auto_write
        self._pixels = [(0, 0, 0)] * num_pixels
        self._closed = False
        
        # Create GUI
        self.root = tk.Tk()
        self.root.title(f"LED Simulator - {num_pixels} pixels ({num_pixels//2} pairs)")
        self.canvas = tk.Canvas(self.root, width=1000, height=800, bg='black')
        self.canvas.pack()
        
        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        # Create LED pairs in random positions within circle
        self.circles = []
        center_x, center_y = 400, 300
        max_radius = 250  # Maximum radius for LED placement
        led_size = 8
        pair_spacing = 18  # Distance between two LEDs in a pair
        
        # Create LED pairs on 20 radial lines with proper spacing
        self.circles = []
        center_x, center_y = 500, 400
        max_radius = 300  # R - bigger radius for bigger window
        inner_radius = max_radius / 5  # rc = R/5 - no LEDs in center
        led_size = 5  # Smaller LEDs
        pair_spacing = 12  # Distance between two LEDs in a pair
        
        # Create 20 radial lines
        num_lines = 20
        line_angle_step = 2 * math.pi / num_lines
        
        pair_positions = []
        
        for line in range(num_lines):
            # Each line gets 2-3 pairs
            pairs_on_line = random.randint(2, 3)
            
            # Line angle
            line_angle = line * line_angle_step
            
            # Divide the available radius into segments for even spacing
            available_length = max_radius - inner_radius - 40  # Leave margins
            segment_length = available_length / pairs_on_line
            
            for pair_idx in range(pairs_on_line):
                # Place pair in its segment with some randomness
                segment_start = inner_radius + 20 + pair_idx * segment_length
                segment_end = segment_start + segment_length
                r = random.uniform(segment_start, segment_end)
                
                # Position on the line
                pair_center_x = center_x + r * math.cos(line_angle)
                pair_center_y = center_y + r * math.sin(line_angle)
                
                # Random orientation for the pair (add some randomness to perpendicular)
                base_angle = line_angle + math.pi/2  # Perpendicular to radial line
                random_offset = random.uniform(-math.pi/4, math.pi/4)  # ±45 degrees
                pair_angle = base_angle + random_offset
                pair_positions.append((pair_center_x, pair_center_y, pair_angle))
        
        # Create LED circles for each pair
        led_index = 0
        for pair_idx, (pair_center_x, pair_center_y, pair_angle) in enumerate(pair_positions):
            # Position two LEDs as a pair (touching)
            for led_in_pair in range(2):
                if led_index >= num_pixels:
                    break
                    
                # Offset from pair center
                offset = (led_in_pair - 0.5) * pair_spacing
                led_x = pair_center_x + offset * math.cos(pair_angle)
                led_y = pair_center_y + offset * math.sin(pair_angle)
                
                # Create LED circle
                circle = self.canvas.create_oval(
                    led_x - led_size, led_y - led_size, 
                    led_x + led_size, led_y + led_size, 
                    fill='black', outline='gray', width=1
                )
                self.circles.append(circle)
                led_index += 1
            
            if led_index >= num_pixels:
                break
        
        # Fill remaining circles if we have fewer pairs than expected
        while len(self.circles) < num_pixels:
            # Create invisible placeholder circles
            circle = self.canvas.create_oval(-10, -10, -5, -5, fill='black', outline='black')
            self.circles.append(circle)
        
        # Draw circle boundaries and radial lines
        # Outer circle boundary
        self.canvas.create_oval(
            center_x - max_radius, center_y - max_radius,
            center_x + max_radius, center_y + max_radius,
            outline='darkgray', width=1, fill=''
        )
        
        # Inner circle (no LED zone) - same color as outer
        self.canvas.create_oval(
            center_x - inner_radius, center_y - inner_radius,
            center_x + inner_radius, center_y + inner_radius,
            outline='darkgray', width=1, fill=''
        )
        
        # 20 radial lines where LEDs are placed
        for line in range(num_lines):
            angle = line * line_angle_step
            x1 = center_x + inner_radius * math.cos(angle)
            y1 = center_y + inner_radius * math.sin(angle)
            x2 = center_x + max_radius * math.cos(angle)
            y2 = center_y + max_radius * math.sin(angle)
            self.canvas.create_line(x1, y1, x2, y2, fill='darkgray', width=1)
        
        # Add text showing LED indexing
        total_pairs = len(pair_positions)
        self.canvas.create_text(10, 10, text=f"LEDs 0-{total_pairs*2-1} ({total_pairs} pairs on 20 lines)", 
                               fill='white', anchor='nw')
    
    def __setitem__(self, index: int, color: Tuple[int, int, int]):
        """Set pixel color"""
        if 0 <= index < self.num_pixels:
            # Apply brightness
            r, g, b = color
            r = int(r * self.brightness)
            g = int(g * self.brightness)
            b = int(b * self.brightness)
            
            self._pixels[index] = (r, g, b)
            
            # Update GUI immediately if auto_write is True
            if self.auto_write:
                self._update_pixel(index, (r, g, b))
    
    def __getitem__(self, index: int) -> Tuple[int, int, int]:
        """Get pixel color"""
        return self._pixels[index]
    
    def _update_pixel(self, index: int, color: Tuple[int, int, int]):
        """Update a single pixel in the GUI"""
        if self._closed:
            return
        r, g, b = color
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        self.canvas.itemconfig(self.circles[index], fill=hex_color)
        self.root.update_idletasks()
    
    def show(self):
        """Update all pixels in the GUI"""
        if self._closed:
            return
        for i, color in enumerate(self._pixels):
            self._update_pixel(i, color)
        self.root.update()
    
    def fill(self, color: Tuple[int, int, int]):
        """Fill all pixels with the same color"""
        for i in range(self.num_pixels):
            self[i] = color
    
    def _on_window_close(self):
        """Handle window close event"""
        self._closed = True
        self.root.destroy()
        print("\nGUI window closed - press Ctrl+C to stop")
    
    def deinit(self):
        """Clean up resources"""
        try:
            self.root.destroy()
        except:
            pass
    
    def __len__(self):
        return self.num_pixels

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
