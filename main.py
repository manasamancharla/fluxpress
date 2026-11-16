import os
import shutil
import uuid
import re
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import imageio_ffmpeg

# Directories setup
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
OUTPUT_DIR = BASE_DIR / "storage" / "outputs"
STATIC_DIR = BASE_DIR / "static"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# FFmpeg binary
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

app = FastAPI(title="FFmpeg Video Compressor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job registry for tracking progress
# job_id -> { status: "pending" | "processing" | "completed" | "failed", progress: float, ... }
jobs: Dict[str, Dict[str, Any]] = {}

def get_video_info(file_path: str) -> Dict[str, Any]:
    """Parse media details (duration, resolution, audio/video streams) using ffmpeg -i."""
    try:
        proc = subprocess.run(
            [FFMPEG_EXE, "-i", file_path],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        output = proc.stderr

        duration_sec = 0.0
        match_dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
        if match_dur:
            hours, mins, secs = match_dur.groups()
            duration_sec = int(hours) * 3600 + int(mins) * 60 + float(secs)

        width, height = None, None
        match_res = re.search(r"Stream #\d+:\d+.*Video:.*,\s*(\d{2,5})x(\d{2,5})", output)
        if match_res:
            width = int(match_res.group(1))
            height = int(match_res.group(2))

        bitrate = None
        match_br = re.search(r"bitrate:\s*(\d+)\s*kb/s", output)
        if match_br:
            bitrate = f"{match_br.group(1)} kb/s"

        file_size = os.path.getsize(file_path)

        return {
            "duration": duration_sec,
            "width": width,
            "height": height,
            "bitrate": bitrate,
            "file_size": file_size,
            "raw": output[:1000]
        }
    except Exception as e:
        return {"duration": 0.0, "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0, "error": str(e)}

async def run_compression_task(
    job_id: str,
    input_path: str,
    output_path: str,
    crf: int,
    preset: str,
    resolution: str,
    codec: str,
    audio_bitrate: str,
    fps: Optional[str] = None
):
    jobs[job_id]["status"] = "processing"
    jobs[job_id]["progress"] = 5

    info = get_video_info(input_path)
    total_duration = info.get("duration", 0.0)
    jobs[job_id]["input_info"] = info

    # Build FFmpeg command
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", input_path,
        "-c:v", codec,
        "-crf", str(crf),
        "-preset", preset,
        "-pix_fmt", "yuv420p"  # Ensure wide browser / player compatibility
    ]

    # Video filters (scaling, framerate)
    vf_filters = []
    if resolution and resolution != "original":
        if resolution == "1080p":
            vf_filters.append("scale='min(1920,iw)':'-2'")
        elif resolution == "720p":
            vf_filters.append("scale='min(1280,iw)':'-2'")
        elif resolution == "480p":
            vf_filters.append("scale='min(854,iw)':'-2'")
        elif resolution == "360p":
            vf_filters.append("scale='min(640,iw)':'-2'")
        elif resolution == "half":
            vf_filters.append("scale='iw/2':'-2'")

    if fps and fps != "original":
        vf_filters.append(f"fps={fps}")

    if vf_filters:
        cmd.extend(["-vf", ",".join(vf_filters)])

    # Audio encoding
    if audio_bitrate == "copy":
        cmd.extend(["-c:a", "copy"])
    else:
        cmd.extend(["-c:a", "aac", "-b:a", audio_bitrate])

    # MP4 faststart for web streaming / immediate browser playback
    cmd.extend(["-movflags", "+faststart", output_path])

    jobs[job_id]["command"] = " ".join(cmd)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        time_pattern = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")

        # Read stderr line-by-line for progress updates
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace")
            m = time_pattern.search(text)
            if m and total_duration > 0:
                h, mins, s = m.groups()
                curr_sec = int(h) * 3600 + int(mins) * 60 + float(s)
                pct = min(99.0, max(5.0, (curr_sec / total_duration) * 100.0))
                jobs[job_id]["progress"] = round(pct, 1)

        await proc.wait()

        if proc.returncode == 0 and os.path.exists(output_path):
            out_info = get_video_info(output_path)
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["progress"] = 100.0
            jobs[job_id]["output_info"] = out_info
            
            in_size = jobs[job_id]["input_info"].get("file_size", 1)
            out_size = out_info.get("file_size", 0)
            reduction = max(0.0, ((in_size - out_size) / in_size) * 100.0) if in_size > 0 else 0.0
            jobs[job_id]["reduction_pct"] = round(reduction, 1)
        else:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = f"FFmpeg failed with exit code {proc.returncode}"
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


@app.post("/api/compress")
async def compress_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    crf: int = Form(23),
    preset: str = Form("medium"),
    resolution: str = Form("original"),
    codec: str = Form("libx264"),
    audio_bitrate: str = Form("128k"),
    fps: str = Form("original")
):
    """
    Handle video upload and start compression in background.
    CRF guide:
    - 18: Near lossless, visually transparent
    - 23: Default, excellent balance between quality and compression
    - 28: Noticeable compression, much smaller file size
    - 32+: Aggressive compression
    """
    # Validation
    if crf < 0 or crf > 51:
        raise HTTPException(status_code=400, detail="CRF must be between 0 (lossless) and 51 (lowest quality).")
    
    valid_presets = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]
    if preset not in valid_presets:
        preset = "medium"

    valid_codecs = ["libx264", "libx265"]
    if codec not in valid_codecs:
        codec = "libx264"

    job_id = str(uuid.uuid4())
    safe_filename = Path(file.filename or "video.mp4").name
    stem = Path(safe_filename).stem
    input_file = UPLOAD_DIR / f"{job_id}_{safe_filename}"
    output_filename = f"{stem}_compressed_crf{crf}.mp4"
    output_file = OUTPUT_DIR / f"{job_id}_{output_filename}"

    # Save uploaded file
    try:
        with open(input_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")
    finally:
        file.file.close()

    # Pre-read input info
    in_info = get_video_info(str(input_file))

    jobs[job_id] = {
        "job_id": job_id,
        "filename": safe_filename,
        "output_filename": output_filename,
        "status": "pending",
        "progress": 0.0,
        "crf": crf,
        "preset": preset,
        "resolution": resolution,
        "codec": codec,
        "audio_bitrate": audio_bitrate,
        "input_path": str(input_file),
        "output_path": str(output_file),
        "input_info": in_info,
        "output_info": None,
        "reduction_pct": 0.0
    }

    # Dispatch async compression
    background_tasks.add_task(
        run_compression_task,
        job_id,
        str(input_file),
        str(output_file),
        crf,
        preset,
        resolution,
        codec,
        audio_bitrate,
        fps
    )

    return JSONResponse(content={
        "job_id": job_id,
        "status": "pending",
        "filename": safe_filename,
        "input_info": in_info
    })

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JSONResponse(content={
        "job_id": job["job_id"],
        "status": job["status"],
        "progress": job.get("progress", 0),
        "reduction_pct": job.get("reduction_pct", 0),
        "input_info": job.get("input_info"),
        "output_info": job.get("output_info"),
        "error": job.get("error"),
        "download_url": f"/api/download/{job_id}" if job["status"] == "completed" else None,
        "preview_url": f"/api/preview/{job_id}" if job["status"] == "completed" else None
    })

@app.get("/api/download/{job_id}")
async def download_compressed(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "completed" or not os.path.exists(job["output_path"]):
        raise HTTPException(status_code=400, detail="Compression not finished or file missing")
    
    return FileResponse(
        path=job["output_path"],
        filename=job["output_filename"],
        media_type="video/mp4"
    )

@app.get("/api/preview/{job_id}")
async def preview_compressed(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "completed" or not os.path.exists(job["output_path"]):
        raise HTTPException(status_code=400, detail="File not ready")
    
    return FileResponse(
        path=job["output_path"],
        media_type="video/mp4"
    )

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "ffmpeg": FFMPEG_EXE,
        "active_jobs": len(jobs)
    }

# Mount static folder
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>FFmpeg Compressor</h1><p>UI is initializing...</p>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
