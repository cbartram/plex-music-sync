from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import subprocess
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Spotify to Plex API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
MUSIC_DIR = os.getenv("MUSIC_DIR", "/music")
SPOTDL_PATH = os.getenv("SPOTDL_PATH", "/app/spotdl-4.4.3-linux")


class SpotifyRequest(BaseModel):
    spotify_url: str


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "music_dir": MUSIC_DIR,
        "music_dir_exists": os.path.exists(MUSIC_DIR),
        "spotdl_available": check_spotdl_available()
    }


def check_spotdl_available():
    """Check if spotdl is available"""
    try:
        result = subprocess.run(
            [SPOTDL_PATH, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"SpotDL check failed: {e}")
        return False


async def download_spotify_content(spotify_url: str):
    """Background task to download Spotify content"""
    try:
        logger.info(f"Starting download for: {spotify_url}")

        # Ensure music directory exists
        Path(MUSIC_DIR).mkdir(parents=True, exist_ok=True)

        # Run spotdl
        cmd = [
            SPOTDL_PATH,
            "download",
            spotify_url,
            "--output", MUSIC_DIR,
            "--format", "mp3",
            "--bitrate", "320k"
        ]

        logger.info(f"Executing: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )

        if result.returncode == 0:
            logger.info(f"Download completed successfully: {spotify_url}")
            logger.info(f"Output: {result.stdout}")
        else:
            logger.error(f"Download failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        logger.error(f"Download timeout for: {spotify_url}")
    except Exception as e:
        logger.error(f"Download error: {str(e)}")


@app.post("/api/download")
async def download_spotify(
        request: SpotifyRequest,
        background_tasks: BackgroundTasks
):
    """
    Download Spotify track or playlist to Plex music directory
    """
    if not ("spotify.com" in request.spotify_url):
        raise HTTPException(
            status_code=400,
            detail="Invalid Spotify URL. Must be a spotify.com link."
        )

    if not check_spotdl_available():
        raise HTTPException(
            status_code=503,
            detail="SpotDL is not available. Please check the backend configuration."
        )

    if not os.path.exists(MUSIC_DIR):
        try:
            Path(MUSIC_DIR).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Cannot access music directory: {str(e)}"
            )

    background_tasks.add_task(download_spotify_content, request.spotify_url)

    return {
        "status": "started",
        "message": "Download started. Check logs for progress.",
        "spotify_url": request.spotify_url,
        "music_dir": MUSIC_DIR
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Plex Sync API",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)