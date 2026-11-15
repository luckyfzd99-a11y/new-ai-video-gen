from pathlib import Path
import shutil, subprocess, uuid, re, os
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent.parent
WORK = BASE / "work"
EXPORTS = BASE / "exports"
WORK.mkdir(exist_ok=True)
EXPORTS.mkdir(exist_ok=True)

app = FastAPI(title="Free AI Video Studio")
app.mount("/static", StaticFiles(directory=BASE / "app" / "static"), name="static")

def run_ffmpeg(args):
    try:
        p = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args,
                           capture_output=True, text=True, timeout=60*30)
    except FileNotFoundError:
        raise HTTPException(500, "FFmpeg was not found. Install FFmpeg and add it to PATH.")
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Rendering timed out.")
    if p.returncode != 0:
        raise HTTPException(500, "FFmpeg error: " + (p.stderr[-1800:] or "Unknown error"))
    return p

def font(size):
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf"
    ]
    for f in candidates:
        if Path(f).exists():
            try: return ImageFont.truetype(f, size)
            except Exception: pass
    return ImageFont.load_default()

def wrap_text(draw, text, fnt, max_width):
    words = text.split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        if draw.textbbox((0,0), test, font=fnt)[2] <= max_width:
            line = test
        else:
            if line: lines.append(line)
            line = word
    if line: lines.append(line)
    return lines or [""]

