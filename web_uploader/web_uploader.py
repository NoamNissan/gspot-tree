#!/usr/bin/env python3
"""
Simple web file uploader for Raspberry Pi
Allows uploading music files from phone/PC to an uploads directory
"""

from flask import Flask, request, render_template_string, redirect, url_for
import os
import argparse

app = Flask(__name__)

# Default uploads directory
DEFAULT_UPLOADS_DIR = "../songs"
UPLOADS_DIR = DEFAULT_UPLOADS_DIR

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Music Uploader</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            margin-bottom: 30px;
        }
        h2 {
            color: #555;
            margin-top: 40px;
            margin-bottom: 20px;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }
        .upload-form {
            margin: 20px 0;
        }
        input[type="file"] {
            display: block;
            margin: 20px 0;
            padding: 10px;
            width: 100%;
            border: 2px dashed #ccc;
            border-radius: 5px;
        }
        button {
            background: #4CAF50;
            color: white;
            padding: 15px 30px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
        }
        button:hover {
            background: #45a049;
        }
        .message {
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }
        .success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .info {
            color: #666;
            font-size: 14px;
            margin-top: 20px;
        }
        .file-list {
            list-style: none;
            padding: 0;
        }
        .file-list li {
            padding: 10px;
            margin: 5px 0;
            background: #f9f9f9;
            border-radius: 5px;
            display: flex;
            align-items: center;
        }
        .file-list li.directory {
            background: #e3f2fd;
            font-weight: bold;
            cursor: pointer;
        }
        .file-list li.directory:hover {
            background: #bbdefb;
        }
        .file-list li.directory a {
            text-decoration: none;
            color: inherit;
            display: flex;
            align-items: center;
            width: 100%;
        }
        .file-icon {
            margin-right: 10px;
            font-size: 18px;
        }
        .empty-message {
            color: #999;
            font-style: italic;
            padding: 20px;
            text-align: center;
        }
        .breadcrumb {
            padding: 10px 0;
            margin-bottom: 20px;
            color: #666;
        }
        .breadcrumb a {
            color: #4CAF50;
            text-decoration: none;
        }
        .breadcrumb a:hover {
            text-decoration: underline;
        }
        .breadcrumb span {
            margin: 0 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Music Uploader</h1>
        
        {% if message %}
        <div class="message {{ message_type }}">
            {{ message }}
        </div>
        {% endif %}
        
        <form class="upload-form" method="POST" enctype="multipart/form-data">
            <input type="file" name="file" accept="audio/*,.mp3,.wav,.m4a,.flac" required multiple>
            <button type="submit">Upload Music</button>
        </form>
        
        <div class="info">
            <p>📁 Upload directory: {{ uploads_dir }}</p>
            <p>Supported formats: MP3, WAV, M4A, FLAC</p>
        </div>
        
        <h2>📂 Files & Directories</h2>
        
        {% if current_path %}
        <div class="breadcrumb">
            <a href="/">📁 {{ root_name }}</a>
            {% for part in breadcrumbs %}
            <span>/</span>
            <a href="?path={{ part.path }}">{{ part.name }}</a>
            {% endfor %}
        </div>
        {% endif %}
        
        {% if files %}
        <ul class="file-list">
            {% for item in files %}
            <li class="{{ 'directory' if item.is_dir else '' }}">
                {% if item.is_dir %}
                <a href="?path={{ item.path }}">
                    <span class="file-icon">📁</span>
                    {{ item.name }}
                </a>
                {% else %}
                <span class="file-icon">🎵</span>
                {{ item.name }}
                {% endif %}
            </li>
            {% endfor %}
        </ul>
        {% else %}
        <div class="empty-message">No files yet. Upload some music!</div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    message = None
    message_type = None
    
    # Get current path from query parameter
    current_path = request.args.get('path', '')
    
    # Sanitize path - ensure it stays within UPLOADS_DIR
    if current_path:
        current_path = current_path.strip('/')
        # Prevent directory traversal
        if '..' in current_path or current_path.startswith('/'):
            current_path = ''
    
    # Full path to current directory
    full_path = os.path.join(UPLOADS_DIR, current_path) if current_path else UPLOADS_DIR
    
    # Ensure path is within UPLOADS_DIR
    full_path = os.path.abspath(full_path)
    uploads_abs = os.path.abspath(UPLOADS_DIR)
    if not full_path.startswith(uploads_abs):
        current_path = ''
        full_path = uploads_abs
    
    if request.method == 'POST':
        if 'file' not in request.files:
            message = "No file selected"
            message_type = "error"
        else:
            files = request.files.getlist('file')
            uploaded = []
            errors = []
            
            for file in files:
                if file.filename == '':
                    continue
                    
                # Sanitize filename
                filename = os.path.basename(file.filename)
                filepath = os.path.join(full_path, filename)
                
                try:
                    file.save(filepath)
                    uploaded.append(filename)
                except Exception as e:
                    errors.append(f"{filename}: {str(e)}")
            
            if uploaded:
                message = f"✅ Uploaded {len(uploaded)} file(s): {', '.join(uploaded)}"
                message_type = "success"
            if errors:
                message = (message or "") + f"\n❌ Errors: {', '.join(errors)}"
                message_type = "error" if not uploaded else "success"
    
    # Build breadcrumbs
    breadcrumbs = []
    if current_path:
        parts = current_path.split('/')
        path_so_far = ''
        for part in parts:
            path_so_far = os.path.join(path_so_far, part) if path_so_far else part
            breadcrumbs.append({
                'name': part,
                'path': path_so_far
            })
    
    # Get list of files and directories
    files_list = []
    try:
        for item in sorted(os.listdir(full_path)):
            item_path = os.path.join(full_path, item)
            item_rel_path = os.path.join(current_path, item) if current_path else item
            files_list.append({
                'name': item,
                'is_dir': os.path.isdir(item_path),
                'path': item_rel_path
            })
    except Exception as e:
        print(f"Error listing files: {e}")
    
    return render_template_string(
        HTML_TEMPLATE,
        message=message,
        message_type=message_type,
        uploads_dir=os.path.abspath(full_path),
        files=files_list,
        current_path=current_path,
        breadcrumbs=breadcrumbs,
        root_name=os.path.basename(os.path.abspath(UPLOADS_DIR))
    )

def main():
    global UPLOADS_DIR
    
    parser = argparse.ArgumentParser(description='Simple web file uploader')
    parser.add_argument('--uploads-dir', default=DEFAULT_UPLOADS_DIR,
                        help=f'Uploads directory (default: {DEFAULT_UPLOADS_DIR})')
    parser.add_argument('--port', type=int, default=5500,
                        help='Port to run on (default: 5500)')
    parser.add_argument('--host', default='0.0.0.0',
                        help='Host to bind to (default: 0.0.0.0)')
    
    args = parser.parse_args()
    
    # Set uploads directory
    UPLOADS_DIR = args.uploads_dir
    
    # Create uploads directory if it doesn't exist
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    
    print(f"🎵 Music Uploader starting...")
    print(f"📁 Uploads directory: {os.path.abspath(UPLOADS_DIR)}")
    print(f"🌐 Server: http://{args.host}:{args.port}")
    print(f"Press Ctrl+C to stop")
    
    app.run(host=args.host, port=args.port, debug=False)

if __name__ == '__main__':
    main()
