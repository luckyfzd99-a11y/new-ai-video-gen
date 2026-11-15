# Free AI Video Studio

A local-first, open-source video maker that runs on Windows/Linux/macOS and in a browser on your local network. No paid API keys are required.

## What it can do

- **Story / text videos:** turn a script into title-and-scene cards; optionally generate narration with local `pyttsx3` TTS.
- **Images to video:** combine uploaded images into a slideshow with optional narration/music.
- **Audio to video:** create an audio waveform visualizer video from an MP3/WAV file.
- **Shorts / Reels:** export vertical 9:16 videos (1080x1920).
- **YouTube videos:** export landscape 16:9 videos (1920x1080).
- **Browser UI:** use the web interface from the same PC or another device on your Wi-Fi.
- **No cloud API dependency:** rendering is done locally with FFmpeg and Pillow.

> Important: this first version creates motion-graphics/story-card videos and audio visualizers. It does **not** generate photorealistic AI video from a text prompt by itself. For that, connect a locally hosted ComfyUI workflow in a later phase; video-generation models generally need substantial disk space and a capable GPU.

## Requirements

- Python 3.10+
- FFmpeg installed and available on PATH (`ffmpeg -version` should work)
- Optional: local TTS support via `pyttsx3` (included in requirements; operating-system voice engines may need setup)

## Windows quick start

1. Install Python 3.10+ from https://www.python.org/downloads/ (enable **Add Python to PATH**).
2. Install FFmpeg. One option is `winget install Gyan.FFmpeg`, then reopen PowerShell.
3. Extract this project.
4. Double-click `start_windows.bat`, or run:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

5. Open http://127.0.0.1:8000

## Use from your phone / another PC on the same Wi-Fi

Run `python run.py --host 0.0.0.0`, find your PC's local IPv4 address with `ipconfig`, then open `http://YOUR-PC-IP:8000` on the other device. Allow Python through Windows Firewall on private networks if prompted. Do not expose this development server directly to the public internet.

## Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Install FFmpeg using your package manager (for example `sudo apt install ffmpeg` on Ubuntu or `brew install ffmpeg` on macOS).

## Project layout

```text
app/
  main.py              FastAPI endpoints and rendering pipeline
  static/
    index.html         Browser interface
    app.js             Frontend logic
    style.css          Styling
requirements.txt
run.py
start_windows.bat
Dockerfile
```

## Export notes

- Rendering happens on your computer, so speed depends on CPU, RAM and source media.
- Uploads are temporary and stored under `work/`; exported MP4 files are stored under `exports/`.
- Keep ownership/licensing rights for images, music, voices and other media you use.
- This is an MVP. Add authentication before hosting it publicly.

## GitHub

Create a **public** repository named `free-ai-video-studio`, upload these files, and keep the repository free. GitHub stores the source code; it does not provide free unlimited video rendering. Render videos on your own PC.