def make_card(text, path, width, height, index, total):
    img = Image.new("RGB", (width, height), (13, 22, 42))
    d = ImageDraw.Draw(img)
    # restrained gradient
    for y in range(height):
        t = y / max(1, height-1)
        c = (int(10+16*t), int(22+15*t), int(42+30*t))
        d.line((0,y,width,y), fill=c)
    margin = int(width * .09)
    d.rounded_rectangle((margin, margin, width-margin, height-margin),
                        radius=max(18, width//35), outline=(73, 153, 190), width=max(2,width//500))
    d.text((margin+25, margin+25), "YOUR STORY", font=font(max(18,width//45)), fill=(125,220,210))
    fnt = font(max(28, width//19))
    lines = wrap_text(d, text, fnt, width-2*margin-70)
    line_h = int(fnt.size*1.35) if hasattr(fnt,"size") else max(40,width//18)
    total_h = len(lines)*line_h
    y = (height-total_h)//2
    for line in lines:
        d.text((width//2, y), line, font=fnt, fill=(250,250,252), anchor="mm")
        y += line_h
    d.text((margin+25, height-margin-45), f"SCENE {index+1:02d} / {total:02d}",
           font=font(max(14,width//65)), fill=(170,190,210))
    img.save(path, quality=94)

def safe_name(name):
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name or "media")

def create_tts(text, out):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.save_to_file(text, str(out))
        engine.runAndWait()
        return out.exists() and out.stat().st_size > 100
    except Exception:
        return False

@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE / "app" / "static" / "index.html").read_text(encoding="utf-8")

@app.get("/api/health")
def health():
    ff = shutil.which("ffmpeg")
    return {"ok": True, "ffmpeg": bool(ff), "ffmpeg_path": ff}

@app.post("/api/render/story")
async def render_story(script: str = Form(...), aspect: str = Form("vertical"),
                       seconds_per_scene: int = Form(4), narration: bool = Form(False)):
    scenes = [s.strip() for s in re.split(r"[\n.!?]+", script) if s.strip()]
    if not scenes: raise HTTPException(400, "Please enter a story or script.")
    scenes = scenes[:40]
    width, height = (1080,1920) if aspect == "vertical" else (1920,1080)
    job = uuid.uuid4().hex[:10]
    folder = WORK/job; folder.mkdir()
    concat = folder/"list.txt"
    for i, scene in enumerate(scenes):
        p = folder/f"scene_{i:03d}.jpg"
        make_card(scene, p, width, height, i, len(scenes))
    concat.write_text("".join(f"file '{(folder/f'scene_{i:03d}.jpg').as_posix()}'\nduration {max(2,min(15,seconds_per_scene))}\n" for i in range(len(scenes))) +
                      f"file '{(folder/f'scene_{len(scenes)-1:03d}.jpg').as_posix()}'\n", encoding="utf-8")
    silent = folder/"silent.mp4"
    run_ffmpeg(["-f","concat","-safe","0","-i",str(concat),"-vsync","vfr","-pix_fmt","yuv420p","-c:v","libx264","-r","30",str(silent)])
    output = EXPORTS/f"story_{job}.mp4"
    if narration:
        audio = folder/"voice.wav"
        ok = create_tts(" ".join(scenes), audio)
        if ok:
            run_ffmpeg(["-i",str(silent),"-i",str(audio),"-c:v","copy","-c:a","aac","-shortest",str(output)])
        else:
            shutil.copy2(silent, output)
    else:
        shutil.copy2(silent, output)
    return {"ok":True,"file":output.name,"url":f"/exports/{output.name}","scenes":len(scenes),
            "note":None if not narration or (folder/"voice.wav").exists() else "Local TTS unavailable; exported without narration."}

@app.post("/api/render/images")
async def render_images(files: List[UploadFile] = File(...), audio: Optional[UploadFile] = File(None),
                        aspect: str = Form("vertical"), seconds_per_image: int = Form(3)):
    if not files: raise HTTPException(400,"Upload at least one image.")
    job=uuid.uuid4().hex[:10]; folder=WORK/job; folder.mkdir()
    width,height=(1080,1920) if aspect=="vertical" else (1920,1080)
    paths=[]
    for i, up in enumerate(files[:60]):
        ext=Path(up.filename or "").suffix.lower()
        if ext not in [".jpg",".jpeg",".png",".webp"]: continue
        dest=folder/f"image_{i:03d}{ext}"
        dest.write_bytes(await up.read())
        try:
            im=Image.open(dest).convert("RGB")
            # cover crop
            ratio=max(width/im.width,height/im.height)
            im=im.resize((int(im.width*ratio),int(im.height*ratio)))
            x=(im.width-width)//2; y=(im.height-height)//2
            im=im.crop((x,y,x+width,y+height))
            normalized=folder/f"frame_{i:03d}.jpg"; im.save(normalized,quality=93); paths.append(normalized)
        except Exception: continue
    if not paths: raise HTTPException(400,"No supported images were uploaded.")
    listing=folder/"list.txt"
    dur=max(2,min(15,seconds_per_image))
    listing.write_text("".join(f"file '{p.as_posix()}'\nduration {dur}\n" for p in paths)+f"file '{paths[-1].as_posix()}'\n",encoding="utf-8")
    silent=folder/"silent.mp4"
    run_ffmpeg(["-f","concat","-safe","0","-i",str(listing),"-vsync","vfr","-pix_fmt","yuv420p","-c:v","libx264","-r","30",str(silent)])
    output=EXPORTS/f"images_{job}.mp4"
    if audio and audio.filename:
        ap=folder/safe_name(audio.filename); ap.write_bytes(await audio.read())
        run_ffmpeg(["-i",str(silent),"-i",str(ap),"-c:v","copy","-c:a","aac","-shortest",str(output)])
    else: shutil.copy2(silent,output)
    return {"ok":True,"file":output.name,"url":f"/exports/{output.name}","images":len(paths)}

@app.post("/api/render/audio")
async def render_audio(audio: UploadFile = File(...), aspect: str = Form("vertical")):
    ext=Path(audio.filename or "").suffix.lower()
    if ext not in [".mp3",".wav",".m4a",".aac",".ogg"]: raise HTTPException(400,"Use MP3, WAV, M4A, AAC or OGG audio.")
    job=uuid.uuid4().hex[:10]; folder=WORK/job; folder.mkdir()
    ap=folder/("input"+ext); ap.write_bytes(await audio.read())
    width,height=(1080,1920) if aspect=="vertical" else (1920,1080)
    output=EXPORTS/f"audio_{job}.mp4"
    # Background plus centered waveform and original audio
    filt=f"color=c=#101b32:s={width}x{height}:r=30,format=yuv420p[bg];[0:a]showwaves=s={width-160}x{max(160,height//5)}:mode=cline:colors=0x55d6be:rate=30,format=rgba[wave];[bg][wave]overlay=(W-w)/2:(H-h)/2"
    run_ffmpeg(["-i",str(ap),"-filter_complex",filt,"-map","[out]"] if False else
               ["-i",str(ap),"-filter_complex",f"color=c=#101b32:s={width}x{height}:r=30[bg];[0:a]showwaves=s={width-160}x{max(160,height//5)}:mode=cline:colors=0x55d6be:rate=30[wave];[bg][wave]overlay=(W-w)/2:(H-h)/2[v]","-map","[v]","-map","0:a","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(output)])
    return {"ok":True,"file":output.name,"url":f"/exports/{output.name}"}

@app.get("/exports/{filename}")
def download_export(filename: str):
    path=EXPORTS/safe_name(filename)
    if not path.exists() or path.parent != EXPORTS: raise HTTPException(404,"Export not found.")
    return FileResponse(path,media_type="video/mp4",filename=path.name)
