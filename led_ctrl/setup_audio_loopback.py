#!/usr/bin/env python3
"""
Set up PipeWire/PulseAudio loopback for simultaneous HDMI output and LED detection
Based on the working sound_controller.py approach
"""
import subprocess
import sys

def run_cmd(args):
    try:
        result = subprocess.run(args, check=True, text=True, capture_output=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(args)}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return None

def find_hdmi_sink():
    """Find HDMI sink name"""
    try:
        sinks = run_cmd(["pactl", "list", "short", "sinks"])
        if not sinks:
            return None
            
        for line in sinks.splitlines():
            parts = line.split('\t')
            if len(parts) >= 2:
                name = parts[1]
                if "hdmi" in name.lower():
                    return name
        return None
    except Exception as e:
        print(f"Failed to find HDMI sink: {e}")
        return None

def setup_loopback():
    """Set up PulseAudio loopback for HDMI + LED detection"""
    print("Setting up audio loopback...")
    
    # 1. Create null sink for loopback
    print("Creating null sink...")
    run_cmd([
        "pactl", "load-module", "module-null-sink",
        "sink_name=loopback_out",
        "sink_properties=device.description=LoopbackOut"
    ])
    
    # 2. Find HDMI sink
    hdmi_sink = find_hdmi_sink()
    if not hdmi_sink:
        print("ERROR: No HDMI sink found!")
        return False
    
    print(f"Found HDMI sink: {hdmi_sink}")
    
    # 3. Connect loopback from null sink monitor to HDMI
    print("Creating loopback connection...")
    run_cmd([
        "pactl", "load-module", "module-loopback",
        "source=loopback_out.monitor",
        f"sink={hdmi_sink}"
    ])
    
    # 4. Set null sink as default
    print("Setting default sink...")
    run_cmd(["pactl", "set-default-sink", "loopback_out"])
    run_cmd(["pactl", "set-default-source", "loopback_out.monitor"])
    
    print("✅ Audio loopback configured!")
    print("Now audio will go to both HDMI (you hear) and loopback_out.monitor (LEDs detect)")
    return True

def test_setup():
    """Test the loopback setup"""
    print("\nTesting setup...")
    print("Available sinks:")
    sinks = run_cmd(["pactl", "list", "short", "sinks"])
    if sinks:
        for line in sinks.splitlines():
            parts = line.split('\t')
            if len(parts) >= 2:
                print(f"  {parts[1]}")
    
    print("\nDefault sink:")
    default = run_cmd(["pactl", "get-default-sink"])
    if default:
        print(f"  {default}")

if __name__ == "__main__":
    if setup_loopback():
        test_setup()
        print("\n🎵 Ready to test!")
        print("Run: mpg123 'song.mp3' (should play to HDMI)")
        print("LEDs should detect from loopback_out.monitor")
    else:
        sys.exit(1)
