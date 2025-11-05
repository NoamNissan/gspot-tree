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

app = Flask(__name__)

# Available recipes organized by category
RING_RECIPES = [
    {"id": "ring_ripple", "name": "Ring Ripple", "description": "Ripple effect through tree rings"}
]

BRANCH_RECIPES = [
    {"id": "branch_sweep", "name": "Branch Sweep", "description": "Sweep effect around tree branches"}
]

GENERAL_RECIPES = [
    {"id": "complex_demo", "name": "Complex Demo", "description": "Multi-effect demonstration"},
    {"id": "sunset_breathing", "name": "Sunset Breathing", "description": "Calm red-pink breathing"},
    {"id": "rainbow_wave", "name": "Rainbow Wave", "description": "Rainbow with wave effects"},
    {"id": "rainbow", "name": "Pure Rainbow", "description": "Classic rainbow cycling"},
    {"id": "music_spectrum", "name": "Music Spectrum", "description": "3-band spectrum (bottom-up)"},
    {"id": "music_spectrum_c", "name": "Music Spectrum Center", "description": "3-band spectrum (center-out)"},
    {"id": "spectrum_enhanced", "name": "Enhanced Spectrum", "description": "6-band spectrum (bottom-up)"},
    {"id": "spectrum_enhanced_c", "name": "Enhanced Spectrum Center", "description": "6-band spectrum (center-out)"},
    {"id": "spectrum_enhanced_9", "name": "Enhanced Spectrum 9-Band", "description": "9-band spectrum"},
    {"id": "spectrum_enhanced_9_c", "name": "Enhanced Spectrum 9-Band Center", "description": "9-band spectrum (center-out)"},
    {"id": "spectrum_enhanced_12", "name": "Enhanced Spectrum 12-Band", "description": "12-band spectrum"},
    {"id": "spectrum_enhanced_12_c", "name": "Enhanced Spectrum 12-Band Center", "description": "12-band spectrum (center-out)"},
    {"id": "music_spectrum_morph", "name": "Music Spectrum Morphing", "description": "3-band spectrum with color morphing"},
    {"id": "music_spectrum_c_morph", "name": "Music Spectrum Center Morphing", "description": "3-band center spectrum with color morphing"},
    {"id": "spectrum_enhanced_morph", "name": "Enhanced Spectrum Morphing", "description": "6-band spectrum with color morphing"},
    {"id": "spectrum_enhanced_c_morph", "name": "Enhanced Spectrum Center Morphing", "description": "6-band center spectrum with color morphing"},
    {"id": "spectrum_enhanced_9_morph", "name": "Enhanced Spectrum 9-Band Morphing", "description": "9-band spectrum with color morphing"},
    {"id": "spectrum_enhanced_12_morph", "name": "Enhanced Spectrum 12-Band Morphing", "description": "12-band spectrum with color morphing"},
    {"id": "music_pulse", "name": "Music Pulse", "description": "Colors pulse with music"},
    {"id": "spectrum_analyzer", "name": "Spectrum Analyzer", "description": "LedFx-style spectrum bars"},
    {"id": "energy_pulse", "name": "Energy Pulse", "description": "Energy-based color changes"},
    {"id": "wavelength_flow", "name": "Wavelength Flow", "description": "Traveling wavelength effect"},
    {"id": "rainbow_scroll", "name": "Rainbow Scroll", "description": "Scrolling rainbow pattern"},
    {"id": "frequency_bars", "name": "Frequency Bars", "description": "Audio frequency bar visualization"},
    {"id": "lava_lamp", "name": "Lava Lamp", "description": "Smooth flowing lava lamp effect"},
    {"id": "fire_demo", "name": "Fire Demo", "description": "Flickering fire effect"},
    {"id": "circle_scanner", "name": "Circle Scanner", "description": "Circular scanner effect"},
    {"id": "scanner", "name": "Scanner", "description": "Cylon eye scanner effect"},
    {"id": "digital_rain", "name": "Digital Rain", "description": "Matrix-style digital rain"},
    {"id": "melt_flow", "name": "Melt Flow", "description": "Melting color flow effect"},
    {"id": "water_ripples", "name": "Water Ripples", "description": "Calm water ripple effect"},
    {"id": "marching_ants", "name": "Marching Ants", "description": "Classic marching ants pattern"},
    {"id": "glitch_matrix", "name": "Glitch Matrix", "description": "Digital glitch corruption"},
    {"id": "power_bars", "name": "Power Bars", "description": "Power level visualization"},
    {"id": "fade_cycle", "name": "Fade Cycle", "description": "Smooth color fade cycling"},
    {"id": "color_blocks", "name": "Color Blocks", "description": "Moving color blocks"},
]

# Global process tracking
current_process = None
current_recipe = None
music_process = None
current_song = None

def get_songs():
    """Get list of available songs"""
    songs_dir = "/home/tao/repo/gspot-tree/songs"
    if not os.path.exists(songs_dir):
        return []
    
    song_files = []
    for ext in ['*.mp3', '*.wav', '*.m4a', '*.flac']:
        song_files.extend(glob.glob(os.path.join(songs_dir, ext)))
    
    songs = []
    for filepath in sorted(song_files):
        filename = os.path.basename(filepath)
        name = os.path.splitext(filename)[0]
        songs.append({"filename": filename, "name": name})
    
    return songs

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
        current_process = subprocess.Popen(
            cmd, 
            cwd="/home/tao/repo/gspot-tree/web_controller",
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
        current_process = subprocess.Popen(
            cmd, 
            cwd="/home/tao/repo/gspot-tree/web_controller",
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
    
    songs_dir = "/home/tao/repo/gspot-tree/songs"
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
        clear_process = subprocess.Popen(
            clear_cmd,
            cwd="/home/tao/repo/gspot-tree/web_controller",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        clear_process.wait(timeout=5)
    except Exception:
        pass  # If clearing fails, ignore
    
    current_recipe = None
    return jsonify({"status": "success", "message": "Stopped and cleared"})

@app.route('/play/<filename>')
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
    print("🌐 LED Web Controller starting...")
    print("📱 Access from your phone: http://<raspberry-pi-ip>:5000")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        kill_current_process()
        kill_music_process()
