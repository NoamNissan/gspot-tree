# Music Uploader

Simple web interface for uploading music files to the Raspberry Pi.

## Features
- Upload music files from phone/PC to Raspberry Pi
- Supports multiple file upload
- Browse and navigate through directories
- Click on folders to view their contents
- Breadcrumb navigation
- Runs on port 5500 (separate from web controller)
- Only writes to specified uploads directory (sandboxed)

## Usage

```bash
# Default (uploads to ../songs)
python web_uploader.py

# Custom uploads directory
python web_uploader.py --uploads-dir /path/to/music

# Custom port
python web_uploader.py --port 8000
```

## Access
Open in browser: `http://raspberry-pi-ip:5500`

## Supported Formats
MP3, WAV, M4A, FLAC

## Security
- All file operations are restricted to the uploads directory
- Directory traversal attacks are prevented
- Cannot access files outside the specified uploads folder
