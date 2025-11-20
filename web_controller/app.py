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

CWD="."

app = Flask(__name__)

# Dynamically load recipes from recipe_manager
def get_available_recipes():
    """Get recipes organized by category from recipe_manager"""
    import sys
    import os
    sys.path.insert(0, os.path.join(CWD, '..'))
    
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

RING_RECIPES, BRANCH_RECIPES, GENERAL_RECIPES = get_available_recipes()

# Global process tracking
current_process = None
current_recipe = None
music_process = None
current_song = None

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

def kill_current_process():
    """Kill the current LED orchestrator process"""
    global current_process
    if current_process and current_process.poll() is None:
        try:
            current_process.terminate()
            current_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            current_process.kill()
        current_process = None

def kill_music_process():
    """Kill the current music process"""
    global music_process, current_song
    if music_process and music_process.poll() is None:
        try:
            music_process.terminate()
            music_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            music_process.kill()
        music_process = None
        current_song = None

def run_recipe(recipe_id, pixels=60):
    """Run LED orchestrator with specified recipe"""
    global current_process, current_recipe
    
    # Kill any existing process
    kill_current_process()
    
    # Start new process
    cmd = [
        "python3", 
        "../led_ctrl/led_orchestrator.py", 
        "--recipe", recipe_id,
        "--pixels", str(pixels),
        "--tree-config", "../led_ctrl/tree_config.yaml"
    ]
   
    try:
        print("cmd",cmd)
        current_process = subprocess.Popen(
            cmd, 
            cwd=CWD,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        current_recipe = recipe_id
        return True
    except Exception as e:
        print(f"Error starting recipe {recipe_id}: {e}")
        return False

def run_recipe_with_params(recipe_id, pixels, freq, color):
    """Run LED orchestrator with recipe and custom parameters"""
    global current_process, current_recipe
    
    # Kill any existing process
    kill_current_process()
    
    # Start new process with parameters
    cmd = [
        "python3", 
        "../led_ctrl/led_orchestrator.py", 
        "--recipe", recipe_id,
        "--pixels", str(pixels),
        "--strobe-freq", str(freq),
        "--strobe-color", color
    ]
    
    try:
        print("cmd",cmd)
        current_process = subprocess.Popen(
            cmd, 
            cwd=CWD,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        current_recipe = f"{recipe_id} ({freq}Hz {color})"
        return True
    except Exception as e:
        print(f"Error starting strobe: {e}")
        return False

def play_song(filename):
    """Play a song using mpg123 or aplay"""
    global music_process, current_song
    
    # Kill any existing music
    kill_music_process()
    
    songs_dir = f"{CWD}/../songs"
    filepath = os.path.join(songs_dir, filename)
    
    if not os.path.exists(filepath):
        return False
    
    # Try mpg123 first, then aplay
    try:
        music_process = subprocess.Popen(
            ["mpg123", filepath],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        current_song = filename
        return True
    except FileNotFoundError:
        try:
            music_process = subprocess.Popen(
                ["aplay", filepath],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            current_song = filename
            return True
        except FileNotFoundError:
            return False

@app.route('/')
def index():
    """Main control page"""
    songs = get_songs()
    return render_template('index.html', 
                         ring_recipes=RING_RECIPES, 
                         branch_recipes=BRANCH_RECIPES, 
                         general_recipes=GENERAL_RECIPES, 
                         songs=songs, 
                         current_recipe=current_recipe, 
                         current_song=current_song)

@app.route('/start/<recipe_id>')
def start_recipe(recipe_id):
    """Start a specific recipe"""
    pixels = request.args.get('pixels', 60, type=int)
    
    if run_recipe(recipe_id, pixels):
        return jsonify({"status": "success", "recipe": recipe_id, "pixels": pixels})
    else:
        return jsonify({"status": "error", "message": "Failed to start recipe"}), 500

@app.route('/stop')
def stop_recipe():
    """Stop current recipe and clear all LEDs"""
    global current_recipe
    kill_current_process()
    
    # Wait a moment for process to fully stop
    import time
    time.sleep(0.2)
    
    # Clear all LEDs
    pixels = request.args.get('pixels', 60, type=int)
    try:
        clear_cmd = [
            "python3", 
            "../led_ctrl/led_orchestrator.py", 
            "--clear-all",
            "--pixels", str(pixels)
        ]
        print("cmd",clear_cmd)
        clear_process = subprocess.Popen(
            clear_cmd,
            cwd=CWD,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        clear_process.wait(timeout=5)
    except Exception:
        pass  # If clearing fails, ignore
    
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
    kill_music_process()
    return jsonify({"status": "success", "message": "Music stopped"})

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
        return jsonify({"status": "error", "message": "Failed to start strobe"}), 500

@app.route('/crawl')
def start_crawl():
    """Start LED crawl mode"""
    global current_process, current_recipe
    
    pixels = request.args.get('pixels', 60, type=int)
    blink_time = request.args.get('blink_time', 2.0, type=float)
    
    kill_current_process()
    
    cmd = [
        "python3", 
        "../led_ctrl/led_orchestrator.py", 
        "--led-crawl",
        "--pixels", str(pixels),
        "--crawl-blink-time", str(blink_time),
        "--tree-config", "../led_ctrl/tree_config.yaml"
    ]
    
    try:
        print("cmd",cmd)
        current_process = subprocess.Popen(
            cmd, 
            cwd=CWD,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        # Print first few lines of output
        for line in current_process.stdout:
            print("Process output:", line.decode().strip())

        current_recipe = f"LED Crawl ({blink_time}s blink)"
        return jsonify({"status": "success", "mode": "crawl", "blink_time": blink_time})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/set_led_range')
def set_led_range():
    """Set specific LED range"""
    global current_process, current_recipe
    
    pixels = request.args.get('pixels', 60, type=int)
    led_range = request.args.get('range', '')
    
    if not led_range:
        return jsonify({"status": "error", "message": "Range parameter required"}), 400
    
    kill_current_process()
    
    cmd = [
        "python3", 
        "../led_ctrl/led_orchestrator.py", 
        "--set-led-range", led_range,
        "--pixels", str(pixels),
        "--tree-config", "../led_ctrl/tree_config.yaml"
    ]
    
    try:
        print("cmd",cmd)
        current_process = subprocess.Popen(
            cmd, 
            cwd=CWD,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        current_recipe = f"LED Range: {led_range}"
        return jsonify({"status": "success", "mode": "range", "range": led_range})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/set_ring/<int:ring_id>')
def set_ring(ring_id):
    """Set specific ring"""
    global current_process, current_recipe
    
    pixels = request.args.get('pixels', 60, type=int)
    
    kill_current_process()
    
    cmd = [
        "python3", 
        "../led_ctrl/led_orchestrator.py", 
        "--set-ring", str(ring_id),
        "--pixels", str(pixels),
        "--tree-config", "../led_ctrl/tree_config.yaml"
    ]
    
    try:
        print("cmd",cmd)
        current_process = subprocess.Popen(
            cmd, 
            cwd=CWD,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        current_recipe = f"Ring {ring_id}"
        return jsonify({"status": "success", "mode": "ring", "ring": ring_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/set_branch/<int:branch_id>')
def set_branch(branch_id):
    """Set specific branch"""
    global current_process, current_recipe
    
    pixels = request.args.get('pixels', 60, type=int)
    
    kill_current_process()
    
    cmd = [
        "python3", 
        "../led_ctrl/led_orchestrator.py", 
        "--set-branch", str(branch_id),
        "--pixels", str(pixels),
        "--tree-config", "../led_ctrl/tree_config.yaml"
    ]
    
    try:
        current_process = subprocess.Popen(
            cmd, 
            cwd=CWD,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        current_recipe = f"Branch {branch_id}"
        return jsonify({"status": "success", "mode": "branch", "branch": branch_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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
    global current_process, current_recipe, music_process, current_song
    
    is_running = current_process and current_process.poll() is None
    music_playing = music_process and music_process.poll() is None
    
    return jsonify({
        "running": is_running,
        "recipe": current_recipe if is_running else None,
        "music_playing": music_playing,
        "current_song": current_song if music_playing else None
    })

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='LED Web Controller')
    parser.add_argument('--cwd', type=str, default='.', help='Working directory for spawned processes (default: current directory)')
    parser.add_argument('--port', type=int, default=5000, help='Port to run server on (default: 5000)')
    args = parser.parse_args()
    
    # Override CWD if provided
    CWD = args.cwd
    
    print("🌐 LED Web Controller starting...")
    print(f"📁 Working directory: {CWD}")
    print(f"📱 Access from your phone: http://<raspberry-pi-ip>:{args.port}")
    
    try:
        app.run(host='0.0.0.0', port=args.port, debug=False)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        kill_current_process()
        kill_music_process()
