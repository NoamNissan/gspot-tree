from sound_controller import SoundController
from light_controller import LightController
from rfid_reader import RFIDReader
import os
import csv

SONGS_DIR = "songs"
CSV_FILE = "rfid_songs.csv"


def load_rfid_song_mapping(csv_path):
    mapping = {}
    try:
        with open(csv_path, newline="") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) >= 2:
                    code, filename = row[0].strip(), row[1].strip()
                    mapping[code] = filename
    except Exception as e:
        print(f"Error reading CSV mapping: {e}")
    return mapping


def main():
    sound = SoundController(SONGS_DIR)
    light = LightController()
    rfid = RFIDReader()
    code_to_song = load_rfid_song_mapping(CSV_FILE)

    print("Ready for RFID scans. Scan a tag to play a song.")
    while True:
        code = rfid.get_next_code()
        if not code:
            continue
        song_file = code_to_song.get(code)
        if not song_file:
            print(f"No song mapped for code: {code}")
            continue
        print(f"Scanned code: {code}. Playing {song_file}...")
        sound.play_song(song_file)
        # light.do_nothing()  # Placeholder for future light actions

if __name__ == "__main__":
    main()