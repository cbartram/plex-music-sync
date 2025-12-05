import os
import asyncio
import logging
import time
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks, Security, Depends, status
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
from pydantic import BaseModel
from pathlib import Path
from spotdl import Spotdl
from spotdl.types.options import DownloaderOptions
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MUSIC_DIR = os.getenv("MUSIC_DIR", "./music")
STATIC_DIR = os.getenv("STATIC_DIR", "/app/static")
COOKIES_FILE = os.getenv("COOKIES_FILE", "/app/cookies.txt")
APP_AUTH_KEY = os.getenv("APP_AUTH_KEY", "DEFAULT_APP_AUTH_KEY_WILL_NOT_WORK_IN_PROD")
API_KEY_NAME = "X-API-Key"

_spotdl_client = None
_client_lock = threading.Lock()

# --- JOB STORAGE ---
# In a production app with multiple replicas, you would use Redis here.
# For a single pod, this in-memory dict works fine.
JOBS = {}

app = FastAPI(title="Plex Sync API", version="1.0.0")
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == APP_AUTH_KEY:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate credentials"
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SpotifyRequest(BaseModel):
    spotify_url: str


def get_or_create_spotdl_client():
    global _spotdl_client
    with _client_lock:
        if _spotdl_client is None:
            cookies = read_cookies_files()
            if cookies is None:
                # We log this but don't crash yet, individual jobs will fail gracefully
                logger.error("Failed to read cookies.txt file contents.")

            # Using empty token if not provided
            po_token = ""

            _spotdl_client = Spotdl(
                client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                downloader_settings=DownloaderOptions(
                    output=MUSIC_DIR + "/{artists}/{album}/{title}.{output-ext}",
                    threads=4,
                    cookie_file=cookies,
                    yt_dlp_args=f"--extractor-args \"youtube:player_client=web_music,default;po_token=web_music+{po_token}\""
                ),
            )
        return _spotdl_client


# Helper to log to both system stdout and the specific job storage
def job_log(job_id: str, message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"

    # Update Job Store
    if job_id in JOBS:
        JOBS[job_id]["logs"].append(log_entry)

    # Update System Log
    if level == "ERROR":
        logger.error(f"[{job_id}] {message}")
    else:
        logger.info(f"[{job_id}] {message}")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/download", dependencies=[Depends(get_api_key)])
async def download_spotify(
        request: SpotifyRequest,
        background_tasks: BackgroundTasks
):
    """
    Download Spotify track or playlist to Plex music directory
    """
    if "spotify.com" not in request.spotify_url:
        raise HTTPException(status_code=400, detail="Invalid Spotify URL.")

    if not os.path.exists(MUSIC_DIR):
        try:
            Path(MUSIC_DIR).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Cannot access music directory: {str(e)}"
            )

    # Generate a new Job ID
    job_id = str(uuid.uuid4())

    # Initialize Job State
    JOBS[job_id] = {
        "status": "processing",
        "logs": [],
        "created_at": datetime.now().isoformat(),
        "url": request.spotify_url
    }

    background_tasks.add_task(download_spotify_content, job_id, request.spotify_url)

    return {
        "status": "started",
        "job_id": job_id,
        "message": "Download started.",
        "spotify_url": request.spotify_url
    }


@app.get("/api/jobs/{job_id}", dependencies=[Depends(get_api_key)])
async def get_job_status(job_id: str):
    """
    Poll this endpoint to get logs and status
    """
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    return JOBS[job_id]


# Mount static files
app.mount("/assets", StaticFiles(directory=f"{STATIC_DIR}/assets"), name="assets")
if os.path.exists(f"{STATIC_DIR}/docs"):
    app.mount("/docs", StaticFiles(directory=f"{STATIC_DIR}/docs", html=True), name="docs")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    file_path = Path(STATIC_DIR) / full_path
    if file_path.is_file():
        return FileResponse(file_path)
    index_path = Path(STATIC_DIR) / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    # Don't 404 immediately, try serving index for client-side routing if applicable
    # or just return 404 if it's clearly a missing asset
    if "." not in full_path:
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")


def read_cookies_files() -> str | None:
    try:
        if os.path.exists(COOKIES_FILE):
            return COOKIES_FILE  # SpotDL expects a path, not the content string for 'cookie_file'
    except Exception as e:
        logger.error(f"Error checking cookie file: {e}")
    return None


def download_spotify_content(job_id: str, spotify_url: str, max_attempts: int = 3):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        client = get_or_create_spotdl_client()
        job_log(job_id, f"Job started for: {spotify_url}")

        for attempt in range(max_attempts):
            try:
                job_log(job_id, f"Starting download (Attempt {attempt + 1}/{max_attempts})")
                Path(MUSIC_DIR).mkdir(parents=True, exist_ok=True)

                if attempt > 0:
                    wait_time = 2 ** attempt
                    job_log(job_id, f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)

                job_log(job_id, "Searching for songs...")
                songs = client.search([spotify_url])

                job_log(job_id, f"Found {len(songs)} songs. Starting download...")

                # SpotDL download_songs returns path list
                results = client.download_songs(songs)

                job_log(job_id, f"Successfully downloaded {len(results)} songs.")

                # Mark Complete
                JOBS[job_id]["status"] = "completed"
                JOBS[job_id]["result"] = f"Downloaded {len(results)} files"

                loop.close()
                return results

            except Exception as e:
                error_msg = str(e)
                job_log(job_id, f"Error: {error_msg}", level="ERROR")

                if "429" in error_msg or "rate" in error_msg.lower():
                    if attempt < max_attempts - 1:
                        sleep_time = 60 * (attempt + 1)
                        job_log(job_id, f"Rate limited. Sleeping {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue

                if attempt == max_attempts - 1:
                    JOBS[job_id]["status"] = "failed"
                    JOBS[job_id]["error"] = error_msg
                    loop.close()
                    raise
    except Exception as outer_e:
        JOBS[job_id]["status"] = "failed"
        job_log(job_id, f"Critical failure: {str(outer_e)}", level="ERROR")
    finally:
        if loop.is_running():
            loop.close()


if __name__ == "__main__":
    if not os.getenv("SPOTIFY_CLIENT_ID") or not os.getenv("SPOTIFY_CLIENT_SECRET"):
        logger.error("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")
        exit(1)

    logger.info("Starting API")
    uvicorn.run(app, host="0.0.0.0", port=8000)