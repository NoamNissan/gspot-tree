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

def process_bypassed_leds(config_data: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """Validate YAML consistency, collect bypassed LEDs and convert negatives to positives"""
    
    bypassed_leds = set()
    
    # First pass: collect all bypassed LEDs
    def collect_bypassed(structure):
        for group in structure:
            for pair in group:
                for led in pair:
                    if isinstance(led, int) and led < 0:
                        bypassed_leds.add(abs(led))
    
    collect_bypassed(config_data['branches'])
    collect_bypassed(config_data['rings'])
    
    # Second pass: validate consistency - bypassed LEDs must be negative everywhere
    def validate_consistency(structure, structure_name):
        for group_idx, group in enumerate(structure):
            for pair_idx, pair in enumerate(group):
                for led_idx, led in enumerate(pair):
                    if isinstance(led, int):
                        led_num = abs(led)
                        if led_num in bypassed_leds and led > 0:
                            raise ValueError(
                                f"LED {led_num} is bypassed elsewhere but appears as positive "
                                f"in {structure_name}[{group_idx}][{pair_idx}][{led_idx}]. Must be -{led_num}."
                            )
    
    if verbose:
        print("🔧 Processing bypassed LEDs...")
        print(f"🔧 Found bypassed LEDs: {sorted(bypassed_leds)}")
    
    validate_consistency(config_data['branches'], 'branches')
    validate_consistency(config_data['rings'], 'rings')
    
    # Third pass: convert negatives to positives
    def convert_negatives(structure, structure_name):
        for group_idx, group in enumerate(structure):
            for pair_idx, pair in enumerate(group):
                for led_idx, led in enumerate(pair):
                    if isinstance(led, int) and led < 0:
                        bypassed_led_num = abs(led)
                        if verbose:
                            print(f"🔧 Converting -{bypassed_led_num} → {bypassed_led_num} in {structure_name}[{group_idx}][{pair_idx}][{led_idx}]")
                        pair[led_idx] = bypassed_led_num
    
    convert_negatives(config_data['branches'], 'branches')
    convert_negatives(config_data['rings'], 'rings')
    
    if verbose:
        print("✅ All negatives converted to positives, bypassed list created")
    
    return config_data, bypassed_leds

def load_tree_config(config_path: str, verbose: bool = False) -> tuple:
    """Load tree configuration and return config + bypassed LEDs list"""
    with open(config_path, 'r') as f:
        if config_path.endswith('.yaml') or config_path.endswith('.yml'):
            data = yaml.safe_load(f)
        else:
            data = json.load(f)
    
    # Process bypassed LEDs - convert negatives to positives and collect bypassed list
    processed_data, bypassed_leds = process_bypassed_leds(data, verbose)
    
    # Convert to flat LED index lists (no removal, just flattening)
    rings = []
    for ring_pairs in processed_data['rings']:
        ring_leds = []
        for pair in ring_pairs:
            ring_leds.extend(pair)
        rings.append(ring_leds)
    
    branches = []
    for branch_pairs in processed_data['branches']:
        branch_leds = []
        for pair in branch_pairs:
            branch_leds.extend(pair)
        branches.append(branch_leds)
    
    config = {
        'rings': rings,
        'branches': branches,
        'bypassed_leds': bypassed_leds
    }
    
    return config

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
    
    # Load and test with verbose output
    print("Loading tree configuration with verbose output:")
    config = load_tree_config('tree_config.yaml', verbose=True)
    
    print("Tree Configuration Loaded:")
    print(f"Rings: {len(config.rings)}")
    print(f"Branches: {len(config.branches)}")
    
    # Test ring 0 LEDs
    ring0_leds = config.get_ring_leds(0)
    print(f"Ring 0 LEDs: {ring0_leds}")
    
    # Test branch 0 LEDs  
    branch0_leds = config.get_branch_leds(0)
    print(f"Branch 0 LEDs: {branch0_leds}")
