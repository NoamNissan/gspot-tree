#!/usr/bin/env python3
"""
LED Web Controller - Control LED effects from your phone browser
"""

from flask import Flask, render_template, request, jsonify
import subprocess
import threading
import time
import os
import signal
import glob
import sys

# Add parent directory to path to import constants
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from constants import ChipType

CWD="."

# Global state manager (set by create_app)
state_manager = None

app = Flask(__name__)

# Dynamically load recipes from recipe_manager
def get_available_recipes():
    """Get recipes organized by category from recipe_manager"""
    import sys
    import os
    
    # Add parent directory to path to import led_ctrl
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    from led_ctrl.recipe_manager import RECIPES
    
    ring_recipes = []
    branch_recipes = []
    general_recipes = []
    
    for recipe_id, recipe in RECIPES.items():
        recipe_dict = {"id": recipe_id, "name": recipe.name, "description": recipe.description}
        
        # Categorize by name patterns
        if "ring" in recipe_id.lower():
            ring_recipes.append(recipe_dict)
        elif "branch" in recipe_id.lower():
            branch_recipes.append(recipe_dict)
        else:
            general_recipes.append(recipe_dict)
    
    return ring_recipes, branch_recipes, general_recipes

# Initialize recipes (will be called after CWD is set)
RING_RECIPES = []
BRANCH_RECIPES = []
GENERAL_RECIPES = []

# Global state tracking
current_recipe = None

def get_songs():
    """Get list of available songs organized by folder"""
    songs_dir = f"{CWD}/../songs"

    if not os.path.exists(songs_dir):
        return {}
    
    songs_by_folder = {}
    
    # Walk through all subdirectories
    for root, dirs, files in os.walk(songs_dir):
        # Get relative path from songs_dir
        rel_path = os.path.relpath(root, songs_dir)
        if rel_path == '.':
            rel_path = ''  # Root folder
        
        # Find all audio files in this directory
        audio_files = []
        for file in files:
            if file.lower().endswith(('.mp3', '.wav', '.m4a', '.flac')):
                audio_files.append(file)
        
        # Only add folder if it has audio files
        if audio_files:
            songs = []
            for filename in sorted(audio_files):
                name = os.path.splitext(filename)[0]
                # Store relative path from songs/ directory
                rel_file_path = os.path.join(rel_path, filename) if rel_path else filename
                songs.append({"filename": rel_file_path, "name": name})
            
            songs_by_folder[rel_path] = songs
    
    return songs_by_folder

def stop_current_recipe():
    """Stop current LED recipe by going to idle"""
    global state_manager, current_recipe
    if state_manager:
        state_manager.go_idle()
    current_recipe = None

def get_current_song():
    """Get the current song being played via StateManager"""
    global state_manager
    if state_manager:
        state = state_manager.get_state()
        if state.value == "PLAYING":
            # StateManager doesn't expose current_song directly, but we can check state
            return "playing"  # Indicate that something is playing
    return None

def run_recipe(recipe_id, pixels=60):
    """Run LED recipe using StateManager"""
    global current_recipe, state_manager
    
    if not state_manager:
        print("StateManager not available")
        return False
    
    # Use StateManager to start the recipe
    success = state_manager.start_led_recipe(recipe_id)
    if success:
        current_recipe = recipe_id
    return success

def run_recipe_with_params(recipe_id, pixels, freq, color):
    """Run LED recipe with custom parameters using StateManager"""
    global current_recipe, state_manager
    
    if not state_manager:
        print("StateManager not available")
        return False
    
    # For now, just run the recipe (parameter support can be added later if needed)
    # The color_strobe recipe should handle its own parameters
    success = state_manager.start_led_recipe(recipe_id)
    if success:
        current_recipe = f"{recipe_id} ({freq}Hz {color})"
    return success

def play_song(filename):
    """Play a song using StateManager"""
    global state_manager
    
    if not state_manager:
        return False
    
    # Convert relative path to absolute path
    songs_dir = os.path.join(CWD, "..", "songs")
    if not os.path.isabs(filename):
        filepath = os.path.join(songs_dir, filename)
    else:
        filepath = filename
    
    # Normalize the path
    filepath = os.path.normpath(filepath)
    
    if not os.path.exists(filepath):
        print(f"Song file not found: {filepath}")
        return False
    
    try:
        # Determine chip type based on directory
        if "single_chip" in filepath:
            chip_type = ChipType.SINGLE
        elif "double_chip" in filepath:
            chip_type = ChipType.DOUBLE
        else:
            # Default to single chip
            chip_type = ChipType.SINGLE
        
        state_manager.start_song(filepath, chip_type)
        return True
    except Exception as e:
        print(f"Error playing song: {e}")
        return False

