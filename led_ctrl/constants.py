"""
Constants for LED orchestrator
"""

from constants import NUM_PIXELS


# Persistent GUI configuration
PERSISTENT_GUI_PORT = 9998

NEOPIXEL_AUTO_WRITE = False

class LEDLayoutConstants:
    """Constants for LED layout configuration - 20 lines with 2-3 circles each"""

    RADIUS_MULTIPLIER = 1.3
    # Each line contains a list of radius values for circles on that line
    LAYOUT_DATA = [
        [100, 150, 200],  # Line 0: 3 circles at radius 100, 150, 200
        [120, 180],       # Line 1: 2 circles at radius 120, 180
        [90, 140, 190],   # Line 2: 3 circles at radius 90, 140, 190
        [110, 160],       # Line 3: 2 circles at radius 110, 160
        [130, 170, 210],  # Line 4: 3 circles at radius 130, 170, 210
        [95, 145],        # Line 5: 2 circles at radius 95, 145
        [105, 155, 195], # Line 6: 3 circles at radius 105, 155, 195
        [125, 175],      # Line 7: 2 circles at radius 125, 175
        [85, 135, 185],   # Line 8: 3 circles at radius 85, 135, 185
        [115, 165],      # Line 9: 2 circles at radius 115, 165
        [105, 155, 205], # Line 10: 3 circles at radius 105, 155, 205
        [135, 185],      # Line 11: 2 circles at radius 135, 185
        [95, 145, 195],   # Line 12: 3 circles at radius 95, 145, 195
        [125, 175],       # Line 13: 2 circles at radius 125, 175
        [110, 160, 210], # Line 14: 3 circles at radius 110, 160, 210
        [140, 190],      # Line 15: 2 circles at radius 140, 190
        [100, 150, 200], # Line 16: 3 circles at radius 100, 150, 200
        [120, 180],      # Line 17: 2 circles at radius 120, 180
        [90, 140, 190],  # Line 18: 3 circles at radius 90, 140, 190
        [130, 170]       # Line 19: 2 circles at radius 130, 170
    ]