from enum import Enum

# seconds to wait for second chip
DUAL_CHIP_WINDOW = 3

NUM_PIXELS = 100

PENDING_SOUND_FILE = "triangle-bell_D_sharp_minor.wav"

class ChipType(Enum):
    SINGLE = "single"
    DOUBLE = "double"