import subprocess

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel

from backend.downloader import extract_info, start_download, get_job, get_history
from backend.config import load_config, save_config, get_download_folder

app = FastAPI(title="WAJA Video Grabber")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# --- Request models ---

class InfoRequest(BaseModel):
    url: str
    cookies_browser: str | None = None

class DownloadRequest(BaseModel):
    url: str
    format: str = "best"
    cookies_browser: str | None = None

class ConfigUpdate(BaseModel):
    download_folder: str | None = None
    default_format: str | None = None


# --- Routes ---

@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/api/info")
async def api_info(req: InfoRequest):
    try:
        return extract_info(req.url, req.cookies_browser)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/download")
async def api_download(req: DownloadRequest):
    job_id = start_download(req.url, req.format, req.cookies_browser)
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def api_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


@app.get("/api/history")
async def api_history():
    return get_history()


@app.post("/api/open-folder")
async def api_open_folder():
    folder = get_download_folder()
    subprocess.Popen(["open", folder])
    return {"ok": True}


@app.post("/api/pick-folder")
async def api_pick_folder():
    """Open macOS native folder picker and return the selected path."""
    current = get_download_folder()
    script = f'''
    set defaultFolder to POSIX file "{current}" as alias
    try
        set chosenFolder to choose folder with prompt "Choose download folder" default location defaultFolder
        return POSIX path of chosenFolder
    on error
        return ""
    end try
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=120,
    )
    folder = result.stdout.strip()
    if not folder:
        return {"folder": None}
    # Remove trailing slash for cleanliness
    folder = folder.rstrip("/")
    return {"folder": folder}


@app.get("/api/config")
async def api_get_config():
    return load_config()


@app.post("/api/config")
async def api_update_config(req: ConfigUpdate):
    cfg = load_config()
    if req.download_folder is not None:
        cfg["download_folder"] = req.download_folder
    if req.default_format is not None:
        cfg["default_format"] = req.default_format
    save_config(cfg)
    return cfg


# Serve static assets (css, js) — must be last (catch-all mount)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
