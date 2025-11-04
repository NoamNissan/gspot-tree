#!/usr/bin/env python3
"""
Tree LED Configuration Loader
Maps linear LED indices to tree structure (rings and branches)
"""

import yaml
import json
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class TreeConfig:
    """Tree LED configuration"""
    branches: List[List[List[int]]]  # branches[branch][pair] = [led1, led2]
    rings: List[List[List[int]]]     # rings[ring][pair] = [led1, led2]
    
    def get_branch_leds(self, branch_index: int) -> List[int]:
        """Get all LED indices for a branch"""
        if branch_index >= len(self.branches):
            return []
        leds = []
        for pair in self.branches[branch_index]:
            leds.extend(pair)
        return leds
    
    def get_ring_leds(self, ring_index: int) -> List[int]:
        """Get all LED indices for a ring"""
        if ring_index >= len(self.rings):
            return []
        leds = []
        for pair in self.rings[ring_index]:
            leds.extend(pair)
        return leds

def load_tree_config(config_path: str) -> TreeConfig:
    """Load tree configuration from YAML or JSON file"""
    with open(config_path, 'r') as f:
        if config_path.endswith('.yaml') or config_path.endswith('.yml'):
            data = yaml.safe_load(f)
        else:
            data = json.load(f)
    
    return TreeConfig(
        branches=data['branches'],
        rings=data['rings']
    )

def create_example_config(output_path: str = 'tree_config.yaml'):
    """Create example tree configuration file"""
    config = {
        'rings': [
            # Ring 0 (closest to center) - pairs 0,1,2,3
            [0, 1, 2, 3],
            # Ring 1 (middle) - pairs 4,5,6,7,8,9
            [4, 5, 6, 7, 8, 9],
            # Ring 2 (outer) - pairs 10,11,12,13,14,15,16,17
            [10, 11, 12, 13, 14, 15, 16, 17]
        ],
        'branches': [
            # Branch 0 - pairs 0,4,10 (inner to outer)
            [0, 4, 10],
            # Branch 1 - pairs 1,5,11
            [1, 5, 11],
            # Branch 2 - pairs 2,6,12
            [2, 6, 12],
            # Branch 3 - pairs 3,7,13
            [3, 7, 13],
            # ... continue for all 20 branches
        ]
    }
    
    with open(output_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"Example config created: {output_path}")

if __name__ == "__main__":
    # Create example configuration
    create_example_config()
    
    # Load and test
    config = load_tree_config('tree_config.yaml')
    
    print("Tree Configuration Loaded:")
    print(f"Rings: {len(config.rings)}")
    print(f"Branches: {len(config.branches)}")
    
    # Test ring 0 LEDs
    ring0_leds = config.get_ring_leds(0)
    print(f"Ring 0 LEDs: {ring0_leds}")
    
    # Test branch 0 LEDs  
    branch0_leds = config.get_branch_leds(0)
    print(f"Branch 0 LEDs: {branch0_leds}")