@app.route('/')
def index():
    """Main control page"""
    songs = get_songs()
    current_song = get_current_song()
    return render_template('index.html', 
                         ring_recipes=RING_RECIPES, 
                         branch_recipes=BRANCH_RECIPES, 
                         general_recipes=GENERAL_RECIPES, 
                         songs=songs, 
                         current_recipe=current_recipe, 
                         current_song=current_song)

@app.route('/start/<recipe_id>')
def start_recipe(recipe_id):
    """Start a specific recipe, or toggle it off if already active"""
    pixels = request.args.get('pixels', 60, type=int)
    
    # Check if this recipe is already active as a manual override
    if state_manager:
        current_override = state_manager.get_manual_recipe_override()
        if current_override == recipe_id:
            # Same recipe is already active - deselect it
            if state_manager.stop_manual_recipe_override():
                global current_recipe
                current_recipe = None
                return jsonify({"status": "success", "recipe": None, "action": "deselected"})
    
    # Start the recipe
    if run_recipe(recipe_id, pixels):
        return jsonify({"status": "success", "recipe": recipe_id, "pixels": pixels, "action": "started"})
    else:
        return jsonify({"status": "error", "message": "Failed to start recipe"}), 500

@app.route('/stop')
def stop_recipe():
    """Stop current recipe and clear all LEDs, or return to music-reactive if music is playing"""
    global current_recipe, state_manager
    
    if state_manager:
        # Check if there's a manual override active
        if state_manager.get_manual_recipe_override():
            # Stop manual override (will return to music-reactive if music is playing)
            state_manager.stop_manual_recipe_override()
        else:
            # No manual override, stop current recipe and go to idle
            state_manager.go_idle()
            # Clear all LEDs
            state_manager.clear_all_leds()
    
    current_recipe = None
    return jsonify({"status": "success", "message": "Stopped and cleared"})

@app.route('/play/<path:filename>')
def play_music(filename):
    """Play a specific song"""
    if play_song(filename):
        return jsonify({"status": "success", "song": filename})
    else:
        return jsonify({"status": "error", "message": "Failed to play song"}), 500

@app.route('/stop_music')
def stop_music():
    """Stop current music"""
    global state_manager
    if state_manager:
        state_manager.end_song()
        return jsonify({"status": "success", "message": "Music stopped"})
    return jsonify({"status": "error", "message": "StateManager not available"}), 500

@app.route('/strobe')
def start_strobe():
    """Start color strobe with custom frequency and color"""
    freq = request.args.get('freq', 25, type=float)
    color = request.args.get('color', '255,255,255')
    pixels = request.args.get('pixels', 60, type=int)
    
    # Use color_strobe recipe with parameters
    if run_recipe_with_params('color_strobe', pixels, freq, color):
        return jsonify({"status": "success", "frequency": freq, "color": color})
    else:
        return jsonify({"status": "error", "message": "Failed to start strobe (may be playing music)"}), 500

@app.route('/crawl')
def start_crawl():
    """Start LED crawl mode"""
    global current_recipe, state_manager
    
    if not state_manager:
        return jsonify({"status": "error", "message": "StateManager not available"}), 500
    
    blink_time = request.args.get('blink_time', 2.0, type=float)
    
    success = state_manager.led_crawl(blink_time)
    if success:
        current_recipe = f"LED Crawl ({blink_time}s blink)"
        return jsonify({"status": "success", "mode": "crawl", "blink_time": blink_time})
    else:
        return jsonify({"status": "error", "message": "Cannot start crawl: song is currently playing"}), 500

@app.route('/set_led_range')
def set_led_range():
    """Set specific LED range"""
    global current_recipe, state_manager
    
    if not state_manager:
        return jsonify({"status": "error", "message": "StateManager not available"}), 500
    
    led_range = request.args.get('range', '')
    
    if not led_range:
        return jsonify({"status": "error", "message": "Range parameter required"}), 400
    
    success = state_manager.set_led_range(led_range)
    if success:
        current_recipe = f"LED Range: {led_range}"
        return jsonify({"status": "success", "mode": "range", "range": led_range})
    else:
        return jsonify({"status": "error", "message": "Cannot set LED range: song is currently playing"}), 500

