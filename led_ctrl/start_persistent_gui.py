#!/usr/bin/env python3
"""
Start persistent GUI server for LED visualization
"""
import argparse
import sys
import os

# Handle both direct script execution and module import
if __name__ == "__main__" and __package__ is None:
    # Add parent directory to path for direct script execution
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "led_ctrl"

from .mock_neopixel import start_persistent_gui

def main():
    parser = argparse.ArgumentParser(description='Start persistent LED GUI')
    parser.add_argument('--pixels', type=int, default=100, help='Number of pixels (default: 100)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--tree-config', type=str, help='Tree configuration YAML file')
    parser.add_argument('--ascii', action='store_true', help='Enable ASCII tree mode (console output instead of GUI)')
    
    args = parser.parse_args()
    
    # Load tree structure if provided
    tree_structure = None
    if args.tree_config:
        try:
            from .tree_config import load_tree_config
            from .pipeline_demo import TreeStructure
            
            tree_data = load_tree_config(args.tree_config, verbose=True)
            tree_structure = TreeStructure(tree_data['rings'], tree_data['branches'])
            print(f"🌲 Tree config loaded: {len(tree_structure.rings)} rings, {len(tree_structure.branches)} branches")
        except Exception as e:
            print(f"❌ Failed to load tree config: {e}")
    
    # Enable ASCII mode if requested
    if args.ascii:
        print("🌲 ASCII tree mode enabled - will print to console alongside GUI")
    
    print(f"🖥️ Starting persistent LED GUI with {args.pixels} pixels")
    print("   Close the window to stop the server")
    
    start_persistent_gui(args.pixels, verbose=args.verbose, tree_structure=tree_structure, ascii=args.ascii)

if __name__ == "__main__":
    main()
