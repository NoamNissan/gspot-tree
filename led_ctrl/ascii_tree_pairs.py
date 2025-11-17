#!/usr/bin/env python3
import math
import yaml

def load_tree_config(config_path):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def generate_ascii_tree_with_pairs(led_colors, tree_config, width=120, height=80):
    """Generate ASCII art of the tree with LED colors shown as adjacent pairs"""
    # Create empty grid
    grid = [[' ' for _ in range(width)] for _ in range(height)]
    
    center_x, center_y = width // 2, height // 2
    max_radius_x = width // 2 - 5  # Horizontal radius (wider)
    max_radius_y = height // 2 - 5  # Vertical radius (narrower)
    inner_radius = min(max_radius_x, max_radius_y) // 5
    
    # Draw tree structure
    num_branches = len(tree_config['branches'])
    line_angle_step = 2 * math.pi / num_branches
    
    # Draw radial lines (branches) and label them
    for branch_idx in range(num_branches):
        angle = branch_idx * line_angle_step
        
        # Determine line character based on angle
        angle_deg = math.degrees(angle) % 360
        if 22.5 <= angle_deg < 67.5:
            line_char = '\\'
        elif 67.5 <= angle_deg < 112.5:
            line_char = '|'
        elif 112.5 <= angle_deg < 157.5:
            line_char = '/'
        elif 157.5 <= angle_deg < 202.5:
            line_char = '-'
        elif 202.5 <= angle_deg < 247.5:
            line_char = '\\'
        elif 247.5 <= angle_deg < 292.5:
            line_char = '|'
        elif 292.5 <= angle_deg < 337.5:
            line_char = '/'
        else:
            line_char = '-'
        
        # Draw branch line with elliptical shape
        for r in range(inner_radius, min(max_radius_x, max_radius_y)):
            # Use elliptical coordinates for stretching
            x = int(center_x + r * math.cos(angle) * (max_radius_x / max_radius_y))
            y = int(center_y + r * math.sin(angle))
            if 0 <= x < width and 0 <= y < height:
                if grid[y][x] == ' ':
                    grid[y][x] = line_char
        
        # Add branch number at the end
        label_x = int(center_x + (min(max_radius_x, max_radius_y) + 1) * math.cos(angle) * (max_radius_x / max_radius_y))
        label_y = int(center_y + (min(max_radius_x, max_radius_y) + 1) * math.sin(angle))
        
        # Place two-digit branch number (00-19)
        branch_str = f"{branch_idx:02d}"
        
        # Place first digit
        if 0 <= label_x-1 < width and 0 <= label_y < height:
            grid[label_y][label_x-1] = branch_str[0]
        
        # Place second digit  
        if 0 <= label_x < width and 0 <= label_y < height:
            grid[label_y][label_x] = branch_str[1]
    
    # Place LED pairs on branches
    available_length = min(max_radius_x, max_radius_y) - inner_radius - 5
    three_pair_positions = [0.10, 0.6, 1.00]
    two_pair_positions = [0.35, 0.8]
    
    def color_to_char(color):
        if color == (255, 255, 255):
            return 'w'
        elif color == (255, 0, 0):
            return 'r'
        elif color == (0, 255, 0):
            return 'g'
        elif color == (0, 0, 255):
            return 'b'
        elif color == (0, 0, 0):
            return 'n'
        else:
            return 's'
    
    led_index = 0
    for branch_idx, branch_leds in enumerate(tree_config['branches']):
        line_angle = branch_idx * line_angle_step
        num_pairs = len(branch_leds)
        
        positions = three_pair_positions if num_pairs == 3 else two_pair_positions
        
        for pair_idx in range(num_pairs):
            base_distance = inner_radius + 2 + positions[pair_idx] * available_length
            r = int(base_distance)
            
            # Get pair of LED colors
            if led_index < len(led_colors) and led_index + 1 < len(led_colors):
                color1 = led_colors[led_index]
                color2 = led_colors[led_index + 1]
                
                char1 = color_to_char(color1)
                char2 = color_to_char(color2)
                
                # Place pair adjacent to each other horizontally with elliptical positioning
                pair_x = int(center_x + r * math.cos(line_angle) * (max_radius_x / max_radius_y))
                pair_y = int(center_y + r * math.sin(line_angle))
                
                # Always place pairs horizontally (side by side)
                if 0 <= pair_x-1 < width and 0 <= pair_y < height:
                    grid[pair_y][pair_x-1] = char1
                if 0 <= pair_x < width and 0 <= pair_y < height:
                    grid[pair_y][pair_x] = char2
                
                led_index += 2
    
    # Convert grid to string
    return '\n'.join(''.join(row) for row in grid)

def create_test_colors():
    """Create test LED colors - one branch with all white, others colored"""
    colors = []
    
    # Branch 0: all white (6 LEDs)
    colors.extend([(255, 255, 255)] * 6)
    
    # Remaining branches: mix of colors
    for i in range(94):  # 100 total - 6 white = 94
        if i % 4 == 0:
            colors.append((255, 0, 0))    # Red
        elif i % 4 == 1:
            colors.append((0, 255, 0))    # Green  
        elif i % 4 == 2:
            colors.append((0, 0, 255))    # Blue
        else:
            colors.append((128, 128, 0))  # Shade
    
    return colors

if __name__ == "__main__":
    tree_config = load_tree_config('tree_config.yaml')
    test_colors = create_test_colors()
    
    ascii_art = generate_ascii_tree_with_pairs(test_colors, tree_config)
    print(ascii_art)
    
    # Count white LEDs and show branch mapping
    white_count = sum(1 for color in test_colors if color == (255, 255, 255))
    print(f"\nWhite LEDs: {white_count}")
    print("Branch labels: 00-19 (two digits for each branch)")
    print("LED pairs shown as adjacent characters (e.g., 'ww' = white pair, 'br' = blue-red pair)")