@app.route('/set_ring/<int:ring_id>')
def set_ring(ring_id):
    """Set specific ring"""
    global current_recipe, state_manager
    
    if not state_manager:
        return jsonify({"status": "error", "message": "StateManager not available"}), 500
    
    success = state_manager.set_ring(ring_id)
    if success:
        current_recipe = f"Ring {ring_id}"
        return jsonify({"status": "success", "mode": "ring", "ring": ring_id})
    else:
        return jsonify({"status": "error", "message": "Cannot set ring: song is currently playing"}), 500

@app.route('/set_branch/<int:branch_id>')
def set_branch(branch_id):
    """Set specific branch"""
    global current_recipe, state_manager
    
    if not state_manager:
        return jsonify({"status": "error", "message": "StateManager not available"}), 500
    
    success = state_manager.set_branch(branch_id)
    if success:
        current_recipe = f"Branch {branch_id}"
        return jsonify({"status": "success", "mode": "branch", "branch": branch_id})
    else:
        return jsonify({"status": "error", "message": "Cannot set branch: song is currently playing"}), 500

@app.route('/volume', methods=['POST'])
def set_volume():
    """Set Master volume (0-100)"""
    try:
        volume = request.json.get('volume', 50)
        volume = max(0, min(100, int(volume)))  # Clamp 0-100
        
        # Set Master volume using amixer
        subprocess.run(['amixer', 'set', 'Master', f'{volume}%'], check=True)
        
        return jsonify({"status": "success", "volume": volume})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/volume', methods=['GET'])
def get_volume():
    """Get current Master volume"""
    try:
        result = subprocess.run(['amixer', 'get', 'Master'], capture_output=True, text=True)
        # Parse volume from output like: [50%]
        import re
        match = re.search(r'\[(\d+)%\]', result.stdout)
        volume = int(match.group(1)) if match else 50
        
        return jsonify({"status": "success", "volume": volume})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "volume": 50}), 200

@app.route('/status')
def get_status():
    """Get current status"""
    global current_recipe, state_manager
    
    # Check if a recipe is running (not playing music and recipe is set)
    music_playing = state_manager and state_manager.get_state().value == "PLAYING"
    manual_override = state_manager.get_manual_recipe_override() if state_manager else None
    
    # Recipe is running if:
    # 1. Not playing music and current_recipe is set, OR
    # 2. Playing music and manual override is active
    recipe_running = (not music_playing and current_recipe is not None) or (music_playing and manual_override is not None)
    
    # Use manual override recipe name if available, otherwise use current_recipe
    active_recipe = manual_override if manual_override else (current_recipe if recipe_running else None)
    
    current_song = get_current_song()
    
    return jsonify({
        "running": recipe_running,
        "recipe": active_recipe,
        "music_playing": music_playing,
        "current_song": current_song if music_playing else None,
        "manual_override": manual_override is not None
    })

def create_app(state_mgr=None, cwd=".", port=5000):
    """Create and configure the Flask app with StateManager"""
    global state_manager, CWD, RING_RECIPES, BRANCH_RECIPES, GENERAL_RECIPES
    state_manager = state_mgr
    CWD = cwd
    # Load recipes after CWD is set
    RING_RECIPES, BRANCH_RECIPES, GENERAL_RECIPES = get_available_recipes()
    return app

def run_app(port=5000, host='0.0.0.0', debug=False):
    """Run the Flask app"""
    print(f"🌐 LED Web Controller starting...")
    print(f"📁 Working directory: {CWD}")
    print(f"📱 Access from your phone: http://<raspberry-pi-ip>:{port}")
    
    try:
        # Use werkzeug's development server
        from werkzeug.serving import make_server
        server = make_server(host, port, app, threaded=True)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Web controller shutting down...")
        stop_current_recipe()
    except Exception as e:
        print(f"Error in web controller server: {e}")
        stop_current_recipe()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='LED Web Controller')
    parser.add_argument('--cwd', type=str, default='.', help='Working directory for spawned processes (default: current directory)')
    parser.add_argument('--port', type=int, default=5000, help='Port to run server on (default: 5000)')
    args = parser.parse_args()
    
    # Override CWD if provided
    CWD = args.cwd
    
    run_app(port=args.port)
