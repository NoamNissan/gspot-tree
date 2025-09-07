#!/usr/bin/env python3
"""
Start persistent GUI server for LED visualization
"""
import argparse
try:
    # Prefer package-relative import when executed as a module
    from .mock_neopixel import start_persistent_gui
except ImportError:
    # Fallback to support direct script execution (adds this dir to sys.path)
    import os
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from mock_neopixel import start_persistent_gui

def main():
    parser = argparse.ArgumentParser(description='Start persistent LED GUI')
    parser.add_argument('--pixels', type=int, default=100, help='Number of pixels (default: 100)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    print(f"🖥️ Starting persistent LED GUI with {args.pixels} pixels")
    print("   Close the window to stop the server")
    
    start_persistent_gui(args.pixels, verbose=args.verbose)

if __name__ == "__main__":
    main()
