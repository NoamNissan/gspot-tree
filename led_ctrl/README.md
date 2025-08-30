# 🎵 LED Orchestrator

A powerful, composable LED effects system with real-time music visualization and smart recipe transitions.

## ✨ Features

- **🍽️ Recipe System**: Data-driven LED configurations with smart transitions
- **🎵 Music Visualization**: Real-time audio analysis with multiple visualization modes
- **⚡ Layered Effects**: Combine multiple effects seamlessly (breathing + sparkle + music)
- **🔄 Smart Transitions**: Effects continue smoothly when switching recipes
- **🎨 Multiple Effects**: Breathing, strobe, sparkle, wave, random flash, music reactive
- **🖥️ GUI Simulator**: Test effects without hardware
- **🥧 Raspberry Pi Ready**: Optimized for real LED strips

## 🚀 Quick Start

### Installation

```bash
# Clone and navigate
cd led_ctrl

# Install Python dependencies
pip install -r requirements.txt

# For Raspberry Pi with real LEDs (optional):
# sudo pip install rpi-ws281x adafruit-circuitpython-neopixel
```

### Basic Usage

```bash
# Run full demo sequence (all recipes)
python led_orchestrator.py

# Run specific recipe
python led_orchestrator.py --recipe music_pulse

# Custom pixel count
python led_orchestrator.py --recipe music_spectrum --pixels 200
```

## 🍽️ Available Recipes

### **complex_demo** - Complex Demo
Multi-effect demonstration with breathing, sparkle, wave, and strobe effects.

### **sunset_breathing** - Sunset Breathing 🌅
Calm red-pink color transition with gentle breathing and random white flashes.

### **rainbow_wave** - Rainbow Wave
Rainbow color cycling with wave effects and sparkles.

### **rainbow** - Pure Rainbow 🌈
Classic rainbow cycling effect, similar to the old demo.

### **music_spectrum** - Music Spectrum Analyzer 🎵
Real-time 3-band spectrum analyzer (bass=red, mid=green, high=blue).

### **music_pulse** - Music Pulse 🎵
Red-blue color fade with brightness pulsing to music amplitude.

## 🎵 Music Visualization

The system captures **real-time system audio** for music visualization:

