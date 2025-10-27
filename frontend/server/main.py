from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
import logging
import os
from pathlib import Path
from spotdl import Spotdl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Plex Sync API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
MUSIC_DIR = os.getenv("MUSIC_DIR", "./music")
SPOTDL_PATH = os.getenv("SPOTDL_PATH", "/app/spotdl-4.4.3-linux")
STATIC_DIR = os.getenv("STATIC_DIR", "/app/static")
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
client = Spotdl(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)

class SpotifyRequest(BaseModel):
    spotify_url: str


# API Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from spotdl._version import __version__
    return {
        "status": "healthy",
        "music_dir": MUSIC_DIR,
        "music_dir_exists": os.path.exists(MUSIC_DIR),
        "spotdl_version": __version__
    }


async def download_spotify_content(spotify_url: str):
    """Background task to download Spotify content"""
    try:
        logger.info(f"Starting download for: {spotify_url}")

        # Ensure music directory exists
        Path(MUSIC_DIR).mkdir(parents=True, exist_ok=True)

        # Run spotdl
        songs = client.search([spotify_url])
        logger.info(f"Found {len(songs)} songs for URL: {spotify_url}")
        results = client.download_songs(songs)
        logger.info(f"Results: {results}")

        # TODO Organize into plex format and store in PVC dir.
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


# Mount static files for assets (JS, CSS, images, etc.)
# This must come before the catch-all route
app.mount("/assets", StaticFiles(directory=f"{STATIC_DIR}/assets"), name="assets")

# If you have a docs directory
if os.path.exists(f"{STATIC_DIR}/docs"):
    app.mount("/docs", StaticFiles(directory=f"{STATIC_DIR}/docs", html=True), name="docs")


# Catch-all route for SPA - this must be last
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """
    Serve the React SPA for all non-API routes.
    This enables client-side routing.
    """
    # Try to serve the requested file if it exists
    file_path = Path(STATIC_DIR) / full_path

    # If it's a file and exists, serve it
    if file_path.is_file():
        return FileResponse(file_path)

    # Otherwise, serve index.html for SPA routing
    index_path = Path(STATIC_DIR) / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn

    if not CLIENT_ID or not CLIENT_SECRET:
        logger.error("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in environment variables.")
        exit(1)

    uvicorn.run(app, host="0.0.0.0", port=8000)