### Audio Setup
- **macOS**: Uses Core Audio (built-in) - no additional setup needed
- **System Audio**: Install [BlackHole](https://github.com/ExistentialAudio/BlackHole) for system audio capture
- **Raspberry Pi**: Works with ALSA/PulseAudio out of the box

### Music Modes
- **spectrum**: 3-band frequency analyzer with colored bars
- **pulse**: Base colors pulse with music amplitude  
- **wave**: Wave effects driven by bass levels
- **strobe**: White flashes on beat detection

## 🎨 Recipe Architecture

### Recipe Structure
```python
Recipe(
    name="My Recipe",
    description="Custom LED effect",
    base_colors=BaseColorConfig(
        colors=[Color(255, 0, 0), Color(0, 0, 255)],  # Red to blue
        mode=TransitionMode.FADE,
        speed=0.2
    ),
    effects=[
        EffectConfig("breathing", {"speed": 0.5, "min_intensity": 0.3}),
        EffectConfig("music_visualizer", {"mode": "pulse", "sensitivity": 1.0})
    ]
)
```

### Base Color Modes
- **STATIC**: Single color or repeating pattern
- **CYCLE**: Cycle through colors over time
- **FADE**: Smooth transitions between colors
- **RANDOM**: Random color selection

### Available Effects
- **breathing**: Sine wave intensity modulation
- **strobe**: Rapid on/off flashing  
- **sparkle**: Random pixel highlights
- **wave**: Traveling wave patterns
- **random_flash**: Random single LED flashes
- **music_visualizer**: Real-time audio reactive effects

## 🔧 Configuration

### Effect Parameters

#### Breathing Effect
```python
EffectConfig("breathing", {
    "speed": 1.0,           # Breathing rate
    "min_intensity": 0.3,   # Minimum brightness (0.0-1.0)
    "max_intensity": 1.0    # Maximum brightness (0.0-1.0)
})
```

#### Music Visualizer
```python
EffectConfig("music_visualizer", {
    "mode": "pulse",        # spectrum, pulse, wave, strobe
    "sensitivity": 1.0,     # Audio sensitivity multiplier
    "bass_boost": 2.0       # Extra bass emphasis
})
```

#### Sparkle Effect
```python
EffectConfig("sparkle", {
    "density": 0.05,        # Percentage of pixels sparkling
    "brightness": 1.0       # Sparkle intensity
})
```

## 🥧 Raspberry Pi Setup

### Hardware Requirements
- **Raspberry Pi 3/4** (Pi Zero 2 works but with fewer LEDs)
- **WS2812B LED strip** (NeoPixels)
- **External 5V power supply** for LEDs
- **Level shifter** (3.3V → 5V, optional but recommended)

### Wiring
```
Raspberry Pi GPIO 18 → LED Data Pin
5V Power Supply → LED VCC
Ground → LED GND + Pi GND
```

### Performance
- **Pi 4**: 500+ LEDs at 60 FPS
- **Pi 3**: 300+ LEDs at 60 FPS  
- **Pi Zero 2**: 200+ LEDs at 60 FPS

### Audio Setup (Pi)
```bash
# Install audio dependencies
sudo apt-get update
sudo apt-get install portaudio19-dev python3-pyaudio

# For system audio capture (optional)
sudo apt-get install pulseaudio-module-loopback
```

## 🎯 Advanced Usage

### Creating Custom Recipes
```python
# Add to RECIPES dictionary in led_orchestrator.py
"my_recipe": Recipe(
    name="Custom Effect",
    description="My custom LED recipe",
    base_colors=BaseColorConfig(
        colors=[Color(255, 255, 0)],  # Yellow
        mode=TransitionMode.STATIC
    ),
    effects=[
        EffectConfig("breathing", {"speed": 2.0}),
        EffectConfig("sparkle", {"density": 0.1})
    ]
)
```

### Smooth Recipe Transitions
```python
# Transition between recipes with custom timing
await recipe_manager.apply_recipe(RECIPES["recipe2"], transition_time=3.0)
```

### Real-time Effect Control
```python
# Change effect parameters while running
effect = controller.pipeline.get_effect(effect_id)
effect.update_parameters({"speed": 2.0, "sensitivity": 1.5})
```

## 🔍 Troubleshooting

### Audio Issues
- **No audio detected**: Check microphone permissions
- **Music not working**: Install system audio loopback (BlackHole on macOS)
- **Raspberry Pi audio**: Ensure ALSA/PulseAudio is configured

### Performance Issues  
- **Slow rendering**: Reduce pixel count or frame rate
- **High CPU**: Lower audio sample rate or disable effects
- **Memory usage**: Use fewer simultaneous effects

### LED Hardware Issues
- **No LEDs**: Check wiring and power supply
- **Wrong colors**: Verify LED type (WS2812B vs others)
- **Flickering**: Add level shifter or check power supply

## 📁 File Structure

```
led_ctrl/
├── led_orchestrator.py   # Main LED orchestrator with music visualization
├── pipeline_demo.py      # Effects pipeline and base effects
├── led_controller.py     # Color class and LED controller
├── mock_neopixel.py     # GUI simulator for testing
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## 🎵 Music Visualization Details

### Audio Processing
- **Sample Rate**: 22kHz (optimized for performance)
- **Block Size**: 512 samples (~23ms latency)
- **Frequency Bands**: 
  - Bass: 0-250Hz (kick drums, bass guitar)
  - Mid: 250-4000Hz (vocals, instruments)
  - High: 4000Hz+ (cymbals, harmonics)

### Beat Detection
- **Algorithm**: Bass spike detection with timing constraints
- **Threshold**: Configurable sensitivity
- **Debounce**: 100ms minimum between beats

### Performance Optimization
- **NumPy vectorization** for fast FFT processing
- **Logarithmic scaling** for better music dynamics
- **Dynamic range compression** for visible variations

## 🤝 Contributing

1. **Add new effects**: Extend the `Effect` base class
2. **Create recipes**: Add to `RECIPES` dictionary  
3. **Improve audio**: Enhance frequency analysis or beat detection
4. **Hardware support**: Add new LED controller types

## 📄 License

MIT License - Feel free to use and modify for your LED projects!

---

**🎵 Ready to light up your world with music-reactive LEDs!** ✨
